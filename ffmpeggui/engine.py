"""Черга конвертації.

Стан моделі змінюється лише в головному (Tk) потоці. Кожен файл конвертується
в окремому робочому потоці, який надсилає події в queue.Queue; головний потік
забирає їх через poll().
"""

from __future__ import annotations

import os
import queue
import threading
import time
from typing import Callable

from . import ffmpeg_tools
from .i18n import t
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
    reserved_outputs,
)
from .timing import file_elapsed, format_duration, task_elapsed


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
                raise RuntimeError(t("У файлі не знайдено відеопотоку."))
            self._post("duration", info.duration)
            os.makedirs(os.path.dirname(self.dst) or ".", exist_ok=True)
            cmd = ffmpeg_tools.build_command(self.src, self.dst, self.settings, info)
            with self._lock:
                if self._cancel.is_set():
                    return
                self._proc = ffmpeg_tools.start_process(cmd)
                started = True
            rc, err = ffmpeg_tools.watch_process(
                self._proc, info.duration, lambda update: self._post("progress", update))
            if self._cancel.is_set():
                self._remove_partial()
                return
            if rc == 0:
                self._post("done")
            else:
                self._remove_partial()
                self._post("error", err or t("ffmpeg завершився з кодом {code}").format(code=rc))
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
        self.probe_results: queue.Queue = queue.Queue()
        self.jobs: dict[str, Job] = {}
        self._probing: set[str] = set()
        self._was_busy = False

    # ------------------------------------------------------------ стан

    def is_busy(self) -> bool:
        return any(t_.is_active for t_ in self.tasks)

    def _find(self, task_id: str, file_id: str):
        for task in self.tasks:
            if task.id == task_id:
                for f in task.files:
                    if f.id == file_id:
                        return task, f
                return task, None
        return None, None

    # ------------------------------------------------------------ тривалості

    def prefetch_durations(self, tasks: list[Task] | None = None) -> None:
        """У фоні визначає тривалість файлів — потрібна для оцінки часу."""
        if not ffmpeg_tools.ffmpeg_available():
            return
        items = []
        for task in (self.tasks if tasks is None else tasks):
            for f in task.files:
                if f.duration <= 0 and f.id not in self._probing:
                    self._probing.add(f.id)
                    items.append((task.id, f.id, f.src))
        if items:
            threading.Thread(target=self._probe_worker, args=(items,), daemon=True).start()

    def _probe_worker(self, items) -> None:
        for task_id, file_id, src in items:
            duration = ffmpeg_tools.probe_duration(src)
            self.probe_results.put((task_id, file_id, duration))

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
            f.started_at = 0.0
            f.finished_at = 0.0
            f.fps = 0.0
            f.speed = 0.0
        assign_output_paths(task, reserved_outputs(self.tasks, task))
        task.status = TASK_QUEUED
        # Час завдання рахуємо від старту його першого файлу (_launch), а не від
        # постановки в чергу — інакше після «Запустити всі» всі завдання мали б один час.
        task.started_at = 0.0
        task.finished_at = 0.0
        self.log(t("Завдання «{name}» додано в чергу. Файлів: {count}.").format(
            name=task.name, count=len(targets)), "info")
        self.on_change(task, False)
        self.prefetch_durations([task])
        if schedule:
            self.schedule()
        return True

    def start_all(self) -> int:
        started = 0
        for task in self.tasks:
            if task.status != TASK_DONE and self.start_task(task, schedule=False):
                started += 1
        self.schedule()
        return started

    def stop_task(self, task: Task, schedule: bool = True) -> None:
        now = time.time()
        for file_id, job in list(self.jobs.items()):
            if job.task_id == task.id:
                job.kill()
                del self.jobs[file_id]
        for f in task.files:
            if f.status == FILE_RUNNING:
                f.status = FILE_STOPPED
                f.progress = 0.0
                f.finished_at = now
                f.fps = 0.0
                f.speed = 0.0
        if task.is_active:
            task.status = TASK_STOPPED
            task.finished_at = now
            self.log(t("Завдання «{name}» зупинено.").format(name=task.name), "warn")
        self.on_change(task, False)
        if schedule:
            self.schedule()

    def stop_all(self) -> None:
        for task in self.tasks:
            if task.is_active:
                self.stop_task(task, schedule=False)
        self.schedule()

    # ------------------------------------------------------------ планувальник

    def _next_pending(self):
        for task in self.tasks:
            if task.is_active:
                for f in task.files:
                    if f.status == FILE_PENDING:
                        return task, f
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
        f.started_at = time.time()
        f.finished_at = 0.0
        task.status = TASK_RUNNING
        if not task.started_at:
            task.started_at = f.started_at
        job = Job(task.id, f.id, f.src, f.out_path, task.settings.copy(), self.events)
        self.jobs[f.id] = job
        job.start()
        self.log(t("[{task}] Почато: {src} → {dst}").format(
            task=task.name, src=os.path.basename(f.src), dst=os.path.basename(f.out_path)), "info")
        self.on_change(task, False)

    def _finalize(self) -> None:
        for task in self.tasks:
            if not task.is_active:
                continue
            if any(f.status in (FILE_PENDING, FILE_RUNNING) for f in task.files):
                continue
            task.finished_at = time.time()
            spent = format_duration(task_elapsed(task))
            done, errors = task.count(FILE_DONE), task.count(FILE_ERROR)
            if errors == 0:
                task.status = TASK_DONE
                self.log(t("Завдання «{name}» завершено. Готових файлів: {done}. Витрачено: {time}.").format(
                    name=task.name, done=done, time=spent), "ok")
            elif done == 0:
                task.status = TASK_ERROR
                self.log(t("Завдання «{name}» завершено з помилками: жоден файл не сконвертовано.").format(
                    name=task.name), "error")
            else:
                task.status = TASK_PARTIAL
                self.log(t("Завдання «{name}» завершено: готово {done}, з помилками {errors}. Витрачено: {time}.").format(
                    name=task.name, done=done, errors=errors, time=spent), "warn")
            self.on_change(task, False)
        busy = self.is_busy()
        if self._was_busy and not busy:
            self.log(t("Черга оброблена."), "ok")
        self._was_busy = busy

    # ------------------------------------------------------------ події потоків

    def poll(self) -> None:
        finished = False
        while True:
            try:
                task_id, file_id, duration = self.probe_results.get_nowait()
            except queue.Empty:
                break
            self._probing.discard(file_id)
            task, f = self._find(task_id, file_id)
            if f is not None and duration > 0:
                f.duration = duration
                self.on_change(task, True)

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
            if kind == "duration":
                if data and data > 0:
                    f.duration = data
                self.on_change(task, True)
                continue
            if kind == "progress":
                f.progress = data.fraction
                f.fps = data.fps
                f.speed = data.speed
                self.on_change(task, True)
                continue

            del self.jobs[job.file_id]
            finished = True
            f.finished_at = time.time()
            f.fps = 0.0
            f.speed = 0.0
            if kind == "done":
                f.status = FILE_DONE
                f.progress = 1.0
                self.log(t("[{task}] Готово за {time}: {path}").format(
                    task=task.name, time=format_duration(file_elapsed(f)), path=f.out_path), "ok")
            else:
                f.status = FILE_ERROR
                f.progress = 0.0
                f.message = str(data)
                self.log(t("[{task}] ПОМИЛКА: {name}: {error}").format(
                    task=task.name, name=os.path.basename(f.src), error=data), "error")
            self.on_change(task, False)
        if finished:
            self.schedule()

    def shutdown(self) -> None:
        """Зупиняє все при виході й прибирає недописані файли."""
        jobs = list(self.jobs.values())
        self.stop_all()
        for job in jobs:
            job.wait_and_cleanup(timeout=3)
