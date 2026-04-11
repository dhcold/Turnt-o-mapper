"""
Lightweight isometric / perspective wireframe 3D viewer.

``Viewer3DWidget`` is a QWidget subclass that renders rooms and bridges
as depth-sorted wireframe boxes.  Supports mouse-drag rotation, scroll
zoom, and WASD keyboard panning.  Preset views (Iso, Top, Front, Side)
are available via ``set_preset()``.
"""

import math
from typing import List, Tuple

from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, QTimer, QRectF, QPointF
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QBrush, QFont, QPolygonF
)

from .constants import T, DOOR_H
from .models import Room, Bridge


class Viewer3DWidget(QWidget):
    """Interactive isometric wireframe viewer for Room + Bridge lists.

    Usage::

        v = Viewer3DWidget(parent)
        v.load(rooms, bridges)
        v.set_preset("Iso")  # snap to isometric view
    """

    PRESETS = {
        "Iso":   (35.264, 45.0),
        "Top":   (89.9,    0.0),
        "Front": ( 0.0,    0.0),
        "Side":  ( 0.0,   90.0),
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(100, 100)
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)

        self._rooms:   List[Room]   = []
        self._bridges: List[Bridge] = []
        self._elev  =  30.0
        self._azim  =  45.0
        self._zoom  =   1.0
        self._drag_x = self._drag_y = 0
        self._pan_x  =  0.0
        self._pan_y  =  0.0
        self._keys: set = set()
        self._show_labels: bool = True
        self._cx3d = self._cy3d = self._cz3d = 0.0

        # WASD pan at ~60 fps
        self._wasd_timer = QTimer(self)
        self._wasd_timer.setInterval(16)
        self._wasd_timer.timeout.connect(self._wasd_tick)
        self._wasd_timer.start()

    # ── public API ────────────────────────────────────────────────────────
    def load(self, rooms: List[Room], bridges: List[Bridge],
             show_labels: bool = True):
        """Load a new set of rooms and bridges and redraw."""
        self._rooms        = rooms
        self._bridges      = bridges
        self._show_labels  = show_labels
        self._pan_x        = 0.0
        self._pan_y        = 0.0
        self._fit()
        self.update()

    def set_preset(self, name: str):
        """Snap the camera to a named preset view angle."""
        self._elev, self._azim = self.PRESETS.get(name, (30.0, 45.0))
        self.update()

    # ── WASD ──────────────────────────────────────────────────────────────
    def _wasd_tick(self):
        spd = max(4.0, 400.0 / max(self._zoom * 100, 1))
        changed = False
        if Qt.Key.Key_W in self._keys: self._pan_y += spd; changed = True
        if Qt.Key.Key_S in self._keys: self._pan_y -= spd; changed = True
        if Qt.Key.Key_A in self._keys: self._pan_x -= spd; changed = True
        if Qt.Key.Key_D in self._keys: self._pan_x += spd; changed = True
        if changed:
            self.update()

    # ── geometry ──────────────────────────────────────────────────────────
    def _fit(self):
        if not self._rooms:
            return
        xs = [r.x1 for r in self._rooms] + [r.x2 for r in self._rooms]
        ys = [r.y1 for r in self._rooms] + [r.y2 for r in self._rooms]
        zs = [r.z1 for r in self._rooms] + [r.z2 for r in self._rooms]
        span = max(max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs), 1)
        W = self.width()  or 400
        H = self.height() or 400
        self._zoom = min(W, H) * 0.55 / span
        self._cx3d = (min(xs) + max(xs)) / 2
        self._cy3d = (min(ys) + max(ys)) / 2
        self._cz3d = (min(zs) + max(zs)) / 2

    def _project(self, x, y, z) -> Tuple[float, float]:
        x -= self._cx3d
        y -= self._cy3d
        z -= self._cz3d

        az = math.radians(self._azim)
        el = math.radians(self._elev)

        xr =  x * math.cos(az) + y * math.sin(az)
        yr = -x * math.sin(az) + y * math.cos(az)

        xf =  xr
        zf =  yr * math.sin(el) + z * math.cos(el)

        W = self.width()  or 400
        H = self.height() or 400
        sx = W / 2 + xf * self._zoom + self._pan_x
        sy = H / 2 - zf * self._zoom + self._pan_y
        return sx, sy

    def _box_edges(self, x1, y1, z1, x2, y2, z2):
        corners = [
            (x1, y1, z1), (x2, y1, z1), (x2, y2, z1), (x1, y2, z1),
            (x1, y1, z2), (x2, y1, z2), (x2, y2, z2), (x1, y2, z2),
        ]
        proj = [self._project(*c) for c in corners]
        edges = [
            (0, 1), (1, 2), (2, 3), (3, 0),
            (4, 5), (5, 6), (6, 7), (7, 4),
            (0, 4), (1, 5), (2, 6), (3, 7),
        ]
        return [(proj[a], proj[b]) for a, b in edges]

    def _wedge_edges(self, corners):
        """Return projected edge pairs for an 8-corner sloped prism (ramp).

        corners must be a sequence of 8 (x, y, z) tuples ordered the same
        way as _box_edges: 0-3 are the bottom face (low end → high end),
        4-7 are the top face above them.
        """
        proj = [self._project(*c) for c in corners]
        edges = [
            (0, 1), (1, 2), (2, 3), (3, 0),
            (4, 5), (5, 6), (6, 7), (7, 4),
            (0, 4), (1, 5), (2, 6), (3, 7),
        ]
        return [(proj[a], proj[b]) for a, b in edges]

    # ── painting ──────────────────────────────────────────────────────────
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()
        painter.fillRect(0, 0, W, H, QColor(T["prev_bg"]))

        if not self._rooms:
            painter.setPen(QColor(T["text_dim"]))
            painter.setFont(QFont("Segoe UI", 11))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                             "Generate a map to see 3D view")
            return

        self._draw_scene(painter, W, H)

    def _draw_scene(self, painter: QPainter, W: int, H: int):
        n = len(self._rooms)

        def depth(r):
            _, sy = self._project(r.cx(), r.cy(), (r.z1 + r.z2) / 2)
            return sy
        sorted_rooms = sorted(self._rooms, key=depth, reverse=True)

        # Bridges first (behind rooms)
        pen_corr = QPen(QColor(T["corr_col"]), 1)
        for br in self._bridges:
            hw  = br.door_hw
            ht  = br.door_ht
            dz  = abs(br.az - br.bz)
            painter.setPen(pen_corr)

            if dz >= 32:
                # Ramp: sloped wedge — low end keeps its z, high end keeps its z.
                if br.axis == 'x':
                    if br.ax <= br.bx:
                        x_lo, z_lo = br.ax, br.az
                        x_hi, z_hi = br.bx, br.bz
                    else:
                        x_lo, z_lo = br.bx, br.bz
                        x_hi, z_hi = br.ax, br.az
                    cy = (br.ay + br.by) // 2
                    corners = [
                        (x_lo, cy - hw, z_lo),      (x_lo, cy + hw, z_lo),
                        (x_hi, cy + hw, z_hi),      (x_hi, cy - hw, z_hi),
                        (x_lo, cy - hw, z_lo + ht), (x_lo, cy + hw, z_lo + ht),
                        (x_hi, cy + hw, z_hi + ht), (x_hi, cy - hw, z_hi + ht),
                    ]
                else:  # 'y'
                    if br.ay <= br.by:
                        y_lo, z_lo = br.ay, br.az
                        y_hi, z_hi = br.by, br.bz
                    else:
                        y_lo, z_lo = br.by, br.bz
                        y_hi, z_hi = br.ay, br.az
                    cx = (br.ax + br.bx) // 2
                    corners = [
                        (cx - hw, y_lo, z_lo),      (cx + hw, y_lo, z_lo),
                        (cx + hw, y_hi, z_hi),      (cx - hw, y_hi, z_hi),
                        (cx - hw, y_lo, z_lo + ht), (cx + hw, y_lo, z_lo + ht),
                        (cx + hw, y_hi, z_hi + ht), (cx - hw, y_hi, z_hi + ht),
                    ]
                for (ax, ay), (bx, by) in self._wedge_edges(corners):
                    painter.drawLine(QPointF(ax, ay), QPointF(bx, by))
            else:
                # Flat corridor: plain axis-aligned box at the lower z level.
                if br.axis == 'x':
                    bx1, by1, bz1 = min(br.ax, br.bx), br.ay - hw, min(br.az, br.bz)
                    bx2, by2, bz2 = max(br.ax, br.bx), br.ay + hw, min(br.az, br.bz) + ht
                else:
                    bx1, by1, bz1 = br.ax - hw, min(br.ay, br.by), min(br.az, br.bz)
                    bx2, by2, bz2 = br.ax + hw, max(br.ay, br.by), min(br.az, br.bz) + ht
                for (ax, ay), (bx, by) in self._box_edges(bx1, by1, bz1, bx2, by2, bz2):
                    painter.drawLine(QPointF(ax, ay), QPointF(bx, by))

        # Rooms (depth sorted)
        for room in sorted_rooms:
            idx = room.idx
            if idx == 0:
                col_str, edge_str = T["start_col"], T["success"]
            elif idx == n - 1:
                col_str, edge_str = T["end_col"], T["accent"]
            else:
                t_speed = (room.speed_in - 550) / max(1, (550 + 60 * n) - 550)
                t_speed = max(0.0, min(1.0, t_speed))
                r_c = int(0x1e + t_speed * (0x2a - 0x1e))
                g_c = int(0x39 + t_speed * (0x5a - 0x39))
                b_c = int(0x60 + t_speed * (0x9e - 0x60))
                col_str  = f"#{r_c:02x}{g_c:02x}{b_c:02x}"
                edge_str = T["room_bdr"]

            col  = QColor(col_str)
            edge = QColor(edge_str)

            # Top face polygon (semi-transparent fill)
            top_col = QColor(col)
            top_col.setAlpha(120)
            top_pts = [
                self._project(room.x1, room.y1, room.z2),
                self._project(room.x2, room.y1, room.z2),
                self._project(room.x2, room.y2, room.z2),
                self._project(room.x1, room.y2, room.z2),
            ]
            poly = QPolygonF([QPointF(px, py) for px, py in top_pts])
            painter.setBrush(QBrush(top_col))
            painter.setPen(QPen(edge, 1))
            painter.drawPolygon(poly)

            # Box edges
            painter.setPen(QPen(edge, 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            for (ax, ay), (bx, by) in self._box_edges(
                    room.x1, room.y1, room.z1, room.x2, room.y2, room.z2):
                painter.drawLine(QPointF(ax, ay), QPointF(bx, by))

            # Label
            if self._show_labels:
                p_lo = self._project(room.x1, room.y1, room.z2)
                p_hi = self._project(room.x2, room.y2, room.z2)
                proj_size = max(abs(p_hi[0] - p_lo[0]), abs(p_hi[1] - p_lo[1]))
                label_gap = max(1, int(25 / max(proj_size, 1)))
                if proj_size > 18 and idx % label_gap == 0:
                    sx = (p_lo[0] + p_hi[0]) / 2
                    sy = (p_lo[1] + p_hi[1]) / 2 - 8
                    painter.setPen(QColor(T["text"]))
                    painter.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
                    painter.drawText(QPointF(sx, sy), str(idx + 1))

        # HUD
        hud = (f"elev={self._elev:.0f}°  azim={self._azim:.0f}°"
               f"  zoom={self._zoom*100:.0f}%"
               "   WASD=pan  drag=rotate  scroll=zoom")
        painter.setPen(QColor(T["text_dim"]))
        painter.setFont(QFont("Consolas", 7))
        painter.drawText(QPointF(8, 14), hud)

    # ── mouse / keyboard ──────────────────────────────────────────────────
    def mousePressEvent(self, event):
        self._drag_x = event.position().x()
        self._drag_y = event.position().y()
        self.setFocus()

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton:
            dx = event.position().x() - self._drag_x
            dy = event.position().y() - self._drag_y
            self._azim = (self._azim + dx * 0.5) % 360
            self._elev = max(-89.9, min(89.9, self._elev - dy * 0.4))
            self._drag_x = event.position().x()
            self._drag_y = event.position().y()
            self.update()

    def wheelEvent(self, event):
        if event.angleDelta().y() > 0:
            self._zoom *= 1.1
        else:
            self._zoom /= 1.1
        self._zoom = max(0.001, min(self._zoom, 50.0))
        self.update()

    def keyPressEvent(self, event):
        self._keys.add(event.key())

    def keyReleaseEvent(self, event):
        self._keys.discard(event.key())
