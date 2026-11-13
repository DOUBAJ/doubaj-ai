# PyInstaller spec – builds the portable folder "DOUBAJ AI/" containing "DOUBAJ AI.exe"
# Usage (from the project root):  pyinstaller build/doubaj.spec --noconfirm
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules, collect_dynamic_libs

ROOT = Path(SPECPATH).parent
ICON = ROOT / "build" / "doubaj.ico"

datas = [(str(ROOT / "doubaj" / "assets"), "doubaj/assets")]
datas += collect_data_files("qtawesome")
datas += collect_data_files("docx")
datas += collect_data_files("pptx")
datas += collect_data_files("pypdfium2")
datas += collect_data_files("pypdfium2_raw")
binaries = collect_dynamic_libs("pypdfium2_raw")

hiddenimports = []
for pkg in ("pygments.lexers", "pygments.styles", "pygments.formatters", "markdown.extensions",
            "anthropic", "openai", "openpyxl", "pptx", "docx"):
    hiddenimports += collect_submodules(pkg)
hiddenimports += ["PySide6.QtWebEngineWidgets", "PySide6.QtPdf", "PySide6.QtPdfWidgets",
                  "PySide6.QtTextToSpeech", "PySide6.QtMultimedia", "pypdfium2", "xlrd", "psutil", "bs4"]
if sys.platform.startswith("win"):
    hiddenimports += ["win32com.client", "pythoncom", "pywintypes"]

excludes = ["tkinter", "PySide6.Qt3DCore", "PySide6.Qt3DRender", "PySide6.Qt3DInput", "PySide6.Qt3DLogic",
            "PySide6.Qt3DAnimation", "PySide6.Qt3DExtras", "PySide6.QtCharts", "PySide6.QtDataVisualization",
            "PySide6.QtGraphs", "PySide6.QtBluetooth", "PySide6.QtNfc", "PySide6.QtSensors", "PySide6.QtSerialPort",
            "PySide6.QtSerialBus", "PySide6.QtDesigner", "PySide6.QtQuick3D", "PySide6.QtSpatialAudio",
            "PySide6.QtScxml", "PySide6.QtStateMachine", "PySide6.QtRemoteObjects", "PySide6.QtHttpServer",
            "matplotlib", "numpy.f2py", "IPython", "pytest"]

a = Analysis([str(ROOT / "main.py")], pathex=[str(ROOT)], binaries=binaries, datas=datas,
             hiddenimports=hiddenimports, excludes=excludes, noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="DOUBAJ AI", console=False,
          icon=str(ICON) if ICON.exists() else None, upx=False,
          version=str(ROOT / "build" / "version_info.txt") if (ROOT / "build" / "version_info.txt").exists() else None)
coll = COLLECT(exe, a.binaries, a.datas, name="DOUBAJ AI", upx=False)
