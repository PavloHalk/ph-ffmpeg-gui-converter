"""Моделі даних: налаштування конвертації, файли, завдання."""

from __future__ import annotations

import os
import uuid
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

# Пресети швидкості x264 з коротким поясненням.
X264_PRESETS = [
    ("ultrafast", "найшвидше кодування, найбільший файл"),
    ("superfast", "дуже швидко, файл великий"),
    ("veryfast", "швидко"),
    ("faster", "швидше за стандарт"),
    ("fast", "трохи швидше за стандарт"),
    ("medium", "стандарт ffmpeg — баланс"),
    ("slow", "повільніше, менший файл (як у старому скрипті)"),
    ("slower", "ще повільніше, ще менший файл"),
    ("veryslow", "найповільніше, найменший файл"),
]
X264_PRESET_NAMES = [p for p, _ in X264_PRESETS]

AUDIO_CODECS = [
    ("aac", "AAC (рекомендовано)"),
    ("mp3", "MP3"),
    ("copy", "Копіювати без перекодування"),
    ("none", "Без звуку"),
]

PIX_FMTS = [
    ("yuv420p", "yuv420p (рекомендовано)"),
    ("yuv422p", "yuv422p"),
    ("yuv444p", "yuv444p"),
    ("", "Як у вихідного файлу"),
]

TUNES = [
    ("", "Немає"),
    ("film", "film — зйомка з реального життя"),
    ("animation", "animation — мультиплікація"),
    ("grain", "grain — зберегти плівкове зерно"),
    ("stillimage", "stillimage — статичні кадри"),
    ("fastdecode", "fastdecode — легке декодування"),
]

CONTAINERS = ["mp4", "mov", "mkv"]

# Розширення, за якими скануються теки (окремі файли можна додавати будь-які).
VIDEO_EXTENSIONS = {
    ".mp4", ".mov", ".mkv", ".avi", ".mts", ".m2ts", ".ts", ".m4v", ".wmv",
    ".webm", ".flv", ".3gp", ".mpg", ".mpeg", ".vob", ".mxf", ".dv", ".hevc",
    ".h265", ".265", ".insv",
}


@dataclass
class ConvSettings:
    crf: int = 17
    preset: str = "slow"
    res_mode: str = "source"      # source | custom
    res_master: str = "width"     # width | height — яке поле головне
    width: int = 1920
    height: int = 1080
    fps_mode: str = "source"      # source | custom
    fps: str = "30"
    audio_codec: str = "aac"      # aac | mp3 | copy | none
    audio_bitrate_mode: str = "custom"  # source | custom
    audio_bitrate: int = 320      # кбіт/с
    keyint: int = 30              # 0 = не задавати
    min_keyint: int = 1
    pix_fmt: str = "yuv420p"      # "" = як у вихідного файлу
    tune: str = ""
    container: str = "mp4"
    faststart: bool = False
    extra_args: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    def copy(self) -> "ConvSettings":
        return ConvSettings.from_dict(self.to_dict())

    @classmethod
    def from_dict(cls, data: dict | None) -> "ConvSettings":
        obj = cls()
        for f in fields(cls):
            if not data or f.name not in data:
                continue
            default = getattr(obj, f.name)
            value = data[f.name]
            try:
                value = bool(value) if isinstance(default, bool) else type(default)(value)
            except (TypeError, ValueError):
                continue
            setattr(obj, f.name, value)
        return obj


FILE_PENDING = "pending"
FILE_RUNNING = "running"
FILE_DONE = "done"
FILE_ERROR = "error"
FILE_STOPPED = "stopped"

FILE_STATUS_LABELS = {
    FILE_PENDING: "Очікує",
    FILE_RUNNING: "Конвертується",
    FILE_DONE: "Готово",
    FILE_ERROR: "Помилка",
    FILE_STOPPED: "Зупинено",
}

TASK_IDLE = "idle"
TASK_QUEUED = "queued"
TASK_RUNNING = "running"
TASK_DONE = "done"
TASK_ERROR = "error"
TASK_PARTIAL = "partial"
TASK_STOPPED = "stopped"

TASK_ACTIVE = (TASK_QUEUED, TASK_RUNNING)

TASK_STATUS_LABELS = {
    TASK_IDLE: "Не почато",
    TASK_QUEUED: "В черзі",
    TASK_RUNNING: "Конвертується",
    TASK_DONE: "Готово",
    TASK_ERROR: "З помилками",
    TASK_PARTIAL: "Готово, є помилки",
    TASK_STOPPED: "Не завершено",
}


def _new_id() -> str:
    return uuid.uuid4().hex


@dataclass
class FileItem:
    src: str
    id: str = field(default_factory=_new_id)
    status: str = FILE_PENDING
    progress: float = 0.0          # 0..1
    out_path: str = ""
    message: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "FileItem":
        return cls(
            src=d.get("src", ""),
            id=d.get("id") or _new_id(),
            status=d.get("status", FILE_PENDING) if d.get("status") in FILE_STATUS_LABELS else FILE_PENDING,
            progress=float(d.get("progress", 0.0) or 0.0),
            out_path=d.get("out_path", ""),
            message=d.get("message", ""),
        )


@dataclass
class Task:
    name: str = "Завдання"
    files: list[FileItem] = field(default_factory=list)
    out_dir: str = ""
    prefix: str = "h264_"
    settings: ConvSettings = field(default_factory=ConvSettings)
    id: str = field(default_factory=_new_id)
    status: str = TASK_IDLE

    @property
    def is_active(self) -> bool:
        return self.status in TASK_ACTIVE

    def progress(self) -> float:
        """Частка оброблених файлів (з урахуванням прогресу поточних)."""
        if not self.files:
            return 0.0
        total = 0.0
        for f in self.files:
            if f.status in (FILE_DONE, FILE_ERROR):
                total += 1.0
            elif f.status == FILE_RUNNING:
                total += f.progress
        return total / len(self.files)

    def count(self, status: str) -> int:
        return sum(1 for f in self.files if f.status == status)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "status": self.status,
            "out_dir": self.out_dir,
            "prefix": self.prefix,
            "settings": self.settings.to_dict(),
            "files": [f.to_dict() for f in self.files],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Task":
        return cls(
            id=d.get("id") or _new_id(),
            name=d.get("name", "Завдання"),
            status=d.get("status", TASK_IDLE) if d.get("status") in TASK_STATUS_LABELS else TASK_IDLE,
            out_dir=d.get("out_dir", ""),
            prefix=d.get("prefix", ""),
            settings=ConvSettings.from_dict(d.get("settings")),
            files=[FileItem.from_dict(x) for x in d.get("files", [])],
        )


def _norm(path: str) -> str:
    return os.path.normcase(os.path.abspath(path))


def assign_output_paths(task: Task) -> None:
    """Розраховує імена вихідних файлів.

    Ім'я = префікс + ім'я вихідного файлу + розширення контейнера. Якщо ім'я вже
    зайняте іншим файлом цього завдання (або збігається з будь-яким вихідним
    файлом), додається суфікс _000, _001, … Файли, які вже сконвертовано,
    зберігають своє ім'я.
    """
    ext = "." + (task.settings.container or "mp4")
    forbidden = {_norm(f.src) for f in task.files}
    used: set[str] = set()
    for f in task.files:
        if f.status == FILE_DONE and f.out_path:
            used.add(_norm(f.out_path))
    for f in task.files:
        if f.status == FILE_DONE and f.out_path:
            continue
        base = task.prefix + Path(f.src).stem
        candidate = os.path.join(task.out_dir, base + ext)
        n = 0
        while _norm(candidate) in used or _norm(candidate) in forbidden:
            candidate = os.path.join(task.out_dir, f"{base}_{n:03d}{ext}")
            n += 1
        used.add(_norm(candidate))
        f.out_path = candidate
