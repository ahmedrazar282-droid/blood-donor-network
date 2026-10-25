from functools import wraps

from flask import Blueprint, abort, flash, redirect, render_template, url_for
from flask_login import current_user, login_required

from . import db
from .models import BloodRequest, Donor, Report, User
from .services import expire_old_requests

bp = Blueprint("admin", __name__, url_prefix="/admin")


def admin_required(view):
    @wraps(view)
    @login_required
    def wrapper(*args, **kwargs):
        if not current_user.is_admin:
            abort(403)
        return view(*args, **kwargs)
    return wrapper


@bp.route("/")
@admin_required
def dashboard():
    expire_old_requests()
    count = lambda s: BloodRequest.query.filter_by(status=s).count()  # noqa: E731
    stats = {"users": User.query.filter_by(role="user").count(), "donors": Donor.query.count(),
             "pending": count("pending"), "fulfilled": count("fulfilled"), "expired": count("expired")}
    return render_template("admin.html", stats=stats,
                           requests=BloodRequest.query.order_by(BloodRequest.created_at.desc()).all(),
                           reports=Report.query.order_by(Report.created_at.desc()).all(),
                           users=User.query.filter_by(role="user").order_by(User.created_at.desc()).all())


@bp.route("/verify/<int:rid>", methods=["POST"])
@admin_required
def verify(rid):
    r = db.get_or_404(BloodRequest, rid)
    r.is_verified = not r.is_verified
    db.session.commit()
    flash("Request verified." if r.is_verified else "Verification removed.", "success")
    return redirect(url_for("admin.dashboard"))


@bp.route("/delete/<int:rid>", methods=["POST"])
@admin_required
def delete(rid):
    db.session.delete(db.get_or_404(BloodRequest, rid))
    db.session.commit()
    flash("Request deleted.", "info")
    return redirect(url_for("admin.dashboard"))


@bp.route("/users/<int:uid>/block", methods=["POST"])
@admin_required
def block(uid):
    user = db.get_or_404(User, uid)
    if user.is_admin:
        abort(403)
    user.is_blocked = not user.is_blocked
    db.session.commit()
    flash("User blocked." if user.is_blocked else "User unblocked.", "info")
    return redirect(url_for("admin.dashboard"))
