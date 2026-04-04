"""Group repository functions."""

from datetime import datetime
from sqlite3 import Row

from student_network.db import get_db


def get_groups_for_user(user_id: int, search_query: str) -> list[Row]:
    database = get_db()
    search_value = f"%{search_query.strip().lower()}%"
    rows = database.execute(
        """
        SELECT
            g.id,
            g.nazov,
            g.popis,
            g.obrazok_url,
            g.je_sukromna,
            gm.status AS membership_status,
            gm.role AS membership_role,
            COALESCE(member_counts.member_count, 0) AS member_count
        FROM groups_table g
        LEFT JOIN group_memberships gm
            ON gm.group_id = g.id
            AND gm.user_id = ?
        LEFT JOIN (
            SELECT group_id, COUNT(*) AS member_count
            FROM group_memberships
            WHERE status = 'member'
            GROUP BY group_id
        ) member_counts ON member_counts.group_id = g.id
        WHERE LOWER(g.nazov) LIKE ?
        ORDER BY g.nazov COLLATE NOCASE ASC
        """,
        (user_id, search_value),
    ).fetchall()
    return list(rows)


def get_group_by_id(group_id: int) -> Row | None:
    database = get_db()
    return database.execute(
        """
        SELECT
            g.id,
            g.nazov,
            g.popis,
            g.obrazok_url,
            g.je_sukromna,
            COALESCE(member_counts.member_count, 0) AS member_count
        FROM groups_table g
        LEFT JOIN (
            SELECT group_id, COUNT(*) AS member_count
            FROM group_memberships
            WHERE status = 'member'
            GROUP BY group_id
        ) member_counts ON member_counts.group_id = g.id
        WHERE g.id = ?
        """,
        (group_id,),
    ).fetchone()


def get_group_membership(group_id: int, user_id: int) -> Row | None:
    database = get_db()
    return database.execute(
        """
        SELECT id, group_id, user_id, status, role, requested_at, joined_at
        FROM group_memberships
        WHERE group_id = ? AND user_id = ?
        """,
        (group_id, user_id),
    ).fetchone()


def create_group(
    creator_user_id: int,
    nazov: str,
    popis: str,
    obrazok_url: str,
    je_sukromna: bool,
) -> int:
    database = get_db()
    now = datetime.utcnow().isoformat(timespec='seconds')
    cursor = database.execute(
        """
        INSERT INTO groups_table (nazov, popis, obrazok_url, je_sukromna, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (nazov, popis, obrazok_url, 1 if je_sukromna else 0, now),
    )
    group_id = int(cursor.lastrowid)

    database.execute(
        """
        INSERT INTO group_memberships (group_id, user_id, status, role, requested_at, joined_at)
        VALUES (?, ?, 'member', 'admin', ?, ?)
        """,
        (group_id, creator_user_id, now, now),
    )
    database.commit()
    return group_id


def update_group(
    group_id: int,
    nazov: str,
    popis: str,
    obrazok_url: str,
    je_sukromna: bool,
) -> None:
    database = get_db()
    database.execute(
        """
        UPDATE groups_table
        SET nazov = ?, popis = ?, obrazok_url = ?, je_sukromna = ?
        WHERE id = ?
        """,
        (nazov, popis, obrazok_url, 1 if je_sukromna else 0, group_id),
    )
    database.commit()


def join_public_group(group_id: int, user_id: int) -> str:
    database = get_db()
    now = datetime.utcnow().isoformat(timespec='seconds')
    membership = get_group_membership(group_id, user_id)

    if membership is None:
        database.execute(
            """
            INSERT INTO group_memberships (group_id, user_id, status, role, requested_at, joined_at)
            VALUES (?, ?, 'member', 'member', ?, ?)
            """,
            (group_id, user_id, now, now),
        )
        database.commit()
        return 'joined'

    if membership['status'] == 'member':
        return 'already-member'

    database.execute(
        """
        UPDATE group_memberships
        SET status = 'member', role = 'member', joined_at = ?
        WHERE group_id = ? AND user_id = ?
        """,
        (now, group_id, user_id),
    )
    database.commit()
    return 'joined'


def request_private_group_membership(group_id: int, user_id: int) -> str:
    database = get_db()
    now = datetime.utcnow().isoformat(timespec='seconds')
    membership = get_group_membership(group_id, user_id)

    if membership is None:
        database.execute(
            """
            INSERT INTO group_memberships (group_id, user_id, status, role, requested_at, joined_at)
            VALUES (?, ?, 'pending', 'member', ?, '')
            """,
            (group_id, user_id, now),
        )
        database.commit()
        return 'requested'

    if membership['status'] == 'pending':
        return 'already-requested'

    return 'already-member'


def get_group_members(group_id: int) -> list[Row]:
    database = get_db()
    rows = database.execute(
        """
        SELECT
            gm.user_id,
            gm.role,
            gm.joined_at,
            u.meno,
            u.priezvisko,
            up.profilova_fotka
        FROM group_memberships gm
        JOIN users u ON u.id = gm.user_id
        LEFT JOIN user_profiles up ON up.user_id = gm.user_id
        WHERE gm.group_id = ? AND gm.status = 'member'
        ORDER BY
            CASE WHEN gm.role = 'admin' THEN 0 ELSE 1 END ASC,
            u.priezvisko COLLATE NOCASE ASC,
            u.meno COLLATE NOCASE ASC
        """,
        (group_id,),
    ).fetchall()
    return list(rows)


def get_pending_group_requests(group_id: int) -> list[Row]:
    database = get_db()
    rows = database.execute(
        """
        SELECT
            gm.user_id,
            gm.requested_at,
            u.meno,
            u.priezvisko,
            up.profilova_fotka
        FROM group_memberships gm
        JOIN users u ON u.id = gm.user_id
        LEFT JOIN user_profiles up ON up.user_id = gm.user_id
        WHERE gm.group_id = ? AND gm.status = 'pending'
        ORDER BY gm.requested_at ASC
        """,
        (group_id,),
    ).fetchall()
    return list(rows)


def is_group_admin(group_id: int, user_id: int) -> bool:
    membership = get_group_membership(group_id=group_id, user_id=user_id)
    return bool(membership and membership['status'] == 'member' and membership['role'] == 'admin')


def update_member_role(group_id: int, member_user_id: int, role: str) -> None:
    database = get_db()
    database.execute(
        """
        UPDATE group_memberships
        SET role = ?
        WHERE group_id = ? AND user_id = ? AND status = 'member'
        """,
        (role, group_id, member_user_id),
    )
    database.commit()


def remove_group_member(group_id: int, member_user_id: int) -> None:
    database = get_db()
    database.execute(
        "DELETE FROM group_memberships WHERE group_id = ? AND user_id = ?",
        (group_id, member_user_id),
    )
    database.commit()


def approve_group_request(group_id: int, user_id: int) -> None:
    database = get_db()
    now = datetime.utcnow().isoformat(timespec='seconds')
    database.execute(
        """
        UPDATE group_memberships
        SET status = 'member', role = 'member', joined_at = ?
        WHERE group_id = ? AND user_id = ? AND status = 'pending'
        """,
        (now, group_id, user_id),
    )
    database.commit()


def reject_group_request(group_id: int, user_id: int) -> None:
    database = get_db()
    database.execute(
        "DELETE FROM group_memberships WHERE group_id = ? AND user_id = ? AND status = 'pending'",
        (group_id, user_id),
    )
    database.commit()


def count_group_admins(group_id: int) -> int:
    database = get_db()
    row = database.execute(
        """
        SELECT COUNT(*) AS cnt
        FROM group_memberships
        WHERE group_id = ? AND status = 'member' AND role = 'admin'
        """,
        (group_id,),
    ).fetchone()
    return int(row['cnt']) if row is not None else 0
