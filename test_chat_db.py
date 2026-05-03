#!/usr/bin/env python
"""Quick test script to verify chat DB operations."""

from student_network.db import get_db
from student_network.repositories.group_chats import get_group_chats, create_group_chat
from student_network import create_app

app = create_app()
with app.app_context():
    db = get_db()
    
    # Get groups
    rows = db.execute('SELECT id, nazov FROM groups LIMIT 1').fetchall()
    groups = [dict(row) for row in rows]
    print(f'[ DB Query ] Groups found: {len(groups)}')
    
    if groups:
        gid = groups[0]['id']
        print(f'[ DB Query ] Testing with group ID: {gid}')
        
        # Get current chats
        chats = get_group_chats(gid)
        print(f'[ DB Query ] Group {gid} has {len(chats)} existing chats')
        for c in chats:
            print(f'  - Chat ID {c["id"]}: "{c["nazov"]}"')
        
        # Try creating a new chat
        try:
            print(f'\n[ DB Test ] Creating new chat...')
            new_chat_id = create_group_chat(gid, 'Test Chat - DB')
            print(f'[ DB Test ] ✓ Created new chat with ID: {new_chat_id}')
            
            # Verify
            chats_after = get_group_chats(gid)
            print(f'[ DB Test ] Group {gid} now has {len(chats_after)} chats')
            for c in chats_after:
                print(f'  - Chat ID {c["id"]}: "{c["nazov"]}"')
        except Exception as e:
            print(f'[ DB Test ] ✗ Error: {e}')
            import traceback
            traceback.print_exc()
    else:
        print('[ ERROR ] No groups found. Cannot test.')
