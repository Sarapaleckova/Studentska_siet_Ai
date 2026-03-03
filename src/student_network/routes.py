"""Route definitions for Študentská sieť."""

from flask import Flask, render_template


def register_routes(app: Flask) -> None:
    @app.route('/')
    def index() -> str:
        return render_template('index.html')

    @app.route('/prihlasenie')
    def prihlasenie() -> str:
        return render_template('prihlasenie.html')

    @app.route('/registracia')
    def registracia() -> str:
        return render_template('registracia.html')

    @app.route('/aplikacia')
    @app.route('/aplikacia/domov')
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
    def aplikacia_pridat() -> str:
        return render_template(
            'app_main.html',
            active_tab='pridat',
            section_title='Pridať',
            section_content='Sekcia Pridať',
            show_search=False,
            search_placeholder=''
        )

    @app.route('/aplikacia/profil')
    def aplikacia_profil() -> str:
        return render_template(
            'app_main.html',
            active_tab='profil',
            section_title='Profil',
            section_content='Profil bude doplnený neskôr',
            show_search=False,
            search_placeholder=''
        )
