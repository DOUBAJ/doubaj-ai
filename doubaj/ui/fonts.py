"""Load bundled fonts (Amiri, OFL licence) and pick the best Arabic families available."""
from __future__ import annotations

from PySide6.QtGui import QFontDatabase

from ..config import resource_dir

_loaded: dict[str, str] = {}


def load_fonts() -> None:
    fdir = resource_dir() / "fonts"
    for f in sorted(fdir.glob("*.ttf")):
        fid = QFontDatabase.addApplicationFont(str(f))
        if fid >= 0:
            fams = QFontDatabase.applicationFontFamilies(fid)
            if fams:
                _loaded[f.stem] = fams[0]


def _first_available(cands: list[str]) -> str:
    fams = set(QFontDatabase.families())
    for c in cands:
        if c in fams:
            return c
    return cands[-1]


def quran_family() -> str:
    return _first_available([_loaded.get("AmiriQuran", "Amiri Quran"), _loaded.get("Amiri-Regular", "Amiri"),
                             "Sakkal Majalla", "Traditional Arabic", "Arial"])


def arabic_family() -> str:
    return _first_available([_loaded.get("Amiri-Regular", "Amiri"), "Sakkal Majalla", "Segoe UI", "Arial"])
