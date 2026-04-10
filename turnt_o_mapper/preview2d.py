"""
2D top-down map preview renderer.

``draw_2d_preview()`` is a standalone function that draws rooms, bridges,
arrows, labels, and a height-map colour bar onto a Tkinter Canvas.  All
state (rooms, bridges, zoom, pan, options) is passed as parameters so the
function has no dependency on the App class.
"""

from typing import Dict, List

from .constants import T
from .models import Room, Bridge


def draw_2d_preview(canvas, rooms: List[Room], bridges: List[Bridge],
                    zoom: float, pan_x: float, pan_y: float,
                    is_rbe_import: bool = False,
                    use_physics: bool = False,
                    show_labels: bool = True,
                    show_hmap: bool = True):
    """Render a 2D top-down preview of the map onto *canvas*.

    Parameters:
        canvas: a ``tk.Canvas`` widget to draw on (cleared first).
        rooms: list of :class:`Room` objects to draw.
        bridges: list of :class:`Bridge` objects to draw.
        zoom: current zoom multiplier (1.0 = fit-to-canvas).
        pan_x, pan_y: pixel offsets for panning.
        is_rbe_import: True when showing an imported DBT map (hides labels).
        use_physics: True when physics model is active (shows speed labels).
        show_labels: whether to draw room numbers and Z-height labels.
        show_hmap: whether to draw the Z-height colour bar on the right edge.
    """
    c = canvas
    c.delete("all")
    W, H = c.winfo_width(), c.winfo_height()
    if W < 10 or H < 10:
        return
    if not rooms:
        c.create_text(W // 2, H // 2,
                      text="Press Generate map to see preview",
                      fill=T["text_dim"],
                      font=("Segoe UI", 12), justify="center")
        return

    all_x = [r.x1 for r in rooms] + [r.x2 for r in rooms]
    all_y = [r.y1 for r in rooms] + [r.y2 for r in rooms]
    mx, my = min(all_x), min(all_y)
    rw = max(all_x) - mx
    rh = max(all_y) - my

    PAD = 44
    sc_base = min((W - PAD * 2 - 24) / max(rw, 1),
                  (H - PAD * 2 - 20) / max(rh, 1))
    sc = sc_base * zoom

    cx_base = PAD + pan_x
    cy_base = H - PAD + pan_y

    def tx(v):
        return cx_base + (v - mx) * sc

    def ty(v):
        return cy_base - (v - my) * sc

    all_z   = [r.z1 for r in rooms]
    z_min   = min(all_z)
    z_max   = max(all_z)
    z_range = max(z_max - z_min, 1)

    # Build per-room exit/entry data for arrow drawing
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

    # ── Bridges ──────────────────────────────────────────────────────────
    for br in bridges:
        hw = br.door_hw
        if br.axis == 'x':
            xmn = min(br.ax, br.bx); xmx = max(br.ax, br.bx)
            cy  = (br.ay + br.by) // 2
            c.create_rectangle(tx(xmn), ty(cy - hw),
                               tx(xmx), ty(cy + hw),
                               fill=T["corr_col"],
                               outline=T["border"], width=1)
        else:
            cx  = (br.ax + br.bx) // 2
            ymn = min(br.ay, br.by); ymx = max(br.ay, br.by)
            c.create_rectangle(tx(cx - hw), ty(ymn),
                               tx(cx + hw), ty(ymx),
                               fill=T["corr_col"],
                               outline=T["border"], width=1)

    # ── Rooms ────────────────────────────────────────────────────────────
    n = len(rooms)
    for i, room in enumerate(rooms):
        if i == 0:
            fill, bdr = T["start_col"], T["success"]
        elif i == n - 1:
            fill, bdr = T["end_col"], T["accent"]
        else:
            if use_physics:
                t_s = (room.speed_in - 550) / max(1, 60 * n)
                t_s = max(0.0, min(1.0, t_s))
            else:
                t_s = 0.0
            t_z = (room.z1 - z_min) / z_range
            r_c = max(0, min(255, int(0x1e + t_s * (0x18 - 0x1e))))
            g_c = max(0, min(255, int(0x3a + t_s * (0x70 - 0x3a) + t_z * 0x35)))
            b_c = max(0, min(255, int(0x62 + t_s * (0x90 - 0x62))))
            fill = f"#{r_c:02x}{g_c:02x}{b_c:02x}"
            bdr  = T["room_bdr"]

        ls = tx(room.x1); rs = tx(room.x2)
        ts = ty(room.y2); bs = ty(room.y1)
        c.create_rectangle(ls, ts, rs, bs,
                           fill=fill, outline=bdr, width=2)

        pw = rs - ls
        ph = bs - ts
        cxs = (ls + rs) / 2
        cys = (ts + bs) / 2
        fs  = max(7, min(14, int(min(pw, ph) / 4)))
        min_dim = min(pw, ph)

        _show_lbl = show_labels and not is_rbe_import
        if _show_lbl and min_dim > 30:
            c.create_text(ls + 4, ts + 3,
                          text=str(i + 1),
                          fill="white",
                          font=("Segoe UI", max(8, fs), "bold"),
                          anchor="nw")

        if _show_lbl and min_dim > 45:
            z_label = f"z{room.z1:+d}" if room.z1 != 0 else "z0"
            c.create_text(rs - 4, ts + 3,
                          text=z_label,
                          fill="#7fb8d0",
                          font=("Consolas", max(6, fs - 2)),
                          anchor="ne")

        if not is_rbe_import and use_physics:
            c.create_text(ls + 4, bs - 3,
                          text=f"{room.speed_in:.0f}u",
                          fill=T["accent2"],
                          font=("Segoe UI", max(6, fs - 2), "bold"),
                          anchor="sw")

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

            if wall_name == 'wx2':
                cx_d = rs; cy_d = ty(center)
                c.create_line(cxs, cys, cx_d, cy_d,
                              fill=arrow_col, width=a_w,
                              arrow="last", arrowshape=(9, 11, 4))
            elif wall_name == 'wx1':
                cx_d = ls; cy_d = ty(center)
                c.create_line(cxs, cys, cx_d, cy_d,
                              fill=arrow_col, width=a_w,
                              arrow="last", arrowshape=(9, 11, 4))
            elif wall_name == 'wy2':
                cx_d = tx(center); cy_d = ts
                c.create_line(cxs, cys, cx_d, cy_d,
                              fill=arrow_col, width=a_w,
                              arrow="last", arrowshape=(9, 11, 4))
            elif wall_name == 'wy1':
                cx_d = tx(center); cy_d = bs
                c.create_line(cxs, cys, cx_d, cy_d,
                              fill=arrow_col, width=a_w,
                              arrow="last", arrowshape=(9, 11, 4))

    # ── Z-height scale bar ───────────────────────────────────────────────
    if z_min != z_max and show_hmap:
        sx = W - 18
        for py in range(int(PAD), int(H - PAD)):
            t = 1.0 - (py - PAD) / max(H - PAD * 2, 1)
            gv = int(0x28 + t * 0x88)
            c.create_line(sx, py, sx + 10, py,
                          fill=f"#1e{gv:02x}60")
        c.create_text(sx + 5, PAD - 2,   text=f"+{z_max}",
                      fill=T["text_dim"], font=("Consolas", 7), anchor="s")
        c.create_text(sx + 5, H - PAD + 2, text=f"{z_min}",
                      fill=T["text_dim"], font=("Consolas", 7), anchor="n")

    # ── Legend ────────────────────────────────────────────────────────────
    items = [("\u25a0 Start", T["success"]), ("\u25a0 Rooms", T["room_col"]),
             ("\u25a0 End",   T["accent"]),  ("\u2501 Bridge", T["corr_col"]),
             ("\u2192 Exit", "#ffdd33"),     ("\u2192 Entry", "#66aacc")]
    for j, (txt, col) in enumerate(items):
        c.create_text(PAD + j * 88, H - 13, text=txt,
                      fill=col, font=("Segoe UI", 8), anchor="w")
