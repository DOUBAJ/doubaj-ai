"""Interactive workspace ("artifacts"): preview, code editor, console and generated files."""
from __future__ import annotations

import html
import re
import tempfile
from pathlib import Path

from PySide6.QtCore import QUrl, Signal, Qt
from PySide6.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat
from PySide6.QtWidgets import (QComboBox, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QMessageBox,
                               QPlainTextEdit, QPushButton, QTabWidget, QTextBrowser, QVBoxLayout, QWidget,
                               QFileDialog)

from .. import i18n
from ..core.markdown_render import is_rtl, md_to_html, wrap_document
from ..documents.reader import IMAGE_EXT, read_file
from ..tools.sandbox import run_python
from .chat_widgets import FuncWorker, icon, open_path

try:
    from PySide6.QtWebEngineWidgets import QWebEngineView
    HAS_WEBENGINE = True
except Exception:  # pragma: no cover
    HAS_WEBENGINE = False

try:
    from PySide6.QtPdf import QPdfDocument
    from PySide6.QtPdfWidgets import QPdfView
    HAS_PDF = True
except Exception:  # pragma: no cover
    HAS_PDF = False

CODE_BLOCK = re.compile(r"```([\w+#.-]*)[^\n]*\n(.*?)```", re.S)
LANGS = ["markdown", "html", "python", "javascript", "css", "java", "c", "cpp", "csharp", "sql", "php", "json", "text"]


class PygmentsHighlighter(QSyntaxHighlighter):
    def __init__(self, doc, dark: bool):
        super().__init__(doc)
        from pygments.styles import get_style_by_name
        self.style = get_style_by_name("monokai" if dark else "friendly")
        self.lexer = None
        self._formats: dict = {}

    def set_language(self, lang: str):
        from pygments.lexers import get_lexer_by_name
        try:
            self.lexer = get_lexer_by_name(lang)
        except Exception:
            self.lexer = None
        self.rehighlight()

    def _fmt(self, ttype):
        if ttype not in self._formats:
            st = self.style.style_for_token(ttype)
            f = QTextCharFormat()
            if st["color"]:
                f.setForeground(QColor("#" + st["color"]))
            if st["bold"]:
                f.setFontWeight(QFont.Bold)
            if st["italic"]:
                f.setFontItalic(True)
            self._formats[ttype] = f
        return self._formats[ttype]

    def highlightBlock(self, text):
        if not self.lexer:
            return
        pos = 0
        for ttype, value in self.lexer.get_tokens(text):
            n = len(value)
            if value.endswith("\n"):
                n -= 1
            if n > 0:
                self.setFormat(pos, n, self._fmt(ttype))
            pos += len(value)


class Workspace(QWidget):
    improve_requested = Signal(str)

    def __init__(self, db, theme: str):
        super().__init__()
        self.db = db
        self.theme = theme
        self.tmp = Path(tempfile.mkdtemp(prefix="doubaj_ws_"))
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        head = QHBoxLayout()
        t = QLabel(f"<b>{i18n.tr('workspace')}</b>")
        head.addWidget(t)
        head.addStretch()
        lay.addLayout(head)

        self.tabs = QTabWidget()
        lay.addWidget(self.tabs, 1)

        # preview
        if HAS_WEBENGINE:
            self.web = QWebEngineView()
            self.tabs.addTab(self.web, i18n.tr("ws_preview"))
        else:
            self.web = QTextBrowser()
            self.web.setOpenExternalLinks(True)
            self.tabs.addTab(self.web, i18n.tr("ws_preview"))
        self.pdf_view = None
        if HAS_PDF:
            self.pdf_doc = QPdfDocument(self)
            self.pdf_view = QPdfView()
            self.pdf_view.setDocument(self.pdf_doc)
            self.pdf_view.setPageMode(QPdfView.PageMode.MultiPage)
            self.pdf_view.setZoomMode(QPdfView.ZoomMode.FitToWidth)

        # editor
        ed = QWidget()
        el = QVBoxLayout(ed)
        el.setContentsMargins(0, 4, 0, 0)
        row = QHBoxLayout()
        self.lang = QComboBox()
        self.lang.addItems(LANGS)
        self.lang.currentTextChanged.connect(self._lang_changed)
        row.addWidget(self.lang)
        row.addStretch()
        self.run_btn = QPushButton(icon("mdi6.play"), i18n.tr("ws_run"))
        self.run_btn.setObjectName("Primary")
        self.run_btn.clicked.connect(self.run_current)
        row.addWidget(self.run_btn)
        b_browser = QPushButton(icon("mdi6.web"), "")
        b_browser.setToolTip(i18n.tr("ws_browser"))
        b_browser.clicked.connect(self.open_in_browser)
        row.addWidget(b_browser)
        b_save = QPushButton(icon("mdi6.content-save-outline"), "")
        b_save.setToolTip(i18n.tr("ws_save"))
        b_save.clicked.connect(self.save_editor)
        row.addWidget(b_save)
        b_imp = QPushButton(icon("mdi6.auto-fix"), i18n.tr("ws_improve"))
        b_imp.clicked.connect(lambda: self.improve_requested.emit(self._editor_payload()))
        row.addWidget(b_imp)
        el.addLayout(row)
        self.editor = QPlainTextEdit()
        self.editor.setObjectName("CodeEditor")
        self.editor.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.editor.setTabStopDistance(28)
        self.hl = PygmentsHighlighter(self.editor.document(), theme == "dark")
        el.addWidget(self.editor, 1)
        self.tabs.addTab(ed, i18n.tr("ws_code"))

        # console
        self.console = QPlainTextEdit()
        self.console.setReadOnly(True)
        self.console.setObjectName("CodeEditor")
        self.tabs.addTab(self.console, i18n.tr("ws_output"))

        # files
        fw = QWidget()
        fl = QVBoxLayout(fw)
        fl.setContentsMargins(0, 4, 0, 0)
        self.files = QListWidget()
        self.files.itemDoubleClicked.connect(lambda it: self.preview_file(it.data(Qt.UserRole)))
        fl.addWidget(self.files, 1)
        frow = QHBoxLayout()
        for text, fn in ((i18n.tr("preview"), lambda: self._sel(self.preview_file)),
                         (i18n.tr("open"), lambda: self._sel(open_path))):
            b = QPushButton(text)
            b.clicked.connect(fn)
            frow.addWidget(b)
        fl.addLayout(frow)
        self.tabs.addTab(fw, i18n.tr("ws_files"))
        self._worker = None
        self.refresh_files()

    # ------------------------------------------------------------------
    def _sel(self, fn):
        it = self.files.currentItem()
        if it:
            fn(it.data(Qt.UserRole))

    def refresh_files(self, project_id=None):
        self.files.clear()
        for o in self.db.list_outputs(project_id):
            if Path(o["path"]).exists():
                it = QListWidgetItem(icon("mdi6.file-outline"), o["name"])
                it.setData(Qt.UserRole, o["path"])
                it.setToolTip(o["path"])
                self.files.addItem(it)

    def _lang_changed(self, lang):
        self.hl.set_language({"markdown": "md", "text": "text", "csharp": "csharp"}.get(lang, lang))

    def _editor_payload(self) -> str:
        return f"{i18n.tr('improve_prompt')}\n\n```{self.lang.currentText()}\n{self.editor.toPlainText()}\n```"

    def _show_html(self, html_text: str, base: Path | None = None):
        self._ensure_web_tab()
        if HAS_WEBENGINE:
            f = self.tmp / "preview.html"
            f.write_text(html_text, encoding="utf-8")
            self.web.setUrl(QUrl.fromLocalFile(str(f)))
        else:
            self.web.setHtml(html_text)
        self.tabs.setCurrentIndex(0)

    def _ensure_web_tab(self):
        if self.tabs.widget(0) is not self.web:
            self.tabs.removeTab(0)
            self.tabs.insertTab(0, self.web, i18n.tr("ws_preview"))

    # ------------------------------------------------------------------
    def load_answer(self, content: str):
        """Put the most relevant part of an answer in the workspace."""
        from ..documents.generator import strip_file_blocks
        content = strip_file_blocks(content)
        blocks = [(lang.lower(), code) for lang, code in CODE_BLOCK.findall(content)
                  if not lang.startswith("doubaj")]
        html_blocks = [b for b in blocks if b[0] in ("html", "htm")]
        if html_blocks:
            lang, code = html_blocks[-1]
            # inline sibling css/js blocks if the html does not contain them
            css = "\n".join(c for l, c in blocks if l == "css")
            js = "\n".join(c for l, c in blocks if l in ("javascript", "js"))
            if css and "<style" not in code:
                code = code.replace("</head>", f"<style>\n{css}\n</style>\n</head>") if "</head>" in code else f"<style>{css}</style>\n{code}"
            if js and "<script" not in code:
                code = code.replace("</body>", f"<script>\n{js}\n</script>\n</body>") if "</body>" in code else f"{code}\n<script>{js}</script>"
            self.set_editor(code, "html")
            self._show_html(code)
            return
        if blocks:
            lang, code = blocks[-1]
            lang = {"py": "python", "js": "javascript", "c++": "cpp", "cs": "csharp", "c#": "csharp", "": "text"}.get(lang, lang)
            self.set_editor(code, lang if lang in LANGS else "text")
            self.tabs.setCurrentIndex(1)
            return
        self.set_editor(content, "markdown")
        self._show_html(wrap_document(md_to_html(content), "DOUBAJ AI", rtl=is_rtl(content), dark=False))

    def set_editor(self, text: str, lang: str):
        self.lang.setCurrentText(lang)
        self._lang_changed(lang)
        self.editor.setPlainText(text)

    def run_current(self):
        lang = self.lang.currentText()
        code = self.editor.toPlainText()
        if lang == "html":
            self._show_html(code)
        elif lang == "markdown":
            self._show_html(wrap_document(md_to_html(code), "DOUBAJ AI", rtl=is_rtl(code)))
        elif lang == "python":
            self.run_python(code)
        elif lang in ("javascript", "css"):
            page = f"<html><body><pre id='out'></pre><script>const _l=console.log;console.log=(...a)=>{{document.getElementById('out').textContent+=a.join(' ')+'\\n';_l(...a)}};\n{code}\n</script></body></html>" \
                if lang == "javascript" else f"<html><head><style>{code}</style></head><body><h1>Titre</h1><p>Paragraphe <a href='#'>lien</a></p><button>Bouton</button></body></html>"
            self._show_html(page)
        else:
            QMessageBox.information(self, "DOUBAJ AI", "Exécution directe disponible pour Python, HTML, CSS, JavaScript et Markdown. "
                                                       "Pour les autres langages, enregistrez le fichier et compilez-le avec votre outil habituel.")

    def run_python(self, code: str, ask: bool = True):
        if ask and QMessageBox.question(self, "DOUBAJ AI", i18n.tr("run_confirm")) != QMessageBox.Yes:
            return
        restricted = bool(self.db.get_setting("sandbox_restricted", True))
        self.console.setPlainText("▶ …")
        self.tabs.setCurrentWidget(self.console)
        self._worker = FuncWorker(run_python, code, 30, restricted)
        self._worker.result.connect(self._show_run)
        self._worker.failed.connect(lambda e: self.console.setPlainText(e))
        self._worker.start()

    def _show_run(self, r):
        txt = r.stdout
        if r.stderr:
            txt += "\n--- stderr ---\n" + r.stderr
        txt += f"\n[exit code {r.returncode}{' – timeout' if r.timed_out else ''}] · {r.workdir}"
        self.console.setPlainText(txt)

    def open_in_browser(self):
        lang = self.lang.currentText()
        code = self.editor.toPlainText()
        if lang == "markdown":
            code = wrap_document(md_to_html(code), "DOUBAJ AI", rtl=is_rtl(code))
        elif lang != "html":
            code = f"<pre>{html.escape(code)}</pre>"
        f = self.tmp / "page.html"
        f.write_text(code, encoding="utf-8")
        open_path(str(f))

    def save_editor(self):
        ext = {"python": ".py", "javascript": ".js", "markdown": ".md", "html": ".html", "css": ".css", "java": ".java",
               "c": ".c", "cpp": ".cpp", "csharp": ".cs", "sql": ".sql", "php": ".php", "json": ".json"}.get(self.lang.currentText(), ".txt")
        dest, _ = QFileDialog.getSaveFileName(self, i18n.tr("ws_save"), str(Path.home() / f"doubaj{ext}"))
        if dest:
            Path(dest).write_text(self.editor.toPlainText(), encoding="utf-8")

    # ------------------------------------------------------------------
    def preview_file(self, path: str):
        p = Path(path)
        ext = p.suffix.lower()
        if ext == ".pdf" and self.pdf_view is not None:
            self.pdf_doc.load(str(p))
            if self.tabs.widget(0) is not self.pdf_view:
                self.tabs.removeTab(0)
                self.tabs.insertTab(0, self.pdf_view, i18n.tr("ws_preview"))
            self.tabs.setCurrentIndex(0)
            return
        if ext in (".html", ".htm"):
            self._ensure_web_tab()
            if HAS_WEBENGINE:
                self.web.setUrl(QUrl.fromLocalFile(str(p)))
            else:
                self.web.setHtml(p.read_text(encoding="utf-8", errors="replace"))
            self.tabs.setCurrentIndex(0)
            self.set_editor(p.read_text(encoding="utf-8", errors="replace"), "html")
            return
        if ext in IMAGE_EXT:
            self._show_html(f"<html><body style='margin:0;background:#222;text-align:center'>"
                            f"<img src='{QUrl.fromLocalFile(str(p)).toString()}' style='max-width:100%'></body></html>")
            return
        if ext == ".zip":
            import zipfile
            names = zipfile.ZipFile(p).namelist()
            self._show_html("<h3>" + html.escape(p.name) + "</h3><ul>" + "".join(f"<li>{html.escape(n)}</li>" for n in names) + "</ul>")
            return
        r = read_file(p)
        text = r.text
        # turn markers into headings for a readable preview
        text = re.sub(r"^\[(Slide|Page|Sheet)([^\]]*)\]", r"\n### \1\2\n", text, flags=re.M)
        if ext in (".py", ".js", ".css", ".java", ".c", ".cpp", ".cs", ".sql", ".php", ".json", ".txt", ".csv"):
            lang = {".py": "python", ".js": "javascript", ".cs": "csharp", ".txt": "text", ".csv": "text"}.get(ext, ext[1:])
            self.set_editor(r.text, lang if lang in LANGS else "text")
            self.tabs.setCurrentIndex(1)
            return
        body = md_to_html(text) if ext not in (".xlsx", ".xls") else "<pre>" + html.escape(text) + "</pre>"
        self._show_html(wrap_document(body, p.name, rtl=is_rtl(text)))
