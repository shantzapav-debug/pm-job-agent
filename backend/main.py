"""
FastAPI backend — Google Sheets as DB, JWT auth, multi-user, rate limiting.
"""
import io
import json
import logging
import os
from datetime import datetime, timezone
from typing import Optional

import pdfplumber
from dotenv import load_dotenv
from fastapi import BackgroundTasks, Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from agents.auto_apply import try_apply
from agents.job_scraper import scrape_all_jobs
from agents.resume_tailor import tailor_resume
from auth import (
    SCRAPE_COOLDOWN_MINUTES, check_scrape_cooldown, create_token, create_user,
    decode_token, get_user_by_email, get_user_by_id, update_last_scrape,
    update_resume,
)
from sheets_db import PipelineState, SheetsDB, init_sheets

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Pavan Job Agent API", version="3.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

bearer = HTTPBearer(auto_error=False)


# ─────────────── AUTH HELPERS ───────────────

def get_current_user(creds: HTTPAuthorizationCredentials = Depends(bearer)) -> dict:
    if not creds:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = decode_token(creds.credentials)
        user = get_user_by_id(payload["sub"])
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        return user
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


def get_optional_user(creds: HTTPAuthorizationCredentials = Depends(bearer)) -> dict | None:
    if not creds:
        return None
    try:
        payload = decode_token(creds.credentials)
        return get_user_by_id(payload["sub"])
    except Exception:
        return None


# ─────────────── STARTUP ───────────────

@app.on_event("startup")
def startup():
    try:
        init_sheets()
        logger.info("Google Sheets initialized")
    except Exception as e:
        logger.warning(f"Sheets init skipped: {e}")


# ─────────────── AUTH ROUTES ───────────────

class SignupRequest(BaseModel):
    email: str
    password: str
    name: str


class LoginRequest(BaseModel):
    email: str
    password: str


@app.post("/api/auth/signup")
def signup(body: SignupRequest):
    try:
        if get_user_by_email(body.email):
            raise HTTPException(status_code=400, detail="Email already registered")
        user = create_user(body.email, body.password, body.name)
        token = create_token(user["id"], user["email"])
        return {"token": token, "user": {"id": user["id"], "email": user["email"], "name": user["name"]}}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Signup error: {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {str(e)}")


@app.post("/api/auth/login")
def login(body: LoginRequest):
    from auth import verify_password
    user = get_user_by_email(body.email)
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = create_token(user["id"], user["email"])
    return {"token": token, "user": {"id": user["id"], "email": user["email"], "name": user["name"]}}


@app.get("/api/auth/me")
def me(user: dict = Depends(get_current_user)):
    return {
        "id": user["id"], "email": user["email"], "name": user["name"],
        "target_role": user.get("target_role", ""), "target_location": user.get("target_location", ""),
        "has_resume": bool(user.get("resume_text")),
    }


# ─────────────── RESUME UPLOAD ───────────────

@app.post("/api/resume/upload")
async def upload_resume(
    file: UploadFile = File(...),
    target_role: str = "product manager",
    target_location: str = "Bengaluru",
    user: dict = Depends(get_current_user),
):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files supported")

    content = await file.read()
    try:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            resume_text = "\n".join(p.extract_text() or "" for p in pdf.pages).strip()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not read PDF: {e}")

    if len(resume_text) < 100:
        raise HTTPException(status_code=400, detail="PDF appears empty or unreadable")

    # Save resume + preferences
    update_resume(user["id"], resume_text, target_role, target_location)

    # Claude analyzes the resume and recommends roles + skill gaps
    analysis = _analyze_resume(resume_text, target_role)

    return {
        "message": "Resume uploaded successfully",
        "word_count": len(resume_text.split()),
        "analysis": analysis,
    }


def _analyze_resume(resume_text: str, target_role: str) -> dict:
    import anthropic
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        return {"recommended_roles": [], "skill_gaps": [], "strengths": [], "summary": ""}

    client = anthropic.Anthropic(api_key=api_key)
    prompt = f"""Analyze this resume for someone targeting "{target_role}" roles.

Return ONLY valid JSON with this structure:
{{
  "summary": "<2-sentence summary of the candidate>",
  "strengths": ["<strength1>", "<strength2>", "<strength3>"],
  "recommended_roles": ["<role1>", "<role2>", "<role3>"],
  "skill_gaps": ["<gap1>", "<gap2>", "<gap3>"],
  "suggested_keywords": ["<kw1>", "<kw2>", "<kw3>"]
}}

Resume:
{resume_text[:3000]}"""

    try:
        import re
        msg = client.messages.create(model="claude-sonnet-4-6", max_tokens=800,
                                     messages=[{"role": "user", "content": prompt}])
        raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", msg.content[0].text.strip())
        return json.loads(raw)
    except Exception as e:
        logger.warning(f"Resume analysis failed: {e}")
        return {"summary": "", "strengths": [], "recommended_roles": [], "skill_gaps": [], "suggested_keywords": []}


# ─────────────── PIPELINE ───────────────

class SearchRequest(BaseModel):
    keyword: str = "product manager"
    location: str = "Bengaluru"
    max_jobs: int = 30
    auto_apply: bool = True
    additional_requirements: Optional[str] = None  # user's extra requirements


def run_pipeline(req: SearchRequest, user_id: str, resume_text: str):
    db = SheetsDB()
    ps = PipelineState()
    ps.set(running=True, progress="Scraping jobs...", jobs_found=0, jobs_tailored=0, jobs_applied=0)

    try:
        raw_jobs = scrape_all_jobs(req.keyword, req.location)
        raw_jobs = raw_jobs[:req.max_jobs]
        ps.set(running=True, progress=f"Found {len(raw_jobs)} jobs. Saving...", jobs_found=len(raw_jobs))

        existing_ids = db.get_all_external_ids()
        saved_count = 0

        for idx, raw in enumerate(raw_jobs):
            if raw["job_id_external"] in existing_ids:
                continue
            db.add_job({
                **raw,
                "tailored_resume_text": "",
                "original_resume_text": "",
                "changes_log": [],
                "change_percentage": 0.0,
                "keywords_added": [],
                "status": "manual",
                "applied_at": "",
                "apply_note": "Ready — tailor & apply manually via link",
                "user_id": user_id,
            })
            saved_count += 1
            if idx % 5 == 0:
                ps.set(running=True,
                       progress=f"Saved {saved_count} new jobs...",
                       jobs_found=len(raw_jobs), jobs_tailored=0, jobs_applied=0)

        update_last_scrape(user_id)
        ps.set(running=False, progress=f"Done — {saved_count} new jobs found. Tap a job to tailor your resume.",
               jobs_found=len(raw_jobs), jobs_tailored=0, jobs_applied=saved_count)

    except Exception as e:
        logger.error(f"Pipeline error: {e}")
        ps.set(running=False, progress=f"Error: {str(e)[:100]}")


@app.post("/api/jobs/search")
async def search_jobs(req: SearchRequest, background_tasks: BackgroundTasks,
                      user: dict = Depends(get_current_user)):
    ps = PipelineState()
    if ps.get()["running"]:
        raise HTTPException(status_code=409, detail="Pipeline already running")

    can_scrape, next_at = check_scrape_cooldown(user)
    if not can_scrape:
        raise HTTPException(status_code=429, detail=f"Rate limited. Next scrape allowed at: {next_at}")

    resume_text = user.get("resume_text", "")
    background_tasks.add_task(run_pipeline, req, user["id"], resume_text)
    return {"message": "Pipeline started"}


# ─────────────── JOBS ───────────────

@app.get("/api/jobs")
def list_jobs(status: Optional[str] = None, source: Optional[str] = None,
              search: Optional[str] = None, user: dict = Depends(get_current_user)):
    db = SheetsDB()
    jobs = db.list_jobs(user_id=user["id"], status=status, source=source, search=search)
    return {"total": len(jobs), "jobs": jobs}


@app.get("/api/jobs/{job_id}")
def get_job(job_id: int, user: dict = Depends(get_current_user)):
    db = SheetsDB()
    job = db.get_job(job_id, include_resume=True, user_id=user["id"])
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.get("/api/jobs/{job_id}/resume")
def get_resume(job_id: int, user: dict = Depends(get_current_user)):
    db = SheetsDB()
    job = db.get_job(job_id, include_resume=True, user_id=user["id"])
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {
        "job_id": job_id, "title": job["title"], "company": job["company"],
        "tailored_resume_text": job.get("tailored_resume_text", ""),
        "original_resume_text": job.get("original_resume_text", ""),
        "changes_log": job.get("changes_log", []),
        "change_percentage": job.get("change_percentage", 0),
        "keywords_added": job.get("keywords_added", []),
    }


@app.get("/api/jobs/{job_id}/resume/pdf")
def download_resume_pdf(job_id: int, user: dict = Depends(get_current_user)):
    db = SheetsDB()
    job = db.get_job(job_id, include_resume=True, user_id=user["id"])
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    text = job.get("tailored_resume_text") or job.get("original_resume_text") or ""
    if not text.strip():
        raise HTTPException(status_code=404, detail="No resume text available for this job")

    buf = _build_resume_pdf(text, job.get("title", ""), job.get("company", ""))
    safe_name = f"resume_{job.get('company', 'job')}_{job.get('title', '')}.pdf".replace(" ", "_")
    return StreamingResponse(
        buf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}"'},
    )


def _build_resume_pdf(resume_text: str, role: str, company: str) -> io.BytesIO:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=0.75 * inch, rightMargin=0.75 * inch,
        topMargin=0.75 * inch, bottomMargin=0.75 * inch,
    )
    styles = getSampleStyleSheet()
    normal = ParagraphStyle("body", parent=styles["Normal"], fontSize=10, leading=14, spaceAfter=4)
    heading = ParagraphStyle("head", parent=styles["Normal"], fontSize=12, leading=16,
                             fontName="Helvetica-Bold", spaceAfter=6, spaceBefore=10)
    sub = ParagraphStyle("sub", parent=styles["Normal"], fontSize=10, leading=14,
                         fontName="Helvetica-BoldOblique", spaceAfter=4)

    story = []
    for line in resume_text.split("\n"):
        stripped = line.strip()
        if not stripped:
            story.append(Spacer(1, 6))
            continue
        # Simple heuristic: ALL CAPS short line → section heading
        if stripped.isupper() and len(stripped) < 60:
            story.append(Paragraph(stripped, heading))
        elif stripped.startswith("•") or stripped.startswith("-"):
            bullet_text = stripped.lstrip("•-").strip()
            story.append(Paragraph(f"• {bullet_text}", normal))
        else:
            story.append(Paragraph(stripped, normal))

    try:
        doc.build(story)
    except Exception as e:
        logger.warning(f"PDF build error: {e}; falling back to plain layout")
        buf = io.BytesIO()
        doc2 = SimpleDocTemplate(buf, pagesize=A4)
        doc2.build([Paragraph(resume_text.replace("\n", "<br/>"), styles["Normal"])])

    buf.seek(0)
    return buf


class ManualApplyRequest(BaseModel):
    note: Optional[str] = "Applied manually"


@app.post("/api/jobs/{job_id}/apply")
def mark_applied(job_id: int, body: ManualApplyRequest, user: dict = Depends(get_current_user)):
    db = SheetsDB()
    if not db.get_job(job_id, user_id=user["id"]):
        raise HTTPException(status_code=404, detail="Job not found")
    db.update_job(job_id, {"status": "applied",
                            "applied_at": datetime.now(timezone.utc).isoformat(),
                            "apply_note": body.note or "Applied manually"})
    return {"message": "Marked as applied"}


class RetailorRequest(BaseModel):
    jd_override: Optional[str] = None


@app.post("/api/jobs/{job_id}/retailor")
def retailor_job(job_id: int, body: RetailorRequest, user: dict = Depends(get_current_user)):
    db = SheetsDB()
    job = db.get_job(job_id, include_resume=True, user_id=user["id"])
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    jd = body.jd_override or job.get("description", "")
    if not jd:
        raise HTTPException(status_code=400, detail="No JD available")
    resume_text = user.get("resume_text") or None
    result = tailor_resume(jd, company=job["company"], role=job["title"],
                           resume_text_override=resume_text)
    db.update_job(job_id, {
        "tailored_resume_text": result["tailored_resume_text"],
        "original_resume_text": result["original_resume_text"],
        "changes_log": result["changes_log"],
        "change_percentage": result["change_percentage"],
        "keywords_added": result["keywords_added"],
    })
    return {"message": "Re-tailored", "change_percentage": result["change_percentage"]}


@app.delete("/api/jobs/{job_id}")
def delete_job(job_id: int, user: dict = Depends(get_current_user)):
    db = SheetsDB()
    db.delete_job(job_id)
    return {"message": "Deleted"}


# ─────────────── STATUS ───────────────

@app.get("/api/status")
def get_status(user: dict = Depends(get_optional_user)):
    db = SheetsDB()
    ps = PipelineState()
    uid = user["id"] if user else None
    can_scrape, next_at = check_scrape_cooldown(user) if user else (True, "")
    return {
        "pipeline": ps.get(),
        "stats": db.stats(),
        "scrape_cooldown": {
            "can_scrape": can_scrape,
            "next_scrape_at": next_at,
            "cooldown_minutes": SCRAPE_COOLDOWN_MINUTES,
        }
    }


@app.get("/api/config-check")
def config_check():
    return {
        "ANTHROPIC_API_KEY": "set" if os.getenv("ANTHROPIC_API_KEY") else "MISSING",
        "GOOGLE_SHEET_ID": "set" if os.getenv("GOOGLE_SHEET_ID") else "MISSING",
        "GOOGLE_SERVICE_ACCOUNT_JSON": "set" if os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON") else "MISSING",
    }


@app.get("/")
def root():
    return {"status": "PM Job Agent API running", "version": "3.0 (multi-user + auth)"}
