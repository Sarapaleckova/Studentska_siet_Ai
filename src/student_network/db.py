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

CREATE TABLE IF NOT EXISTS user_profiles (
    user_id INTEGER PRIMARY KEY,
    skola TEXT NOT NULL DEFAULT '',
    rocnik_studia TEXT NOT NULL DEFAULT '',
    popis TEXT NOT NULL DEFAULT '',
    profilova_fotka TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    author_id INTEGER NOT NULL,
    nazov TEXT NOT NULL,
    popis TEXT NOT NULL DEFAULT '',
    nahladovy_obrazok TEXT NOT NULL DEFAULT '',
    subor TEXT NOT NULL DEFAULT '',
    subor_povodny_nazov TEXT NOT NULL DEFAULT '',
    datum_vytvorenia TEXT NOT NULL,
    FOREIGN KEY (author_id) REFERENCES users(id) ON DELETE CASCADE
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
    ensure_profile_photo_column(database)
    database.commit()


def ensure_profile_photo_column(database: sqlite3.Connection) -> None:
    columns = database.execute("PRAGMA table_info(user_profiles)").fetchall()
    existing_column_names = {column['name'] for column in columns}

    if 'profilova_fotka' not in existing_column_names:
        database.execute(
            "ALTER TABLE user_profiles ADD COLUMN profilova_fotka TEXT NOT NULL DEFAULT ''"
        )


def current_database_path() -> str:
    from flask import current_app

    return current_app.config['DATABASE']
