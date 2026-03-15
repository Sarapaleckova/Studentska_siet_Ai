"""Profile service helpers."""

from collections.abc import Mapping
from sqlite3 import Row


def profile_values_from_row(profile: Row | None) -> dict[str, str]:
    if profile is None:
        return {
            'skola': '',
            'rocnik_studia': '',
            'popis': '',
        }

    return {
        'skola': profile['skola'] or '',
        'rocnik_studia': profile['rocnik_studia'] or '',
        'popis': profile['popis'] or '',
    }


def validate_profile(form: Mapping[str, str]) -> tuple[dict[str, str], dict[str, str]]:
    values = {
        'skola': form.get('skola', '').strip(),
        'rocnik_studia': form.get('rocnik_studia', '').strip(),
        'popis': form.get('popis', '').strip(),
    }
    errors: dict[str, str] = {}

    if len(values['skola']) > 120:
        errors['skola'] = 'Názov školy môže mať najviac 120 znakov.'

    if len(values['rocnik_studia']) > 50:
        errors['rocnik_studia'] = 'Ročník štúdia môže mať najviac 50 znakov.'

    if len(values['popis']) > 500:
        errors['popis'] = 'Popis môže mať najviac 500 znakov.'

    return errors, values
