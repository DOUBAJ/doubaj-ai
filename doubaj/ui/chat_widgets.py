"""Message bubbles, file cards and the background worker that streams model answers."""
from __future__ import annotations

import os
import re
import sys
import subprocess
from pathlib import Path
from typing import Callable

import qtawesome as qta
from PySide6.QtCore import QObject, QSize, Qt, QThread, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QGuiApplication, QTextOption
from PySide6.QtWidgets import (QFileDialog, QFrame, QHBoxLayout, QLabel, QSizePolicy, QTextBrowser, QToolButton,
                               QVBoxLayout, QWidget)

from .. import i18n
from ..core.markdown_render import is_rtl, md_to_html
from ..documents.generator import strip_file_blocks
from ..providers.base import CancelToken, Provider, StreamEvent
from .theme import PALETTES, chat_css


def open_path(path: str) -> None:
    QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))


def icon(name: str, color: str | None = None):
    try:
        return qta.icon(name, color=color or "#8C96A8")
    except Exception:
        return qta.icon("mdi6.circle-small")


# ---------------------------------------------------------------- worker
class ChatWorker(QThread):
    status = Signal(str)
    chunk = Signal(str)
    thinking = Signal(str)
    done = Signal(dict)
    failed = Signal(str)

    def __init__(self, provider: Provider, build: Callable[[Callable[[str], None]], object], cancel: CancelToken):
        """build(status_cb) -> ChatRequest ; runs inside the thread (web search, document reading...)."""
        super().__init__()
        self.provider, self.build, self.cancel = provider, build, cancel

    def run(self) -> None:
        try:
            req = self.build(self.status.emit)
            if self.cancel.cancelled:
                self.done.emit({"cancelled": True})
                return
            usage = None
            for ev in self.provider.stream_chat(req, self.cancel):
                ev: StreamEvent
                if ev.kind == "text":
                    self.chunk.emit(ev.text)
                elif ev.kind == "thinking":
                    self.thinking.emit(ev.text)
                elif ev.kind == "error":
                    self.failed.emit(ev.text)
                    return
                elif ev.kind == "done":
                    usage = ev.usage
            self.done.emit({"usage": usage, "cancelled": self.cancel.cancelled})
        except Exception as e:  # noqa: BLE001 - never crash the UI
            self.failed.emit(f"{type(e).__name__}: {e}")


class FuncWorker(QThread):
    """Run any blocking function in background."""
    result = Signal(object)
    failed = Signal(str)

    def __init__(self, fn, *args, **kw):
        super().__init__()
        self.fn, self.args, self.kw = fn, args, kw

    def run(self):
        try:
            self.result.emit(self.fn(*self.args, **self.kw))
        except Exception as e:  # noqa: BLE001
            self.failed.emit(f"{type(e).__name__}: {e}")


# ---------------------------------------------------------------- auto-height text browser
class AutoBrowser(QTextBrowser):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setOpenExternalLinks(True)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.document().contentsChanged.connect(self._fit)
        self.setTextInteractionFlags(Qt.TextBrowserInteraction | Qt.TextSelectableByKeyboard)

    def _fit(self):
        self.document().setTextWidth(self.viewport().width())
        h = int(self.document().size().height()) + 8
        if self.height() != h:
            self.setFixedHeight(max(h, 24))

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._fit()


# ---------------------------------------------------------------- message bubble
class MessageWidget(QFrame):
    copy_requested = Signal(str)
    regenerate_requested = Signal(int)
    edit_requested = Signal(int)
    speak_requested = Signal(str)
    workspace_requested = Signal(str)

    def __init__(self, role: str, content: str, msg_id: int | None, theme: str, attachments=None, meta=None):
        super().__init__()
        self.role, self.content, self.msg_id, self.theme = role, content, msg_id, theme
        self.meta = meta or {}
        self.setObjectName("UserBubble" if role == "user" else "AiBubble")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 10, 14, 6)
        outer.setSpacing(4)

        head = QHBoxLayout()
        who = QLabel("👤" if role == "user" else "✦ DOUBAJ AI")
        who.setStyleSheet(f"font-weight:600;color:{PALETTES[theme]['accent']};")
        head.addWidget(who)
        self.status = QLabel("")
        self.status.setObjectName("Muted")
        head.addWidget(self.status)
        head.addStretch()
        outer.addLayout(head)

        if attachments:
            chips = QLabel("  ".join(f"📎 {a.get('name', '')}" for a in attachments))
            chips.setObjectName("Muted")
            chips.setWordWrap(True)
            outer.addWidget(chips)

        self.view = AutoBrowser()
        self.view.setObjectName("MsgView")
        outer.addWidget(self.view)
        self.files_box = QVBoxLayout()
        outer.addLayout(self.files_box)

        bar = QHBoxLayout()
        bar.setSpacing(2)
        bar.addStretch()
        self.btns = []

        def mk(ic, tip, fn):
            b = QToolButton()
            b.setIcon(icon(ic))
            b.setIconSize(QSize(16, 16))
            b.setToolTip(tip)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(fn)
            bar.addWidget(b)
            self.btns.append(b)
            return b

        mk("mdi6.content-copy", i18n.tr("copy"), self._copy)
        if role == "assistant":
            mk("mdi6.volume-high", i18n.tr("read_aloud"), lambda: self.speak_requested.emit(self.content))
            mk("mdi6.application-brackets-outline", i18n.tr("open_ws"), lambda: self.workspace_requested.emit(self.content))
            mk("mdi6.refresh", i18n.tr("regenerate"), lambda: self.regenerate_requested.emit(self.msg_id or -1))
        else:
            mk("mdi6.pencil-outline", i18n.tr("edit"), lambda: self.edit_requested.emit(self.msg_id or -1))
        outer.addLayout(bar)
        self.usage = QLabel("")
        self.usage.setObjectName("Muted")
        bar.insertWidget(0, self.usage)

        self._pending = False
        self._timer = QTimer(self)
        self._timer.setInterval(90)
        self._timer.timeout.connect(self._flush)
        self.set_content(content)
        if self.meta.get("usage"):
            u = self.meta["usage"]
            self.usage.setText(f"{self.meta.get('model', '')} · {u.get('input', '?')}→{u.get('output', '?')} {i18n.tr('tokens_used')}")
        elif self.meta.get("model"):
            self.usage.setText(self.meta.get("model", ""))

    # rendering ---------------------------------------------------
    def _render(self):
        shown = strip_file_blocks(self.content) if self.role == "assistant" else self.content
        shown = re.sub(r"^(`{3,})doubaj-memory\s*\n.*?\n\1[ \t]*$", "", shown, flags=re.S | re.M)
        # an unterminated file block while streaming: hide its raw content
        m = re.search(r"^(`{3,})doubaj-file\s+name=\"([^\"]+)\".*\Z", shown, flags=re.S | re.M)
        if m and self.role == "assistant":
            shown = shown[:m.start()] + f"\n⏳ … {m.group(2)}\n"
        rtl = is_rtl(shown)
        opt = QTextOption()
        opt.setTextDirection(Qt.RightToLeft if rtl else Qt.LeftToRight)
        opt.setWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)
        self.view.document().setDefaultTextOption(opt)
        self.view.document().setDefaultStyleSheet(chat_css(self.theme))
        if self.role == "user":
            import html as _h
            body = "<p>" + _h.escape(shown).replace("\n", "<br>") + "</p>"
        else:
            body = md_to_html(shown)
        align = "right" if rtl else "left"
        self.view.setHtml(f"<div dir='{'rtl' if rtl else 'ltr'}' align='{align}'>{body}</div>")

    def set_content(self, text: str):
        self.content = text
        self._render()

    def append(self, text: str):
        self.content += text
        if not self._timer.isActive():
            self._timer.start()
        self._pending = True

    def _flush(self):
        if self._pending:
            self._pending = False
            self._render()
        else:
            self._timer.stop()

    def finish(self):
        self._timer.stop()
        self._pending = False
        self._render()

    def set_status(self, s: str):
        self.status.setText(s)

    def _copy(self):
        QGuiApplication.clipboard().setText(self.content)
        self.status.setText(i18n.tr("copied"))
        QTimer.singleShot(1500, lambda: self.status.setText(""))

    def add_file_card(self, name: str, path: str, error: str = "", on_preview=None):
        card = QFrame()
        card.setObjectName("FileCard")
        lay = QHBoxLayout(card)
        lay.setContentsMargins(10, 6, 10, 6)
        ext = Path(name).suffix.lower()
        ic = {".docx": "mdi6.file-word", ".pdf": "mdi6.file-pdf-box", ".pptx": "mdi6.file-powerpoint",
              ".xlsx": "mdi6.file-excel", ".zip": "mdi6.folder-zip", ".html": "mdi6.language-html5",
              ".png": "mdi6.file-image", ".csv": "mdi6.file-delimited", ".py": "mdi6.language-python"}.get(ext, "mdi6.file-document")
        il = QLabel()
        il.setPixmap(icon(ic, PALETTES[self.theme]["accent"]).pixmap(28, 28))
        lay.addWidget(il)
        lbl = QLabel(f"<b>{name}</b>" + (f"<br><span style='color:#C0392B'>{error}</span>" if error else ""))
        lbl.setTextFormat(Qt.RichText)
        lay.addWidget(lbl, 1)
        if not error:
            for ic2, tip, fn in (("mdi6.eye-outline", i18n.tr("preview"), lambda: on_preview and on_preview(path)),
                                 ("mdi6.open-in-new", i18n.tr("open"), lambda: open_path(path)),
                                 ("mdi6.content-save-outline", i18n.tr("save_as"), lambda: save_copy(self, path)),
                                 ("mdi6.folder-open-outline", i18n.tr("open_folder"), lambda: reveal(path))):
                b = QToolButton()
                b.setIcon(icon(ic2))
                b.setToolTip(tip)
                b.clicked.connect(fn)
                lay.addWidget(b)
        self.files_box.addWidget(card)


def save_copy(parent, path: str):
    import shutil
    dest, _ = QFileDialog.getSaveFileName(parent, i18n.tr("save_as"), str(Path.home() / Path(path).name))
    if dest:
        shutil.copyfile(path, dest)


def reveal(path: str):
    if sys.platform.startswith("win"):
        subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
    else:
        open_path(str(Path(path).parent))
