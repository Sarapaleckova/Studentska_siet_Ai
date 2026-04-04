"""Route definitions for Študentská sieť."""

from calendar import monthrange
from datetime import date, datetime
from functools import wraps
from pathlib import Path
import re
import sqlite3
import unicodedata
from uuid import uuid4

from flask import Flask, flash, g, redirect, render_template, request, session, url_for
from werkzeug.utils import secure_filename

from student_network.file_types import (
    ALLOWED_POST_FILE_EXTENSIONS,
    ALLOWED_POST_IMAGE_EXTENSIONS,
    POST_FILE_ACCEPT_VALUE,
    post_file_types_description,
)
from student_network.repositories.comments import create_post_comment, get_post_comment_by_id, get_post_comments
from student_network.repositories.group_events import (
    create_group_event,
    create_group_event_notification,
    delete_group_event,
    get_group_event_by_id,
    get_group_events_for_month,
    get_group_notifications,
    update_group_event,
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
from student_network.repositories.profiles import get_profile_by_user_id, save_profile
from student_network.repositories.posts import create_post, get_all_posts, get_post_by_id, get_posts_by_author_id
from student_network.repositories.ratings import get_user_post_rating, upsert_post_rating
from student_network.repositories.users import get_user_by_id, update_user_name
from student_network.services.auth_service import register_user, validate_login
from student_network.services.profile_service import profile_form_values, profile_values_from_row, validate_profile

ALLOWED_PROFILE_PHOTO_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp', '.gif'}
ALLOWED_GROUP_PHOTO_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp', '.gif'}
APP_BASE_PATH = '/studentska-siet'
GROUP_TABS = {'zdielat', 'notifikacie', 'kalendar', 'clenovia', 'subory'}


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
                'autor': f"{row['author_meno']} {row['author_priezvisko']}",
                'subor_povodny_nazov': row['subor_povodny_nazov'],
                'typ_suboru': _post_file_type_from_name(row['subor_povodny_nazov']) if row['subor_povodny_nazov'] else 'bez súboru',
                'average_rating': float(row['average_rating'] or 0),
                'rating_count': int(row['rating_count'] or 0),
                'rating_text': _format_rating(float(row['average_rating'] or 0), int(row['rating_count'] or 0)),
                'nahladovy_obrazok_url': url_for('static', filename=row['nahladovy_obrazok']) if row['nahladovy_obrazok'] else None,
            }
            for row in post_rows
        ]
        return render_template(
            'domov.html',
            active_tab='domov',
            posts=posts,
        )

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
            }
            for row in pending_rows
        ]

        month_value = request.args.get('month', '').strip()
        year_value, month_number = _parse_group_month(month_value)
        current_month_key = _month_key(year_value, month_number)
        prev_month_key = _month_key(*_shift_month(year_value, month_number, -1))
        next_month_key = _month_key(*_shift_month(year_value, month_number, 1))

        active_detail_tab = request.args.get('tab', 'zdielat').strip().lower()
        if active_detail_tab not in GROUP_TABS:
            active_detail_tab = 'zdielat'

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
        event_dates = {event['event_date'] for event in month_events}

        calendar_weeks = _build_group_calendar_grid(
            year_value=year_value,
            month_value=month_number,
            event_dates=event_dates,
        )

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

        month_title = datetime(year_value, month_number, 1).strftime('%B %Y')

        return render_template(
            'skupina_detail.html',
            active_tab='skupiny',
            group=group_view,
            hide_main_nav=True,
            active_detail_tab=active_detail_tab,
            current_month_key=current_month_key,
            prev_month_key=prev_month_key,
            next_month_key=next_month_key,
            month_title=month_title,
            calendar_weeks=calendar_weeks,
            month_events=month_events,
            notifications=notifications,
            week_days=['Po', 'Ut', 'St', 'Št', 'Pi', 'So', 'Ne'],
            members=members,
            pending_requests=pending_requests,
            is_group_admin=user_is_admin,
        )

    @app.route(f'{APP_BASE_PATH}/skupiny/<int:group_id>/nastavenia', methods=['GET', 'POST'])
    @login_required
    def aplikacia_skupina_nastavenia(group_id: int) -> str:
        group = get_group_by_id(group_id)
        if group is None:
            flash('Skupina sa nenašla.', 'error')
            return redirect(url_for('aplikacia_skupiny'))

        if not is_group_admin(group_id=group_id, user_id=int(g.user['id'])):
            flash('Nastavenia môže meniť len administrátor skupiny.', 'error')
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

    @app.route(f'{APP_BASE_PATH}/hladat')
    @login_required
    def aplikacia_hladat() -> str:
        return render_template(
            'app_main.html',
            active_tab='hladat',
            section_title='Hľadať',
            section_content='Stránka na vyhľadávanie',
            show_search=True,
            search_placeholder='Hľadať...'
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
        if uploaded_file and uploaded_file.filename:
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

        create_post(
            author_id=int(g.user['id']),
            nazov=values['nazov'],
            popis=values['popis'],
            nahladovy_obrazok=image_relative_path,
            subor=file_relative_path,
            subor_povodny_nazov=file_original_name,
        )
        flash('Príspevok bol úspešne nahratý.', 'success')
        return redirect(url_for('aplikacia_domov'))

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

        if request.method == 'POST':
            action_type = request.form.get('action_type', '')

            if action_type == 'rating':
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

            if action_type == 'comment':
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

            else:
                flash('Neplatná akcia.', 'error')
                return redirect(url_for('aplikacia_prispevok_detail', post_id=post_id, post_slug=canonical_post_slug))

        current_user_rating = None if is_owner else get_user_post_rating(post_id=post_id, user_id=int(g.user['id']))
        comments_tree = _build_comment_tree(get_post_comments(post_id))

        post = {
            'id': post_row['id'],
            'nazov': post_row['nazov'],
            'popis': post_row['popis'],
            'autor': f"{post_row['author_meno']} {post_row['author_priezvisko']}",
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
            current_user_rating=current_user_rating,
            comments_tree=comments_tree,
            comment_errors=comment_errors,
            comment_form_values=comment_form_values,
            comments_modal_open=bool(comment_errors),
        )

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
        profile_values = profile_values_from_row(profile)
        values = profile_form_values(g.user, profile)
        profile_photo_path = profile_values['profilova_fotka']

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

            if not errors:
                update_user_name(
                    user_id=int(g.user['id']),
                    meno=values['meno'],
                    priezvisko=values['priezvisko'],
                )
                save_profile(
                    user_id=int(g.user['id']),
                    skola=values['skola'],
                    rocnik_studia=values['rocnik_studia'],
                    popis=values['popis'],
                    profilova_fotka=profile_photo_path,
                )
                flash('Profil bol úspešne uložený.', 'success')
                return redirect(url_for('aplikacia_profil'))

        profile_photo_url = url_for('static', filename=profile_photo_path) if profile_photo_path else None

        return render_template(
            'profil.html',
            active_tab='profil',
            user=g.user,
            profile_values=profile_values,
            profile_photo_url=profile_photo_url,
            values=values,
            errors=errors,
            edit_mode=edit_mode,
            user_posts=user_posts,
            user_groups=user_groups,
        )
