"""After PyInstaller: assemble 'DOUBAJ AI PORTABLE/' and zip it as 'DOUBAJ AI PORTABLE.zip'."""
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
dist = ROOT / "dist" / "DOUBAJ AI"
out_dir = ROOT / "dist" / "DOUBAJ AI PORTABLE"
if out_dir.exists():
    shutil.rmtree(out_dir)
shutil.copytree(dist, out_dir)
(out_dir / "data").mkdir(exist_ok=True)
(out_dir / "data" / "models").mkdir(exist_ok=True)
shutil.copyfile(ROOT / "docs" / "LISEZ-MOI.txt", out_dir / "LISEZ-MOI - اقرأني.txt")
zpath = ROOT / "dist" / "DOUBAJ AI PORTABLE.zip"
with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
    for f in out_dir.rglob("*"):
        z.write(f, Path("DOUBAJ AI PORTABLE") / f.relative_to(out_dir))
print(zpath, round(zpath.stat().st_size / 1024 / 1024, 1), "MB")
