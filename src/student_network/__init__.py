"""Application factory for Študentská sieť."""

from pathlib import Path

from flask import Flask
try:
    from flask_socketio import SocketIO
except Exception:
    SocketIO = None

from .db import init_app as init_db_app


def create_app() -> Flask:
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'studentska-siet-secret-key'
    app.config['DATABASE'] = str(Path(app.root_path) / 'data' / 'student_network.db')
    app.config['PROFILE_PHOTO_UPLOAD_DIR'] = str(Path(app.root_path) / 'static' / 'uploads' / 'profile_photos')
    app.config['THEME_BG_UPLOAD_DIR'] = str(Path(app.root_path) / 'static' / 'uploads' / 'theme_backgrounds')
    app.config['GROUP_PHOTO_UPLOAD_DIR'] = str(Path(app.root_path) / 'static' / 'uploads' / 'group_photos')
    app.config['GROUP_FILE_UPLOAD_DIR'] = str(Path(app.root_path) / 'static' / 'uploads' / 'group_files')
    app.config['POST_IMAGE_UPLOAD_DIR'] = str(Path(app.root_path) / 'static' / 'uploads' / 'post_images')
    app.config['POST_FILE_UPLOAD_DIR'] = str(Path(app.root_path) / 'static' / 'uploads' / 'post_files')

    Path(app.config['PROFILE_PHOTO_UPLOAD_DIR']).mkdir(parents=True, exist_ok=True)
    Path(app.config['THEME_BG_UPLOAD_DIR']).mkdir(parents=True, exist_ok=True)
    Path(app.config['GROUP_PHOTO_UPLOAD_DIR']).mkdir(parents=True, exist_ok=True)
    Path(app.config['GROUP_FILE_UPLOAD_DIR']).mkdir(parents=True, exist_ok=True)
    Path(app.config['POST_IMAGE_UPLOAD_DIR']).mkdir(parents=True, exist_ok=True)
    Path(app.config['POST_FILE_UPLOAD_DIR']).mkdir(parents=True, exist_ok=True)

    init_db_app(app)

    from .routes import register_routes

    register_routes(app)
    # initialize SocketIO if available
    if SocketIO is not None:
        # create module-level socketio instance and init with app
        from . import socketio as _socketio_module
        if getattr(_socketio_module, 'socketio', None) is None:
            # socketio module will create instance on import
            pass
        else:
            _socketio_module.socketio.init_app(app)
        # import events to register handlers
        try:
            from . import socketio_events  # noqa: F401
        except Exception:
            # best-effort: don't crash app if socket events fail to import
            pass
    return app
