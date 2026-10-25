import os

from flask import Flask
from flask_login import LoginManager, current_user
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:  # python-dotenv is optional
    pass

db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()
login_manager.login_view = "auth.login"
login_manager.login_message = "Please log in to continue."
login_manager.login_message_category = "warning"


def create_app(config=None):
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-only-change-me"),
        SQLALCHEMY_DATABASE_URI=os.environ.get("DATABASE_URL", "sqlite:///blood.db"),
        MAIL_SERVER=os.environ.get("MAIL_SERVER", "smtp.gmail.com"),
        MAIL_PORT=int(os.environ.get("MAIL_PORT", 587)),
        MAIL_USERNAME=os.environ.get("MAIL_USERNAME", ""),
        MAIL_PASSWORD=os.environ.get("MAIL_PASSWORD", ""),
    )
    if config:
        app.config.update(config)

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    from .admin import bp as admin_bp
    from .auth import bp as auth_bp
    from .models import RequestResponse
    from .services import BLOOD_TYPES, CITIES, URGENCIES, wa_link
    from .views import bp as main_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(admin_bp)
    app.jinja_env.filters["wa_link"] = wa_link
    app.jinja_env.globals.update(BLOOD_TYPES=BLOOD_TYPES, CITIES=CITIES, URGENCIES=list(URGENCIES))

    @app.context_processor
    def inject_incoming_count():
        n = 0
        if current_user.is_authenticated and current_user.donor:
            n = RequestResponse.query.filter_by(donor_id=current_user.donor.id, status="pending").count()
        return {"incoming_count": n}

    with app.app_context():
        db.create_all()
    return app
