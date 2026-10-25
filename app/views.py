from datetime import date, timedelta

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import case

from . import db
from .models import BloodRequest, Donor, Report, RequestResponse, utcnow
from .services import (BLOOD_TYPES, CITIES, MAX_REQUESTS_PER_DAY, MAX_SENDS_PER_DAY, URGENCIES,
                       days_until_eligible, expire_old_requests, match_donors, send_email_async,
                       validate_request_form)

bp = Blueprint("main", __name__)


@bp.route("/")
def index():
    expire_old_requests()
    stats = {"donors": Donor.query.count(),
             "pending": BloodRequest.query.filter_by(status="pending").count(),
             "fulfilled": BloodRequest.query.filter_by(status="fulfilled").count()}
    latest = []
    if current_user.is_authenticated:
        latest = (BloodRequest.query.filter_by(status="pending")
                  .order_by(BloodRequest.is_verified.desc(), BloodRequest.created_at.desc()).limit(3).all())
    return render_template("index.html", stats=stats, latest=latest)


@bp.route("/requests")
@login_required
def requests_list():
    expire_old_requests()
    f = {"blood_type": request.args.get("blood_type", ""), "city": request.args.get("city", ""),
         "status": request.args.get("status", "")}
    q = BloodRequest.query
    if f["blood_type"] in BLOOD_TYPES:
        q = q.filter_by(blood_type=f["blood_type"])
    if f["city"] in CITIES:
        q = q.filter_by(city=f["city"])
    if f["status"] in ("pending", "fulfilled", "expired"):
        q = q.filter_by(status=f["status"])
    items = q.order_by(BloodRequest.is_verified.desc(),
                       case((BloodRequest.status == "pending", 0), else_=1),
                       BloodRequest.created_at.desc()).all()
    return render_template("requests.html", items=items, f=f)


@bp.route("/requests/new", methods=["GET", "POST"])
@login_required
def new_request():
    f = {}
    if request.method == "POST":
        f = {k: request.form.get(k, "").strip() for k in
             ("patient_name", "blood_type", "units", "urgency", "hospital", "city", "contact_phone")}
        errors = validate_request_form(f)
        today_count = BloodRequest.query.filter(
            BloodRequest.requester_id == current_user.id,
            BloodRequest.created_at >= utcnow() - timedelta(days=1)).count()
        if today_count >= MAX_REQUESTS_PER_DAY:
            errors.append(f"You can post at most {MAX_REQUESTS_PER_DAY} requests per day.")
        if not errors:
            req = BloodRequest(requester_id=current_user.id, patient_name=f["patient_name"],
                               blood_type=f["blood_type"], units=int(f["units"]), urgency=f["urgency"],
                               hospital=f["hospital"], city=f["city"], contact_phone=f["contact_phone"],
                               expires_at=utcnow() + timedelta(hours=URGENCIES[f["urgency"]]))
            db.session.add(req)
            db.session.commit()
            flash("Request posted. Now choose donors to contact.", "success")
            return redirect(url_for("main.request_detail", rid=req.id))
        for e in errors:
            flash(e, "danger")
    return render_template("request_new.html", f=f)


@bp.route("/requests/<int:rid>")
@login_required
def request_detail(rid):
    expire_old_requests()
    r = db.get_or_404(BloodRequest, rid)
    mine = r.requester_id == current_user.id
    matches = match_donors(r) if mine else []
    responses = {x.donor_id: x for x in r.responses} if mine else {}
    return render_template("request_detail.html", r=r, mine=mine, matches=matches, responses=responses)


def _own_pending_request(rid):
    r = db.get_or_404(BloodRequest, rid)
    if r.requester_id != current_user.id:
        abort(403)
    if r.status != "pending":
        flash("This request is no longer pending.", "warning")
        return None
    return r


def _sends_today():
    since = utcnow() - timedelta(days=1)
    return (RequestResponse.query.join(BloodRequest)
            .filter(BloodRequest.requester_id == current_user.id, RequestResponse.created_at >= since).count())


def _send_to(r, donor):
    if RequestResponse.query.filter_by(request_id=r.id, donor_id=donor.id).first():
        return False
    db.session.add(RequestResponse(request_id=r.id, donor_id=donor.id))
    link = url_for("main.incoming", _external=True)
    send_email_async(current_app._get_current_object(), donor.user.email,
                     f"Blood needed: {r.blood_type} in {r.city}",
                     f"{r.blood_type} blood is needed at {r.hospital}, {r.city} (urgency: {r.urgency}).\n"
                     f"Log in to accept or decline: {link}")
    return True


@bp.route("/requests/<int:rid>/send/<int:donor_id>", methods=["POST"])
@login_required
def send_one(rid, donor_id):
    r = _own_pending_request(rid)
    if r is None:
        return redirect(url_for("main.request_detail", rid=rid))
    donor = db.get_or_404(Donor, donor_id)
    if donor.id not in {d.id for d in match_donors(r)}:
        abort(403)
    if _sends_today() >= MAX_SENDS_PER_DAY:
        flash("Daily limit for sending requests reached.", "warning")
    elif _send_to(r, donor):
        db.session.commit()
        flash("Request sent. The donor will see it and get an email.", "success")
    return redirect(url_for("main.request_detail", rid=rid))


@bp.route("/requests/<int:rid>/send-all", methods=["POST"])
@login_required
def send_all(rid):
    r = _own_pending_request(rid)
    if r is None:
        return redirect(url_for("main.request_detail", rid=rid))
    room = MAX_SENDS_PER_DAY - _sends_today()
    sent = 0
    for donor in match_donors(r):
        if sent >= room:
            flash("Daily limit for sending requests reached.", "warning")
            break
        sent += _send_to(r, donor)
    db.session.commit()
    flash(f"Request sent to {sent} donor(s)." if sent else "No new donors to contact.", "info")
    return redirect(url_for("main.request_detail", rid=rid))


@bp.route("/requests/<int:rid>/fulfil", methods=["POST"])
@login_required
def fulfil(rid):
    r = _own_pending_request(rid)
    if r is not None:
        r.status = "fulfilled"
        db.session.commit()
        flash("Marked as fulfilled. Thank you to every donor.", "success")
    return redirect(url_for("main.request_detail", rid=rid))


@bp.route("/requests/<int:rid>/report", methods=["POST"])
@login_required
def report(rid):
    r = db.get_or_404(BloodRequest, rid)
    reason = request.form.get("reason", "").strip()[:200]
    if r.requester_id == current_user.id:
        abort(403)
    if len(reason) < 3:
        flash("Please write a short reason.", "danger")
    elif Report.query.filter_by(request_id=r.id, reporter_id=current_user.id).first():
        flash("You already reported this request.", "info")
    else:
        db.session.add(Report(request_id=r.id, reporter_id=current_user.id, reason=reason))
        db.session.commit()
        flash("Thank you. The admin will review this request.", "success")
    return redirect(url_for("main.request_detail", rid=rid))


@bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    donor = current_user.donor
    if request.method == "POST":
        blood, city = request.form.get("blood_type", ""), request.form.get("city", "")
        raw_date = request.form.get("last_donation_date", "").strip()
        errors, last = [], None
        if blood not in BLOOD_TYPES:
            errors.append("Choose a valid blood group.")
        if city not in CITIES:
            errors.append("Choose a city in Sindh from the list.")
        if raw_date:
            try:
                last = date.fromisoformat(raw_date)
                if last > date.today():
                    errors.append("Last donation date cannot be in the future.")
            except ValueError:
                errors.append("Enter a valid date.")
        if not errors:
            if donor is None:
                donor = Donor(user_id=current_user.id)
                db.session.add(donor)
            donor.blood_type, donor.city, donor.last_donation_date = blood, city, last
            donor.is_available = request.form.get("is_available") == "on"
            db.session.commit()
            flash("Profile saved.", "success")
            return redirect(url_for("main.profile"))
        for e in errors:
            flash(e, "danger")
    wait = days_until_eligible(donor) if donor else 0
    return render_template("profile.html", donor=donor, wait=wait, today=date.today().isoformat())


@bp.route("/incoming")
@login_required
def incoming():
    items = []
    if current_user.donor:
        items = (RequestResponse.query.filter_by(donor_id=current_user.donor.id)
                 .order_by(RequestResponse.created_at.desc()).all())
    return render_template("incoming.html", items=items)


@bp.route("/responses/<int:resp_id>/<action>", methods=["POST"])
@login_required
def respond(resp_id, action):
    if action not in ("accept", "decline"):
        abort(404)
    resp = db.get_or_404(RequestResponse, resp_id)
    if not current_user.donor or resp.donor_id != current_user.donor.id:
        abort(403)
    if resp.status != "pending" or resp.request.status != "pending":
        flash("This request can no longer be answered.", "warning")
    else:
        resp.status = "accepted" if action == "accept" else "declined"
        db.session.commit()
        flash("Accepted. The requester can now see your phone number." if action == "accept"
              else "Declined.", "success" if action == "accept" else "info")
    return redirect(url_for("main.incoming"))
