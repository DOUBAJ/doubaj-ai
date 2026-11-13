"""UI smoke test: splash, main window, full chat round-trip with a mock provider, file generation,
language/theme switching. Saves screenshots to tests/shots/."""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["DOUBAJ_DATA_DIR"] = tempfile.mkdtemp()

from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

import mock_server  # noqa: E402

SHOTS = Path(__file__).parent / "shots"
SHOTS.mkdir(exist_ok=True)
app = QApplication(sys.argv)
app.setQuitOnLastWindowClosed(False)
QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Yes)  # auto-confirm dialogs
QMessageBox.warning = staticmethod(lambda *a, **k: print("WARNING", a[1:]))

from doubaj import i18n  # noqa: E402
from doubaj.config import DB_PATH, ensure_dirs  # noqa: E402
from doubaj.storage.db import Database  # noqa: E402
from doubaj.ui.fonts import load_fonts  # noqa: E402
from doubaj.ui.logo import app_icon, export_icon_files  # noqa: E402
from doubaj.ui.main_window import MainWindow  # noqa: E402
from doubaj.ui.splash import SplashScreen  # noqa: E402

ensure_dirs()
load_fonts()
app.setWindowIcon(app_icon())
export_icon_files(str(SHOTS / "logo.png"))
srv = mock_server.start(8766)
REPLY = """## Moteur asynchrone triphasé

Le moteur se compose d'un **stator** et d'un **rotor**. La vitesse de synchronisme est $n_s = \\frac{60 f}{p}$.

| Grandeur | Symbole | Unité |
|---|---|---|
| Fréquence | f | Hz |
| Paires de pôles | p | – |

```python
def vitesse(f, p):
    return 60 * f / p
print(vitesse(50, 2))
```

J'ai créé la présentation demandée :

````doubaj-file name="moteur_triphase.pptx"
{"title": "Moteur asynchrone triphasé", "slides": [{"title": "Constitution", "bullets": ["Stator", "Rotor"]}]}
````
"""
mock_server.REPLY = lambda body: REPLY

db = Database(DB_PATH)
db.set_setting("provider", "custom")
db.set_setting("base_url:custom", "http://127.0.0.1:8766/v1")
db.set_setting("model:custom", "mock-model")

def grab(w, name):
    w.grab().save(str(SHOTS / name))
    print("shot", name)

splash = SplashScreen("fr")
splash.show()
app.processEvents()
QTimer.singleShot(1200, lambda: (grab(splash, "01_splash.png"), splash.set_lang("ar"), app.processEvents(),
                                 grab(splash, "01b_splash_ar.png"), splash.close()))

state = {}

def step_main():
    i18n.set_lang("fr")
    win = MainWindow(db)
    win.resize(1500, 900)
    win.show()
    state["win"] = win
    app.processEvents()
    grab(win, "02_welcome_light.png")
    win.input.setPlainText("Explique le moteur asynchrone triphasé et crée un PowerPoint")
    win.send()
    QTimer.singleShot(2500, step_after_answer)

def step_after_answer():
    win = state["win"]
    app.processEvents()
    msgs = db.get_messages(win.conv_id)
    assert len(msgs) == 2, msgs
    assert msgs[1]["meta"]["files"] and not msgs[1]["meta"]["files"][0]["error"], msgs[1]["meta"]
    assert Path(msgs[1]["meta"]["files"][0]["path"]).exists()
    print("✓ round-trip OK, file generated:", msgs[1]["meta"]["files"][0]["path"])
    grab(win, "03_chat_light.png")
    # regenerate
    win.regenerate(msgs[1]["id"])
    QTimer.singleShot(2500, step_dark_ar)

def step_dark_ar():
    win = state["win"]
    msgs = db.get_messages(win.conv_id)
    assert len(msgs) == 2 and msgs[1]["role"] == "assistant", [m["role"] for m in msgs]
    print("✓ regenerate OK")
    db.set_setting("theme", "dark")
    db.set_setting("lang", "ar")
    i18n.set_lang("ar")
    win.close()
    from PySide6.QtCore import Qt
    app.setLayoutDirection(Qt.RightToLeft)
    mock_server.REPLY = lambda body: "## المحرك اللاتزامني\n\nيتكون المحرك من **الساكن** و**الدوار**.\n\n- النقطة الأولى\n- النقطة الثانية\n\n| العنصر | الدور |\n|---|---|\n| الساكن | يولد حقلاً دواراً |"
    win2 = MainWindow(db)
    win2.resize(1500, 900)
    win2.show()
    state["win"] = win2
    win2.open_conversation(win.conv_id)
    win2.input.setPlainText("اشرح المحرك اللاتزامني")
    win2.send()
    QTimer.singleShot(2500, step_ws)

def step_ws():
    win = state["win"]
    app.processEvents()
    win.scroll_bottom()
    app.processEvents()
    grab(win, "04_chat_dark_ar.png")
    msgs = db.get_messages(win.conv_id)
    win.open_in_workspace(msgs[1]["content"])
    app.processEvents()
    QTimer.singleShot(1500, finish)

def finish():
    win = state["win"]
    app.processEvents()
    grab(win, "05_workspace_dark_ar.png")
    from doubaj.ui.dialogs import SettingsDialog, ProjectsDialog
    from doubaj.core.settings import Settings
    d = SettingsDialog(Settings(db), win)
    d.show(); app.processEvents(); grab(d, "06_settings.png"); d.close()
    pid = db.create_project("Cours Technologie industrielle", "Cours 2 Bac", "Réponds en français")
    p = ProjectsDialog(db, win, pid)
    p.show(); app.processEvents(); grab(p, "07_projects.png"); p.close()
    print("ALL UI STEPS PASSED")
    srv.shutdown()
    app.quit()

QTimer.singleShot(1600, step_main)
QTimer.singleShot(30000, lambda: (print("TIMEOUT"), app.exit(1)))
sys.exit(app.exec())
