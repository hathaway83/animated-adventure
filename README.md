# Mini ATS

A lightweight Applicant Tracking System for a recruiting coordinator at a small biotech. Runs locally with no external services — just Python, Flask, and SQLite.

## Features

- **Candidate management** — create, edit, archive, search candidates with stage tracking
- **Pipeline dashboard** — see counts per stage, overdue next steps, stale candidates (5+ business days)
- **Email templates** — generate copy-ready drafts for scheduling, rejection, feedback requests
- **Interview scheduling** — store interviews, download `.ics` files (Outlook-compatible)
- **Reports** — pipeline stats, stuck candidates list, time-to-offer
- **CSV export** — export candidate lists and stuck-candidate reports

## Quick Start

### Option A: Run directly

```bash
pip install -r requirements.txt
python run.py
```

Open http://localhost:5000

### Option B: Docker

```bash
docker build -t mini-ats .
docker run -p 5000:5000 mini-ats
```

## How to Use

1. **Dashboard** — your home screen. Shows the pipeline funnel and any overdue/stale candidates.
2. **Candidates** — click "+ New" to add a candidate. Use filters and search to find people. Click a name to see details, add notes, schedule interviews, or generate email drafts.
3. **Interviews** — lists all scheduled interviews. Download `.ics` files to import into Outlook.
4. **Templates** — view available email templates. To generate a draft for a specific candidate, go to that candidate's detail page.
5. **Reports** — pipeline stats and a stuck-candidates report with CSV export.

## Database

SQLite database is created automatically at `instance/mini_ats.db` on first run. Default stages and sample candidates are seeded automatically.

To reset: delete `instance/mini_ats.db` and restart.

## Project Structure

```
mini_ats/
  __init__.py
  app.py          # Flask app and all routes
  models.py       # SQLAlchemy models
  seed.py         # Default data seeding
  ics_util.py     # .ics calendar file generation
  templates/      # Jinja2 HTML templates
  static/         # (reserved for future static assets)
run.py            # Entry point
requirements.txt
Dockerfile
```
