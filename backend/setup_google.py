"""
Run this ONCE after downloading your service account JSON key.
It creates the Google Sheet + Drive folder and prints the IDs
you need to paste into your .env and Cloud Run env vars.

Usage:
    py -3 setup_google.py path/to/service-account.json
"""
import json
import sys
from pathlib import Path

def main():
    if len(sys.argv) < 2:
        print("Usage: py -3 setup_google.py path/to/service-account.json")
        sys.exit(1)

    key_path = sys.argv[1]
    with open(key_path) as f:
        sa_info = json.load(f)

    sa_email = sa_info["client_email"]
    print(f"\nService account email: {sa_email}")

    import gspread
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build

    SCOPES = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_info(sa_info, scopes=SCOPES)

    # ── 1. Create Google Sheet ──
    print("\nCreating Google Sheet...")
    gc = gspread.authorize(creds)
    try:
        wb = gc.open("PM Job Agent - Pavan Ram")
        print("  Sheet already exists.")
    except gspread.exceptions.SpreadsheetNotFound:
        wb = gc.create("PM Job Agent - Pavan Ram")
        print("  Created new sheet.")

    # Share with your personal Gmail so you can view it
    wb.share("shantzapav@gmail.com", perm_type="user", role="writer")
    print(f"  Shared with shantzapav@gmail.com")

    sheet_id = wb.id
    print(f"  Sheet ID: {sheet_id}")

    # Add tabs
    existing = [ws.title for ws in wb.worksheets()]
    headers = [
        "id","title","company","location","source","job_url","job_id_external",
        "description","experience_required","salary_range","posted_date",
        "skills_required","created_at","tailored_resume_text","original_resume_text",
        "changes_log","change_percentage","keywords_added","status","applied_at","apply_note"
    ]
    if "Jobs" not in existing:
        ws = wb.add_worksheet("Jobs", rows=1000, cols=len(headers))
        ws.append_row(headers)
        print("  Created Jobs tab with headers.")
    if "Pipeline" not in existing:
        ps = wb.add_worksheet("Pipeline", rows=10, cols=5)
        ps.append_row(["running","progress","jobs_found","jobs_tailored","jobs_applied"])
        ps.append_row(["false","idle","0","0","0"])
        print("  Created Pipeline tab.")

    # Remove default Sheet1 if empty
    if "Sheet1" in existing:
        try:
            wb.del_worksheet(wb.worksheet("Sheet1"))
        except Exception:
            pass

    # ── 2. Create Drive folder ──
    print("\nCreating Google Drive folder...")
    drive_svc = build("drive", "v3", credentials=creds)
    q = "name='PM Job Agent' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    existing_folders = drive_svc.files().list(q=q, fields="files(id,name)").execute()

    if existing_folders["files"]:
        folder_id = existing_folders["files"][0]["id"]
        print("  Folder already exists.")
    else:
        meta = {"name": "PM Job Agent", "mimeType": "application/vnd.google-apps.folder"}
        folder = drive_svc.files().create(body=meta, fields="id").execute()
        folder_id = folder["id"]
        print("  Created 'PM Job Agent' folder in Drive.")

    # Share folder with personal Gmail
    drive_svc.permissions().create(
        fileId=folder_id,
        body={"type": "user", "role": "writer", "emailAddress": "shantzapav@gmail.com"}
    ).execute()
    print(f"  Shared folder with shantzapav@gmail.com")
    print(f"  Folder ID: {folder_id}")

    # ── 3. Upload resume ──
    print("\nUploading resume PDF to Drive...")
    resume_path = Path(__file__).parent / "resume" / "Pavan_Ram_Resume_1.pdf"
    if resume_path.exists():
        from googleapiclient.http import MediaFileUpload
        q2 = f"name='Pavan_Ram_Resume_Original.pdf' and '{folder_id}' in parents and trashed=false"
        ex = drive_svc.files().list(q=q2, fields="files(id)").execute()
        if not ex["files"]:
            media = MediaFileUpload(str(resume_path), mimetype="application/pdf")
            drive_svc.files().create(
                body={"name": "Pavan_Ram_Resume_Original.pdf", "parents": [folder_id]},
                media_body=media, fields="id"
            ).execute()
            print("  Resume uploaded.")
        else:
            print("  Resume already in Drive.")
    else:
        print("  Resume PDF not found — skipping.")

    # ── 4. Print .env values ──
    sa_json_str = json.dumps(sa_info)

    print("\n" + "="*60)
    print("COPY THESE INTO YOUR .env FILE AND CLOUD RUN ENV VARS:")
    print("="*60)
    print(f"\nGOOGLE_SHEET_ID={sheet_id}")
    print(f"GOOGLE_DRIVE_FOLDER_ID={folder_id}")
    print(f"\nGOOGLE_SERVICE_ACCOUNT_JSON='{sa_json_str}'")
    print("\n" + "="*60)
    print("\nAlso open your Sheet here:")
    print(f"https://docs.google.com/spreadsheets/d/{sheet_id}")
    print(f"\nDrive folder:")
    print(f"https://drive.google.com/drive/folders/{folder_id}")
    print("\nSetup complete!")


if __name__ == "__main__":
    main()
