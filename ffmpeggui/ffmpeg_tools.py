"""Робота з ffmpeg/ffprobe: пошук у теці bin, завантаження, аналіз файлів, запуск."""

from __future__ import annotations

import collections
import json
import os
import shlex
import subprocess
import tempfile
import threading
import time
import urllib.request
import zipfile
from dataclasses import dataclass
from typing import Callable

from . import paths
from .i18n import t
from .models import ConvSettings
from .version import APP_NAME, __version__

CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0

DOWNLOAD_SOURCES = [
    ("gyan.dev", "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"),
    ("GitHub (BtbN)",
     "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"),
]
MANUAL_PAGES = [
    "https://www.gyan.dev/ffmpeg/builds/",
    "https://github.com/BtbN/FFmpeg-Builds/releases",
]


class ProbeError(Exception):
    pass


# ---------------------------------------------------------------- наявність

def ffmpeg_available() -> bool:
    return os.path.isfile(paths.ffmpeg_exe()) and os.path.isfile(paths.ffprobe_exe())


def ffmpeg_version() -> str:
    try:
        r = subprocess.run(
            [paths.ffmpeg_exe(), "-hide_banner", "-version"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            creationflags=CREATE_NO_WINDOW, timeout=15,
        )
        first = (r.stdout or "").splitlines()
        return first[0].strip() if first else ""
    except (OSError, subprocess.SubprocessError):
        return ""


# ---------------------------------------------------------------- завантаження

def download_ffmpeg(
    on_progress: Callable[[int, int], None],
    on_status: Callable[[str], None],
    cancel: threading.Event,
) -> None:
    """Завантажує статичну збірку і кладе ffmpeg.exe/ffprobe.exe у теку bin.

    Кидає виняток з поясненням, якщо жодне джерело не спрацювало.
    """
    os.makedirs(paths.bin_dir(), exist_ok=True)
    errors = []
    for name, url in DOWNLOAD_SOURCES:
        if cancel.is_set():
            raise RuntimeError(t("Завантаження скасовано."))
        fd, tmp_zip = tempfile.mkstemp(suffix=".zip", prefix="ffmpeg_")
        os.close(fd)
        try:
            on_status(t("Завантаження з {source}…").format(source=name))
            req = urllib.request.Request(url, headers={"User-Agent": f"{APP_NAME}/{__version__}"})
            with urllib.request.urlopen(req, timeout=30) as resp, open(tmp_zip, "wb") as out:
                total = int(resp.headers.get("Content-Length") or 0)
                done = 0
                while True:
                    if cancel.is_set():
                        raise RuntimeError(t("Завантаження скасовано."))
                    chunk = resp.read(256 * 1024)
                    if not chunk:
                        break
                    out.write(chunk)
                    done += len(chunk)
                    on_progress(done, total)
            on_status(t("Розпакування…"))
            _extract_binaries(tmp_zip)
            if ffmpeg_available():
                return
            errors.append(f"{name}: " + t("в архіві не знайдено ffmpeg.exe/ffprobe.exe"))
        except Exception as exc:  # noqa: BLE001 — пробуємо наступне джерело
            if cancel.is_set():
                raise RuntimeError(t("Завантаження скасовано.")) from exc
            errors.append(f"{name}: {exc}")
        finally:
            try:
                os.remove(tmp_zip)
            except OSError:
                pass
    raise RuntimeError(t("Не вдалося завантажити ffmpeg.") + "\n" + "\n".join(errors))


def _extract_binaries(zip_path: str) -> None:
    wanted = {"ffmpeg.exe", "ffprobe.exe"}
    with zipfile.ZipFile(zip_path) as zf:
        for member in zf.namelist():
            base = os.path.basename(member).lower()
            if base not in wanted:
                continue
            target = os.path.join(paths.bin_dir(), base)
            tmp = target + ".part"
            with zf.open(member) as src, open(tmp, "wb") as dst:
                while True:
                    buf = src.read(1024 * 1024)
                    if not buf:
                        break
                    dst.write(buf)
            os.replace(tmp, target)
            wanted.discard(base)


# ---------------------------------------------------------------- ffprobe

@dataclass
class ProbeInfo:
    duration: float = 0.0
    has_video: bool = False
    width: int = 0
    height: int = 0
    fps: float = 0.0
    has_audio: bool = False
    audio_bitrate: int = 0  # біт/с, 0 = невідомо


def _parse_rate(value: str) -> float:
    try:
        if "/" in value:
            num, den = value.split("/", 1)
            return float(num) / float(den) if float(den) else 0.0
        return float(value)
    except (ValueError, ZeroDivisionError):
        return 0.0


def probe(path: str) -> ProbeInfo:
    cmd = [paths.ffprobe_exe(), "-v", "error", "-print_format", "json",
           "-show_format", "-show_streams", path]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", creationflags=CREATE_NO_WINDOW, timeout=120)
    except (OSError, subprocess.SubprocessError) as exc:
        raise ProbeError(t("Не вдалося запустити ffprobe: {error}").format(error=exc)) from exc
    if r.returncode != 0:
        raise ProbeError((r.stderr or "").strip() or t("ffprobe не зміг прочитати файл"))
    try:
        data = json.loads(r.stdout or "{}")
    except ValueError as exc:
        raise ProbeError(t("Некоректна відповідь ffprobe")) from exc

    info = ProbeInfo()
    fmt = data.get("format", {})
    info.duration = _parse_rate(str(fmt.get("duration", "0")))
    for st in data.get("streams", []):
        kind = st.get("codec_type")
        if kind == "video" and not info.has_video:
            if st.get("disposition", {}).get("attached_pic"):
                continue
            info.has_video = True
            info.width = int(st.get("width") or 0)
            info.height = int(st.get("height") or 0)
            info.fps = _parse_rate(st.get("avg_frame_rate") or st.get("r_frame_rate") or "0")
            rotation = 0
            for sd in st.get("side_data_list", []) or []:
                if "rotation" in sd:
                    rotation = int(float(sd["rotation"]))
            rotation = rotation or int(float(st.get("tags", {}).get("rotate", 0) or 0))
            if abs(rotation) % 180 == 90:  # ffmpeg автоматично повертає кадр
                info.width, info.height = info.height, info.width
            if not info.duration:
                info.duration = _parse_rate(str(st.get("duration", "0")))
        elif kind == "audio" and not info.has_audio:
            info.has_audio = True
            info.audio_bitrate = int(_parse_rate(str(st.get("bit_rate", "0"))))
    return info


def probe_duration(path: str) -> float:
    """Лише тривалість (для оцінки часу до завершення). 0, якщо не вдалося."""
    try:
        return probe(path).duration
    except (ProbeError, OSError):
        return 0.0


# ---------------------------------------------------------------- команда

def build_command(src: str, dst: str, s: ConvSettings, info: ProbeInfo) -> list[str]:
    cmd = [paths.ffmpeg_exe(), "-hide_banner", "-nostdin", "-y", "-loglevel", "error",
           "-progress", "pipe:1", "-nostats", "-i", src]

    cmd += ["-c:v", "libx264", "-crf", str(s.crf), "-preset", s.preset]
    if s.tune:
        cmd += ["-tune", s.tune]
    if s.pix_fmt:
        cmd += ["-pix_fmt", s.pix_fmt]
    if s.keyint > 0:
        cmd += ["-x264opts", f"keyint={s.keyint}:min-keyint={max(1, s.min_keyint)}"]

    if s.res_mode == "custom":
        if s.res_master == "width":
            w = max(2, s.width - s.width % 2)
            cmd += ["-vf", f"scale={w}:-2"]
        else:
            h = max(2, s.height - s.height % 2)
            cmd += ["-vf", f"scale=-2:{h}"]
    if s.fps_mode == "custom" and s.fps:
        cmd += ["-r", s.fps]

    if s.audio_codec == "none":
        cmd += ["-an"]
    elif s.audio_codec == "copy":
        cmd += ["-c:a", "copy"]
    else:
        cmd += ["-c:a", "aac" if s.audio_codec == "aac" else "libmp3lame"]
        limit = 320_000 if s.audio_codec == "mp3" else 512_000
        if s.audio_bitrate_mode == "custom":
            cmd += ["-b:a", f"{s.audio_bitrate}k"]
        elif info.audio_bitrate:
            cmd += ["-b:a", str(min(info.audio_bitrate, limit))]

    if s.faststart and s.container in ("mp4", "mov"):
        cmd += ["-movflags", "+faststart"]
    if s.extra_args.strip():
        cmd += split_args(s.extra_args)
    cmd.append(dst)
    return cmd


def split_args(text: str) -> list[str]:
    """Розбиває рядок параметрів за правилами командного рядка Windows.

    shlex.split працює за правилами Linux, де «\\» — службовий символ, і псує
    шляхи на кшталт C:\\subs\\a.srt. Тому на Windows користуємося системною
    функцією CommandLineToArgvW — саме так рядок розібрав би сам Windows.
    """
    if os.name != "nt":
        return shlex.split(text)
    import ctypes
    from ctypes import wintypes
    parse = ctypes.windll.shell32.CommandLineToArgvW
    parse.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(ctypes.c_int)]
    parse.restype = ctypes.POINTER(wintypes.LPWSTR)
    count = ctypes.c_int()
    # Перше слово Windows розбирає як ім'я програми (за іншими правилами) — підставляємо заглушку.
    argv = parse("x " + text, ctypes.byref(count))
    if not argv:
        raise ValueError(text)
    try:
        return [argv[i] for i in range(1, count.value)]
    finally:
        ctypes.windll.kernel32.LocalFree(argv)


def start_process(cmd: list[str]) -> subprocess.Popen:
    return subprocess.Popen(
        cmd,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        creationflags=CREATE_NO_WINDOW,
    )


@dataclass
class ProgressUpdate:
    """Те, що ffmpeg повідомляє про хід конвертації одного файлу."""

    fraction: float = 0.0   # 0..1 за часом відео
    fps: float = 0.0        # кадрів за секунду обробки
    speed: float = 0.0      # у скільки разів швидше за реальний час
    frame: int = 0


def watch_process(proc: subprocess.Popen, duration: float,
                  on_progress: Callable[[ProgressUpdate], None]) -> tuple[int, str]:
    """Читає -progress з stdout, повертає (код завершення, хвіст stderr)."""
    tail: collections.deque[str] = collections.deque(maxlen=40)

    def read_stderr():
        for line in proc.stderr:
            line = line.strip()
            if line:
                tail.append(line)

    reader = threading.Thread(target=read_stderr, daemon=True)
    reader.start()

    state = ProgressUpdate()
    reported_fps = 0.0
    measured_fps = 0.0
    last_frame = 0
    last_frame_time = time.monotonic()
    last_sent = 0.0

    for line in proc.stdout:
        key, _, value = line.strip().partition("=")
        value = value.strip()
        if key == "frame":
            try:
                frame = int(value)
            except ValueError:
                continue
            state.frame = frame
            now = time.monotonic()
            gap = now - last_frame_time
            if gap >= 0.5 and frame > last_frame:
                instant = (frame - last_frame) / gap
                # згладжуємо, щоб показник не стрибав
                measured_fps = instant if measured_fps <= 0 else measured_fps * 0.6 + instant * 0.4
                last_frame, last_frame_time = frame, now
        elif key == "fps":
            try:
                reported_fps = float(value)
            except ValueError:
                reported_fps = 0.0
        elif key == "speed":
            try:
                state.speed = float(value.rstrip("x").strip())
            except ValueError:
                pass
        elif key in ("out_time_us", "out_time_ms"):
            try:
                seconds = int(value) / 1_000_000
            except ValueError:
                continue
            if duration > 0:
                state.fraction = max(0.0, min(1.0, seconds / duration))
        elif key == "progress":
            # кінець блоку значень — саме тут маємо узгоджений стан
            state.fps = measured_fps or reported_fps
            now = time.monotonic()
            if now - last_sent >= 0.25 or value == "end":
                last_sent = now
                on_progress(ProgressUpdate(state.fraction, state.fps, state.speed, state.frame))

    rc = proc.wait()
    reader.join(timeout=2)
    return rc, "\n".join(list(tail)[-6:])
