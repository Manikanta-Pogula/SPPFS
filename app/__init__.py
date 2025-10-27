# app/__init__.py
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from config import Config
from flask_cors import CORS

# Extensions
db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
# default login view (used for redirects)
login_manager.login_view = "auth.login"


def create_app():
    app = Flask(
        __name__,
        template_folder="../templates",
        static_folder="../static",
        instance_relative_config=False
    )

    # Load configuration (SECRET_KEY, SQLALCHEMY_DATABASE_URI, etc.)
    app.config.from_object(Config)

    # -------------------------
    # Cookie & CORS (local dev)
    # -------------------------
    # Allow the dev frontend (Vite) if used, and also allow same-origin from Flask.
    # Add any other origins you use during development.
    CORS(app, supports_credentials=True, origins=[
        "http://localhost:5173",
        "http://localhost:5000",
        "http://127.0.0.1:5000"
    ])

    # Session cookie settings for local development:
    # - Lax works for same-origin navigation (safer) and avoids some Chrome 'secure' issues on localhost.
    # - Set SECURE=True only if you're serving over HTTPS or you know Chrome treats your host as secure.
    app.config.update(
        SESSION_COOKIE_NAME="session",
        SESSION_COOKIE_SAMESITE="Lax",    # Lax is fine for same-origin navigation; change to 'None' if you need cross-site
        SESSION_COOKIE_SECURE=False,      # False for http://localhost; set True on HTTPS
        SESSION_COOKIE_HTTPONLY=True,
    )
    # -------------------------

    # init extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)

    # -------------------------
    # login_manager: unauthorized handler
    # -------------------------
    # If request prefers JSON or is XHR -> return JSON 401 (for API calls).
    # Otherwise -> redirect browser users to login page.
    @login_manager.unauthorized_handler
    def unauthorized():
        # import inside function to avoid circular import issues at module import time
        from flask import jsonify, redirect, url_for, request, current_app

        current_app.logger.info(
            "[UNAUTH] path=%s accept=%s X-Requested-With=%s cookies=%s",
            request.path,
            request.headers.get("Accept"),
            request.headers.get("X-Requested-With"),
            dict(request.cookies)
        )

        # Heuristics to decide if client expects JSON (API/XHR)
        wants_json = (
            request.headers.get("X-Requested-With") == "XMLHttpRequest"
            or request.is_json
            or (request.accept_mimetypes["application/json"] >= request.accept_mimetypes["text/html"])
        )

        if wants_json:
            return jsonify({"error": "unauthorized"}), 401

        # Otherwise, redirect to login page for interactive browser users
        return redirect(url_for("auth.login"))
    # -------------------------

    # import models so db knows them
    from app import models
    from app.models import Institution

    # user loader for flask-login
    @login_manager.user_loader
    def load_user(user_id):
        # import current_app lazily
        from flask import current_app
        try:
            current_app.logger.debug(f"[LOAD_USER] trying id={user_id}")
            # try numeric id first, then fallback to raw
            try:
                return models.User.query.get(int(user_id))
            except Exception:
                return models.User.query.get(user_id)
        except Exception as e:
            current_app.logger.exception(f"[LOAD_USER] failed to load user {user_id}: {e}")
            return None

    # Ensure at least one Institution row exists (safe seeding)
    from sqlalchemy import inspect
    with app.app_context():
        try:
            inspector = inspect(db.engine)
            if "institution" in inspector.get_table_names():
                if Institution.query.count() == 0:
                    inst = Institution(name="🏫 GOVT. POLYTECHNIC, SIDDIPET")
                    db.session.add(inst)
                    db.session.commit()
        except Exception as e:
            app.logger.warning(f"Skipping Institution seed (reason: {e})")

    # Register blueprints (order preserved)
    from app.auth.routes import auth_bp
    from app.main.routes import main_bp
    from app.results.routes import results_bp
    from app.api.files import files_bp
    from app.uploads import uploads_bp

    app.register_blueprint(uploads_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(results_bp)
    app.register_blueprint(files_bp)

    return app
