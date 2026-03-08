"""
Run this ONCE after creating a Google Sheet and sharing it with the service account.
Drive folder is no longer needed — everything is stored in Google Sheets.

Usage:
    py -3 setup_google.py <service-account.json> <sheet_id>

Example:
    py -3 setup_google.py C:\\Users\\2025\\Downloads\\service-account.json 1azCLtP6gzHh...
"""
import json
import sys


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    key_path = sys.argv[1]
    sheet_id = sys.argv[2]

    with open(key_path) as f:
        sa_info = json.load(f)

    print(f"\nService account: {sa_info['client_email']}")

    import gspread
    from google.oauth2.service_account import Credentials

    SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(sa_info, scopes=SCOPES)
    gc = gspread.authorize(creds)

    # ── Set up Sheet tabs ──
    print("\nSetting up Google Sheet tabs...")
    wb = gc.open_by_key(sheet_id)
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
        print("  OK Created Jobs tab with headers")
    else:
        print("  OK Jobs tab already exists")

    if "Pipeline" not in existing:
        ps = wb.add_worksheet("Pipeline", rows=10, cols=5)
        ps.append_row(["running","progress","jobs_found","jobs_tailored","jobs_applied"])
        ps.append_row(["false","idle","0","0","0"])
        print("  OK Created Pipeline tab")
    else:
        print("  OK Pipeline tab already exists")

    if "Sheet1" in existing:
        try:
            wb.del_worksheet(wb.worksheet("Sheet1"))
            print("  OK Removed default Sheet1")
        except Exception:
            pass

    # ── Print env vars ──
    sa_json_str = json.dumps(sa_info)

    print("\n" + "="*60)
    print("ADD THESE TO YOUR .env AND CLOUD RUN ENVIRONMENT VARS:")
    print("="*60)
    print(f"\nGOOGLE_SHEET_ID={sheet_id}")
    print(f"\nGOOGLE_SERVICE_ACCOUNT_JSON={sa_json_str}")
    print("\n" + "="*60)
    print(f"\nView your Sheet: https://docs.google.com/spreadsheets/d/{sheet_id}")
    print("\nSetup complete!")


if __name__ == "__main__":
    main()
