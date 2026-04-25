"""Group file repository functions."""

from datetime import datetime
from sqlite3 import Row

from student_network.db import get_db


def create_group_file(
    group_id: int,
    uploaded_by_user_id: int,
    stored_subor: str,
    original_nazov: str,
    typ_suboru: str,
    folder_id: int | None = None,
) -> int:
    database = get_db()
    now = datetime.utcnow().isoformat(timespec='seconds')
    cursor = database.execute(
        """
        INSERT INTO group_files (
            group_id,
            uploaded_by_user_id,
            folder_id,
            stored_subor,
            original_nazov,
            typ_suboru,
            uploaded_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (group_id, uploaded_by_user_id, folder_id, stored_subor, original_nazov, typ_suboru, now),
    )
    database.commit()
    return int(cursor.lastrowid)


def create_group_file_folder(group_id: int, created_by_user_id: int, nazov: str) -> int | None:
    database = get_db()
    folder_name = nazov.strip()
    if not folder_name:
        return None

    existing = database.execute(
        """
        SELECT id
        FROM group_file_folders
        WHERE group_id = ? AND LOWER(nazov) = LOWER(?)
        """,
        (group_id, folder_name),
    ).fetchone()
    if existing is not None:
        return None

    now = datetime.utcnow().isoformat(timespec='seconds')
    cursor = database.execute(
        """
        INSERT INTO group_file_folders (group_id, created_by_user_id, nazov, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (group_id, created_by_user_id, folder_name, now),
    )
    database.commit()
    return int(cursor.lastrowid)


def get_group_file_folders(group_id: int) -> list[Row]:
    database = get_db()
    rows = database.execute(
        """
        SELECT
            gff.id,
            gff.group_id,
            gff.nazov,
            gff.created_at,
            gff.created_by_user_id,
            u.meno AS author_meno,
            u.priezvisko AS author_priezvisko
        FROM group_file_folders gff
        JOIN users u ON u.id = gff.created_by_user_id
        WHERE gff.group_id = ?
        ORDER BY gff.nazov COLLATE NOCASE ASC, gff.id ASC
        """,
        (group_id,),
    ).fetchall()
    return list(rows)


def get_group_file_folder_by_id(group_id: int, folder_id: int) -> Row | None:
    database = get_db()
    return database.execute(
        """
        SELECT id, group_id, nazov, created_at, created_by_user_id
        FROM group_file_folders
        WHERE group_id = ? AND id = ?
        """,
        (group_id, folder_id),
    ).fetchone()


def get_group_files(group_id: int, folder_id: int | None = None, only_unassigned: bool = False) -> list[Row]:
    database = get_db()
    where_clause = "WHERE gf.group_id = ?"
    params: list[object] = [group_id]

    if only_unassigned:
        where_clause += " AND gf.folder_id IS NULL"
    elif folder_id is not None:
        where_clause += " AND gf.folder_id = ?"
        params.append(folder_id)

    rows = database.execute(
        """
        SELECT
            gf.id,
            gf.group_id,
            gf.uploaded_by_user_id,
            gf.folder_id,
            gf.stored_subor,
            gf.original_nazov,
            gf.typ_suboru,
            gf.uploaded_at,
            gff.nazov AS folder_nazov,
            u.meno AS author_meno,
            u.priezvisko AS author_priezvisko
        FROM group_files gf
        LEFT JOIN group_file_folders gff ON gff.id = gf.folder_id
        JOIN users u ON u.id = gf.uploaded_by_user_id
        """
        + where_clause
        +
        """
        ORDER BY gf.uploaded_at DESC, gf.id DESC
        """,
        tuple(params),
    ).fetchall()
    return list(rows)


def update_group_file_folder(group_id: int, group_file_id: int, folder_id: int | None) -> bool:
    database = get_db()
    cursor = database.execute(
        """
        UPDATE group_files
        SET folder_id = ?
        WHERE id = ? AND group_id = ?
        """,
        (folder_id, group_file_id, group_id),
    )
    database.commit()
    return int(cursor.rowcount) > 0


def get_group_file_by_id(group_id: int, group_file_id: int) -> Row | None:
    database = get_db()
    return database.execute(
        """
        SELECT
            gf.id,
            gf.group_id,
            gf.uploaded_by_user_id,
            gf.folder_id,
            gf.stored_subor,
            gf.original_nazov,
            gf.typ_suboru,
            gf.uploaded_at,
            gff.nazov AS folder_nazov,
            u.meno AS author_meno,
            u.priezvisko AS author_priezvisko
        FROM group_files gf
        LEFT JOIN group_file_folders gff ON gff.id = gf.folder_id
        JOIN users u ON u.id = gf.uploaded_by_user_id
        WHERE gf.group_id = ? AND gf.id = ?
        """,
        (group_id, group_file_id),
    ).fetchone()
