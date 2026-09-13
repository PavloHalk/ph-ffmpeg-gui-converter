"""Збірка exe.

1. Генерує version.txt (формат VSVersionInfo для PyInstaller) з h264conv/version.py.
2. Запускає PyInstaller.

Використання:
    python build.py              — згенерувати version.txt і зібрати exe
    python build.py --version-only — лише згенерувати version.txt
"""

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from h264conv import version as v  # noqa: E402

VERSION_TEMPLATE = """# UTF-8
# Файл згенеровано build.py з h264conv/version.py — не редагуйте вручну.
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
          '042204B0',
          [
            StringStruct('CompanyName', {author!r}),
            StringStruct('FileDescription', {description!r}),
            StringStruct('FileVersion', {version!r}),
            StringStruct('InternalName', {name!r}),
            StringStruct('LegalCopyright', {copyright!r}),
            StringStruct('OriginalFilename', {exe!r}),
            StringStruct('ProductName', {title!r}),
            StringStruct('ProductVersion', {version!r}),
          ]
        )
      ]
    ),
    VarFileInfo([VarStruct('Translation', [0x0422, 1200])])
  ]
)
"""


def version_tuple(text: str) -> tuple:
    nums = [int(x) for x in re.findall(r"\d+", text)][:4]
    return tuple(nums + [0] * (4 - len(nums)))


def write_version_file() -> Path:
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
    ), encoding="utf-8")
    print(f"version.txt згенеровано (версія {v.__version__})")
    return path


def build() -> int:
    version_file = write_version_file()
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean", "--onefile", "--windowed",
        "--name", v.APP_NAME,
        "--version-file", str(version_file),
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
        write_version_file()
        sys.exit(0)
    sys.exit(build())
