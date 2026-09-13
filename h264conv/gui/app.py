"""Головне вікно програми."""

from __future__ import annotations

import os
import tkinter as tk
from datetime import datetime
from tkinter import font as tkfont
from tkinter import messagebox, ttk

from .. import ffmpeg_tools, paths, store
from ..engine import Engine
from ..models import (
    FILE_DONE,
    FILE_ERROR,
    FILE_RUNNING,
    FILE_STATUS_LABELS,
    TASK_DONE,
    TASK_ERROR,
    TASK_IDLE,
    TASK_PARTIAL,
    TASK_QUEUED,
    TASK_RUNNING,
    TASK_STATUS_LABELS,
    TASK_STOPPED,
    Task,
    assign_output_paths,
)
from ..version import APP_TITLE, AUTHOR, DESCRIPTION, __version__
from .ffmpeg_setup import ensure_ffmpeg
from .task_dialog import TaskDialog
from .widgets import ScrollableFrame, ToolTip

STATUS_COLORS = {
    TASK_IDLE: "#444444",
    TASK_QUEUED: "#8a6d00",
    TASK_RUNNING: "#0050b0",
    TASK_DONE: "#1a7f1a",
    TASK_ERROR: "#c00000",
    TASK_PARTIAL: "#b35c00",
    TASK_STOPPED: "#666666",
}
MAX_LOG_LINES = 5000


class TaskRow(tk.Frame):
    """Рядок завдання: інформація, прогрес, кнопки, розгортуваний список файлів."""

    def __init__(self, parent, app: "MainWindow", task: Task, index: int, count: int, expanded: bool):
        super().__init__(parent, bd=2, relief="groove", padx=4, pady=3)
        self.app = app
        self.task = task
        self.index = index
        self.expanded = expanded
        self.tree: ttk.Treeview | None = None

        top = tk.Frame(self)
        top.pack(fill="x")
        top.columnconfigure(1, weight=1)

        # Рядок 0: [+] назва ............ кнопки
        # Рядок 1:     налаштування/тека .. статус [прогрес] %
        self.btn_toggle = ttk.Button(top, width=3, command=self.toggle)
        self.btn_toggle.grid(row=0, column=0, rowspan=2, padx=(0, 6), sticky="n")
        ToolTip(self.btn_toggle, "Показати / сховати список файлів завдання")

        self.lbl_title = tk.Label(top, anchor="w", font=app.bold_font)
        self.lbl_title.grid(row=0, column=1, sticky="we")
        self.lbl_sub = tk.Label(top, anchor="w", fg="#555555")
        self.lbl_sub.grid(row=1, column=1, sticky="we")
        for w in (self.lbl_title, self.lbl_sub):
            w.bind("<Double-Button-1>", lambda e: self.toggle())

        self.lbl_status = tk.Label(top, width=24, anchor="w")
        self.lbl_status.grid(row=1, column=2, padx=6, sticky="w")
        self.pb = ttk.Progressbar(top, length=170, maximum=100)
        self.pb.grid(row=1, column=3, pady=(2, 0))
        self.lbl_pct = tk.Label(top, width=5, anchor="e")
        self.lbl_pct.grid(row=1, column=4)

        btns = tk.Frame(top)
        btns.grid(row=0, column=2, columnspan=3, sticky="e", padx=(6, 0))
        self.btn_run = ttk.Button(btns, width=9, command=lambda: app.toggle_task(task))
        self.btn_edit = ttk.Button(btns, text="Редагувати", command=lambda: app.edit_task(task))
        self.btn_up = ttk.Button(btns, text="▲", width=3, command=lambda: app.move_task(task, -1))
        self.btn_down = ttk.Button(btns, text="▼", width=3, command=lambda: app.move_task(task, 1))
        self.btn_folder = ttk.Button(btns, text="Тека", width=6, command=lambda: app.open_folder(task))
        self.btn_del = ttk.Button(btns, text="Видалити", command=lambda: app.delete_task(task))
        for b in (self.btn_run, self.btn_edit, self.btn_up, self.btn_down, self.btn_folder, self.btn_del):
            b.pack(side="left", padx=1)
        ToolTip(self.btn_run, "Почати або зупинити конвертування цього завдання")
        ToolTip(self.btn_edit, "Змінити файли та налаштування завдання")
        ToolTip(self.btn_up, "Перемістити завдання на 1 позицію вгору")
        ToolTip(self.btn_down, "Перемістити завдання на 1 позицію вниз")
        ToolTip(self.btn_folder, "Відкрити в Провіднику теку з готовими файлами")
        ToolTip(self.btn_del, "Видалити завдання зі списку (файли на диску не видаляються)")
        if index == 1:
            self.btn_up.state(["disabled"])
        if index == count:
            self.btn_down.state(["disabled"])

        self.files_frame = tk.Frame(self)
        if expanded:
            self._show_files()
        self.refresh()

    # ------------------------------------------------------------ файли

    def toggle(self):
        self.expanded = not self.expanded
        if self.expanded:
            self.app.expanded.add(self.task.id)
            self._show_files()
        else:
            self.app.expanded.discard(self.task.id)
            self.files_frame.pack_forget()
            if self.tree is not None:
                self.tree.master.destroy()
                self.tree = None
        self.refresh()

    def _show_files(self):
        holder = tk.Frame(self.files_frame)
        holder.pack(fill="x")
        cols = ("n", "src", "out", "status", "pct")
        tree = ttk.Treeview(holder, columns=cols, show="headings", selectmode="none",
                            height=min(max(len(self.task.files), 1), 10))
        for col, title, width, stretch in (("n", "№", 40, False), ("src", "Вихідний файл", 300, True),
                                           ("out", "Результат", 300, True), ("status", "Стан", 260, True),
                                           ("pct", "Прогрес", 70, False)):
            tree.heading(col, text=title)
            tree.column(col, width=width, stretch=stretch, anchor="e" if col in ("n", "pct") else "w")
        tree.tag_configure("done", foreground="#1a7f1a")
        tree.tag_configure("error", foreground="#c00000")
        tree.tag_configure("running", foreground="#0050b0")
        vsb = ttk.Scrollbar(holder, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.pack(side="left", fill="x", expand=True)
        vsb.pack(side="right", fill="y")
        self.tree = tree
        self.files_frame.pack(fill="x", pady=(4, 0))
        self._fill_tree()

    @staticmethod
    def _file_values(i, f):
        status = FILE_STATUS_LABELS.get(f.status, f.status)
        if f.status == FILE_ERROR and f.message:
            status += ": " + f.message.splitlines()[-1][:120]
        if f.status == FILE_DONE:
            pct = "100%"
        elif f.status == FILE_RUNNING:
            pct = f"{f.progress * 100:.1f}%"
        else:
            pct = ""
        return (i, os.path.basename(f.src), os.path.basename(f.out_path) if f.out_path else "—", status, pct)

    @staticmethod
    def _file_tag(f):
        return {FILE_DONE: ("done",), FILE_ERROR: ("error",), FILE_RUNNING: ("running",)}.get(f.status, ())

    def _fill_tree(self):
        tree = self.tree
        tree.delete(*tree.get_children())
        for i, f in enumerate(self.task.files, 1):
            tree.insert("", "end", iid=f.id, values=self._file_values(i, f), tags=self._file_tag(f))
        tree.configure(height=min(max(len(self.task.files), 1), 10))

    def _update_tree(self):
        tree = self.tree
        if list(tree.get_children()) != [f.id for f in self.task.files]:
            self._fill_tree()
            return
        for i, f in enumerate(self.task.files, 1):
            tree.item(f.id, values=self._file_values(i, f), tags=self._file_tag(f))

    # ------------------------------------------------------------ оновлення

    def refresh(self):
        t = self.task
        s = t.settings
        self.btn_toggle.configure(text="−" if self.expanded else "+")
        self.lbl_title.configure(text=f"{self.index}. {t.name}")
        if s.res_mode == "source":
            res = "роздільність як є"
        elif s.res_master == "width":
            res = f"ширина {s.width}"
        else:
            res = f"висота {s.height}"
        self.lbl_sub.configure(
            text=f"Файлів: {len(t.files)}  |  CRF {s.crf}, {s.preset}, {res}, {s.container.upper()}  |  → {t.out_dir}")

        status = TASK_STATUS_LABELS.get(t.status, t.status)
        done, errors = t.count(FILE_DONE), t.count(FILE_ERROR)
        if t.is_active:
            status += f" ({done + errors}/{len(t.files)})"
        elif t.status in (TASK_ERROR, TASK_PARTIAL):
            status = f"{status} ({errors})"
        self.lbl_status.configure(text=status, fg=STATUS_COLORS.get(t.status, "#000000"))

        pct = t.progress() * 100
        self.pb["value"] = pct
        self.lbl_pct.configure(text=f"{pct:.0f}%")

        active = t.is_active
        self.btn_run.configure(text="■ Стоп" if active else "▶ Старт")
        self.btn_edit.state(["disabled"] if active else ["!disabled"])
        if self.tree is not None:
            self._update_tree()


class MainWindow:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.settings = store.load_settings()
        self.presets = store.PresetStore()
        self.tasks: list[Task] = store.load_tasks()
        self.expanded: set[str] = set()
        self.rows: dict[str, TaskRow] = {}
        self._save_after = None
        self._title = ""

        base = tkfont.nametofont("TkDefaultFont")
        self.bold_font = base.copy()
        self.bold_font.configure(weight="bold")

        self.v_parallel = tk.StringVar(value=str(self.settings.get("max_parallel", 1)))
        self.engine = Engine(self.tasks, self._max_parallel, self._on_engine_change, self.log)

        root.title(f"{APP_TITLE} {__version__}")
        root.geometry(self.settings.get("geometry") or "1150x720")
        root.minsize(950, 520)

        self._build_menu()
        self._build_toolbar()
        self._build_statusbar()
        self._build_body()
        self._rebuild_rows()

        self.log(f"{APP_TITLE} {__version__} запущено. Налаштування та черга: {paths.data_dir()}", "info")
        if self.tasks:
            self.log(f"Відновлено завдань із попереднього сеансу: {len(self.tasks)}.", "info")

        root.protocol("WM_DELETE_WINDOW", self._on_close)
        root.bind_all("<Control-n>", lambda e: self.add_task())
        root.after(150, self._poll)
        root.after(400, self._startup_ffmpeg_check)

    # ================================================================ побудова

    def _build_menu(self):
        m = tk.Menu(self.root)
        fm = tk.Menu(m, tearoff=False)
        fm.add_command(label="Додати завдання…", accelerator="Ctrl+N", command=self.add_task)
        fm.add_separator()
        fm.add_command(label="Вихід", command=self._on_close)
        m.add_cascade(label="Файл", menu=fm)

        qm = tk.Menu(m, tearoff=False)
        qm.add_command(label="Запустити всі", command=self.start_all)
        qm.add_command(label="Зупинити все", command=self.stop_all)
        qm.add_separator()
        qm.add_command(label="Прибрати завершені завдання зі списку", command=self.remove_finished)
        m.add_cascade(label="Черга", menu=qm)

        sm = tk.Menu(m, tearoff=False)
        sm.add_command(label="Перевірити / встановити ffmpeg…", command=self._check_ffmpeg_manual)
        sm.add_command(label="Відкрити теку bin (ffmpeg)", command=self._open_bin)
        sm.add_command(label="Відкрити теку з пресетами та чергою", command=lambda: os.startfile(paths.data_dir()))
        m.add_cascade(label="Налаштування", menu=sm)

        hm = tk.Menu(m, tearoff=False)
        hm.add_command(label="Про програму", command=self._about)
        m.add_cascade(label="Довідка", menu=hm)
        self.root.configure(menu=m)

    def _build_toolbar(self):
        tb = ttk.Frame(self.root, padding=(6, 6, 6, 2))
        tb.pack(side="top", fill="x")
        b = ttk.Button(tb, text="Додати завдання…", command=self.add_task)
        b.pack(side="left")
        ToolTip(b, "Створити нове завдання: вибрати файли, теку для результату та якість (Ctrl+N)")
        ttk.Separator(tb, orient="vertical").pack(side="left", fill="y", padx=8)
        b = ttk.Button(tb, text="▶ Запустити всі", command=self.start_all)
        b.pack(side="left")
        ToolTip(b, "Поставити в чергу всі незавершені завдання й конвертувати їх по черзі")
        b = ttk.Button(tb, text="■ Зупинити все", command=self.stop_all)
        b.pack(side="left", padx=4)
        ToolTip(b, "Негайно зупинити всі процеси ffmpeg (прогрес поточних файлів буде втрачено)")

        ttk.Separator(tb, orient="vertical").pack(side="left", fill="y", padx=8)
        ttk.Label(tb, text="Паралельних процесів:").pack(side="left")
        sp = ttk.Spinbox(tb, from_=1, to=max(1, os.cpu_count() or 1), width=4,
                         textvariable=self.v_parallel, command=self._on_parallel_change)
        sp.pack(side="left", padx=4)
        sp.bind("<Return>", lambda e: self._on_parallel_change())
        sp.bind("<FocusOut>", lambda e: self._on_parallel_change())
        ToolTip(sp, "Скільки файлів конвертувати одночасно. 1 — строго по черзі. Більше значення може "
                    "пришвидшити роботу на багатоядерних процесорах, але x264 і так використовує всі ядра.")

    def _build_body(self):
        paned = ttk.PanedWindow(self.root, orient="vertical")
        paned.pack(fill="both", expand=True, padx=6, pady=4)

        tasks_lf = ttk.LabelFrame(paned, text="Завдання", padding=4)
        self.list = ScrollableFrame(tasks_lf)
        self.list.pack(fill="both", expand=True)
        self.empty_lbl = ttk.Label(self.list.inner, foreground="#555555",
                                   text="Немає завдань. Натисніть «Додати завдання…», щоб почати.")
        paned.add(tasks_lf, weight=4)

        log_lf = ttk.LabelFrame(paned, text="Журнал", padding=4)
        log_lf.columnconfigure(0, weight=1)
        log_lf.rowconfigure(0, weight=1)
        self.log_text = tk.Text(log_lf, height=8, wrap="word", state="disabled",
                                font=("Consolas", 9), relief="sunken", borderwidth=2)
        vsb = ttk.Scrollbar(log_lf, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=vsb.set)
        self.log_text.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        self.log_text.tag_configure("error", foreground="#c00000")
        self.log_text.tag_configure("warn", foreground="#b35c00")
        self.log_text.tag_configure("ok", foreground="#1a7f1a")
        self.log_text.tag_configure("time", foreground="#777777")
        ttk.Button(log_lf, text="Очистити журнал", command=self._clear_log).grid(
            row=1, column=0, sticky="e", pady=(4, 0))
        paned.add(log_lf, weight=1)

    def _build_statusbar(self):
        bar = tk.Frame(self.root, bd=1, relief="sunken")
        bar.pack(side="bottom", fill="x")
        self.lbl_ffmpeg = tk.Label(bar, anchor="w", padx=4)
        self.lbl_ffmpeg.pack(side="left", fill="x", expand=True)
        tk.Label(bar, text=f"v{__version__}", padx=6).pack(side="right")
        self._update_ffmpeg_status()

    def _rebuild_rows(self):
        for row in self.rows.values():
            row.destroy()
        self.rows.clear()
        self.empty_lbl.pack_forget()
        if not self.tasks:
            self.empty_lbl.pack(pady=30)
        for i, t in enumerate(self.tasks, 1):
            row = TaskRow(self.list.inner, self, t, i, len(self.tasks), t.id in self.expanded)
            row.pack(fill="x", padx=2, pady=2)
            self.rows[t.id] = row

    # ================================================================ журнал

    def log(self, message: str, level: str = "info"):
        now = datetime.now()
        self.log_text.configure(state="normal")
        self.log_text.insert("end", now.strftime("%H:%M:%S  "), ("time",))
        self.log_text.insert("end", message + "\n", (level,) if level != "info" else ())
        lines = int(self.log_text.index("end-1c").split(".")[0])
        if lines > MAX_LOG_LINES:
            self.log_text.delete("1.0", f"{lines - MAX_LOG_LINES}.0")
        self.log_text.configure(state="disabled")
        self.log_text.see("end")
        try:
            with open(paths.log_file(), "a", encoding="utf-8") as fh:
                fh.write(f"{now:%Y-%m-%d %H:%M:%S} [{level}] {message}\n")
        except OSError:
            pass

    def _clear_log(self):
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

    # ================================================================ рушій

    def _max_parallel(self) -> int:
        try:
            return max(1, min(64, int(self.v_parallel.get())))
        except ValueError:
            return 1

    def _on_parallel_change(self):
        n = self._max_parallel()
        self.v_parallel.set(str(n))
        if self.settings.get("max_parallel") != n:
            self.settings["max_parallel"] = n
            self._save_settings()
            self.log(f"Кількість паралельних процесів: {n}.", "info")
            self.engine.schedule()

    def _on_engine_change(self, task: Task, progress_only: bool):
        row = self.rows.get(task.id)
        if row is not None:
            row.refresh()
        if not progress_only:
            self._schedule_save()

    def _poll(self):
        try:
            self.engine.poll()
            p = self.engine.overall_progress()
            title = f"[{p * 100:.0f}%] {APP_TITLE}" if p is not None else f"{APP_TITLE} {__version__}"
            if title != self._title:
                self._title = title
                self.root.title(title)
        finally:
            self.root.after(150, self._poll)

    # ================================================================ збереження

    def _schedule_save(self):
        if self._save_after is None:
            self._save_after = self.root.after(800, self._save_now)

    def _save_now(self):
        self._save_after = None
        try:
            store.save_tasks(self.tasks)
        except OSError as exc:
            self.log(f"Не вдалося зберегти чергу: {exc}", "error")

    def _save_settings(self):
        try:
            store.save_settings(self.settings)
        except OSError as exc:
            self.log(f"Не вдалося зберегти налаштування: {exc}", "error")

    # ================================================================ дії із завданнями

    def add_task(self):
        dlg = TaskDialog(self.root, self.presets, self.settings, None,
                         default_name=f"Завдання {len(self.tasks) + 1}")
        self.root.wait_window(dlg)
        self._save_settings()
        task = dlg.result
        if task is None:
            return
        assign_output_paths(task)
        self.tasks.append(task)
        self._rebuild_rows()
        self.list.scroll_to_bottom()
        self._schedule_save()
        self.log(f"Додано завдання «{task.name}» ({len(task.files)} файл.).", "info")
        if self.engine.is_busy():
            # Конвертація вже йде — нове завдання стає в кінець черги.
            self.engine.start_task(task)

    def edit_task(self, task: Task):
        if task.is_active:
            messagebox.showinfo("Редагування", "Спершу зупиніть конвертування цього завдання.", parent=self.root)
            return
        dlg = TaskDialog(self.root, self.presets, self.settings, task)
        self.root.wait_window(dlg)
        self._save_settings()
        r = dlg.result
        if r is None:
            return
        task.name = r.name
        task.files = r.files
        task.out_dir = r.out_dir
        task.prefix = r.prefix
        task.settings = r.settings
        if task.status == TASK_DONE and any(f.status != FILE_DONE for f in task.files):
            task.status = TASK_IDLE
        assign_output_paths(task)
        self._rebuild_rows()
        self._schedule_save()
        self.log(f"Завдання «{task.name}» змінено.", "info")

    def toggle_task(self, task: Task):
        if task.is_active:
            self.engine.stop_task(task)
            return
        if not self._require_ffmpeg():
            return
        if task.files and all(f.status == FILE_DONE for f in task.files):
            if not messagebox.askyesno("Повторна конвертація",
                                       f"Усі файли завдання «{task.name}» вже сконвертовано.\n"
                                       "Сконвертувати їх заново (готові файли буде перезаписано)?",
                                       parent=self.root):
                return
        self.engine.start_task(task)

    def start_all(self):
        if not self._require_ffmpeg():
            return
        started = self.engine.start_all()
        if not started and not self.engine.is_busy():
            messagebox.showinfo("Запустити всі",
                                "Немає завдань для запуску (список порожній або всі завдання вже готові).",
                                parent=self.root)

    def stop_all(self):
        if self.engine.is_busy():
            self.engine.stop_all()

    def delete_task(self, task: Task):
        text = f"Видалити завдання «{task.name}» зі списку?\n\nВихідні та готові файли на диску не видаляються."
        if task.is_active:
            text += "\n\nКонвертування цього завдання буде зупинено."
        if not messagebox.askyesno("Видалити завдання", text, parent=self.root):
            return
        if task.is_active:
            self.engine.stop_task(task)
        if task in self.tasks:
            self.tasks.remove(task)
        self.expanded.discard(task.id)
        self._rebuild_rows()
        self._schedule_save()
        self.log(f"Завдання «{task.name}» видалено зі списку.", "info")

    def move_task(self, task: Task, delta: int):
        i = self.tasks.index(task)
        j = i + delta
        if not 0 <= j < len(self.tasks):
            return
        self.tasks[i], self.tasks[j] = self.tasks[j], self.tasks[i]
        self._rebuild_rows()
        self._schedule_save()

    def remove_finished(self):
        done = [t for t in self.tasks if t.status == TASK_DONE]
        if not done:
            messagebox.showinfo("Черга", "Немає повністю завершених завдань.", parent=self.root)
            return
        if not messagebox.askyesno("Черга", f"Прибрати зі списку завершені завдання ({len(done)})?\n"
                                            "Файли на диску не видаляються.", parent=self.root):
            return
        for t in done:
            self.tasks.remove(t)
        self._rebuild_rows()
        self._schedule_save()

    def open_folder(self, task: Task):
        path = task.out_dir
        if path and os.path.isdir(path):
            os.startfile(path)
        else:
            messagebox.showinfo("Тека", f"Тека ще не існує:\n{path}\n\n"
                                        "Вона буде створена під час конвертування першого файлу.",
                                parent=self.root)

    # ================================================================ ffmpeg

    def _update_ffmpeg_status(self):
        if ffmpeg_tools.ffmpeg_available():
            version = ffmpeg_tools.ffmpeg_version() or "ffmpeg"
            self.lbl_ffmpeg.configure(text=f"ffmpeg: {version}  ({paths.bin_dir()})", fg="#000000")
        else:
            self.lbl_ffmpeg.configure(text=f"ffmpeg не знайдено в {paths.bin_dir()} — конвертація недоступна",
                                      fg="#c00000")

    def _startup_ffmpeg_check(self):
        if not ffmpeg_tools.ffmpeg_available():
            ensure_ffmpeg(self.root, self.log)
            self._update_ffmpeg_status()

    def _require_ffmpeg(self) -> bool:
        if ffmpeg_tools.ffmpeg_available():
            return True
        ok = ensure_ffmpeg(self.root, self.log, reason="Для конвертування потрібен ffmpeg.")
        self._update_ffmpeg_status()
        return ok

    def _check_ffmpeg_manual(self):
        if ffmpeg_tools.ffmpeg_available():
            messagebox.showinfo("ffmpeg", f"ffmpeg знайдено:\n{ffmpeg_tools.ffmpeg_version()}\n\n"
                                          f"Тека: {paths.bin_dir()}", parent=self.root)
        else:
            ensure_ffmpeg(self.root, self.log)
        self._update_ffmpeg_status()

    def _open_bin(self):
        os.makedirs(paths.bin_dir(), exist_ok=True)
        os.startfile(paths.bin_dir())

    def _about(self):
        messagebox.showinfo(
            "Про програму",
            f"{APP_TITLE}\nВерсія {__version__}\n\n{DESCRIPTION}\n\nАвтор: {AUTHOR}\n\n"
            f"ffmpeg: {paths.bin_dir()}\nДані програми: {paths.data_dir()}",
            parent=self.root)

    # ================================================================ вихід

    def _on_close(self):
        if self.engine.is_busy():
            if not messagebox.askyesno(
                    "Вихід", "Конвертування ще триває. Зупинити його та вийти?\n\n"
                             "Недописані файли буде видалено, завдання залишаться в списку як незавершені.",
                    parent=self.root):
                return
            self.engine.shutdown()
        try:
            self.settings["geometry"] = self.root.geometry()
            self.settings["max_parallel"] = self._max_parallel()
            store.save_settings(self.settings)
            store.save_tasks(self.tasks)
        except OSError:
            pass
        self.root.destroy()


def _enable_dpi_awareness():
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        pass


def run():
    _enable_dpi_awareness()
    root = tk.Tk()
    # Колесо миші над списками/лічильниками не повинно випадково змінювати значення —
    # воно прокручує панель налаштувань.
    for cls in ("TCombobox", "TSpinbox"):
        root.unbind_class(cls, "<MouseWheel>")
    MainWindow(root)
    root.mainloop()
