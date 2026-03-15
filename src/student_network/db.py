"""Database helpers for Študentská sieť."""

from pathlib import Path
import sqlite3

from flask import Flask, g

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    meno TEXT NOT NULL,
    priezvisko TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    heslo TEXT NOT NULL,
    datum_vytvorenia_uctu TEXT NOT NULL
);
"""


def init_app(app: Flask) -> None:
    database_path = Path(app.config['DATABASE'])
    database_path.parent.mkdir(parents=True, exist_ok=True)

    app.teardown_appcontext(close_db)

    with app.app_context():
        init_db()


def get_db() -> sqlite3.Connection:
    if 'db' not in g:
        g.db = sqlite3.connect(current_database_path())
        g.db.row_factory = sqlite3.Row

    return g.db


def close_db(_exception: Exception | None = None) -> None:
    database = g.pop('db', None)

    if database is not None:
        database.close()


def init_db() -> None:
    database = get_db()
    database.executescript(SCHEMA)
    database.commit()


def current_database_path() -> str:
    from flask import current_app

    return current_app.config['DATABASE']
