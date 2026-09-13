"""Витрачений час, оцінка часу до завершення та швидкість обробки."""

from __future__ import annotations

import time

from .models import FILE_DONE, FILE_PENDING, FILE_RUNNING, FileItem, Task


def format_duration(seconds: float | None) -> str:
    """Секунди → «3:07» або «1:02:33». Порожній рядок, якщо значення невідоме."""
    if seconds is None or seconds < 0 or seconds != seconds or seconds == float("inf"):
        return ""
    total = int(round(seconds))
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def file_elapsed(f: FileItem, now: float | None = None) -> float:
    if not f.started_at:
        return 0.0
    if f.finished_at:
        return max(0.0, f.finished_at - f.started_at)
    if f.status == FILE_RUNNING:
        return max(0.0, (now or time.time()) - f.started_at)
    return 0.0


def file_eta(f: FileItem, now: float | None = None) -> float | None:
    """Скільки ще лишилось конвертувати цей файл (секунди)."""
    if f.status != FILE_RUNNING:
        return None
    if f.duration > 0 and f.speed > 0:
        return max(0.0, f.duration * (1.0 - f.progress) / f.speed)
    elapsed = file_elapsed(f, now)
    if f.progress > 0.01 and elapsed > 1:
        return max(0.0, elapsed * (1.0 - f.progress) / f.progress)
    return None


def task_elapsed(task: Task, now: float | None = None) -> float:
    if not task.started_at:
        return 0.0
    if task.finished_at:
        return max(0.0, task.finished_at - task.started_at)
    if task.is_active:
        return max(0.0, (now or time.time()) - task.started_at)
    return 0.0


def task_eta(task: Task, now: float | None = None, parallel: int = 1) -> float | None:
    """Оцінка часу до завершення всього завдання.

    Основний спосіб — за тривалістю відео, що лишилось, і поточною швидкістю
    ffmpeg. Якщо тривалості ще невідомі, береться середній час на файл.
    """
    now = now or time.time()
    running = [f for f in task.files if f.status == FILE_RUNNING]
    pending = [f for f in task.files if f.status == FILE_PENDING]
    if not running and not pending:
        return None

    speed = sum(f.speed for f in running if f.speed > 0)
    durations_known = all(f.duration > 0 for f in running + pending)
    if speed > 0 and durations_known:
        remaining = sum(f.duration * max(0.0, 1.0 - f.progress) for f in running)
        remaining += sum(f.duration for f in pending)
        return remaining / speed

    finished = [f for f in task.files
                if f.status == FILE_DONE and f.started_at and f.finished_at]
    if finished:
        average = sum(file_elapsed(f) for f in finished) / len(finished)
        remaining_files = len(pending) + sum(max(0.0, 1.0 - f.progress) for f in running)
        workers = max(1, min(parallel, len(running) or 1))
        return remaining_files * average / workers

    etas = [e for e in (file_eta(f, now) for f in running) if e is not None]
    if etas and not pending:
        return max(etas)
    return None


def queue_eta(tasks: list[Task], now: float | None = None, parallel: int = 1) -> float | None:
    """Сума оцінок по всіх завданнях, які ще мають необроблені файли."""
    now = now or time.time()
    values = [task_eta(t, now, parallel) for t in tasks
              if any(f.status in (FILE_PENDING, FILE_RUNNING) for f in t.files)]
    known = [v for v in values if v is not None]
    return sum(known) if known else None
