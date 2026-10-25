# Sindh Blood Donor Network

A web application that connects blood donors and people in need across Sindh.
Built for CSC-206 Software Engineering, Aror University, Sukkur.

## Features implemented
**Core (from the brief)**
- Donor registration: name, contact, blood type, Sindh city, availability toggle, last donation date, 90-day cooldown
- Blood request posting: blood type, units, urgency, hospital, city, contact
- Search and matching: correct blood-type compatibility, same city first, only available and eligible donors
- Authentication: signup/login/logout, passwords hashed (never plain text)
- Request status: Pending / Fulfilled / Expired (auto-expiry: Critical 24h, High 48h, Normal 72h)

**Extras**
- Requester can send a request to one donor or all matching donors; donors Accept/Decline from an Incoming page
- Donor phone numbers stay hidden until the donor accepts
- Email notification to the donor (optional, needs Gmail App Password in `.env`)
- Admin panel: dashboard, verify/unverify requests, delete fake requests, reports, block/unblock users
- Report button, daily rate limits (5 requests and 30 donor requests per user per day)

## Run it
```bash
python -m venv venv
venv\Scripts\activate          # Windows   (Mac/Linux: source venv/bin/activate)
pip install -r requirements.txt
copy .env.example .env         # Mac/Linux: cp .env.example .env  (then set SECRET_KEY)
python seed.py                 # optional demo data
python run.py                  # open http://127.0.0.1:5000
```
Demo logins after `python seed.py`: `ahmed@example.com` and `sara@example.com` (password `Demo@12345`),
admin `admin@example.com` (password `Admin@12345` unless `ADMIN_PASSWORD` is set; change it).

## Run the tests
```bash
python -m pytest
```
26 tests cover compatibility rules, the 90-day eligibility rule, matching, privacy of phone numbers,
roles, blocking, expiry, validation and the rate limit.

## Project structure
```
app/__init__.py     app factory, extensions
app/models.py       database tables
app/services.py     compatibility, eligibility, matching, validation, email (pure logic)
app/auth.py         signup / login / logout
app/views.py        requests, donor profile, incoming requests
app/admin.py        admin dashboard and moderation
app/templates/      Jinja pages (Bootstrap 5)
tests/              pytest tests
seed.py, run.py     demo data and entry point
```

## Security notes
Hashed passwords, server-side validation, CSRF protection on every form, ORM queries (no raw SQL),
auto-escaped templates, role checks on admin routes, ownership checks on requests, secrets in `.env`.

## Deploy (Render / PythonAnywhere)
Set environment variables `SECRET_KEY` (and optionally `MAIL_USERNAME`, `MAIL_PASSWORD`), install
`requirements.txt` plus `gunicorn`, and start with `gunicorn run:app`. Do not use `debug=True` in production.
For a persistent database on a host with a temporary disk, set `DATABASE_URL` to a PostgreSQL URL.

## Known limitations
- Verification is manual (admin calls the contact number); unverified requests are still visible
- Matching is by city, not GPS distance
- Eligibility is self-declared (last donation date); the system cannot check medical fitness
- Email may be slow or land in spam; WhatsApp links are used for contact after acceptance
- Sindh only in this version

## AI Usage Disclosure
(Fill in honestly before submission: which AI tools were used, for which parts, and what the team did itself.)
