"""
SQLite database models for the job application tracker.
"""
from sqlalchemy import create_engine, Column, Integer, String, Text, Float, DateTime, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime
import json

import os
_DB_URL = os.getenv("DATABASE_URL", "sqlite:///./jobs.db")
# Render/Heroku give postgres:// but SQLAlchemy needs postgresql://
if _DB_URL.startswith("postgres://"):
    _DB_URL = _DB_URL.replace("postgres://", "postgresql://", 1)
DATABASE_URL = _DB_URL
_kwargs = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(300), nullable=False)
    company = Column(String(200), nullable=False)
    location = Column(String(200))
    source = Column(String(50))          # naukri / linkedin / indeed
    job_url = Column(String(1000))
    job_id_external = Column(String(200), unique=True)  # source's job ID
    description = Column(Text)
    experience_required = Column(String(100))
    salary_range = Column(String(100))
    posted_date = Column(String(50))
    skills_required = Column(Text)       # JSON list
    created_at = Column(DateTime, default=datetime.utcnow)

    # Tailoring info
    tailored_resume_text = Column(Text)
    original_resume_text = Column(Text)
    changes_log = Column(Text)           # JSON list of change objects
    change_percentage = Column(Float)
    keywords_added = Column(Text)        # JSON list

    # Application status
    status = Column(String(50), default="pending")  # pending | applied | manual | failed
    applied_at = Column(DateTime)
    apply_note = Column(Text)            # reason if failed/manual

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "company": self.company,
            "location": self.location,
            "source": self.source,
            "job_url": self.job_url,
            "experience_required": self.experience_required,
            "salary_range": self.salary_range,
            "posted_date": self.posted_date,
            "skills_required": json.loads(self.skills_required) if self.skills_required else [],
            "description": self.description,
            "change_percentage": self.change_percentage,
            "keywords_added": json.loads(self.keywords_added) if self.keywords_added else [],
            "status": self.status,
            "applied_at": self.applied_at.isoformat() if self.applied_at else None,
            "apply_note": self.apply_note,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def to_detail_dict(self):
        d = self.to_dict()
        d["tailored_resume_text"] = self.tailored_resume_text
        d["original_resume_text"] = self.original_resume_text
        d["changes_log"] = json.loads(self.changes_log) if self.changes_log else []
        return d


def init_db():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
