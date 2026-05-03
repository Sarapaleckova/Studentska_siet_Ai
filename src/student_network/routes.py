"""Route definitions for Študentská sieť."""

from calendar import monthrange
from datetime import date, datetime
from collections import defaultdict
from functools import wraps
import mimetypes
from pathlib import Path
import re
import sqlite3
import unicodedata
from uuid import uuid4

from flask import Flask, abort, flash, g, jsonify, redirect, render_template, request, send_from_directory, session, url_for
from werkzeug.utils import secure_filename

from student_network.db import get_db
from student_network.thumbnail_service import generate_thumbnail_from_file, get_file_icon_svg

from student_network.file_types import (
    ALLOWED_POST_FILE_EXTENSIONS,
    ALLOWED_POST_IMAGE_EXTENSIONS,
    POST_FILE_ACCEPT_VALUE,
    post_file_types_description,
)
from student_network.repositories.comments import create_post_comment, get_post_comment_by_id, get_post_comments, update_post_comment
from student_network.repositories.group_events import (
    create_group_event,
    create_group_event_notification,
    delete_group_event,
    get_group_event_by_id,
    get_group_events_for_month,
    get_group_notifications,
    update_group_event,
)
from student_network.repositories.group_board_posts import create_group_board_post, get_group_board_posts, update_group_board_post
from student_network.repositories.group_chats import get_group_chats, create_group_chat, create_group_chat_message, get_chat_by_id, get_chat_messages
from student_network.repositories.private_messages import (
    create_private_message,
    get_messages_for_user,
    get_unread_count,
    mark_message_read,
)
from student_network.repositories.group_files import (
    create_group_file,
    create_group_file_folder,
    get_group_file_by_id,
    get_group_file_folder_by_id,
    get_group_file_folders,
    get_group_files,
    update_group_file_folder,
)
from student_network.repositories.home_events import (
    create_home_event,
    get_home_event_by_id,
    get_home_events_with_visibility_for_user,
    set_home_event_hidden_for_user,
)
from student_network.repositories.groups import (
    approve_group_request,
    bulk_update_member_roles,
    count_group_admins,
    create_group,
    get_group_by_id,
    get_group_membership,
    get_group_members,
    get_pending_group_requests,
    get_groups_for_user,
    get_member_groups_for_user,
    is_group_admin,
    join_public_group,
    reject_group_request,
    remove_group_member,
    request_private_group_membership,
    update_group,
    update_member_role,
)
from student_network.repositories.profiles import (
    get_profile_by_user_id,
    get_user_additional_emails,
    replace_user_additional_emails,
    save_profile,
)
from student_network.repositories.posts import create_post, delete_post, get_all_posts, get_post_by_id, get_posts_by_author_id, search_posts, update_post
from student_network.repositories.ratings import get_user_post_rating, upsert_post_rating
from student_network.repositories.tasks import (
    create_task,
    delete_task,
    get_task_by_id,
    get_tasks_for_user,
    toggle_task_completion,
    update_task,
)
from student_network.repositories.cards import (
    create_attempt,
    create_card,
    create_deck,
    delete_card,
    delete_deck,
    get_card_by_id,
    get_cards_for_deck,
    get_deck_attempts,
    get_deck_by_id,
    get_decks_for_user,
    update_card,
    update_deck,
)
from student_network.repositories.users import get_user_by_id, search_users_by_name, update_user_name
from student_network.services.auth_service import register_user, validate_login
from student_network.services.profile_service import profile_form_values, profile_values_from_row, validate_profile

ALLOWED_PROFILE_PHOTO_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp', '.gif'}
ALLOWED_THEME_BG_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp', '.gif'}
ALLOWED_GROUP_PHOTO_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp', '.gif'}
APP_BASE_PATH = '/studentska-siet'
GROUP_TABS = {'hlavna', 'zdielat', 'notifikacie', 'kalendar', 'clenovia', 'subory', 'spravy'}
ALLOWED_GROUP_SHARED_FILE_EXTENSIONS = ALLOWED_POST_FILE_EXTENSIONS | ALLOWED_POST_IMAGE_EXTENSIONS
GROUP_FILE_ACCEPT_VALUE = ','.join(sorted(ALLOWED_GROUP_SHARED_FILE_EXTENSIONS))
THEME_PRESETS: dict[str, dict[str, str]] = {
    'default': {'bg': '#0b1f4d', 'nav': '#071433'},
    'pink': {'bg': '#b84f8a', 'nav': '#7a1f4e'},
    'ocean': {'bg': '#1a4f8b', 'nav': '#0f2f54'},
}
HOME_EVENT_CATEGORY_LABELS: dict[str, str] = {
    'spolocenska': 'Spoločenská udalosť',
    'podujatie': 'Podujatie / event',
    'sutaz': 'Súťaž',
    'party': 'Party',
    'ine': 'Iné',
}
HEX_COLOR_PATTERN = re.compile(r'^#[0-9a-fA-F]{6}$')


def _post_file_type_from_name(file_name: str) -> str:
    extension = Path(file_name).suffix.lower()
    return extension if extension else 'bez prípony'


def _save_uploaded_file(uploaded_file, target_dir: Path, user_id: int) -> tuple[str, str]:
    original_name = secure_filename(uploaded_file.filename)
    extension = Path(original_name).suffix.lower()
    unique_name = f"user_{user_id}_{uuid4().hex}{extension}"
    target_path = target_dir / unique_name
    uploaded_file.save(target_path)
    return unique_name, original_name


def _delete_uploaded_static_file(static_folder: str | None, relative_path: str) -> None:
    if not static_folder or not relative_path:
        return

    file_path = Path(static_folder) / relative_path
    if file_path.exists() and file_path.is_file():
        file_path.unlink()


def _slugify(text: str) -> str:
    normalized = unicodedata.normalize('NFKD', text)
    ascii_text = normalized.encode('ascii', 'ignore').decode('ascii')
    slug = re.sub(r'[^a-z0-9]+', '-', ascii_text.lower()).strip('-')
    return slug or 'prispevok'


def _format_rating(average_rating: float, rating_count: int) -> str:
    if rating_count == 0:
        return 'Bez hodnotenia'
    return f"{average_rating:.1f}/5 ({rating_count})"


def _build_rating_stars(average_rating: float) -> list[str]:
    stars: list[str] = []
    for star in range(1, 6):
        if average_rating >= star:
            stars.append('filled')
        elif average_rating >= star - 0.5:
            stars.append('half')
        else:
            stars.append('empty')
    return stars


def _build_comment_tree(comment_rows) -> list[dict]:
    comments_by_id: dict[int, dict] = {}
    root_comments: list[dict] = []

    for row in comment_rows:
        comment = {
            'id': row['id'],
            'post_id': row['post_id'],
            'user_id': row['user_id'],
            'parent_comment_id': row['parent_comment_id'],
            'text': row['text'],
            'created_at': _format_datetime_eu(row['created_at']),
            'author': f"{row['author_meno']} {row['author_priezvisko']}",
            'children': [],
        }
        comments_by_id[comment['id']] = comment

    for comment in comments_by_id.values():
        parent_id = comment['parent_comment_id']
        if parent_id and parent_id in comments_by_id:
            comments_by_id[parent_id]['children'].append(comment)
        else:
            root_comments.append(comment)

    return root_comments


def _format_date_eu(date_value: str) -> str:
    try:
        parsed = datetime.strptime(date_value, '%Y-%m-%d')
    except (TypeError, ValueError):
        return date_value
    return parsed.strftime('%d/%m/%Y')


def _format_time_24(time_value: str) -> str:
    for time_pattern in ('%H:%M', '%H:%M:%S'):
        try:
            parsed = datetime.strptime(time_value, time_pattern)
            return parsed.strftime('%H:%M')
        except (TypeError, ValueError):
            continue
    return time_value


def _format_datetime_eu(datetime_value: str) -> str:
    for date_pattern in ('%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S'):
        try:
            parsed = datetime.strptime(datetime_value, date_pattern)
            return parsed.strftime('%d/%m/%Y %H:%M')
        except (TypeError, ValueError):
            continue
    return datetime_value


def _parse_event_date_input(date_value: str) -> date | None:
    for date_pattern in ('%d/%m/%Y', '%Y-%m-%d'):
        try:
            return datetime.strptime(date_value, date_pattern).date()
        except (TypeError, ValueError):
            continue
    return None


def _group_image_src(image_value: str) -> str:
    if not image_value:
        return ''
    if image_value.startswith('http://') or image_value.startswith('https://'):
        return image_value
    return url_for('static', filename=image_value)


def _normalize_theme_values(theme_preset: str, bg_color: str, nav_color: str) -> tuple[str, str, str]:
    preset_key = theme_preset if theme_preset in {'default', 'pink', 'ocean', 'custom'} else 'default'

    if preset_key != 'custom':
        preset = THEME_PRESETS.get(preset_key, THEME_PRESETS['default'])
        return preset_key, preset['bg'], preset['nav']

    normalized_bg = bg_color if HEX_COLOR_PATTERN.fullmatch(bg_color or '') else THEME_PRESETS['default']['bg']
    normalized_nav = nav_color if HEX_COLOR_PATTERN.fullmatch(nav_color or '') else THEME_PRESETS['default']['nav']
    return preset_key, normalized_bg, normalized_nav


def _build_theme_context(profile_row) -> dict[str, str]:
    theme_preset, bg_color, nav_color = _normalize_theme_values(
        str(profile_row['theme_preset'] or 'default') if profile_row is not None else 'default',
        str(profile_row['theme_bg_color'] or THEME_PRESETS['default']['bg']) if profile_row is not None else THEME_PRESETS['default']['bg'],
        str(profile_row['theme_nav_color'] or THEME_PRESETS['default']['nav']) if profile_row is not None else THEME_PRESETS['default']['nav'],
    )
    bg_image = str(profile_row['theme_bg_image'] or '') if profile_row is not None else ''

    return {
        'preset': theme_preset,
        'bg_color': bg_color,
        'nav_color': nav_color,
        'bg_image_css': f"url('{url_for('static', filename=bg_image)}')" if bg_image else 'none',
    }


def _profile_url_for_user(user_id: int) -> str:
    if g.get('user') is not None and int(g.user['id']) == int(user_id):
        return url_for('aplikacia_profil')
    return url_for('aplikacia_profil_verejny', user_id=user_id)


def _parse_group_month(raw_value: str) -> tuple[int, int]:
    today = date.today()
    if not raw_value or not re.fullmatch(r'\d{4}-\d{2}', raw_value):
        return today.year, today.month

    year_value = int(raw_value[:4])
    month_value = int(raw_value[5:7])
    if year_value < 1970 or year_value > 2100 or month_value < 1 or month_value > 12:
        return today.year, today.month

    return year_value, month_value


def _month_key(year_value: int, month_value: int) -> str:
    return f"{year_value:04d}-{month_value:02d}"


def _shift_month(year_value: int, month_value: int, delta: int) -> tuple[int, int]:
    absolute_month = year_value * 12 + (month_value - 1) + delta
    return absolute_month // 12, (absolute_month % 12) + 1


def _build_group_calendar_grid(
    year_value: int,
    month_value: int,
    event_dates: set[str],
) -> list[list[dict]]:
    first_weekday, days_in_month = monthrange(year_value, month_value)
    prev_year, prev_month = _shift_month(year_value, month_value, -1)
    next_year, next_month = _shift_month(year_value, month_value, 1)
    prev_days = monthrange(prev_year, prev_month)[1]
    today_iso = date.today().isoformat()

    cells: list[dict] = []

    for day_value in range(prev_days - first_weekday + 1, prev_days + 1):
        date_iso = f"{prev_year:04d}-{prev_month:02d}-{day_value:02d}"
        cells.append(
            {
                'day': day_value,
                'date_iso': date_iso,
                'in_current_month': False,
                'is_today': date_iso == today_iso,
                'has_events': date_iso in event_dates,
            }
        )

    for day_value in range(1, days_in_month + 1):
        date_iso = f"{year_value:04d}-{month_value:02d}-{day_value:02d}"
        cells.append(
            {
                'day': day_value,
                'date_iso': date_iso,
                'in_current_month': True,
                'is_today': date_iso == today_iso,
                'has_events': date_iso in event_dates,
            }
        )

    trailing_day = 1
    while len(cells) % 7 != 0:
        date_iso = f"{next_year:04d}-{next_month:02d}-{trailing_day:02d}"
        cells.append(
            {
                'day': trailing_day,
                'date_iso': date_iso,
                'in_current_month': False,
                'is_today': date_iso == today_iso,
                'has_events': date_iso in event_dates,
            }
        )
        trailing_day += 1

    return [cells[index:index + 7] for index in range(0, len(cells), 7)]


def register_routes(app: Flask) -> None:
    @app.before_request
    def load_logged_in_user() -> None:
        user_id = session.get('user_id')
        g.user = get_user_by_id(user_id) if user_id else None
        profile_row = get_profile_by_user_id(int(g.user['id'])) if g.user else None
        g.app_theme = _build_theme_context(profile_row)
        profile_photo_path = str(profile_row['profilova_fotka'] or '') if profile_row is not None else ''
        g.top_nav_profile_photo_url = url_for('static', filename=profile_photo_path) if profile_photo_path else ''
        first_name = str(g.user['meno'] or '').strip() if g.user else ''
        g.top_nav_profile_initial = first_name[:1].upper() if first_name else 'U'

    @app.context_processor
    def inject_app_theme() -> dict[str, dict[str, str] | str]:
        return {
            'app_theme': g.app_theme if hasattr(g, 'app_theme') else _build_theme_context(None),
            'top_nav_profile_photo_url': g.top_nav_profile_photo_url if hasattr(g, 'top_nav_profile_photo_url') else '',
            'top_nav_profile_initial': g.top_nav_profile_initial if hasattr(g, 'top_nav_profile_initial') else 'U',
        }

    def login_required(view):
        @wraps(view)
        def wrapped_view(*args, **kwargs):
            if g.user is None:
                return redirect(url_for('prihlasenie'))

            return view(*args, **kwargs)

        return wrapped_view

    @app.route('/')
    def root_redirect() -> str:
        return redirect(url_for('index'))

    @app.route(APP_BASE_PATH)
    def index() -> str:
        return render_template('index.html')

    @app.route(f'{APP_BASE_PATH}/prihlasenie', methods=['GET', 'POST'])
    def prihlasenie() -> str:
        errors: dict[str, str] = {}
        values = {'email': ''}

        if request.method == 'POST':
            errors, values, user_id = validate_login(request.form)

            if not errors and user_id is not None:
                session.clear()
                session['user_id'] = user_id
                return redirect(url_for('aplikacia_domov'))

        return render_template('prihlasenie.html', errors=errors, values=values)

    @app.route(f'{APP_BASE_PATH}/registracia', methods=['GET', 'POST'])
    def registracia() -> str:
        errors: dict[str, str] = {}
        values = {
            'meno': '',
            'priezvisko': '',
            'email': '',
        }

        if request.method == 'POST':
            errors, values = register_user(request.form)

            if not errors:
                flash('Registrácia prebehla úspešne. Teraz sa môžete prihlásiť.', 'success')
                return redirect(url_for('prihlasenie'))

        return render_template('registracia.html', errors=errors, values=values)

    @app.route(f'{APP_BASE_PATH}/odhlasenie')
    def odhlasenie() -> str:
        session.clear()
        return redirect(url_for('index'))

    @app.route(f'{APP_BASE_PATH}/domov')
    @login_required
    def aplikacia_domov() -> str:
        post_rows = get_all_posts()
        posts = [
            {
                'id': row['id'],
                'nazov': row['nazov'],
                'post_slug': _slugify(row['nazov']),
                'author_id': int(row['author_id']),
                'autor': f"{row['author_meno']} {row['author_priezvisko']}",
                'author_profile_url': _profile_url_for_user(int(row['author_id'])),
                'author_is_current_user': int(row['author_id']) == int(g.user['id']),
                'subor_povodny_nazov': row['subor_povodny_nazov'],
                'typ_suboru': _post_file_type_from_name(row['subor_povodny_nazov']) if row['subor_povodny_nazov'] else 'bez súboru',
                'average_rating': float(row['average_rating'] or 0),
                'rating_count': int(row['rating_count'] or 0),
                'rating_text': _format_rating(float(row['average_rating'] or 0), int(row['rating_count'] or 0)),
                'nahladovy_obrazok_url': (
                    row['nahladovy_obrazok'] if (row['nahladovy_obrazok'] or '').startswith('data:') else url_for('static', filename=row['nahladovy_obrazok'])
                ) if row['nahladovy_obrazok'] else None,
            }
            for row in post_rows
        ]

        event_rows = get_home_events_with_visibility_for_user(user_id=int(g.user['id']))
        now_value = datetime.now()
        upcoming_events: list[dict] = []
        past_events: list[dict] = []
        hidden_events: list[dict] = []

        for row in event_rows:
            try:
                event_dt = datetime.strptime(str(row['event_at']), '%Y-%m-%d %H:%M:%S')
            except ValueError:
                continue

            event_view = {
                'id': int(row['id']),
                'nazov': row['nazov'],
                'event_at': row['event_at'],
                'event_at_display': event_dt.strftime('%d/%m/%Y %H:%M'),
                'kategoria': row['kategoria'],
                'kategoria_label': HOME_EVENT_CATEGORY_LABELS.get(str(row['kategoria']), 'Iné'),
                'category_class': f"event-category-{row['kategoria']}",
                'author': f"{row['author_meno']} {row['author_priezvisko']}",
                'author_profile_url': _profile_url_for_user(int(row['created_by_user_id'])),
                'author_is_current_user': int(row['created_by_user_id']) == int(g.user['id']),
                'event_at_input': event_dt.strftime('%Y-%m-%dT%H:%M'),
                'is_hidden': bool(row['is_hidden']),
            }

            if event_view['is_hidden']:
                hidden_events.append(event_view)
            elif event_dt >= now_value:
                upcoming_events.append(event_view)
            else:
                past_events.append(event_view)

        past_events.sort(key=lambda item: item['event_at'], reverse=True)

        return render_template(
            'domov.html',
            active_tab='domov',
            posts=posts,
            upcoming_events=upcoming_events,
            past_events=past_events,
            hidden_events=hidden_events,
            home_event_categories=[
                {'value': key, 'label': label, 'class_name': f'event-category-{key}'}
                for key, label in HOME_EVENT_CATEGORY_LABELS.items()
            ],
        )

    @app.route(f'{APP_BASE_PATH}/domov/udalosti', methods=['POST'])
    @login_required
    def aplikacia_domov_udalosti() -> str:
        action_type = request.form.get('event_action', '').strip().lower()

        if action_type == 'create':
            nazov = request.form.get('event_name', '').strip()
            event_datetime_raw = request.form.get('event_datetime', '').strip()
            category = request.form.get('event_category', '').strip().lower()

            if not nazov:
                flash('Názov udalosti je povinný.', 'error')
                return redirect(url_for('aplikacia_domov'))

            if len(nazov) > 160:
                flash('Názov udalosti môže mať najviac 160 znakov.', 'error')
                return redirect(url_for('aplikacia_domov'))

            if not event_datetime_raw:
                flash('Dátum a čas udalosti je povinný.', 'error')
                return redirect(url_for('aplikacia_domov'))

            if category not in HOME_EVENT_CATEGORY_LABELS:
                category = 'ine'

            try:
                parsed_dt = datetime.strptime(event_datetime_raw, '%Y-%m-%dT%H:%M')
            except ValueError:
                flash('Neplatný formát dátumu a času udalosti.', 'error')
                return redirect(url_for('aplikacia_domov'))

            create_home_event(
                created_by_user_id=int(g.user['id']),
                nazov=nazov,
                event_at=parsed_dt.strftime('%Y-%m-%d %H:%M:%S'),
                kategoria=category,
            )
            flash('Udalosť bola pridaná na nástenku.', 'success')
            return redirect(url_for('aplikacia_domov'))

        if action_type in {'hide', 'unhide'}:
            event_id_raw = request.form.get('event_id', '').strip()
            try:
                event_id = int(event_id_raw)
            except ValueError:
                flash('Neplatná udalosť.', 'error')
                return redirect(url_for('aplikacia_domov'))

            event_row = get_home_event_by_id(event_id=event_id)
            if event_row is None:
                flash('Udalosť sa nenašla.', 'error')
                return redirect(url_for('aplikacia_domov'))

            set_home_event_hidden_for_user(
                user_id=int(g.user['id']),
                event_id=event_id,
                is_hidden=(action_type == 'hide'),
            )
            if action_type == 'hide':
                flash('Udalosť bola skrytá.', 'success')
            else:
                flash('Udalosť sa opäť zobrazuje.', 'success')
            return redirect(url_for('aplikacia_domov'))

        if action_type == 'edit':
            event_id_raw = request.form.get('event_id', '').strip()
            nazov = request.form.get('event_name', '').strip()
            event_datetime_raw = request.form.get('event_datetime', '').strip()
            category = request.form.get('event_category', '').strip().lower()

            try:
                event_id = int(event_id_raw)
            except ValueError:
                flash('Neplatná udalosť.', 'error')
                return redirect(url_for('aplikacia_domov'))

            event_row = get_home_event_by_id(event_id=event_id)
            if event_row is None:
                flash('Udalosť sa nenašla.', 'error')
                return redirect(url_for('aplikacia_domov'))

            if int(event_row['created_by_user_id']) != int(g.user['id']):
                abort(403)

            if not nazov:
                flash('Názov udalosti je povinný.', 'error')
                return redirect(url_for('aplikacia_domov'))

            if len(nazov) > 160:
                flash('Názov udalosti môže mať najviac 160 znakov.', 'error')
                return redirect(url_for('aplikacia_domov'))

            if not event_datetime_raw:
                flash('Dátum a čas udalosti je povinný.', 'error')
                return redirect(url_for('aplikacia_domov'))

            if category not in HOME_EVENT_CATEGORY_LABELS:
                category = 'ine'

            try:
                parsed_dt = datetime.strptime(event_datetime_raw, '%Y-%m-%dT%H:%M')
            except ValueError:
                flash('Neplatný formát dátumu a času udalosti.', 'error')
                return redirect(url_for('aplikacia_domov'))

            database = get_db()
            database.execute(
                """
                UPDATE home_events
                SET nazov = ?, event_at = ?, kategoria = ?
                WHERE id = ?
                """,
                (nazov, parsed_dt.strftime('%Y-%m-%d %H:%M:%S'), category, event_id),
            )
            database.commit()
            flash('Udalosť bola upravená.', 'success')
            return redirect(url_for('aplikacia_domov'))

        flash('Neplatná akcia udalosti.', 'error')
        return redirect(url_for('aplikacia_domov'))

    @app.route(f'{APP_BASE_PATH}/skupiny')
    @login_required
    def aplikacia_skupiny() -> str:
        search_query = request.args.get('q', '').strip()
        group_rows = get_groups_for_user(int(g.user['id']), search_query)

        member_groups = [
            {
                'id': row['id'],
                'nazov': row['nazov'],
                'popis': row['popis'],
                'obrazok_url': _group_image_src(row['obrazok_url']),
                'je_sukromna': bool(row['je_sukromna']),
                'member_count': int(row['member_count'] or 0),
                'membership_role': row['membership_role'] or 'member',
            }
            for row in group_rows
            if row['membership_status'] == 'member'
        ]

        non_member_groups = [
            {
                'id': row['id'],
                'nazov': row['nazov'],
                'popis': row['popis'],
                'obrazok_url': _group_image_src(row['obrazok_url']),
                'je_sukromna': bool(row['je_sukromna']),
                'member_count': int(row['member_count'] or 0),
                'membership_status': row['membership_status'] or '',
            }
            for row in group_rows
            if row['membership_status'] != 'member'
        ]

        return render_template(
            'skupiny.html',
            active_tab='skupiny',
            search_query=search_query,
            member_groups=member_groups,
            non_member_groups=non_member_groups,
        )

    # --- Private messages API -------------------------------------------------
    @app.route(f'{APP_BASE_PATH}/messages/unread_count')
    @login_required
    def messages_unread_count():
        count = get_unread_count(int(g.user['id']))
        return {'count': count}

    @app.route(f'{APP_BASE_PATH}/messages', methods=['GET', 'POST'])
    @login_required
    def messages_endpoint():
        if request.method == 'GET':
            rows = get_messages_for_user(int(g.user['id']))
            sent = []
            received = []
            unread = []
            for row in rows:
                item = {
                    'id': row['id'],
                    'sender_id': row['sender_id'],
                    'recipient_id': row['recipient_id'],
                    'content': row['content'],
                    'is_read': bool(row['is_read']),
                    'created_at': _format_datetime_eu(row['created_at']),
                    'sender_name': f"{row['sender_meno']} {row['sender_priezvisko']}",
                    'recipient_name': f"{row['recipient_meno']} {row['recipient_priezvisko']}",
                }
                if int(row['sender_id']) == int(g.user['id']):
                    sent.append(item)
                if int(row['recipient_id']) == int(g.user['id']):
                    received.append(item)
                    if not row['is_read']:
                        unread.append(item)

            return {'sent': sent, 'received': received, 'unread': unread}

        # POST -> create new message
        try:
            recipient_id = int(request.form.get('recipient_id', '0'))
        except ValueError:
            return {'error': 'Neplatný príjemca'}, 400

        content = (request.form.get('content') or '').strip()
        if not content:
            return {'error': 'Obsah správy je prázdny.'}, 400

        message_id = create_private_message(sender_id=int(g.user['id']), recipient_id=recipient_id, content=content)
        return {'ok': True, 'id': message_id}

    @app.route(f'{APP_BASE_PATH}/messages/<int:message_id>/read', methods=['POST'])
    @login_required
    def messages_mark_read(message_id: int):
        mark_message_read(message_id=message_id, recipient_id=int(g.user['id']))
        return {'ok': True}

    @app.route(f'{APP_BASE_PATH}/users/search')
    @login_required
    def users_search():
        q = request.args.get('q', '').strip()
        rows = search_users_by_name(q) if q else []
        result = [
            {'id': r['id'], 'name': f"{r['meno']} {r['priezvisko']}", 'photo': (url_for('static', filename=r['profilova_fotka']) if r['profilova_fotka'] else '')}
            for r in rows
        ]
        return {'results': result}

    @app.route(f'{APP_BASE_PATH}/skupiny/vytvorit', methods=['GET', 'POST'])
    @login_required
    def aplikacia_skupiny_vytvorit() -> str:
        errors: dict[str, str] = {}
        values = {
            'nazov': '',
            'popis': '',
            'pristupnost': 'public',
        }

        if request.method == 'POST':
            values['nazov'] = request.form.get('nazov', '').strip()
            values['popis'] = request.form.get('popis', '').strip()
            values['pristupnost'] = request.form.get('pristupnost', 'public').strip()

            if not values['nazov']:
                errors['nazov'] = 'Názov skupiny je povinný.'
            elif len(values['nazov']) > 120:
                errors['nazov'] = 'Názov môže mať najviac 120 znakov.'

            if len(values['popis']) > 2000:
                errors['popis'] = 'Popis môže mať najviac 2000 znakov.'

            if values['pristupnost'] not in {'public', 'private'}:
                errors['pristupnost'] = 'Neplatná prístupnosť skupiny.'

            image_relative_path = ''
            uploaded_photo = request.files.get('profilova_fotka')
            if uploaded_photo and uploaded_photo.filename:
                image_filename = secure_filename(uploaded_photo.filename)
                image_extension = Path(image_filename).suffix.lower()

                if image_extension not in ALLOWED_GROUP_PHOTO_EXTENSIONS:
                    errors['profilova_fotka'] = 'Povolené formáty: PNG, JPG, JPEG, WEBP, GIF.'
                else:
                    stored_image_name, _ = _save_uploaded_file(
                        uploaded_photo,
                        Path(app.config['GROUP_PHOTO_UPLOAD_DIR']),
                        int(g.user['id']),
                    )
                    image_relative_path = f"uploads/group_photos/{stored_image_name}"

            existing_group = None
            if values['nazov']:
                existing_group = next((row for row in get_groups_for_user(int(g.user['id']), values['nazov']) if row['nazov'].lower() == values['nazov'].lower()), None)
            if existing_group is not None:
                errors['nazov'] = 'Skupina s týmto názvom už existuje.'

            if not errors:
                try:
                    new_group_id = create_group(
                        creator_user_id=int(g.user['id']),
                        nazov=values['nazov'],
                        popis=values['popis'],
                        obrazok_url=image_relative_path,
                        je_sukromna=values['pristupnost'] == 'private',
                    )
                except sqlite3.IntegrityError:
                    errors['nazov'] = 'Skupina s týmto názvom už existuje.'
                else:
                    flash('Skupina bola úspešne vytvorená.', 'success')
                    return redirect(url_for('aplikacia_skupina_detail', group_id=new_group_id))

        return render_template(
            'skupina_form.html',
            active_tab='skupiny',
            form_title='Vytvoriť skupinu',
            submit_label='Vytvoriť skupinu',
            values=values,
            errors=errors,
            is_edit=False,
            group_photo_url=None,
        )

    @app.route(f'{APP_BASE_PATH}/skupiny/akcia', methods=['POST'])
    @login_required
    def aplikacia_skupiny_akcia() -> str:
        search_query = request.form.get('q', '').strip()
        redirect_target = url_for('aplikacia_skupiny', q=search_query) if search_query else url_for('aplikacia_skupiny')

        try:
            group_id = int(request.form.get('group_id', '0'))
        except ValueError:
            flash('Neplatná skupina.', 'error')
            return redirect(redirect_target)

        action = request.form.get('action', '')
        group = get_group_by_id(group_id)
        if group is None:
            flash('Skupina sa nenašla.', 'error')
            return redirect(redirect_target)

        if action == 'join':
            if bool(group['je_sukromna']):
                flash('Do súkromnej skupiny sa nedá pridať priamo.', 'error')
                return redirect(redirect_target)

            result = join_public_group(group_id=group_id, user_id=int(g.user['id']))
            if result == 'already-member':
                flash('Už ste členom tejto skupiny.', 'success')
            else:
                flash('Boli ste pridaný do skupiny.', 'success')
            return redirect(redirect_target)

        if action == 'request':
            if not bool(group['je_sukromna']):
                flash('Verejná skupina nevyžaduje žiadosť.', 'error')
                return redirect(redirect_target)

            result = request_private_group_membership(group_id=group_id, user_id=int(g.user['id']))
            if result == 'already-member':
                flash('Už ste členom tejto skupiny.', 'success')
            elif result == 'already-requested':
                flash('Žiadosť už bola odoslaná.', 'success')
            else:
                flash('Žiadosť o prijatie bola odoslaná.', 'success')
            return redirect(redirect_target)

        flash('Neplatná akcia skupiny.', 'error')
        return redirect(redirect_target)

    @app.route(f'{APP_BASE_PATH}/skupiny/<int:group_id>')
    @login_required
    def aplikacia_skupina_detail(group_id: int) -> str:
        group = get_group_by_id(group_id)
        if group is None:
            flash('Skupina sa nenašla.', 'error')
            return redirect(url_for('aplikacia_skupiny'))

        membership = get_group_membership(group_id=group_id, user_id=int(g.user['id']))
        if membership is None or membership['status'] != 'member':
            flash('Detail je dostupný len pre členov skupiny.', 'error')
            return redirect(url_for('aplikacia_skupiny'))

        group_view = {
            'id': group['id'],
            'nazov': group['nazov'],
            'popis': group['popis'],
            'obrazok_url': _group_image_src(group['obrazok_url']),
            'je_sukromna': bool(group['je_sukromna']),
            'member_count': int(group['member_count'] or 0),
            'created_at': _format_datetime_eu(group['created_at']) if group['created_at'] else '',
        }

        user_is_admin = is_group_admin(group_id=group_id, user_id=int(g.user['id']))
        member_rows = get_group_members(group_id)
        members = [
            {
                'user_id': row['user_id'],
                'meno': row['meno'],
                'priezvisko': row['priezvisko'],
                'full_name': f"{row['meno']} {row['priezvisko']}",
                'role': row['role'],
                'joined_at': _format_datetime_eu(row['joined_at']) if row['joined_at'] else '',
                'photo_url': url_for('static', filename=row['profilova_fotka']) if row['profilova_fotka'] else None,
                'is_current_user': int(row['user_id']) == int(g.user['id']),
                'profile_url': _profile_url_for_user(int(row['user_id'])),
            }
            for row in member_rows
        ]

        pending_rows = get_pending_group_requests(group_id) if user_is_admin else []
        pending_requests = [
            {
                'user_id': row['user_id'],
                'full_name': f"{row['meno']} {row['priezvisko']}",
                'requested_at': _format_datetime_eu(row['requested_at']),
                'photo_url': url_for('static', filename=row['profilova_fotka']) if row['profilova_fotka'] else None,
                'profile_url': _profile_url_for_user(int(row['user_id'])),
            }
            for row in pending_rows
        ]

        month_value = request.args.get('month', '').strip()
        year_value, month_number = _parse_group_month(month_value)
        current_month_key = _month_key(year_value, month_number)
        prev_month_key = _month_key(*_shift_month(year_value, month_number, -1))
        next_month_key = _month_key(*_shift_month(year_value, month_number, 1))

        active_detail_tab = request.args.get('tab', 'hlavna').strip().lower()
        if active_detail_tab not in GROUP_TABS:
            active_detail_tab = 'hlavna'

        group_announcement_rows = get_group_board_posts(group_id=group_id, board_type='announcement')
        group_member_post_rows = get_group_board_posts(group_id=group_id, board_type='member')
        group_announcements = [
            {
                'id': row['id'],
                'title': row['title'],
                'content': row['content'],
                'created_at': _format_datetime_eu(row['created_at']),
                'author': f"{row['author_meno']} {row['author_priezvisko']}",
                'author_profile_url': _profile_url_for_user(int(row['author_user_id'])),
                'author_is_current_user': int(row['author_user_id']) == int(g.user['id']),
            }
            for row in group_announcement_rows
        ]
        group_member_posts = [
            {
                'id': row['id'],
                'title': row['title'],
                'content': row['content'],
                'created_at': _format_datetime_eu(row['created_at']),
                'author': f"{row['author_meno']} {row['author_priezvisko']}",
                'author_profile_url': _profile_url_for_user(int(row['author_user_id'])),
                'author_is_current_user': int(row['author_user_id']) == int(g.user['id']),
            }
            for row in group_member_post_rows
        ]

        month_event_rows = get_group_events_for_month(group_id=group_id, year=year_value, month=month_number)
        month_events = [
            {
                'id': row['id'],
                'event_date': row['event_date'],
                'event_time': row['event_time'],
                'event_date_display': _format_date_eu(row['event_date']),
                'event_time_display': _format_time_24(row['event_time']),
                'nazov': row['nazov'],
                'popis': row['popis'],
                'author': f"{row['actor_meno']} {row['actor_priezvisko']}",
            }
            for row in month_event_rows
        ]

        events_by_date: dict[str, list[dict[str, str]]] = defaultdict(list)
        for event in month_events:
            events_by_date[event['event_date']].append(
                {
                    'time': event['event_time_display'] or '',
                    'title': event['nazov'] or '',
                    'description': event['popis'] or '',
                }
            )

        event_dates = {event['event_date'] for event in month_events}

        calendar_weeks = _build_group_calendar_grid(
            year_value=year_value,
            month_value=month_number,
            event_dates=event_dates,
        )

        for week in calendar_weeks:
            for day in week:
                day['events'] = events_by_date.get(day['date_iso'], [])

        notification_rows = get_group_notifications(group_id)
        notifications = [
            {
                'id': row['id'],
                'action_type': row['action_type'],
                'message': row['message'],
                'created_at': _format_datetime_eu(row['created_at']),
                'actor': f"{row['actor_meno']} {row['actor_priezvisko']}",
                'event_date': row['event_date'] or row['notification_event_date'],
                'event_time': row['event_time'] or row['notification_event_time'],
                'event_date_display': _format_date_eu(row['event_date'] or row['notification_event_date']),
                'event_time_display': _format_time_24(row['event_time'] or row['notification_event_time']),
                'event_nazov': row['event_nazov'],
            }
            for row in notification_rows
        ]

        folder_filter = request.args.get('folder', 'all').strip().lower()
        if not folder_filter:
            folder_filter = 'all'

        group_folder_rows = get_group_file_folders(group_id=group_id)
        group_file_folders = [
            {
                'id': int(row['id']),
                'nazov': row['nazov'],
                'created_at': _format_datetime_eu(row['created_at']),
                'author': f"{row['author_meno']} {row['author_priezvisko']}",
            }
            for row in group_folder_rows
        ]
        folder_ids = {str(folder['id']) for folder in group_file_folders}

        selected_folder_id: int | None = None
        if folder_filter in {'nezaradene', 'unassigned'}:
            folder_filter = 'all'
        elif folder_filter.isdigit() and folder_filter in folder_ids:
            selected_folder_id = int(folder_filter)
        else:
            folder_filter = 'all'

        def _file_row_to_view(row):
            return {
                'id': row['id'],
                'original_nazov': row['original_nazov'],
                'typ_suboru': row['typ_suboru'] or _post_file_type_from_name(row['original_nazov']),
                'author': f"{row['author_meno']} {row['author_priezvisko']}",
                'uploaded_at': _format_datetime_eu(row['uploaded_at']),
                'folder_id': int(row['folder_id']) if row['folder_id'] is not None else None,
                'folder_nazov': row['folder_nazov'] if row['folder_nazov'] else 'Nezaradené',
            }

        if selected_folder_id is not None:
            selected_group_file_rows = get_group_files(group_id=group_id, folder_id=selected_folder_id)
            selected_files_title = next(
                (folder['nazov'] for folder in group_file_folders if folder['id'] == selected_folder_id),
                'Priečinok',
            )
        else:
            all_group_file_rows = get_group_files(group_id=group_id)
            selected_group_file_rows = [row for row in all_group_file_rows if row['folder_id'] is not None]
            selected_files_title = 'Všetky priečinky'

        unassigned_group_file_rows = get_group_files(group_id=group_id, only_unassigned=True)

        group_files = [_file_row_to_view(row) for row in selected_group_file_rows]
        unassigned_group_files = [_file_row_to_view(row) for row in unassigned_group_file_rows]

        month_title = datetime(year_value, month_number, 1).strftime('%B %Y')

        # loads chats for the group (may be empty)
        try:
            group_chats = get_group_chats(group_id=group_id)
        except Exception:
            group_chats = []

        return render_template(
            'skupina_detail.html',
            active_tab='skupiny',
            group=group_view,
            hide_main_nav=True,
            active_detail_tab=active_detail_tab,
            group_announcements=group_announcements,
            group_member_posts=group_member_posts,
            group_chats=group_chats,
            current_month_key=current_month_key,
            prev_month_key=prev_month_key,
            next_month_key=next_month_key,
            month_title=month_title,
            calendar_weeks=calendar_weeks,
            month_events=month_events,
            notifications=notifications,
            group_files=group_files,
            unassigned_group_files=unassigned_group_files,
            selected_files_title=selected_files_title,
            group_file_folders=group_file_folders,
            active_file_folder_filter=folder_filter,
            group_file_accept=GROUP_FILE_ACCEPT_VALUE,
            week_days=['Po', 'Ut', 'St', 'Št', 'Pi', 'So', 'Ne'],
            members=members,
            pending_requests=pending_requests,
            is_group_admin=user_is_admin,
        )

    @app.route(f'{APP_BASE_PATH}/skupiny/<int:group_id>/nastenka', methods=['POST'])
    @login_required
    def aplikacia_skupina_nastenka(group_id: int) -> str:
        group = get_group_by_id(group_id)
        if group is None:
            flash('Skupina sa nenašla.', 'error')
            return redirect(url_for('aplikacia_skupiny'))

        membership = get_group_membership(group_id=group_id, user_id=int(g.user['id']))
        if membership is None or membership['status'] != 'member':
            flash('Príspevky na nástenke sú dostupné len pre členov skupiny.', 'error')
            return redirect(url_for('aplikacia_skupiny'))

        board_type = request.form.get('board_type', '').strip().lower()
        board_post_id_raw = request.form.get('board_post_id', '').strip()
        title = request.form.get('title', '').strip()
        content = request.form.get('content', '').strip()
        board_post_id = None

        if request.form.get('board_action', 'create').strip().lower() == 'edit':
            if board_type not in {'announcement', 'member'}:
                flash('Neplatný typ nástenky.', 'error')
                return redirect(url_for('aplikacia_skupina_detail', group_id=group_id, tab='hlavna', _anchor='nastenka'))

            try:
                board_post_id = int(board_post_id_raw)
            except ValueError:
                flash('Neplatný oznam.', 'error')
                return redirect(url_for('aplikacia_skupina_detail', group_id=group_id, tab='hlavna', _anchor='nastenka'))

            post_rows = get_group_board_posts(group_id=group_id, board_type=board_type)
            target_row = next((row for row in post_rows if int(row['id']) == board_post_id), None)
            if target_row is None:
                flash('Oznam sa nenašiel.', 'error')
                return redirect(url_for('aplikacia_skupina_detail', group_id=group_id, tab='hlavna', _anchor='nastenka'))

            if int(target_row['author_user_id']) != int(g.user['id']):
                abort(403)

            if not title:
                flash('Nadpis je povinný.', 'error')
                return redirect(url_for('aplikacia_skupina_detail', group_id=group_id, tab='hlavna', _anchor='nastenka'))

            if len(title) > 140:
                flash('Nadpis môže mať najviac 140 znakov.', 'error')
                return redirect(url_for('aplikacia_skupina_detail', group_id=group_id, tab='hlavna', _anchor='nastenka'))

            if not content:
                flash('Obsah príspevku je povinný.', 'error')
                return redirect(url_for('aplikacia_skupina_detail', group_id=group_id, tab='hlavna', _anchor='nastenka'))

            if len(content) > 1500:
                flash('Obsah môže mať najviac 1500 znakov.', 'error')
                return redirect(url_for('aplikacia_skupina_detail', group_id=group_id, tab='hlavna', _anchor='nastenka'))

            update_group_board_post(post_id=board_post_id, title=title, content=content)
            flash('Oznam bol upravený.', 'success')
            return redirect(url_for('aplikacia_skupina_detail', group_id=group_id, tab='hlavna', _anchor='nastenka'))

        if board_type not in {'announcement', 'member'}:
            flash('Neplatný typ nástenky.', 'error')
            return redirect(url_for('aplikacia_skupina_detail', group_id=group_id, tab='hlavna'))

        if board_type == 'announcement' and not is_group_admin(group_id=group_id, user_id=int(g.user['id'])):
            flash('Oznamy môže pridávať iba administrátor skupiny.', 'error')
            return redirect(url_for('aplikacia_skupina_detail', group_id=group_id, tab='hlavna'))

        if not title:
            flash('Nadpis je povinný.', 'error')
            return redirect(url_for('aplikacia_skupina_detail', group_id=group_id, tab='hlavna', _anchor='nastenka'))

        if len(title) > 140:
            flash('Nadpis môže mať najviac 140 znakov.', 'error')
            return redirect(url_for('aplikacia_skupina_detail', group_id=group_id, tab='hlavna', _anchor='nastenka'))

        if not content:
            flash('Obsah príspevku je povinný.', 'error')
            return redirect(url_for('aplikacia_skupina_detail', group_id=group_id, tab='hlavna', _anchor='nastenka'))

        if len(content) > 1500:
            flash('Obsah môže mať najviac 1500 znakov.', 'error')
            return redirect(url_for('aplikacia_skupina_detail', group_id=group_id, tab='hlavna', _anchor='nastenka'))

        create_group_board_post(
            group_id=group_id,
            author_user_id=int(g.user['id']),
            board_type=board_type,
            title=title,
            content=content,
        )

        flash('Príspevok bol pridaný na nástenku.', 'success')
        return redirect(url_for('aplikacia_skupina_detail', group_id=group_id, tab='hlavna', _anchor='nastenka'))

    @app.route(f'{APP_BASE_PATH}/skupiny/<int:group_id>/nastavenia', methods=['GET', 'POST'])
    @login_required
    def aplikacia_skupina_nastavenia(group_id: int) -> str:
        group = get_group_by_id(group_id)
        if group is None:
            flash('Skupina sa nenašla.', 'error')
            return redirect(url_for('aplikacia_skupiny'))

        if not is_group_admin(group_id=group_id, user_id=int(g.user['id'])):
            flash('Používateľ nemá oprávnenie na úpravu nastavení skupiny.', 'error')
            return redirect(url_for('aplikacia_skupina_detail', group_id=group_id, tab='clenovia'))

        errors: dict[str, str] = {}
        values = {
            'nazov': group['nazov'],
            'popis': group['popis'],
            'pristupnost': 'private' if bool(group['je_sukromna']) else 'public',
        }
        current_image_path = group['obrazok_url']

        member_rows = get_group_members(group_id)
        members = [
            {
                'user_id': int(row['user_id']),
                'full_name': f"{row['meno']} {row['priezvisko']}",
                'role': row['role'],
                'photo_url': url_for('static', filename=row['profilova_fotka']) if row['profilova_fotka'] else None,
                'is_current_user': int(row['user_id']) == int(g.user['id']),
            }
            for row in member_rows
        ]

        if request.method == 'POST':
            settings_action = request.form.get('settings_action', 'group').strip().lower()

            if settings_action == 'role_member':
                try:
                    target_user_id = int(request.form.get('target_user_id', '0'))
                except ValueError:
                    target_user_id = 0
                role_value = request.form.get('role', '').strip().lower()

                if target_user_id <= 0 or role_value not in {'admin', 'member'}:
                    flash('Neplatné údaje pre zmenu role.', 'error')
                    return redirect(url_for('aplikacia_skupina_nastavenia', group_id=group_id))

                target_membership = get_group_membership(group_id=group_id, user_id=target_user_id)
                if target_membership is None or target_membership['status'] != 'member':
                    flash('Člen sa nenašiel.', 'error')
                    return redirect(url_for('aplikacia_skupina_nastavenia', group_id=group_id))

                if target_user_id == int(g.user['id']) and role_value != 'admin' and count_group_admins(group_id) <= 1:
                    flash('Nemôžete odobrať posledného administrátora.', 'error')
                    return redirect(url_for('aplikacia_skupina_nastavenia', group_id=group_id))

                update_member_role(group_id=group_id, member_user_id=target_user_id, role=role_value)
                flash('Rola člena bola aktualizovaná.', 'success')
                return redirect(url_for('aplikacia_skupina_nastavenia', group_id=group_id))

            if settings_action == 'role_all':
                role_value = request.form.get('role', '').strip().lower()
                if role_value not in {'admin', 'member'}:
                    flash('Neplatná rola.', 'error')
                    return redirect(url_for('aplikacia_skupina_nastavenia', group_id=group_id))

                if role_value == 'member':
                    bulk_update_member_roles(group_id=group_id, role='member', exclude_user_id=int(g.user['id']))
                    update_member_role(group_id=group_id, member_user_id=int(g.user['id']), role='admin')
                else:
                    bulk_update_member_roles(group_id=group_id, role='admin')

                flash('Role členov boli hromadne aktualizované.', 'success')
                return redirect(url_for('aplikacia_skupina_nastavenia', group_id=group_id))

            values['nazov'] = request.form.get('nazov', '').strip()
            values['popis'] = request.form.get('popis', '').strip()
            values['pristupnost'] = request.form.get('pristupnost', 'public').strip()

            if not values['nazov']:
                errors['nazov'] = 'Názov skupiny je povinný.'
            elif len(values['nazov']) > 120:
                errors['nazov'] = 'Názov môže mať najviac 120 znakov.'

            if len(values['popis']) > 2000:
                errors['popis'] = 'Popis môže mať najviac 2000 znakov.'

            if values['pristupnost'] not in {'public', 'private'}:
                errors['pristupnost'] = 'Neplatná prístupnosť skupiny.'

            uploaded_photo = request.files.get('profilova_fotka')
            if uploaded_photo and uploaded_photo.filename:
                image_filename = secure_filename(uploaded_photo.filename)
                image_extension = Path(image_filename).suffix.lower()

                if image_extension not in ALLOWED_GROUP_PHOTO_EXTENSIONS:
                    errors['profilova_fotka'] = 'Povolené formáty: PNG, JPG, JPEG, WEBP, GIF.'
                else:
                    stored_image_name, _ = _save_uploaded_file(
                        uploaded_photo,
                        Path(app.config['GROUP_PHOTO_UPLOAD_DIR']),
                        int(g.user['id']),
                    )
                    current_image_path = f"uploads/group_photos/{stored_image_name}"

            if not errors:
                try:
                    update_group(
                        group_id=group_id,
                        nazov=values['nazov'],
                        popis=values['popis'],
                        obrazok_url=current_image_path,
                        je_sukromna=values['pristupnost'] == 'private',
                    )
                except sqlite3.IntegrityError:
                    errors['nazov'] = 'Skupina s týmto názvom už existuje.'
                else:
                    flash('Nastavenia skupiny boli uložené.', 'success')
                    return redirect(url_for('aplikacia_skupina_detail', group_id=group_id, tab='clenovia'))

        group_photo_url = _group_image_src(current_image_path)
        return render_template(
            'skupina_form.html',
            active_tab='skupiny',
            form_title='Nastavenia skupiny',
            submit_label='Uložiť nastavenia',
            values=values,
            errors=errors,
            is_edit=True,
            group_photo_url=group_photo_url,
            group_id=group_id,
            members=members,
            hide_main_nav=True,
        )

    @app.route(f'{APP_BASE_PATH}/skupiny/<int:group_id>/clenovia', methods=['POST'])
    @login_required
    def aplikacia_skupina_clenovia(group_id: int) -> str:
        group = get_group_by_id(group_id)
        if group is None:
            flash('Skupina sa nenašla.', 'error')
            return redirect(url_for('aplikacia_skupiny'))

        if not is_group_admin(group_id=group_id, user_id=int(g.user['id'])):
            flash('Členov môže spravovať len administrátor skupiny.', 'error')
            return redirect(url_for('aplikacia_skupina_detail', group_id=group_id, tab='clenovia'))

        member_action = request.form.get('member_action', '').strip().lower()
        try:
            target_user_id = int(request.form.get('target_user_id', '0'))
        except ValueError:
            target_user_id = 0

        if target_user_id <= 0:
            flash('Neplatný člen skupiny.', 'error')
            return redirect(url_for('aplikacia_skupina_detail', group_id=group_id, tab='clenovia'))

        if member_action == 'remove_member':
            target_membership = get_group_membership(group_id=group_id, user_id=target_user_id)
            if target_membership is None or target_membership['status'] != 'member':
                flash('Člen sa nenašiel.', 'error')
                return redirect(url_for('aplikacia_skupina_detail', group_id=group_id, tab='clenovia'))

            if target_membership['role'] == 'admin' and count_group_admins(group_id) <= 1:
                flash('Nie je možné odstrániť posledného administrátora.', 'error')
                return redirect(url_for('aplikacia_skupina_detail', group_id=group_id, tab='clenovia'))

            remove_group_member(group_id=group_id, member_user_id=target_user_id)
            flash('Člen bol odstránený zo skupiny.', 'success')
            return redirect(url_for('aplikacia_skupina_detail', group_id=group_id, tab='clenovia'))

        if member_action == 'approve_request':
            approve_group_request(group_id=group_id, user_id=target_user_id)
            flash('Žiadosť bola schválená.', 'success')
            return redirect(url_for('aplikacia_skupina_detail', group_id=group_id, tab='clenovia'))

        if member_action == 'reject_request':
            reject_group_request(group_id=group_id, user_id=target_user_id)
            flash('Žiadosť bola zamietnutá.', 'success')
            return redirect(url_for('aplikacia_skupina_detail', group_id=group_id, tab='clenovia'))

        flash('Neplatná akcia správy členov.', 'error')
        return redirect(url_for('aplikacia_skupina_detail', group_id=group_id, tab='clenovia'))

    @app.route(f'{APP_BASE_PATH}/skupiny/<int:group_id>/udalosti', methods=['POST'])
    @login_required
    def aplikacia_skupina_udalosti(group_id: int) -> str:
        group = get_group_by_id(group_id)
        if group is None:
            flash('Skupina sa nenašla.', 'error')
            return redirect(url_for('aplikacia_skupiny'))

        membership = get_group_membership(group_id=group_id, user_id=int(g.user['id']))
        if membership is None or membership['status'] != 'member':
            flash('Kalendár je dostupný len pre členov skupiny.', 'error')
            return redirect(url_for('aplikacia_skupiny'))

        month_raw = request.form.get('month', '').strip()
        month_year, month_number = _parse_group_month(month_raw)
        redirect_month = _month_key(month_year, month_number)

        def _redirect_calendar(month_key: str) -> str:
            return redirect(url_for('aplikacia_skupina_detail', group_id=group_id, tab='kalendar', month=month_key))

        event_action = request.form.get('event_action', '').strip().lower()
        try:
            event_id = int(request.form.get('event_id', '0'))
        except ValueError:
            event_id = 0

        if event_action == 'delete':
            if event_id <= 0:
                flash('Neplatná udalosť.', 'error')
                return _redirect_calendar(redirect_month)

            existing_event = get_group_event_by_id(group_id=group_id, event_id=event_id)
            if existing_event is None:
                flash('Udalosť sa nenašla.', 'error')
                return _redirect_calendar(redirect_month)

            event_label = f"{_format_date_eu(existing_event['event_date'])} {_format_time_24(existing_event['event_time'])} - {existing_event['nazov']}"
            delete_group_event(group_id=group_id, event_id=event_id)
            create_group_event_notification(
                group_id=group_id,
                event_id=None,
                actor_user_id=int(g.user['id']),
                action_type='delete',
                event_date=existing_event['event_date'],
                event_time=existing_event['event_time'],
                message=f"Udalosť bola odstránená: {event_label}",
            )
            flash('Udalosť bola odstránená.', 'success')
            return _redirect_calendar(redirect_month)

        event_date_raw = request.form.get('event_date', '').strip()
        event_time_raw = request.form.get('event_time', '').strip()
        event_title = request.form.get('nazov', '').strip()
        event_description = request.form.get('popis', '').strip()

        parsed_date = _parse_event_date_input(event_date_raw)
        if parsed_date is None:
            flash('Neplatný dátum udalosti.', 'error')
            return _redirect_calendar(redirect_month)

        event_date_raw = parsed_date.isoformat()

        try:
            datetime.strptime(event_time_raw, '%H:%M')
        except ValueError:
            flash('Neplatný čas udalosti.', 'error')
            return _redirect_calendar(redirect_month)

        if not event_title:
            flash('Názov udalosti je povinný.', 'error')
            return _redirect_calendar(redirect_month)

        if len(event_title) > 160:
            flash('Názov udalosti môže mať najviac 160 znakov.', 'error')
            return _redirect_calendar(redirect_month)

        if len(event_description) > 2000:
            flash('Popis udalosti môže mať najviac 2000 znakov.', 'error')
            return _redirect_calendar(redirect_month)

        redirect_month = _month_key(parsed_date.year, parsed_date.month)

        if event_action == 'create':
            new_event_id = create_group_event(
                group_id=group_id,
                created_by_user_id=int(g.user['id']),
                event_date=event_date_raw,
                event_time=event_time_raw,
                nazov=event_title,
                popis=event_description,
            )
            create_group_event_notification(
                group_id=group_id,
                event_id=new_event_id,
                actor_user_id=int(g.user['id']),
                action_type='create',
                event_date=event_date_raw,
                event_time=event_time_raw,
                message=f"Nová udalosť: {_format_date_eu(event_date_raw)} {_format_time_24(event_time_raw)} - {event_title}",
            )
            flash('Udalosť bola vytvorená.', 'success')
            return _redirect_calendar(redirect_month)

        if event_action == 'update':
            if event_id <= 0:
                flash('Neplatná udalosť.', 'error')
                return _redirect_calendar(redirect_month)

            existing_event = get_group_event_by_id(group_id=group_id, event_id=event_id)
            if existing_event is None:
                flash('Udalosť sa nenašla.', 'error')
                return _redirect_calendar(redirect_month)

            update_group_event(
                group_id=group_id,
                event_id=event_id,
                event_date=event_date_raw,
                event_time=event_time_raw,
                nazov=event_title,
                popis=event_description,
            )
            create_group_event_notification(
                group_id=group_id,
                event_id=event_id,
                actor_user_id=int(g.user['id']),
                action_type='update',
                event_date=event_date_raw,
                event_time=event_time_raw,
                message=f"Upravená udalosť: {_format_date_eu(event_date_raw)} {_format_time_24(event_time_raw)} - {event_title}",
            )
            flash('Udalosť bola upravená.', 'success')
            return _redirect_calendar(redirect_month)

        flash('Neplatná akcia udalosti.', 'error')
        return _redirect_calendar(redirect_month)

    @app.route(f'{APP_BASE_PATH}/skupiny/<int:group_id>/subory', methods=['POST'])
    @login_required
    def aplikacia_skupina_subory_nahrat(group_id: int) -> str:
        group = get_group_by_id(group_id)
        if group is None:
            flash('Skupina sa nenašla.', 'error')
            return redirect(url_for('aplikacia_skupiny'))

        membership = get_group_membership(group_id=group_id, user_id=int(g.user['id']))
        if membership is None or membership['status'] != 'member':
            flash('Nahrávanie súborov je dostupné len pre členov skupiny.', 'error')
            return redirect(url_for('aplikacia_skupiny'))

        folder_value = request.form.get('folder_id', '').strip().lower()
        selected_folder_id: int | None = None
        if folder_value and folder_value != 'nezaradene':
            if not folder_value.isdigit():
                flash('Neplatný priečinok pre súbor.', 'error')
                return redirect(url_for('aplikacia_skupina_detail', group_id=group_id, tab='zdielat'))
            selected_folder_id = int(folder_value)
            folder_row = get_group_file_folder_by_id(group_id=group_id, folder_id=selected_folder_id)
            if folder_row is None:
                flash('Vybraný priečinok neexistuje.', 'error')
                return redirect(url_for('aplikacia_skupina_detail', group_id=group_id, tab='zdielat'))

        uploaded_file = request.files.get('subor')
        if not uploaded_file or not uploaded_file.filename:
            flash('Vyberte súbor na nahratie.', 'error')
            return redirect(url_for('aplikacia_skupina_detail', group_id=group_id, tab='zdielat'))

        original_name = secure_filename(uploaded_file.filename)
        extension = Path(original_name).suffix.lower()
        if extension not in ALLOWED_GROUP_SHARED_FILE_EXTENSIONS:
            flash('Nepodporovaný typ súboru.', 'error')
            return redirect(url_for('aplikacia_skupina_detail', group_id=group_id, tab='zdielat'))

        stored_name, original_name = _save_uploaded_file(
            uploaded_file,
            Path(app.config['GROUP_FILE_UPLOAD_DIR']),
            int(g.user['id']),
        )
        file_type = extension if extension else _post_file_type_from_name(original_name)

        create_group_file(
            group_id=group_id,
            uploaded_by_user_id=int(g.user['id']),
            stored_subor=stored_name,
            original_nazov=original_name,
            typ_suboru=file_type,
            folder_id=selected_folder_id,
        )
        flash('Súbor bol nahratý do skupiny.', 'success')
        redirect_folder = str(selected_folder_id) if selected_folder_id is not None else 'nezaradene'
        return redirect(url_for('aplikacia_skupina_detail', group_id=group_id, tab='subory', folder=redirect_folder))

    @app.route(f'{APP_BASE_PATH}/skupiny/<int:group_id>/subory/priecinky', methods=['POST'])
    @login_required
    def aplikacia_skupina_subory_priecinok_vytvorit(group_id: int) -> str:
        group = get_group_by_id(group_id)
        if group is None:
            flash('Skupina sa nenašla.', 'error')
            return redirect(url_for('aplikacia_skupiny'))

        membership = get_group_membership(group_id=group_id, user_id=int(g.user['id']))
        if membership is None or membership['status'] != 'member':
            flash('Priečinky môže spravovať len člen skupiny.', 'error')
            return redirect(url_for('aplikacia_skupiny'))

        folder_name = request.form.get('folder_name', '').strip()
        if not folder_name:
            flash('Názov priečinka je povinný.', 'error')
            return redirect(url_for('aplikacia_skupina_detail', group_id=group_id, tab='subory'))

        if len(folder_name) > 80:
            flash('Názov priečinka môže mať najviac 80 znakov.', 'error')
            return redirect(url_for('aplikacia_skupina_detail', group_id=group_id, tab='subory'))

        folder_id = create_group_file_folder(
            group_id=group_id,
            created_by_user_id=int(g.user['id']),
            nazov=folder_name,
        )
        if folder_id is None:
            flash('Priečinok s týmto názvom už existuje.', 'error')
            return redirect(url_for('aplikacia_skupina_detail', group_id=group_id, tab='subory'))

        flash('Priečinok bol vytvorený.', 'success')
        return redirect(url_for('aplikacia_skupina_detail', group_id=group_id, tab='subory', folder=folder_id))

    @app.route(f'{APP_BASE_PATH}/skupiny/<int:group_id>/subory/<int:group_file_id>/priecinok', methods=['POST'])
    @login_required
    def aplikacia_skupina_subor_priecinok_nastavit(group_id: int, group_file_id: int) -> str:
        group = get_group_by_id(group_id)
        if group is None:
            flash('Skupina sa nenašla.', 'error')
            return redirect(url_for('aplikacia_skupiny'))

        membership = get_group_membership(group_id=group_id, user_id=int(g.user['id']))
        if membership is None or membership['status'] != 'member':
            flash('Triedenie súborov je dostupné len pre členov skupiny.', 'error')
            return redirect(url_for('aplikacia_skupiny'))

        group_file = get_group_file_by_id(group_id=group_id, group_file_id=group_file_id)
        if group_file is None:
            flash('Súbor sa nenašiel.', 'error')
            return redirect(url_for('aplikacia_skupina_detail', group_id=group_id, tab='subory'))

        folder_value = request.form.get('folder_id', '').strip().lower()
        target_folder_id: int | None = None
        redirect_folder = 'all'

        if folder_value and folder_value != 'nezaradene':
            if not folder_value.isdigit():
                flash('Neplatný priečinok pre súbor.', 'error')
                return redirect(url_for('aplikacia_skupina_detail', group_id=group_id, tab='subory'))

            target_folder_id = int(folder_value)
            folder_row = get_group_file_folder_by_id(group_id=group_id, folder_id=target_folder_id)
            if folder_row is None:
                flash('Vybraný priečinok neexistuje.', 'error')
                return redirect(url_for('aplikacia_skupina_detail', group_id=group_id, tab='subory'))
            redirect_folder = folder_value
        else:
            redirect_folder = 'nezaradene'

        update_group_file_folder(
            group_id=group_id,
            group_file_id=group_file_id,
            folder_id=target_folder_id,
        )
        flash('Priečinok súboru bol aktualizovaný.', 'success')
        return redirect(url_for('aplikacia_skupina_detail', group_id=group_id, tab='subory', folder=redirect_folder))

    @app.route(f'{APP_BASE_PATH}/skupiny/<int:group_id>/subory/<int:group_file_id>/nahlad')
    @login_required
    def aplikacia_skupina_subor_nahlad(group_id: int, group_file_id: int):
        group = get_group_by_id(group_id)
        if group is None:
            abort(404)

        membership = get_group_membership(group_id=group_id, user_id=int(g.user['id']))
        if membership is None or membership['status'] != 'member':
            abort(403)

        group_file = get_group_file_by_id(group_id=group_id, group_file_id=group_file_id)
        if group_file is None:
            abort(404)

        mimetype_value = mimetypes.guess_type(group_file['original_nazov'])[0]
        if not mimetype_value:
            mimetype_value = 'application/octet-stream'

        return send_from_directory(
            app.config['GROUP_FILE_UPLOAD_DIR'],
            group_file['stored_subor'],
            as_attachment=False,
            download_name=group_file['original_nazov'],
            mimetype=mimetype_value,
        )

    @app.route(f'{APP_BASE_PATH}/skupiny/<int:group_id>/subory/<int:group_file_id>/stiahnut')
    @login_required
    def aplikacia_skupina_subor_stiahnut(group_id: int, group_file_id: int):
        group = get_group_by_id(group_id)
        if group is None:
            abort(404)

        membership = get_group_membership(group_id=group_id, user_id=int(g.user['id']))
        if membership is None or membership['status'] != 'member':
            abort(403)

        group_file = get_group_file_by_id(group_id=group_id, group_file_id=group_file_id)
        if group_file is None:
            abort(404)

        return send_from_directory(
            app.config['GROUP_FILE_UPLOAD_DIR'],
            group_file['stored_subor'],
            as_attachment=True,
            download_name=group_file['original_nazov'],
        )

    @app.route(f'{APP_BASE_PATH}/skupiny/<int:group_id>/chats', methods=['POST'])
    @login_required
    def aplikacia_skupina_create_chat(group_id: int):
        group = get_group_by_id(group_id)
        if group is None:
            abort(404)

        membership = get_group_membership(group_id=group_id, user_id=int(g.user['id']))
        if membership is None or membership['status'] != 'member':
            abort(403)

        name = request.form.get('name') or (request.json and request.json.get('name')) or ''
        name = str(name).strip()[:140] or 'Chat'

        new_id = create_group_chat(group_id=group_id, nazov=name)

        if request.is_json:
            return {'id': new_id, 'nazov': name}
        return redirect(url_for('aplikacia_skupina_detail', group_id=group_id, tab='spravy'))


    @app.route(f'{APP_BASE_PATH}/skupiny/<int:group_id>/chats/<int:chat_id>/messages', methods=['POST'])
    @login_required
    def aplikacia_skupina_send_message(group_id: int, chat_id: int):
        group = get_group_by_id(group_id)
        if group is None:
            abort(404)

        membership = get_group_membership(group_id=group_id, user_id=int(g.user['id']))
        if membership is None or membership['status'] != 'member':
            abort(403)

        content = request.form.get('content') or (request.json and request.json.get('content')) or ''
        content = str(content).strip()
        if not content:
            abort(400)

        msg_id = create_group_chat_message(chat_id=chat_id, sender_user_id=int(g.user['id']), content=content)

        if request.is_json:
            return {'id': msg_id, 'chat_id': chat_id, 'content': content}
        return redirect(url_for('aplikacia_skupina_detail', group_id=group_id, tab='spravy'))


    @app.route(f'{APP_BASE_PATH}/skupiny/<int:group_id>/chats/<int:chat_id>/messages', methods=['GET'])
    @login_required
    def aplikacia_skupina_get_messages(group_id: int, chat_id: int):
        group = get_group_by_id(group_id)
        if group is None:
            abort(404)

        membership = get_group_membership(group_id=group_id, user_id=int(g.user['id']))
        if membership is None or membership['status'] != 'member':
            abort(403)

        chat = get_chat_by_id(chat_id)
        if chat is None or int(chat['group_id']) != int(group_id):
            abort(404)

        msgs = get_chat_messages(chat_id)
        # format messages similarly to websocket payload
        formatted = []
        for m in msgs:
            author = f"{m.get('author_meno','') or ''} {m.get('author_priezvisko','') or ''}".strip()
            formatted.append({
                'id': m['id'],
                'chat_id': m['chat_id'],
                'sender_user_id': m['sender_user_id'],
                'content': m['content'],
                'created_at': m['created_at'],
                'author': author,
            })
        return {'chat_id': chat_id, 'messages': formatted}

    @app.route(f'{APP_BASE_PATH}/hladat')
    @login_required
    def aplikacia_hladat() -> str:
        query = request.args.get('q', '').strip()
        selected_filters = request.args.getlist('typ')
        valid_filters = {'profiles', 'groups', 'posts'}
        selected_filter_set = {item for item in selected_filters if item in valid_filters}
        if not selected_filter_set:
            selected_filter_set = set(valid_filters)

        members: list[dict] = []
        groups: list[dict] = []
        posts: list[dict] = []

        if query:
            if 'profiles' in selected_filter_set:
                member_rows = search_users_by_name(query)
                members = [
                    {
                        'id': row['id'],
                        'full_name': f"{row['meno']} {row['priezvisko']}",
                        'email': row['email'],
                        'photo_url': url_for('static', filename=row['profilova_fotka']) if row['profilova_fotka'] else None,
                        'profile_url': _profile_url_for_user(int(row['id'])),
                        'is_current_user': int(row['id']) == int(g.user['id']),
                    }
                    for row in member_rows
                ]

            if 'groups' in selected_filter_set:
                group_rows = get_groups_for_user(int(g.user['id']), query)
                groups = [
                    {
                        'id': row['id'],
                        'nazov': row['nazov'],
                        'popis': row['popis'],
                        'obrazok_url': _group_image_src(row['obrazok_url']),
                        'member_count': int(row['member_count'] or 0),
                        'membership_status': row['membership_status'] or '',
                    }
                    for row in group_rows
                ]

            if 'posts' in selected_filter_set:
                post_rows = search_posts(query)
                posts = [
                    {
                        'id': row['id'],
                        'nazov': row['nazov'],
                        'popis': row['popis'],
                        'author': f"{row['author_meno']} {row['author_priezvisko']}",
                        'author_profile_url': _profile_url_for_user(int(row['author_id'])),
                        'author_is_current_user': int(row['author_id']) == int(g.user['id']),
                        'post_slug': _slugify(row['nazov']),
                    }
                    for row in post_rows
                ]

        return render_template(
            'hladat.html',
            active_tab='hladat',
            query=query,
            selected_filters=selected_filter_set,
            members=members,
            groups=groups,
            posts=posts,
        )

    @app.route(f'{APP_BASE_PATH}/pridat')
    @login_required
    def aplikacia_pridat() -> str:
        values = {
            'nazov': '',
            'popis': '',
        }
        return render_template(
            'pridat_prispevok.html',
            active_tab='pridat',
            values=values,
            errors={},
            post_file_accept=POST_FILE_ACCEPT_VALUE,
            post_file_types_description=post_file_types_description(),
        )

    @app.route(f'{APP_BASE_PATH}/pridat', methods=['POST'])
    @login_required
    def aplikacia_pridat_submit() -> str:
        errors: dict[str, str] = {}
        values = {
            'nazov': request.form.get('nazov', '').strip(),
            'popis': request.form.get('popis', '').strip(),
        }

        if not values['nazov']:
            errors['nazov'] = 'Názov príspevku je povinný.'
        elif len(values['nazov']) > 160:
            errors['nazov'] = 'Názov môže mať najviac 160 znakov.'

        if len(values['popis']) > 2000:
            errors['popis'] = 'Popis môže mať najviac 2000 znakov.'

        uploaded_image = request.files.get('nahladovy_obrazok')
        image_relative_path = ''
        if uploaded_image and uploaded_image.filename:
            image_filename = secure_filename(uploaded_image.filename)
            image_extension = Path(image_filename).suffix.lower()

            if image_extension not in ALLOWED_POST_IMAGE_EXTENSIONS:
                errors['nahladovy_obrazok'] = 'Povolené formáty obrázka: PNG, JPG, JPEG, WEBP, GIF.'
            else:
                stored_image_name, _ = _save_uploaded_file(
                    uploaded_image,
                    Path(app.config['POST_IMAGE_UPLOAD_DIR']),
                    int(g.user['id']),
                )
                image_relative_path = f"uploads/post_images/{stored_image_name}"

        uploaded_file = request.files.get('subor')
        file_relative_path = ''
        file_original_name = ''
        file_extension = ''
        if not uploaded_file or not uploaded_file.filename:
            errors['subor'] = 'Súbor je povinný.'
        else:
            file_name = secure_filename(uploaded_file.filename)
            file_extension = Path(file_name).suffix.lower()

            if file_extension not in ALLOWED_POST_FILE_EXTENSIONS:
                errors['subor'] = 'Nepodporovaný typ súboru.'
            else:
                stored_file_name, file_original_name = _save_uploaded_file(
                    uploaded_file,
                    Path(app.config['POST_FILE_UPLOAD_DIR']),
                    int(g.user['id']),
                )
                file_relative_path = f"uploads/post_files/{stored_file_name}"

        if errors:
            return render_template(
                'pridat_prispevok.html',
                active_tab='pridat',
                values=values,
                errors=errors,
                post_file_accept=POST_FILE_ACCEPT_VALUE,
                post_file_types_description=post_file_types_description(),
            )

        # Generate thumbnail if no preview image was uploaded
        final_preview_path = image_relative_path
        if not final_preview_path and file_relative_path:
            # If file is an image, use it as preview
            if file_extension in {'.jpg', '.jpeg', '.png', '.webp', '.gif'}:
                final_preview_path = file_relative_path
            # If file is PDF, try to generate thumbnail
            elif file_extension == '.pdf':
                file_full_path = Path(app.config['POST_FILE_UPLOAD_DIR']) / stored_file_name
                thumbnail_uri = generate_thumbnail_from_file(file_full_path, file_extension)
                if thumbnail_uri:
                    final_preview_path = thumbnail_uri
                else:
                    # Fallback to SVG icon if PDF conversion fails
                    final_preview_path = get_file_icon_svg(file_extension)
            # For other file types, use SVG icon
            else:
                final_preview_path = get_file_icon_svg(file_extension)

        create_post(
            author_id=int(g.user['id']),
            nazov=values['nazov'],
            popis=values['popis'],
            nahladovy_obrazok=final_preview_path,
            subor=file_relative_path,
            subor_povodny_nazov=file_original_name,
        )
        flash('Príspevok bol úspešne nahratý.', 'success')
        return redirect(url_for('aplikacia_domov'))

    @app.route(f'{APP_BASE_PATH}/ucenie')
    @login_required
    def aplikacia_ucenie() -> str:
        return render_template(
            'ucenie.html',
            active_tab='ucenie',
        )

    @app.route(f'{APP_BASE_PATH}/todo-list')
    @login_required
    def aplikacia_todo_list() -> str:
        return render_template(
            'todo_list.html',
            active_tab='ucenie',
        )

    @app.route(f'{APP_BASE_PATH}/api/tasks', methods=['GET'])
    @login_required
    def api_get_tasks():
        user_id = int(g.user['id'])
        tasks = get_tasks_for_user(user_id)
        return jsonify({
            'success': True,
            'tasks': [
                {
                    'id': task['id'],
                    'text': task['text'],
                    'is_completed': bool(task['is_completed']),
                    'deadline': task['deadline'],
                }
                for task in tasks
            ]
        })

    @app.route(f'{APP_BASE_PATH}/api/tasks', methods=['POST'])
    @login_required
    def api_create_task():
        data = request.get_json()
        if not data or 'text' not in data:
            return jsonify({'success': False, 'message': 'Text je povinný'}), 400

        user_id = int(g.user['id'])
        text = data.get('text', '').strip()
        deadline = data.get('deadline')

        if not text:
            return jsonify({'success': False, 'message': 'Text úlohy nemôže byť prázdny'}), 400

        task_id = create_task(user_id, text, deadline)
        return jsonify({'success': True, 'task_id': task_id})

    @app.route(f'{APP_BASE_PATH}/api/tasks/<int:task_id>', methods=['PUT'])
    @login_required
    def api_update_task(task_id: int):
        task = get_task_by_id(task_id)
        if not task or task['user_id'] != int(g.user['id']):
            return jsonify({'success': False, 'message': 'Úloha sa nenašla'}), 404

        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'Žiadne údaje'}), 400

        text = data.get('text', task['text']).strip()
        deadline = data.get('deadline', task['deadline'])

        if not text:
            return jsonify({'success': False, 'message': 'Text úlohy nemôže byť prázdny'}), 400

        update_task(task_id, text=text, deadline=deadline)
        return jsonify({'success': True})

    @app.route(f'{APP_BASE_PATH}/api/tasks/<int:task_id>', methods=['DELETE'])
    @login_required
    def api_delete_task(task_id: int):
        task = get_task_by_id(task_id)
        if not task or task['user_id'] != int(g.user['id']):
            return jsonify({'success': False, 'message': 'Úloha sa nenašla'}), 404

        delete_task(task_id)
        return jsonify({'success': True})

    @app.route(f'{APP_BASE_PATH}/api/tasks/<int:task_id>/toggle', methods=['PUT'])
    @login_required
    def api_toggle_task(task_id: int):
        task = get_task_by_id(task_id)
        if not task or task['user_id'] != int(g.user['id']):
            return jsonify({'success': False, 'message': 'Úloha sa nenašla'}), 404

        toggle_task_completion(task_id)
        return jsonify({'success': True})

    @app.route(f'{APP_BASE_PATH}/karticky')
    @login_required
    def aplikacia_karticky() -> str:
        return render_template(
            'karticky.html',
            active_tab='ucenie',
        )

    @app.route(f'{APP_BASE_PATH}/karticky/<int:deck_id>')
    @login_required
    def aplikacia_karticky_learn(deck_id: int) -> str:
        deck = get_deck_by_id(deck_id)
        if not deck or deck['user_id'] != int(g.user['id']):
            flash('Balíček sa nenašiel.', 'error')
            return redirect(url_for('aplikacia_karticky'))
        return render_template(
            'karticky_learn.html',
            deck=deck,
            active_tab='ucenie',
        )

    @app.route(f'{APP_BASE_PATH}/api/decks', methods=['GET'])
    @login_required
    def api_get_decks():
        user_id = int(g.user['id'])
        decks = get_decks_for_user(user_id)
        return jsonify({
            'success': True,
            'decks': [
                {
                    'id': deck['id'],
                    'name': deck['name'],
                    'description': deck['description'],
                    'color': deck['color'],
                    'card_count': len(get_cards_for_deck(deck['id'])),
                }
                for deck in decks
            ]
        })

    @app.route(f'{APP_BASE_PATH}/api/decks', methods=['POST'])
    @login_required
    def api_create_deck():
        data = request.get_json()
        if not data or 'name' not in data:
            return jsonify({'success': False, 'message': 'Názov je povinný'}), 400

        user_id = int(g.user['id'])
        name = data.get('name', '').strip()
        description = data.get('description', '').strip()
        color = data.get('color', '#FFE5B4').strip()

        if not name:
            return jsonify({'success': False, 'message': 'Názov nemôže byť prázdny'}), 400

        deck_id = create_deck(user_id, name, description, color)
        return jsonify({'success': True, 'deck_id': deck_id, 'color': color})

    @app.route(f'{APP_BASE_PATH}/api/decks/<int:deck_id>', methods=['DELETE'])
    @login_required
    def api_delete_deck(deck_id: int):
        deck = get_deck_by_id(deck_id)
        if not deck or deck['user_id'] != int(g.user['id']):
            return jsonify({'success': False, 'message': 'Balíček sa nenašiel'}), 404

        delete_deck(deck_id)
        return jsonify({'success': True})

    @app.route(f'{APP_BASE_PATH}/api/decks/<int:deck_id>/cards', methods=['GET'])
    @login_required
    def api_get_cards(deck_id: int):
        deck = get_deck_by_id(deck_id)
        if not deck or deck['user_id'] != int(g.user['id']):
            return jsonify({'success': False, 'message': 'Balíček sa nenašiel'}), 404

        cards = get_cards_for_deck(deck_id)
        return jsonify({
            'success': True,
            'cards': [
                {
                    'id': card['id'],
                    'question': card['question'],
                    'answer': card['answer'],
                    'color': card['color'],
                }
                for card in cards
            ]
        })

    @app.route(f'{APP_BASE_PATH}/api/decks/<int:deck_id>/cards', methods=['POST'])
    @login_required
    def api_create_card(deck_id: int):
        deck = get_deck_by_id(deck_id)
        if not deck or deck['user_id'] != int(g.user['id']):
            return jsonify({'success': False, 'message': 'Balíček sa nenašiel'}), 404

        data = request.get_json()
        if not data or 'question' not in data or 'answer' not in data:
            return jsonify({'success': False, 'message': 'Otázka a odpoveď sú povinné'}), 400

        question = data.get('question', '').strip()
        answer = data.get('answer', '').strip()

        if not question or not answer:
            return jsonify({'success': False, 'message': 'Otázka a odpoveď nemôžu byť prázdne'}), 400

        card_id = create_card(deck_id, question, answer)
        return jsonify({'success': True, 'card_id': card_id})

    @app.route(f'{APP_BASE_PATH}/api/decks/<int:deck_id>/cards/<int:card_id>', methods=['DELETE'])
    @login_required
    def api_delete_card(deck_id: int, card_id: int):
        deck = get_deck_by_id(deck_id)
        if not deck or deck['user_id'] != int(g.user['id']):
            return jsonify({'success': False, 'message': 'Balíček sa nenašiel'}), 404

        card = get_card_by_id(card_id)
        if not card or card['deck_id'] != deck_id:
            return jsonify({'success': False, 'message': 'Kartička sa nenašla'}), 404

        delete_card(card_id)
        return jsonify({'success': True})

    @app.route(f'{APP_BASE_PATH}/api/attempts', methods=['POST'])
    @login_required
    def api_save_attempt():
        data = request.get_json()
        if not data or 'deck_id' not in data:
            return jsonify({'success': False, 'message': 'Údaje sú povinné'}), 400

        deck_id = data.get('deck_id')
        correct_count = data.get('correct_count', 0)
        incorrect_count = data.get('incorrect_count', 0)

        deck = get_deck_by_id(deck_id)
        if not deck or deck['user_id'] != int(g.user['id']):
            return jsonify({'success': False, 'message': 'Balíček sa nenašiel'}), 404

        user_id = int(g.user['id'])
        attempt_id = create_attempt(deck_id, user_id, correct_count, incorrect_count)
        return jsonify({'success': True, 'attempt_id': attempt_id})

    @app.route(f'{APP_BASE_PATH}/prispevky/<int:post_id>/<post_slug>', methods=['GET', 'POST'])
    @login_required
    def aplikacia_prispevok_detail(post_id: int, post_slug: str) -> str:
        post_row = get_post_by_id(post_id)
        if post_row is None:
            flash('Príspevok sa nenašiel.', 'error')
            return redirect(url_for('aplikacia_domov'))

        canonical_post_slug = _slugify(post_row['nazov'])
        if post_slug != canonical_post_slug and request.method == 'GET':
            return redirect(url_for('aplikacia_prispevok_detail', post_id=post_id, post_slug=canonical_post_slug))

        is_owner = int(post_row['author_id']) == int(g.user['id'])

        comment_errors: dict[str, str] = {}
        comment_form_values = {
            'text': '',
            'parent_comment_id': '',
        }
        comment_edit_errors: dict[str, str] = {}
        comment_edit_values = {
            'comment_id': '',
            'text': '',
        }
        edit_errors: dict[str, str] = {}
        edit_values = {
            'nazov': post_row['nazov'],
            'popis': post_row['popis'],
            'remove_nahladovy_obrazok': False,
            'remove_subor': False,
        }
        edit_form_open = request.args.get('edit') == '1'

        if request.method == 'POST':
            action_type = request.form.get('action_type', '')

            if action_type == 'edit_post':
                if not is_owner:
                    abort(403)

                edit_values['nazov'] = request.form.get('nazov', '').strip()
                edit_values['popis'] = request.form.get('popis', '').strip()
                edit_values['remove_nahladovy_obrazok'] = request.form.get('remove_nahladovy_obrazok') == '1'
                edit_values['remove_subor'] = request.form.get('remove_subor') == '1'

                if not edit_values['nazov']:
                    edit_errors['nazov'] = 'Názov príspevku je povinný.'
                elif len(edit_values['nazov']) > 160:
                    edit_errors['nazov'] = 'Názov môže mať najviac 160 znakov.'

                if len(edit_values['popis']) > 2000:
                    edit_errors['popis'] = 'Popis môže mať najviac 2000 znakov.'

                image_relative_path = str(post_row['nahladovy_obrazok'] or '')
                new_image_relative_path = ''
                uploaded_image = request.files.get('nahladovy_obrazok')
                if uploaded_image and uploaded_image.filename:
                    image_filename = secure_filename(uploaded_image.filename)
                    image_extension = Path(image_filename).suffix.lower()
                    if image_extension not in ALLOWED_POST_IMAGE_EXTENSIONS:
                        edit_errors['nahladovy_obrazok'] = 'Povolené formáty obrázka: PNG, JPG, JPEG, WEBP, GIF.'
                    else:
                        stored_image_name, _ = _save_uploaded_file(
                            uploaded_image,
                            Path(app.config['POST_IMAGE_UPLOAD_DIR']),
                            int(g.user['id']),
                        )
                        new_image_relative_path = f"uploads/post_images/{stored_image_name}"

                file_relative_path = str(post_row['subor'] or '')
                file_original_name = str(post_row['subor_povodny_nazov'] or '')
                new_file_relative_path = ''
                new_file_original_name = ''
                uploaded_file = request.files.get('subor')
                if uploaded_file and uploaded_file.filename:
                    file_name = secure_filename(uploaded_file.filename)
                    file_extension = Path(file_name).suffix.lower()
                    if file_extension not in ALLOWED_POST_FILE_EXTENSIONS:
                        edit_errors['subor'] = 'Nepodporovaný typ súboru.'
                    else:
                        stored_file_name, new_file_original_name = _save_uploaded_file(
                            uploaded_file,
                            Path(app.config['POST_FILE_UPLOAD_DIR']),
                            int(g.user['id']),
                        )
                        new_file_relative_path = f"uploads/post_files/{stored_file_name}"

                if edit_errors:
                    if new_image_relative_path:
                        _delete_uploaded_static_file(app.static_folder, new_image_relative_path)
                    if new_file_relative_path:
                        _delete_uploaded_static_file(app.static_folder, new_file_relative_path)
                    edit_form_open = True
                else:
                    if new_image_relative_path:
                        if image_relative_path:
                            _delete_uploaded_static_file(app.static_folder, image_relative_path)
                        image_relative_path = new_image_relative_path
                    elif edit_values['remove_nahladovy_obrazok'] and image_relative_path:
                        _delete_uploaded_static_file(app.static_folder, image_relative_path)
                        image_relative_path = ''

                    if new_file_relative_path:
                        if file_relative_path:
                            _delete_uploaded_static_file(app.static_folder, file_relative_path)
                        file_relative_path = new_file_relative_path
                        file_original_name = new_file_original_name
                    elif edit_values['remove_subor'] and file_relative_path:
                        _delete_uploaded_static_file(app.static_folder, file_relative_path)
                        file_relative_path = ''
                        file_original_name = ''

                    update_post(
                        post_id=post_id,
                        nazov=edit_values['nazov'],
                        popis=edit_values['popis'],
                        nahladovy_obrazok=image_relative_path,
                        subor=file_relative_path,
                        subor_povodny_nazov=file_original_name,
                    )
                    flash('Príspevok bol upravený.', 'success')
                    return redirect(
                        url_for(
                            'aplikacia_prispevok_detail',
                            post_id=post_id,
                            post_slug=_slugify(edit_values['nazov']),
                        )
                    )

            elif action_type == 'delete_post':
                if not is_owner:
                    abort(403)

                image_relative_path = str(post_row['nahladovy_obrazok'] or '')
                file_relative_path = str(post_row['subor'] or '')
                if image_relative_path:
                    _delete_uploaded_static_file(app.static_folder, image_relative_path)
                if file_relative_path:
                    _delete_uploaded_static_file(app.static_folder, file_relative_path)

                delete_post(post_id)
                flash('Príspevok bol vymazaný.', 'success')
                return redirect(url_for('aplikacia_domov'))

            elif action_type == 'rating':
                if is_owner:
                    flash('Autor príspevku nemôže hodnotiť vlastný príspevok.', 'error')
                    return redirect(url_for('aplikacia_prispevok_detail', post_id=post_id, post_slug=canonical_post_slug))

                try:
                    rating_value = int(request.form.get('rating', '0'))
                except ValueError:
                    rating_value = 0

                if rating_value < 1 or rating_value > 5:
                    flash('Hodnotenie musí byť od 1 do 5 hviezdičiek.', 'error')
                else:
                    upsert_post_rating(post_id=post_id, user_id=int(g.user['id']), rating=rating_value)
                    flash('Hodnotenie bolo uložené.', 'success')

                return redirect(url_for('aplikacia_prispevok_detail', post_id=post_id, post_slug=canonical_post_slug, _anchor='hodnotenie'))

            elif action_type == 'comment':
                comment_text = request.form.get('text', '').strip()
                parent_comment_raw = request.form.get('parent_comment_id', '').strip()
                comment_form_values['text'] = comment_text
                comment_form_values['parent_comment_id'] = parent_comment_raw

                if not comment_text:
                    comment_errors['text'] = 'Komentár nemôže byť prázdny.'
                elif len(comment_text) > 2000:
                    comment_errors['text'] = 'Komentár môže mať najviac 2000 znakov.'

                parent_comment_id = None
                if parent_comment_raw:
                    try:
                        parent_comment_id = int(parent_comment_raw)
                    except ValueError:
                        comment_errors['parent_comment_id'] = 'Neplatná odpoveď na komentár.'
                    else:
                        parent_comment_row = get_post_comment_by_id(post_id, parent_comment_id)
                        if parent_comment_row is None:
                            comment_errors['parent_comment_id'] = 'Pôvodný komentár sa nenašiel.'

                if not comment_errors:
                    create_post_comment(
                        post_id=post_id,
                        user_id=int(g.user['id']),
                        text=comment_text,
                        parent_comment_id=parent_comment_id,
                    )
                    flash('Komentár bol uložený.', 'success')
                    return redirect(url_for('aplikacia_prispevok_detail', post_id=post_id, post_slug=canonical_post_slug, _anchor='komentare'))

            elif action_type == 'edit_comment':
                comment_id_raw = request.form.get('comment_id', '').strip()
                edited_text = request.form.get('text', '').strip()

                comment_edit_values['comment_id'] = comment_id_raw
                comment_edit_values['text'] = edited_text

                comment_row = None
                comment_id = None

                if not comment_id_raw:
                    comment_edit_errors['text'] = 'Komentár sa nepodarilo identifikovať.'
                else:
                    try:
                        comment_id = int(comment_id_raw)
                    except ValueError:
                        comment_edit_errors['text'] = 'Neplatný identifikátor komentára.'
                    else:
                        comment_row = get_post_comment_by_id(post_id, comment_id)
                        if comment_row is None:
                            comment_edit_errors['text'] = 'Komentár sa nenašiel.'
                        elif int(comment_row['user_id']) != int(g.user['id']):
                            abort(403)

                if not edited_text:
                    comment_edit_errors['text'] = 'Komentár nemôže byť prázdny.'
                elif len(edited_text) > 2000:
                    comment_edit_errors['text'] = 'Komentár môže mať najviac 2000 znakov.'

                if not comment_edit_errors and comment_id is not None:
                    update_post_comment(comment_id=comment_id, text=edited_text)
                    flash('Komentár bol upravený.', 'success')
                    return redirect(url_for('aplikacia_prispevok_detail', post_id=post_id, post_slug=canonical_post_slug, _anchor='komentare'))

            else:
                flash('Neplatná akcia.', 'error')
                return redirect(url_for('aplikacia_prispevok_detail', post_id=post_id, post_slug=canonical_post_slug))

        post_row = get_post_by_id(post_id)
        if post_row is None:
            flash('Príspevok sa nenašiel.', 'error')
            return redirect(url_for('aplikacia_domov'))

        current_user_rating = None if is_owner else get_user_post_rating(post_id=post_id, user_id=int(g.user['id']))
        comments_tree = _build_comment_tree(get_post_comments(post_id))

        post = {
            'id': post_row['id'],
            'nazov': post_row['nazov'],
            'popis': post_row['popis'],
            'author_id': int(post_row['author_id']),
            'autor': f"{post_row['author_meno']} {post_row['author_priezvisko']}",
            'author_profile_url': _profile_url_for_user(int(post_row['author_id'])),
            'author_is_current_user': int(post_row['author_id']) == int(g.user['id']),
            'datum_vytvorenia': _format_datetime_eu(post_row['datum_vytvorenia']),
            'nahladovy_obrazok_url': url_for('static', filename=post_row['nahladovy_obrazok']) if post_row['nahladovy_obrazok'] else None,
            'subor_url': url_for('static', filename=post_row['subor']) if post_row['subor'] else None,
            'subor_povodny_nazov': post_row['subor_povodny_nazov'],
            'typ_suboru': _post_file_type_from_name(post_row['subor_povodny_nazov']) if post_row['subor_povodny_nazov'] else 'bez súboru',
            'post_slug': canonical_post_slug,
            'average_rating': float(post_row['average_rating'] or 0),
            'rating_count': int(post_row['rating_count'] or 0),
            'rating_text': _format_rating(float(post_row['average_rating'] or 0), int(post_row['rating_count'] or 0)),
            'rating_stars': _build_rating_stars(float(post_row['average_rating'] or 0)),
        }

        return render_template(
            'prispevok_detail.html',
            active_tab='domov',
            post=post,
            is_post_owner=is_owner,
            post_file_accept=POST_FILE_ACCEPT_VALUE,
            current_user_rating=current_user_rating,
            comments_tree=comments_tree,
            comment_errors=comment_errors,
            comment_form_values=comment_form_values,
            comment_edit_errors=comment_edit_errors,
            comment_edit_values=comment_edit_values,
            comments_modal_open=bool(comment_errors or comment_edit_errors),
            edit_errors=edit_errors,
            edit_values=edit_values,
            edit_form_open=edit_form_open,
        )

    @app.route(f'{APP_BASE_PATH}/prispevky/<int:post_id>/vymazat', methods=['POST'])
    @login_required
    def aplikacia_prispevok_vymazat(post_id: int) -> str:
        post_row = get_post_by_id(post_id)
        if post_row is None:
            flash('Príspevok sa nenašiel.', 'error')
            return redirect(url_for('aplikacia_profil'))

        if int(post_row['author_id']) != int(g.user['id']):
            abort(403)

        image_relative_path = str(post_row['nahladovy_obrazok'] or '')
        file_relative_path = str(post_row['subor'] or '')
        if image_relative_path:
            _delete_uploaded_static_file(app.static_folder, image_relative_path)
        if file_relative_path:
            _delete_uploaded_static_file(app.static_folder, file_relative_path)

        delete_post(post_id)
        flash('Príspevok bol vymazaný.', 'success')
        return redirect(url_for('aplikacia_profil'))

    @app.route(f'{APP_BASE_PATH}/profil', methods=['GET', 'POST'])
    @login_required
    def aplikacia_profil() -> str:
        errors: dict[str, str] = {}
        edit_mode = request.args.get('edit') == '1'
        user_posts_rows = get_posts_by_author_id(int(g.user['id']))
        user_groups_rows = get_member_groups_for_user(int(g.user['id']))
        user_posts = [
            {
                'id': row['id'],
                'nazov': row['nazov'],
                'post_slug': _slugify(row['nazov']),
                'datum_vytvorenia': _format_datetime_eu(row['datum_vytvorenia']),
            }
            for row in user_posts_rows
        ]
        user_groups = [
            {
                'id': row['id'],
                'nazov': row['nazov'],
                'obrazok_url': _group_image_src(row['obrazok_url']),
                'membership_role': row['membership_role'],
                'member_count': int(row['member_count'] or 0),
            }
            for row in user_groups_rows
        ]
        profile = get_profile_by_user_id(int(g.user['id']))
        additional_emails = get_user_additional_emails(int(g.user['id']))
        profile_values = profile_values_from_row(profile)
        values = profile_form_values(g.user, profile)
        values['additional_emails'] = '\n'.join(additional_emails)
        profile_photo_path = profile_values['profilova_fotka']
        theme_bg_image_path = profile_values['theme_bg_image']

        if request.method == 'POST':
            if request.form.get('action') == 'cancel':
                return redirect(url_for('aplikacia_profil'))

            errors, values = validate_profile(request.form, g.user)
            edit_mode = True

            uploaded_photo = request.files.get('profilova_fotka')
            if uploaded_photo and uploaded_photo.filename:
                sanitized_filename = secure_filename(uploaded_photo.filename)
                extension = Path(sanitized_filename).suffix.lower()

                if extension not in ALLOWED_PROFILE_PHOTO_EXTENSIONS:
                    errors['profilova_fotka'] = 'Povolené formáty: PNG, JPG, JPEG, WEBP, GIF.'
                else:
                    upload_dir = Path(app.config['PROFILE_PHOTO_UPLOAD_DIR'])
                    new_filename = f"user_{int(g.user['id'])}_{uuid4().hex}{extension}"
                    destination = upload_dir / new_filename
                    uploaded_photo.save(destination)

                    if profile_photo_path:
                        old_file = Path(app.static_folder or '') / profile_photo_path
                        if old_file.exists() and old_file.is_file():
                            old_file.unlink()

                    profile_photo_path = f"uploads/profile_photos/{new_filename}"

            uploaded_theme_bg = request.files.get('theme_bg_image')
            if uploaded_theme_bg and uploaded_theme_bg.filename:
                sanitized_bg_name = secure_filename(uploaded_theme_bg.filename)
                bg_extension = Path(sanitized_bg_name).suffix.lower()

                if bg_extension not in ALLOWED_THEME_BG_EXTENSIONS:
                    errors['theme_bg_image'] = 'Povolené formáty obrázka pozadia: PNG, JPG, JPEG, WEBP, GIF.'
                else:
                    bg_upload_dir = Path(app.config['THEME_BG_UPLOAD_DIR'])
                    new_bg_name = f"user_{int(g.user['id'])}_theme_{uuid4().hex}{bg_extension}"
                    bg_destination = bg_upload_dir / new_bg_name
                    uploaded_theme_bg.save(bg_destination)

                    if theme_bg_image_path:
                        old_bg_file = Path(app.static_folder or '') / theme_bg_image_path
                        if old_bg_file.exists() and old_bg_file.is_file():
                            old_bg_file.unlink()

                    theme_bg_image_path = f"uploads/theme_backgrounds/{new_bg_name}"

            if request.form.get('remove_theme_bg') == '1' and not (uploaded_theme_bg and uploaded_theme_bg.filename):
                if theme_bg_image_path:
                    old_bg_file = Path(app.static_folder or '') / theme_bg_image_path
                    if old_bg_file.exists() and old_bg_file.is_file():
                        old_bg_file.unlink()
                theme_bg_image_path = ''

            selected_theme_preset = values.get('theme_preset', 'default')
            selected_theme_bg_color = values.get('theme_bg_color', THEME_PRESETS['default']['bg'])
            selected_theme_nav_color = values.get('theme_nav_color', THEME_PRESETS['default']['nav'])
            selected_theme_preset, selected_theme_bg_color, selected_theme_nav_color = _normalize_theme_values(
                selected_theme_preset,
                selected_theme_bg_color,
                selected_theme_nav_color,
            )
            values['theme_preset'] = selected_theme_preset
            values['theme_bg_color'] = selected_theme_bg_color
            values['theme_nav_color'] = selected_theme_nav_color

            if not errors:
                save_profile(
                    user_id=int(g.user['id']),
                    skola=values['skola'],
                    rocnik_studia=values['rocnik_studia'],
                    popis=values['popis'],
                    profilova_fotka=profile_photo_path,
                    theme_preset=values['theme_preset'],
                    theme_bg_color=values['theme_bg_color'],
                    theme_nav_color=values['theme_nav_color'],
                    theme_bg_image=theme_bg_image_path,
                )
                replace_user_additional_emails(
                    user_id=int(g.user['id']),
                    emails=[line.strip() for line in values.get('additional_emails', '').splitlines() if line.strip()],
                )
                flash('Profil bol úspešne uložený.', 'success')
                return redirect(url_for('aplikacia_profil'))

        profile_photo_url = url_for('static', filename=profile_photo_path) if profile_photo_path else None
        theme_bg_image_url = url_for('static', filename=theme_bg_image_path) if theme_bg_image_path else None

        return render_template(
            'profil.html',
            active_tab='profil',
            profile_user=g.user,
            profile_values=profile_values,
            profile_photo_url=profile_photo_url,
            values=values,
            errors=errors,
            edit_mode=edit_mode,
            is_public_view=False,
            user_posts=user_posts,
            user_groups=user_groups,
            additional_emails=additional_emails,
            theme_bg_image_url=theme_bg_image_url,
            theme_presets=THEME_PRESETS,
        )

    @app.route(f'{APP_BASE_PATH}/profil/<int:user_id>')
    @login_required
    def aplikacia_profil_verejny(user_id: int) -> str:
        if int(g.user['id']) == user_id:
            return redirect(url_for('aplikacia_profil'))

        viewed_user = get_user_by_id(user_id)
        if viewed_user is None:
            flash('Používateľ sa nenašiel.', 'error')
            return redirect(url_for('aplikacia_hladat'))

        profile = get_profile_by_user_id(user_id)
        additional_emails = get_user_additional_emails(user_id)
        profile_values = profile_values_from_row(profile)

        user_posts_rows = get_posts_by_author_id(user_id)
        user_groups_rows = get_member_groups_for_user(user_id)

        user_posts = [
            {
                'id': row['id'],
                'nazov': row['nazov'],
                'post_slug': _slugify(row['nazov']),
                'datum_vytvorenia': _format_datetime_eu(row['datum_vytvorenia']),
            }
            for row in user_posts_rows
        ]
        user_groups = [
            {
                'id': row['id'],
                'nazov': row['nazov'],
                'obrazok_url': _group_image_src(row['obrazok_url']),
                'membership_role': row['membership_role'],
                'member_count': int(row['member_count'] or 0),
            }
            for row in user_groups_rows
        ]

        profile_photo_path = profile_values['profilova_fotka']
        profile_photo_url = url_for('static', filename=profile_photo_path) if profile_photo_path else None

        return render_template(
            'profil.html',
            active_tab='hladat',
            profile_user=viewed_user,
            profile_values=profile_values,
            profile_photo_url=profile_photo_url,
            values={},
            errors={},
            edit_mode=False,
            is_public_view=True,
            user_posts=user_posts,
            user_groups=user_groups,
            additional_emails=additional_emails,
            theme_bg_image_url=None,
            theme_presets=THEME_PRESETS,
        )
