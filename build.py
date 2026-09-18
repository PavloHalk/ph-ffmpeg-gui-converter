"""Збірка exe.

1. Генерує version.txt (формат VSVersionInfo для PyInstaller) з ffmpeggui/version.py.
2. Записує дату збірки у ffmpeggui/_build_date.py (показується у вікні «Про програму»).
3. Генерує build/FFMpegGuiConverter.spec — один exe без непотрібних файлів Tcl/Tk
   (див. EXCLUDED_DATA) — і запускає за ним PyInstaller.

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


# Файли даних Tcl/Tk, які програмі не потрібні.
# PyInstaller кладе бібліотеку Tcl у збірку цілком, бо не знає, що інтерпретатор Tcl
# завантажить під час роботи. А exe-«один файл» розпаковує кожен такий файл у %TEMP%
# при КОЖНОМУ запуску, тож зайві файли прямо сповільнюють старт (заміряно: 2,8 с -> 1,8 с).
EXCLUDED_DATA = (
    "_tcl_data/tzdata/",  # ~610 файлів часових поясів Tcl — час у програмі рахує Python, не Tcl
    "_tcl_data/msgs/",    # ~130 перекладів повідомлень Tcl (назви місяців для clock format)
    "_tk_data/msgs/",     # переклади вбудованих діалогів Tk — на Windows діалоги системні
)

SPEC_TEMPLATE = '''# Згенеровано build.py — не редагуйте вручну.
a = Analysis(
    [{main!r}],
    pathex=[{root!r}],
    datas=[({icon!r}, "assets")],
    hiddenimports=["ffmpeggui._build_date"],
)

EXCLUDED_DATA = {excluded!r}
before = len(a.datas)
a.datas = [d for d in a.datas
           if not any(d[0].replace("\\\\", "/").startswith(prefix) for prefix in EXCLUDED_DATA)]
print(f"Виключено непотрібних файлів даних Tcl/Tk: {{before - len(a.datas)}} з {{before}}")

pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [],
    name={name!r},
    console=False,
    upx=False,
    icon={icon!r},
    version={version_file!r},
)
'''


def write_spec(version_file: Path, icon: Path) -> Path:
    """Spec-файл для PyInstaller: один exe без непотрібних файлів Tcl/Tk."""
    spec = ROOT / "build" / f"{v.APP_NAME}.spec"
    spec.parent.mkdir(exist_ok=True)
    spec.write_text(SPEC_TEMPLATE.format(
        main=(ROOT / "main.py").as_posix(),
        root=ROOT.as_posix(),
        icon=icon.as_posix(),
        excluded=EXCLUDED_DATA,
        name=v.APP_NAME,
        version_file=version_file.as_posix(),
    ), encoding="utf-8")
    return spec


def build() -> int:
    icon = ROOT / "assets" / "app.ico"
    if not icon.is_file():
        print("Іконки немає — генерую: python tools/make_icon.py")
        subprocess.call([sys.executable, str(ROOT / "tools" / "make_icon.py")], cwd=ROOT)

    build_date = write_build_date()
    version_file = write_version_file(build_date)
    spec = write_spec(version_file, icon)
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean",
        "--distpath", str(ROOT / "dist"),
        "--workpath", str(ROOT / "build"),
        str(spec),
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
