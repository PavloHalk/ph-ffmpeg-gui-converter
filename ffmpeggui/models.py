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
    ("slow", "повільніше, менший файл"),
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


def _number(d: dict, key: str) -> float:
    try:
        return float(d.get(key, 0.0) or 0.0)
    except (TypeError, ValueError):
        return 0.0


@dataclass
class FileItem:
    src: str
    id: str = field(default_factory=_new_id)
    status: str = FILE_PENDING
    progress: float = 0.0          # 0..1
    out_path: str = ""
    message: str = ""
    duration: float = 0.0          # тривалість відео в секундах (з ffprobe)
    started_at: float = 0.0        # коли почалась конвертація (time.time())
    finished_at: float = 0.0       # коли завершилась
    fps: float = 0.0               # кадрів за секунду обробки
    speed: float = 0.0             # у скільки разів швидше за реальний час

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "FileItem":
        return cls(
            src=d.get("src", ""),
            id=d.get("id") or _new_id(),
            status=d.get("status", FILE_PENDING) if d.get("status") in FILE_STATUS_LABELS else FILE_PENDING,
            progress=_number(d, "progress"),
            out_path=d.get("out_path", ""),
            message=d.get("message", ""),
            duration=_number(d, "duration"),
            started_at=_number(d, "started_at"),
            finished_at=_number(d, "finished_at"),
            fps=_number(d, "fps"),
            speed=_number(d, "speed"),
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
    started_at: float = 0.0
    finished_at: float = 0.0
    preset_name: str = ""   # з якого пресету взяті налаштування (для позначки «(змінено)»)

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
            "preset_name": self.preset_name,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
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
            preset_name=d.get("preset_name", ""),
            started_at=_number(d, "started_at"),
            finished_at=_number(d, "finished_at"),
            settings=ConvSettings.from_dict(d.get("settings")),
            files=[FileItem.from_dict(x) for x in d.get("files", [])],
        )


def effective_settings(s: ConvSettings) -> dict:
    """Лише ті налаштування, які реально впливають на результат.

    Потрібно, щоб порівняння з пресетом не спрацьовувало через значення полів,
    які зараз вимкнені (наприклад ширину, коли роздільність лишається як є).
    """
    d = s.to_dict()
    if s.res_mode != "custom":
        for key in ("width", "height", "res_master"):
            d.pop(key, None)
    elif s.res_master == "width":
        d.pop("height", None)
    else:
        d.pop("width", None)
    if s.fps_mode != "custom":
        d.pop("fps", None)
    if s.audio_codec not in ("aac", "mp3"):
        d.pop("audio_bitrate", None)
        d.pop("audio_bitrate_mode", None)
    elif s.audio_bitrate_mode != "custom":
        d.pop("audio_bitrate", None)
    if s.keyint == 0:
        d.pop("min_keyint", None)
    if not s.faststart or s.container not in ("mp4", "mov"):
        d.pop("faststart", None)
    return d


@dataclass
class QueueStats:
    """Стан усієї черги — незалежно від того, що зараз запущено."""

    total: int = 0          # усього файлів у всіх завданнях
    done: int = 0           # успішно сконвертовано
    errors: int = 0         # завершились помилкою
    running: int = 0        # конвертуються просто зараз
    fraction: float = 0.0   # 0..1 — частка опрацьованого

    @property
    def processed(self) -> int:
        return self.done + self.errors

    @property
    def percent(self) -> float:
        return self.fraction * 100.0


def queue_stats(tasks: list[Task]) -> QueueStats:
    """Прогрес усієї черги: враховуються всі завдання списку, а не лише запущені."""
    stats = QueueStats()
    partial = 0.0
    for task in tasks:
        for f in task.files:
            stats.total += 1
            if f.status == FILE_DONE:
                stats.done += 1
            elif f.status == FILE_ERROR:
                stats.errors += 1
            elif f.status == FILE_RUNNING:
                stats.running += 1
                partial += f.progress
    if stats.total:
        stats.fraction = (stats.processed + partial) / stats.total
    return stats


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
