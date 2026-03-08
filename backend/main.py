"""
FastAPI backend — Google Sheets as DB. Resume PDF lives in the container.
"""
import json
import logging
import os
from datetime import datetime
from typing import Optional

from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agents.auto_apply import try_apply
from agents.job_scraper import scrape_all_jobs
from agents.resume_tailor import tailor_resume
from sheets_db import PipelineState, SheetsDB, init_sheets

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Pavan Job Agent API", version="2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    try:
        init_sheets()
        logger.info("Google Sheets initialized")
    except Exception as e:
        logger.warning(f"Sheets init skipped: {e}")


# ─────────────── PIPELINE ───────────────

class SearchRequest(BaseModel):
    keyword: str = "product manager"
    location: str = "Bengaluru"
    max_jobs: int = 30
    auto_apply: bool = True


def run_pipeline(req: SearchRequest):
    db = SheetsDB()
    ps = PipelineState()
    ps.set(running=True, progress="Scraping jobs...", jobs_found=0, jobs_tailored=0, jobs_applied=0)

    try:
        raw_jobs = scrape_all_jobs(req.keyword, req.location)
        raw_jobs = raw_jobs[:req.max_jobs]
        ps.set(running=True, progress=f"Found {len(raw_jobs)} jobs. Tailoring...", jobs_found=len(raw_jobs))

        tailored_count = 0
        applied_count = 0

        for idx, raw in enumerate(raw_jobs):
            ps.set(
                running=True,
                progress=f"Tailoring {idx+1}/{len(raw_jobs)}: {raw['title'][:40]} @ {raw['company'][:20]}",
                jobs_found=len(raw_jobs),
                jobs_tailored=tailored_count,
                jobs_applied=applied_count,
            )

            if db.job_exists(raw["job_id_external"]):
                continue

            jd = raw.get("description", "")
            tailor_result = {"tailored_resume_text": "", "original_resume_text": "",
                             "changes_log": [], "change_percentage": 0.0, "keywords_added": []}

            if jd and os.getenv("ANTHROPIC_API_KEY"):
                try:
                    tailor_result = tailor_resume(jd, company=raw["company"], role=raw["title"])
                    tailored_count += 1
                except Exception as e:
                    logger.warning(f"Tailor failed: {e}")

            applied = False
            apply_note = "Ready — apply manually via link"
            if req.auto_apply and raw.get("job_url"):
                applied, apply_note = try_apply(raw["source"], raw["job_url"])
                if applied:
                    applied_count += 1

            job_data = {
                **raw,
                **tailor_result,
                "status": "applied" if applied else "manual",
                "applied_at": datetime.utcnow().isoformat() if applied else "",
                "apply_note": apply_note,
            }
            job_id = db.add_job(job_data)

        ps.set(running=False, progress=f"Done — {tailored_count} tailored, {applied_count} applied",
               jobs_found=len(raw_jobs), jobs_tailored=tailored_count, jobs_applied=applied_count)

    except Exception as e:
        logger.error(f"Pipeline error: {e}")
        ps.set(running=False, progress=f"Error: {str(e)[:100]}")


@app.post("/api/jobs/search")
async def search_jobs(req: SearchRequest, background_tasks: BackgroundTasks):
    ps = PipelineState()
    if ps.get()["running"]:
        raise HTTPException(status_code=409, detail="Pipeline already running")
    background_tasks.add_task(run_pipeline, req)
    return {"message": "Pipeline started"}


# ─────────────── JOBS ───────────────

@app.get("/api/jobs")
def list_jobs(status: Optional[str] = None, source: Optional[str] = None, search: Optional[str] = None):
    db = SheetsDB()
    jobs = db.list_jobs(status=status, source=source, search=search)
    return {"total": len(jobs), "jobs": jobs}


@app.get("/api/jobs/{job_id}")
def get_job(job_id: int):
    db = SheetsDB()
    job = db.get_job(job_id, include_resume=True)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.get("/api/jobs/{job_id}/resume")
def get_resume(job_id: int):
    db = SheetsDB()
    job = db.get_job(job_id, include_resume=True)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {
        "job_id": job_id,
        "title": job["title"],
        "company": job["company"],
        "tailored_resume_text": job.get("tailored_resume_text", ""),
        "original_resume_text": job.get("original_resume_text", ""),
        "changes_log": job.get("changes_log", []),
        "change_percentage": job.get("change_percentage", 0),
        "keywords_added": job.get("keywords_added", []),
    }


class ManualApplyRequest(BaseModel):
    note: Optional[str] = "Applied manually"


@app.post("/api/jobs/{job_id}/apply")
def mark_applied(job_id: int, body: ManualApplyRequest):
    db = SheetsDB()
    job = db.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    db.update_job(job_id, {
        "status": "applied",
        "applied_at": datetime.utcnow().isoformat(),
        "apply_note": body.note or "Applied manually",
    })
    return {"message": "Marked as applied"}


class RetailorRequest(BaseModel):
    jd_override: Optional[str] = None


@app.post("/api/jobs/{job_id}/retailor")
def retailor_job(job_id: int, body: RetailorRequest):
    db = SheetsDB()
    job = db.get_job(job_id, include_resume=True)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    jd = body.jd_override or job.get("description", "")
    if not jd:
        raise HTTPException(status_code=400, detail="No JD available")
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise HTTPException(status_code=400, detail="ANTHROPIC_API_KEY not set")
    result = tailor_resume(jd, company=job["company"], role=job["title"])
    db.update_job(job_id, {
        "tailored_resume_text": result["tailored_resume_text"],
        "original_resume_text": result["original_resume_text"],
        "changes_log": result["changes_log"],
        "change_percentage": result["change_percentage"],
        "keywords_added": result["keywords_added"],
    })
    return {"message": "Re-tailored", "change_percentage": result["change_percentage"]}


@app.delete("/api/jobs/{job_id}")
def delete_job(job_id: int):
    db = SheetsDB()
    db.delete_job(job_id)
    return {"message": "Deleted"}


# ─────────────── STATUS ───────────────

@app.get("/api/status")
def get_status():
    db = SheetsDB()
    ps = PipelineState()
    return {"pipeline": ps.get(), "stats": db.stats()}


@app.get("/")
def root():
    return {"status": "PM Job Agent API running", "version": "2.0 (Google Sheets)"}
