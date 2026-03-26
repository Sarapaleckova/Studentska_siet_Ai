"""Profile service helpers."""

from collections.abc import Mapping
from sqlite3 import Row


def profile_values_from_row(profile: Row | None) -> dict[str, str]:
    if profile is None:
        return {
            'skola': '',
            'rocnik_studia': '',
            'popis': '',
            'profilova_fotka': '',
        }

    return {
        'skola': profile['skola'] or '',
        'rocnik_studia': profile['rocnik_studia'] or '',
        'popis': profile['popis'] or '',
        'profilova_fotka': profile['profilova_fotka'] or '',
    }


def profile_form_values(user: Mapping[str, str], profile: Row | None) -> dict[str, str]:
    values = profile_values_from_row(profile)
    values['meno'] = (user['meno'] if 'meno' in user else '').strip()
    values['priezvisko'] = (user['priezvisko'] if 'priezvisko' in user else '').strip()
    return values


def validate_profile(form: Mapping[str, str], current_user: Mapping[str, str] | None = None) -> tuple[dict[str, str], dict[str, str]]:
    original_meno = str(current_user['meno']).strip() if current_user is not None and 'meno' in current_user else ''
    original_priezvisko = str(current_user['priezvisko']).strip() if current_user is not None and 'priezvisko' in current_user else ''

    values = {
        'meno': form.get('meno', '').strip(),
        'priezvisko': form.get('priezvisko', '').strip(),
        'skola': form.get('skola', '').strip(),
        'rocnik_studia': form.get('rocnik_studia', '').strip(),
        'popis': form.get('popis', '').strip(),
    }
    errors: dict[str, str] = {}

    if not values['meno']:
        values['meno'] = original_meno

    if not values['priezvisko']:
        values['priezvisko'] = original_priezvisko

    if len(values['meno']) > 80:
        errors['meno'] = 'Meno môže mať najviac 80 znakov.'

    if len(values['priezvisko']) > 80:
        errors['priezvisko'] = 'Priezvisko môže mať najviac 80 znakov.'

    if len(values['skola']) > 120:
        errors['skola'] = 'Názov školy môže mať najviac 120 znakov.'

    if len(values['rocnik_studia']) > 50:
        errors['rocnik_studia'] = 'Ročník štúdia môže mať najviac 50 znakov.'

    if len(values['popis']) > 500:
        errors['popis'] = 'Popis môže mať najviac 500 znakov.'

    return errors, values
