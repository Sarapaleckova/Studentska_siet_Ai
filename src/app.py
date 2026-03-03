"""Študentská sieť - základná aplikácia."""

from flask import Flask, render_template_string

app = Flask(__name__)

@app.route('/')
def index():
    return render_template_string(
        """
        <!doctype html>
        <html lang="sk">
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <title>Študentská sieť</title>
            <style>
                body {
                    margin: 0;
                    min-height: 100vh;
                    background: #0b1f4d;
                    color: #ffffff;
                    font-family: Arial, sans-serif;
                    display: flex;
                    flex-direction: column;
                    justify-content: space-between;
                    align-items: center;
                }

                h1 {
                    margin-top: 48px;
                    font-size: 2rem;
                }

                .actions {
                    margin-bottom: 64px;
                    display: flex;
                    gap: 16px;
                }

                .button-link {
                    display: inline-block;
                    padding: 12px 24px;
                    border: none;
                    border-radius: 8px;
                    font-size: 1rem;
                    text-decoration: none;
                    color: #000000;
                    background: #ffffff;
                }
            </style>
        </head>
        <body>
            <h1>Študentská sieť</h1>
            <div class="actions">
                <a class="button-link" href="/prihlasenie">Prihlásiť sa</a>
                <a class="button-link" href="/registracia">Registrovať sa</a>
            </div>
        </body>
        </html>
        """
    )


@app.route('/prihlasenie')
def prihlasenie():
    return "Prihlásenie"


@app.route('/registracia')
def registracia():
    return "Registrácia"

if __name__ == '__main__':
    app.run(debug=True)
