"""
Google Sheets as database.
Each row = one job. Two tabs: Jobs, Pipeline.
"""
import json
import os
from datetime import datetime

import gspread
from google.oauth2.service_account import Credentials

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
]

HEADERS = [
    "id", "title", "company", "location", "source", "job_url",
    "job_id_external", "description", "experience_required", "salary_range",
    "posted_date", "skills_required", "created_at",
    "tailored_resume_text", "original_resume_text", "changes_log",
    "change_percentage", "keywords_added", "status", "applied_at", "apply_note",
]


def _get_client():
    raw = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "")
    if not raw:
        raise RuntimeError("GOOGLE_SERVICE_ACCOUNT_JSON env var not set")
    info = json.loads(raw)
    creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    return gspread.authorize(creds)


def _get_sheet():
    client = _get_client()
    sheet_id = os.getenv("GOOGLE_SHEET_ID", "")
    if not sheet_id:
        raise RuntimeError("GOOGLE_SHEET_ID env var not set")
    return client.open_by_key(sheet_id)


def init_sheets():
    """Create tabs and headers if they don't exist."""
    wb = _get_sheet()
    titles = [ws.title for ws in wb.worksheets()]

    if "Jobs" not in titles:
        ws = wb.add_worksheet("Jobs", rows=1000, cols=len(HEADERS))
        ws.append_row(HEADERS)
    if "Pipeline" not in titles:
        ps = wb.add_worksheet("Pipeline", rows=10, cols=4)
        ps.append_row(["running", "progress", "jobs_found", "jobs_tailored", "jobs_applied"])
        ps.append_row(["false", "idle", "0", "0", "0"])


def _row_to_dict(row: list, include_resume=False) -> dict:
    def v(i): return row[i] if i < len(row) else ""

    d = {
        "id":                  int(v(0)) if v(0) else 0,
        "title":               v(1),
        "company":             v(2),
        "location":            v(3),
        "source":              v(4),
        "job_url":             v(5),
        "experience_required": v(8),
        "salary_range":        v(9),
        "posted_date":         v(10),
        "skills_required":     json.loads(v(11)) if v(11) else [],
        "description":         v(7),
        "change_percentage":   float(v(16)) if v(16) else 0.0,
        "keywords_added":      json.loads(v(17)) if v(17) else [],
        "status":              v(18) or "pending",
        "applied_at":          v(19) or None,
        "apply_note":          v(20) or None,
        "created_at":          v(12) or None,
    }
    if include_resume:
        d["tailored_resume_text"] = v(13)
        d["original_resume_text"] = v(14)
        d["changes_log"] = json.loads(v(15)) if v(15) else []
    return d


class SheetsDB:
    def __init__(self):
        self.wb = _get_sheet()
        self.ws = self.wb.worksheet("Jobs")
        # Cache all rows in memory for the lifetime of this instance
        # to avoid repeated API calls (rate limit = 300 reads/min)
        self._cache: list[list] | None = None

    def _all_rows(self) -> list[list]:
        if self._cache is None:
            self._cache = self.ws.get_all_values()
        return self._cache

    def _invalidate_cache(self):
        self._cache = None

    def _next_id(self):
        rows = self._all_rows()
        if len(rows) <= 1:
            return 1
        ids = []
        for r in rows[1:]:
            try:
                ids.append(int(r[0]))
            except (ValueError, IndexError):
                pass
        return max(ids) + 1 if ids else 1

    def get_all_external_ids(self) -> set:
        """Return set of all existing job_id_external values — single API call."""
        rows = self._all_rows()
        return {r[6] for r in rows[1:] if len(r) > 6 and r[6]}

    def job_exists(self, job_id_external: str) -> bool:
        return job_id_external in self.get_all_external_ids()

    def add_job(self, data: dict) -> int:
        self._invalidate_cache()  # force fresh read after write
        jid = self._next_id()
        row = [
            jid,
            data.get("title", ""),
            data.get("company", ""),
            data.get("location", ""),
            data.get("source", ""),
            data.get("job_url", ""),
            data.get("job_id_external", ""),
            data.get("description", "")[:5000],
            data.get("experience_required", ""),
            data.get("salary_range", ""),
            data.get("posted_date", ""),
            json.dumps(data.get("skills_required", [])),
            datetime.utcnow().isoformat(),
            data.get("tailored_resume_text", "")[:10000],
            data.get("original_resume_text", "")[:10000],
            json.dumps(data.get("changes_log", [])),
            data.get("change_percentage", 0.0),
            json.dumps(data.get("keywords_added", [])),
            data.get("status", "pending"),
            data.get("applied_at", ""),
            data.get("apply_note", ""),
        ]
        self.ws.append_row([str(x) for x in row])
        return jid

    def list_jobs(self, status=None, source=None, search=None) -> list:
        rows = self.ws.get_all_values()[1:]  # skip header
        result = []
        for r in rows:
            if not r or not r[0]:
                continue
            d = _row_to_dict(r)
            if status and d["status"] != status:
                continue
            if source and d["source"] != source:
                continue
            if search:
                s = search.lower()
                if s not in d["title"].lower() and s not in d["company"].lower():
                    continue
            result.append(d)
        return list(reversed(result))

    def get_job(self, job_id: int, include_resume=False) -> dict | None:
        rows = self.ws.get_all_values()[1:]
        for r in rows:
            if r and r[0] == str(job_id):
                return _row_to_dict(r, include_resume=include_resume)
        return None

    def update_job(self, job_id: int, updates: dict):
        all_rows = self.ws.get_all_values()
        for i, r in enumerate(all_rows):
            if r and r[0] == str(job_id):
                row_num = i + 1
                field_map = {
                    "status":               19,
                    "applied_at":           20,
                    "apply_note":           21,
                    "tailored_resume_text": 14,
                    "original_resume_text": 15,
                    "changes_log":          16,
                    "change_percentage":    17,
                    "keywords_added":       18,
                }
                for key, val in updates.items():
                    if key in field_map:
                        col = field_map[key]
                        v = json.dumps(val) if isinstance(val, (list, dict)) else str(val)
                        self.ws.update_cell(row_num, col, v)
                return
        raise ValueError(f"Job {job_id} not found")

    def delete_job(self, job_id: int):
        all_rows = self.ws.get_all_values()
        for i, r in enumerate(all_rows):
            if r and r[0] == str(job_id):
                self.ws.delete_rows(i + 1)
                return

    def stats(self) -> dict:
        rows = self.ws.get_all_values()[1:]
        total = applied = manual = pending = tailored = 0
        for r in rows:
            if not r or not r[0]:
                continue
            total += 1
            st = r[18] if len(r) > 18 else "pending"
            if st == "applied":
                applied += 1
            elif st == "manual":
                manual += 1
            elif st == "pending":
                pending += 1
            pct = float(r[16]) if len(r) > 16 and r[16] else 0
            if pct > 0:
                tailored += 1
        return {"total_jobs": total, "applied": applied,
                "manual_apply_needed": manual, "pending": pending, "tailored": tailored}


# Pipeline state stored in Sheets "Pipeline" tab
class PipelineState:
    def __init__(self):
        self.wb = _get_sheet()
        self.ps = self.wb.worksheet("Pipeline")

    def get(self) -> dict:
        row = self.ps.row_values(2)
        return {
            "running":       row[0] == "true" if row else False,
            "progress":      row[1] if len(row) > 1 else "idle",
            "jobs_found":    int(row[2]) if len(row) > 2 and row[2] else 0,
            "jobs_tailored": int(row[3]) if len(row) > 3 and row[3] else 0,
            "jobs_applied":  int(row[4]) if len(row) > 4 and row[4] else 0,
        }

    def set(self, **kwargs):
        current = self.get()
        current.update(kwargs)
        self.ps.update("A2:E2", [[
            "true" if current["running"] else "false",
            current["progress"],
            str(current["jobs_found"]),
            str(current["jobs_tailored"]),
            str(current["jobs_applied"]),
        ]])
