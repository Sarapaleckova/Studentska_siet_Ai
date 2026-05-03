#!/usr/bin/env python
"""Test chat HTTP endpoints directly."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from student_network import create_app
from student_network.db import get_db
import json

app = create_app()

# Create test client
client = app.test_client()

# Get first user and group from DB
with app.app_context():
    db = get_db()
    
    # Get test user
    user_row = db.execute('SELECT id FROM users LIMIT 1').fetchone()
    if not user_row:
        print('[ ERROR ] No users found')
        exit(1)
    
    user_id = user_row[0]
    print(f'[ TEST ] Using user ID: {user_id}')
    
    # Get first group that user is member of
    group_row = db.execute('''
        SELECT g.id FROM groups_table g
        WHERE g.id IN (SELECT group_id FROM group_memberships WHERE user_id = ?)
        LIMIT 1
    ''', (user_id,)).fetchone()
    
    if not group_row:
        print('[ ERROR ] User is not member of any group')
        exit(1)
    
    group_id = group_row[0]
    print(f'[ TEST ] Using group ID: {group_id}')

# Simulate login
print('\n[ TEST ] Logging in...')
with client.session_transaction() as sess:
    sess['user_id'] = user_id

# Test creating a chat (HTTP fallback)
print(f'[ TEST] Creating chat via HTTP POST /studentska-siet/skupiny/{group_id}/chats')
response = client.post(
    f'/studentska-siet/skupiny/{group_id}/chats',
    json={'name': 'Test Chat HTTP'},
    content_type='application/json'
)
print(f'  Status: {response.status_code}')
print(f'  Response: {response.get_json() or response.get_data(as_text=True)[:200]}')

if response.status_code == 200:
    data = response.get_json()
    chat_id = data.get('id')
    print(f'\n[ SUCCESS ] Created chat ID: {chat_id}')
    
    # Verify in DB
    with app.app_context():
        db = get_db()
        row = db.execute('SELECT * FROM group_chats WHERE id = ?', (chat_id,)).fetchone()
        if row:
            print(f'[ SUCCESS ] Chat verified in DB: {dict(row)}')
        else:
            print(f'[ ERROR ] Chat not found in DB')
    
    # Try sending a message
    print(f'\n[ TEST ] Sending message to chat...')
    response = client.post(
        f'/studentska-siet/skupiny/{group_id}/chats/{chat_id}/messages',
        json={'content': 'Test message from HTTP'},
        content_type='application/json'
    )
    print(f'  Status: {response.status_code}')
    print(f'  Response: {response.get_json() or response.get_data(as_text=True)[:200]}')
    
    if response.status_code == 200:
        print('[ SUCCESS ] Message sent')
else:
    print(f'[ ERROR ] Failed to create chat: {response.status_code}')
    print(f'  Response: {response.get_data(as_text=True)[:300]}')
