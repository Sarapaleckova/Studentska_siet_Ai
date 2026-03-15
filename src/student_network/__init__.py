"""Application factory for Študentská sieť."""

from pathlib import Path

from flask import Flask

from .db import init_app as init_db_app


def create_app() -> Flask:
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'studentska-siet-secret-key'
    app.config['DATABASE'] = str(Path(app.root_path) / 'data' / 'student_network.db')

    init_db_app(app)

    from .routes import register_routes

    register_routes(app)
    return app
