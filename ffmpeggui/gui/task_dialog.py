"""Вікно «Додати / Редагувати завдання»."""

from __future__ import annotations

import os
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from .. import ffmpeg_tools
from ..i18n import t
from ..models import (
    AUDIO_CODECS,
    CONTAINERS,
    FILE_STATUS_LABELS,
    PIX_FMTS,
    TUNES,
    VIDEO_EXTENSIONS,
    X264_PRESET_NAMES,
    X264_PRESETS,
    ConvSettings,
    FileItem,
    Task,
    effective_settings,
)
from ..store import PresetStore
from .widgets import Collapsible, ScrollableFrame, ToolTip, hint, safe_geometry

FPS_VALUES = ["23.976", "24", "25", "29.97", "30", "48", "50", "59.94", "60"]
BITRATE_VALUES = ["96", "128", "160", "192", "256", "320"]
INVALID_NAME_CHARS = set('<>:"/\\|?*')


def _label_for(options, value):
    for v, label in options:
        if v == value:
            return t(label)
    return t(options[0][1])


def _value_for(options, label):
    for v, lab in options:
        if t(lab) == label:
            return v
    return options[0][0]


def _labels(options):
    return [t(label) for _, label in options]


class TaskDialog(tk.Toplevel):
    def __init__(self, master, presets: PresetStore, app_settings: dict,
                 task: Task | None = None, default_name: str = "Завдання",
                 known_out_dirs: set[str] | None = None):
        super().__init__(master)
        self.presets = presets
        self.app_settings = app_settings
        self.task = task
        self.known_out_dirs = known_out_dirs or set()
        self.result: Task | None = None
        self.title(t("Редагування завдання") if task else t("Нове завдання"))
        self.transient(master)
        self.geometry(safe_geometry(self.app_settings.get("dialog_geometry"), "1240x780"))
        self.minsize(1000, 600)

        if task:
            self.files = [FileItem.from_dict(f.to_dict()) for f in task.files]
            settings = task.settings.copy()
        else:
            self.files = []
            settings = presets.get(app_settings.get("last_preset", "")) or ConvSettings()

        self._src_dims: tuple[int, int] | None = None
        self._probed_path: str | None = None

        self.v_name = tk.StringVar(value=task.name if task else default_name)
        self.v_out = tk.StringVar(value=task.out_dir if task else "")
        self.v_prefix = tk.StringVar(value=task.prefix if task else app_settings.get("default_prefix", "h264_"))
        self.v_recursive = tk.BooleanVar(value=bool(app_settings.get("recursive_scan")))
        # Завдання пам'ятає, з якого пресету взяті його налаштування.
        if task:
            initial_preset = task.preset_name if presets.get(task.preset_name) else ""
        else:
            last_preset = app_settings.get("last_preset", "")
            initial_preset = last_preset if presets.get(last_preset) else ""
        self.v_preset = tk.StringVar(value=initial_preset)
        self._preset_baseline = presets.get(initial_preset) if initial_preset else None
        self._make_setting_vars()

        self._build()
        self._apply_settings(settings)
        self._refresh_files()

        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.bind("<Escape>", lambda e: self._cancel())
        self.grab_set()
        self.focus_set()

    # ================================================================ змінні

    def _make_setting_vars(self):
        self.v_crf = tk.StringVar()
        self.v_xpreset = tk.StringVar()
        self.v_res_mode = tk.StringVar()
        self.v_res_master = tk.StringVar()
        self.v_w = tk.StringVar()
        self.v_h = tk.StringVar()
        self.v_fps_mode = tk.StringVar()
        self.v_fps = tk.StringVar()
        self.v_acodec = tk.StringVar()
        self.v_ab_mode = tk.StringVar()
        self.v_ab = tk.StringVar()
        self.v_keyint = tk.StringVar()
        self.v_minkey = tk.StringVar()
        self.v_pix = tk.StringVar()
        self.v_tune = tk.StringVar()
        self.v_container = tk.StringVar()
        self.v_faststart = tk.BooleanVar()
        self.v_extra = tk.StringVar()

        for var in (self.v_res_mode, self.v_res_master, self.v_fps_mode,
                    self.v_acodec, self.v_ab_mode, self.v_xpreset):
            var.trace_add("write", lambda *_: self._update_states())
        self.v_res_master.trace_add("write", lambda *_: self._recalc())
        self.v_res_mode.trace_add("write", lambda *_: self._recalc())
        self.v_w.trace_add("write", lambda *_: self.v_res_master.get() == "width" and self._recalc())
        self.v_h.trace_add("write", lambda *_: self.v_res_master.get() == "height" and self._recalc())
        self.v_prefix.trace_add("write", lambda *_: self._update_example())
        self.v_container.trace_add("write", lambda *_: self._update_example())
        for var in (self.v_crf, self.v_xpreset, self.v_res_mode, self.v_res_master, self.v_w,
                    self.v_h, self.v_fps_mode, self.v_fps, self.v_acodec, self.v_ab_mode,
                    self.v_ab, self.v_keyint, self.v_minkey, self.v_pix, self.v_tune,
                    self.v_container, self.v_faststart, self.v_extra):
            var.trace_add("write", lambda *_: self._update_preset_marker())

    def _apply_settings(self, s: ConvSettings):
        self.v_crf.set(str(s.crf))
        self.v_xpreset.set(s.preset if s.preset in X264_PRESET_NAMES else "slow")
        self.v_w.set(str(s.width))
        self.v_h.set(str(s.height))
        self.v_res_master.set(s.res_master)
        self.v_res_mode.set(s.res_mode)
        self.v_fps.set(s.fps)
        self.v_fps_mode.set(s.fps_mode)
        self.v_acodec.set(_label_for(AUDIO_CODECS, s.audio_codec))
        self.v_ab.set(str(s.audio_bitrate))
        self.v_ab_mode.set(s.audio_bitrate_mode)
        self.v_keyint.set(str(s.keyint))
        self.v_minkey.set(str(s.min_keyint))
        self.v_pix.set(_label_for(PIX_FMTS, s.pix_fmt))
        self.v_tune.set(_label_for(TUNES, s.tune))
        self.v_container.set(s.container if s.container in CONTAINERS else "mp4")
        self.v_faststart.set(s.faststart)
        self.v_extra.set(s.extra_args)
        self._update_states()
        self._update_preset_marker()

    # ================================================================ побудова

    def _build(self):
        outer = ttk.Frame(self, padding=8)
        outer.pack(fill="both", expand=True)

        top = ttk.Frame(outer)
        top.pack(fill="x")
        ttk.Label(top, text=t("Назва завдання:")).pack(side="left")
        ttk.Entry(top, textvariable=self.v_name, width=50).pack(side="left", padx=6)

        bottom = ttk.Frame(outer)
        bottom.pack(side="bottom", fill="x", pady=(8, 0))
        ttk.Button(bottom, text=t("Скасувати"), command=self._cancel).pack(side="right")
        ttk.Button(bottom, text=t("Зберегти"), command=self._ok).pack(side="right", padx=6)

        body = ttk.Frame(outer)
        body.pack(fill="both", expand=True, pady=(8, 0))
        body.columnconfigure(0, weight=3)
        body.columnconfigure(1, weight=2, minsize=540)
        body.rowconfigure(0, weight=1)

        left = ttk.Frame(body)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        right = ScrollableFrame(body)
        right.grid(row=0, column=1, sticky="nsew")

        self._build_files(left)
        self._build_output(left)
        self._build_presets(right.inner)
        self._build_video(right.inner)
        self._build_audio(right.inner)
        self._build_advanced(right.inner)

    # ---------------------------------------------------------------- файли

    def _build_files(self, parent):
        lf = ttk.LabelFrame(parent, text=t("Вихідні файли"), padding=6)
        lf.pack(fill="both", expand=True)
        lf.columnconfigure(0, weight=1)
        lf.rowconfigure(0, weight=1)

        cols = ("n", "name", "folder", "status")
        self.tree = ttk.Treeview(lf, columns=cols, show="headings", selectmode="extended")
        for col, title, width, stretch in (("n", t("№"), 40, False), ("name", t("Файл"), 220, True),
                                           ("folder", t("Тека"), 260, True),
                                           ("status", t("Стан"), 100, False)):
            self.tree.heading(col, text=title)
            self.tree.column(col, width=width, stretch=stretch, anchor="e" if col == "n" else "w")
        vsb = ttk.Scrollbar(lf, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        self.tree.bind("<Delete>", lambda e: self._remove())

        btns = ttk.Frame(lf)
        btns.grid(row=0, column=2, sticky="n", padx=(8, 0))
        b = ttk.Button(btns, text=t("Додати файли…"), command=self._add_files)
        b.pack(fill="x", pady=2)
        ToolTip(b, t("Вибрати один чи кілька файлів. Можна додати будь-який файл, "
                     "який здатен прочитати ffmpeg."))
        b = ttk.Button(btns, text=t("Додати теку…"), command=self._add_folder)
        b.pack(fill="x", pady=2)
        ToolTip(b, t("Додати всі відеофайли з теки (mp4, mov, mkv, avi, mts, m2ts тощо)."))
        ttk.Checkbutton(btns, text=t("разом з підтеками"),
                        variable=self.v_recursive).pack(anchor="w", pady=(0, 6))
        ttk.Separator(btns).pack(fill="x", pady=4)
        ttk.Button(btns, text=t("Вилучити"), command=self._remove).pack(fill="x", pady=2)
        ttk.Button(btns, text=t("▲ Вгору"), command=lambda: self._move(-1)).pack(fill="x", pady=2)
        ttk.Button(btns, text=t("▼ Вниз"), command=lambda: self._move(1)).pack(fill="x", pady=2)
        ttk.Button(btns, text=t("За назвою"), command=self._sort_by_name).pack(fill="x", pady=2)
        ttk.Separator(btns).pack(fill="x", pady=4)
        ttk.Button(btns, text=t("Очистити"), command=self._clear).pack(fill="x", pady=2)

        self.lbl_count = ttk.Label(lf, text="")
        self.lbl_count.grid(row=1, column=0, sticky="w", pady=(4, 0))

    def _build_output(self, parent):
        lf = ttk.LabelFrame(parent, text=t("Куди зберігати"), padding=6)
        lf.pack(fill="x", pady=(8, 0))
        lf.columnconfigure(1, weight=1)

        ttk.Label(lf, text=t("Тека для готових файлів:")).grid(row=0, column=0, sticky="w")
        ttk.Entry(lf, textvariable=self.v_out).grid(row=0, column=1, sticky="we", padx=4)
        ttk.Button(lf, text=t("Огляд…"), command=self._browse_out).grid(row=0, column=2)

        ttk.Label(lf, text=t("Префікс імені:")).grid(row=1, column=0, sticky="w", pady=(6, 0))
        pf = ttk.Frame(lf)
        pf.grid(row=1, column=1, columnspan=2, sticky="we", pady=(6, 0))
        e = ttk.Entry(pf, textvariable=self.v_prefix, width=20)
        e.pack(side="left", padx=4)
        ToolTip(e, t("Текст, що додається на початок імені кожного готового файлу. "
                     "Можна залишити порожнім."))
        self.lbl_example = ttk.Label(pf, text="")
        self.lbl_example.pack(side="left", padx=8)

        hint(lf, t("Якщо кілька файлів завдання отримають однакове ім'я (наприклад, з різних тек), "
                   "до імені додається суфікс _000, _001, _002 …"), wrap=560).grid(
            row=2, column=0, columnspan=3, sticky="w", pady=(6, 0))

    # ---------------------------------------------------------------- пресети

    def _build_presets(self, parent):
        lf = ttk.LabelFrame(parent, text=t("Пресет налаштувань"), padding=6)
        lf.pack(fill="x", padx=(0, 4), pady=(0, 6))
        lf.columnconfigure(2, weight=1)
        self.cb_preset = ttk.Combobox(lf, textvariable=self.v_preset, state="readonly",
                                      values=self.presets.names(), width=32)
        self.cb_preset.grid(row=0, column=0, sticky="w")
        self.cb_preset.bind("<<ComboboxSelected>>", lambda e: self._load_preset())
        self.lbl_preset_state = ttk.Label(lf, text="", foreground="#b35c00")
        self.lbl_preset_state.grid(row=0, column=1, columnspan=2, sticky="w", padx=(6, 0))
        ToolTip(self.lbl_preset_state,
                t("Налаштування нижче відрізняються від збережених у цьому пресеті. "
                  "Щоб оновити сам пресет, натисніть «Зберегти як пресет…» і підтвердіть "
                  "перезапис під тим самим іменем."))
        ttk.Button(lf, text=t("Зберегти як пресет…"), command=self._save_preset).grid(
            row=1, column=0, sticky="w", pady=(6, 0))
        ttk.Button(lf, text=t("Видалити пресет"), command=self._delete_preset).grid(
            row=1, column=1, sticky="w", padx=6, pady=(6, 0))
        hint(lf, t("Пресет зберігає всі налаштування якості нижче (базові та розширені). "
                   "Вибір пресету одразу заповнює поля."), wrap=480).grid(
            row=2, column=0, columnspan=3, sticky="w", pady=(6, 0))

    # ---------------------------------------------------------------- відео

    def _build_video(self, parent):
        lf = ttk.LabelFrame(parent, text=t("Відео (H.264 / libx264)"), padding=6)
        lf.pack(fill="x", padx=(0, 4), pady=(0, 6))
        lf.columnconfigure(1, weight=1)

        r = 0
        ttk.Label(lf, text=t("Якість (CRF):")).grid(row=r, column=0, sticky="w")
        sp = ttk.Spinbox(lf, from_=0, to=51, width=6, textvariable=self.v_crf)
        sp.grid(row=r, column=1, sticky="w")
        ToolTip(sp, t("CRF (Constant Rate Factor) — рівень якості. 0 — без втрат, 17–18 — візуально "
                      "без втрат, 23 — типове значення ffmpeg. Менше число = краща якість і більший файл."))
        r += 1
        hint(lf, t("0–51; менше = краща якість і більший файл. 17–18 — візуально без втрат."),
             wrap=330).grid(row=r, column=1, sticky="w")

        r += 1
        ttk.Label(lf, text=t("Швидкість (preset):")).grid(row=r, column=0, sticky="w", pady=(6, 0))
        cb = ttk.Combobox(lf, textvariable=self.v_xpreset, values=X264_PRESET_NAMES,
                          state="readonly", width=11)
        cb.grid(row=r, column=1, sticky="w", pady=(6, 0))
        ToolTip(cb, t("Повільніші пресети стискають ефективніше (менший файл за тієї самої якості), "
                      "але кодують довше. На якість при заданому CRF впливає мало."))
        r += 1
        self.lbl_preset_desc = hint(lf, "", wrap=330)
        self.lbl_preset_desc.grid(row=r, column=1, sticky="w")

        r += 1
        ttk.Label(lf, text=t("Роздільність:")).grid(row=r, column=0, sticky="w", pady=(8, 0))
        rf = ttk.Frame(lf)
        rf.grid(row=r, column=1, sticky="w", pady=(8, 0))
        ttk.Radiobutton(rf, text=t("Як є"), value="source", variable=self.v_res_mode).pack(side="left")
        ttk.Radiobutton(rf, text=t("Власна"), value="custom",
                        variable=self.v_res_mode).pack(side="left", padx=8)

        r += 1
        cf = ttk.Frame(lf)
        cf.grid(row=r, column=1, sticky="w")
        ttk.Label(cf, text=t("Головне поле:")).grid(row=0, column=0, sticky="w")
        self.rb_master_w = ttk.Radiobutton(cf, text=t("Ширина"), value="width", variable=self.v_res_master)
        self.rb_master_w.grid(row=0, column=1, sticky="w", padx=4)
        self.rb_master_h = ttk.Radiobutton(cf, text=t("Висота"), value="height", variable=self.v_res_master)
        self.rb_master_h.grid(row=0, column=2, sticky="w")
        ef = ttk.Frame(cf)
        ef.grid(row=1, column=0, columnspan=3, sticky="w", pady=(4, 0))
        ttk.Label(ef, text=t("Ширина")).pack(side="left")
        self.e_w = ttk.Entry(ef, textvariable=self.v_w, width=7)
        self.e_w.pack(side="left", padx=4)
        ttk.Label(ef, text=t("×  Висота")).pack(side="left")
        self.e_h = ttk.Entry(ef, textvariable=self.v_h, width=7)
        self.e_h.pack(side="left", padx=4)
        ttk.Label(ef, text=t("px")).pack(side="left")
        self.lbl_dims = hint(cf, "", wrap=330)
        self.lbl_dims.grid(row=2, column=0, columnspan=3, sticky="w", pady=(2, 0))
        for entry in (self.e_w, self.e_h):
            ToolTip(entry, t("Введіть значення в головне поле — друге розраховується автоматично "
                             "зі збереженням пропорцій кожного вихідного файлу."))

        r += 1
        ttk.Label(lf, text=t("Частота кадрів:")).grid(row=r, column=0, sticky="w", pady=(8, 0))
        ff = ttk.Frame(lf)
        ff.grid(row=r, column=1, sticky="w", pady=(8, 0))
        ttk.Radiobutton(ff, text=t("Як є"), value="source", variable=self.v_fps_mode).pack(side="left")
        ttk.Radiobutton(ff, text=t("Власна:"), value="custom",
                        variable=self.v_fps_mode).pack(side="left", padx=(8, 2))
        self.cb_fps = ttk.Combobox(ff, textvariable=self.v_fps, values=FPS_VALUES, width=7)
        self.cb_fps.pack(side="left")
        ttk.Label(ff, text=t("кадр/с")).pack(side="left", padx=4)
        ToolTip(self.cb_fps, t("Можна вибрати зі списку або ввести своє значення "
                               "(наприклад 25 або 29.97)."))

    # ---------------------------------------------------------------- аудіо

    def _build_audio(self, parent):
        lf = ttk.LabelFrame(parent, text=t("Аудіо"), padding=6)
        lf.pack(fill="x", padx=(0, 4), pady=(0, 6))
        lf.columnconfigure(1, weight=1)

        ttk.Label(lf, text=t("Кодек:")).grid(row=0, column=0, sticky="w")
        cb = ttk.Combobox(lf, textvariable=self.v_acodec, values=_labels(AUDIO_CODECS),
                          state="readonly", width=30)
        cb.grid(row=0, column=1, sticky="w")

        ttk.Label(lf, text=t("Бітрейт:")).grid(row=1, column=0, sticky="w", pady=(6, 0))
        bf = ttk.Frame(lf)
        bf.grid(row=1, column=1, sticky="w", pady=(6, 0))
        self.rb_ab_src = ttk.Radiobutton(bf, text=t("Як є"), value="source", variable=self.v_ab_mode)
        self.rb_ab_src.pack(side="left")
        ToolTip(self.rb_ab_src, t("Використати бітрейт звуку вихідного файлу "
                                  "(якщо його вдасться визначити)."))
        self.rb_ab_custom = ttk.Radiobutton(bf, text=t("Власний:"), value="custom", variable=self.v_ab_mode)
        self.rb_ab_custom.pack(side="left", padx=(8, 2))
        self.cb_ab = ttk.Combobox(bf, textvariable=self.v_ab, values=BITRATE_VALUES, width=6)
        self.cb_ab.pack(side="left")
        ttk.Label(bf, text=t("кбіт/с")).pack(side="left", padx=4)

        hint(lf, t("«Копіювати без перекодування» зберігає звук без змін (бітрейт не застосовується). "
                   "Деякі кодеки (наприклад PCM) не підтримуються контейнером MP4 — тоді виберіть "
                   "контейнер MOV у розширених налаштуваннях."), wrap=480).grid(
            row=2, column=0, columnspan=2, sticky="w", pady=(6, 0))

    # ---------------------------------------------------------------- розширені

    def _build_advanced(self, parent):
        col = Collapsible(parent, t("Розширені налаштування"), expanded=False)
        col.pack(fill="x", padx=(0, 4), pady=(0, 6))
        b = col.body
        b.columnconfigure(1, weight=1)
        r = 0

        def row(label, widget, text):
            nonlocal r
            ttk.Label(b, text=label).grid(row=r, column=0, sticky="nw", pady=(6, 0))
            widget.grid(row=r, column=1, sticky="w", pady=(6, 0))
            r += 1
            hint(b, text, wrap=330).grid(row=r, column=1, sticky="w")
            r += 1

        row(t("Інтервал ключових\nкадрів (keyint):"),
            ttk.Spinbox(b, from_=0, to=1000, width=7, textvariable=self.v_keyint),
            t("Як часто у відео трапляються повні (незалежні) кадри. Менший інтервал дає плавніше "
              "перемотування/скрабінг при монтажі, але трохи збільшує розмір файлу. 30 ≈ один ключовий "
              "кадр на секунду при 30 кадр/с. 0 — не задавати (типове значення x264 — 250)."))
        row(t("Мінімальний інтервал\n(min-keyint):"),
            ttk.Spinbox(b, from_=1, to=1000, width=7, textvariable=self.v_minkey),
            t("Найменша відстань між ключовими кадрами. 1 дозволяє кодеку ставити ключовий кадр "
              "на будь-якій зміні сцени."))
        row(t("Формат пікселів\n(pix_fmt):"),
            ttk.Combobox(b, textvariable=self.v_pix, values=_labels(PIX_FMTS),
                         state="readonly", width=26),
            t("Спосіб кодування кольору. yuv420p забезпечує сумісність відео з переважною більшістю "
              "програм монтажу та програвачів — змінювати без потреби не варто. yuv422p/yuv444p "
              "зберігають більше інформації про колір, але можуть не відкриватися в деяких програмах."))
        row(t("Оптимізація (tune):"),
            ttk.Combobox(b, textvariable=self.v_tune, values=_labels(TUNES),
                         state="readonly", width=32),
            t("Підлаштовує кодек під тип вмісту. Зазвичай не потрібна — залиште «Немає»."))
        row(t("Контейнер:"),
            ttk.Combobox(b, textvariable=self.v_container, values=CONTAINERS, state="readonly", width=6),
            t("Тип вихідного файлу. MP4 — найсумісніший. MOV — якщо копіюєте звук у форматі PCM. "
              "MKV — універсальний, але гірше підтримується програмами монтажу."))
        row(t("Швидкий старт:"),
            ttk.Checkbutton(b, text="-movflags +faststart", variable=self.v_faststart),
            t("Переносить службову інформацію на початок файлу, щоб відео починало грати ще до повного "
              "завантаження (браузер, мережа). Для монтажу не потрібно. Лише для MP4/MOV."))
        row(t("Додаткові параметри\nffmpeg:"),
            ttk.Entry(b, textvariable=self.v_extra, width=36),
            t("Для досвідчених користувачів: довільні параметри ffmpeg, що додаються перед іменем "
              "вихідного файлу. Приклад: -map_metadata 0. Залиште порожнім, якщо не впевнені."))

    # ================================================================ стан полів

    def _update_states(self):
        if not hasattr(self, "e_w"):
            return
        custom = self.v_res_mode.get() == "custom"
        master = self.v_res_master.get()
        for rb in (self.rb_master_w, self.rb_master_h):
            rb.state(["!disabled"] if custom else ["disabled"])
        if custom:
            self.e_w.configure(state="normal" if master == "width" else "readonly")
            self.e_h.configure(state="normal" if master == "height" else "readonly")
        else:
            self.e_w.configure(state="disabled")
            self.e_h.configure(state="disabled")
        self.cb_fps.configure(state="normal" if self.v_fps_mode.get() == "custom" else "disabled")

        codec = _value_for(AUDIO_CODECS, self.v_acodec.get())
        can_bitrate = codec in ("aac", "mp3")
        for rb in (self.rb_ab_src, self.rb_ab_custom):
            rb.state(["!disabled"] if can_bitrate else ["disabled"])
        self.cb_ab.configure(state="normal" if can_bitrate and self.v_ab_mode.get() == "custom" else "disabled")

        desc = dict(X264_PRESETS).get(self.v_xpreset.get(), "")
        self.lbl_preset_desc.configure(text=t(desc) if desc else "")
        self._update_dims_label()

    def _update_dims_label(self):
        if not hasattr(self, "lbl_dims"):
            return
        if self._src_dims:
            w, h = self._src_dims
            text = t("Розмір першого файлу: {w}×{h}. Для інших файлів пропорції беруться "
                     "з кожного файлу окремо.").format(w=w, h=h)
        elif self.files and not ffmpeg_tools.ffmpeg_available():
            text = t("Друге поле буде розраховано автоматично для кожного файлу (ffmpeg не знайдено).")
        elif self.files:
            text = t("Друге поле буде розраховано автоматично для кожного файлу.")
        else:
            text = t("Додайте файли, щоб побачити розрахунок другого поля.")
        self.lbl_dims.configure(text=text)

    def _recalc(self):
        if self.v_res_mode.get() != "custom":
            return
        master = self.v_res_master.get()
        slave_var = self.v_h if master == "width" else self.v_w
        if not self._src_dims:
            slave_var.set(t("авто"))
            return
        sw, sh = self._src_dims
        try:
            value = int((self.v_w if master == "width" else self.v_h).get())
        except ValueError:
            slave_var.set("")
            return
        if master == "width":
            other = round(value * sh / sw / 2) * 2
        else:
            other = round(value * sw / sh / 2) * 2
        slave_var.set(str(max(2, other)))

    def _maybe_probe(self):
        if not self.files or not ffmpeg_tools.ffmpeg_available():
            self._src_dims = None
            self._probed_path = None
            self._update_dims_label()
            return
        path = self.files[0].src
        if path == self._probed_path:
            return
        self._probed_path = path
        self._src_dims = None
        self.lbl_dims.configure(text=t("Визначення розміру першого файлу…"))
        holder: dict = {}

        def work():
            try:
                info = ffmpeg_tools.probe(path)
                holder["dims"] = (info.width, info.height) if info.width and info.height else None
            except Exception:  # noqa: BLE001
                holder["dims"] = None
            holder["done"] = True

        threading.Thread(target=work, daemon=True).start()
        self.after(100, self._probe_poll, path, holder)

    def _probe_poll(self, path, holder):
        try:
            if not self.winfo_exists():
                return
        except tk.TclError:
            return
        if not holder.get("done"):
            self.after(100, self._probe_poll, path, holder)
            return
        if path != self._probed_path:
            return
        self._src_dims = holder.get("dims")
        self._update_dims_label()
        self._recalc()

    # ================================================================ файли: дії

    def _refresh_files(self, select: set[str] | None = None):
        self.tree.delete(*self.tree.get_children())
        for i, f in enumerate(self.files, 1):
            self.tree.insert("", "end", iid=f.id, values=(
                i, os.path.basename(f.src), os.path.dirname(f.src),
                t(FILE_STATUS_LABELS.get(f.status, ""))))
        if select:
            keep = [i for i in select if self.tree.exists(i)]
            self.tree.selection_set(keep)
            if keep:
                self.tree.see(keep[0])
        self.lbl_count.configure(text=t("Файлів: {count}").format(count=len(self.files)))
        self._update_example()
        self._maybe_probe()

    def _update_example(self):
        if not hasattr(self, "lbl_example"):
            return
        stem = Path(self.files[0].src).stem if self.files else "C0001"
        self.lbl_example.configure(text=t("Приклад: {name}").format(
            name=f"{self.v_prefix.get()}{stem}.{self.v_container.get() or 'mp4'}"))

    def _add_paths(self, paths_to_add: list[str]) -> int:
        existing = {os.path.normcase(os.path.abspath(f.src)) for f in self.files}
        added = 0
        for p in paths_to_add:
            p = os.path.abspath(p)
            key = os.path.normcase(p)
            if key in existing or not os.path.isfile(p):
                continue
            existing.add(key)
            self.files.append(FileItem(src=p))
            added += 1
        if added:
            if not self.v_out.get().strip():
                self.v_out.set(os.path.join(os.path.dirname(self.files[0].src), "h264_master"))
            self._refresh_files()
        return added

    def _add_files(self):
        files = filedialog.askopenfilenames(
            parent=self, title=t("Виберіть відеофайли"),
            initialdir=self.app_settings.get("last_dir") or None,
            filetypes=[(t("Усі файли"), "*.*"),
                       (t("Відеофайли"), " ".join("*" + e for e in sorted(VIDEO_EXTENSIONS)))])
        if files:
            self.app_settings["last_dir"] = os.path.dirname(files[0])
            self._add_paths(list(files))

    def _add_folder(self):
        folder = filedialog.askdirectory(parent=self, title=t("Виберіть теку з відео"),
                                         initialdir=self.app_settings.get("last_dir") or None)
        if not folder:
            return
        folder = os.path.abspath(folder)
        self.app_settings["last_dir"] = folder
        # Теки з результатами (цього та інших завдань) не скануємо — інакше в список
        # потраплять уже сконвертовані файли.
        skip = {os.path.normcase(os.path.abspath(d))
                for d in self.known_out_dirs | {self.v_out.get().strip()} if d}
        found = []
        if self.v_recursive.get():
            for root, dirs, files in os.walk(folder):
                # Не скануємо теку з результатами, щоб не додати вже готові файли.
                dirs[:] = [d for d in dirs if os.path.normcase(os.path.join(root, d)) not in skip]
                dirs.sort(key=str.lower)
                for name in sorted(files, key=str.lower):
                    found.append(os.path.join(root, name))
        else:
            try:
                names = sorted(os.listdir(folder), key=str.lower)
            except OSError as exc:
                messagebox.showerror(t("Помилка"),
                                     t("Не вдалося прочитати теку:\n{error}").format(error=exc), parent=self)
                return
            found = [os.path.join(folder, n) for n in names]
        found = [p for p in found if os.path.isfile(p) and os.path.splitext(p)[1].lower() in VIDEO_EXTENSIONS]
        if not found:
            messagebox.showinfo(t("Нічого не знайдено"),
                                t("У теці не знайдено відеофайлів:\n{path}").format(path=folder), parent=self)
            return
        added = self._add_paths(found)
        if added < len(found):
            messagebox.showinfo(t("Додано файли"),
                                t("Знайдено файлів: {found}, додано: {added} "
                                  "(решта вже є в списку).").format(found=len(found), added=added),
                                parent=self)

    def _remove(self):
        sel = set(self.tree.selection())
        if not sel:
            return
        self.files = [f for f in self.files if f.id not in sel]
        self._refresh_files()

    def _move(self, delta: int):
        sel = set(self.tree.selection())
        if not sel:
            return
        idx = range(len(self.files)) if delta < 0 else range(len(self.files) - 1, -1, -1)
        for i in idx:
            j = i + delta
            if self.files[i].id in sel and 0 <= j < len(self.files) and self.files[j].id not in sel:
                self.files[i], self.files[j] = self.files[j], self.files[i]
        self._refresh_files(select=sel)

    def _sort_by_name(self):
        self.files.sort(key=lambda f: os.path.basename(f.src).lower())
        self._refresh_files(select=set(self.tree.selection()))

    def _clear(self):
        if self.files and messagebox.askyesno(t("Очистити"),
                                              t("Вилучити всі файли зі списку завдання?"), parent=self):
            self.files = []
            self._refresh_files()

    def _browse_out(self):
        initial = self.v_out.get().strip() or self.app_settings.get("last_out_dir") or None
        if initial and not os.path.isdir(initial):
            initial = os.path.dirname(initial) if os.path.isdir(os.path.dirname(initial)) else None
        folder = filedialog.askdirectory(parent=self, title=t("Тека для готових файлів"), initialdir=initial)
        if folder:
            self.v_out.set(os.path.abspath(folder))

    # ================================================================ пресети: дії

    def _update_preset_marker(self):
        """Позначка «(змінено)», якщо поля відрізняються від збереженого пресету."""
        if not hasattr(self, "lbl_preset_state"):
            return
        if not self.v_preset.get() or self._preset_baseline is None:
            self.lbl_preset_state.configure(text="")
            return
        try:
            changed = effective_settings(self._collect()) != effective_settings(self._preset_baseline)
        except ValueError:
            changed = True   # поле заповнене некоректно — точно не збігається з пресетом
        self.lbl_preset_state.configure(text=t("(змінено)") if changed else "")

    def _load_preset(self):
        name = self.v_preset.get()
        s = self.presets.get(name)
        if s:
            self._preset_baseline = s
            self._apply_settings(s)
            self.app_settings["last_preset"] = name
            self._update_preset_marker()

    def _save_preset(self):
        try:
            s = self._collect()
        except ValueError as exc:
            messagebox.showerror(t("Помилка в налаштуваннях"), str(exc), parent=self)
            return
        name = simpledialog.askstring(t("Зберегти пресет"), t("Назва пресету:"),
                                      initialvalue=self.v_preset.get(), parent=self)
        if not name or not name.strip():
            return
        name = name.strip()
        if name in self.presets.names() and not messagebox.askyesno(
                t("Пресет існує"),
                t("Пресет «{name}» вже існує. Перезаписати?").format(name=name), parent=self):
            return
        self.presets.put(name, s)
        self._preset_baseline = s
        self.cb_preset.configure(values=self.presets.names())
        self.v_preset.set(name)
        self.app_settings["last_preset"] = name
        self._update_preset_marker()

    def _delete_preset(self):
        name = self.v_preset.get()
        if not name or name not in self.presets.names():
            messagebox.showinfo(t("Пресет"), t("Спершу виберіть пресет у списку."), parent=self)
            return
        if messagebox.askyesno(t("Видалити пресет"),
                               t("Видалити пресет «{name}»?").format(name=name), parent=self):
            self.presets.delete(name)
            self.cb_preset.configure(values=self.presets.names())
            self.v_preset.set("")
            self._preset_baseline = None
            self._update_preset_marker()

    # ================================================================ збір і перевірка

    @staticmethod
    def _int(var, name, lo, hi) -> int:
        try:
            value = int(str(var.get()).strip())
        except ValueError:
            raise ValueError(t("Поле «{field}»: введіть ціле число.").format(field=name)) from None
        if not lo <= value <= hi:
            raise ValueError(t("Поле «{field}»: значення має бути від {lo} до {hi}.").format(
                field=name, lo=lo, hi=hi))
        return value

    @staticmethod
    def _int_or(var, default: int) -> int:
        try:
            return int(str(var.get()).strip())
        except ValueError:
            return default

    def _collect(self) -> ConvSettings:
        s = ConvSettings()
        s.crf = self._int(self.v_crf, t("Якість (CRF)"), 0, 51)
        s.preset = self.v_xpreset.get() if self.v_xpreset.get() in X264_PRESET_NAMES else "slow"

        s.res_mode = self.v_res_mode.get()
        s.res_master = self.v_res_master.get()
        if s.res_mode == "custom":
            if s.res_master == "width":
                s.width = self._int(self.v_w, t("Ширина"), 16, 16384)
                s.height = self._int_or(self.v_h, s.height)
            else:
                s.height = self._int(self.v_h, t("Висота"), 16, 16384)
                s.width = self._int_or(self.v_w, s.width)
        else:
            s.width = self._int_or(self.v_w, s.width)
            s.height = self._int_or(self.v_h, s.height)

        s.fps_mode = self.v_fps_mode.get()
        fps = self.v_fps.get().strip().replace(",", ".")
        if s.fps_mode == "custom":
            try:
                value = float(fps)
            except ValueError:
                raise ValueError(t("Поле «Частота кадрів»: введіть число, наприклад 25 або 29.97.")) from None
            if not 1 <= value <= 1000:
                raise ValueError(t("Поле «Частота кадрів»: значення має бути від 1 до 1000."))
        s.fps = fps or "30"

        s.audio_codec = _value_for(AUDIO_CODECS, self.v_acodec.get())
        s.audio_bitrate_mode = self.v_ab_mode.get()
        if s.audio_codec in ("aac", "mp3") and s.audio_bitrate_mode == "custom":
            s.audio_bitrate = self._int(self.v_ab, t("Бітрейт аудіо"), 8,
                                        640 if s.audio_codec == "aac" else 320)
        else:
            s.audio_bitrate = self._int_or(self.v_ab, s.audio_bitrate)

        s.keyint = self._int(self.v_keyint, t("Інтервал ключових кадрів"), 0, 1000)
        s.min_keyint = self._int(self.v_minkey, t("Мінімальний інтервал"), 1, 1000)
        s.pix_fmt = _value_for(PIX_FMTS, self.v_pix.get())
        s.tune = _value_for(TUNES, self.v_tune.get())
        s.container = self.v_container.get() if self.v_container.get() in CONTAINERS else "mp4"
        s.faststart = bool(self.v_faststart.get())
        s.extra_args = self.v_extra.get().strip()
        if s.extra_args:
            try:
                ffmpeg_tools.split_args(s.extra_args)
            except ValueError as exc:
                raise ValueError(t("Поле «Додаткові параметри ffmpeg»: {error}").format(error=exc)) from None
        return s

    def _ok(self):
        if not self.files:
            messagebox.showerror(t("Помилка"), t("Додайте хоча б один файл."), parent=self)
            return
        out = self.v_out.get().strip()
        if not out or not os.path.isabs(out):
            messagebox.showerror(t("Помилка"),
                                 t("Вкажіть повний шлях до теки для готових файлів."), parent=self)
            return
        prefix = self.v_prefix.get()
        if any(ch in INVALID_NAME_CHARS for ch in prefix):
            messagebox.showerror(t("Помилка"),
                                 t('Префікс не може містити символи  < > : " / \\ | ? *'), parent=self)
            return
        try:
            settings = self._collect()
        except ValueError as exc:
            messagebox.showerror(t("Помилка в налаштуваннях"), str(exc), parent=self)
            return

        base = self.task
        self.result = Task(
            id=base.id if base else Task().id,
            name=self.v_name.get().strip() or t("Без назви"),
            status=base.status if base else Task().status,
            files=self.files,
            out_dir=os.path.abspath(out),
            prefix=prefix,
            settings=settings,
            preset_name=self.v_preset.get(),
        )
        self.app_settings["last_out_dir"] = out
        self.app_settings["default_prefix"] = prefix
        self.app_settings["recursive_scan"] = bool(self.v_recursive.get())
        self._close()

    def _cancel(self):
        self.result = None
        self._close()

    def _close(self):
        try:
            self.app_settings["dialog_geometry"] = self.geometry()
        except tk.TclError:
            pass
        self.grab_release()
        self.destroy()
