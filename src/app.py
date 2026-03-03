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
    return render_template_string(
        """
        <!doctype html>
        <html lang="sk">
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <title>Prihlásenie</title>
            <style>
                body {
                    margin: 0;
                    min-height: 100vh;
                    background: #0b1f4d;
                    font-family: Arial, sans-serif;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                }

                .card {
                    background: #ffffff;
                    color: #000000;
                    width: 100%;
                    max-width: 420px;
                    border-radius: 12px;
                    padding: 24px;
                    box-sizing: border-box;
                }

                h1 {
                    margin: 0 0 20px 0;
                    text-align: center;
                }

                .field {
                    margin-bottom: 14px;
                }

                label {
                    display: block;
                    margin-bottom: 6px;
                }

                input {
                    width: 100%;
                    padding: 10px;
                    box-sizing: border-box;
                }

                .actions {
                    display: flex;
                    gap: 12px;
                    margin-top: 8px;
                }

                .btn,
                .btn-link {
                    flex: 1;
                    text-align: center;
                    padding: 10px;
                    border-radius: 8px;
                    border: 1px solid #c0c0c0;
                    text-decoration: none;
                    font-size: 1rem;
                    background: #ffffff;
                    color: #000000;
                    box-sizing: border-box;
                }

                .forgot {
                    margin-top: 12px;
                    width: 100%;
                    padding: 10px;
                    border-radius: 8px;
                    border: 1px solid #c0c0c0;
                    background: #ffffff;
                    font-size: 1rem;
                }
            </style>
        </head>
        <body>
            <div class="card">
                <h1>Prihlásenie</h1>
                <form>
                    <div class="field">
                        <label for="meno">Meno</label>
                        <input id="meno" name="meno" type="text">
                    </div>
                    <div class="field">
                        <label for="heslo">Heslo</label>
                        <input id="heslo" name="heslo" type="password">
                    </div>
                    <div class="actions">
                        <button class="btn" type="button">Ďalej</button>
                        <a class="btn-link" href="/">Späť</a>
                    </div>
                    <button class="forgot" type="button">Zabudnuté heslo</button>
                </form>
            </div>
        </body>
        </html>
        """
    )


@app.route('/registracia')
def registracia():
    return render_template_string(
        """
        <!doctype html>
        <html lang="sk">
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <title>Registrácia</title>
            <style>
                body {
                    margin: 0;
                    min-height: 100vh;
                    background: #0b1f4d;
                    font-family: Arial, sans-serif;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                }

                .card {
                    background: #ffffff;
                    color: #000000;
                    width: 100%;
                    max-width: 420px;
                    border-radius: 12px;
                    padding: 24px;
                    box-sizing: border-box;
                }

                h1 {
                    margin: 0 0 20px 0;
                    text-align: center;
                }

                .field {
                    margin-bottom: 14px;
                }

                label {
                    display: block;
                    margin-bottom: 6px;
                }

                input {
                    width: 100%;
                    padding: 10px;
                    box-sizing: border-box;
                }

                .actions {
                    display: flex;
                    gap: 12px;
                    margin-top: 8px;
                }

                .btn,
                .btn-link {
                    flex: 1;
                    text-align: center;
                    padding: 10px;
                    border-radius: 8px;
                    border: 1px solid #c0c0c0;
                    text-decoration: none;
                    font-size: 1rem;
                    background: #ffffff;
                    color: #000000;
                    box-sizing: border-box;
                }
            </style>
        </head>
        <body>
            <div class="card">
                <h1>Registrácia</h1>
                <form>
                    <div class="field">
                        <label for="meno">Meno</label>
                        <input id="meno" name="meno" type="text">
                    </div>
                    <div class="field">
                        <label for="priezvisko">Priezvisko</label>
                        <input id="priezvisko" name="priezvisko" type="text">
                    </div>
                    <div class="field">
                        <label for="email">E-mail</label>
                        <input id="email" name="email" type="email">
                    </div>
                    <div class="field">
                        <label for="heslo">Heslo</label>
                        <input id="heslo" name="heslo" type="password">
                    </div>
                    <div class="field">
                        <label for="znova_heslo">Znova heslo</label>
                        <input id="znova_heslo" name="znova_heslo" type="password">
                    </div>
                    <div class="actions">
                        <button class="btn" type="button">Ďalej</button>
                        <a class="btn-link" href="/">Späť</a>
                    </div>
                </form>
            </div>
        </body>
        </html>
        """
    )

if __name__ == '__main__':
    app.run(debug=True)
