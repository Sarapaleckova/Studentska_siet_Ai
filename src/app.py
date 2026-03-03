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

                button {
                    padding: 12px 24px;
                    border: none;
                    border-radius: 8px;
                    font-size: 1rem;
                    cursor: pointer;
                }
            </style>
        </head>
        <body>
            <h1>Študentská sieť</h1>
            <div class="actions">
                <button type="button">Prihlásiť sa</button>
                <button type="button">Registrovať sa</button>
            </div>
        </body>
        </html>
        """
    )

if __name__ == '__main__':
    app.run(debug=True) v prostredí chýba Flask; nainštalujem ho a hneď znovu spustím server.
