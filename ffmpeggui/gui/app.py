"""Головне вікно програми."""

from __future__ import annotations

import os
import tkinter as tk
from datetime import datetime
from tkinter import filedialog
from tkinter import font as tkfont
from tkinter import messagebox, ttk

from .. import buildinfo, ffmpeg_tools, i18n, paths, store
from ..engine import Engine
from ..i18n import t
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
    queue_stats,
)
from ..timing import file_elapsed, file_eta, format_duration, queue_eta, task_elapsed, task_eta
from ..version import APP_NAME, APP_TITLE, AUTHOR, VERSION_DATE, __version__
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
ERROR_COLOR = "#c00000"
ERROR_BG = "#ffe8e8"
MAX_LOG_LINES = 5000


def shorten_path(path: str, limit: int = 46) -> str:
    """Від довгого шляху лишаємо диск і дві останні теки: C:\\…\\Відео\\h264_master."""
    if len(path) <= limit:
        return path
    parts = [p for p in path.replace("/", "\\").split("\\") if p]
    if len(parts) < 3:
        return path
    drive = parts[0] + "\\" if parts[0].endswith(":") else ""
    short = drive + "…\\" + "\\".join(parts[-2:])
    return short if len(short) < len(path) else path


def parallel_help_text() -> str:
    return t(
        "Скільки файлів конвертувати одночасно.\n\n"
        "Значення можна змінювати й під час конвертації — вона не переривається:\n\n"
        "• Якщо збільшити — діє одразу: програма тут же бере наступні файли з черги "
        "й запускає додаткові процеси ffmpeg.\n\n"
        "• Якщо зменшити — жоден процес не вбивається. Файли, що вже конвертуються, "
        "спокійно дораховуються до кінця, а нові не запускаються, доки їх кількість "
        "не впаде до нового значення. Тобто зменшення діє поступово, на відміну від "
        "кнопки «Зупинити».\n\n"
        "1 означає строго послідовну обробку. Врахуйте, що x264 і так використовує всі "
        "ядра процесора, тож виграш від кількох одночасних процесів зазвичай невеликий."
    )


class TaskRow(tk.Frame):
    """Рядок завдання: інформація, прогрес, час, кнопки та список файлів."""

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

        # Рядок 0: [+] назва .......... кнопки
        # Рядок 1:     підпис (файли, налаштування, тека)
        # Рядок 2:     статус | прогрес | % | час
        self.btn_toggle = ttk.Button(top, width=3, command=self.toggle)
        self.btn_toggle.grid(row=0, column=0, rowspan=3, padx=(0, 6), sticky="n")
        ToolTip(self.btn_toggle, t("Показати / сховати список файлів завдання"))

        self.lbl_title = tk.Label(top, anchor="w", font=app.bold_font)
        self.lbl_title.grid(row=0, column=1, sticky="we")
        self.lbl_sub = tk.Label(top, anchor="w", fg="#555555")
        self.lbl_sub.grid(row=1, column=1, sticky="we")
        for w in (self.lbl_title, self.lbl_sub):
            w.bind("<Double-Button-1>", lambda e: self.toggle())
        ToolTip(self.lbl_sub, task.out_dir)

        btns = tk.Frame(top)
        btns.grid(row=0, column=2, sticky="e", padx=(6, 0))
        self.btn_run = ttk.Button(btns, width=9, command=lambda: app.toggle_task(task))
        self.btn_edit = ttk.Button(btns, text=t("Редагувати"), command=lambda: app.edit_task(task))
        self.btn_up = ttk.Button(btns, text="▲", width=3, command=lambda: app.move_task(task, -1))
        self.btn_down = ttk.Button(btns, text="▼", width=3, command=lambda: app.move_task(task, 1))
        self.btn_folder = ttk.Button(btns, text=t("Тека"), width=6, command=lambda: app.open_folder(task))
        self.btn_del = ttk.Button(btns, text=t("Видалити"), command=lambda: app.delete_task(task))
        for b in (self.btn_run, self.btn_edit, self.btn_up, self.btn_down, self.btn_folder, self.btn_del):
            b.pack(side="left", padx=1)
        ToolTip(self.btn_run, t("Почати або зупинити конвертування цього завдання"))
        ToolTip(self.btn_edit, t("Змінити файли та налаштування завдання"))
        ToolTip(self.btn_up, t("Перемістити завдання на 1 позицію вгору"))
        ToolTip(self.btn_down, t("Перемістити завдання на 1 позицію вниз"))
        ToolTip(self.btn_folder, t("Відкрити в Провіднику теку з готовими файлами"))
        ToolTip(self.btn_del, t("Видалити завдання зі списку (файли на диску не видаляються)"))
        if index == 1:
            self.btn_up.state(["disabled"])
        if index == count:
            self.btn_down.state(["disabled"])

        metrics = tk.Frame(top)
        metrics.grid(row=2, column=1, columnspan=2, sticky="we", pady=(2, 0))
        self.lbl_status = tk.Label(metrics, width=24, anchor="w")
        self.lbl_status.pack(side="left")
        self.pb = ttk.Progressbar(metrics, length=170, maximum=100)
        self.pb.pack(side="left", padx=(0, 6))
        self.lbl_pct = tk.Label(metrics, width=5, anchor="e")
        self.lbl_pct.pack(side="left")
        self.lbl_time = tk.Label(metrics, anchor="w", fg="#333333")
        self.lbl_time.pack(side="left", padx=(10, 0))

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
        cols = ("n", "src", "out", "status", "pct", "elapsed", "eta", "fps")
        tree = ttk.Treeview(holder, columns=cols, show="headings", selectmode="none",
                            height=min(max(len(self.task.files), 1), 10))
        layout = (
            ("n", t("№"), 36, False, "e"),
            ("src", t("Вихідний файл"), 230, True, "w"),
            ("out", t("Результат"), 210, True, "w"),
            ("status", t("Стан"), 150, True, "w"),
            ("pct", t("Прогрес"), 70, False, "e"),
            ("elapsed", t("Час"), 65, False, "e"),
            ("eta", t("Залишилось"), 95, False, "e"),
            ("fps", t("кадр/с"), 60, False, "e"),
        )
        for col, title, width, stretch, anchor in layout:
            tree.heading(col, text=title)
            tree.column(col, width=width, stretch=stretch, anchor=anchor)
        tree.tag_configure("done", foreground="#1a7f1a")
        tree.tag_configure("error", foreground=ERROR_COLOR)
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
        status = t(FILE_STATUS_LABELS.get(f.status, f.status))
        if f.status == FILE_ERROR and f.message:
            status += ": " + f.message.splitlines()[-1][:120]
        if f.status == FILE_DONE:
            pct = "100%"
        elif f.status == FILE_RUNNING:
            pct = f"{f.progress * 100:.1f}%"
        else:
            pct = ""
        elapsed = format_duration(file_elapsed(f)) if f.started_at else ""
        eta = format_duration(file_eta(f)) if f.status == FILE_RUNNING else ""
        fps = f"{f.fps:.0f}" if f.status == FILE_RUNNING and f.fps > 0 else ""
        return (i, os.path.basename(f.src), os.path.basename(f.out_path) if f.out_path else "—",
                status, pct, elapsed, eta, fps)

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
        task = self.task
        s = task.settings
        self.btn_toggle.configure(text="−" if self.expanded else "+")
        self.lbl_title.configure(text=f"{self.index}. {task.name}")
        if s.res_mode == "source":
            res = t("роздільність як є")
        elif s.res_master == "width":
            res = t("ширина {value}").format(value=s.width)
        else:
            res = t("висота {value}").format(value=s.height)
        self.lbl_sub.configure(text=t("Файлів: {count}  |  CRF {crf}, {preset}, {res}, {container}  |  → {out}").format(
            count=len(task.files), crf=s.crf, preset=s.preset, res=res,
            container=s.container.upper(), out=shorten_path(task.out_dir)))

        status = t(TASK_STATUS_LABELS.get(task.status, task.status))
        done, errors = task.count(FILE_DONE), task.count(FILE_ERROR)
        if task.is_active:
            status += f" ({done + errors}/{len(task.files)})"
        elif task.status in (TASK_ERROR, TASK_PARTIAL):
            status = f"{status} ({errors})"
        self.lbl_status.configure(text=status, fg=STATUS_COLORS.get(task.status, "#000000"))

        pct = task.progress() * 100
        self.pb["value"] = pct
        self.lbl_pct.configure(text=f"{pct:.0f}%")
        self.lbl_time.configure(text=self._time_text())

        active = task.is_active
        self.btn_run.configure(text=t("■ Стоп") if active else t("▶ Старт"))
        self.btn_edit.state(["disabled"] if active else ["!disabled"])
        if self.tree is not None:
            self._update_tree()

    def _time_text(self) -> str:
        task = self.task
        parts = []
        elapsed = task_elapsed(task)
        if elapsed > 0:
            label = t("минуло {time}") if task.is_active else t("витрачено {time}")
            parts.append(label.format(time=format_duration(elapsed)))
        if task.is_active:
            eta = task_eta(task, parallel=self.app.max_parallel())
            if eta is not None:
                parts.append(t("залишилось ~{time}").format(time=format_duration(eta)))
            fps = sum(f.fps for f in task.files if f.status == FILE_RUNNING and f.fps > 0)
            if fps > 0:
                parts.append(t("{fps} кадр/с").format(fps=f"{fps:.0f}"))
        return "  ·  ".join(parts)


class MainWindow:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.settings = store.load_settings()
        i18n.set_language(self.settings.get("language", i18n.DEFAULT_LANGUAGE))
        self.presets = store.PresetStore()
        self.tasks: list[Task] = store.load_tasks()
        self.expanded: set[str] = set()
        self.rows: dict[str, TaskRow] = {}
        self.log_entries: list[tuple[datetime, str, str]] = []
        self.error_count = 0
        self.log_collapsed = bool(self.settings.get("log_collapsed"))
        self._saved_sash = 0
        self._save_after = None
        self._title = ""

        base = tkfont.nametofont("TkDefaultFont")
        self.bold_font = base.copy()
        self.bold_font.configure(weight="bold")

        self.v_parallel = tk.StringVar(value=str(self.settings.get("max_parallel", 1)))
        self.v_language = tk.StringVar(value=i18n.get_language())
        self.engine = Engine(self.tasks, self.max_parallel, self._on_engine_change, self.log)

        root.geometry(self.settings.get("geometry") or "1150x720")
        root.minsize(980, 560)
        self._build_ui()

        self.log(t("{app} {version} запущено. Налаштування та черга: {path}").format(
            app=APP_TITLE, version=__version__, path=paths.data_dir()), "info")
        migrated = paths.migrated_files()
        if migrated:
            self.log(t("Перенесено з теки попередньої версії: {files}").format(
                files=", ".join(migrated)), "info")
        if self.tasks:
            self.log(t("Відновлено завдань із попереднього сеансу: {count}.").format(
                count=len(self.tasks)), "info")
        self.engine.prefetch_durations()

        root.protocol("WM_DELETE_WINDOW", self._on_close)
        root.bind_all("<Control-n>", lambda e: self.add_task())
        root.after(150, self._poll)
        root.after(400, self._startup_ffmpeg_check)

    # ================================================================ побудова

    def _build_ui(self):
        self._build_menu()
        self._build_toolbar()
        self._build_statusbar()
        self._build_body()
        self._rebuild_rows()
        for entry in self.log_entries:
            self._append_log_line(*entry)
        self._update_log_header()
        # Початковий стан застосовуємо, коли вікно вже отримало свої розміри.
        self.root.after(250, lambda: self._apply_log_state(initial=True))

    def _destroy_ui(self):
        for widget in (getattr(self, "toolbar", None), getattr(self, "paned", None),
                       getattr(self, "statusbar", None)):
            if widget is not None:
                widget.destroy()
        self.rows.clear()

    def change_language(self, code: str):
        if code == i18n.get_language():
            return
        i18n.set_language(code)
        self.settings["language"] = code
        self._save_settings()
        self._destroy_ui()
        self._build_ui()
        self._update_ffmpeg_status()
        self.log(t("Мову інтерфейсу змінено."), "info")

    def _build_menu(self):
        m = tk.Menu(self.root)
        fm = tk.Menu(m, tearoff=False)
        fm.add_command(label=t("Додати завдання…"), accelerator="Ctrl+N", command=self.add_task)
        fm.add_separator()
        fm.add_command(label=t("Вихід"), command=self._on_close)
        m.add_cascade(label=t("Файл"), menu=fm)

        qm = tk.Menu(m, tearoff=False)
        qm.add_command(label=t("Запустити всі"), command=self.start_all)
        qm.add_command(label=t("Зупинити все"), command=self.stop_all)
        qm.add_separator()
        qm.add_command(label=t("Прибрати завершені завдання зі списку"), command=self.remove_finished)
        m.add_cascade(label=t("Черга"), menu=qm)

        sm = tk.Menu(m, tearoff=False)
        lm = tk.Menu(sm, tearoff=False)
        for code, name in i18n.LANGUAGES:
            lm.add_radiobutton(label=name, value=code, variable=self.v_language,
                               command=lambda c=code: self.change_language(c))
        sm.add_cascade(label=t("Мова інтерфейсу"), menu=lm)
        sm.add_separator()
        sm.add_command(label=t("Перевірити / встановити ffmpeg…"), command=self._check_ffmpeg_manual)
        sm.add_command(label=t("Відкрити теку bin (ffmpeg)"), command=self._open_bin)
        sm.add_command(label=t("Відкрити теку з пресетами та чергою"),
                       command=lambda: os.startfile(paths.data_dir()))
        m.add_cascade(label=t("Налаштування"), menu=sm)

        hm = tk.Menu(m, tearoff=False)
        hm.add_command(label=t("Про програму"), command=self._about)
        m.add_cascade(label=t("Довідка"), menu=hm)
        self.root.configure(menu=m)

    def _build_toolbar(self):
        self.toolbar = ttk.Frame(self.root, padding=(6, 6, 6, 2))
        self.toolbar.pack(side="top", fill="x")

        line1 = ttk.Frame(self.toolbar)
        line1.pack(fill="x")
        b = ttk.Button(line1, text=t("Додати завдання…"), command=self.add_task)
        b.pack(side="left")
        ToolTip(b, t("Створити нове завдання: вибрати файли, теку для результату та якість (Ctrl+N)"))
        ttk.Separator(line1, orient="vertical").pack(side="left", fill="y", padx=8)
        b = ttk.Button(line1, text=t("▶ Запустити всі"), command=self.start_all)
        b.pack(side="left")
        ToolTip(b, t("Поставити в чергу всі незавершені завдання й конвертувати їх по черзі"))
        b = ttk.Button(line1, text=t("■ Зупинити все"), command=self.stop_all)
        b.pack(side="left", padx=4)
        ToolTip(b, t("Негайно зупинити всі процеси ffmpeg (прогрес поточних файлів буде втрачено)"))

        ttk.Separator(line1, orient="vertical").pack(side="left", fill="y", padx=8)
        ttk.Label(line1, text=t("Паралельних процесів:")).pack(side="left")
        sp = ttk.Spinbox(line1, from_=1, to=max(1, os.cpu_count() or 1), width=4,
                         textvariable=self.v_parallel, command=self._on_parallel_change)
        sp.pack(side="left", padx=4)
        sp.bind("<Return>", lambda e: self._on_parallel_change())
        sp.bind("<FocusOut>", lambda e: self._on_parallel_change())
        ToolTip(sp, t("Скільки файлів конвертувати одночасно. 1 — строго по черзі. "
                      "Значення можна змінювати під час конвертації: збільшення діє одразу, "
                      "зменшення — у міру завершення поточних файлів."))
        b = ttk.Button(line1, text=" ? ", width=3, command=self._parallel_help)
        b.pack(side="left")
        ToolTip(b, t("Що буде, якщо змінити це значення під час конвертації?"))

        line2 = ttk.Frame(self.toolbar)
        line2.pack(fill="x", pady=(6, 2))
        ttk.Label(line2, text=t("Загальний прогрес:")).pack(side="left")
        self.queue_pb = ttk.Progressbar(line2, length=220, maximum=100)
        self.queue_pb.pack(side="left", padx=6)
        self.lbl_queue = ttk.Label(line2, text="")
        self.lbl_queue.pack(side="left")
        ToolTip(self.queue_pb, t("Частка сконвертованих файлів серед усіх файлів у списку завдань — "
                                 "незалежно від того, що саме зараз запущено."))

    def _build_body(self):
        self.paned = ttk.PanedWindow(self.root, orient="vertical")
        self.paned.pack(fill="both", expand=True, padx=6, pady=4)

        tasks_lf = ttk.LabelFrame(self.paned, text=t("Завдання"), padding=4)
        self.list = ScrollableFrame(tasks_lf)
        self.list.pack(fill="both", expand=True)
        self.empty_lbl = ttk.Label(self.list.inner, foreground="#555555",
                                   text=t("Немає завдань. Натисніть «Додати завдання…», щоб почати."))
        self.paned.add(tasks_lf, weight=4)

        self.log_frame = tk.Frame(self.paned, bd=1, relief="sunken")
        self.log_header = tk.Frame(self.log_frame)
        self.log_header.pack(fill="x")
        self.btn_log = ttk.Button(self.log_header, width=22, command=self.toggle_log)
        self.btn_log.pack(side="left", padx=2, pady=2)
        ToolTip(self.btn_log, t("Згорнути або розгорнути журнал, щоб звільнити місце для завдань"))
        b = ttk.Button(self.log_header, text=t("Зберегти журнал…"), command=self.save_log)
        b.pack(side="left", padx=2)
        ToolTip(b, t("Зберегти вміст журналу у файл .log"))
        ttk.Button(self.log_header, text=t("Очистити"), command=self.clear_log).pack(side="left", padx=2)
        self.lbl_log_errors = tk.Label(self.log_header, fg=ERROR_COLOR, font=self.bold_font)
        self.lbl_log_errors.pack(side="right", padx=8)

        self.log_body = tk.Frame(self.log_frame)
        self.log_body.pack(fill="both", expand=True)
        self.log_text = tk.Text(self.log_body, height=8, wrap="word", state="disabled",
                                font=("Consolas", 9), relief="flat")
        vsb = ttk.Scrollbar(self.log_body, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=vsb.set)
        self.log_text.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.log_text.tag_configure("error", foreground=ERROR_COLOR)
        self.log_text.tag_configure("warn", foreground="#b35c00")
        self.log_text.tag_configure("ok", foreground="#1a7f1a")
        self.log_text.tag_configure("time", foreground="#777777")
        self.paned.add(self.log_frame, weight=1)

    def _build_statusbar(self):
        self.statusbar = tk.Frame(self.root, bd=1, relief="sunken")
        self.statusbar.pack(side="bottom", fill="x")
        self.lbl_ffmpeg = tk.Label(self.statusbar, anchor="w", padx=4)
        self.lbl_ffmpeg.pack(side="left", fill="x", expand=True)
        tk.Label(self.statusbar, text=f"v{__version__}", padx=6).pack(side="right")
        self._update_ffmpeg_status()

    def _rebuild_rows(self):
        for row in self.rows.values():
            row.destroy()
        self.rows.clear()
        self.empty_lbl.pack_forget()
        if not self.tasks:
            self.empty_lbl.pack(pady=30)
        for i, task in enumerate(self.tasks, 1):
            row = TaskRow(self.list.inner, self, task, i, len(self.tasks), task.id in self.expanded)
            row.pack(fill="x", padx=2, pady=2)
            self.rows[task.id] = row

    # ================================================================ журнал

    def log(self, message: str, level: str = "info"):
        entry = (datetime.now(), message, level)
        self.log_entries.append(entry)
        if len(self.log_entries) > MAX_LOG_LINES:
            del self.log_entries[:len(self.log_entries) - MAX_LOG_LINES]
        self._append_log_line(*entry)
        if level == "error":
            self.error_count += 1
            self._update_log_header()
        try:
            with open(paths.log_file(), "a", encoding="utf-8") as fh:
                fh.write(f"{entry[0]:%Y-%m-%d %H:%M:%S} [{level}] {message}\n")
        except OSError:
            pass

    def _append_log_line(self, moment: datetime, message: str, level: str):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", moment.strftime("%H:%M:%S  "), ("time",))
        self.log_text.insert("end", message + "\n", (level,) if level != "info" else ())
        lines = int(self.log_text.index("end-1c").split(".")[0])
        if lines > MAX_LOG_LINES:
            self.log_text.delete("1.0", f"{lines - MAX_LOG_LINES}.0")
        self.log_text.configure(state="disabled")
        self.log_text.see("end")

    def _update_log_header(self):
        has_errors = self.error_count > 0
        arrow = "▸" if self.log_collapsed else "▾"
        self.btn_log.configure(text=f"{arrow} " + t("Журнал"))
        self.lbl_log_errors.configure(
            text=t("помилок: {count}").format(count=self.error_count) if has_errors else "")
        color = ERROR_BG if has_errors else self.root.cget("background")
        self.log_frame.configure(background=color, highlightthickness=2 if has_errors else 0,
                                 highlightbackground=ERROR_COLOR, highlightcolor=ERROR_COLOR)
        self.log_header.configure(background=color)

    def _clear_error_highlight(self):
        if self.error_count:
            self.error_count = 0
            self._update_log_header()

    def toggle_log(self):
        self.log_collapsed = not self.log_collapsed
        self.settings["log_collapsed"] = self.log_collapsed
        if not self.log_collapsed:
            self._clear_error_highlight()
        self._apply_log_state()
        self._save_settings()

    def _apply_log_state(self, initial: bool = False):
        """Згортання журналу: ховаємо текст і присуваємо роздільник донизу."""
        try:
            if self.log_collapsed:
                self.root.update_idletasks()
                height = self.paned.winfo_height()
                header = self.log_header.winfo_reqheight() + 6
                if not initial:
                    self._saved_sash = self.paned.sashpos(0)
                self.log_body.pack_forget()
                if height > header:
                    self.paned.sashpos(0, max(0, height - header))
            else:
                self.log_body.pack(fill="both", expand=True)
                if not initial:
                    # Після розгортання повертаємо роздільник туди, де він був.
                    self.root.update_idletasks()
                    height = self.paned.winfo_height()
                    header = self.log_header.winfo_reqheight() + 6
                    target = self._saved_sash or int(height * 0.7)
                    self.paned.sashpos(0, min(max(80, target), max(80, height - header - 60)))
                self._saved_sash = 0
        except tk.TclError:
            pass
        self._update_log_header()

    def save_log(self):
        if not self.log_entries:
            messagebox.showinfo(t("Журнал"), t("Журнал порожній."), parent=self.root)
            return
        path = filedialog.asksaveasfilename(
            parent=self.root, title=t("Зберегти журнал"), defaultextension=".log",
            initialfile=f"{APP_NAME}_{datetime.now():%Y%m%d_%H%M}.log",
            filetypes=[(t("Файли журналу"), "*.log"), (t("Текстові файли"), "*.txt"),
                       (t("Усі файли"), "*.*")])
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as fh:
                for moment, message, level in self.log_entries:
                    fh.write(f"{moment:%Y-%m-%d %H:%M:%S} [{level}] {message}\n")
        except OSError as exc:
            messagebox.showerror(t("Помилка"),
                                 t("Не вдалося зберегти журнал:\n{error}").format(error=exc),
                                 parent=self.root)
            return
        self.log(t("Журнал збережено у файл: {path}").format(path=path), "ok")

    def clear_log(self):
        self.log_entries.clear()
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")
        self._clear_error_highlight()

    # ================================================================ рушій

    def max_parallel(self) -> int:
        try:
            return max(1, min(64, int(self.v_parallel.get())))
        except (ValueError, tk.TclError):
            return 1

    def _on_parallel_change(self):
        n = self.max_parallel()
        self.v_parallel.set(str(n))
        if self.settings.get("max_parallel") != n:
            self.settings["max_parallel"] = n
            self._save_settings()
            self.log(t("Кількість паралельних процесів: {count}.").format(count=n), "info")
            self.engine.schedule()

    def _parallel_help(self):
        messagebox.showinfo(t("Паралельні процеси"), parallel_help_text(), parent=self.root)

    def _on_engine_change(self, task: Task, progress_only: bool):
        row = self.rows.get(task.id)
        if row is not None:
            row.refresh()
        if not progress_only:
            self._schedule_save()

    def _poll(self):
        try:
            self.engine.poll()
            self._update_indicators()
            for row in self.rows.values():
                if row.task.is_active:
                    row.refresh()
        finally:
            self.root.after(150, self._poll)

    def _update_indicators(self):
        stats = queue_stats(self.tasks)
        if stats.total:
            title = f"{stats.percent:.0f}% ({stats.processed}/{stats.total}) — {APP_TITLE}"
            text = t("Сконвертовано {processed} з {total} файлів ({percent}%)").format(
                processed=stats.processed, total=stats.total, percent=f"{stats.percent:.0f}")
            if stats.errors:
                text += "  ·  " + t("помилок: {count}").format(count=stats.errors)
            if stats.running:
                eta = queue_eta(self.tasks, parallel=self.max_parallel())
                if eta is not None:
                    text += "  ·  " + t("залишилось ~{time}").format(time=format_duration(eta))
        else:
            title = f"{APP_TITLE} {__version__}"
            text = t("Черга порожня")
        self.queue_pb["value"] = stats.percent
        self.lbl_queue.configure(text=text)
        if title != self._title:
            self._title = title
            self.root.title(title)

    # ================================================================ збереження

    def _schedule_save(self):
        if self._save_after is None:
            self._save_after = self.root.after(800, self._save_now)

    def _save_now(self):
        self._save_after = None
        try:
            store.save_tasks(self.tasks)
        except OSError as exc:
            self.log(t("Не вдалося зберегти чергу: {error}").format(error=exc), "error")

    def _save_settings(self):
        try:
            store.save_settings(self.settings)
        except OSError as exc:
            self.log(t("Не вдалося зберегти налаштування: {error}").format(error=exc), "error")

    # ================================================================ дії із завданнями

    def add_task(self):
        dlg = TaskDialog(self.root, self.presets, self.settings, None,
                         default_name=t("Завдання {number}").format(number=len(self.tasks) + 1))
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
        self.log(t("Додано завдання «{name}». Файлів: {count}.").format(
            name=task.name, count=len(task.files)), "info")
        if self.engine.is_busy():
            # Конвертація вже йде — нове завдання стає в кінець черги.
            self.engine.start_task(task)
        else:
            self.engine.prefetch_durations([task])

    def edit_task(self, task: Task):
        if task.is_active:
            messagebox.showinfo(t("Редагування"),
                                t("Спершу зупиніть конвертування цього завдання."), parent=self.root)
            return
        dlg = TaskDialog(self.root, self.presets, self.settings, task)
        self.root.wait_window(dlg)
        self._save_settings()
        result = dlg.result
        if result is None:
            return
        task.name = result.name
        task.files = result.files
        task.out_dir = result.out_dir
        task.prefix = result.prefix
        task.settings = result.settings
        task.preset_name = result.preset_name
        if task.status == TASK_DONE and any(f.status != FILE_DONE for f in task.files):
            task.status = TASK_IDLE
        assign_output_paths(task)
        self._rebuild_rows()
        self._schedule_save()
        self.engine.prefetch_durations([task])
        self.log(t("Завдання «{name}» змінено.").format(name=task.name), "info")

    def toggle_task(self, task: Task):
        if task.is_active:
            self.engine.stop_task(task)
            return
        if not self._require_ffmpeg():
            return
        if task.files and all(f.status == FILE_DONE for f in task.files):
            if not messagebox.askyesno(
                    t("Повторна конвертація"),
                    t("Усі файли завдання «{name}» вже сконвертовано.\n"
                      "Сконвертувати їх заново (готові файли буде перезаписано)?").format(name=task.name),
                    parent=self.root):
                return
        self.engine.start_task(task)

    def start_all(self):
        if not self._require_ffmpeg():
            return
        started = self.engine.start_all()
        if not started and not self.engine.is_busy():
            messagebox.showinfo(t("Запустити всі"),
                                t("Немає завдань для запуску (список порожній або всі завдання вже готові)."),
                                parent=self.root)

    def stop_all(self):
        if self.engine.is_busy():
            self.engine.stop_all()

    def delete_task(self, task: Task):
        text = t("Видалити завдання «{name}» зі списку?\n\n"
                 "Вихідні та готові файли на диску не видаляються.").format(name=task.name)
        if task.is_active:
            text += "\n\n" + t("Конвертування цього завдання буде зупинено.")
        if not messagebox.askyesno(t("Видалити завдання"), text, parent=self.root):
            return
        if task.is_active:
            self.engine.stop_task(task)
        if task in self.tasks:
            self.tasks.remove(task)
        self.expanded.discard(task.id)
        self._rebuild_rows()
        self._schedule_save()
        self.log(t("Завдання «{name}» видалено зі списку.").format(name=task.name), "info")

    def move_task(self, task: Task, delta: int):
        i = self.tasks.index(task)
        j = i + delta
        if not 0 <= j < len(self.tasks):
            return
        self.tasks[i], self.tasks[j] = self.tasks[j], self.tasks[i]
        self._rebuild_rows()
        self._schedule_save()

    def remove_finished(self):
        done = [task for task in self.tasks if task.status == TASK_DONE]
        if not done:
            messagebox.showinfo(t("Черга"), t("Немає повністю завершених завдань."), parent=self.root)
            return
        if not messagebox.askyesno(t("Черга"),
                                   t("Прибрати зі списку завершені завдання ({count})?\n"
                                     "Файли на диску не видаляються.").format(count=len(done)),
                                   parent=self.root):
            return
        for task in done:
            self.tasks.remove(task)
        self._rebuild_rows()
        self._schedule_save()

    def open_folder(self, task: Task):
        path = task.out_dir
        if path and os.path.isdir(path):
            os.startfile(path)
        else:
            messagebox.showinfo(t("Тека"),
                                t("Тека ще не існує:\n{path}\n\n"
                                  "Вона буде створена під час конвертування першого файлу.").format(path=path),
                                parent=self.root)

    # ================================================================ ffmpeg

    def _update_ffmpeg_status(self):
        if ffmpeg_tools.ffmpeg_available():
            version = ffmpeg_tools.ffmpeg_version() or "ffmpeg"
            self.lbl_ffmpeg.configure(text=f"ffmpeg: {version}  ({paths.bin_dir()})", fg="#000000")
        else:
            self.lbl_ffmpeg.configure(
                text=t("ffmpeg не знайдено в {path} — конвертація недоступна").format(path=paths.bin_dir()),
                fg=ERROR_COLOR)

    def _startup_ffmpeg_check(self):
        if not ffmpeg_tools.ffmpeg_available():
            ensure_ffmpeg(self.root, self.log)
            self._update_ffmpeg_status()
            if ffmpeg_tools.ffmpeg_available():
                self.engine.prefetch_durations()

    def _require_ffmpeg(self) -> bool:
        if ffmpeg_tools.ffmpeg_available():
            return True
        ok = ensure_ffmpeg(self.root, self.log, reason=t("Для конвертування потрібен ffmpeg."))
        self._update_ffmpeg_status()
        return ok

    def _check_ffmpeg_manual(self):
        if ffmpeg_tools.ffmpeg_available():
            messagebox.showinfo("ffmpeg",
                                t("ffmpeg знайдено:\n{version}\n\nТека: {path}").format(
                                    version=ffmpeg_tools.ffmpeg_version(), path=paths.bin_dir()),
                                parent=self.root)
        else:
            ensure_ffmpeg(self.root, self.log)
        self._update_ffmpeg_status()

    def _open_bin(self):
        os.makedirs(paths.bin_dir(), exist_ok=True)
        os.startfile(paths.bin_dir())

    def _about(self):
        lines = [
            APP_TITLE,
            t("Версія: {version} від {date}").format(version=__version__, date=VERSION_DATE),
            t("Дата збірки: {date}").format(date=buildinfo.build_date()),
            "" if buildinfo.is_frozen() else t("(запущено з вихідних кодів)"),
            "",
            t("Конвертер відео у формат H.264 — графічна оболонка для ffmpeg."),
            "",
            t("Автор: {author}").format(author=AUTHOR),
            t("ffmpeg: {path}").format(path=paths.bin_dir()),
            t("Дані програми: {path}").format(path=paths.data_dir()),
        ]
        messagebox.showinfo(t("Про програму"), "\n".join(x for x in lines if x is not None),
                            parent=self.root)

    # ================================================================ вихід

    def _on_close(self):
        if self.engine.is_busy():
            if not messagebox.askyesno(
                    t("Вихід"),
                    t("Конвертування ще триває. Зупинити його та вийти?\n\n"
                      "Недописані файли буде видалено, завдання залишаться в списку як незавершені."),
                    parent=self.root):
                return
            self.engine.shutdown()
        try:
            self.settings["geometry"] = self.root.geometry()
            self.settings["max_parallel"] = self.max_parallel()
            self.settings["log_collapsed"] = self.log_collapsed
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
    try:
        root.iconbitmap(default=paths.icon_file())
    except tk.TclError:
        pass
    # Колесо миші над списками й лічильниками не повинно випадково змінювати значення —
    # воно прокручує панель налаштувань.
    for cls in ("TCombobox", "TSpinbox"):
        root.unbind_class(cls, "<MouseWheel>")
    MainWindow(root)
    root.mainloop()
