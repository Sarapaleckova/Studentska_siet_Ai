"""Card/Flashcard repository functions."""

from datetime import datetime
from typing import Optional
from sqlite3 import Row

from student_network.db import get_db


def create_deck(
    user_id: int,
    name: str,
    description: str = '',
    color: str = '#FFE5B4',
) -> int:
    """Create a new card deck."""
    database = get_db()
    cursor = database.execute(
        """
        INSERT INTO card_decks (user_id, name, description, color, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (user_id, name, description, color, datetime.utcnow().isoformat(timespec='seconds')),
    )
    database.commit()
    return int(cursor.lastrowid)


def get_deck_by_id(deck_id: int) -> Optional[Row]:
    """Get a deck by ID."""
    database = get_db()
    return database.execute(
        "SELECT * FROM card_decks WHERE id = ?",
        (deck_id,),
    ).fetchone()


def get_decks_for_user(user_id: int) -> list[Row]:
    """Get all decks for a user."""
    database = get_db()
    return database.execute(
        "SELECT * FROM card_decks WHERE user_id = ? ORDER BY created_at DESC",
        (user_id,),
    ).fetchall()


def update_deck(deck_id: int, name: str, description: str = '') -> bool:
    """Update a deck."""
    database = get_db()
    database.execute(
        "UPDATE card_decks SET name = ?, description = ? WHERE id = ?",
        (name, description, deck_id),
    )
    database.commit()
    return True


def delete_deck(deck_id: int) -> bool:
    """Delete a deck and all its cards."""
    database = get_db()
    database.execute("DELETE FROM card_decks WHERE id = ?", (deck_id,))
    database.commit()
    return True


def create_card(
    deck_id: int,
    question: str,
    answer: str,
    color: Optional[str] = None,
) -> int:
    """Create a new card in a deck."""
    database = get_db()
    deck = get_deck_by_id(deck_id)
    card_color = color if color is not None else (deck['color'] if deck is not None and deck['color'] else '#FFE5B4')
    cursor = database.execute(
        """
        INSERT INTO cards (deck_id, question, answer, color, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (deck_id, question, answer, card_color, datetime.utcnow().isoformat(timespec='seconds')),
    )
    database.commit()
    return int(cursor.lastrowid)


def get_card_by_id(card_id: int) -> Optional[Row]:
    """Get a card by ID."""
    database = get_db()
    return database.execute(
        "SELECT * FROM cards WHERE id = ?",
        (card_id,),
    ).fetchone()


def get_cards_for_deck(deck_id: int) -> list[Row]:
    """Get all cards in a deck."""
    database = get_db()
    return database.execute(
        "SELECT * FROM cards WHERE deck_id = ? ORDER BY created_at",
        (deck_id,),
    ).fetchall()


def update_card(
    card_id: int,
    question: Optional[str] = None,
    answer: Optional[str] = None,
    color: Optional[str] = None,
) -> bool:
    """Update a card."""
    database = get_db()
    card = get_card_by_id(card_id)
    if card is None:
        return False

    current_question = question if question is not None else card['question']
    current_answer = answer if answer is not None else card['answer']
    current_color = color if color is not None else card['color']

    database.execute(
        "UPDATE cards SET question = ?, answer = ?, color = ? WHERE id = ?",
        (current_question, current_answer, current_color, card_id),
    )
    database.commit()
    return True


def delete_card(card_id: int) -> bool:
    """Delete a card."""
    database = get_db()
    database.execute("DELETE FROM cards WHERE id = ?", (card_id,))
    database.commit()
    return True


def create_attempt(
    deck_id: int,
    user_id: int,
    correct_count: int,
    incorrect_count: int,
) -> int:
    """Create a card attempt record."""
    database = get_db()
    cursor = database.execute(
        """
        INSERT INTO card_attempts (deck_id, user_id, correct_count, incorrect_count, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (deck_id, user_id, correct_count, incorrect_count, datetime.utcnow().isoformat(timespec='seconds')),
    )
    database.commit()
    return int(cursor.lastrowid)


def get_deck_attempts(deck_id: int) -> list[Row]:
    """Get all attempts for a deck."""
    database = get_db()
    return database.execute(
        "SELECT * FROM card_attempts WHERE deck_id = ? ORDER BY created_at DESC",
        (deck_id,),
    ).fetchall()
