"""Єдине джерело правди для версії та метаданих програми.

build.py генерує з цих значень version.txt для PyInstaller.
"""

__version__ = "1.1.0"
VERSION_DATE = "2026-09-13"

APP_NAME = "FFMpegGuiConverter"
APP_TITLE = "FFMpeg GUI Converter"
AUTHOR = "Pavel Halkovsky"
DESCRIPTION = "Video converter to H.264 - GUI front-end for ffmpeg"
COPYRIGHT = "(c) 2026 Pavel Halkovsky"

# Попередня назва програми — потрібна, щоб перенести налаштування користувача.
LEGACY_APP_NAME = "H264Converter"
