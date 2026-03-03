"""Route definitions for Študentská sieť."""

from flask import Flask, render_template


def register_routes(app: Flask) -> None:
    @app.route('/')
    def index() -> str:
        return render_template('index.html')

    @app.route('/prihlasenie')
    def prihlasenie() -> str:
        return render_template('prihlasenie.html')

    @app.route('/registracia')
    def registracia() -> str:
        return render_template('registracia.html')
