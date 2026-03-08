"""
FastAPI backend for Pavan's Job Application Agent.

Endpoints:
  POST /api/jobs/search          — scrape + tailor + auto-apply pipeline
  GET  /api/jobs                 — list all jobs
  GET  /api/jobs/{id}            — job detail + tailored resume
  GET  /api/jobs/{id}/resume     — tailored resume text + diff
  POST /api/jobs/{id}/apply      — mark as manually applied
  POST /api/jobs/{id}/retailor   — re-tailor a specific job
  DELETE /api/jobs/{id}          — remove a job
  GET  /api/status               — pipeline status / stats
"""

import json
import logging
import os
from datetime import datetime
from typing import Optional

from dotenv import load_dotenv
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session

from agents.auto_apply import try_apply
from agents.job_scraper import scrape_all_jobs
from agents.resume_tailor import tailor_resume
from database import Job, get_db, init_db

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Pavan Job Agent API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pipeline state (simple in-memory flag)
pipeline_state = {"running": False, "progress": "", "jobs_found": 0, "jobs_tailored": 0, "jobs_applied": 0}


@app.on_event("startup")
def startup():
    init_db()
    logger.info("DB initialized")


# ─────────────── PIPELINE ───────────────

class SearchRequest(BaseModel):
    keyword: str = "product manager"
    location: str = "Bengaluru"
    max_jobs: int = 30
    auto_apply: bool = True


def run_pipeline(req: SearchRequest, db: Session):
    global pipeline_state
    pipeline_state.update({"running": True, "progress": "Scraping jobs...", "jobs_found": 0, "jobs_tailored": 0, "jobs_applied": 0})

    try:
        # 1. Scrape
        raw_jobs = scrape_all_jobs(req.keyword, req.location)
        raw_jobs = raw_jobs[: req.max_jobs]
        pipeline_state["jobs_found"] = len(raw_jobs)
        logger.info(f"Scraped {len(raw_jobs)} jobs")

        for idx, raw in enumerate(raw_jobs):
            pipeline_state["progress"] = f"Tailoring {idx + 1}/{len(raw_jobs)}: {raw['title']} @ {raw['company']}"

            # Skip if already in DB
            existing = db.query(Job).filter(Job.job_id_external == raw["job_id_external"]).first()
            if existing:
                logger.info(f"Skipping duplicate: {raw['job_id_external']}")
                continue

            # 2. Tailor resume
            jd = raw.get("description", "")
            tailor_result = {"tailored_resume_text": "", "original_resume_text": "",
                             "changes_log": [], "change_percentage": 0.0, "keywords_added": []}
            if jd and os.getenv("ANTHROPIC_API_KEY"):
                try:
                    tailor_result = tailor_resume(jd, company=raw["company"], role=raw["title"])
                    pipeline_state["jobs_tailored"] += 1
                except Exception as e:
                    logger.warning(f"Tailoring failed for {raw['title']}: {e}")

            # 3. Auto-apply
            applied = False
            apply_note = "Tailored — pending manual apply"
            if req.auto_apply and raw.get("job_url"):
                applied, apply_note = try_apply(raw["source"], raw["job_url"])
                if applied:
                    pipeline_state["jobs_applied"] += 1

            # 4. Save to DB
            job = Job(
                title=raw["title"],
                company=raw["company"],
                location=raw.get("location", ""),
                source=raw["source"],
                job_url=raw.get("job_url", ""),
                job_id_external=raw["job_id_external"],
                description=jd,
                experience_required=raw.get("experience_required", ""),
                salary_range=raw.get("salary_range", "Not disclosed"),
                posted_date=raw.get("posted_date", ""),
                skills_required=json.dumps(raw.get("skills_required", [])),
                tailored_resume_text=tailor_result["tailored_resume_text"],
                original_resume_text=tailor_result["original_resume_text"],
                changes_log=json.dumps(tailor_result["changes_log"]),
                change_percentage=tailor_result["change_percentage"],
                keywords_added=json.dumps(tailor_result["keywords_added"]),
                status="applied" if applied else "manual",
                applied_at=datetime.utcnow() if applied else None,
                apply_note=apply_note,
            )
            db.add(job)
            db.commit()

        pipeline_state["progress"] = "Done"
    except Exception as e:
        logger.error(f"Pipeline error: {e}")
        pipeline_state["progress"] = f"Error: {e}"
    finally:
        pipeline_state["running"] = False


@app.post("/api/jobs/search")
async def search_jobs(req: SearchRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    if pipeline_state["running"]:
        raise HTTPException(status_code=409, detail="Pipeline already running")
    background_tasks.add_task(run_pipeline, req, db)
    return {"message": "Pipeline started", "status": "running"}


# ─────────────── JOBS ───────────────

@app.get("/api/jobs")
def list_jobs(
    status: Optional[str] = None,
    source: Optional[str] = None,
    search: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    q = db.query(Job)
    if status:
        q = q.filter(Job.status == status)
    if source:
        q = q.filter(Job.source == source)
    if search:
        q = q.filter(Job.title.contains(search) | Job.company.contains(search))
    total = q.count()
    jobs = q.order_by(Job.created_at.desc()).offset(skip).limit(limit).all()
    return {"total": total, "jobs": [j.to_dict() for j in jobs]}


@app.get("/api/jobs/{job_id}")
def get_job(job_id: int, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job.to_detail_dict()


@app.get("/api/jobs/{job_id}/resume")
def get_tailored_resume(job_id: int, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {
        "job_id": job_id,
        "title": job.title,
        "company": job.company,
        "tailored_resume_text": job.tailored_resume_text or job.original_resume_text,
        "original_resume_text": job.original_resume_text,
        "changes_log": json.loads(job.changes_log) if job.changes_log else [],
        "change_percentage": job.change_percentage,
        "keywords_added": json.loads(job.keywords_added) if job.keywords_added else [],
    }


class ManualApplyRequest(BaseModel):
    note: Optional[str] = "Applied manually"


@app.post("/api/jobs/{job_id}/apply")
def mark_applied(job_id: int, body: ManualApplyRequest, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    job.status = "applied"
    job.applied_at = datetime.utcnow()
    job.apply_note = body.note
    db.commit()
    return {"message": "Marked as applied", "job_id": job_id}


class RetailorRequest(BaseModel):
    jd_override: Optional[str] = None


@app.post("/api/jobs/{job_id}/retailor")
def retailor_job(job_id: int, body: RetailorRequest, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    jd = body.jd_override or job.description or ""
    if not jd:
        raise HTTPException(status_code=400, detail="No JD available to tailor against")
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise HTTPException(status_code=400, detail="ANTHROPIC_API_KEY not set")

    result = tailor_resume(jd, company=job.company, role=job.title)
    job.tailored_resume_text = result["tailored_resume_text"]
    job.original_resume_text = result["original_resume_text"]
    job.changes_log = json.dumps(result["changes_log"])
    job.change_percentage = result["change_percentage"]
    job.keywords_added = json.dumps(result["keywords_added"])
    db.commit()
    return {"message": "Re-tailored", "change_percentage": result["change_percentage"]}


@app.delete("/api/jobs/{job_id}")
def delete_job(job_id: int, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    db.delete(job)
    db.commit()
    return {"message": "Deleted"}


# ─────────────── STATUS ───────────────

@app.get("/api/status")
def get_status(db: Session = Depends(get_db)):
    total = db.query(Job).count()
    applied = db.query(Job).filter(Job.status == "applied").count()
    manual = db.query(Job).filter(Job.status == "manual").count()
    pending = db.query(Job).filter(Job.status == "pending").count()
    tailored = db.query(Job).filter(Job.change_percentage > 0).count()
    return {
        "pipeline": pipeline_state,
        "stats": {
            "total_jobs": total,
            "applied": applied,
            "manual_apply_needed": manual,
            "pending": pending,
            "tailored": tailored,
        },
    }
