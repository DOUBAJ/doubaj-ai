"""Core tests: providers (via mock servers), engine, document generation and reading."""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["DOUBAJ_DATA_DIR"] = tempfile.mkdtemp()

from PySide6.QtWidgets import QApplication  # noqa: E402

import mock_server  # noqa: E402
from doubaj.core import engine  # noqa: E402
from doubaj.documents.generator import extract_and_generate  # noqa: E402
from doubaj.documents.reader import read_file  # noqa: E402
from doubaj.providers.base import CancelToken  # noqa: E402
from doubaj.providers.registry import create  # noqa: E402
from doubaj.storage.db import Database  # noqa: E402
from doubaj.core.settings import Settings  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)
from doubaj.ui.fonts import load_fonts  # noqa: E402
load_fonts()  # bundled Amiri font (the offscreen platform has no system fonts on Windows CI)
srv = mock_server.start(8765)
OUT = Path(tempfile.mkdtemp())
ok = 0


def check(cond, label):
    global ok
    assert cond, label
    ok += 1
    print("✓", label)


# ---- providers
for pid, url in (("custom", "http://127.0.0.1:8765/v1"), ("ollama", "http://127.0.0.1:8765/v1"),
                 ("anthropic", "http://127.0.0.1:8765")):
    p = create(pid, api_key="test-key", base_url=url)
    sysmsg = engine.build_system_prompt(provider_label=p.info.label, model="m", ui_lang="ar", mode="education",
                                        reasoning="deep", memories=["Je suis professeur"], project=None, length="normal")
    req = engine.build_request(model="claude-opus-5-5" if pid == "anthropic" else "mock-model", system=sysmsg,
                               history=[{"role": "user", "content": "مرحبا", "attachments": []}],
                               reasoning="deep", max_tokens=1000, temperature=None, context_chars=100000, project_docs=[])
    text = "".join(ev.text for ev in p.stream_chat(req, CancelToken()) if ev.kind == "text")
    check("مرحبا" in text, f"{pid}: streaming answer received ({text[:40]}…)")
    if pid == "anthropic":
        b = mock_server.H.last_body
        check(b["thinking"]["type"] == "adaptive" and b["output_config"]["effort"] == "high", "anthropic: adaptive thinking + effort sent")
        check("temperature" not in b, "anthropic: no temperature for modern models")
    check(len(p.list_models()) >= 1, f"{pid}: list_models")

# ---- error handling: unreachable server
p = create("ollama", base_url="http://127.0.0.1:9/v1")
evs = list(p.stream_chat(engine.build_request(model="x", system="", history=[{"role": "user", "content": "hi", "attachments": []}],
                                              reasoning="fast", max_tokens=10, temperature=None, context_chars=1000, project_docs=[]),
                         CancelToken()))
check(evs[-1].kind == "error", "unreachable local server gives a clean error: " + evs[-1].text[:60])

# ---- file generation
answer = '''Voici vos fichiers.

````doubaj-file name="rapport.docx"
# Rapport sur les moteurs
Un **moteur** asynchrone.

## Tableau
| Grandeur | Valeur |
|---|---|
| U | 400 V |

- point 1
- point 2

```python
print("code inside")
```
````

````doubaj-file name="cours.pdf"
# درس المحركات
المحرك اللاتزامني ثلاثي الأطوار يتكون من **الساكن** و**الدوار**.

| العنصر | الدور |
|---|---|
| الساكن | يولد حقلاً دواراً |
````

````doubaj-file name="moteurs.pptx"
{"title": "Moteurs triphasés", "subtitle": "Cours", "theme": "green", "slides": [
 {"title": "Constitution", "bullets": ["Stator", "Rotor", "  cage d'écureuil"], "notes": "Expliquer"},
 {"title": "Tableau", "table": [["Type","P"],["MAS","4 kW"]]},
 {"title": "Graphique", "chart": {"type": "bar", "categories": ["A","B"], "series": [{"name": "S", "values": [1,2]}]}, "bullets": ["note"]},
 {"title": "Comparaison", "left": ["a"], "right": ["b"]},
 {"title": "Démarrage", "diagram": ["Réseau", "Contacteur", "Moteur"]},
]}
````

````doubaj-file name="notes.xlsx"
{"sheets": [{"name": "Notes", "columns": ["Nom", "N1", "N2", "Moyenne"], "rows": [["Ali", 12, 14, "=AVERAGE(B2:C2)"], ["Sara", 16, 15, "=AVERAGE(B3:C3)"]],
  "chart": {"type": "bar", "title": "Moyennes", "data_cols": [4], "category_col": 1}}]}
````

````doubaj-file name="data.csv"
nom,note
Ali,12
````

````doubaj-file name="gestion_notes/main.py"
print("hello")
````

````doubaj-file name="gestion_notes/README.md"
# Gestion des notes
````
'''
res = extract_and_generate(answer, OUT)
for r in res:
    check(not r.error and r.path.exists() and r.path.stat().st_size > 0, f"generated {r.name} ({r.path.stat().st_size} bytes) {r.error}")
check(len(res) == 8, "7 files + 1 project zip")

# ---- reading back
for name, needle in (("rapport.docx", "400 V"), ("cours.pdf", "Page"), ("moteurs.pptx", "Stator"),
                     ("notes.xlsx", "Ali"), ("data.csv", "Ali")):
    r = read_file(OUT / name)
    check(needle in r.text or needle in r.text.replace(" ", ""), f"read {name}: found '{needle}' {r.warnings}")
check("[Slide 2]" in read_file(OUT / "moteurs.pptx").text, "pptx reader has slide markers")
check("[Page 1]" in read_file(OUT / "cours.pdf").text or read_file(OUT / "cours.pdf").images, "pdf reader has page markers")

# ---- retrieval on large docs
big = "\n".join(f"[Page {i}]\n" + ("texte sans intérêt " * 200) for i in range(1, 60))
big += "\n[Page 60]\nLe couple de démarrage du moteur est 25 Nm."
ctx = engine.retrieve("Quel est le couple de démarrage ?", [("doc.pdf", big)], 8000)
check("25 Nm" in ctx and len(ctx) < 9000, "retrieval picks the relevant page from a large document")

# ---- db + settings + secrets
db = Database(Path(os.environ["DOUBAJ_DATA_DIR"]) / "t.db")
s = Settings(db)
s.set_secret("openai", "sk-secret-123456")
raw = db.get_setting("secret:openai")
check("sk-secret" not in raw and s.get_secret("openai") == "sk-secret-123456", "API key stored encrypted")
cid = db.create_conversation("t")
m1 = db.add_message(cid, "user", "a")
db.add_message(cid, "assistant", "b")
db.delete_messages_from(cid, m1)
check(db.get_messages(cid) == [], "delete messages from id")
pid = db.create_project("Cours Technologie industrielle")
db.add_project_file(pid, "c.txt", "x", "contenu")
check(db.list_project_files(pid)[0]["extracted_text"] == "contenu", "project files")
check(engine.extract_memories("ok\n````doubaj-memory\nJ'enseigne en 2Bac\n````\n") == ["J'enseigne en 2Bac"], "memory suggestion parsing")
print(f"\nALL {ok} CHECKS PASSED")
srv.shutdown()
