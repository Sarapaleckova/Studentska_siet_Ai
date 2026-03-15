"""Authentication helpers."""

from collections.abc import Mapping
import re

from werkzeug.security import check_password_hash, generate_password_hash

from student_network.repositories.users import create_user, get_user_by_email

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def validate_registration(form: Mapping[str, str]) -> tuple[dict[str, str], dict[str, str]]:
    data = {
        'meno': form.get('meno', '').strip(),
        'priezvisko': form.get('priezvisko', '').strip(),
        'email': form.get('email', '').strip(),
    }
    heslo = form.get('heslo', '')
    znova_heslo = form.get('znova_heslo', '')
    errors: dict[str, str] = {}

    if not data['meno']:
        errors['meno'] = 'Meno je povinné.'

    if not data['priezvisko']:
        errors['priezvisko'] = 'Priezvisko je povinné.'

    if not data['email']:
        errors['email'] = 'E-mail je povinný.'
    elif not EMAIL_PATTERN.match(data['email']):
        errors['email'] = 'Mail je v nesprávnom tvare.'
    elif get_user_by_email(data['email']) is not None:
        errors['email'] = 'Používateľ s týmto e-mailom už existuje.'

    if not heslo:
        errors['heslo'] = 'Heslo je povinné.'

    if not znova_heslo:
        errors['znova_heslo'] = 'Potvrdenie hesla je povinné.'

    if heslo and znova_heslo and heslo != znova_heslo:
        errors['znova_heslo'] = 'Heslá nie sú rovnaké.'

    return errors, data


def register_user(form: Mapping[str, str]) -> tuple[dict[str, str], dict[str, str]]:
    errors, data = validate_registration(form)
    if errors:
        return errors, data

    create_user(
        meno=data['meno'],
        priezvisko=data['priezvisko'],
        email=data['email'],
        heslo=generate_password_hash(form.get('heslo', '')),
    )
    return {}, data


def validate_login(form: Mapping[str, str]) -> tuple[dict[str, str], dict[str, str], int | None]:
    data = {
        'email': form.get('email', '').strip(),
    }
    heslo = form.get('heslo', '')
    errors: dict[str, str] = {}

    if not data['email']:
        errors['email'] = 'E-mail je povinný.'

    if not heslo:
        errors['heslo'] = 'Heslo je povinné.'

    if errors:
        return errors, data, None

    user = get_user_by_email(data['email'])
    if user is None or not check_password_hash(user['heslo'], heslo):
        errors['general'] = 'Nesprávny e-mail alebo heslo.'
        return errors, data, None

    return {}, data, int(user['id'])
