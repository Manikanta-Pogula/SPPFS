from flask import Flask
from flask_migrate import Migrate
from config import Config
from extension import db, migrate

migrate = Migrate()

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    migrate.init_app(app, db)

    # Register blueprints
    from routes import auth
    app.register_blueprint(auth)

    return app

if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
