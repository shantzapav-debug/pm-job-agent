"""
Auth module — JWT + user management via Google Sheets.
Users sheet columns: id | email | password_hash | name | created_at | last_scrape_at | resume_text | target_role | target_location
"""
import base64
import hashlib
import hmac
import json
import os
from datetime import datetime, timedelta, timezone

import jwt

from sheets_db import _get_sheet

SECRET_KEY = os.getenv("JWT_SECRET", "pm-job-agent-secret-2026")
ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = 72
SCRAPE_COOLDOWN_MINUTES = 60


def _hash_password(password: str) -> str:
    """PBKDF2-HMAC-SHA256, no 72-byte bcrypt limit."""
    salt = os.urandom(32)
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200_000)
    return base64.b64encode(salt + key).decode("utf-8")


def verify_password(plain: str, stored: str) -> bool:
    try:
        raw = base64.b64decode(stored.encode("utf-8"))
        salt, stored_key = raw[:32], raw[32:]
        key = hashlib.pbkdf2_hmac("sha256", plain.encode("utf-8"), salt, 200_000)
        return hmac.compare_digest(key, stored_key)
    except Exception:
        return False

USER_HEADERS = ["id", "email", "password_hash", "name", "created_at",
                "last_scrape_at", "resume_text", "target_role", "target_location"]


def _users_sheet():
    wb = _get_sheet()
    titles = [ws.title for ws in wb.worksheets()]
    if "Users" not in titles:
        ws = wb.add_worksheet("Users", rows=500, cols=len(USER_HEADERS))
        ws.append_row(USER_HEADERS)
    return wb.worksheet("Users")


def _row_to_user(row: list) -> dict:
    def v(i): return row[i] if i < len(row) else ""
    return {
        "id":               v(0),
        "email":            v(1),
        "password_hash":    v(2),
        "name":             v(3),
        "created_at":       v(4),
        "last_scrape_at":   v(5),
        "resume_text":      v(6),
        "target_role":      v(7),
        "target_location":  v(8),
    }


def get_user_by_email(email: str) -> dict | None:
    ws = _users_sheet()
    rows = ws.get_all_values()[1:]
    for r in rows:
        if r and r[1].lower() == email.lower():
            return _row_to_user(r)
    return None


def get_user_by_id(user_id: str) -> dict | None:
    ws = _users_sheet()
    rows = ws.get_all_values()[1:]
    for r in rows:
        if r and r[0] == user_id:
            return _row_to_user(r)
    return None


def create_user(email: str, password: str, name: str) -> dict:
    ws = _users_sheet()
    rows = ws.get_all_values()[1:]
    next_id = str(len(rows) + 1)
    pw_hash = _hash_password(password)
    now = datetime.now(timezone.utc).isoformat()
    row = [next_id, email, pw_hash, name, now, "", "", "product manager", "Bengaluru"]
    ws.append_row(row)
    return {"id": next_id, "email": email, "name": name}



def create_token(user_id: str, email: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=TOKEN_EXPIRE_HOURS)
    return jwt.encode({"sub": user_id, "email": email, "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])


def update_last_scrape(user_id: str):
    ws = _users_sheet()
    rows = ws.get_all_values()
    for i, r in enumerate(rows):
        if r and r[0] == user_id:
            ws.update_cell(i + 1, 6, datetime.now(timezone.utc).isoformat())
            return


def update_resume(user_id: str, resume_text: str, target_role: str = "", target_location: str = ""):
    ws = _users_sheet()
    rows = ws.get_all_values()
    for i, r in enumerate(rows):
        if r and r[0] == user_id:
            ws.update_cell(i + 1, 7, resume_text[:15000])
            if target_role:
                ws.update_cell(i + 1, 8, target_role)
            if target_location:
                ws.update_cell(i + 1, 9, target_location)
            return


def check_scrape_cooldown(user: dict) -> tuple[bool, str]:
    """Returns (can_scrape, next_scrape_at_iso). can_scrape=True if cooldown passed."""
    last = user.get("last_scrape_at", "")
    if not last:
        return True, ""
    try:
        last_dt = datetime.fromisoformat(last)
        if last_dt.tzinfo is None:
            last_dt = last_dt.replace(tzinfo=timezone.utc)
        next_dt = last_dt + timedelta(minutes=SCRAPE_COOLDOWN_MINUTES)
        now = datetime.now(timezone.utc)
        if now >= next_dt:
            return True, ""
        return False, next_dt.isoformat()
    except Exception:
        return True, ""
