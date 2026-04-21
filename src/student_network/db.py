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
    theme_preset TEXT NOT NULL DEFAULT 'default',
    theme_bg_color TEXT NOT NULL DEFAULT '#0b1f4d',
    theme_nav_color TEXT NOT NULL DEFAULT '#071433',
    theme_bg_image TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS user_additional_emails (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    email TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(user_id, email),
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

CREATE TABLE IF NOT EXISTS post_ratings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    rating INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
    rated_at TEXT NOT NULL,
    UNIQUE(post_id, user_id),
    FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS post_comments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    parent_comment_id INTEGER,
    text TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (parent_comment_id) REFERENCES post_comments(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS groups_table (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nazov TEXT NOT NULL UNIQUE,
    popis TEXT NOT NULL DEFAULT '',
    obrazok_url TEXT NOT NULL DEFAULT '',
    je_sukromna INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS group_memberships (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('member', 'pending')),
    role TEXT NOT NULL DEFAULT 'member' CHECK (role IN ('admin', 'member')),
    requested_at TEXT NOT NULL,
    joined_at TEXT NOT NULL DEFAULT '',
    UNIQUE(group_id, user_id),
    FOREIGN KEY (group_id) REFERENCES groups_table(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS group_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id INTEGER NOT NULL,
    created_by_user_id INTEGER NOT NULL,
    event_date TEXT NOT NULL,
    event_time TEXT NOT NULL,
    nazov TEXT NOT NULL,
    popis TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (group_id) REFERENCES groups_table(id) ON DELETE CASCADE,
    FOREIGN KEY (created_by_user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS group_event_notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id INTEGER NOT NULL,
    event_id INTEGER,
    actor_user_id INTEGER NOT NULL,
    action_type TEXT NOT NULL CHECK (action_type IN ('create', 'update', 'delete')),
    event_date TEXT NOT NULL DEFAULT '',
    event_time TEXT NOT NULL DEFAULT '',
    message TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (group_id) REFERENCES groups_table(id) ON DELETE CASCADE,
    FOREIGN KEY (event_id) REFERENCES group_events(id) ON DELETE SET NULL,
    FOREIGN KEY (actor_user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS group_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id INTEGER NOT NULL,
    uploaded_by_user_id INTEGER NOT NULL,
    stored_subor TEXT NOT NULL,
    original_nazov TEXT NOT NULL,
    typ_suboru TEXT NOT NULL DEFAULT '',
    uploaded_at TEXT NOT NULL,
    FOREIGN KEY (group_id) REFERENCES groups_table(id) ON DELETE CASCADE,
    FOREIGN KEY (uploaded_by_user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS group_board_posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id INTEGER NOT NULL,
    author_user_id INTEGER NOT NULL,
    board_type TEXT NOT NULL CHECK (board_type IN ('announcement', 'member')),
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (group_id) REFERENCES groups_table(id) ON DELETE CASCADE,
    FOREIGN KEY (author_user_id) REFERENCES users(id) ON DELETE CASCADE
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
    ensure_profile_theme_columns(database)
    ensure_group_membership_joined_at_column(database)
    ensure_group_membership_role_column(database)
    ensure_group_event_notification_schedule_columns(database)
    ensure_seed_groups(database)
    database.commit()


def ensure_profile_photo_column(database: sqlite3.Connection) -> None:
    columns = database.execute("PRAGMA table_info(user_profiles)").fetchall()
    existing_column_names = {column['name'] for column in columns}

    if 'profilova_fotka' not in existing_column_names:
        database.execute(
            "ALTER TABLE user_profiles ADD COLUMN profilova_fotka TEXT NOT NULL DEFAULT ''"
        )


def ensure_profile_theme_columns(database: sqlite3.Connection) -> None:
    columns = database.execute("PRAGMA table_info(user_profiles)").fetchall()
    existing_column_names = {column['name'] for column in columns}

    if 'theme_preset' not in existing_column_names:
        database.execute(
            "ALTER TABLE user_profiles ADD COLUMN theme_preset TEXT NOT NULL DEFAULT 'default'"
        )

    if 'theme_bg_color' not in existing_column_names:
        database.execute(
            "ALTER TABLE user_profiles ADD COLUMN theme_bg_color TEXT NOT NULL DEFAULT '#0b1f4d'"
        )

    if 'theme_nav_color' not in existing_column_names:
        database.execute(
            "ALTER TABLE user_profiles ADD COLUMN theme_nav_color TEXT NOT NULL DEFAULT '#071433'"
        )

    if 'theme_bg_image' not in existing_column_names:
        database.execute(
            "ALTER TABLE user_profiles ADD COLUMN theme_bg_image TEXT NOT NULL DEFAULT ''"
        )


def ensure_group_membership_joined_at_column(database: sqlite3.Connection) -> None:
    columns = database.execute("PRAGMA table_info(group_memberships)").fetchall()
    existing_column_names = {column['name'] for column in columns}

    if 'joined_at' not in existing_column_names:
        database.execute(
            "ALTER TABLE group_memberships ADD COLUMN joined_at TEXT NOT NULL DEFAULT ''"
        )


def ensure_group_membership_role_column(database: sqlite3.Connection) -> None:
    columns = database.execute("PRAGMA table_info(group_memberships)").fetchall()
    existing_column_names = {column['name'] for column in columns}

    if 'role' not in existing_column_names:
        database.execute(
            "ALTER TABLE group_memberships ADD COLUMN role TEXT NOT NULL DEFAULT 'member'"
        )

    database.execute(
        """
        UPDATE group_memberships
        SET role = 'member'
        WHERE role IS NULL OR TRIM(role) = ''
        """
    )

    group_rows = database.execute("SELECT id FROM groups_table").fetchall()
    for group_row in group_rows:
        group_id = int(group_row['id'])
        admin_count_row = database.execute(
            """
            SELECT COUNT(*) AS cnt
            FROM group_memberships
            WHERE group_id = ? AND status = 'member' AND role = 'admin'
            """,
            (group_id,),
        ).fetchone()

        if admin_count_row is not None and int(admin_count_row['cnt']) > 0:
            continue

        first_member_row = database.execute(
            """
            SELECT id
            FROM group_memberships
            WHERE group_id = ? AND status = 'member'
            ORDER BY
                CASE WHEN joined_at != '' THEN joined_at ELSE requested_at END ASC,
                id ASC
            LIMIT 1
            """,
            (group_id,),
        ).fetchone()

        if first_member_row is not None:
            database.execute(
                "UPDATE group_memberships SET role = 'admin' WHERE id = ?",
                (int(first_member_row['id']),),
            )


def ensure_group_event_notification_schedule_columns(database: sqlite3.Connection) -> None:
    columns = database.execute("PRAGMA table_info(group_event_notifications)").fetchall()
    existing_column_names = {column['name'] for column in columns}

    if 'event_date' not in existing_column_names:
        database.execute(
            "ALTER TABLE group_event_notifications ADD COLUMN event_date TEXT NOT NULL DEFAULT ''"
        )

    if 'event_time' not in existing_column_names:
        database.execute(
            "ALTER TABLE group_event_notifications ADD COLUMN event_time TEXT NOT NULL DEFAULT ''"
        )


def ensure_seed_groups(database: sqlite3.Connection) -> None:
    row = database.execute("SELECT COUNT(*) AS cnt FROM groups_table").fetchone()
    if row is not None and int(row['cnt']) > 0:
        return

    database.executemany(
        """
        INSERT INTO groups_table (nazov, popis, obrazok_url, je_sukromna, created_at)
        VALUES (?, ?, ?, ?, datetime('now'))
        """,
        [
            (
                'Programatori TUKE',
                'Skupina pre studentov programovania na TUKE. Delime sa o zdrojaky, tipy a pomoc s projektmi.',
                'https://images.unsplash.com/photo-1515879218367-8466d910aaa4?auto=format&fit=crop&w=1200&q=80',
                0,
            ),
            (
                'Matematika bez stresu',
                'Spolocne pocitanie uloh z matematiky, pripravy na testy a zdielanie studijnych materialov.',
                'https://images.unsplash.com/photo-1635070041078-e363dbe005cb?auto=format&fit=crop&w=1200&q=80',
                0,
            ),
            (
                'AI Lab Students',
                'Diskusie o AI, machine learning projektoch, modeloch a experimentovani.',
                'https://images.unsplash.com/photo-1677442136019-21780ecad995?auto=format&fit=crop&w=1200&q=80',
                1,
            ),
            (
                'Sport na internate',
                'Organizujeme futbal, volejbal a beh. Kazdy novy clen je vitany.',
                'https://images.unsplash.com/photo-1461896836934-ffe607ba8211?auto=format&fit=crop&w=1200&q=80',
                0,
            ),
            (
                'Kyberbezpecnost TUKE',
                'Skupina pre nadsencov kyberbezpecnosti, CTF ulohy a prednasky.',
                'https://images.unsplash.com/photo-1550751827-4bd374c3f58b?auto=format&fit=crop&w=1200&q=80',
                1,
            ),
        ],
    )


def current_database_path() -> str:
    from flask import current_app

    return current_app.config['DATABASE']
