"""Entry point for Študentská sieť."""

from student_network import create_app

app = create_app()


if __name__ == '__main__':
    # Run Flask dev server only (Socket.IO optional for real-time; HTTP fallback works fine)
    app.run(debug=True)
