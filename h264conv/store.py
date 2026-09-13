"""Збереження та завантаження черги, пресетів і налаштувань (json у %APPDATA%)."""

from __future__ import annotations

import json
import os

from . import paths
from .models import (
    FILE_RUNNING,
    FILE_STOPPED,
    TASK_ACTIVE,
    TASK_STOPPED,
    ConvSettings,
    Task,
)

DEFAULT_PRESET_NAME = "Стандарт (CRF 17, slow — як у скрипті)"


def _read_json(path: str, default):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        return default
    except (OSError, ValueError):
        # Пошкоджений файл — зберігаємо копію, щоб не втратити дані остаточно.
        try:
            os.replace(path, path + ".bad")
        except OSError:
            pass
        return default


def _write_json(path: str, data) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


# ---------------------------------------------------------------- черга

def load_tasks() -> list[Task]:
    data = _read_json(paths.queue_file(), {})
    tasks = [Task.from_dict(d) for d in data.get("tasks", [])]
    # Те, що конвертувалось на момент закриття, — не завершене і само не продовжується.
    for t in tasks:
        if t.status in TASK_ACTIVE:
            t.status = TASK_STOPPED
        for f in t.files:
            if f.status == FILE_RUNNING:
                f.status = FILE_STOPPED
                f.progress = 0.0
    return tasks


def save_tasks(tasks: list[Task]) -> None:
    _write_json(paths.queue_file(), {"tasks": [t.to_dict() for t in tasks]})


# ---------------------------------------------------------------- налаштування

DEFAULT_SETTINGS = {
    "max_parallel": 1,
    "geometry": "",
    "last_preset": DEFAULT_PRESET_NAME,
    "last_dir": "",
    "last_out_dir": "",
    "default_prefix": "h264_",
    "recursive_scan": False,
}


def load_settings() -> dict:
    data = _read_json(paths.settings_file(), {})
    result = dict(DEFAULT_SETTINGS)
    if isinstance(data, dict):
        result.update(data)
    return result


def save_settings(settings: dict) -> None:
    _write_json(paths.settings_file(), settings)


# ---------------------------------------------------------------- пресети

class PresetStore:
    def __init__(self):
        self.presets: dict[str, dict] = {}
        self.load()

    def load(self) -> None:
        data = _read_json(paths.presets_file(), None)
        if not isinstance(data, dict) or not data.get("presets"):
            self.presets = {DEFAULT_PRESET_NAME: ConvSettings().to_dict()}
            self.save()
        else:
            self.presets = dict(data["presets"])

    def save(self) -> None:
        _write_json(paths.presets_file(), {"presets": self.presets})

    def names(self) -> list[str]:
        return list(self.presets.keys())

    def get(self, name: str) -> ConvSettings | None:
        if name not in self.presets:
            return None
        return ConvSettings.from_dict(self.presets[name])

    def put(self, name: str, settings: ConvSettings) -> None:
        self.presets[name] = settings.to_dict()
        self.save()

    def delete(self, name: str) -> None:
        self.presets.pop(name, None)
        self.save()
