"""Перевірка наявності ffmpeg, автоматичне завантаження та інструкція."""

from __future__ import annotations

import os
import queue
import threading
import tkinter as tk
import webbrowser
from tkinter import messagebox, ttk

from .. import ffmpeg_tools, paths


def _center(win: tk.Toplevel, master) -> None:
    win.update_idletasks()
    try:
        x = master.winfo_rootx() + (master.winfo_width() - win.winfo_width()) // 2
        y = master.winfo_rooty() + (master.winfo_height() - win.winfo_height()) // 3
        win.geometry(f"+{max(0, x)}+{max(0, y)}")
    except tk.TclError:
        pass


def instructions_text() -> str:
    return (
        "Як встановити ffmpeg вручну:\n\n"
        "1. Відкрийте сторінку завантаження:\n"
        f"      {ffmpeg_tools.MANUAL_PAGES[0]}\n"
        "   і завантажте архів «ffmpeg-release-essentials.zip».\n"
        "   Інший варіант — сторінка\n"
        f"      {ffmpeg_tools.MANUAL_PAGES[1]}\n"
        "   файл «ffmpeg-master-latest-win64-gpl.zip».\n\n"
        "2. Розпакуйте архів у будь-яке місце.\n\n"
        "3. Усередині архіву знайдіть теку «bin» і скопіюйте з неї два файли:\n"
        "      ffmpeg.exe\n"
        "      ffprobe.exe\n"
        "   у теку програми:\n"
        f"      {paths.bin_dir()}\n"
        "   (якщо теки ще немає — створіть її або натисніть «Відкрити теку bin»).\n\n"
        "4. Натисніть «Перевірити знову».\n\n"
        "Встановлювати ffmpeg у систему чи змінювати PATH не потрібно — програма\n"
        "використовує лише файли з теки bin поруч із собою."
    )


class DownloadDialog(tk.Toplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("Завантаження ffmpeg")
        self.resizable(False, False)
        self.transient(master)
        self.success = False
        self.error = ""
        self._q: queue.Queue = queue.Queue()
        self._cancel = threading.Event()
        self._indeterminate = False

        frm = ttk.Frame(self, padding=12)
        frm.pack(fill="both", expand=True)
        self.lbl = ttk.Label(frm, text="Підготовка…", width=60)
        self.lbl.pack(anchor="w")
        self.pb = ttk.Progressbar(frm, length=440, mode="determinate", maximum=100)
        self.pb.pack(fill="x", pady=8)
        self.lbl_size = ttk.Label(frm, text="")
        self.lbl_size.pack(anchor="w")
        ttk.Label(frm, text=f"Файли буде розпаковано в: {paths.bin_dir()}",
                  foreground="#555555", wraplength=440).pack(anchor="w", pady=(6, 0))
        ttk.Button(frm, text="Скасувати", command=self._on_cancel).pack(anchor="e", pady=(10, 0))
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)

        threading.Thread(target=self._worker, daemon=True).start()
        self.after(100, self._poll)
        _center(self, master)
        self.grab_set()

    def _worker(self):
        try:
            ffmpeg_tools.download_ffmpeg(
                lambda done, total: self._q.put(("progress", done, total)),
                lambda text: self._q.put(("status", text, None)),
                self._cancel,
            )
            self._q.put(("ok", None, None))
        except Exception as exc:  # noqa: BLE001
            self._q.put(("fail", str(exc), None))

    def _poll(self):
        try:
            while True:
                kind, a, b = self._q.get_nowait()
                if kind == "progress":
                    if b:
                        self.pb["value"] = a * 100 / b
                        self.lbl_size.configure(text=f"{a / 1048576:.1f} з {b / 1048576:.1f} МБ")
                    else:
                        if not self._indeterminate:
                            self._indeterminate = True
                            self.pb.configure(mode="indeterminate")
                            self.pb.start(20)
                        self.lbl_size.configure(text=f"{a / 1048576:.1f} МБ")
                elif kind == "status":
                    self.lbl.configure(text=a)
                elif kind == "ok":
                    self.success = True
                    self.destroy()
                    return
                elif kind == "fail":
                    self.error = a
                    self.destroy()
                    return
        except queue.Empty:
            pass
        self.after(100, self._poll)

    def _on_cancel(self):
        self._cancel.set()
        self.lbl.configure(text="Скасування…")


class InstructionsDialog(tk.Toplevel):
    def __init__(self, master, error: str = ""):
        super().__init__(master)
        self.title("Встановлення ffmpeg")
        self.transient(master)
        self.retry_download = False

        frm = ttk.Frame(self, padding=10)
        frm.pack(fill="both", expand=True)
        if error:
            ttk.Label(frm, text="Автоматичне завантаження не вдалося:", foreground="#c00000").pack(anchor="w")
            ttk.Label(frm, text=error, foreground="#c00000", wraplength=620,
                      justify="left").pack(anchor="w", pady=(0, 8))
        txt = tk.Text(frm, width=82, height=22, wrap="word", relief="sunken", borderwidth=2)
        txt.insert("1.0", instructions_text())
        txt.configure(state="disabled")
        txt.pack(fill="both", expand=True)

        btns = ttk.Frame(frm)
        btns.pack(fill="x", pady=(8, 0))
        ttk.Button(btns, text="Відкрити сторінку завантаження",
                   command=lambda: webbrowser.open(ffmpeg_tools.MANUAL_PAGES[0])).pack(side="left")
        ttk.Button(btns, text="Відкрити теку bin", command=self._open_bin).pack(side="left", padx=4)
        ttk.Button(btns, text="Завантажити автоматично", command=self._retry).pack(side="left")
        ttk.Button(btns, text="Закрити", command=self.destroy).pack(side="right")
        ttk.Button(btns, text="Перевірити знову", command=self._check).pack(side="right", padx=4)
        _center(self, master)
        self.grab_set()

    def _open_bin(self):
        os.makedirs(paths.bin_dir(), exist_ok=True)
        os.startfile(paths.bin_dir())

    def _retry(self):
        self.retry_download = True
        self.destroy()

    def _check(self):
        if ffmpeg_tools.ffmpeg_available():
            messagebox.showinfo("ffmpeg", "ffmpeg та ffprobe знайдено. Можна працювати!", parent=self)
            self.destroy()
        else:
            messagebox.showwarning(
                "ffmpeg", f"Файли ffmpeg.exe та ffprobe.exe досі не знайдено в теці:\n{paths.bin_dir()}",
                parent=self)


def ensure_ffmpeg(parent, log, reason: str = "") -> bool:
    """Повертає True, якщо ffmpeg доступний (за потреби пропонує встановити)."""
    if ffmpeg_tools.ffmpeg_available():
        return True
    text = (f"{reason}\n\n" if reason else "") + (
        "Не знайдено ffmpeg.exe та ffprobe.exe у теці:\n"
        f"{paths.bin_dir()}\n\n"
        "Завантажити статичну збірку ffmpeg автоматично?\n"
        "(близько 100 МБ; джерело — gyan.dev, резервне — GitHub)\n\n"
        "Файли буде розпаковано лише в цю теку: системний PATH і реєстр не змінюються, "
        "права адміністратора не потрібні.\n\n"
        "«Ні» — показати інструкцію для ручного встановлення."
    )
    want_download = messagebox.askyesno("ffmpeg не знайдено", text, parent=parent)
    while True:
        error = ""
        if want_download:
            log("Завантаження ffmpeg…", "info")
            dlg = DownloadDialog(parent)
            parent.wait_window(dlg)
            if dlg.success:
                log(f"ffmpeg встановлено в {paths.bin_dir()}", "ok")
                messagebox.showinfo("ffmpeg", "ffmpeg успішно завантажено та встановлено.", parent=parent)
                return True
            error = dlg.error
            log(error, "error")
        ins = InstructionsDialog(parent, error)
        parent.wait_window(ins)
        if ffmpeg_tools.ffmpeg_available():
            log("ffmpeg знайдено.", "ok")
            return True
        if not ins.retry_download:
            log("ffmpeg не встановлено — конвертація недоступна.", "warn")
            return False
        want_download = True
