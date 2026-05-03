try:
    from flask_socketio import SocketIO
except Exception:
    SocketIO = None

socketio = SocketIO(cors_allowed_origins='*') if SocketIO is not None else None
