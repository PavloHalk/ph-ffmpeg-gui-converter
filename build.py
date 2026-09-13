"""Збірка exe.

1. Генерує version.txt (формат VSVersionInfo для PyInstaller) з ffmpeggui/version.py.
2. Записує дату збірки у ffmpeggui/_build_date.py (показується у вікні «Про програму»).
3. Запускає PyInstaller.

Використання:
    python build.py                — згенерувати version.txt і зібрати exe
    python build.py --version-only — лише згенерувати version.txt і дату збірки
"""

import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from ffmpeggui import version as v  # noqa: E402

VERSION_TEMPLATE = """# UTF-8
# Файл згенеровано build.py з ffmpeggui/version.py — не редагуйте вручну.
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={vtuple},
    prodvers={vtuple},
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo(
      [
        StringTable(
          '040904B0',
          [
            StringStruct('CompanyName', {author!r}),
            StringStruct('FileDescription', {description!r}),
            StringStruct('FileVersion', {version!r}),
            StringStruct('InternalName', {name!r}),
            StringStruct('LegalCopyright', {copyright!r}),
            StringStruct('OriginalFilename', {exe!r}),
            StringStruct('ProductName', {title!r}),
            StringStruct('ProductVersion', {version!r}),
            StringStruct('BuildDate', {build_date!r}),
          ]
        )
      ]
    ),
    VarFileInfo([VarStruct('Translation', [0x0409, 1200])])
  ]
)
"""

BUILD_DATE_TEMPLATE = '''"""Дата збірки — файл генерується build.py, у git не зберігається."""

BUILD_DATE = "{date}"
'''


def version_tuple(text: str) -> tuple:
    nums = [int(x) for x in re.findall(r"\d+", text)][:4]
    return tuple(nums + [0] * (4 - len(nums)))


def write_build_date() -> str:
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    (ROOT / "ffmpeggui" / "_build_date.py").write_text(
        BUILD_DATE_TEMPLATE.format(date=stamp), encoding="utf-8")
    return stamp


def write_version_file(build_date: str) -> Path:
    path = ROOT / "version.txt"
    path.write_text(VERSION_TEMPLATE.format(
        vtuple=version_tuple(v.__version__),
        version=v.__version__,
        author=v.AUTHOR,
        description=v.DESCRIPTION,
        name=v.APP_NAME,
        title=v.APP_TITLE,
        copyright=v.COPYRIGHT,
        exe=f"{v.APP_NAME}.exe",
        build_date=build_date,
    ), encoding="utf-8")
    print(f"version.txt: версія {v.__version__}, зібрано {build_date}")
    return path


def build() -> int:
    icon = ROOT / "assets" / "app.ico"
    if not icon.is_file():
        print("Іконки немає — генерую: python tools/make_icon.py")
        subprocess.call([sys.executable, str(ROOT / "tools" / "make_icon.py")], cwd=ROOT)

    build_date = write_build_date()
    version_file = write_version_file(build_date)
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean", "--onefile", "--windowed",
        "--name", v.APP_NAME,
        "--version-file", str(version_file),
        "--hidden-import", "ffmpeggui._build_date",
        "--icon", str(icon),
        "--add-data", f"{icon}{';' if sys.platform == 'win32' else ':'}assets",
        str(ROOT / "main.py"),
    ]
    print(" ".join(cmd))
    rc = subprocess.call(cmd, cwd=ROOT)
    if rc == 0:
        print(f"\nГотово: {ROOT / 'dist' / (v.APP_NAME + '.exe')}")
        print("Поруч з exe програма створить теку bin для ffmpeg (або запропонує завантажити його).")
    return rc


if __name__ == "__main__":
    if "--version-only" in sys.argv:
        write_version_file(write_build_date())
        sys.exit(0)
    sys.exit(build())
