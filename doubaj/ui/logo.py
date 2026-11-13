"""Original DOUBAJ AI logo, drawn in code (no external artwork):
an eight-pointed star (zellige motif) in teal and gold, enclosing a stylised 'D' made of a
circuit line with neural nodes."""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QIcon, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap, QPolygonF

TEAL = QColor("#0E7C86")
TEAL2 = QColor("#21B3BE")
GOLD = QColor("#E0B055")
NIGHT = QColor("#0C1B2A")


def _star(cx: float, cy: float, r_out: float, r_in: float, points: int = 8) -> QPolygonF:
    poly = QPolygonF()
    for i in range(points * 2):
        r = r_out if i % 2 == 0 else r_in
        a = math.pi / points * i - math.pi / 2
        poly.append(QPointF(cx + r * math.cos(a), cy + r * math.sin(a)))
    return poly


def paint_logo(p: QPainter, size: int) -> None:
    s = float(size)
    c = s / 2
    p.setRenderHint(QPainter.Antialiasing)
    grad = QLinearGradient(0, 0, s, s)
    grad.setColorAt(0, TEAL2)
    grad.setColorAt(1, TEAL)
    # outer star
    p.setPen(QPen(GOLD, max(1.0, s * 0.025)))
    p.setBrush(QBrush(grad))
    p.drawPolygon(_star(c, c, s * 0.48, s * 0.39))
    # inner disc
    p.setPen(Qt.NoPen)
    p.setBrush(NIGHT)
    p.drawEllipse(QPointF(c, c), s * 0.31, s * 0.31)
    # stylised D: vertical bar + arc as a circuit trace
    pen = QPen(GOLD, s * 0.045, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    x0, top, bot = c - s * 0.12, c - s * 0.17, c + s * 0.17
    path = QPainterPath(QPointF(x0, top))
    path.lineTo(x0, bot)
    path.moveTo(x0, top)
    path.lineTo(c, top)
    path.arcTo(QRectF(c - s * 0.17, top, s * 0.34, s * 0.34), 90, -180)
    path.lineTo(x0, bot)
    p.drawPath(path)
    # neural nodes
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#FFFFFF"))
    for (dx, dy) in ((0, 0), (0.08, -0.07), (0.08, 0.07)):
        p.drawEllipse(QPointF(c - s * 0.02 + s * dx, c + s * dy), s * 0.03, s * 0.03)
    p.setPen(QPen(QColor(255, 255, 255, 170), s * 0.012))
    p.drawLine(QPointF(c - s * 0.02, c), QPointF(c + s * 0.06, c - s * 0.07))
    p.drawLine(QPointF(c - s * 0.02, c), QPointF(c + s * 0.06, c + s * 0.07))
    p.drawLine(QPointF(x0, c), QPointF(c - s * 0.02, c))


def logo_pixmap(size: int = 128) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    paint_logo(p, size)
    p.end()
    return pm


def app_icon() -> QIcon:
    icon = QIcon()
    for s in (16, 24, 32, 48, 64, 128, 256):
        icon.addPixmap(logo_pixmap(s))
    return icon


def export_icon_files(png_path: str, ico_path: str | None = None) -> None:
    """Used by the build script to create doubaj.png / doubaj.ico."""
    logo_pixmap(512).save(png_path)
    if ico_path:
        from PIL import Image
        Image.open(png_path).save(ico_path, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
