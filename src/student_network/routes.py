"""Route definitions for Študentská sieť."""

from functools import wraps
from pathlib import Path
import re
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
from student_network.repositories.groups import (
    get_group_by_id,
    get_group_membership,
    get_groups_for_user,
    join_public_group,
    request_private_group_membership,
)
from student_network.repositories.profiles import get_profile_by_user_id, save_profile
from student_network.repositories.posts import create_post, get_all_posts, get_post_by_id, get_posts_by_author_id
from student_network.repositories.ratings import get_user_post_rating, upsert_post_rating
from student_network.repositories.users import get_user_by_id, update_user_name
from student_network.services.auth_service import register_user, validate_login
from student_network.services.profile_service import profile_form_values, profile_values_from_row, validate_profile

ALLOWED_PROFILE_PHOTO_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp', '.gif'}
APP_BASE_PATH = '/studentska-siet'


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
            'created_at': row['created_at'].replace('T', ' '),
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
                'obrazok_url': row['obrazok_url'],
                'je_sukromna': bool(row['je_sukromna']),
                'member_count': int(row['member_count'] or 0),
            }
            for row in group_rows
            if row['membership_status'] == 'member'
        ]

        non_member_groups = [
            {
                'id': row['id'],
                'nazov': row['nazov'],
                'popis': row['popis'],
                'obrazok_url': row['obrazok_url'],
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
            'obrazok_url': group['obrazok_url'],
            'je_sukromna': bool(group['je_sukromna']),
            'member_count': int(group['member_count'] or 0),
        }

        return render_template(
            'skupina_detail.html',
            active_tab='skupiny',
            group=group_view,
        )

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
            'datum_vytvorenia': post_row['datum_vytvorenia'].replace('T', ' '),
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
        user_posts = [
            {
                'id': row['id'],
                'nazov': row['nazov'],
                'post_slug': _slugify(row['nazov']),
                'datum_vytvorenia': row['datum_vytvorenia'].replace('T', ' '),
            }
            for row in user_posts_rows
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
        )
