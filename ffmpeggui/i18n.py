"""Двомовний інтерфейс (українська / англійська).

Ключ перекладу — сам український рядок з коду, тож код лишається читабельним,
а англійський переклад береться зі словника TRANSLATIONS["en"].
Якщо перекладу немає — показується український оригінал.

Рядки зі змінними використовують .format():  t("Файлів: {n}").format(n=3)
"""

from __future__ import annotations

LANGUAGES = [("uk", "Українська"), ("en", "English")]
DEFAULT_LANGUAGE = "uk"

_language = DEFAULT_LANGUAGE

# Заповнюється у translations_en.py, щоб не роздувати цей файл.
from .translations_en import EN  # noqa: E402

TRANSLATIONS = {"en": EN}


def set_language(code: str) -> None:
    global _language
    _language = code if code in {c for c, _ in LANGUAGES} else DEFAULT_LANGUAGE


def get_language() -> str:
    return _language


def language_name(code: str) -> str:
    for c, name in LANGUAGES:
        if c == code:
            return name
    return code


def t(text: str) -> str:
    """Переклад рядка на поточну мову."""
    if _language == DEFAULT_LANGUAGE:
        return text
    return TRANSLATIONS.get(_language, {}).get(text, text)
