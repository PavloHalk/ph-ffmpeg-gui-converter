"""Витрачений час, оцінка часу до завершення та швидкість обробки."""

from __future__ import annotations

import time

from .models import FILE_DONE, FILE_ERROR, FILE_PENDING, FILE_RUNNING, FileItem, Task


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


def _weights(files: list[FileItem]) -> list[float]:
    """Вага файлу для загального прогресу — тривалість відео.

    Файлам, чия тривалість ще невідома (або не визначилась), даємо середню
    тривалість решти; якщо невідома жодна — усі файли важать однаково.
    """
    known = [f.duration for f in files if f.duration > 0]
    average = sum(known) / len(known) if known else 1.0
    return [f.duration if f.duration > 0 else average for f in files]


def queue_progress(tasks: list[Task]) -> float:
    """Частка виконаної роботи в усьому списку завдань (0..1).

    Рахується за тривалістю відео, а не за кількістю файлів: інакше відсоток
    повзе разом із поточним файлом і стрибає на коротких. Враховуються всі
    завдання списку, незалежно від того, що зараз запущено.
    """
    files = [f for task in tasks for f in task.files]
    if not files:
        return 0.0
    total = done = 0.0
    for f, weight in zip(files, _weights(files)):
        total += weight
        if f.status in (FILE_DONE, FILE_ERROR):
            done += weight
        elif f.status == FILE_RUNNING:
            done += weight * f.progress
    return done / total if total else 0.0


def queue_eta(tasks: list[Task], now: float | None = None, parallel: int = 1) -> float | None:
    """Скільки ще триватиме вся черга — усі завдання «В черзі» та «Конвертується».

    Відео, що лишилось у всіх цих завданнях, ділимо на сумарну поточну швидкість
    процесів ffmpeg. Завдання, які ще чекають своєї черги, теж враховуються.
    """
    now = now or time.time()
    active = [t for t in tasks if t.is_active]
    running = [f for t in active for f in t.files if f.status == FILE_RUNNING]
    pending = [f for t in active for f in t.files if f.status == FILE_PENDING]
    if not running and not pending:
        return None

    speed = sum(f.speed for f in running if f.speed > 0)
    if speed > 0:
        files = running + pending
        weights = _weights(files)
        remaining = sum(w * max(0.0, 1.0 - f.progress) if f.status == FILE_RUNNING else w
                        for f, w in zip(files, weights))
        return remaining / speed

    # Швидкість ще невідома (ffmpeg тільки стартував) — за середнім часом на файл.
    finished = [f for t in tasks for f in t.files
                if f.status == FILE_DONE and f.started_at and f.finished_at]
    if finished:
        average = sum(file_elapsed(f) for f in finished) / len(finished)
        remaining_files = len(pending) + sum(max(0.0, 1.0 - f.progress) for f in running)
        workers = max(1, min(parallel, len(running) or 1))
        return remaining_files * average / workers
    return None
