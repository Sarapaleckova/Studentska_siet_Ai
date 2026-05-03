"""Entry point for Študentská sieť."""

from student_network import create_app

app = create_app()


if __name__ == '__main__':
    try:
        from student_network.socketio import socketio
    except Exception:
        socketio = None

    if socketio is not None:
        socketio.run(app, debug=True)
    else:
        app.run(debug=True)
