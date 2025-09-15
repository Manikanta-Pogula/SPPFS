# app/__init__.py
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from config import Config

# Extensions
db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
login_manager.login_view = "auth.login"


def create_app():
    app = Flask(
        __name__,
        template_folder="../templates",
        static_folder="../static",
        instance_relative_config=False
    )
    app.config.from_object(Config)

    # init extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)

    # import models so db knows them
    from app import models
    from app.models import Institution

    # user loader for flask-login
    @login_manager.user_loader
    def load_user(user_id):
        return models.User.query.get(int(user_id))

    # Ensure at least one Institution row exists
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

    # Register blueprints
    from app.auth.routes import auth_bp
    from app.main.routes import main_bp
    from app.results.routes import results_bp
    from app.files.routes import files_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(results_bp)
    app.register_blueprint(files_bp)

    return app
