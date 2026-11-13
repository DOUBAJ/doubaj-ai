"""Settings, Projects and Memory dialogs."""
from __future__ import annotations

import json
import shutil
import time
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFileDialog,
                               QFormLayout, QGroupBox, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QListWidget,
                               QListWidgetItem, QMessageBox, QPlainTextEdit, QPushButton, QSpinBox, QSplitter,
                               QTabWidget, QVBoxLayout, QWidget)

from .. import i18n
from ..config import BACKUP_DIR, FILES_DIR, MODELS_DIR
from ..core import secrets
from ..documents.reader import SUPPORTED, read_file
from ..providers.registry import PROVIDERS
from .chat_widgets import FuncWorker, icon, open_path

tr = i18n.tr


def total_ram_gb() -> float:
    try:
        import psutil
        return psutil.virtual_memory().total / 1024 ** 3
    except Exception:
        return 0.0


# ======================================================================= SETTINGS
class ProviderPage(QWidget):
    def __init__(self, settings, pid: str):
        super().__init__()
        self.s, self.pid = settings, pid
        info = PROVIDERS[pid].info
        form = QFormLayout(self)
        hint = QLabel(f"<i>{info.help}</i>")
        hint.setWordWrap(True)
        hint.setObjectName("Muted")
        form.addRow(hint)
        self.key = QLineEdit()
        self.key.setEchoMode(QLineEdit.Password)
        existing = settings.get_secret(pid)
        self.key.setPlaceholderText(secrets.mask(existing) if existing else ("(optionnel)" if not info.needs_key else "sk-…"))
        form.addRow(tr("api_key"), self.key)
        self.url = QLineEdit(settings.provider_base_url(pid))
        self.url.setPlaceholderText(info.default_base_url or "(défaut du SDK)")
        form.addRow(tr("base_url"), self.url)
        self.model = QComboBox()
        self.model.setEditable(True)
        self.model.addItems(info.suggested_models)
        self.model.setCurrentText(settings.provider_model(pid))
        row = QHBoxLayout()
        row.addWidget(self.model, 1)
        b = QPushButton(icon("mdi6.refresh"), tr("refresh_models"))
        b.clicked.connect(self.refresh)
        row.addWidget(b)
        form.addRow(tr("default_model"), row)
        tb = QPushButton(icon("mdi6.lan-connect"), tr("test"))
        tb.clicked.connect(self.test)
        self.result = QLabel("")
        self.result.setWordWrap(True)
        form.addRow(tb, self.result)
        self._w = None

    def _provider(self):
        key = self.key.text().strip() or self.s.get_secret(self.pid)
        return PROVIDERS[self.pid](api_key=key, base_url=self.url.text().strip())

    def refresh(self):
        self.result.setText("…")
        self._w = FuncWorker(self._provider().list_models)
        self._w.result.connect(self._set_models)
        self._w.failed.connect(self.result.setText)
        self._w.start()

    def _set_models(self, models):
        cur = self.model.currentText()
        self.model.clear()
        self.model.addItems(models)
        self.model.setCurrentText(cur if cur else (models[0] if models else ""))
        self.result.setText(f"{len(models)} modèles")

    def test(self):
        self.result.setText("…")
        self._w = FuncWorker(self._provider().test_connection, self.model.currentText())
        self._w.result.connect(lambda r: self.result.setText(
            ("✅ " + tr("ok_conn") + " : " if r[0] else "❌ " + tr("fail_conn") + " : ") + r[1]))
        self._w.failed.connect(lambda e: self.result.setText("❌ " + e))
        self._w.start()

    def save(self):
        if self.key.text().strip():
            self.s.set_secret(self.pid, self.key.text())
        self.s.db.set_setting(f"base_url:{self.pid}", self.url.text().strip())
        self.s.db.set_setting(f"model:{self.pid}", self.model.currentText().strip())


class LocalModelsPage(QWidget):
    def __init__(self, settings):
        super().__init__()
        self.s = settings
        lay = QVBoxLayout(self)
        help_ = QLabel(tr("local_help"))
        help_.setWordWrap(True)
        lay.addWidget(help_)
        ram = total_ram_gb()
        lay.addWidget(QLabel(f"<b>{tr('ram_info')} :</b> {ram:.1f} Go" if ram else ""))
        lay.addWidget(QLabel(f"<b>{tr('installed_models')}</b>"))
        self.list = QListWidget()
        lay.addWidget(self.list, 1)
        row = QHBoxLayout()
        self.pull_name = QComboBox()
        self.pull_name.setEditable(True)
        self.pull_name.addItems(["llama3.2:3b  (≈2 Go)", "qwen2.5:7b  (≈4.7 Go, bon en arabe/français)",
                                 "mistral:7b  (≈4.1 Go)", "gemma3:4b  (≈3.3 Go, vision)",
                                 "llava:7b  (≈4.7 Go, vision)", "qwen2.5-coder:7b  (≈4.7 Go, code)"])
        row.addWidget(self.pull_name, 1)
        pb = QPushButton(icon("mdi6.download"), tr("pull_model"))
        pb.clicked.connect(self.pull)
        row.addWidget(pb)
        rb = QPushButton(icon("mdi6.refresh"), "")
        rb.clicked.connect(self.refresh)
        row.addWidget(rb)
        lay.addLayout(row)
        ib = QPushButton(icon("mdi6.file-import-outline"), tr("import_gguf"))
        ib.clicked.connect(self.import_gguf)
        lay.addWidget(ib)
        self.status = QLabel("")
        self.status.setWordWrap(True)
        lay.addWidget(self.status)
        self._w = None
        self.refresh()

    def _root(self):
        return self.s.provider_base_url("ollama").rstrip("/").removesuffix("/v1")

    def refresh(self):
        self.list.clear()
        import httpx

        def fetch():
            return httpx.get(self._root() + "/api/tags", timeout=4).json().get("models", [])
        self._w = FuncWorker(fetch)
        self._w.result.connect(self._fill)
        self._w.failed.connect(lambda e: self.status.setText("Ollama non détecté (" + self._root() + "). Installez-le depuis ollama.com puis relancez."))
        self._w.start()

    def _fill(self, models):
        ram = total_ram_gb()
        for m in models:
            size = m.get("size", 0) / 1024 ** 3
            need = size * 1.2 + 1
            ok = "✅" if not ram or need < ram * 0.8 else "⚠️"
            d = m.get("details", {})
            self.list.addItem(f"{ok} {m['name']} — {size:.1f} Go · {d.get('parameter_size', '')} {d.get('quantization_level', '')}"
                              f" · RAM/VRAM ≈ {need:.1f} Go")
        self.status.setText(f"{len(models)} modèle(s) – Ollama OK")

    def pull(self):
        name = self.pull_name.currentText().split()[0]
        import httpx

        def do():
            with httpx.stream("POST", self._root() + "/api/pull", json={"name": name}, timeout=None) as r:
                last = ""
                for line in r.iter_lines():
                    try:
                        last = json.loads(line).get("status", "")
                    except ValueError:
                        pass
                return last
        self.status.setText(f"Téléchargement de {name}… (peut prendre plusieurs minutes)")
        self._w = FuncWorker(do)
        self._w.result.connect(lambda s: (self.status.setText(f"{name} : {s}"), self.refresh()))
        self._w.failed.connect(lambda e: self.status.setText("❌ " + e))
        self._w.start()

    def import_gguf(self):
        path, _ = QFileDialog.getOpenFileName(self, tr("import_gguf"), "", "GGUF (*.gguf)")
        if not path:
            return
        dest = MODELS_DIR / Path(path).name
        if not dest.exists():
            shutil.copyfile(path, dest)
        name, ok = QInputDialog.getText(self, "Ollama", tr("name"), text=Path(path).stem.lower()[:40])
        if not ok or not name:
            return
        import httpx

        def create_model():
            # Ollama: create a model from a local GGUF through a Modelfile (ollama CLI)
            import subprocess
            mf = MODELS_DIR / f"{name}.Modelfile"
            mf.write_text(f"FROM {dest}\n", encoding="utf-8")
            p = subprocess.run(["ollama", "create", name, "-f", str(mf)], capture_output=True, text=True)
            if p.returncode != 0:
                raise RuntimeError(p.stderr or "ollama create failed")
            return name
        size = dest.stat().st_size / 1024 ** 3
        self.status.setText(f"Import… ({size:.1f} Go, RAM/VRAM nécessaire ≈ {size * 1.2 + 1:.1f} Go)")
        self._w = FuncWorker(create_model)
        self._w.result.connect(lambda n: (self.status.setText(f"✅ {n} importé"), self.refresh()))
        self._w.failed.connect(lambda e: self.status.setText(
            f"❌ {e}\nAlternative : lancez llama.cpp → llama-server -m \"{dest}\" --port 8080 puis choisissez « llama.cpp server »."))
        self._w.start()


class SettingsDialog(QDialog):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.s = settings
        self.setWindowTitle(tr("settings"))
        self.resize(780, 620)
        lay = QVBoxLayout(self)
        tabs = QTabWidget()
        lay.addWidget(tabs)

        # providers
        pw = QWidget()
        pl = QVBoxLayout(pw)
        self.ptabs = QTabWidget()
        self.pages = {}
        for pid, cls in PROVIDERS.items():
            page = ProviderPage(settings, pid)
            self.pages[pid] = page
            self.ptabs.addTab(page, cls.info.label)
        pl.addWidget(self.ptabs)
        sec = QLabel(f"🔒 {tr('key_secure')} {secrets.SECURE_BACKEND}")
        sec.setObjectName("Muted")
        pl.addWidget(sec)
        tabs.addTab(pw, tr("providers"))

        # general
        gw = QWidget()
        gf = QFormLayout(gw)
        self.lang = QComboBox()
        for code, label in (("fr", "Français"), ("ar", "العربية"), ("en", "English")):
            self.lang.addItem(label, code)
        self.lang.setCurrentIndex(["fr", "ar", "en"].index(settings.get("lang")))
        gf.addRow(tr("language"), self.lang)
        self.dark = QCheckBox()
        self.dark.setChecked(settings.get("theme") == "dark")
        gf.addRow(tr("dark_mode"), self.dark)
        self.temp_auto = QCheckBox(tr("auto"))
        self.temp = QDoubleSpinBox()
        self.temp.setRange(0, 2)
        self.temp.setSingleStep(0.1)
        t = settings.get("temperature")
        self.temp_auto.setChecked(t is None)
        self.temp.setValue(0.7 if t is None else float(t))
        row = QHBoxLayout()
        row.addWidget(self.temp_auto)
        row.addWidget(self.temp)
        note = QLabel("(ignorée par les modèles récents qui ne la supportent pas)")
        note.setObjectName("Muted")
        row.addWidget(note)
        gf.addRow(tr("temperature"), row)
        self.length = QComboBox()
        for k in ("short", "normal", "long"):
            self.length.addItem(tr("l_" + k), k)
        self.length.setCurrentIndex(["short", "normal", "long"].index(settings.get("length")))
        gf.addRow(tr("length"), self.length)
        self.max_tokens = QSpinBox()
        self.max_tokens.setRange(256, 128000)
        self.max_tokens.setSingleStep(1024)
        self.max_tokens.setValue(int(settings.get("max_tokens")))
        gf.addRow(tr("max_tokens"), self.max_tokens)
        self.ctx = QSpinBox()
        self.ctx.setRange(4000, 3_000_000)
        self.ctx.setSingleStep(10000)
        self.ctx.setValue(int(settings.get("context_chars")))
        ctx_note = QLabel("≈ 4 caractères = 1 token. Réduisez pour les petits modèles locaux (ex. 24 000).")
        ctx_note.setObjectName("Muted")
        gf.addRow(tr("context_chars"), self.ctx)
        gf.addRow("", ctx_note)
        self.web_backend = QComboBox()
        for k, label in (("duckduckgo", "DuckDuckGo (gratuit, sans clé)"), ("tavily", "Tavily (clé API)"), ("brave", "Brave Search (clé API)")):
            self.web_backend.addItem(label, k)
        self.web_backend.setCurrentIndex(max(0, ["duckduckgo", "tavily", "brave"].index(settings.get("web_backend"))))
        gf.addRow(tr("web_backend"), self.web_backend)
        self.web_key = QLineEdit()
        self.web_key.setEchoMode(QLineEdit.Password)
        self.web_key.setPlaceholderText(secrets.mask(settings.get_secret("web")) or "Tavily / Brave")
        gf.addRow(tr("api_key") + " (web)", self.web_key)
        tabs.addTab(gw, tr("general"))

        # local models
        tabs.addTab(LocalModelsPage(settings), tr("local_models"))

        # voice & images
        vw = QWidget()
        vf = QFormLayout(vw)
        self.voice = QComboBox()
        self.voice.addItem("(défaut système)", "")
        try:
            from PySide6.QtTextToSpeech import QTextToSpeech
            tts = QTextToSpeech()
            for v in tts.availableVoices():
                self.voice.addItem(f"{v.name()} – {v.locale().nativeLanguageName()}", v.name())
            idx = self.voice.findData(settings.get("tts_voice"))
            if idx >= 0:
                self.voice.setCurrentIndex(idx)
        except Exception:
            pass
        vf.addRow(tr("tts_voice"), self.voice)
        self.rate = QDoubleSpinBox()
        self.rate.setRange(-1, 1)
        self.rate.setSingleStep(0.1)
        self.rate.setValue(float(settings.get("tts_rate")))
        vf.addRow(tr("tts_rate"), self.rate)
        g = QGroupBox(tr("stt_service"))
        gfl = QFormLayout(g)
        self.stt_url = QLineEdit(settings.get("stt_url"))
        self.stt_model = QLineEdit(settings.get("stt_model"))
        self.stt_key = QLineEdit()
        self.stt_key.setEchoMode(QLineEdit.Password)
        self.stt_key.setPlaceholderText(secrets.mask(settings.get_secret("stt")) or tr("same_as_openai"))
        gfl.addRow(tr("base_url"), self.stt_url)
        gfl.addRow(tr("model"), self.stt_model)
        gfl.addRow(tr("api_key"), self.stt_key)
        vf.addRow(g)
        g2 = QGroupBox(tr("img_service"))
        g2l = QFormLayout(g2)
        self.img_url = QLineEdit(settings.get("img_url"))
        self.img_model = QLineEdit(settings.get("img_model"))
        self.img_key = QLineEdit()
        self.img_key.setEchoMode(QLineEdit.Password)
        self.img_key.setPlaceholderText(secrets.mask(settings.get_secret("img")) or tr("same_as_openai"))
        g2l.addRow(tr("base_url"), self.img_url)
        g2l.addRow(tr("model"), self.img_model)
        g2l.addRow(tr("api_key"), self.img_key)
        vf.addRow(g2)
        tabs.addTab(vw, tr("voice_tab") + " / " + tr("images_tab"))

        # privacy
        prw = QWidget()
        prl = QVBoxLayout(prw)
        self.mem_on = QCheckBox(tr("memory_enabled"))
        self.mem_on.setChecked(bool(settings.get("memory_enabled")))
        self.confirm_up = QCheckBox(tr("confirm_upload"))
        self.confirm_up.setChecked(bool(settings.get("confirm_upload")))
        self.sandbox = QCheckBox(tr("sandbox_restricted"))
        self.sandbox.setChecked(bool(settings.get("sandbox_restricted")))
        for w in (self.mem_on, self.confirm_up, self.sandbox):
            prl.addWidget(w)
        info = QLabel("• Conversations, projets et fichiers sont enregistrés localement dans le dossier « data » à côté de l'application.\n"
                      "• Les fichiers ne sont envoyés à un service en ligne que lorsque vous les joignez à un message.\n"
                      "• Le code n'est jamais exécuté sans votre confirmation.\n"
                      "• Les clés API sont chiffrées et ne sont jamais écrites dans les journaux.")
        info.setWordWrap(True)
        info.setObjectName("Muted")
        prl.addWidget(info)
        b1 = QPushButton(icon("mdi6.backup-restore"), tr("backup"))
        b1.clicked.connect(self.backup)
        b2 = QPushButton(icon("mdi6.delete-alert-outline"), tr("delete_all"))
        b2.setObjectName("Danger")
        b2.clicked.connect(self.delete_all)
        b3 = QPushButton(icon("mdi6.folder-open-outline"), tr("open_folder"))
        b3.clicked.connect(lambda: open_path(str(FILES_DIR.parent)))
        for b in (b1, b2, b3):
            prl.addWidget(b)
        prl.addStretch()
        tabs.addTab(prw, tr("privacy"))

        # about
        ab = QLabel("<h2>DOUBAJ AI</h2><p>Réalisé par <b>Doubaj Ahmed</b> – Professeur de technologie industrielle.<br>"
                    "من إعداد دباج أحمد – أستاذ مادة التكنولوجيا الصناعية</p>"
                    "<p>DOUBAJ AI est une application cliente : l'intelligence provient des modèles du fournisseur choisi "
                    "(Anthropic, OpenAI, Google, ou un modèle local via Ollama / llama.cpp). DOUBAJ AI ne possède pas son propre modèle.</p>"
                    "<p>Police coranique : Amiri (SIL Open Font License).</p>"
                    "<p>Tous droits réservés : Doubaj Ahmed – DOUBAJ AHMED.</p>")
        ab.setWordWrap(True)
        ab.setAlignment(Qt.AlignTop)
        tabs.addTab(ab, tr("about"))

        bb = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Save).setText(tr("save"))
        bb.button(QDialogButtonBox.Cancel).setText(tr("cancel"))
        bb.accepted.connect(self.save)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def backup(self):
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        dest = BACKUP_DIR / f"doubaj_backup_{time.strftime('%Y%m%d_%H%M%S')}.sqlite3"
        self.s.db.backup_to(dest)
        QMessageBox.information(self, "DOUBAJ AI", str(dest))

    def delete_all(self):
        if QMessageBox.question(self, "DOUBAJ AI", tr("confirm_delete")) == QMessageBox.Yes:
            self.s.db.delete_all_conversations()

    def save(self):
        for p in self.pages.values():
            p.save()
        s = self.s
        s.set("lang", self.lang.currentData())
        s.set("theme", "dark" if self.dark.isChecked() else "light")
        s.set("temperature", None if self.temp_auto.isChecked() else self.temp.value())
        s.set("length", self.length.currentData())
        s.set("max_tokens", self.max_tokens.value())
        s.set("context_chars", self.ctx.value())
        s.set("web_backend", self.web_backend.currentData())
        if self.web_key.text().strip():
            s.set_secret("web", self.web_key.text())
        s.set("tts_voice", self.voice.currentData() or "")
        s.set("tts_rate", self.rate.value())
        s.set("stt_url", self.stt_url.text().strip())
        s.set("stt_model", self.stt_model.text().strip())
        if self.stt_key.text().strip():
            s.set_secret("stt", self.stt_key.text())
        s.set("img_url", self.img_url.text().strip())
        s.set("img_model", self.img_model.text().strip())
        if self.img_key.text().strip():
            s.set_secret("img", self.img_key.text())
        s.set("memory_enabled", self.mem_on.isChecked())
        s.set("confirm_upload", self.confirm_up.isChecked())
        s.set("sandbox_restricted", self.sandbox.isChecked())
        self.accept()


# ======================================================================= PROJECTS
class ProjectsDialog(QDialog):
    def __init__(self, db, parent=None, select_id=None):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle(tr("projects"))
        self.resize(900, 600)
        self.current = None
        lay = QHBoxLayout(self)
        split = QSplitter()
        lay.addWidget(split)
        left = QWidget()
        ll = QVBoxLayout(left)
        nb = QPushButton(icon("mdi6.plus"), tr("new_project"))
        nb.setObjectName("Primary")
        nb.clicked.connect(self.new_project)
        ll.addWidget(nb)
        self.list = QListWidget()
        self.list.currentItemChanged.connect(self._select)
        ll.addWidget(self.list, 1)
        split.addWidget(left)

        right = QWidget()
        rl = QVBoxLayout(right)
        form = QFormLayout()
        self.name = QLineEdit()
        self.desc = QLineEdit()
        self.instr = QPlainTextEdit()
        self.instr.setPlaceholderText("Ex. : Réponds en français, niveau 2e année Bac Sciences et Technologies, "
                                      "respecte le programme officiel…")
        form.addRow(tr("name"), self.name)
        form.addRow(tr("description"), self.desc)
        form.addRow(tr("instructions"), self.instr)
        rl.addLayout(form)
        tabs = QTabWidget()
        fw = QWidget()
        fl = QVBoxLayout(fw)
        self.files = QListWidget()
        fl.addWidget(self.files)
        fr = QHBoxLayout()
        ab = QPushButton(icon("mdi6.file-plus-outline"), tr("add"))
        ab.clicked.connect(self.add_files)
        db_ = QPushButton(icon("mdi6.delete-outline"), tr("delete"))
        db_.clicked.connect(self.del_file)
        fr.addWidget(ab)
        fr.addWidget(db_)
        fr.addStretch()
        fl.addLayout(fr)
        tabs.addTab(fw, tr("project_files"))
        self.chats = QListWidget()
        tabs.addTab(self.chats, tr("project_chats"))
        self.outputs = QListWidget()
        self.outputs.itemDoubleClicked.connect(lambda it: open_path(it.data(Qt.UserRole)))
        tabs.addTab(self.outputs, tr("project_outputs"))
        rl.addWidget(tabs, 1)
        br = QHBoxLayout()
        sb = QPushButton(icon("mdi6.content-save"), tr("save"))
        sb.setObjectName("Primary")
        sb.clicked.connect(self.save)
        delb = QPushButton(icon("mdi6.delete"), tr("delete"))
        delb.setObjectName("Danger")
        delb.clicked.connect(self.delete)
        self.activate_btn = QPushButton(icon("mdi6.check-circle-outline"), tr("active_project"))
        self.activate_btn.clicked.connect(self.accept)
        br.addWidget(sb)
        br.addWidget(delb)
        br.addStretch()
        br.addWidget(self.activate_btn)
        rl.addLayout(br)
        self.status = QLabel("")
        self.status.setObjectName("Muted")
        rl.addWidget(self.status)
        split.addWidget(right)
        split.setSizes([260, 640])
        self._w = None
        self.reload(select_id)

    def reload(self, select_id=None):
        self.list.clear()
        for p in self.db.list_projects():
            it = QListWidgetItem(icon("mdi6.folder-outline"), p["name"])
            it.setData(Qt.UserRole, p["id"])
            self.list.addItem(it)
            if p["id"] == select_id:
                self.list.setCurrentItem(it)
        if self.list.currentItem() is None and self.list.count():
            self.list.setCurrentRow(0)

    def _select(self, it, _prev=None):
        if not it:
            self.current = None
            return
        p = self.db.get_project(it.data(Qt.UserRole))
        self.current = p["id"]
        self.name.setText(p["name"])
        self.desc.setText(p["description"])
        self.instr.setPlainText(p["instructions"])
        self.files.clear()
        for f in self.db.list_project_files(p["id"]):
            item = QListWidgetItem(f"{f['name']}  ({len(f['extracted_text'] or ''):,} car.)")
            item.setData(Qt.UserRole, f["id"])
            self.files.addItem(item)
        self.chats.clear()
        for c in self.db.list_conversations(project_id=p["id"]):
            self.chats.addItem(c["title"])
        self.outputs.clear()
        for o in self.db.list_outputs(p["id"]):
            item = QListWidgetItem(o["name"])
            item.setData(Qt.UserRole, o["path"])
            self.outputs.addItem(item)

    def new_project(self):
        name, ok = QInputDialog.getText(self, tr("new_project"), tr("name"))
        if ok and name.strip():
            pid = self.db.create_project(name.strip())
            self.reload(pid)

    def save(self):
        if self.current:
            self.db.update_project(self.current, self.name.text(), self.desc.text(), self.instr.toPlainText())
            self.reload(self.current)

    def delete(self):
        if self.current and QMessageBox.question(self, "DOUBAJ AI", tr("confirm_delete")) == QMessageBox.Yes:
            self.db.delete_project(self.current)
            self.current = None
            self.reload()

    def add_files(self):
        if not self.current:
            return
        paths, _ = QFileDialog.getOpenFileNames(self, tr("add"), "", "Documents (" + " ".join("*" + e for e in SUPPORTED) + ");;*.*")
        if not paths:
            return
        pid = self.current

        def work():
            done = []
            dest_dir = FILES_DIR / f"project_{pid}"
            dest_dir.mkdir(parents=True, exist_ok=True)
            for p in paths:
                dest = dest_dir / Path(p).name
                shutil.copyfile(p, dest)
                r = read_file(dest)
                text = r.text or ("\n".join(r.warnings))
                self.db.add_project_file(pid, r.name, str(dest), text)
                done.append(r.name)
            return done
        self.status.setText(tr("reading"))
        self._w = FuncWorker(work)
        self._w.result.connect(lambda d: (self.status.setText(", ".join(d)), self._select(self.list.currentItem())))
        self._w.failed.connect(self.status.setText)
        self._w.start()

    def del_file(self):
        it = self.files.currentItem()
        if it:
            self.db.delete_project_file(it.data(Qt.UserRole))
            self._select(self.list.currentItem())


# ======================================================================= MEMORY
class MemoryDialog(QDialog):
    def __init__(self, db, settings, parent=None):
        super().__init__(parent)
        self.db, self.s = db, settings
        self.setWindowTitle(tr("memory"))
        self.resize(640, 480)
        lay = QVBoxLayout(self)
        self.enabled = QCheckBox(tr("memory_enabled"))
        self.enabled.setChecked(bool(settings.get("memory_enabled")))
        self.enabled.toggled.connect(lambda v: settings.set("memory_enabled", v))
        lay.addWidget(self.enabled)
        self.list = QListWidget()
        self.list.itemDoubleClicked.connect(self.edit)
        lay.addWidget(self.list, 1)
        row = QHBoxLayout()
        for text, ic, fn in ((tr("add"), "mdi6.plus", self.add), (tr("edit_memory"), "mdi6.pencil", lambda: self.edit(self.list.currentItem())),
                             (tr("delete"), "mdi6.delete-outline", self.delete), (tr("clear_all"), "mdi6.delete-sweep", self.clear)):
            b = QPushButton(icon(ic), text)
            b.clicked.connect(fn)
            row.addWidget(b)
        lay.addLayout(row)
        close = QPushButton(tr("close"))
        close.clicked.connect(self.accept)
        lay.addWidget(close)
        self.reload()

    def reload(self):
        self.list.clear()
        projects = {p["id"]: p["name"] for p in self.db.list_projects()}
        for m in self.db.list_memories():
            scope = projects.get(m["project_id"], tr("global")) if m["project_id"] else tr("global")
            it = QListWidgetItem(f"[{scope}] {m['content']}")
            it.setData(Qt.UserRole, m["id"])
            it.setData(Qt.UserRole + 1, m["content"])
            self.list.addItem(it)

    def add(self):
        text, ok = QInputDialog.getMultiLineText(self, tr("memory"), tr("add"))
        if ok and text.strip():
            self.db.add_memory(text.strip())
            self.reload()

    def edit(self, it):
        if not it:
            return
        text, ok = QInputDialog.getMultiLineText(self, tr("memory"), tr("edit_memory"), it.data(Qt.UserRole + 1))
        if ok and text.strip():
            self.db.update_memory(it.data(Qt.UserRole), text.strip())
            self.reload()

    def delete(self):
        it = self.list.currentItem()
        if it:
            self.db.delete_memory(it.data(Qt.UserRole))
            self.reload()

    def clear(self):
        if QMessageBox.question(self, "DOUBAJ AI", tr("confirm_delete")) == QMessageBox.Yes:
            self.db.clear_memories()
            self.reload()
