# Voylla Task Tracker

Department-based task board (Flask + Postgres). Teams raise tasks for each other
with a needed-by date (TAT); the receiving department accepts or extends it with a
note. Email notifications, per-department logins, task conversations, admin
workload view.

## Deploy (Render)

- Build: `pip install -r requirements.txt`
- Start: `gunicorn app:app --bind 0.0.0.0:$PORT --workers 2`
- Environment variables (all required):
  - `DB_HOST`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`, `DB_PORT` — Postgres connection
  - `MAIL_USER`, `MAIL_PASS`, `MAIL_SENDER` — Gmail app-password account for notifications
  - `SECRET_KEY` — any long random string (session signing)

Without env vars it falls back to local credential files (see `find_cred` in app.py).
