"""Opening screen: logo, name, author, Quranic verse and the COMMENCER button."""
from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt, Signal
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QBrush
from PySide6.QtWidgets import QGraphicsOpacityEffect, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from .. import i18n
from ..config import APP_VERSION
from .fonts import arabic_family, quran_family
from .logo import _star, logo_pixmap


class SplashScreen(QWidget):
    started = Signal(str)  # chosen language

    def __init__(self, lang: str = "fr"):
        super().__init__()
        self.lang = lang
        self.setWindowTitle("DOUBAJ AI")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.resize(980, 760)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(60, 36, 60, 30)
        lay.setSpacing(10)

        top = QHBoxLayout()
        top.addStretch()
        self.lang_btns = {}
        for code, label in (("fr", "FR"), ("ar", "ع"), ("en", "EN")):
            b = QPushButton(label)
            b.setCheckable(True)
            b.setFixedSize(40, 28)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, c=code: self.set_lang(c))
            b.setStyleSheet("QPushButton{background:rgba(255,255,255,0.08);color:#E6EAF2;border:1px solid rgba(255,255,255,0.18);"
                            "border-radius:6px;} QPushButton:checked{background:#E0B055;color:#0C1B2A;}")
            self.lang_btns[code] = b
            top.addWidget(b)
        close = QPushButton("✕")
        close.setFixedSize(28, 28)
        close.setStyleSheet("QPushButton{background:transparent;color:#8C96A8;border:none;font-size:14pt;}")
        close.clicked.connect(self.close)
        top.addWidget(close)
        lay.addLayout(top)

        logo = QLabel()
        logo.setPixmap(logo_pixmap(120))
        logo.setAlignment(Qt.AlignCenter)
        lay.addWidget(logo)

        title = QLabel("DOUBAJ AI")
        title.setAlignment(Qt.AlignCenter)
        f = QFont("Segoe UI", 38, QFont.Bold)
        f.setLetterSpacing(QFont.AbsoluteSpacing, 6)
        title.setFont(f)
        title.setStyleSheet("color:#FFFFFF;")
        lay.addWidget(title)

        self.tagline = QLabel()
        self.tagline.setAlignment(Qt.AlignCenter)
        self.tagline.setStyleSheet("color:#21B3BE;font-size:12pt;letter-spacing:1px;")
        lay.addWidget(self.tagline)

        lay.addSpacing(8)
        verse = QLabel(f"﴿ {i18n.VERSE} ﴾")
        verse.setWordWrap(True)
        verse.setAlignment(Qt.AlignCenter)
        verse.setLayoutDirection(Qt.RightToLeft)
        verse.setFont(QFont(quran_family(), 20))
        verse.setMinimumHeight(130)
        verse.setStyleSheet("color:#F3E3BC; padding: 6px 10px;")
        lay.addWidget(verse)
        ref = QLabel(i18n.VERSE_REF)
        ref.setAlignment(Qt.AlignCenter)
        ref.setFont(QFont(arabic_family(), 11))
        ref.setStyleSheet("color:#8C96A8;")
        lay.addWidget(ref)

        lay.addSpacing(10)
        self.author_ar = QLabel("من إعداد دباج أحمد")
        self.author_ar.setAlignment(Qt.AlignCenter)
        self.author_ar.setFont(QFont(arabic_family(), 17, QFont.Bold))
        self.author_ar.setStyleSheet("color:#E0B055;")
        lay.addWidget(self.author_ar)
        self.role = QLabel("أستاذ مادة التكنولوجيا الصناعية")
        self.role.setAlignment(Qt.AlignCenter)
        self.role.setFont(QFont(arabic_family(), 13))
        self.role.setStyleSheet("color:#C9D2E0;")
        lay.addWidget(self.role)
        self.role_tr = QLabel()
        self.role_tr.setAlignment(Qt.AlignCenter)
        self.role_tr.setStyleSheet("color:#8C96A8;font-size:9.5pt;")
        lay.addWidget(self.role_tr)

        lay.addStretch()
        self.btn = QPushButton("COMMENCER")
        self.btn.setCursor(Qt.PointingHandCursor)
        self.btn.setFixedSize(230, 50)
        self.btn.setStyleSheet(
            "QPushButton{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #0E7C86,stop:1 #21B3BE);color:white;"
            "font-size:14pt;font-weight:700;letter-spacing:3px;border:none;border-radius:25px;}"
            "QPushButton:hover{background:#E0B055;color:#0C1B2A;}")
        self.btn.clicked.connect(lambda: self.started.emit(self.lang))
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(self.btn)
        row.addStretch()
        lay.addLayout(row)
        lay.addSpacing(10)
        self.rights = QLabel()
        self.rights.setAlignment(Qt.AlignCenter)
        self.rights.setStyleSheet("color:#667085;font-size:8.5pt;")
        lay.addWidget(self.rights)

        self.set_lang(lang)
        # fade-in
        self._fx = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._fx)
        self._anim = QPropertyAnimation(self._fx, b"opacity", self)
        self._anim.setDuration(900)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim.start()
        self._drag = None

    def set_lang(self, code: str) -> None:
        self.lang = code
        i18n.set_lang(code)
        for c, b in self.lang_btns.items():
            b.setChecked(c == code)
        self.tagline.setText(i18n.tr("tagline") + f"  ·  v{APP_VERSION}")
        self.role_tr.setText("" if code == "ar" else i18n.tr("by") + " — " + i18n.tr("role"))
        self.rights.setText(i18n.tr("rights"))

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        g = QLinearGradient(0, 0, self.width(), self.height())
        g.setColorAt(0, QColor("#0C1B2A"))
        g.setColorAt(1, QColor("#08262B"))
        p.setBrush(QBrush(g))
        p.setPen(QColor(224, 176, 85, 90))
        p.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 22, 22)
        # discreet zellige stars in the background
        p.setPen(QColor(33, 179, 190, 28))
        p.setBrush(Qt.NoBrush)
        for x, y, r in ((80, 90, 60), (self.width() - 90, self.height() - 110, 80), (self.width() - 140, 120, 35),
                        (120, self.height() - 80, 40)):
            p.drawPolygon(_star(x, y, r, r * 0.8))
        p.end()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._drag = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if self._drag is not None:
            self.move(e.globalPosition().toPoint() - self._drag)

    def mouseReleaseEvent(self, _):
        self._drag = None

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key_Return, Qt.Key_Enter):
            self.started.emit(self.lang)
        elif e.key() == Qt.Key_Escape:
            self.close()
