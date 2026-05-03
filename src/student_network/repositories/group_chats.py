from typing import List, Dict, Optional
import sqlite3
from flask import g

from student_network.db import get_db


def get_group_chats(group_id: int) -> List[Dict]:
    db = get_db()
    rows = db.execute(
        """
        SELECT id, group_id, nazov, created_at
        FROM group_chats
        WHERE group_id = ?
        ORDER BY id ASC
        """,
        (group_id,)
    ).fetchall()

    return [dict(row) for row in rows]


def create_group_chat(group_id: int, nazov: str) -> int:
    db = get_db()
    cur = db.execute(
        "INSERT INTO group_chats (group_id, nazov, created_at) VALUES (?, ?, datetime('now'))",
        (group_id, nazov),
    )
    db.commit()
    return cur.lastrowid


def get_chat_by_id(chat_id: int) -> Optional[Dict]:
    db = get_db()
    row = db.execute(
        "SELECT id, group_id, nazov, created_at FROM group_chats WHERE id = ?",
        (chat_id,),
    ).fetchone()
    return dict(row) if row else None


def get_chat_messages(chat_id: int, limit: int = 200) -> List[Dict]:
    db = get_db()
    rows = db.execute(
        """
        SELECT m.id, m.chat_id, m.sender_user_id, m.content, m.created_at,
               u.meno AS author_meno, u.priezvisko AS author_priezvisko, p.profilova_fotka
        FROM group_chat_messages m
        JOIN users u ON u.id = m.sender_user_id
        LEFT JOIN user_profiles p ON p.user_id = u.id
        WHERE m.chat_id = ?
        ORDER BY m.id ASC
        LIMIT ?
        """,
        (chat_id, limit),
    ).fetchall()

    return [dict(row) for row in rows]


def create_group_chat_message(chat_id: int, sender_user_id: int, content: str) -> int:
    db = get_db()
    cur = db.execute(
        "INSERT INTO group_chat_messages (chat_id, sender_user_id, content, created_at) VALUES (?, ?, ?, datetime('now'))",
        (chat_id, sender_user_id, content),
    )
    db.commit()
    return cur.lastrowid
