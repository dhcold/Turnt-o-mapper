"""
2D top-down map preview renderer.

``Preview2DWidget`` is a QWidget subclass that draws rooms, bridges,
arrows, labels, and a height-map colour bar.  State (rooms, bridges,
zoom, pan, options) is stored internally; call ``load()`` to update and
``fit()`` to reset the viewport.
"""

import io
import math
from typing import Dict, List, Optional

from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, QPointF, QRectF
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QBrush, QFont, QPolygonF, QFontMetrics
)

from .constants import T
from .models import Room, Bridge


def _draw_arrow(painter: QPainter, x1: float, y1: float,
                x2: float, y2: float, color: str, width: int):
    """Draw a line with a filled arrowhead at (x2, y2)."""
    angle = math.atan2(y2 - y1, x2 - x1)
    hs = 9
    pts = QPolygonF([
        QPointF(x2, y2),
        QPointF(x2 - hs * math.cos(angle - 0.4), y2 - hs * math.sin(angle - 0.4)),
        QPointF(x2 - hs * math.cos(angle + 0.4), y2 - hs * math.sin(angle + 0.4)),
    ])
    qcol = QColor(color)
    painter.setPen(QPen(qcol, width))
    painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))
    painter.setBrush(QBrush(qcol))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawPolygon(pts)


class Preview2DWidget(QWidget):
    """Interactive 2D top-down preview of a generated map."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(100, 100)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)

        self._rooms:   List[Room]   = []
        self._bridges: List[Bridge] = []
        self._zoom   = 1.0
        self._pan_x  = 0.0
        self._pan_y  = 0.0
        self._drag_x = 0.0
        self._drag_y = 0.0

        self._is_rbe_import = False
        self._use_physics   = False
        self._show_labels   = True
        self._show_hmap     = True

    # ── public API ────────────────────────────────────────────────────────
    def load(self, rooms: List[Room], bridges: List[Bridge],
             is_rbe_import: bool = False,
             use_physics:   bool = False,
             show_labels:   bool = True,
             show_hmap:     bool = True):
        self._rooms         = rooms
        self._bridges       = bridges
        self._is_rbe_import = is_rbe_import
        self._use_physics   = use_physics
        self._show_labels   = show_labels
        self._show_hmap     = show_hmap
        self.update()

    def fit(self):
        self._zoom  = 1.0
        self._pan_x = 0.0
        self._pan_y = 0.0
        self.update()

    # ── painting ──────────────────────────────────────────────────────────
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()
        painter.fillRect(0, 0, W, H, QColor(T["prev_bg"]))

        if not self._rooms:
            painter.setPen(QColor(T["text_dim"]))
            painter.setFont(QFont("Segoe UI", 12))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                             "Press Generate to see preview")
            return

        self._draw_scene(painter, W, H)

    def _make_transforms(self, W: int, H: int):
        all_x = [r.x1 for r in self._rooms] + [r.x2 for r in self._rooms]
        all_y = [r.y1 for r in self._rooms] + [r.y2 for r in self._rooms]
        mx, my = min(all_x), min(all_y)
        rw = max(all_x) - mx
        rh = max(all_y) - my

        PAD = 44
        sc_base = min((W - PAD * 2 - 24) / max(rw, 1),
                      (H - PAD * 2 - 20) / max(rh, 1))
        sc = sc_base * self._zoom

        cx_base = PAD + self._pan_x
        cy_base = H - PAD + self._pan_y

        def tx(v): return cx_base + (v - mx) * sc
        def ty(v): return cy_base - (v - my) * sc

        return tx, ty, sc, PAD

    def _draw_scene(self, painter: QPainter, W: int, H: int):
        rooms, bridges = self._rooms, self._bridges
        tx, ty, sc, PAD = self._make_transforms(W, H)

        all_z   = [r.z1 for r in rooms]
        z_min   = min(all_z)
        z_max   = max(all_z)
        z_range = max(z_max - z_min, 1)
        n       = len(rooms)

        # Per-room exit/entry map for arrows
        room_exits: Dict[int, list] = {}
        for br in bridges:
            hw = br.door_hw
            ra = rooms[br.room_a]; rb = rooms[br.room_b]
            if br.axis == 'x':
                ra_wall = 'wx2' if br.ax >= ra.x2 - 1 else 'wx1'
                rb_wall = 'wx1' if br.bx <= rb.x1 + 1 else 'wx2'
                room_exits.setdefault(br.room_a, []).append((ra_wall, br.ay, hw))
                room_exits.setdefault(br.room_b, []).append((rb_wall, br.ay, hw))
            else:
                ra_wall = 'wy2' if br.ay >= ra.y2 - 1 else 'wy1'
                rb_wall = 'wy1' if br.by <= rb.y1 + 1 else 'wy2'
                room_exits.setdefault(br.room_a, []).append((ra_wall, br.ax, hw))
                room_exits.setdefault(br.room_b, []).append((rb_wall, br.ax, hw))

        # ── Bridges ──────────────────────────────────────────────────────
        for br in bridges:
            hw = br.door_hw
            if br.axis == 'x':
                xmn = min(br.ax, br.bx); xmx = max(br.ax, br.bx)
                cy  = (br.ay + br.by) // 2
                painter.fillRect(
                    QRectF(tx(xmn), ty(cy + hw), tx(xmx) - tx(xmn), ty(cy - hw) - ty(cy + hw)),
                    QColor(T["corr_col"]))
                painter.setPen(QPen(QColor(T["border"]), 1))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRect(
                    QRectF(tx(xmn), ty(cy + hw), tx(xmx) - tx(xmn), ty(cy - hw) - ty(cy + hw)))
            else:
                cx  = (br.ax + br.bx) // 2
                ymn = min(br.ay, br.by); ymx = max(br.ay, br.by)
                painter.fillRect(
                    QRectF(tx(cx - hw), ty(ymx), tx(cx + hw) - tx(cx - hw), ty(ymn) - ty(ymx)),
                    QColor(T["corr_col"]))
                painter.setPen(QPen(QColor(T["border"]), 1))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRect(
                    QRectF(tx(cx - hw), ty(ymx), tx(cx + hw) - tx(cx - hw), ty(ymn) - ty(ymx)))

        # ── Rooms ────────────────────────────────────────────────────────
        for i, room in enumerate(rooms):
            if i == 0:
                fill_str, bdr_str = T["start_col"], T["success"]
            elif i == n - 1:
                fill_str, bdr_str = T["end_col"], T["accent"]
            else:
                if self._use_physics:
                    t_s = (room.speed_in - 550) / max(1, 60 * n)
                    t_s = max(0.0, min(1.0, t_s))
                else:
                    t_s = 0.0
                t_z = (room.z1 - z_min) / z_range
                r_c = max(0, min(255, int(0x1e + t_s * (0x18 - 0x1e))))
                g_c = max(0, min(255, int(0x3a + t_s * (0x70 - 0x3a) + t_z * 0x35)))
                b_c = max(0, min(255, int(0x62 + t_s * (0x90 - 0x62))))
                fill_str = f"#{r_c:02x}{g_c:02x}{b_c:02x}"
                bdr_str  = T["room_bdr"]

            ls = tx(room.x1); rs = tx(room.x2)
            ts = ty(room.y2); bs = ty(room.y1)
            rect = QRectF(ls, ts, rs - ls, bs - ts)

            painter.fillRect(rect, QColor(fill_str))
            painter.setPen(QPen(QColor(bdr_str), 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(rect)

            pw = rs - ls
            ph = bs - ts
            cxs = (ls + rs) / 2
            cys = (ts + bs) / 2
            fs  = max(7, min(14, int(min(pw, ph) / 4)))
            min_dim = min(pw, ph)

            _show_lbl = self._show_labels and not self._is_rbe_import

            if _show_lbl and min_dim > 30:
                painter.setPen(QColor("white"))
                painter.setFont(QFont("Segoe UI", max(8, fs), QFont.Weight.Bold))
                painter.drawText(QPointF(ls + 4, ts + fs + 3), str(i + 1))

            if _show_lbl and min_dim > 45:
                z_label = f"z{room.z1:+d}" if room.z1 != 0 else "z0"
                painter.setPen(QColor("#7fb8d0"))
                painter.setFont(QFont("Consolas", max(6, fs - 2)))
                fm = QFontMetrics(painter.font())
                tw = fm.horizontalAdvance(z_label)
                painter.drawText(QPointF(rs - tw - 4, ts + max(6, fs - 2) + 3), z_label)

            if not self._is_rbe_import and self._use_physics:
                spd_txt = f"{room.speed_in:.0f}u"
                painter.setPen(QColor(T["accent2"]))
                painter.setFont(QFont("Segoe UI", max(6, fs - 2), QFont.Weight.Bold))
                painter.drawText(QPointF(ls + 4, bs - 3), spd_txt)

            # Exit / entry arrows
            exits = room_exits.get(i, [])
            AW = max(2, int(min(pw, ph) * 0.05))

            for wall_name, center, hw in exits:
                is_exit = any(
                    br.room_a == i
                    for br in bridges
                    if (br.axis == 'x' and br.ay == center and wall_name in ('wx1', 'wx2')) or
                       (br.axis == 'y' and br.ax == center and wall_name in ('wy1', 'wy2'))
                )
                arrow_col = "#ffdd33" if is_exit else "#66aacc"
                a_w = AW if is_exit else max(1, AW - 1)

                painter.setBrush(Qt.BrushStyle.NoBrush)
                if wall_name == 'wx2':
                    _draw_arrow(painter, cxs, cys, rs, ty(center), arrow_col, a_w)
                elif wall_name == 'wx1':
                    _draw_arrow(painter, cxs, cys, ls, ty(center), arrow_col, a_w)
                elif wall_name == 'wy2':
                    _draw_arrow(painter, cxs, cys, tx(center), ts, arrow_col, a_w)
                elif wall_name == 'wy1':
                    _draw_arrow(painter, cxs, cys, tx(center), bs, arrow_col, a_w)

        # ── Z-height scale bar ───────────────────────────────────────────
        if z_min != z_max and self._show_hmap:
            sx = W - 18
            for py in range(int(PAD), int(H - PAD)):
                t_val = 1.0 - (py - PAD) / max(H - PAD * 2, 1)
                gv = int(0x28 + t_val * 0x88)
                painter.setPen(QColor(0x1e, gv, 0x60))
                painter.drawLine(int(sx), py, int(sx) + 10, py)
            painter.setPen(QColor(T["text_dim"]))
            painter.setFont(QFont("Consolas", 7))
            painter.drawText(QPointF(sx, PAD - 4), f"+{z_max}")
            painter.drawText(QPointF(sx, H - PAD + 10), f"{z_min}")

        # ── Legend ────────────────────────────────────────────────────────
        items = [
            ("\u25a0 Start", T["success"]), ("\u25a0 Rooms", T["room_col"]),
            ("\u25a0 End",   T["accent"]),  ("\u2501 Bridge", T["corr_col"]),
            ("\u2192 Exit", "#ffdd33"),     ("\u2192 Entry", "#66aacc"),
        ]
        painter.setFont(QFont("Segoe UI", 8))
        for j, (txt, col) in enumerate(items):
            painter.setPen(QColor(col))
            painter.drawText(QPointF(PAD + j * 88, H - 5), txt)

    # ── mouse interaction ─────────────────────────────────────────────────
    def wheelEvent(self, event):
        factor = 1.15 if event.angleDelta().y() > 0 else 1.0 / 1.15
        self._zoom = max(0.05, min(self._zoom * factor, 80.0))
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_x = event.position().x()
            self._drag_y = event.position().y()

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton:
            dx = event.position().x() - self._drag_x
            dy = event.position().y() - self._drag_y
            self._pan_x += dx
            self._pan_y += dy
            self._drag_x = event.position().x()
            self._drag_y = event.position().y()
            self.update()

    def mouseDoubleClickEvent(self, event):
        self.fit()
