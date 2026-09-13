"""Перевірка повноти перекладу.

Знаходить усі виклики t("…") у коді й порівнює зі словником EN.
    python tools/check_i18n.py          — показати, чого бракує
    python tools/check_i18n.py --dump   — вивести заготовку словника
"""

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(ROOT))

from ffmpeggui import models  # noqa: E402
from ffmpeggui.translations_en import EN  # noqa: E402


def label_values() -> list[str]:
    """Підписи зі списків моделі — вони перекладаються через t() під час показу."""
    values = list(models.FILE_STATUS_LABELS.values()) + list(models.TASK_STATUS_LABELS.values())
    for options in (models.X264_PRESETS, models.AUDIO_CODECS, models.PIX_FMTS, models.TUNES):
        values += [label for _, label in options if label]
    return values


def collect() -> list[str]:
    found: list[str] = []
    for path in sorted((ROOT / "ffmpeggui").rglob("*.py")):
        if path.name in ("translations_en.py", "i18n.py"):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id == "t" and node.args
                    and isinstance(node.args[0], ast.Constant)
                    and isinstance(node.args[0].value, str)):
                value = node.args[0].value
                if value not in found:
                    found.append(value)
    return found


def placeholder_problems() -> list[str]:
    """Плейсхолдери {name} мають збігатися, інакше .format() впаде під час роботи."""
    problems = []
    for key, value in EN.items():
        if not value:
            continue
        a = sorted(re.findall(r"\{(\w+)\}", key))
        b = sorted(re.findall(r"\{(\w+)\}", value))
        if a != b:
            problems.append(f"{key!r}: {a} != {b}")
    return problems


def main() -> int:
    used = collect()
    for value in label_values():
        if value not in used:
            used.append(value)
    missing = [s for s in used if s not in EN]
    extra = [s for s in EN if s not in used]
    if "--dump" in sys.argv:
        for s in used:
            print(f"    {s!r}:\n        {EN.get(s, '')!r},")
        return 0
    print(f"Рядків у коді: {len(used)}; перекладено: {len(used) - len(missing)}")
    if missing:
        print(f"\nБракує перекладу ({len(missing)}):")
        for s in missing:
            print(f"  {s!r}")
    if extra:
        print(f"\nЗайві ключі у словнику ({len(extra)}):")
        for s in extra:
            print(f"  {s!r}")
    problems = placeholder_problems()
    if problems:
        print("")
        print(f"Неузгоджені плейсхолдери ({len(problems)}):")
        for line in problems:
            print(f"  {line}")
    return 1 if missing or extra or problems else 0


if __name__ == "__main__":
    sys.exit(main())
