"""Render the DOUBAJ AI logo to build/doubaj.png and build/doubaj.ico."""
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from PySide6.QtWidgets import QApplication  # noqa: E402
app = QApplication(sys.argv)
from doubaj.ui.logo import export_icon_files  # noqa: E402
export_icon_files(str(ROOT / "build" / "doubaj.png"), str(ROOT / "build" / "doubaj.ico"))
print("icon ok")
