from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from . import db
from .models import User
from .services import EMAIL_RE, PHONE_RE

bp = Blueprint("auth", __name__)


@bp.route("/signup", methods=["GET", "POST"])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))
    f = {}
    if request.method == "POST":
        f = {k: request.form.get(k, "").strip() for k in ("full_name", "email", "phone")}
        f["email"] = f["email"].lower()
        pw, pw2 = request.form.get("password", ""), request.form.get("confirm", "")
        errors = []
        if not 2 <= len(f["full_name"]) <= 80:
            errors.append("Enter your full name.")
        if not EMAIL_RE.match(f["email"]) or len(f["email"]) > 120:
            errors.append("Enter a valid email address.")
        elif User.query.filter_by(email=f["email"]).first():
            errors.append("An account with this email already exists.")
        if not PHONE_RE.match(f["phone"]):
            errors.append("Enter a valid mobile number like 0300-1234567.")
        if len(pw) < 8:
            errors.append("Password must be at least 8 characters.")
        if pw != pw2:
            errors.append("Passwords do not match.")
        if not errors:
            user = User(full_name=f["full_name"], email=f["email"], phone=f["phone"])
            user.set_password(pw)
            db.session.add(user)
            db.session.commit()
            login_user(user)
            flash("Account created. Set up your donor profile if you want to donate.", "success")
            return redirect(url_for("main.profile"))
        for e in errors:
            flash(e, "danger")
    return render_template("signup.html", f=f)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        user = User.query.filter_by(email=email).first()
        if not user or not user.check_password(request.form.get("password", "")):
            flash("Wrong email or password.", "danger")
        elif user.is_blocked:
            flash("This account has been blocked. Contact the admin.", "danger")
        else:
            login_user(user)
            return redirect(url_for("admin.dashboard" if user.is_admin else "main.requests_list"))
    return render_template("login.html")


@bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("main.index"))
