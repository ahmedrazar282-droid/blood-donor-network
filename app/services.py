"""Business logic: blood compatibility, eligibility, matching, validation, email."""
import logging
import re
import smtplib
import threading
from datetime import date
from email.message import EmailMessage

log = logging.getLogger(__name__)

BLOOD_TYPES = ["O-", "O+", "A-", "A+", "B-", "B+", "AB-", "AB+"]
CITIES = ["Karachi", "Hyderabad", "Sukkur", "Larkana", "Nawabshah", "Mirpurkhas", "Khairpur",
          "Naushahro Feroze", "Jacobabad", "Shikarpur", "Dadu", "Thatta", "Badin", "Sanghar",
          "Umerkot", "Jamshoro", "Ghotki"]
URGENCIES = {"Critical": 24, "High": 48, "Normal": 72}  # hours until a request expires
COOLDOWN_DAYS = 90
MAX_REQUESTS_PER_DAY = 5
MAX_SENDS_PER_DAY = 30

# Which recipient types each donor type can give red blood cells to.
CAN_DONATE_TO = {
    "O-": set(BLOOD_TYPES),
    "O+": {"O+", "A+", "B+", "AB+"},
    "A-": {"A-", "A+", "AB-", "AB+"},
    "A+": {"A+", "AB+"},
    "B-": {"B-", "B+", "AB-", "AB+"},
    "B+": {"B+", "AB+"},
    "AB-": {"AB-", "AB+"},
    "AB+": {"AB+"},
}

PHONE_RE = re.compile(r"^03\d{2}-?\d{7}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def can_donate(donor_type, needed_type):
    return needed_type in CAN_DONATE_TO.get(donor_type, set())


def days_until_eligible(donor, today=None):
    today = today or date.today()
    if donor.last_donation_date is None:
        return 0
    return max(0, COOLDOWN_DAYS - (today - donor.last_donation_date).days)


def is_eligible(donor, today=None):
    return bool(donor.is_available) and days_until_eligible(donor, today) == 0


def match_donors(req):
    """Compatible, available, eligible donors. Same city first, then longest since last donation."""
    from .models import Donor, User
    rows = (Donor.query.join(User)
            .filter(User.is_blocked.is_(False), Donor.user_id != req.requester_id,
                    Donor.is_available.is_(True)).all())
    found = [d for d in rows if can_donate(d.blood_type, req.blood_type) and is_eligible(d)]
    found.sort(key=lambda d: (d.city != req.city, d.last_donation_date or date.min))
    return found


def expire_old_requests():
    from . import db
    from .models import BloodRequest, utcnow
    BloodRequest.query.filter(BloodRequest.status == "pending", BloodRequest.expires_at < utcnow()) \
        .update({"status": "expired"}, synchronize_session=False)
    db.session.commit()


def validate_request_form(f):
    errors = []
    if not 2 <= len(f.get("patient_name", "")) <= 60:
        errors.append("Enter the patient name (2 to 60 characters).")
    if not 2 <= len(f.get("hospital", "")) <= 80:
        errors.append("Enter the hospital name (2 to 80 characters).")
    if f.get("blood_type") not in BLOOD_TYPES:
        errors.append("Choose a valid blood group.")
    if f.get("city") not in CITIES:
        errors.append("Choose a city in Sindh from the list.")
    if f.get("urgency") not in URGENCIES:
        errors.append("Choose an urgency level.")
    if not PHONE_RE.match(f.get("contact_phone", "")):
        errors.append("Enter a valid mobile number like 0300-1234567.")
    units = f.get("units", "")
    if not (units.isdigit() and 1 <= int(units) <= 10):
        errors.append("Units must be a number from 1 to 10.")
    return errors


def wa_link(phone):
    digits = re.sub(r"\D", "", phone or "")
    if digits.startswith("0"):
        digits = "92" + digits[1:]
    return "https://wa.me/" + digits


def send_email_async(app, to, subject, body):
    """Send in a background thread. A mail failure must never break the request."""
    def worker():
        with app.app_context():
            cfg = app.config
            if not cfg.get("MAIL_USERNAME"):
                log.info("Email not configured. Would send to %s: %s", to, subject)
                return
            try:
                msg = EmailMessage()
                msg["From"], msg["To"], msg["Subject"] = cfg["MAIL_USERNAME"], to, subject
                msg.set_content(body)
                with smtplib.SMTP(cfg["MAIL_SERVER"], cfg["MAIL_PORT"], timeout=10) as s:
                    s.starttls()
                    s.login(cfg["MAIL_USERNAME"], cfg["MAIL_PASSWORD"])
                    s.send_message(msg)
            except Exception:  # noqa: BLE001 - log and carry on
                log.exception("Email to %s failed", to)
    threading.Thread(target=worker, daemon=True).start()
