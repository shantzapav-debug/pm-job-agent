"""
Google Drive storage for resume PDFs.
Uploads original + tailored resumes to Drive folder.
"""
import io
import json
import os
from pathlib import Path

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseUpload

SCOPES = [
    "https://www.googleapis.com/auth/drive",
]

RESUME_PDF_PATH = Path(__file__).parent / "resume" / "Pavan_Ram_Resume_1.pdf"


def _get_service():
    raw = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "")
    if not raw:
        raise RuntimeError("GOOGLE_SERVICE_ACCOUNT_JSON not set")
    info = json.loads(raw)
    creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    return build("drive", "v3", credentials=creds)


def get_folder_id() -> str:
    fid = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "")
    if not fid:
        raise RuntimeError("GOOGLE_DRIVE_FOLDER_ID not set")
    return fid


def upload_resume_pdf() -> str:
    """Upload the original resume PDF to Drive. Returns file ID."""
    service = _get_service()
    folder_id = get_folder_id()

    # Check if already uploaded
    q = f"name='Pavan_Ram_Resume_Original.pdf' and '{folder_id}' in parents and trashed=false"
    existing = service.files().list(q=q, fields="files(id)").execute()
    if existing["files"]:
        return existing["files"][0]["id"]

    meta = {"name": "Pavan_Ram_Resume_Original.pdf", "parents": [folder_id]}
    media = MediaFileUpload(str(RESUME_PDF_PATH), mimetype="application/pdf")
    f = service.files().create(body=meta, media_body=media, fields="id").execute()
    return f["id"]


def upload_tailored_resume(job_id: int, company: str, text: str) -> str:
    """Save tailored resume text as a .txt file in Drive. Returns file ID."""
    service = _get_service()
    folder_id = get_folder_id()
    name = f"Pavan_Resume_Tailored_{company.replace(' ','_')[:30]}_job{job_id}.txt"

    # Overwrite if exists
    q = f"name='{name}' and '{folder_id}' in parents and trashed=false"
    existing = service.files().list(q=q, fields="files(id)").execute()

    content = text.encode("utf-8")
    media = MediaIoBaseUpload(io.BytesIO(content), mimetype="text/plain")

    if existing["files"]:
        fid = existing["files"][0]["id"]
        service.files().update(fileId=fid, media_body=media).execute()
        return fid

    meta = {"name": name, "parents": [folder_id]}
    f = service.files().create(body=meta, media_body=media, fields="id").execute()
    return f["id"]


def create_folder_if_missing(folder_name: str = "PM Job Agent") -> str:
    """Create the Drive folder if it doesn't exist. Returns folder ID."""
    service = _get_service()
    q = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    existing = service.files().list(q=q, fields="files(id)").execute()
    if existing["files"]:
        return existing["files"][0]["id"]
    meta = {"name": folder_name, "mimeType": "application/vnd.google-apps.folder"}
    f = service.files().create(body=meta, fields="id").execute()
    return f["id"]
