"""DOUBAJ AI – entry point.  Réalisé par Doubaj Ahmed."""
from __future__ import annotations

import logging
import sys
import traceback


def _run_python_mode() -> bool:
    """`DOUBAJ AI.exe --run-python script.py` : used by the code sandbox inside the frozen EXE."""
    if len(sys.argv) >= 3 and sys.argv[1] == "--run-python":
        from doubaj.tools.sandbox import run_script_entry
        run_script_entry(sys.argv[2])
        return True
    return False


def main() -> int:
    if _run_python_mode():
        return 0
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication, QMessageBox

    from doubaj import i18n
    from doubaj.config import DB_PATH, LOG_DIR, ensure_dirs
    from doubaj.storage.db import Database

    ensure_dirs()
    logging.basicConfig(filename=str(LOG_DIR / "doubaj.log"), level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    # never log HTTP request details (they could contain keys in some libraries)
    for noisy in ("httpx", "httpcore", "openai", "anthropic"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    app = QApplication(sys.argv)
    app.setApplicationName("DOUBAJ AI")
    app.setOrganizationName("Doubaj Ahmed")

    def excepthook(exc_type, exc, tb):  # the app must never close on an error
        msg = "".join(traceback.format_exception(exc_type, exc, tb))
        logging.error(msg)
        try:
            QMessageBox.critical(None, "DOUBAJ AI", f"{exc_type.__name__}: {exc}\n\n(détails dans data/logs/doubaj.log)")
        except Exception:
            pass
    sys.excepthook = excepthook

    from doubaj.ui.fonts import load_fonts
    from doubaj.ui.logo import app_icon
    load_fonts()
    app.setWindowIcon(app_icon())

    db = Database(DB_PATH)
    i18n.set_lang(db.get_setting("lang", "fr"))

    from doubaj.ui.main_window import MainWindow
    from doubaj.ui.splash import SplashScreen

    state = {"win": None}

    def open_main():
        if state["win"] is not None:
            state["win"].close()
            state["win"].deleteLater()
        i18n.set_lang(db.get_setting("lang", "fr"))
        app.setLayoutDirection(Qt.RightToLeft if i18n.is_rtl() else Qt.LeftToRight)
        win = MainWindow(db)
        win.rebuild_requested.connect(lambda: open_main())
        win.showMaximized()
        state["win"] = win

    splash = SplashScreen(db.get_setting("lang", "fr"))

    def start(lang):
        db.set_setting("lang", lang)
        open_main()      # open the main window before closing the splash (else Qt quits)
        splash.close()

    splash.started.connect(start)
    splash.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
