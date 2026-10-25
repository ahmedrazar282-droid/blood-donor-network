from datetime import datetime, timezone

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from . import db, login_manager


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    phone = db.Column(db.String(20), nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(10), nullable=False, default="user")  # user or admin
    is_blocked = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, default=utcnow)
    donor = db.relationship("Donor", uselist=False, backref="user", cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)  # never store plain text

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin(self):
        return self.role == "admin"

    @property
    def is_active(self):  # Flask-Login refuses to log in inactive users
        return not self.is_blocked


class Donor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), unique=True, nullable=False)
    blood_type = db.Column(db.String(3), nullable=False)
    city = db.Column(db.String(40), nullable=False)
    is_available = db.Column(db.Boolean, nullable=False, default=True)
    last_donation_date = db.Column(db.Date, nullable=True)


class BloodRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    requester_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    patient_name = db.Column(db.String(60), nullable=False)
    blood_type = db.Column(db.String(3), nullable=False)
    units = db.Column(db.Integer, nullable=False, default=1)
    urgency = db.Column(db.String(10), nullable=False)
    hospital = db.Column(db.String(80), nullable=False)
    city = db.Column(db.String(40), nullable=False)
    contact_phone = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(10), nullable=False, default="pending")  # pending/fulfilled/expired
    is_verified = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, default=utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)
    requester = db.relationship("User", backref="requests")
    responses = db.relationship("RequestResponse", backref="request", cascade="all, delete-orphan")
    reports = db.relationship("Report", backref="request", cascade="all, delete-orphan")


class RequestResponse(db.Model):
    __table_args__ = (db.UniqueConstraint("request_id", "donor_id"),)
    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(db.Integer, db.ForeignKey("blood_request.id"), nullable=False)
    donor_id = db.Column(db.Integer, db.ForeignKey("donor.id"), nullable=False)
    status = db.Column(db.String(10), nullable=False, default="pending")  # pending/accepted/declined
    created_at = db.Column(db.DateTime, default=utcnow)
    donor = db.relationship("Donor", backref="responses")


class Report(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(db.Integer, db.ForeignKey("blood_request.id"), nullable=False)
    reporter_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    reason = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow)
    reporter = db.relationship("User")


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))
