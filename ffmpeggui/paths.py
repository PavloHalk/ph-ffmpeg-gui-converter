"""Шляхи до теки програми, теки bin з ffmpeg та теки даних користувача."""

import os
import shutil
import sys

from .version import APP_NAME, LEGACY_APP_NAME

_data_dir: str | None = None
_migrated: list[str] = []


def app_dir() -> str:
    """Тека, де лежить сама програма (exe або корінь проєкту при запуску з вихідних кодів)."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def resource_path(*parts: str) -> str:
    """Шлях до файлу ресурсів (іконка тощо) — працює і в зібраному exe."""
    base = getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, *parts)


def icon_file() -> str:
    return resource_path("assets", "app.ico")


def bin_dir() -> str:
    return os.path.join(app_dir(), "bin")


def ffmpeg_exe() -> str:
    return os.path.join(bin_dir(), "ffmpeg.exe")


def ffprobe_exe() -> str:
    return os.path.join(bin_dir(), "ffprobe.exe")


def data_dir() -> str:
    """%APPDATA%\FFMpegGuiConverter — пресети, черга, налаштування, журнал."""
    global _data_dir
    if _data_dir:
        return _data_dir
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    path = os.path.join(base, APP_NAME)
    is_new = not os.path.isdir(path)
    os.makedirs(path, exist_ok=True)
    if is_new:
        _migrate_from_legacy(os.path.join(base, LEGACY_APP_NAME), path)
    _data_dir = path
    return path


def _migrate_from_legacy(old_dir: str, new_dir: str) -> None:
    """Переносить пресети, чергу й налаштування зі старої теки (H264Converter)."""
    if not os.path.isdir(old_dir):
        return
    for name in ("presets.json", "queue.json", "settings.json"):
        src = os.path.join(old_dir, name)
        dst = os.path.join(new_dir, name)
        if os.path.isfile(src) and not os.path.exists(dst):
            try:
                shutil.copy2(src, dst)
                _migrated.append(name)
            except OSError:
                pass


def migrated_files() -> list[str]:
    """Файли, перенесені зі старої теки при першому запуску (для журналу)."""
    return list(_migrated)


def presets_file() -> str:
    return os.path.join(data_dir(), "presets.json")


def queue_file() -> str:
    return os.path.join(data_dir(), "queue.json")


def settings_file() -> str:
    return os.path.join(data_dir(), "settings.json")


def log_file() -> str:
    return os.path.join(data_dir(), "ffmpeggui.log")
