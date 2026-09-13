"""Черга конвертації.

Стан моделі змінюється лише в головному (Tk) потоці. Кожен файл конвертується
в окремому робочому потоці, який надсилає події в queue.Queue; головний потік
забирає їх через poll().
"""

from __future__ import annotations

import os
import queue
import threading
from typing import Callable

from . import ffmpeg_tools
from .models import (
    FILE_DONE,
    FILE_ERROR,
    FILE_PENDING,
    FILE_RUNNING,
    FILE_STOPPED,
    TASK_DONE,
    TASK_ERROR,
    TASK_PARTIAL,
    TASK_QUEUED,
    TASK_RUNNING,
    TASK_STOPPED,
    ConvSettings,
    Task,
    assign_output_paths,
)


class Job:
    """Конвертація одного файлу в окремому потоці."""

    def __init__(self, task_id: str, file_id: str, src: str, dst: str,
                 settings: ConvSettings, events: queue.Queue):
        self.task_id = task_id
        self.file_id = file_id
        self.src = src
        self.dst = dst
        self.settings = settings
        self._events = events
        self._cancel = threading.Event()
        self._lock = threading.Lock()
        self._proc = None

    def start(self) -> None:
        threading.Thread(target=self._run, daemon=True).start()

    def kill(self) -> None:
        with self._lock:
            self._cancel.set()
            proc = self._proc
        if proc is not None and proc.poll() is None:
            try:
                proc.kill()
            except OSError:
                pass

    def wait_and_cleanup(self, timeout: float) -> None:
        proc = self._proc
        if proc is None:
            return
        try:
            proc.wait(timeout=timeout)
        except Exception:  # noqa: BLE001
            pass
        self._remove_partial()

    def _post(self, kind: str, data=None) -> None:
        self._events.put((kind, self, data))

    def _remove_partial(self) -> None:
        try:
            if os.path.isfile(self.dst):
                os.remove(self.dst)
        except OSError:
            pass

    def _run(self) -> None:
        started = False
        try:
            info = ffmpeg_tools.probe(self.src)
            if not info.has_video:
                raise RuntimeError("У файлі не знайдено відеопотоку.")
            os.makedirs(os.path.dirname(self.dst) or ".", exist_ok=True)
            cmd = ffmpeg_tools.build_command(self.src, self.dst, self.settings, info)
            with self._lock:
                if self._cancel.is_set():
                    return
                self._proc = ffmpeg_tools.start_process(cmd)
                started = True
            rc, err = ffmpeg_tools.watch_process(
                self._proc, info.duration, lambda p: self._post("progress", p))
            if self._cancel.is_set():
                self._remove_partial()
                return
            if rc == 0:
                self._post("done")
            else:
                self._remove_partial()
                self._post("error", err or f"ffmpeg завершився з кодом {rc}")
        except Exception as exc:  # noqa: BLE001 — будь-яка помилка = помилка файлу
            if started:
                self._remove_partial()
            if not self._cancel.is_set():
                self._post("error", str(exc) or exc.__class__.__name__)


class Engine:
    def __init__(self, tasks: list[Task], max_parallel: Callable[[], int],
                 on_change: Callable[[Task, bool], None],
                 log: Callable[[str, str], None]):
        self.tasks = tasks  # спільний з GUI список (змінюється лише на місці)
        self.max_parallel = max_parallel
        self.on_change = on_change
        self.log = log
        self.events: queue.Queue = queue.Queue()
        self.jobs: dict[str, Job] = {}
        self._was_busy = False

    # ------------------------------------------------------------ стан

    def is_busy(self) -> bool:
        return any(t.is_active for t in self.tasks)

    def overall_progress(self) -> float | None:
        active = [t for t in self.tasks if t.is_active]
        if not active:
            return None
        total = sum(len(t.files) for t in active)
        return sum(t.progress() * len(t.files) for t in active) / total if total else 0.0

    def _find(self, task_id: str, file_id: str):
        for t in self.tasks:
            if t.id == task_id:
                for f in t.files:
                    if f.id == file_id:
                        return t, f
                return t, None
        return None, None

    # ------------------------------------------------------------ керування

    def start_task(self, task: Task, schedule: bool = True) -> bool:
        if task.is_active or not task.files:
            return False
        if all(f.status == FILE_DONE for f in task.files):
            targets = task.files          # все готово — конвертуємо заново
        else:
            targets = [f for f in task.files if f.status != FILE_DONE]
        for f in targets:
            f.status = FILE_PENDING
            f.progress = 0.0
            f.message = ""
        assign_output_paths(task)
        task.status = TASK_QUEUED
        self.log(f"Завдання «{task.name}» додано в чергу ({len(targets)} файл.).", "info")
        self.on_change(task, False)
        if schedule:
            self.schedule()
        return True

    def start_all(self) -> int:
        started = 0
        for t in self.tasks:
            if t.status != TASK_DONE and self.start_task(t, schedule=False):
                started += 1
        self.schedule()
        return started

    def stop_task(self, task: Task, schedule: bool = True) -> None:
        for fid, job in list(self.jobs.items()):
            if job.task_id == task.id:
                job.kill()
                del self.jobs[fid]
        for f in task.files:
            if f.status == FILE_RUNNING:
                f.status = FILE_STOPPED
                f.progress = 0.0
        if task.is_active:
            task.status = TASK_STOPPED
            self.log(f"Завдання «{task.name}» зупинено.", "warn")
        self.on_change(task, False)
        if schedule:
            self.schedule()

    def stop_all(self) -> None:
        for t in self.tasks:
            if t.is_active:
                self.stop_task(t, schedule=False)
        self.schedule()

    # ------------------------------------------------------------ планувальник

    def _next_pending(self):
        for t in self.tasks:
            if t.is_active:
                for f in t.files:
                    if f.status == FILE_PENDING:
                        return t, f
        return None

    def schedule(self) -> None:
        limit = max(1, int(self.max_parallel() or 1))
        while len(self.jobs) < limit:
            nxt = self._next_pending()
            if nxt is None:
                break
            self._launch(*nxt)
        self._finalize()

    def _launch(self, task: Task, f) -> None:
        f.status = FILE_RUNNING
        f.progress = 0.0
        f.message = ""
        task.status = TASK_RUNNING
        job = Job(task.id, f.id, f.src, f.out_path, task.settings.copy(), self.events)
        self.jobs[f.id] = job
        job.start()
        self.log(f"[{task.name}] Почато: {os.path.basename(f.src)} → {os.path.basename(f.out_path)}", "info")
        self.on_change(task, False)

    def _finalize(self) -> None:
        for t in self.tasks:
            if not t.is_active:
                continue
            if any(f.status in (FILE_PENDING, FILE_RUNNING) for f in t.files):
                continue
            done, errors = t.count(FILE_DONE), t.count(FILE_ERROR)
            if errors == 0:
                t.status = TASK_DONE
                self.log(f"Завдання «{t.name}» завершено: {done} файл(ів) готово.", "ok")
            elif done == 0:
                t.status = TASK_ERROR
                self.log(f"Завдання «{t.name}» завершено з помилками: жоден файл не сконвертовано.", "error")
            else:
                t.status = TASK_PARTIAL
                self.log(f"Завдання «{t.name}» завершено: готово {done}, з помилками {errors}.", "warn")
            self.on_change(t, False)
        busy = self.is_busy()
        if self._was_busy and not busy:
            self.log("Черга оброблена.", "ok")
        self._was_busy = busy

    # ------------------------------------------------------------ події потоків

    def poll(self) -> None:
        finished = False
        while True:
            try:
                kind, job, data = self.events.get_nowait()
            except queue.Empty:
                break
            if self.jobs.get(job.file_id) is not job:
                continue  # застаріла подія (завдання зупинене/видалене)
            task, f = self._find(job.task_id, job.file_id)
            if task is None or f is None:
                self.jobs.pop(job.file_id, None)
                finished = True
                continue
            if kind == "progress":
                f.progress = data
                self.on_change(task, True)
                continue
            del self.jobs[job.file_id]
            finished = True
            if kind == "done":
                f.status = FILE_DONE
                f.progress = 1.0
                self.log(f"[{task.name}] Готово: {f.out_path}", "ok")
            else:
                f.status = FILE_ERROR
                f.progress = 0.0
                f.message = str(data)
                self.log(f"[{task.name}] ПОМИЛКА: {os.path.basename(f.src)}: {data}", "error")
            self.on_change(task, False)
        if finished:
            self.schedule()

    def shutdown(self) -> None:
        """Зупиняє все при виході й прибирає недописані файли."""
        jobs = list(self.jobs.values())
        self.stop_all()
        for job in jobs:
            job.wait_and_cleanup(timeout=3)
