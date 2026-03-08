# PM Job Agent — Session Summary
> Auto-updated. Paste this file's contents at the start of any new Claude session to resume instantly.

---

## Who I Am
- **Name**: Pavan Ram | Senior Product Analyst → transitioning to Product Management
- **Resume**: `C:\Users\2025\Downloads\Pavan_Ram_Resume_1.pdf` (also copied to `backend/resume/`)
- **Current role**: redBus India (SEA/LATAM analytics)
- **Target**: Product Manager roles in Bengaluru

---

## What We Built: PM Job Agent

A fully cloud-deployed, mobile-first job application system.

### Project Location
```
C:\Users\2025\pavan_job_agent\
├── backend\               FastAPI Python server
├── mobile_app\            React Native (Expo) Android app
├── render.yaml            Cloud deployment config (Render.com)
├── .gitignore
├── START_BACKEND.bat      Local dev server
├── START_APP.bat          Local Expo dev server
└── SESSION_SUMMARY.md     ← this file
```

### Backend (`backend/`)
| File | Purpose |
|---|---|
| `main.py` | FastAPI server — all endpoints |
| `database.py` | SQLAlchemy — SQLite (local) / PostgreSQL (cloud) |
| `agents/job_scraper.py` | Scrapes Naukri + LinkedIn + Indeed for PM jobs |
| `agents/resume_tailor.py` | Claude API — tailors resume 5–10% per JD |
| `agents/auto_apply.py` | Playwright — LinkedIn Easy Apply |
| `resume/Pavan_Ram_Resume_1.pdf` | Source resume |
| `.env` | API keys (not in git) |
| `Procfile` | For Render/Heroku start command |
| `requirements.txt` | All Python deps |

### Mobile App (`mobile_app/`)
| Screen | Purpose |
|---|---|
| HomeScreen | Job list, filter tabs, Find Jobs modal, ↻ Refresh button |
| JobDetailScreen | JD, tailoring stats, apply buttons |
| ResumeDiffScreen | Full change log (modified/added/removed + reasons) |

### Key API Endpoints
```
POST /api/jobs/search    Run full pipeline (scrape → tailor → apply)
GET  /api/jobs           List all jobs (filter: status, source, search)
GET  /api/jobs/{id}      Job detail
GET  /api/jobs/{id}/resume  Tailored resume + diff
POST /api/jobs/{id}/apply   Mark as manually applied
POST /api/jobs/{id}/retailor  Re-tailor a job
GET  /api/status         Pipeline state + stats
```

---

## Cloud Deployment Status

### Deploy backend to Render.com (TODO — steps below)
1. Push repo to GitHub (see Git Setup below)
2. Go to render.com → New → Blueprint → connect your repo
3. It reads `render.yaml` automatically
4. Set env var `ANTHROPIC_API_KEY` in Render dashboard
5. Your backend URL will be: `https://pavan-job-agent-api.onrender.com`

### Build Android APK (TODO — steps below)
1. `app.json` already has Render URL in `extra.apiBase`
2. Run: `cd mobile_app && npx eas login` (create free expo.dev account)
3. Run: `npx eas build -p android --profile preview`
4. Download APK → install on phone → works anywhere, no PC needed

### Git Setup (needed for Render deploy)
```bash
cd C:\Users\2025\pavan_job_agent
git init
git add .
git commit -m "initial: PM job agent"
# Create repo on github.com → then:
git remote add origin https://github.com/YOUR_USERNAME/pm-job-agent.git
git push -u origin main
```

---

## Environment Variables Needed
| Variable | Where | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | `backend/.env` + Render dashboard | Resume tailoring via Claude |
| `DATABASE_URL` | Auto-set by Render | PostgreSQL connection |
| `LINKEDIN_EMAIL` | Optional | LinkedIn Easy Apply |
| `LINKEDIN_PASSWORD` | Optional | LinkedIn Easy Apply |

---

## How the App Works (End-to-End)
1. Open app on phone → tap **Find Jobs**
2. Backend scrapes Naukri, LinkedIn, Indeed for PM roles in Bengaluru
3. For each job: Claude API tailors your resume 5–10% (keywords matched, summary tweaked)
4. Auto-apply attempted on LinkedIn Easy Apply jobs
5. Status set: **Applied** (auto-applied) or **Apply Manually** (with direct link)
6. App shows all jobs with tailoring stats, change log, keywords added
7. Tap ↻ **Refresh** anytime to re-scrape without changing settings

---

## What's Left / Next Steps
- [ ] Deploy backend to Render (push to GitHub → connect Render)
- [ ] Build APK via EAS (`npx eas build -p android --profile preview`)
- [ ] Test end-to-end with real Anthropic API key
- [ ] Optional: Add LinkedIn credentials for auto-apply
- [ ] Optional: Add more job sources (Foundit, AngelList)
- [ ] Optional: Add email notification when new jobs are found

---

## How to Resume This Conversation
If context hits 100% or daily limit resets, start a new Claude session and say:

> "I'm Pavan Ram. I'm building a PM Job Agent system. Please read my session summary at C:\Users\2025\pavan_job_agent\SESSION_SUMMARY.md and continue from where we left off."

Then paste the relevant section of this file if needed.

---
*Last updated: 2026-03-08*
