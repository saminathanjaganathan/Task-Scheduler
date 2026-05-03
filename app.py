from flask import Flask
from flask_wtf.csrf import CSRFProtect
from config import Config
from models import db

csrf = CSRFProtect()


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    csrf.init_app(app)

    from routes import main_bp
    app.register_blueprint(main_bp)

    with app.app_context():
        db.create_all()

    # Start the background scheduler for daily/weekly tasks
    from scheduler import init_scheduler
    init_scheduler(app)

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, use_reloader=False)
