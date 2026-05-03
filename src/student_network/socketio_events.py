from flask import session, g, url_for
from flask_socketio import join_room, leave_room, emit

from student_network.socketio import socketio
from student_network.repositories.group_chats import (
    get_group_chats, get_chat_by_id, get_chat_messages, create_group_chat_message, create_group_chat,
)
from student_network.repositories.groups import get_group_membership
from student_network.repositories.users import get_user_by_id
from student_network.routes import _format_datetime_eu
from datetime import datetime


@socketio.on('join_chat')
def handle_join_chat(data):
    try:
        chat_id = int(data.get('chat_id', 0))
        group_id = int(data.get('group_id', 0))
    except Exception:
        return

    user_id = session.get('user_id')
    if not user_id:
        emit('error', {'message': 'not-authenticated'})
        return

    membership = get_group_membership(group_id=group_id, user_id=int(user_id))
    if membership is None or membership['status'] != 'member':
        emit('error', {'message': 'not-member'})
        return

    room = f"group_{group_id}_chat_{chat_id}"
    join_room(room)

    # load recent messages
    messages = get_chat_messages(chat_id=chat_id, limit=500)
    payload = []
    for m in messages:
        payload.append({
            'id': m['id'],
            'chat_id': m['chat_id'],
            'sender_user_id': m['sender_user_id'],
            'author': f"{m['author_meno']} {m['author_priezvisko']}",
            'author_profile_url': url_for('aplikacia_profil_verejny', user_id=m['sender_user_id']) if m['sender_user_id'] else '',
            'profile_photo': url_for('static', filename=m['profilova_fotka']) if m.get('profilova_fotka') else '',
            'content': m['content'],
            'created_at': _format_datetime_eu(m['created_at']),
        })

    emit('load_messages', {'chat_id': chat_id, 'messages': payload})


@socketio.on('leave_chat')
def handle_leave_chat(data):
    try:
        chat_id = int(data.get('chat_id', 0))
        group_id = int(data.get('group_id', 0))
    except Exception:
        return

    room = f"group_{group_id}_chat_{chat_id}"
    leave_room(room)


@socketio.on('create_chat')
def handle_create_chat(data):
    try:
        group_id = int(data.get('group_id', 0))
        name = str(data.get('name', '') or '').strip()[:140]
    except Exception:
        return

    user_id = session.get('user_id')
    if not user_id:
        emit('error', {'message': 'not-authenticated'})
        return

    # only members can create chats
    membership = get_group_membership(group_id=group_id, user_id=int(user_id))
    if membership is None or membership['status'] != 'member':
        emit('error', {'message': 'not-member'})
        return

    new_chat_id = create_group_chat(group_id=group_id, nazov=name or 'Chat')
    # broadcast updated chat list to group members connected to a general room
    emit('chat_created', {'chat': {'id': new_chat_id, 'group_id': group_id, 'nazov': name}}, broadcast=True)


@socketio.on('send_message')
def handle_send_message(data):
    try:
        chat_id = int(data.get('chat_id', 0))
        group_id = int(data.get('group_id', 0))
        content = str(data.get('content', '') or '').strip()
    except Exception:
        return

    if not content:
        return

    user_id = session.get('user_id')
    if not user_id:
        emit('error', {'message': 'not-authenticated'})
        return

    membership = get_group_membership(group_id=group_id, user_id=int(user_id))
    if membership is None or membership['status'] != 'member':
        emit('error', {'message': 'not-member'})
        return

    # persist message
    message_id = create_group_chat_message(chat_id=chat_id, sender_user_id=int(user_id), content=content)

    user = get_user_by_id(int(user_id))
    author = f"{user['meno']} {user['priezvisko']}" if user else 'Užívatel'
    profile_photo = ''
    try:
        profile = user and user.get('profilova_fotka')
        if profile:
            profile_photo = url_for('static', filename=profile)
    except Exception:
        profile_photo = ''

    created_at_iso = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    payload = {
        'id': message_id,
        'chat_id': chat_id,
        'sender_user_id': int(user_id),
        'author': author,
        'author_profile_url': url_for('aplikacia_profil_verejny', user_id=int(user_id)),
        'profile_photo': profile_photo,
        'content': content,
        'created_at': _format_datetime_eu(created_at_iso),
    }

    room = f"group_{group_id}_chat_{chat_id}"
    emit('new_message', payload, room=room)
