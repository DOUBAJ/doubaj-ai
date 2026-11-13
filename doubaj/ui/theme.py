"""Visual identity: colours and Qt stylesheets for light and dark modes.
DOUBAJ AI identity: deep night blue + teal, with a warm gold accent (inspired by Moroccan zellige)."""
from __future__ import annotations

PALETTES = {
    "light": {
        "bg": "#F6F7FB", "panel": "#FFFFFF", "side": "#EEF1F7", "border": "#DDE3EE", "text": "#1B2333",
        "muted": "#667085", "accent": "#0E7C86", "accent2": "#C9973B", "accent_text": "#FFFFFF",
        "user_bubble": "#E3F2F3", "ai_bubble": "#FFFFFF", "hover": "#E2E8F2", "input": "#FFFFFF",
        "code_bg": "#F3F5F9", "danger": "#C0392B",
    },
    "dark": {
        "bg": "#10141C", "panel": "#161B25", "side": "#0C1017", "border": "#262E3D", "text": "#E6EAF2",
        "muted": "#8C96A8", "accent": "#21B3BE", "accent2": "#E0B055", "accent_text": "#081014",
        "user_bubble": "#173338", "ai_bubble": "#161B25", "hover": "#1E2533", "input": "#1A202B",
        "code_bg": "#0F131A", "danger": "#E5675A",
    },
}


def stylesheet(mode: str) -> str:
    c = PALETTES[mode]
    return f"""
* {{ font-family: 'Segoe UI', 'Amiri', 'Noto Sans Arabic', Arial; font-size: 10.5pt; color: {c['text']}; }}
QMainWindow, QDialog {{ background: {c['bg']}; }}
QWidget#Sidebar {{ background: {c['side']}; border-right: 1px solid {c['border']}; }}
QWidget#TopBar {{ background: {c['panel']}; border-bottom: 1px solid {c['border']}; }}
QWidget#ChatArea, QScrollArea#ChatScroll, QWidget#ChatInner {{ background: {c['bg']}; border: none; }}
QFrame#Composer {{ background: {c['input']}; border: 1px solid {c['border']}; border-radius: 16px; }}
QFrame#UserBubble {{ background: {c['user_bubble']}; border-radius: 14px; }}
QFrame#AiBubble {{ background: {c['ai_bubble']}; border: 1px solid {c['border']}; border-radius: 14px; }}
QFrame#FileCard {{ background: {c['panel']}; border: 1px solid {c['accent']}; border-radius: 10px; }}
QFrame#Card {{ background: {c['panel']}; border: 1px solid {c['border']}; border-radius: 12px; }}
QLabel#Muted {{ color: {c['muted']}; font-size: 9pt; }}
QLabel#Brand {{ font-size: 15pt; font-weight: 700; color: {c['accent']}; }}
QLabel#Welcome {{ font-size: 20pt; font-weight: 600; }}
QPlainTextEdit, QTextEdit, QLineEdit, QSpinBox, QDoubleSpinBox {{
    background: {c['input']}; border: 1px solid {c['border']}; border-radius: 8px; padding: 6px;
    selection-background-color: {c['accent']}; selection-color: {c['accent_text']}; }}
QTextBrowser#MsgView {{ background: transparent; border: none; padding: 0; }}
QPlainTextEdit#ComposerEdit {{ border: none; background: transparent; padding: 4px; }}
QPlainTextEdit#CodeEditor {{ font-family: Consolas, 'Cascadia Code', monospace; font-size: 10pt;
    background: {c['code_bg']}; }}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus {{ border: 1px solid {c['accent']}; }}
QPushButton {{ background: {c['panel']}; border: 1px solid {c['border']}; border-radius: 8px; padding: 6px 12px; }}
QPushButton:hover {{ background: {c['hover']}; }}
QPushButton:checked {{ background: {c['accent']}; color: {c['accent_text']}; border-color: {c['accent']}; }}
QPushButton#Primary {{ background: {c['accent']}; color: {c['accent_text']}; border: none; font-weight: 600; }}
QPushButton#Primary:hover {{ background: {c['accent2']}; }}
QPushButton#Danger {{ color: {c['danger']}; }}
QToolButton {{ background: transparent; border: none; border-radius: 8px; padding: 5px; }}
QToolButton:hover {{ background: {c['hover']}; }}
QToolButton:checked {{ background: {c['accent']}; }}
QToolButton#SendBtn {{ background: {c['accent']}; border-radius: 16px; padding: 7px; }}
QToolButton#SendBtn:hover {{ background: {c['accent2']}; }}
QComboBox {{ background: {c['input']}; border: 1px solid {c['border']}; border-radius: 8px; padding: 4px 8px; min-height: 22px; }}
QComboBox QAbstractItemView {{ background: {c['panel']}; border: 1px solid {c['border']};
    selection-background-color: {c['accent']}; selection-color: {c['accent_text']}; }}
QListWidget {{ background: transparent; border: none; outline: none; }}
QListWidget::item {{ padding: 8px 10px; border-radius: 8px; margin: 1px 4px; }}
QListWidget::item:hover {{ background: {c['hover']}; }}
QListWidget::item:selected {{ background: {c['accent']}; color: {c['accent_text']}; }}
QTabWidget::pane {{ border: 1px solid {c['border']}; border-radius: 8px; background: {c['panel']}; }}
QTabBar::tab {{ background: transparent; padding: 7px 14px; border-bottom: 2px solid transparent; }}
QTabBar::tab:selected {{ border-bottom: 2px solid {c['accent']}; color: {c['accent']}; font-weight: 600; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 0; }}
QScrollBar::handle:vertical {{ background: {c['border']}; border-radius: 5px; min-height: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; }}
QScrollBar::handle:horizontal {{ background: {c['border']}; border-radius: 5px; }}
QMenu {{ background: {c['panel']}; border: 1px solid {c['border']}; padding: 4px; }}
QMenu::item {{ padding: 6px 18px; border-radius: 6px; }}
QMenu::item:selected {{ background: {c['accent']}; color: {c['accent_text']}; }}
QSplitter::handle {{ background: {c['border']}; }}
QGroupBox {{ border: 1px solid {c['border']}; border-radius: 8px; margin-top: 14px; padding-top: 8px; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 4px; color: {c['accent']}; }}
QCheckBox::indicator {{ width: 16px; height: 16px; }}
QToolTip {{ background: {c['panel']}; color: {c['text']}; border: 1px solid {c['border']}; }}
"""


def chat_css(mode: str) -> str:
    """CSS used inside the message QTextBrowsers (Qt rich-text subset)."""
    c = PALETTES[mode]
    from ..core.markdown_render import pygments_css
    return f"""
body {{ color: {c['text']}; line-height: 150%; }}
a {{ color: {c['accent']}; }}
pre {{ background: {c['code_bg']}; padding: 10px; font-family: Consolas, 'Cascadia Code', monospace; font-size: 9.5pt; }}
code {{ font-family: Consolas, monospace; background: {c['code_bg']}; }}
table {{ border-collapse: collapse; }}
th {{ background: {c['hover']}; font-weight: 600; }}
th, td {{ border: 1px solid {c['border']}; padding: 5px 9px; }}
blockquote {{ color: {c['muted']}; margin-left: 12px; }}
.math {{ font-family: 'Cambria Math', 'Times New Roman', serif; font-style: italic; color: {c['accent']}; }}
h1, h2, h3 {{ color: {c['accent']}; }}
{pygments_css(mode == 'dark')}
"""
