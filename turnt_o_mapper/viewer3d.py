"""
Lightweight isometric / perspective wireframe 3D viewer.

``Viewer3D`` is a Tkinter Canvas subclass that renders rooms and bridges
as depth-sorted wireframe boxes.  Supports mouse-drag rotation, scroll
zoom, and WASD keyboard panning.  Preset views (Iso, Top, Front, Side)
are available via ``set_preset()``.
"""

import math
from typing import List, Tuple

import tkinter as tk

from .constants import T, DOOR_H
from .models import Room, Bridge


class Viewer3D(tk.Canvas):
    """Interactive isometric wireframe viewer for Room + Bridge lists.

    Usage::

        v = Viewer3D(parent_frame)
        v.load(rooms, bridges)
        v.set_preset("Iso")  # snap to isometric view
    """

    PRESETS = {
        "Iso":   (35.264, 45.0),
        "Top":   (89.9,    0.0),
        "Front": ( 0.0,    0.0),
        "Side":  ( 0.0,   90.0),
    }

    def __init__(self, parent, **kw):
        super().__init__(parent, bg=T["prev_bg"],
                         highlightthickness=1,
                         highlightbackground=T["border"], **kw)
        self._rooms:   List[Room]   = []
        self._bridges: List[Bridge] = []
        self._elev  =  30.0
        self._azim  =  45.0
        self._zoom  =   1.0
        self._drag_x = self._drag_y = 0
        self._pan_x  =  0.0
        self._pan_y  =  0.0
        self._keys: set = set()
        self._wasd_job  = None

        self.bind("<Configure>",      lambda e: self._draw())
        self.bind("<ButtonPress-1>",  self._on_press)
        self.bind("<B1-Motion>",      self._on_drag)
        self.bind("<MouseWheel>",     self._on_scroll)
        self.bind("<Button-4>",       self._on_scroll)
        self.bind("<Button-5>",       self._on_scroll)
        self.bind("<ButtonPress-1>",  lambda e: (self.focus_set(), self._on_press(e)))
        self.bind("<KeyPress>",       self._on_key_press)
        self.bind("<KeyRelease>",     self._on_key_release)

        self._wasd_start()

    # ── WASD camera ───────────────────────────────────────────────────────
    def _on_key_press(self, e):
        self._keys.add(e.keysym.lower())

    def _on_key_release(self, e):
        self._keys.discard(e.keysym.lower())

    def _wasd_start(self):
        self._wasd_job = self.after(16, self._wasd_tick)

    def _wasd_tick(self):
        spd = max(4.0, 400.0 / max(self._zoom * 100, 1))
        changed = False
        if 'w' in self._keys:  self._pan_y += spd; changed = True
        if 's' in self._keys:  self._pan_y -= spd; changed = True
        if 'a' in self._keys:  self._pan_x -= spd; changed = True
        if 'd' in self._keys:  self._pan_x += spd; changed = True
        if changed:
            self._draw()
        self._wasd_job = self.after(16, self._wasd_tick)

    # ── public API ────────────────────────────────────────────────────────
    def load(self, rooms: List[Room], bridges: List[Bridge],
             show_labels: bool = True):
        """Load a new set of rooms and bridges and redraw."""
        self._rooms   = rooms
        self._bridges = bridges
        self._show_labels = show_labels
        self._pan_x   = 0.0
        self._pan_y   = 0.0
        self._fit()
        self._draw()

    def set_preset(self, name: str):
        """Snap the camera to a named preset view angle."""
        elev, azim = self.PRESETS.get(name, (30.0, 45.0))
        self._elev = elev
        self._azim = azim
        self._draw()

    # ── internal ──────────────────────────────────────────────────────────
    def _fit(self):
        """Reset zoom so the whole map fits the canvas."""
        if not self._rooms:
            return
        xs = [r.x1 for r in self._rooms] + [r.x2 for r in self._rooms]
        ys = [r.y1 for r in self._rooms] + [r.y2 for r in self._rooms]
        zs = [r.z1 for r in self._rooms] + [r.z2 for r in self._rooms]
        span = max(max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs), 1)
        W = self.winfo_width()  or 400
        H = self.winfo_height() or 400
        self._zoom = min(W, H) * 0.55 / span
        self._cx3d = (min(xs) + max(xs)) / 2
        self._cy3d = (min(ys) + max(ys)) / 2
        self._cz3d = (min(zs) + max(zs)) / 2

    def _project(self, x, y, z) -> Tuple[float, float]:
        """Project a 3D point to 2D screen coordinates via rotation matrix."""
        x -= self._cx3d
        y -= self._cy3d
        z -= self._cz3d

        az = math.radians(self._azim)
        el = math.radians(self._elev)

        xr =  x * math.cos(az) + y * math.sin(az)
        yr = -x * math.sin(az) + y * math.cos(az)
        zr =  z

        xf =  xr
        yf =  yr * math.cos(el) - zr * math.sin(el)
        zf =  yr * math.sin(el) + zr * math.cos(el)

        W = self.winfo_width()  or 400
        H = self.winfo_height() or 400
        sx = W / 2 + xf * self._zoom + self._pan_x
        sy = H / 2 - zf * self._zoom + self._pan_y
        return sx, sy

    def _box_edges(self, x1, y1, z1, x2, y2, z2):
        """Return screen-coord edge pairs for an axis-aligned box."""
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

    def _draw(self):
        """Render the full scene: bridges, rooms (depth-sorted), labels."""
        self.delete("all")
        W = self.winfo_width()
        H = self.winfo_height()
        if W < 10 or H < 10 or not self._rooms:
            if not self._rooms:
                self.create_text(W // 2 if W > 10 else 200,
                                 H // 2 if H > 10 else 150,
                                 text="Generate a map to see 3D view",
                                 fill=T["text_dim"],
                                 font=("Segoe UI", 11))
            return

        n = len(self._rooms)

        def depth(r):
            _, sy = self._project(r.cx(), r.cy(), (r.z1 + r.z2) / 2)
            return sy
        sorted_rooms = sorted(self._rooms, key=depth, reverse=True)

        # Bridges first (behind rooms)
        for br in self._bridges:
            hw = br.door_hw
            if br.axis == 'x':
                bx1, by1, bz1 = min(br.ax, br.bx), br.ay - hw, min(br.az, br.bz)
                bx2, by2, bz2 = max(br.ax, br.bx), br.ay + hw, min(br.az, br.bz) + DOOR_H
            else:
                bx1, by1, bz1 = br.ax - hw, min(br.ay, br.by), min(br.az, br.bz)
                bx2, by2, bz2 = br.ax + hw, max(br.ay, br.by), min(br.az, br.bz) + DOOR_H
            for pa, pb in self._box_edges(bx1, by1, bz1, bx2, by2, bz2):
                self.create_line(pa[0], pa[1], pb[0], pb[1],
                                 fill=T["corr_col"], width=1)

        # Rooms
        for room in sorted_rooms:
            idx = room.idx
            if idx == 0:
                col, edge_col = T["start_col"], T["success"]
            elif idx == n - 1:
                col, edge_col = T["end_col"], T["accent"]
            else:
                t_speed = (room.speed_in - 550) / max(1, (550 + 60 * n) - 550)
                t_speed = max(0.0, min(1.0, t_speed))
                r_c = int(0x1e + t_speed * (0x2a - 0x1e))
                g_c = int(0x39 + t_speed * (0x5a - 0x39))
                b_c = int(0x60 + t_speed * (0x9e - 0x60))
                col = f"#{r_c:02x}{g_c:02x}{b_c:02x}"
                edge_col = T["room_bdr"]

            edges = self._box_edges(room.x1, room.y1, room.z1,
                                    room.x2, room.y2, room.z2)
            top_pts = [
                self._project(room.x1, room.y1, room.z2),
                self._project(room.x2, room.y1, room.z2),
                self._project(room.x2, room.y2, room.z2),
                self._project(room.x1, room.y2, room.z2),
            ]
            flat_top = [c for pt in top_pts for c in pt]
            self.create_polygon(flat_top, fill=col,
                                outline=edge_col, width=1,
                                stipple="gray25")
            for pa, pb in edges:
                self.create_line(pa[0], pa[1], pb[0], pb[1],
                                 fill=edge_col, width=1)

            if getattr(self, '_show_labels', True):
                p_lo = self._project(room.x1, room.y1, room.z2)
                p_hi = self._project(room.x2, room.y2, room.z2)
                proj_size = max(abs(p_hi[0] - p_lo[0]), abs(p_hi[1] - p_lo[1]))
                label_gap = max(1, int(25 / max(proj_size, 1)))
                if proj_size > 18 and idx % label_gap == 0:
                    sx, sy = (p_lo[0] + p_hi[0]) / 2, (p_lo[1] + p_hi[1]) / 2
                    self.create_text(sx, sy - 8, text=str(idx + 1),
                                     fill=T["text"], font=("Segoe UI", 7, "bold"))

        self.create_text(8, 8,
            text=(f"elev={self._elev:.0f}\u00b0  azim={self._azim:.0f}\u00b0  zoom={self._zoom*100:.0f}%"
                  f"   WASD=pan  drag=rotate  scroll=zoom"),
            fill=T["text_dim"], font=("Consolas", 7), anchor="nw")

    # ── mouse interaction ─────────────────────────────────────────────────
    def _on_press(self, e):
        self._drag_x = e.x
        self._drag_y = e.y

    def _on_drag(self, e):
        dx = e.x - self._drag_x
        dy = e.y - self._drag_y
        self._azim  = (self._azim  + dx * 0.5) % 360
        self._elev  = max(-89.9, min(89.9, self._elev - dy * 0.4))
        self._drag_x = e.x
        self._drag_y = e.y
        self._draw()

    def _on_scroll(self, e):
        if e.num == 4 or e.delta > 0:
            self._zoom *= 1.1
        else:
            self._zoom /= 1.1
        self._zoom = max(0.001, min(self._zoom, 50.0))
        self._draw()
