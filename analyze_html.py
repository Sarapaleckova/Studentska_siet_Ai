#!/usr/bin/env python
"""Analyze returned HTML from group detail page."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from student_network import create_app

app = create_app()

# Create test client
client = app.test_client()

# Simulate login
with app.app_context():
    from student_network.db import get_db
    db = get_db()
    
    # Get test user
    user_row = db.execute('SELECT id FROM users LIMIT 1').fetchone()
    user_id = user_row[0] if user_row else None
    
    # Get group
    group_row = db.execute('''
        SELECT g.id FROM groups_table g
        WHERE g.id IN (SELECT group_id FROM group_memberships  WHERE user_id = ?)
        LIMIT 1
    ''', (user_id,)).fetchone()
    
    group_id = group_row[0] if group_row else 6

with client.session_transaction() as sess:
    sess['user_id'] = user_id

# Fetch group detail page with "spravy" tab
print(f'[ TEST ] Fetching group {group_id} detail page with "spravy" tab...')
response = client.get(f'/studentska-siet/skupiny/{group_id}?tab=spravy')
html = response.get_data(as_text=True)

# Check for chat elements
print(f'\n[ HTML ANALYSIS ]')
print(f'  Total HTML size: {len(html)} bytes')
print(f'  Contains "group-chat-layout": {"group-chat-layout" in html}')
print(f'  Contains "id=\"chat-list\"": {"id=\"chat-list\"" in html}')
print(f'  Contains "create-chat-button": {"create-chat-button" in html}')
print(f'  Contains "Promatorikovia": {"Promatorikovia" in html}')
print(f'  Contains "Správy": {"Správy" in html}')

# Find and print group_chats section
if 'id="chat-list"' in html:
    start = html.find('id="chat-list"')
    end = html.find('</ul>', start) + 5
    section = html[max(0, start-50):min(len(html), end+100)]
    print(f'\n[ CHAT LIST HTML ]')
    print(section[:300])
else:
    print('\n[ ERROR ] No chat-list found!')
