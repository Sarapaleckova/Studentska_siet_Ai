#!/usr/bin/env python
"""Query database for group_chats."""

import sqlite3

db = sqlite3.connect('src/student_network/data/student_network.db')
db.row_factory = sqlite3.Row

# Check group_chats table
print('[ DB ] Checking group_chats:')
cursor = db.execute('SELECT COUNT(*) FROM group_chats')
count = cursor.fetchone()[0]
print(f'  Total chats: {count}')

if count > 0:
    cursor = db.execute('SELECT id, group_id, nazov, created_at FROM group_chats ORDER BY id DESC LIMIT 10')
    for row in cursor.fetchall():
        print(f'  - ID {row[0]}: Group {row[1]}: "{row[2]}" (created {row[3]})')

# Check messages
print('\n[ DB ] Checking group_chat_messages:')
cursor = db.execute('SELECT COUNT(*) FROM group_chat_messages')
msg_count = cursor.fetchone()[0]
print(f'  Total messages: {msg_count}')

if msg_count > 0:
    cursor = db.execute('''
        SELECT m.id, m.chat_id, m.sender_user_id, m.content, m.created_at
        FROM group_chat_messages m
        ORDER BY m.id DESC LIMIT 5
    ''')
    for row in cursor.fetchall():
        print(f'  - Msg ID {row[0]}: Chat {row[1]}: User {row[2]}: "{row[3]}" ({row[4]})')

db.close()

