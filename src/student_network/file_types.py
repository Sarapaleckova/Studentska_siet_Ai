"""Centralized supported file type configuration."""

from collections.abc import Iterable

POST_IMAGE_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.webp', '.gif')

POST_FILE_EXTENSION_GROUPS: dict[str, tuple[str, ...]] = {
    'Dokumenty': ('.pdf', '.doc', '.docx', '.txt', '.rtf', '.odt'),
    'Tabuľky': ('.xls', '.xlsx', '.csv', '.ods'),
    'Prezentácie': ('.ppt', '.pptx', '.odp'),
    'Archívy': ('.zip', '.rar', '.7z'),
    'Obrázky': ('.jpg', '.jpeg', '.png', '.webp'),
}


def _flatten_extensions(items: Iterable[tuple[str, ...]]) -> set[str]:
    return {
        extension.lower()
        for group in items
        for extension in group
    }


ALLOWED_POST_IMAGE_EXTENSIONS = set(POST_IMAGE_EXTENSIONS)
ALLOWED_POST_FILE_EXTENSIONS = _flatten_extensions(POST_FILE_EXTENSION_GROUPS.values())
POST_FILE_ACCEPT_VALUE = ','.join(sorted(ALLOWED_POST_FILE_EXTENSIONS))


def post_file_types_description() -> str:
    parts: list[str] = []
    for label, extensions in POST_FILE_EXTENSION_GROUPS.items():
        parts.append(f"{label}: {', '.join(extensions)}")
    return ' | '.join(parts)
