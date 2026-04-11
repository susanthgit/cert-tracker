# 📊 Microsoft Cert Exam Change Tracker

Pipeline that tracks Microsoft certification exam changes weekly. Powers the Cert Tracker at [aguidetocloud.com/cert-tracker/](https://www.aguidetocloud.com/cert-tracker/).

## How it works

1. **`fetch_exams.py`** — Fetches study guide markdown from Microsoft Learn for all tracked exams
2. **`diff_engine.py`** — Compares current vs previous state, detects skill objective changes
3. **`generate_data.py`** — Produces JSON data files + RSS feed for the frontend

## Architecture

Same proven pipeline pattern as [AI News](https://github.com/susanthgit/-ainews) and [M365 Roadmap](https://github.com/susanthgit/m365-roadmap).

## Schedule

Weekly on Sundays at 5:00 UTC via GitHub Actions.

## Adding a new exam

Add an entry to `scripts/exams.json` with the exam code, title, level, role, and products.
