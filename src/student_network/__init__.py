"""Application factory for Študentská sieť."""

from pathlib import Path

from flask import Flask

from .db import init_app as init_db_app


def create_app() -> Flask:
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'studentska-siet-secret-key'
    app.config['DATABASE'] = str(Path(app.root_path) / 'data' / 'student_network.db')
    app.config['PROFILE_PHOTO_UPLOAD_DIR'] = str(Path(app.root_path) / 'static' / 'uploads' / 'profile_photos')
    app.config['POST_IMAGE_UPLOAD_DIR'] = str(Path(app.root_path) / 'static' / 'uploads' / 'post_images')
    app.config['POST_FILE_UPLOAD_DIR'] = str(Path(app.root_path) / 'static' / 'uploads' / 'post_files')

    Path(app.config['PROFILE_PHOTO_UPLOAD_DIR']).mkdir(parents=True, exist_ok=True)
    Path(app.config['POST_IMAGE_UPLOAD_DIR']).mkdir(parents=True, exist_ok=True)
    Path(app.config['POST_FILE_UPLOAD_DIR']).mkdir(parents=True, exist_ok=True)

    init_db_app(app)

    from .routes import register_routes

    register_routes(app)
    return app
