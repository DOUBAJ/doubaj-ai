"""Main application window."""
from __future__ import annotations

import json
import re
import shutil
import tempfile
import time
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QAction, QKeySequence, QShortcut
from PySide6.QtWidgets import (QApplication, QComboBox, QFileDialog, QFrame, QHBoxLayout, QInputDialog, QLabel,
                               QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QMenu, QMessageBox,
                               QPlainTextEdit, QPushButton, QScrollArea, QSizePolicy, QSplitter, QToolButton,
                               QVBoxLayout, QWidget)

from .. import i18n
from ..config import FILES_DIR, OUTPUT_DIR
from ..core import engine
from ..core.markdown_render import is_rtl
from ..core.settings import Settings
from ..documents.generator import extract_and_generate
from ..documents.reader import SUPPORTED
from ..providers.base import CancelToken
from ..providers.registry import PROVIDERS
from ..tools import media, web_search
from .chat_widgets import ChatWorker, FuncWorker, MessageWidget, icon
from .dialogs import MemoryDialog, ProjectsDialog, SettingsDialog
from .logo import logo_pixmap
from .theme import PALETTES, stylesheet
from .workspace import Workspace

tr = i18n.tr
PY_BLOCK = re.compile(r"```(?:python|py)\s*\n(.*?)```", re.S)


class Composer(QPlainTextEdit):
    submitted = Signal()

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key_Return, Qt.Key_Enter) and not (e.modifiers() & Qt.ShiftModifier):
            self.submitted.emit()
            return
        super().keyPressEvent(e)

    def canInsertFromMimeData(self, source):
        return source.hasUrls() or super().canInsertFromMimeData(source)

    def insertFromMimeData(self, source):
        if source.hasUrls():
            self.window().add_attachments([u.toLocalFile() for u in source.urls() if u.isLocalFile()])
        else:
            super().insertFromMimeData(source)


class MainWindow(QMainWindow):
    rebuild_requested = Signal()

    def __init__(self, db):
        super().__init__()
        self.db = db
        self.s = Settings(db)
        self.theme = self.s.get("theme")
        self.conv_id: int | None = None
        self.project_id: int | None = self.s.get("active_project")
        if self.project_id and not db.get_project(self.project_id):
            self.project_id = None
        self.pending: list[dict] = []
        self.worker: ChatWorker | None = None
        self.cancel: CancelToken | None = None
        self.ai_widget: MessageWidget | None = None
        self._bg = []  # keep refs to background workers
        self.tts = None
        self.recorder = None

        self.setWindowTitle("DOUBAJ AI")
        self.resize(1400, 860)
        self.setLayoutDirection(Qt.RightToLeft if i18n.is_rtl() else Qt.LeftToRight)
        self.setAcceptDrops(True)
        self._build()
        self.apply_theme()
        self.refresh_conversations()
        self.refresh_projects()
        self.show_welcome()
        QShortcut(QKeySequence("Ctrl+N"), self, activated=self.new_chat)
        QShortcut(QKeySequence("Esc"), self, activated=self.stop)

    # ================================================================ UI
    def _build(self):
        split = QSplitter(Qt.Horizontal)
        split.setHandleWidth(1)
        self.setCentralWidget(split)

        # ---------- sidebar
        side = QWidget()
        side.setObjectName("Sidebar")
        side.setMinimumWidth(230)
        sl = QVBoxLayout(side)
        sl.setContentsMargins(10, 12, 10, 10)
        brand = QHBoxLayout()
        lg = QLabel()
        lg.setPixmap(logo_pixmap(34))
        brand.addWidget(lg)
        bt = QLabel("DOUBAJ AI")
        bt.setObjectName("Brand")
        brand.addWidget(bt)
        brand.addStretch()
        sl.addLayout(brand)
        nb = QPushButton(icon("mdi6.plus", "#FFFFFF"), "  " + tr("new_chat"))
        nb.setObjectName("Primary")
        nb.setCursor(Qt.PointingHandCursor)
        nb.setMinimumHeight(36)
        nb.clicked.connect(self.new_chat)
        sl.addWidget(nb)
        self.search = QLineEdit()
        self.search.setPlaceholderText(tr("search_chats"))
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(lambda _: QTimer.singleShot(200, self.refresh_conversations))
        sl.addWidget(self.search)
        self.conv_list = QListWidget()
        self.conv_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.conv_list.setTextElideMode(Qt.ElideRight)
        self.conv_list.setWordWrap(False)
        self.conv_list.itemClicked.connect(lambda it: self.open_conversation(it.data(Qt.UserRole)))
        self.conv_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.conv_list.customContextMenuRequested.connect(self._conv_menu)
        sl.addWidget(self.conv_list, 1)
        for text, ic, fn in ((tr("projects"), "mdi6.folder-multiple-outline", self.open_projects),
                             (tr("memory"), "mdi6.brain", self.open_memory),
                             (tr("files"), "mdi6.file-multiple-outline", self.show_files),
                             (tr("settings"), "mdi6.cog-outline", self.open_settings)):
            b = QPushButton(icon(ic), "  " + text)
            b.setStyleSheet("text-align: left; border: none; background: transparent; padding: 8px;")
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(fn)
            sl.addWidget(b)
        credit = QLabel("© Doubaj Ahmed")
        credit.setObjectName("Muted")
        credit.setAlignment(Qt.AlignCenter)
        sl.addWidget(credit)
        split.addWidget(side)

        # ---------- center
        center = QWidget()
        center.setObjectName("ChatArea")
        cl = QVBoxLayout(center)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(0)
        top = QWidget()
        top.setObjectName("TopBar")
        tl = QHBoxLayout(top)
        tl.setContentsMargins(12, 6, 12, 6)
        self.project_combo = QComboBox()
        self.project_combo.setToolTip(tr("active_project"))
        self.project_combo.setMinimumWidth(150)
        self.project_combo.activated.connect(self._project_changed)
        tl.addWidget(QLabel("📁"))
        tl.addWidget(self.project_combo)
        tl.addStretch()
        self.provider_combo = QComboBox()
        self.provider_combo.setToolTip(tr("provider"))
        for pid, cls in PROVIDERS.items():
            self.provider_combo.addItem(cls.info.label, pid)
        self.provider_combo.setCurrentIndex(max(0, self.provider_combo.findData(self.s.get("provider"))))
        self.provider_combo.currentIndexChanged.connect(self._provider_changed)
        tl.addWidget(self.provider_combo)
        self.model_combo = QComboBox()
        self.model_combo.setEditable(True)
        self.model_combo.setMinimumWidth(190)
        self.model_combo.setToolTip(tr("model"))
        self.model_combo.lineEdit().editingFinished.connect(self._model_changed)
        self.model_combo.activated.connect(lambda _: self._model_changed())
        tl.addWidget(self.model_combo)
        self.reason_combo = QComboBox()
        self.reason_combo.setToolTip(tr("reasoning"))
        for k in ("fast", "standard", "deep"):
            self.reason_combo.addItem(tr("r_" + k), k)
        self.reason_combo.setCurrentIndex(["fast", "standard", "deep"].index(self.s.get("reasoning")))
        self.reason_combo.currentIndexChanged.connect(lambda _: self.s.set("reasoning", self.reason_combo.currentData()))
        tl.addWidget(self.reason_combo)
        self.mode_combo = QComboBox()
        self.mode_combo.setToolTip(tr("mode"))
        for k, ic in (("general", "mdi6.chat-outline"), ("education", "mdi6.school-outline"), ("code", "mdi6.code-braces")):
            self.mode_combo.addItem(icon(ic), tr("m_" + k), k)
        self.mode_combo.setCurrentIndex(["general", "education", "code"].index(self.s.get("mode")))
        self.mode_combo.currentIndexChanged.connect(lambda _: self.s.set("mode", self.mode_combo.currentData()))
        tl.addWidget(self.mode_combo)
        self.net_label = QLabel()
        tl.addWidget(self.net_label)
        self.lang_combo = QComboBox()
        for code, label in (("fr", "FR"), ("ar", "ع"), ("en", "EN")):
            self.lang_combo.addItem(label, code)
        self.lang_combo.setCurrentIndex(["fr", "ar", "en"].index(i18n.lang()))
        self.lang_combo.activated.connect(self._lang_changed)
        tl.addWidget(self.lang_combo)
        self.theme_btn = QToolButton()
        self.theme_btn.setToolTip(tr("theme"))
        self.theme_btn.clicked.connect(self.toggle_theme)
        tl.addWidget(self.theme_btn)
        self.ws_btn = QToolButton()
        self.ws_btn.setCheckable(True)
        self.ws_btn.setToolTip(tr("workspace"))
        self.ws_btn.setIcon(icon("mdi6.dock-right"))
        self.ws_btn.toggled.connect(self.toggle_workspace)
        tl.addWidget(self.ws_btn)
        cl.addWidget(top)

        self.scroll = QScrollArea()
        self.scroll.setObjectName("ChatScroll")
        self.scroll.setWidgetResizable(True)
        self.inner = QWidget()
        self.inner.setObjectName("ChatInner")
        self.msgs_layout = QVBoxLayout(self.inner)
        self.msgs_layout.setContentsMargins(40, 20, 40, 20)
        self.msgs_layout.setSpacing(14)
        self.msgs_layout.addStretch()
        self.scroll.setWidget(self.inner)
        cl.addWidget(self.scroll, 1)

        # composer
        wrap = QWidget()
        wl = QVBoxLayout(wrap)
        wl.setContentsMargins(40, 6, 40, 14)
        box = QFrame()
        box.setObjectName("Composer")
        bl = QVBoxLayout(box)
        bl.setContentsMargins(10, 8, 10, 8)
        self.chips = QHBoxLayout()
        self.chips.setSpacing(6)
        self.chips.addStretch()
        bl.addLayout(self.chips)
        self.input = Composer()
        self.input.setObjectName("ComposerEdit")
        self.input.setPlaceholderText(tr("placeholder"))
        self.input.setFixedHeight(76)
        self.input.submitted.connect(self.send)
        bl.addWidget(self.input)
        row = QHBoxLayout()

        def tb(ic, tip, fn=None, checkable=False):
            b = QToolButton()
            b.setIcon(icon(ic))
            b.setIconSize(QSize(20, 20))
            b.setToolTip(tip)
            b.setCheckable(checkable)
            b.setCursor(Qt.PointingHandCursor)
            if fn:
                b.clicked.connect(fn)
            row.addWidget(b)
            return b
        tb("mdi6.paperclip", tr("attach"), self.pick_files)
        self.web_btn = tb("mdi6.web", tr("web"), checkable=True)
        self.tools_btn = tb("mdi6.tools", tr("tools"))
        self.tools_btn.setPopupMode(QToolButton.InstantPopup)
        menu = QMenu(self)
        menu.addAction(icon("mdi6.image-plus"), tr("gen_image"), self.generate_image)
        menu.addAction(icon("mdi6.language-python"), tr("run_code"), self.run_last_python)
        menu.addAction(icon("mdi6.brain"), tr("add_memory"), self.quick_memory)
        menu.addAction(icon("mdi6.play-pause"), tr("pause_resume"), self.tts_pause_resume)
        self.tools_btn.setMenu(menu)
        self.mic_btn = tb("mdi6.microphone-outline", tr("voice"), self.toggle_recording, checkable=True)
        row.addStretch()
        self.status_lbl = QLabel("")
        self.status_lbl.setObjectName("Muted")
        row.addWidget(self.status_lbl)
        self.send_btn = QToolButton()
        self.send_btn.setObjectName("SendBtn")
        self.send_btn.setIcon(icon("mdi6.arrow-up", "#FFFFFF"))
        self.send_btn.setIconSize(QSize(20, 20))
        self.send_btn.setToolTip(tr("send"))
        self.send_btn.setCursor(Qt.PointingHandCursor)
        self.send_btn.clicked.connect(self._send_or_stop)
        row.addWidget(self.send_btn)
        bl.addLayout(row)
        wl.addWidget(box)
        cl.addWidget(wrap)
        split.addWidget(center)

        # ---------- workspace
        self.workspace = Workspace(self.db, self.theme)
        self.workspace.setMinimumWidth(380)
        self.workspace.improve_requested.connect(self._improve)
        split.addWidget(self.workspace)
        split.setStretchFactor(1, 1)
        split.setSizes([260, 820, 480])
        self.workspace.hide()
        self.split = split
        self._provider_changed(init=True)

    # ================================================================ theme / lang
    def apply_theme(self):
        QApplication.instance().setStyleSheet(stylesheet(self.theme))
        self.theme_btn.setIcon(icon("mdi6.weather-night" if self.theme == "light" else "mdi6.white-balance-sunny"))
        self.workspace.theme = self.theme

    def toggle_theme(self):
        self.theme = "dark" if self.theme == "light" else "light"
        self.s.set("theme", self.theme)
        self.apply_theme()
        if self.conv_id:
            self.open_conversation(self.conv_id)
        else:
            self.show_welcome()

    def _lang_changed(self, _):
        self.s.set("lang", self.lang_combo.currentData())
        self.rebuild_requested.emit()

    def toggle_workspace(self, on: bool):
        self.workspace.setVisible(on)

    # ================================================================ providers
    def current_provider_id(self) -> str:
        return self.provider_combo.currentData()

    def _provider_changed(self, *_, init=False):
        pid = self.current_provider_id()
        if not init:
            self.s.set("provider", pid)
        info = PROVIDERS[pid].info
        self.model_combo.blockSignals(True)
        self.model_combo.clear()
        self.model_combo.addItems(info.suggested_models)
        self.model_combo.setCurrentText(self.s.provider_model(pid))
        self.model_combo.blockSignals(False)
        c = PALETTES[self.theme]
        if info.local:
            self.net_label.setText(f"<span style='color:{c['accent2']}'>● {tr('offline')}</span>")
        else:
            self.net_label.setText(f"<span style='color:{c['accent']}'>● {tr('online')}</span>")
        # load the real model list in background (local servers / API)
        if self.s.provider_ready(pid):
            w = FuncWorker(self.s.make_provider(pid).list_models)
            w.result.connect(lambda models, p=pid: self._fill_models(p, models))
            self._bg.append(w)
            w.start()

    def _fill_models(self, pid, models):
        if pid != self.current_provider_id() or not models:
            return
        cur = self.model_combo.currentText()
        self.model_combo.blockSignals(True)
        self.model_combo.clear()
        self.model_combo.addItems(models)
        self.model_combo.setCurrentText(cur)
        self.model_combo.blockSignals(False)

    def _model_changed(self):
        self.db.set_setting(f"model:{self.current_provider_id()}", self.model_combo.currentText().strip())

    # ================================================================ projects
    def refresh_projects(self):
        self.project_combo.clear()
        self.project_combo.addItem(tr("no_project"), None)
        for p in self.db.list_projects():
            self.project_combo.addItem(p["name"], p["id"])
        idx = self.project_combo.findData(self.project_id)
        self.project_combo.setCurrentIndex(idx if idx >= 0 else 0)

    def _project_changed(self, _):
        self.project_id = self.project_combo.currentData()
        self.s.set("active_project", self.project_id)
        if self.conv_id:
            self.db.set_conversation_project(self.conv_id, self.project_id)
        self.workspace.refresh_files(None)

    def open_projects(self):
        dlg = ProjectsDialog(self.db, self, self.project_id)
        if dlg.exec() and dlg.current:
            self.project_id = dlg.current
            self.s.set("active_project", self.project_id)
            self.new_chat()
        self.refresh_projects()

    def open_memory(self):
        MemoryDialog(self.db, self.s, self).exec()

    def open_settings(self):
        old_lang = self.s.get("lang")
        dlg = SettingsDialog(self.s, self)
        if dlg.exec():
            if self.s.get("lang") != old_lang:
                self.rebuild_requested.emit()
                return
            self.theme = self.s.get("theme")
            self.apply_theme()
            self._provider_changed(init=True)
            if self.conv_id:
                self.open_conversation(self.conv_id)

    def show_files(self):
        self.ws_btn.setChecked(True)
        self.workspace.refresh_files()
        self.workspace.tabs.setCurrentIndex(3)

    # ================================================================ conversations
    def refresh_conversations(self):
        self.conv_list.clear()
        for c in self.db.list_conversations(self.search.text().strip()):
            it = QListWidgetItem(c["title"])
            it.setData(Qt.UserRole, c["id"])
            it.setToolTip(time.strftime("%Y-%m-%d %H:%M", time.localtime(c["updated_at"])) + f" · {c['model'] or ''}")
            self.conv_list.addItem(it)
            if c["id"] == self.conv_id:
                it.setSelected(True)

    def _conv_menu(self, pos):
        it = self.conv_list.itemAt(pos)
        if not it:
            return
        cid = it.data(Qt.UserRole)
        m = QMenu(self)
        m.addAction(icon("mdi6.pencil"), tr("rename"), lambda: self.rename_conv(cid))
        m.addAction(icon("mdi6.export"), tr("export"), lambda: self.export_conv(cid))
        pm = m.addMenu(icon("mdi6.folder-move-outline"), tr("move_project"))
        pm.addAction(tr("no_project"), lambda: self._move(cid, None))
        for p in self.db.list_projects():
            pm.addAction(p["name"], lambda pid=p["id"]: self._move(cid, pid))
        m.addSeparator()
        m.addAction(icon("mdi6.delete-outline", "#C0392B"), tr("delete"), lambda: self.delete_conv(cid))
        m.exec(self.conv_list.mapToGlobal(pos))

    def _move(self, cid, pid):
        self.db.set_conversation_project(cid, pid)
        if cid == self.conv_id:
            self.project_id = pid
            self.refresh_projects()

    def rename_conv(self, cid):
        c = self.db.get_conversation(cid)
        name, ok = QInputDialog.getText(self, tr("rename"), tr("name"), text=c["title"])
        if ok and name.strip():
            self.db.rename_conversation(cid, name.strip())
            self.refresh_conversations()

    def delete_conv(self, cid):
        if QMessageBox.question(self, "DOUBAJ AI", tr("confirm_delete")) == QMessageBox.Yes:
            self.db.delete_conversation(cid)
            if cid == self.conv_id:
                self.new_chat()
            self.refresh_conversations()

    def export_conv(self, cid):
        data = self.db.export_conversation(cid)
        title = re.sub(r"[^\w\- ]", "_", data["conversation"].get("title", "conversation"))[:40]
        path, flt = QFileDialog.getSaveFileName(self, tr("export"), str(Path.home() / f"{title}.md"),
                                                "Markdown (*.md);;JSON (*.json);;Word (*.docx)")
        if not path:
            return
        if path.endswith(".json"):
            for m in data["messages"]:
                for a in m.get("attachments", []):
                    a.pop("text", None)
            Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            return
        md = f"# {data['conversation'].get('title', '')}\n\n"
        for m in data["messages"]:
            who = "**Vous**" if m["role"] == "user" else "**DOUBAJ AI**"
            md += f"{who} :\n\n{m['content']}\n\n---\n\n"
        if path.endswith(".docx"):
            from ..documents.generator import markdown_to_docx
            markdown_to_docx(md, Path(path), title)
        else:
            Path(path).write_text(md, encoding="utf-8")

    def clear_messages(self):
        while self.msgs_layout.count() > 1:
            it = self.msgs_layout.takeAt(0)
            if it.widget():
                it.widget().deleteLater()

    def show_welcome(self):
        self.clear_messages()
        w = QWidget()
        l = QVBoxLayout(w)
        l.addSpacing(60)
        lg = QLabel()
        lg.setPixmap(logo_pixmap(84))
        lg.setAlignment(Qt.AlignCenter)
        l.addWidget(lg)
        t = QLabel(tr("welcome"))
        t.setObjectName("Welcome")
        t.setAlignment(Qt.AlignCenter)
        l.addWidget(t)
        sub = QLabel(tr("welcome_sub"))
        sub.setObjectName("Muted")
        sub.setAlignment(Qt.AlignCenter)
        sub.setWordWrap(True)
        l.addWidget(sub)
        if self.project_id:
            p = self.db.get_project(self.project_id)
            if p:
                pl = QLabel(f"📁 {p['name']}")
                pl.setAlignment(Qt.AlignCenter)
                l.addWidget(pl)
        grid = QHBoxLayout()
        examples = {
            "fr": ["Explique le fonctionnement d'un moteur asynchrone triphasé",
                   "Crée un PowerPoint sur les capteurs industriels avec exercices",
                   "Crée un programme Python de gestion des notes avec Excel"],
            "ar": ["اشرح مبدأ اشتغال المحرك اللاتزامني ثلاثي الأطوار",
                   "أنشئ جذاذة درس حول الأنظمة الآلية مع تمارين",
                   "أنشئ ملف Excel لحساب معدلات التلاميذ"],
            "en": ["Explain how a three-phase induction motor works",
                   "Create a PowerPoint about industrial sensors with exercises",
                   "Write a Python program to manage student grades with Excel"],
        }[i18n.lang()]
        for ex in examples:
            b = QPushButton(ex)
            b.setObjectName("Card")
            b.setMinimumHeight(64)
            b.setStyleSheet("text-align:center; padding:10px;")
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, e=ex: (self.input.setPlainText(e), self.input.setFocus()))
            grid.addWidget(b)
        l.addLayout(grid)
        self.msgs_layout.insertWidget(0, w)

    def new_chat(self):
        self.stop()
        self.conv_id = None
        self.conv_list.clearSelection()
        self.refresh_projects()
        self.show_welcome()
        self.input.setFocus()

    def open_conversation(self, cid: int):
        if self.worker and self.worker.isRunning():
            self.stop()
        self.conv_id = cid
        conv = self.db.get_conversation(cid)
        if not conv:
            return
        self.project_id = conv["project_id"]
        self.refresh_projects()
        self.clear_messages()
        for m in self.db.get_messages(cid):
            w = self._add_bubble(m["role"], m["content"], m["id"], m["attachments"], m["meta"])
            for f in m["meta"].get("files", []):
                w.add_file_card(f["name"], f["path"], f.get("error", ""), self.preview_in_workspace)
        QTimer.singleShot(50, self.scroll_bottom)

    def _add_bubble(self, role, content, msg_id, attachments=None, meta=None) -> MessageWidget:
        w = MessageWidget(role, content, msg_id, self.theme, attachments, meta)
        w.regenerate_requested.connect(self.regenerate)
        w.edit_requested.connect(self.edit_message)
        w.speak_requested.connect(self.speak)
        w.workspace_requested.connect(self.open_in_workspace)
        self.msgs_layout.insertWidget(self.msgs_layout.count() - 1, w)
        return w

    def scroll_bottom(self):
        sb = self.scroll.verticalScrollBar()
        sb.setValue(sb.maximum())

    # ================================================================ attachments
    def pick_files(self):
        exts = " ".join("*" + e for e in SUPPORTED)
        paths, _ = QFileDialog.getOpenFileNames(self, tr("attach"), "", f"Documents ({exts});;*.*")
        self.add_attachments(paths)

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        self.add_attachments([u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()])

    def add_attachments(self, paths):
        paths = [p for p in paths if p and Path(p).is_file()]
        if not paths:
            return
        self.status_lbl.setText(tr("reading"))

        def work():
            out = []
            dest_dir = FILES_DIR / time.strftime("%Y%m")
            dest_dir.mkdir(parents=True, exist_ok=True)
            for p in paths:
                dest = dest_dir / f"{int(time.time() * 1000)}_{Path(p).name}"
                shutil.copyfile(p, dest)
                att = engine.Attachment.from_path(str(dest))
                att.name = Path(p).name
                out.append(att.to_record())
            return out
        w = FuncWorker(work)
        w.result.connect(self._attachments_ready)
        w.failed.connect(lambda e: self.status_lbl.setText(e))
        self._bg.append(w)
        w.start()

    def _attachments_ready(self, recs):
        self.status_lbl.setText("")
        for r in recs:
            self.pending.append(r)
            if r.get("warnings"):
                QMessageBox.warning(self, tr("doc_warning"), f"{r['name']}:\n" + "\n".join(r["warnings"]))
        self._render_chips()

    def _render_chips(self):
        while self.chips.count() > 1:
            it = self.chips.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        for i, r in enumerate(self.pending):
            b = QPushButton(f"📎 {r['name']}  ✕")
            b.setToolTip(f"{len(r.get('text', '')):,} car. · {r.get('n_images', 0)} image(s)")
            b.setStyleSheet("padding:3px 8px; border-radius: 10px;")
            b.clicked.connect(lambda _=False, k=i: (self.pending.pop(k), self._render_chips()))
            self.chips.insertWidget(self.chips.count() - 1, b)

    # ================================================================ sending
    def _send_or_stop(self):
        if self.worker and self.worker.isRunning():
            self.stop()
        else:
            self.send()

    def send(self, text: str | None = None):
        if self.worker and self.worker.isRunning():
            return
        text = (text if isinstance(text, str) else self.input.toPlainText()).strip()
        if not text and not self.pending:
            return
        pid = self.current_provider_id()
        info = PROVIDERS[pid].info
        if not self.s.provider_ready(pid):
            QMessageBox.warning(self, "DOUBAJ AI", tr("no_key"))
            self.open_settings()
            return
        if self.pending and not info.local and self.s.get("confirm_upload"):
            if QMessageBox.question(self, "DOUBAJ AI", tr("send_files_confirm", p=info.label)) != QMessageBox.Yes:
                return
        if not self.conv_id:
            self.clear_messages()
            self.conv_id = self.db.create_conversation(engine.auto_title(text or self.pending[0]["name"]),
                                                       self.project_id, pid, self.model_combo.currentText())
        atts = list(self.pending)
        mid = self.db.add_message(self.conv_id, "user", text, atts)
        self._add_bubble("user", text, mid, atts)
        self.pending.clear()
        self._render_chips()
        self.input.clear()
        self.refresh_conversations()
        self.generate()

    def generate(self):
        pid = self.current_provider_id()
        info = PROVIDERS[pid].info
        model = self.model_combo.currentText().strip()
        provider = self.s.make_provider(pid)
        history = self.db.get_messages(self.conv_id)
        use_web = self.web_btn.isChecked()
        project = self.db.get_project(self.project_id) if self.project_id else None
        project_docs = [(f["name"], f["extracted_text"] or "") for f in self.db.list_project_files(self.project_id)] \
            if self.project_id else []
        memories = [m["content"] for m in self.db.list_memories(self.project_id)] if self.s.get("memory_enabled") else []
        system = engine.build_system_prompt(provider_label=info.label, model=model, ui_lang=i18n.lang(),
                                            mode=self.mode_combo.currentData(), reasoning=self.reason_combo.currentData(),
                                            memories=memories, project=project, length=self.s.get("length"))
        reasoning = self.reason_combo.currentData()
        s = self.s
        web_key = s.get_secret("web")

        def build(status):
            web_ctx = ""
            if use_web:
                status(tr("searching"))
                q = history[-1]["content"][:300]
                try:
                    res = web_search.search(q, backend=s.get("web_backend"), key=web_key)
                    web_ctx = web_search.format_for_prompt(q, res)
                except Exception as e:  # noqa: BLE001
                    web_ctx = f"[Web search failed: {e}. Tell the user the search could not be performed.]"
            status(tr("thinking"))
            return engine.build_request(model=model, system=system, history=history, reasoning=reasoning,
                                        max_tokens=int(s.get("max_tokens")), temperature=s.get("temperature"),
                                        context_chars=int(s.get("context_chars")), project_docs=project_docs,
                                        web_context=web_ctx)

        self.ai_widget = self._add_bubble("assistant", "", None, meta={"model": model})
        self.ai_widget.set_status(tr("thinking"))
        self.cancel = CancelToken()
        self.worker = ChatWorker(provider, build, self.cancel)
        self.worker.status.connect(self.ai_widget.set_status)
        self.worker.chunk.connect(self._on_chunk)
        self.worker.thinking.connect(lambda _: self.ai_widget.set_status(tr("thinking")))
        self.worker.done.connect(lambda info_: self._on_done(info_, pid, model))
        self.worker.failed.connect(self._on_error)
        self.worker.start()
        self._set_busy(True)
        QTimer.singleShot(50, self.scroll_bottom)

    def _set_busy(self, busy: bool):
        self.send_btn.setIcon(icon("mdi6.stop" if busy else "mdi6.arrow-up", "#FFFFFF"))
        self.send_btn.setToolTip(tr("stop") if busy else tr("send"))

    def _on_chunk(self, t):
        if self.ai_widget:
            if not self.ai_widget.content:
                self.ai_widget.set_status("")
            self.ai_widget.append(t)
            sb = self.scroll.verticalScrollBar()
            if sb.maximum() - sb.value() < 300:
                QTimer.singleShot(0, self.scroll_bottom)

    def _on_done(self, info, pid, model):
        w = self.ai_widget
        self._set_busy(False)
        if not w:
            return
        w.finish()
        content = w.content
        if info.get("cancelled"):
            content += "\n\n" + tr("stopped")
            w.set_content(content)
        w.set_status("")
        files = []
        if "doubaj-file" in content:
            out_dir = OUTPUT_DIR / time.strftime("%Y%m%d")
            for g in extract_and_generate(content, out_dir):
                files.append({"name": g.name, "path": str(g.path), "error": g.error})
                w.add_file_card(g.name, str(g.path), g.error, self.preview_in_workspace)
                if not g.error:
                    self.db.add_output(self.conv_id, self.project_id, g.name, str(g.path), g.kind)
            self.workspace.refresh_files()
        meta = {"model": model, "provider": pid, "usage": info.get("usage"), "files": files}
        mid = self.db.add_message(self.conv_id, "assistant", content, meta=meta)
        w.msg_id = mid
        u = info.get("usage")
        if u:
            w.usage.setText(f"{model} · {u.get('input', '?')}→{u.get('output', '?')} {tr('tokens_used')}")
        self.db.touch_conversation(self.conv_id, pid, model)
        self.ai_widget = None
        # workspace: auto-open for html apps or generated files
        if files and not any(f["error"] for f in files):
            self.preview_in_workspace(files[0]["path"])
        elif re.search(r"```html", content):
            self.open_in_workspace(content)
        # memory suggestions
        if self.s.get("memory_enabled"):
            for fact in engine.extract_memories(content):
                if QMessageBox.question(self, tr("memory"), f"{tr('memory_suggest')}\n\n« {fact} »") == QMessageBox.Yes:
                    self.db.add_memory(fact, project_id=None)
        self.refresh_conversations()

    def _on_error(self, msg: str):
        self._set_busy(False)
        if self.ai_widget:
            self.ai_widget.finish()
            self.ai_widget.set_status("")
            partial = self.ai_widget.content
            self.ai_widget.set_content((partial + "\n\n" if partial else "") + f"⚠️ **{tr('error')}** : {msg}")
            self.ai_widget = None

    def stop(self):
        if self.cancel:
            self.cancel.cancel()

    def regenerate(self, msg_id: int):
        if (self.worker and self.worker.isRunning()) or not self.conv_id or msg_id < 0:
            return
        self.db.delete_messages_from(self.conv_id, msg_id)
        self.open_conversation(self.conv_id)
        self.generate()

    def edit_message(self, msg_id: int):
        if (self.worker and self.worker.isRunning()) or not self.conv_id or msg_id < 0:
            return
        msgs = {m["id"]: m for m in self.db.get_messages(self.conv_id)}
        m = msgs.get(msg_id)
        if not m:
            return
        text, ok = QInputDialog.getMultiLineText(self, tr("edit"), "", m["content"])
        if not ok or not text.strip():
            return
        self.db.delete_messages_from(self.conv_id, msg_id)
        self.pending = list(m["attachments"])
        self.open_conversation(self.conv_id)
        self.send(text)

    # ================================================================ workspace
    def open_in_workspace(self, content: str):
        self.ws_btn.setChecked(True)
        self.workspace.load_answer(content)

    def preview_in_workspace(self, path: str):
        self.ws_btn.setChecked(True)
        self.workspace.preview_file(path)

    def _improve(self, payload: str):
        self.input.setPlainText(payload)
        self.input.setFocus()

    def run_last_python(self):
        if not self.conv_id:
            return
        for m in reversed(self.db.get_messages(self.conv_id)):
            if m["role"] == "assistant":
                blocks = PY_BLOCK.findall(m["content"])
                if blocks:
                    self.ws_btn.setChecked(True)
                    self.workspace.set_editor(blocks[-1], "python")
                    self.workspace.run_python(blocks[-1])
                    return
        QMessageBox.information(self, "DOUBAJ AI", "Aucun code Python trouvé dans cette conversation.")

    # ================================================================ memory / images
    def quick_memory(self):
        text, ok = QInputDialog.getMultiLineText(self, tr("memory"), tr("add_memory"))
        if ok and text.strip():
            self.db.add_memory(text.strip(), project_id=self.project_id)

    def generate_image(self):
        prompt, ok = QInputDialog.getMultiLineText(self, tr("gen_image"), tr("image_prompt"), self.input.toPlainText())
        if not ok or not prompt.strip():
            return
        key = self.s.get_secret("img") or self.s.get_secret("openai")
        if not key:
            QMessageBox.warning(self, "DOUBAJ AI", tr("no_key"))
            return
        if not self.conv_id:
            self.clear_messages()
            self.conv_id = self.db.create_conversation("🖼 " + engine.auto_title(prompt), self.project_id)
        mid = self.db.add_message(self.conv_id, "user", "🖼 " + prompt)
        self._add_bubble("user", "🖼 " + prompt, mid)
        w = self._add_bubble("assistant", "", None)
        w.set_status("…")
        worker = FuncWorker(media.generate_image, prompt, key, OUTPUT_DIR / "images", self.s.get("img_url"),
                            self.s.get("img_model"))

        def ok_(path):
            content = f"![image]({QUrl.fromLocalFile(str(path)).toString()})"
            w.set_status("")
            w.set_content(content)
            w.add_file_card(Path(path).name, str(path), "", self.preview_in_workspace)
            files = [{"name": Path(path).name, "path": str(path), "error": ""}]
            w.msg_id = self.db.add_message(self.conv_id, "assistant", content,
                                           meta={"model": self.s.get("img_model"), "files": files})
            self.db.add_output(self.conv_id, self.project_id, Path(path).name, str(path), "png")
            self.refresh_conversations()
        worker.result.connect(ok_)
        worker.failed.connect(lambda e: (w.set_status(""), w.set_content(f"⚠️ **{tr('error')}** : {e}")))
        self._bg.append(worker)
        worker.start()

    # ================================================================ voice
    def _tts(self):
        if self.tts is None:
            from PySide6.QtTextToSpeech import QTextToSpeech
            self.tts = QTextToSpeech(self)
        return self.tts

    def speak(self, text: str):
        try:
            tts = self._tts()
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(self, "DOUBAJ AI", f"Synthèse vocale indisponible : {e}")
            return
        clean = re.sub(r"```.*?```", " ", text, flags=re.S)
        clean = re.sub(r"[#*_`>|]", " ", clean)
        clean = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", clean)
        wanted = self.s.get("tts_voice")
        voices = tts.availableVoices()
        chosen = None
        if wanted:
            chosen = next((v for v in voices if v.name() == wanted), None)
        if chosen is None:
            want_ar = is_rtl(clean)
            for v in voices:
                code = v.locale().name()
                if (want_ar and code.startswith("ar")) or (not want_ar and code.startswith(("fr" if i18n.lang() == "fr" else "en"))):
                    chosen = v
                    break
        if chosen is not None:
            tts.setVoice(chosen)
        tts.setRate(float(self.s.get("tts_rate")))
        tts.stop()
        tts.say(clean)

    def tts_pause_resume(self):
        if self.tts is None:
            return
        from PySide6.QtTextToSpeech import QTextToSpeech
        if self.tts.state() == QTextToSpeech.State.Speaking:
            self.tts.pause()
        elif self.tts.state() == QTextToSpeech.State.Paused:
            self.tts.resume()

    def toggle_recording(self, on: bool):
        try:
            from PySide6.QtMultimedia import QAudioInput, QMediaCaptureSession, QMediaFormat, QMediaRecorder
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(self, "DOUBAJ AI", str(e))
            self.mic_btn.setChecked(False)
            return
        if on:
            key = self.s.get_secret("stt") or self.s.get_secret("openai")
            if not key and "localhost" not in self.s.get("stt_url"):
                QMessageBox.warning(self, "DOUBAJ AI", tr("no_key") + "\n(" + tr("stt_service") + ")")
                self.mic_btn.setChecked(False)
                return
            self._session = QMediaCaptureSession()
            self._audio_in = QAudioInput()
            self._session.setAudioInput(self._audio_in)
            self.recorder = QMediaRecorder()
            self._session.setRecorder(self.recorder)
            fmt = QMediaFormat()
            fmt.setFileFormat(QMediaFormat.FileFormat.Wave)
            fmt.setAudioCodec(QMediaFormat.AudioCodec.Wave)
            self.recorder.setMediaFormat(fmt)
            self._rec_path = Path(tempfile.gettempdir()) / f"doubaj_voice_{int(time.time())}.wav"
            self.recorder.setOutputLocation(QUrl.fromLocalFile(str(self._rec_path)))
            self.recorder.record()
            self.mic_btn.setIcon(icon("mdi6.microphone", "#C0392B"))
            self.status_lbl.setText(tr("listening"))
        else:
            if not self.recorder:
                return
            self.recorder.stop()
            self.mic_btn.setIcon(icon("mdi6.microphone-outline"))
            self.status_lbl.setText("…")
            QTimer.singleShot(400, self._transcribe)

    def _transcribe(self):
        path = str(self.recorder.actualLocation().toLocalFile() or self._rec_path)
        key = self.s.get_secret("stt") or self.s.get_secret("openai")
        lang = {"fr": "fr", "ar": "ar", "en": "en"}.get(i18n.lang())
        w = FuncWorker(media.transcribe, path, key, self.s.get("stt_url"), self.s.get("stt_model"), lang)
        w.result.connect(lambda t: (self.input.insertPlainText(t), self.status_lbl.setText("")))
        w.failed.connect(lambda e: self.status_lbl.setText(f"⚠️ {e[:120]}"))
        self._bg.append(w)
        w.start()

    def closeEvent(self, e):
        self.stop()
        if self.worker and self.worker.isRunning():
            self.worker.wait(2000)
        super().closeEvent(e)
