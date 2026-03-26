"""Route definitions for Študentská sieť."""

from functools import wraps
from pathlib import Path
from uuid import uuid4

from flask import Flask, flash, g, redirect, render_template, request, session, url_for
from werkzeug.utils import secure_filename

from student_network.repositories.profiles import get_profile_by_user_id, save_profile
from student_network.repositories.users import get_user_by_id, update_user_name
from student_network.services.auth_service import register_user, validate_login
from student_network.services.profile_service import profile_form_values, profile_values_from_row, validate_profile

ALLOWED_PROFILE_PHOTO_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp', '.gif'}


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
    def index() -> str:
        return render_template('index.html')

    @app.route('/prihlasenie', methods=['GET', 'POST'])
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

    @app.route('/registracia', methods=['GET', 'POST'])
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

    @app.route('/odhlasenie')
    def odhlasenie() -> str:
        session.clear()
        return redirect(url_for('index'))

    @app.route('/aplikacia')
    @app.route('/aplikacia/domov')
    @login_required
    def aplikacia_domov() -> str:
        return render_template(
            'app_main.html',
            active_tab='domov',
            section_title='Domov',
            section_content='Príspevky',
            show_search=True,
            search_placeholder='Hľadať príspevky...'
        )

    @app.route('/aplikacia/skupiny')
    @login_required
    def aplikacia_skupiny() -> str:
        return render_template(
            'app_main.html',
            active_tab='skupiny',
            section_title='Skupiny',
            section_content='Stránka pre skupiny',
            show_search=True,
            search_placeholder='Hľadať skupiny...'
        )

    @app.route('/aplikacia/hladat')
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

    @app.route('/aplikacia/pridat')
    @login_required
    def aplikacia_pridat() -> str:
        return render_template(
            'app_main.html',
            active_tab='pridat',
            section_title='Pridať',
            section_content='Sekcia Pridať',
            show_search=False,
            search_placeholder=''
        )

    @app.route('/aplikacia/profil', methods=['GET', 'POST'])
    @login_required
    def aplikacia_profil() -> str:
        errors: dict[str, str] = {}
        edit_mode = request.args.get('edit') == '1'
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
        )
