"""Шляхи до теки програми, теки bin з ffmpeg та теки даних користувача."""

import os
import sys

from .version import APP_NAME


def app_dir() -> str:
    """Тека, де лежить сама програма (exe або корінь проєкту при запуску з вихідних кодів)."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def bin_dir() -> str:
    return os.path.join(app_dir(), "bin")


def ffmpeg_exe() -> str:
    return os.path.join(bin_dir(), "ffmpeg.exe")


def ffprobe_exe() -> str:
    return os.path.join(bin_dir(), "ffprobe.exe")


def data_dir() -> str:
    """%APPDATA%\\H264Converter — пресети, черга, налаштування, журнал."""
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    path = os.path.join(base, APP_NAME)
    os.makedirs(path, exist_ok=True)
    return path


def presets_file() -> str:
    return os.path.join(data_dir(), "presets.json")


def queue_file() -> str:
    return os.path.join(data_dir(), "queue.json")


def settings_file() -> str:
    return os.path.join(data_dir(), "settings.json")


def log_file() -> str:
    return os.path.join(data_dir(), "h264converter.log")
