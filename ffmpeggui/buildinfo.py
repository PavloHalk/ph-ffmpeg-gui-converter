"""Дата збірки програми.

У зібраному exe дату записує build.py у файл _build_date.py. При запуску з
вихідних кодів береться дата найсвіжішого файлу пакета.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime

from .version import VERSION_DATE


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def _newest_source_date() -> str:
    newest = 0.0
    root = os.path.dirname(os.path.abspath(__file__))
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for name in filenames:
            if name.endswith(".py"):
                try:
                    newest = max(newest, os.path.getmtime(os.path.join(dirpath, name)))
                except OSError:
                    pass
    return datetime.fromtimestamp(newest).strftime("%Y-%m-%d %H:%M") if newest else VERSION_DATE


def build_date() -> str:
    """Дата збірки exe або дата вихідних кодів."""
    try:
        from ._build_date import BUILD_DATE  # генерується build.py
        return BUILD_DATE
    except ImportError:
        pass
    if is_frozen():
        try:
            return datetime.fromtimestamp(os.path.getmtime(sys.executable)).strftime("%Y-%m-%d %H:%M")
        except OSError:
            return VERSION_DATE
    return _newest_source_date()
