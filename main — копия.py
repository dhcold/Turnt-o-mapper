#!/usr/bin/env python3
"""
Turnt-o-mator — Quake 3 / Turnt Defrag Map Generator
"""

import random, os, math, threading, time
from dataclasses import dataclass
from typing import List, Optional, Dict
import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext

try:
    from PIL import Image, ImageTk
    PIL_OK = True
except ImportError:
    PIL_OK = False

# ══════════════════════════════════════════════════════════════════════════════
#  TEXTURES
# ══════════════════════════════════════════════════════════════════════════════
ALL_TEXTURES: Dict[str, int] = {
    "NULL":2,"common/caulk":2,"common/lavacaulk":4,"common/nodraw":2,
    "common/nodrawnonsolid":2,"common/slick":5,"common/slimecaulk":4,
    "common/watercaulk":3,"common/weapclip":2,
    "turnt/temp_blue":8,"turnt/temp_dark":0,"turnt/temp_green":7,
    "turnt/temp_light":1,"turnt/temp_orange":9,"turnt/temp_purple":10,
    "turnt/temp_red":6,"turnt/temp_yellow":11,
    "turnt/turnt_asphalt":12,"turnt/turnt_asphalt_t2":30,
    "turnt/turnt_boost":13,"turnt/turnt_boost_2":31,
    "turnt/turnt_checkpoint":14,"turnt/turnt_checkpoint_2":32,
    "turnt/turnt_concrete":15,"turnt/turnt_concrete_2":33,
    "turnt/turnt_coral":16,"turnt/turnt_coral_t2":34,
    "turnt/turnt_cyan":17,"turnt/turnt_cyan_t2":17,
    "turnt/turnt_gold":18,"turnt/turnt_gold_t2":36,
    "turnt/turnt_hazard":19,"turnt/turnt_hazard_2t":37,
    "turnt/turnt_lime":20,"turnt/turnt_lime_t2":38,
    "turnt/turnt_magenta":21,"turnt/turnt_magenta_t2":39,
    "turnt/turnt_mint":22,"turnt/turnt_mint_t2":40,
    "turnt/turnt_orange":9,"turnt/turnt_orange_2t":41,
    "turnt/turnt_platform":23,"turnt/turnt_platform_2t":42,
    "turnt/turnt_sky":24,"turnt/turnt_sky_2t":43,
    "turnt/turnt_speed":25,"turnt/turnt_speed_2t":44,
    "turnt/turnt_teal":26,"turnt/turnt_teal_2t":45,
    "turnt/turnt_tech":27,"turnt/turnt_tech_2t":46,
    "turnt/turnt_violet":28,"turnt/turnt_violet_2t":47,
    "turnt/turnt_white":29,"turnt/turnt_white_2t":48,
}

FLOOR_TEX  = ["turnt/turnt_concrete","turnt/turnt_asphalt","turnt/turnt_platform",
               "turnt/turnt_tech","turnt/turnt_teal","common/slick"]
WALL_TEX   = ["turnt/turnt_concrete","turnt/turnt_tech","turnt/turnt_white",
               "turnt/turnt_cyan","turnt/turnt_mint","turnt/turnt_violet"]
CEIL_TEX   = ["turnt/turnt_sky","turnt/turnt_white","turnt/turnt_tech","common/nodraw"]
HIDDEN_TEX = "common/caulk"
NODRAW_TEX = "common/nodrawnonsolid"

WALL_T  = 16
DOOR_W  = 128
DOOR_H  = 128

# ══════════════════════════════════════════════════════════════════════════════
#  THEME
# ══════════════════════════════════════════════════════════════════════════════






















T = {
    "bg":        "#0b1020",
    "bg_panel":  "#121a2b",
    "bg_card":   "#17233a",
    "bg_input":  "#0f1728",
    "accent":    "#59d4ff",
    "accent2":   "#7c6cff",
    "text":      "#eaf1ff",
    "text_dim":  "#97a6c4",
    "success":   "#3ddc97",
    "warning":   "#ffb86b",
    "border":    "#273453",
    "btn_fg":    "#ffffff",
    "prev_bg":   "#0d1526",
    "room_col":  "#1e3960",
    "room_bdr":  "#59d4ff",
    "corr_col":  "#1b2a40",
    "start_col": "#11452f",
    "end_col":   "#4a1a2f",
    "lbx_bg":    "#0f1728",
    "lbx_sel":   "#223454",
    "dot_grid":  "#1a2740",
}

# ══════════════════════════════════════════════════════════════════════════════
#  MAP CORE
# ══════════════════════════════════════════════════════════════════════════════
def fv(v):
    return f"( {v[0]:g} {v[1]:g} {v[2]:g} )"

def face(p1, p2, p3, tex,
         ua=(1,0,0), uo=0,
         va=(0,0,-1), vo=0,
         rot=0, sx=.5, sy=.5):
    u = f"[ {ua[0]} {ua[1]} {ua[2]} {uo} ]"
    v = f"[ {va[0]} {va[1]} {va[2]} {vo} ]"
    return f"{fv(p1)} {fv(p2)} {fv(p3)} {tex} {u} {v} {rot} {sx} {sy}"

def box_faces(x1,y1,z1, x2,y2,z2, nx,px,ny,py,nz,pz):
    # Each face's 3 vertices must produce an INWARD-pointing normal
    # via (p2-p1)×(p3-p1). TrenchBroom/Quake treats the solid region
    # as the positive half-space (in the direction the normal points).
    return [
        face((x1,y1,z1),(x1,y2,z1),(x1,y1,z2), nx, (0, 1,0),0,(0,0,-1),0),  # x=x1 → normal +X
        face((x2,y2,z2),(x2,y2,z1),(x2,y1,z2), px, (0,-1,0),0,(0,0,-1),0),  # x=x2 → normal -X
        face((x1,y1,z1),(x1,y1,z2),(x2,y1,z1), ny, (-1,0,0),0,(0,0,-1),0),  # y=y1 → normal +Y
        face((x2,y2,z2),(x1,y2,z2),(x2,y2,z1), py, ( 1,0,0),0,(0,0,-1),0),  # y=y2 → normal -Y
        face((x1,y1,z1),(x2,y1,z1),(x1,y2,z1), nz, (-1,0,0),0,(0,-1,0),0),  # z=z1 → normal +Z
        face((x2,y2,z2),(x2,y1,z2),(x1,y2,z2), pz, ( 1,0,0),0,(0,-1,0),0),  # z=z2 → normal -Z
    ]

def write_brush(faces, cmt=""):
    ln = []
    if cmt:
        ln.append(f"// {cmt}")
    ln.append("{")
    ln.extend(faces)
    ln.append("}")
    return "\n".join(ln)

def hollow_box(x1,y1,z1, x2,y2,z2,
               floor_t, ceil_t, wall_t,
               tag="", bi=0, doors=None):
    H   = WALL_T
    hid = HIDDEN_TEX
    ox1,oy1,oz1 = x1-H, y1-H, z1-H
    ox2,oy2,oz2 = x2+H, y2+H, z2+H
    parts = []

    door_map = {}
    if doors:
        for d in doors:
            door_map.setdefault(d['wall'], []).append(d)

    def rb(ax1,ay1,az1, ax2,ay2,az2,
           nx=hid,px=hid,ny=hid,py=hid,nz=hid,pz=hid, lbl=""):
        nonlocal bi
        if ax1 >= ax2 or ay1 >= ay2 or az1 >= az2:
            return
        fs = box_faces(ax1,ay1,az1,ax2,ay2,az2, nx,px,ny,py,nz,pz)
        parts.append(write_brush(fs, f"brush {bi} {tag}_{lbl}"))
        bi += 1

    def wall_y(bx1, bx2, by1, by2, bz1, bz2, wall_name, **face_kw):
        """Wall spanning the Y axis — cut door openings along Y."""
        ds = door_map.get(wall_name)
        if not ds:
            rb(bx1, by1, bz1, bx2, by2, bz2, lbl=wall_name, **face_kw)
            return
        d = ds[0]
        yc = d['center'];  hw = d['hw']
        z_b = d['z_bot'];  z_t = min(z_b + d['ht'], bz2)
        if z_t < bz2:
            rb(bx1, by1,   z_t, bx2, by2,   bz2, lbl=f"{wall_name}_top", **face_kw)
        if yc - hw > by1:
            rb(bx1, by1,   z_b, bx2, yc-hw, z_t,  lbl=f"{wall_name}_l",  **face_kw)
        if yc + hw < by2:
            rb(bx1, yc+hw, z_b, bx2, by2,   z_t,  lbl=f"{wall_name}_r",  **face_kw)

    def wall_x(bx1, bx2, by1, by2, bz1, bz2, wall_name, **face_kw):
        """Wall spanning the X axis — cut door openings along X."""
        ds = door_map.get(wall_name)
        if not ds:
            rb(bx1, by1, bz1, bx2, by2, bz2, lbl=wall_name, **face_kw)
            return
        d = ds[0]
        xc = d['center'];  hw = d['hw']
        z_b = d['z_bot'];  z_t = min(z_b + d['ht'], bz2)
        if z_t < bz2:
            rb(bx1,   by1, z_t, bx2,   by2, bz2,  lbl=f"{wall_name}_top", **face_kw)
        if xc - hw > bx1:
            rb(bx1,   by1, z_b, xc-hw, by2, z_t,  lbl=f"{wall_name}_l",   **face_kw)
        if xc + hw < bx2:
            rb(xc+hw, by1, z_b, bx2,   by2, z_t,  lbl=f"{wall_name}_r",   **face_kw)

    rb(ox1,oy1,oz1, ox2,oy2,z1,  pz=floor_t, lbl="floor")
    rb(ox1,oy1,z2,  ox2,oy2,oz2, nz=ceil_t,  lbl="ceil")
    wall_y(ox1,x1,  y1,y2, z1,z2, 'wx1', px=wall_t)
    wall_y(x2,ox2,  y1,y2, z1,z2, 'wx2', nx=wall_t)
    wall_x(ox1,ox2, oy1,y1, z1,z2, 'wy1', py=wall_t)
    wall_x(ox1,ox2, y2,oy2, z1,z2, 'wy2', ny=wall_t)
    return parts, bi

def corridor_brushes(ax,ay,az, bx,by,bz,
                     axis, floor_t, ceil_t, wall_t,
                     tag="", bi=0):
    H   = WALL_T
    hw  = DOOR_W // 2
    hid = HIDDEN_TEX
    parts = []
    zf = min(az, bz)
    zc = max(az, bz) + DOOR_H

    def cb(ax1,ay1,az1, ax2,ay2,az2,
           nx=hid,px=hid,ny=hid,py=hid,nz=hid,pz=hid, lbl=""):
        nonlocal bi
        fs = box_faces(ax1,ay1,az1,ax2,ay2,az2, nx,px,ny,py,nz,pz)
        parts.append(write_brush(fs, f"brush {bi} {tag}_{lbl}"))
        bi += 1

    if axis == 'x':
        xmn, xmx = min(ax,bx), max(ax,bx)
        cy = (ay + by) // 2
        cb(xmn, cy-hw,   zf-H, xmx, cy+hw,   zf,   pz=floor_t, lbl="fl")
        cb(xmn, cy-hw,   zc,   xmx, cy+hw,   zc+H, nz=ceil_t,  lbl="ce")
        cb(xmn, cy-hw-H, zf,   xmx, cy-hw,   zc,   py=wall_t,  lbl="w1")
        cb(xmn, cy+hw,   zf,   xmx, cy+hw+H, zc,   ny=wall_t,  lbl="w2")
    else:
        cx = (ax + bx) // 2
        ymn, ymx = min(ay,by), max(ay,by)
        cb(cx-hw,   ymn, zf-H, cx+hw,   ymx, zf,   pz=floor_t, lbl="fl")
        cb(cx-hw,   ymn, zc,   cx+hw,   ymx, zc+H, nz=ceil_t,  lbl="ce")
        cb(cx-hw-H, ymn, zf,   cx-hw,   ymx, zc,   px=wall_t,  lbl="w1")
        cb(cx+hw,   ymn, zf,   cx+hw+H, ymx, zc,   nx=wall_t,  lbl="w2")

    return parts, bi

# ══════════════════════════════════════════════════════════════════════════════
#  DATA CLASSES
# ══════════════════════════════════════════════════════════════════════════════
@dataclass
class Room:
    x:int; y:int; z:int
    w:int; d:int; h:int
    idx:int = 0
    floor_t: str = "turnt/turnt_concrete"
    wall_t:  str = "turnt/turnt_tech"
    ceil_t:  str = "turnt/turnt_sky"

    @property
    def x1(self): return self.x
    @property
    def y1(self): return self.y
    @property
    def z1(self): return self.z
    @property
    def x2(self): return self.x + self.w
    @property
    def y2(self): return self.y + self.d
    @property
    def z2(self): return self.z + self.h
    def cx(self): return (self.x1 + self.x2) // 2
    def cy(self): return (self.y1 + self.y2) // 2

@dataclass
class Bridge:
    room_a: int; room_b: int
    axis: str
    ax:int; ay:int; az:int
    bx:int; by:int; bz:int
    floor_t: str = "turnt/turnt_asphalt"
    wall_t:  str = "turnt/turnt_concrete"
    ceil_t:  str = "turnt/turnt_sky"

# ══════════════════════════════════════════════════════════════════════════════
#  LAYOUT ENGINE
# ══════════════════════════════════════════════════════════════════════════════
def _snap(v, grid=64):
    return round(v / grid) * grid

def place_rooms(n, cfg) -> List[Room]:
    rooms: List[Room] = []
    cx, cy, cz = 0, 0, 0
    direction = 'x'

    for i in range(n):
        w = _snap(random.randint(cfg["min_w"], cfg["max_w"]))
        d = _snap(random.randint(cfg["min_d"], cfg["max_d"]))
        h = _snap(random.randint(cfg["min_h"], cfg["max_h"]))

        if i > 0 and cfg.get("height_var", True):
            cz = _snap(cz + random.choice([0,0,0,32,64,96,-32,-64]), 32)

        r = Room(x=cx, y=cy, z=cz, w=w, d=d, h=h, idx=i,
                 floor_t=random.choice(FLOOR_TEX),
                 wall_t =random.choice(WALL_TEX),
                 ceil_t =random.choice(CEIL_TEX))
        rooms.append(r)

        gap_min, gap_max = cfg.get("gap_range", (-128, 384))
        gap = _snap(random.randint(gap_min, gap_max))
        # Prevent rooms from completely swallowing each other
        gap = max(gap, -(min(w, d) // 2))

        if direction == 'x':
            cx += w + gap
        else:
            cy += d + gap

        if (i + 1) % 2 == 0:
            direction = 'y' if direction == 'x' else 'x'

    return rooms






























def _pick_overlap_center(a1: int, a2: int, b1: int, b2: int, door_w: int) -> Optional[int]:
    lo = max(a1, b1)
    hi = min(a2, b2)
    if hi - lo < door_w:
        return None

    center = _snap((lo + hi) // 2)
    half = door_w // 2
    center = max(lo + half, min(hi - half, center))
    return center


def build_bridges(rooms: List[Room]) -> List[Bridge]:
    bridges: List[Bridge] = []

    for i in range(len(rooms) - 1):
        a, b = rooms[i], rooms[i + 1]
        br: Optional[Bridge] = None

        if b.x1 >= a.x2:
            y_center = _pick_overlap_center(a.y1, a.y2, b.y1, b.y2, DOOR_W)
            if y_center is not None:
                br = Bridge(i, i + 1, 'x',
                            a.x2, y_center, a.z1,
                            b.x1, y_center, b.z1,
                            floor_t=random.choice(FLOOR_TEX),
                            wall_t=random.choice(WALL_TEX),
                            ceil_t=random.choice(CEIL_TEX))
        elif a.x1 >= b.x2:
            y_center = _pick_overlap_center(a.y1, a.y2, b.y1, b.y2, DOOR_W)
            if y_center is not None:
                br = Bridge(i, i + 1, 'x',
                            a.x1, y_center, a.z1,
                            b.x2, y_center, b.z1,
                            floor_t=random.choice(FLOOR_TEX),
                            wall_t=random.choice(WALL_TEX),
                            ceil_t=random.choice(CEIL_TEX))
        elif b.y1 >= a.y2:
            x_center = _pick_overlap_center(a.x1, a.x2, b.x1, b.x2, DOOR_W)
            if x_center is not None:
                br = Bridge(i, i + 1, 'y',
                            x_center, a.y2, a.z1,
                            x_center, b.y1, b.z1,
                            floor_t=random.choice(FLOOR_TEX),
                            wall_t=random.choice(WALL_TEX),
                            ceil_t=random.choice(CEIL_TEX))
        elif a.y1 >= b.y2:
            x_center = _pick_overlap_center(a.x1, a.x2, b.x1, b.x2, DOOR_W)
            if x_center is not None:
                br = Bridge(i, i + 1, 'y',
                            x_center, a.y1, a.z1,
                            x_center, b.y2, b.z1,
                            floor_t=random.choice(FLOOR_TEX),
                            wall_t=random.choice(WALL_TEX),
                            ceil_t=random.choice(CEIL_TEX))

        if br is not None:
            bridges.append(br)

    return bridges

# ══════════════════════════════════════════════════════════════════════════════
#  ENTITIES
# ══════════════════════════════════════════════════════════════════════════════
def ent_kv(**kv):
    lines = ["{"]
    for k, v in kv.items():
        lines.append(f'"{k}" "{v}"')
    lines.append("}")
    return "\n".join(lines)

def ent_brush_box(cls, x1,y1,z1, x2,y2,z2, target="", extra=None):
    fs = box_faces(x1,y1,z1, x2,y2,z2,
                   NODRAW_TEX, NODRAW_TEX, NODRAW_TEX,
                   NODRAW_TEX, NODRAW_TEX, NODRAW_TEX)
    br = write_brush(fs)
    kv = {"classname": cls}
    if target: kv["target"] = target
    if extra:  kv.update(extra)
    lines = ["{"]
    for k, v in kv.items():
        lines.append(f'"{k}" "{v}"')
    lines.append(br)
    lines.append("}")
    return "\n".join(lines)

# ══════════════════════════════════════════════════════════════════════════════
#  MAIN GENERATOR
# ══════════════════════════════════════════════════════════════════════════════
def generate_map(cfg: dict):
    seed = cfg.get("seed")
    if seed is not None:
        random.seed(seed)

    rooms   = place_rooms(cfg["n_rooms"], cfg)
    bridges = build_bridges(rooms)

    lines = [
        "// Game: Quake 3",
        "// Format: Valve",
        f"// Generated by Turnt-o-mator | rooms={cfg['n_rooms']} seed={seed}",
        "// entity 0",
        "{",
        '"mapversion" "220"',
        '"classname" "worldspawn"',
        '"_ambient" "15"',
        f'"message" "{cfg.get("map_name","turnt_map")}"',
    ]

    bi = 0
    # Build per-room door cutout data from bridges
    _hw = DOOR_W // 2
    room_doors: Dict[int, list] = {i: [] for i in range(len(rooms))}
    for br in bridges:
        ra  = rooms[br.room_a]
        rb2 = rooms[br.room_b]
        if br.axis == 'x':
            room_doors[br.room_a].append(
                {'wall':'wx2','center':br.ay,'hw':_hw,'ht':DOOR_H,'z_bot':ra.z1})
            room_doors[br.room_b].append(
                {'wall':'wx1','center':br.ay,'hw':_hw,'ht':DOOR_H,'z_bot':rb2.z1})
        else:
            room_doors[br.room_a].append(
                {'wall':'wy2','center':br.ax,'hw':_hw,'ht':DOOR_H,'z_bot':ra.z1})
            room_doors[br.room_b].append(
                {'wall':'wy1','center':br.ax,'hw':_hw,'ht':DOOR_H,'z_bot':rb2.z1})

    for room in rooms:
        parts, bi = hollow_box(room.x1, room.y1, room.z1,
                               room.x2, room.y2, room.z2,
                               room.floor_t, room.ceil_t, room.wall_t,
                               tag=f"r{room.idx}", bi=bi,
                               doors=room_doors.get(room.idx))
        lines.extend(parts)

    for br in bridges:
        parts, bi = corridor_brushes(
            br.ax, br.ay, br.az,
            br.bx, br.by, br.bz,
            br.axis, br.floor_t, br.ceil_t, br.wall_t,
            tag=f"br{br.room_a}_{br.room_b}", bi=bi)
        lines.extend(parts)

    lines.append("}")  # end worldspawn

    ei    = 1
    first = rooms[0]
    last  = rooms[-1]
    hw    = DOOR_W // 2

    lines.append(f"\n// entity {ei}")
    lines.append(ent_kv(classname="info_player_start",
                        origin=f"{first.cx()} {first.cy()} {first.z1+32}",
                        angle="0"))
    ei += 1

    lines.append(f"\n// entity {ei}")
    lines.append(ent_brush_box("trigger_multiple",
        first.x1, first.cy()-hw, first.z1,
        first.x1+32, first.cy()+hw, first.z1+DOOR_H,
        target="start_t"))
    ei += 1

    lines.append(f"\n// entity {ei}")
    lines.append(ent_kv(classname="target_startTimer",
                        origin=f"{first.x1+16} {first.cy()} {first.z1+64}",
                        targetname="start_t"))
    ei += 1

    lines.append(f"\n// entity {ei}")
    lines.append(ent_brush_box("trigger_multiple",
        last.x2-32, last.cy()-hw, last.z1,
        last.x2,    last.cy()+hw, last.z1+DOOR_H,
        target="stop_t"))
    ei += 1

    lines.append(f"\n// entity {ei}")
    lines.append(ent_kv(classname="target_stopTimer",
                        origin=f"{last.x2-16} {last.cy()} {last.z1+64}",
                        targetname="stop_t"))
    ei += 1

    if cfg.get("checkpoints", True):
        for room in rooms[1:]:
            cx, cy = room.cx(), room.cy()
            fs = box_faces(cx-64, cy-64, room.z1,
                           cx+64, cy+64, room.z1+2,
                           HIDDEN_TEX, HIDDEN_TEX, HIDDEN_TEX,
                           HIDDEN_TEX, HIDDEN_TEX, "turnt/turnt_checkpoint")
            lines.append(f"\n// entity {ei}")
            lines.append('{\n"classname" "func_static"\n' +
                         write_brush(fs) + "\n}")
            ei += 1

    return "\n".join(lines), rooms, bridges

# ══════════════════════════════════════════════════════════════════════════════
#  GUI
# ══════════════════════════════════════════════════════════════════════════════
IMG_EXTS = {".jpg",".jpeg",".png",".bmp",".tga",".gif",".tiff"}

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Turnt-o-mator")
        self.configure(bg=T["bg"])
        self.minsize(1200, 750)
        self.resizable(True, True)

        self._map_str   = ""
        self._rooms:   List[Room]   = []
        self._bridges: List[Bridge] = []

        self._tex_folder = tk.StringVar(value="")
        self._out_path   = tk.StringVar(
            value=os.path.join(os.getcwd(), "generated.map"))
        self._tex_paths: Dict[str, str]    = {}   # tex_name → abs file path
        self._thumb_refs: Dict[str, object] = {}  # keep ImageTk alive

        # per-texture category BooleanVars  {tex_name: BooleanVar}
        self._floor_sel: Dict[str, tk.BooleanVar] = {}
        self._wall_sel:  Dict[str, tk.BooleanVar] = {}
        self._ceil_sel:  Dict[str, tk.BooleanVar] = {}

        self._build_styles()
        self._build_ui()
        self._randomize_seed(silent=True)
        self._log("Turnt-o-mator ready. Configure and hit Generate!", "info")

    # ── styles ────────────────────────────────────────────────────────────────
    def _build_styles(self):
        s = ttk.Style(self)
        s.theme_use("clam")
        bg  = T["bg"];      bgp = T["bg_panel"]; bgc = T["bg_card"]
        acc = T["accent"];  txt = T["text"];      dim = T["text_dim"]
        brd = T["border"]

        s.configure(".",              background=bg,  foreground=txt,
                    font=("Segoe UI", 10))
        s.configure("TFrame",         background=bg)
        s.configure("P.TFrame",       background=bgp)
        s.configure("C.TFrame",       background=bgc)
        s.configure("TLabel",         background=bg,  foreground=txt)
        s.configure("P.TLabel",       background=bgp, foreground=txt)
        s.configure("Pd.TLabel",      background=bgp, foreground=dim)   # dim on panel
        s.configure("C.TLabel",       background=bgc, foreground=txt)


                s.configure("H1.TLabel",      background=bg,  foreground=acc,
                    font=("Segoe UI", 22, "bold"))
        s.configure("H2.TLabel",      background=bgp, foreground=acc,
                    font=("Segoe UI", 10, "bold"))
        s.configure("H3.TLabel",      background=bgc, foreground=acc,
                    font=("Segoe UI",  9, "bold"))
        s.configure("TNotebook",      background=bg,  borderwidth=0)


                s.configure("TNotebook.Tab",  background=bgp, foreground=dim,
                    padding=[14, 7],  font=("Segoe UI", 9, "bold"))
        s.map("TNotebook.Tab",
              background=[("selected", bgc)],
              foreground=[("selected", acc)])


                s.configure("TCheckbutton",   background=bgp, foreground=txt,
                    indicatorcolor=bgc, font=("Segoe UI", 9))
        s.map("TCheckbutton",
              indicatorcolor=[("selected", acc)])
        s.configure("TScale",         background=bgp,
                    troughcolor=T["bg_input"],
                    sliderthickness=13, sliderrelief="flat")
        s.configure("TEntry",         fieldbackground=T["bg_input"],
                    foreground=txt, insertcolor=txt,
                    bordercolor=brd, relief="flat", padding=5)
        s.configure("TSeparator",     background=brd)
        s.configure("Vertical.TScrollbar",
                    background=brd, troughcolor=bg,
                    bordercolor=bg, arrowcolor=dim, relief="flat")
        s.configure("Horizontal.TScrollbar",
                    background=brd, troughcolor=bg,
                    bordercolor=bg, arrowcolor=dim, relief="flat")

    # ── master layout ─────────────────────────────────────────────────────────
    def _build_ui(self):
        # Header
        hdr = tk.Frame(self, bg=T["bg_panel"])
        hdr.pack(fill="x")
        tk.Frame(hdr, bg=T["accent"], height=3).pack(fill="x")
        hdr_inner = tk.Frame(hdr, bg=T["bg_panel"], pady=12)
        hdr_inner.pack(fill="x", padx=18)
        tk.Label(hdr_inner, text="TURNT-O-MATOR",
                 bg=T["bg_panel"], fg=T["text"],
                 font=("Segoe UI", 20, "bold")).pack(side="left")
        tk.Frame(hdr_inner, bg=T["accent"], width=2).pack(
            side="left", fill="y", padx=12, pady=2)
        tk.Label(hdr_inner, text="Quake 3 · Turnt Defrag Map Generator",
                 bg=T["bg_panel"], fg=T["text_dim"],
                 font=("Segoe UI", 9)).pack(side="left")

        body = ttk.Frame(self)


                body.pack(fill="both", expand=True, padx=12, pady=(8, 8))
        body.columnconfigure(0, weight=0, minsize=410)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        left = ttk.Frame(body, style="P.TFrame", padding=(10, 10))
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        self._build_left(left)

        right = ttk.Frame(body)
        right.grid(row=0, column=1, sticky="nsew")
        right.rowconfigure(0, weight=3)
        right.rowconfigure(1, weight=1)
        right.columnconfigure(0, weight=1)
        self._build_right(right)

        self._status = tk.Label(self, text="Ready", anchor="w", padx=10,
                                bg=T["bg_panel"], fg=T["text_dim"],
                                font=("Segoe UI", 8))
        self._status.pack(fill="x", side="bottom")

    # ── LEFT PANEL ────────────────────────────────────────────────────────────
    def _build_left(self, p):
        nb = ttk.Notebook(p)
        nb.pack(fill="both", expand=True)

        t1 = ttk.Frame(nb, style="P.TFrame", padding=8)
        t2 = ttk.Frame(nb, style="P.TFrame", padding=8)
        t3 = ttk.Frame(nb, style="P.TFrame", padding=8)
        nb.add(t1, text="  Layout  ")
        nb.add(t2, text="  Textures  ")
        nb.add(t3, text="  Options  ")

        self._tab_layout(t1)
        self._tab_textures(t2)
        self._tab_options(t3)

        # Output file
        ttk.Separator(p).pack(fill="x", pady=(10, 6))
        ttk.Label(p, text="Output file", style="P.TLabel",
                  font=("Segoe UI", 8, "bold")).pack(anchor="w")
        row = ttk.Frame(p, style="P.TFrame")
        row.pack(fill="x", pady=(3, 0))
        ttk.Entry(row, textvariable=self._out_path,
                  font=("Consolas", 8)).pack(side="left", fill="x", expand=True)
        self._btn(row, "📁", self._browse_out, w=3,
                  color=T["accent2"]).pack(side="left", padx=(4, 0))

        # Action buttons
        bf = ttk.Frame(p, style="P.TFrame")
        bf.pack(fill="x", pady=(10, 0))
        self._btn(bf, "⚡  GENERATE", self._on_generate,
                  color=T["accent"],
                  font=("Segoe UI", 11, "bold")).pack(fill="x", pady=(0, 6))
        r2 = ttk.Frame(bf, style="P.TFrame")
        r2.pack(fill="x")
        self._btn(r2, "💾  Save", self._on_save,
                  color=T["success"]).pack(side="left", fill="x",
                                           expand=True, padx=(0, 4))
        self._btn(r2, "🎲  New Seed", self._randomize_seed,
                  color=T["accent2"]).pack(side="left", fill="x", expand=True)

    # ─ Tab: Layout ─────────────────────────────────────────────────────
    def _tab_layout(self, p):
        self._v_rooms = tk.IntVar(value=6)
        self._slider(p, "Number of rooms", self._v_rooms, 2, 30)

        self._sec(p, "Room size (qu)")
        g = ttk.Frame(p, style="P.TFrame")
        g.pack(fill="x", pady=(0, 6))
        labels  = ["Min W", "Max W", "Min D", "Max D", "Min H", "Max H"]
        defvals = [ 192,     640,     192,     640,     128,     320]
        self._sz: Dict[str, tk.IntVar] = {}
        for i, (lbl, val) in enumerate(zip(labels, defvals)):
            r, c = divmod(i, 2)
            f = ttk.Frame(g, style="P.TFrame")
            f.grid(row=r, column=c, padx=3, pady=2, sticky="ew")
            g.columnconfigure(c, weight=1)
            ttk.Label(f, text=lbl, style="P.TLabel",
                      font=("Segoe UI", 7)).pack(anchor="w")
            v = tk.IntVar(value=val)
            self._sz[lbl] = v
            self._spinbox(f, v, 64, 4096, 64)

        self._sec(p, "Gap between rooms (qu)")
        gf = ttk.Frame(p, style="P.TFrame")
        gf.pack(fill="x", pady=(0, 2))
        gfl = ttk.Frame(gf, style="P.TFrame")
        gfl.pack(side="left", fill="x", expand=True, padx=(0, 4))
        gfr = ttk.Frame(gf, style="P.TFrame")
        gfr.pack(side="left", fill="x", expand=True)
        ttk.Label(gfl, text="Min gap", style="P.TLabel",
                  font=("Segoe UI", 7)).pack(anchor="w")
        ttk.Label(gfr, text="Max gap", style="P.TLabel",
                  font=("Segoe UI", 7)).pack(anchor="w")
        self._v_gap_min = tk.IntVar(value=-128)
        self._v_gap_max = tk.IntVar(value=384)
        self._spinbox(gfl, self._v_gap_min, -1024, 4096, 64)
        self._spinbox(gfr, self._v_gap_max, -1024, 4096, 64)

        # ← use tk.Label, not ttk.Label, so fg works
        tk.Label(p,
                 text="Negative = overlap  |  0 = touching  |  Positive = gap",
                 bg=T["bg_panel"], fg=T["text_dim"],
                 font=("Segoe UI", 7)).pack(anchor="w", pady=(2, 8))

        self._sec(p, "Seed")
        sr = ttk.Frame(p, style="P.TFrame")
        sr.pack(fill="x", pady=(0, 6))
        self._v_seed_lock = tk.BooleanVar(value=False)
        ttk.Checkbutton(sr, text="Lock seed",
                        variable=self._v_seed_lock,
                        command=self._toggle_seed).pack(side="left")
        self._v_seed = tk.IntVar(value=0)
        self._seed_spin = self._spinbox(sr, self._v_seed,
                                        0, 9_999_999, 1,
                                        state="disabled", pack=False)
        self._seed_spin.pack(side="left", padx=(8, 0))

        self._sec(p, "Map name")
        self._v_mapname = tk.StringVar(value="turnt_run")
        ttk.Entry(p, textvariable=self._v_mapname,
                  font=("Consolas", 9)).pack(fill="x", pady=(0, 4))

    # ─ Tab: Textures ──────────────────────────────────────────────────
    def _tab_textures(self, p):
        self._sec(p, "Texture folder (optional)")
        fr = ttk.Frame(p, style="P.TFrame")
        fr.pack(fill="x", pady=(0, 2))
        ttk.Entry(fr, textvariable=self._tex_folder,
                  font=("Consolas", 7)).pack(side="left", fill="x", expand=True)
        self._btn(fr, "📂", self._browse_tex_folder, w=3,
                  color=T["accent2"]).pack(side="left", padx=(3, 0))

        tk.Label(p,
                 text="F = use as Floor   W = Wall   C = Ceiling",
                 bg=T["bg_panel"], fg=T["text_dim"],
                 font=("Segoe UI", 7)).pack(anchor="w", pady=(0, 4))

        # ── Outer split: list (left) | big preview (right)
        outer = ttk.Frame(p, style="P.TFrame")
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=1)
        outer.columnconfigure(1, weight=0)
        outer.rowconfigure(0, weight=1)

        # ── Scrollable checklist
        list_f = ttk.Frame(outer, style="P.TFrame")
        list_f.grid(row=0, column=0, sticky="nsew")
        list_f.rowconfigure(0, weight=1)
        list_f.columnconfigure(0, weight=1)

        self._tex_canvas = tk.Canvas(list_f, bg=T["lbx_bg"],
                                     highlightthickness=0)
        vsb = ttk.Scrollbar(list_f, orient="vertical",
                            command=self._tex_canvas.yview)
        self._tex_canvas.configure(yscrollcommand=vsb.set)
        vsb.grid(row=0, column=1, sticky="ns")
        self._tex_canvas.grid(row=0, column=0, sticky="nsew")

        self._tex_inner = tk.Frame(self._tex_canvas, bg=T["lbx_bg"])
        self._tex_canvas_win = self._tex_canvas.create_window(
            (0, 0), window=self._tex_inner, anchor="nw")

        self._tex_inner.bind("<Configure>",
            lambda e: self._tex_canvas.configure(
                scrollregion=self._tex_canvas.bbox("all")))
        self._tex_canvas.bind("<Configure>",
            lambda e: self._tex_canvas.itemconfig(
                self._tex_canvas_win, width=e.width))
        for seq in ("<MouseWheel>","<Button-4>","<Button-5>"):
            self._tex_canvas.bind(seq, self._on_tex_scroll)

        # ── Big preview pane
        prev_f = tk.Frame(outer, bg=T["bg_card"], padx=6, pady=6)
        prev_f.grid(row=0, column=1, sticky="nsew", padx=(6, 0))

        tk.Label(prev_f, text="Preview",
                 bg=T["bg_card"], fg=T["accent"],
                 font=("Segoe UI", 9, "bold")).pack()
        self._prev_lbl = tk.Label(prev_f, bg=T["bg_card"],
                                  width=16, height=8,
                                  text="—", fg=T["text_dim"],
                                  font=("Segoe UI", 8))
        self._prev_lbl.pack(pady=4)
        self._prev_name = tk.Label(prev_f, bg=T["bg_card"],
                                   fg=T["text_dim"],
                                   font=("Consolas", 6),
                                   wraplength=120, text="")
        self._prev_name.pack()

        self._populate_tex_list()

    def _on_tex_scroll(self, e):
        if e.num == 4:
            self._tex_canvas.yview_scroll(-1, "units")
        elif e.num == 5:
            self._tex_canvas.yview_scroll(1, "units")
        else:
            self._tex_canvas.yview_scroll(-1*(e.delta//120), "units")

    def _populate_tex_list(self):
        for w in self._tex_inner.winfo_children():
            w.destroy()

        # Initialise BooleanVars (only once)
        for tex in ALL_TEXTURES:
            self._floor_sel.setdefault(tex, tk.BooleanVar(value=(tex in FLOOR_TEX)))
            self._wall_sel.setdefault( tex, tk.BooleanVar(value=(tex in WALL_TEX)))
            self._ceil_sel.setdefault( tex, tk.BooleanVar(value=(tex in CEIL_TEX)))

        for tex_name in sorted(ALL_TEXTURES.keys()):
            row = tk.Frame(self._tex_inner, bg=T["lbx_bg"])
            row.pack(fill="x")

            # Thumbnail placeholder
            thumb = tk.Label(row, bg=T["lbx_bg"],
                             width=2, height=1, text=" ")
            thumb.pack(side="left")
            self._load_thumb(tex_name, thumb, size=16)

            # Name — click → big preview
            name_btn = tk.Button(
                row, text=tex_name,
                bg=T["lbx_bg"], fg=T["text"],
                font=("Consolas", 7), relief="flat",
                anchor="w", cursor="hand2",
                activebackground=T["lbx_sel"],
                activeforeground=T["accent"],
                command=lambda t=tex_name: self._show_tex_preview(t))
            name_btn.pack(side="left", fill="x", expand=True)

            # F / W / C checkboxes
            for label, color, sel_dict in [
                ("F", T["success"],  self._floor_sel),
                ("W", T["accent2"],  self._wall_sel),
                ("C", T["accent"],   self._ceil_sel),
            ]:
                ck = tk.Checkbutton(
                    row, text=label,
                    variable=sel_dict[tex_name],
                    bg=T["lbx_bg"], fg=color,
                    selectcolor=T["bg_card"],
                    activebackground=T["lbx_bg"],
                    font=("Segoe UI", 7),
                    relief="flat", cursor="hand2",
                    command=self._update_tex_lists)
                ck.pack(side="left")

    def _load_thumb(self, tex_name, lbl, size=16):
        if not PIL_OK:
            return
        path = self._tex_paths.get(tex_name) or self._find_tex_file(tex_name)
        if not path:
            return
        try:
            img = Image.open(path).convert("RGBA")
            img.thumbnail((size, size))
            tk_img = ImageTk.PhotoImage(img)
            lbl.config(image=tk_img, text="", width=size)
            self._thumb_refs[f"{tex_name}_{size}"] = tk_img
        except Exception:
            pass

    def _find_tex_file(self, tex_name) -> Optional[str]:
        folder = self._tex_folder.get()
        if not folder or not os.path.isdir(folder):
            return None
        base = tex_name.split("/")[-1]
        for root_d, _, files in os.walk(folder):
            for fn in files:
                nm, ext = os.path.splitext(fn)
                if nm.lower() == base.lower() and ext.lower() in IMG_EXTS:
                    fp = os.path.join(root_d, fn)
                    self._tex_paths[tex_name] = fp
                    return fp
        return None

    def _show_tex_preview(self, tex_name):
        self._prev_name.config(text=tex_name)
        if not PIL_OK:
            self._prev_lbl.config(image="",
                                  text="pip install pillow",
                                  fg=T["warning"])
            return
        path = self._tex_paths.get(tex_name) or self._find_tex_file(tex_name)
        if not path:
            self._prev_lbl.config(image="",
                                  text="No image\n(set folder)",
                                  fg=T["text_dim"])
            return
        try:
            img = Image.open(path).convert("RGBA")
            img.thumbnail((128, 128))
            tk_img = ImageTk.PhotoImage(img)
            self._prev_lbl.config(image=tk_img, text="",
                                  width=128, height=128)
            self._thumb_refs["preview"] = tk_img
        except Exception as ex:
            self._prev_lbl.config(image="", text=f"Error:\n{ex}",
                                  fg=T["warning"])

    def _browse_tex_folder(self):
        d = filedialog.askdirectory(title="Select texture folder")
        if d:
            self._tex_folder.set(d)
            self._tex_paths.clear()
            self._status.config(text="Scanning texture folder…")
            threading.Thread(target=self._scan_tex_folder,
                             args=(d,), daemon=True).start()

    def _scan_tex_folder(self, folder):
        found = {}
        for root_d, _, files in os.walk(folder):
            for fn in files:
                nm, ext = os.path.splitext(fn)
                if ext.lower() not in IMG_EXTS:
                    continue
                for tex in ALL_TEXTURES:
                    base = tex.split("/")[-1]
                    if nm.lower() == base.lower():
                        found[tex] = os.path.join(root_d, fn)
        self._tex_paths.update(found)
        self.after(0, lambda: self._status.config(
            text=f"Scan complete — {len(found)} textures matched"))
        self.after(0, self._refresh_thumbs)

    def _refresh_thumbs(self):
        if not PIL_OK:
            return
        for row in self._tex_inner.winfo_children():
            ch = row.winfo_children()
            if len(ch) < 2:
                continue
            thumb_lbl = ch[0]
            name_btn  = ch[1]
            tex_name  = name_btn.cget("text")
            if tex_name in ALL_TEXTURES:
                self._load_thumb(tex_name, thumb_lbl, size=16)

    def _update_tex_lists(self):
        FLOOR_TEX.clear()
        FLOOR_TEX.extend([t for t,v in self._floor_sel.items() if v.get()])
        WALL_TEX.clear()
        WALL_TEX.extend([t for t,v in self._wall_sel.items()  if v.get()])
        CEIL_TEX.clear()
        CEIL_TEX.extend([t for t,v in self._ceil_sel.items()  if v.get()])
        if not FLOOR_TEX: FLOOR_TEX.append("turnt/turnt_concrete")
        if not WALL_TEX:  WALL_TEX.append("turnt/turnt_tech")
        if not CEIL_TEX:  CEIL_TEX.append("turnt/turnt_sky")

    # ─ Tab: Options ────────────────────────────────────────────────────
    def _tab_options(self, p):
        self._sec(p, "Geometry")
        self._v_height   = tk.BooleanVar(value=True)
        self._v_checks   = tk.BooleanVar(value=True)
        self._v_autorand = tk.BooleanVar(value=True)
        for text, var in [
            ("Height variation between rooms", self._v_height),
            ("Add checkpoint pads",            self._v_checks),
            ("Auto-randomize seed after each generation", self._v_autorand),
        ]:
            ttk.Checkbutton(p, text=text, variable=var).pack(anchor="w", pady=2)

        self._sec(p, "Door size (qu)")
        g = ttk.Frame(p, style="P.TFrame")
        g.pack(fill="x", pady=(0, 8))
        for i, (lbl, val, attr) in enumerate([
            ("Door width",  128, "_v_door_w"),
            ("Door height", 128, "_v_door_h"),
        ]):
            f = ttk.Frame(g, style="P.TFrame")
            f.grid(row=0, column=i, padx=4, sticky="ew")
            g.columnconfigure(i, weight=1)
            ttk.Label(f, text=lbl, style="P.TLabel",
                      font=("Segoe UI", 7)).pack(anchor="w")
            v = tk.IntVar(value=val)
            setattr(self, attr, v)
            self._spinbox(f, v, 32, 512, 32)

        self._sec(p, "Preview legend")
        for color, label in [
            (T["start_col"], "Start room"),
            (T["room_col"],  "Mid rooms"),
            (T["end_col"],   "End room"),
            (T["corr_col"],  "Corridor / bridge"),
        ]:
            row = tk.Frame(p, bg=T["bg_panel"])
            row.pack(anchor="w", pady=1)
            tk.Label(row, bg=color, width=2,
                     relief="flat").pack(side="left")
            tk.Label(row, text=f"  {label}",
                     bg=T["bg_panel"], fg=T["text"],
                     font=("Segoe UI", 8)).pack(side="left")

    # ── RIGHT PANEL ───────────────────────────────────────────────────────────
    def _build_right(self, p):
        # Preview
        pc = ttk.Frame(p, style="P.TFrame")
        pc.grid(row=0, column=0, sticky="nsew", pady=(0, 6))
        pc.rowconfigure(1, weight=1)
        pc.columnconfigure(0, weight=1)

        ph = ttk.Frame(pc, style="P.TFrame", padding=(10, 6))
        ph.grid(row=0, column=0, sticky="ew")
        ttk.Label(ph, text="MAP PREVIEW", style="H2.TLabel").pack(side="left")
        self._lbl_stats = ttk.Label(ph, text="", style="Pd.TLabel",
                                    font=("Segoe UI", 8))
        self._lbl_stats.pack(side="right")

        self._canvas = tk.Canvas(pc, bg=T["prev_bg"],
                                 highlightthickness=1,
                                 highlightbackground=T["border"])
        self._canvas.grid(row=1, column=0, sticky="nsew", padx=6, pady=(0, 6))
        self._canvas.bind("<Configure>", lambda e: self._redraw())

        # Log
        lc = ttk.Frame(p, style="P.TFrame")
        lc.grid(row=1, column=0, sticky="nsew")
        lc.rowconfigure(1, weight=1)
        lc.columnconfigure(0, weight=1)

        lh = ttk.Frame(lc, style="P.TFrame", padding=(10, 5))
        lh.grid(row=0, column=0, sticky="ew")
        ttk.Label(lh, text="LOG", style="H2.TLabel").pack(side="left")
        self._btn(lh, "Clear", self._clear_log,
                  color=T["accent2"],
                  font=("Segoe UI", 8), pady=2).pack(side="right")

        self._logbox = scrolledtext.ScrolledText(
            lc, height=7,
            bg=T["bg_input"], fg=T["text_dim"],
            font=("Consolas", 9), relief="flat",
            insertbackground=T["text"],
            wrap="word", state="disabled", borderwidth=0)
        self._logbox.grid(row=1, column=0, sticky="nsew",
                          padx=6, pady=(0, 6))
        self._logbox.tag_config("info",  foreground=T["success"])
        self._logbox.tag_config("warn",  foreground=T["warning"])
        self._logbox.tag_config("error", foreground=T["accent"])

    # ── UI helpers ────────────────────────────────────────────────────────────
    def _btn(self, parent, text, cmd,
             color=None, font=None, w=None, pady=6):
        color = color or T["accent"]
        font  = font  or ("Segoe UI", 10, "bold")
        kw = dict(text=text, command=cmd,
                  bg=color, fg=T["btn_fg"],
                  activebackground=color,
                  activeforeground=T["btn_fg"],
                  relief="flat", cursor="hand2",
                  font=font, padx=12, pady=pady, bd=0)
        if w:
            kw["width"] = w
        b = tk.Button(parent, **kw)
        lit = self._lighten(color, .18)
        b.bind("<Enter>", lambda e: b.config(bg=lit))
        b.bind("<Leave>", lambda e: b.config(bg=color))
        return b

    @staticmethod
    def _lighten(hx, f):
        hx = hx.lstrip("#")
        r, g, b = (int(hx[i:i+2], 16) for i in (0, 2, 4))
        return "#{:02x}{:02x}{:02x}".format(
            min(255, int(r+(255-r)*f)),
            min(255, int(g+(255-g)*f)),
            min(255, int(b+(255-b)*f)))

    def _sec(self, p, text):
        f = ttk.Frame(p, style="P.TFrame")
        f.pack(fill="x", pady=(8, 3))
        ttk.Label(f, text=text, style="H2.TLabel").pack(side="left")
        ttk.Separator(f, orient="horizontal").pack(
            side="left", fill="x", expand=True, padx=(8, 0))

    def _slider(self, p, label, var, lo, hi, step=1):
        row = ttk.Frame(p, style="P.TFrame")
        row.pack(fill="x", pady=(0, 2))
        ttk.Label(row, text=label, style="P.TLabel",
                  font=("Segoe UI", 9)).pack(side="left")
        vl = ttk.Label(row, text=str(var.get()), style="P.TLabel",
                       foreground=T["accent"],
                       font=("Consolas", 9, "bold"))
        vl.pack(side="right")

        def ch(v):
            sv = round(float(v)/step)*step
            var.set(int(sv))
            vl.config(text=str(sv))

        ttk.Scale(p, from_=lo, to=hi, variable=var,
                  orient="horizontal", command=ch).pack(fill="x", pady=(0, 8))

    def _spinbox(self, parent, var, lo, hi, inc,
                 state="normal", pack=True):
        sb = tk.Spinbox(
            parent, textvariable=var,
            from_=lo, to=hi, increment=inc, width=8,
            bg=T["bg_input"], fg=T["text"],
            insertbackground=T["text"],
            relief="flat", font=("Consolas", 9),
            buttonbackground=T["bg_card"],
            state=state,
            disabledforeground=T["text_dim"],
            disabledbackground=T["bg_input"])
        if pack:
            sb.pack(fill="x")
        return sb

    def _toggle_seed(self):
        st = "normal" if self._v_seed_lock.get() else "disabled"
        self._seed_spin.config(state=st)

    def _randomize_seed(self, silent=False):
        s = random.randint(0, 9_999_999)
        self._v_seed.set(s)
        if not silent:
            self._log(f"Seed → {s}", "info")

    def _browse_out(self):
        p = filedialog.asksaveasfilename(
            defaultextension=".map",
            filetypes=[("Quake Map", "*.map"), ("All", "*.*")],
            initialfile=os.path.basename(self._out_path.get()))
        if p:
            self._out_path.set(p)

    def _log(self, msg, level="plain"):
        self._logbox.config(state="normal")
        pfx = {"info":"[OK] ","warn":"[!!] ","error":"[ERR] "}.get(level,"")
        self._logbox.insert("end", pfx+msg+"\n", level)
        self._logbox.see("end")
        self._logbox.config(state="disabled")
        self._status.config(text=msg)

    def _clear_log(self):
        self._logbox.config(state="normal")
        self._logbox.delete("1.0", "end")
        self._logbox.config(state="disabled")

    # ── Generation ────────────────────────────────────────────────────────────
    def _collect_cfg(self) -> dict:
        self._update_tex_lists()
        global DOOR_W, DOOR_H
        DOOR_W = self._v_door_w.get()
        DOOR_H = self._v_door_h.get()
        return {
            "n_rooms":     self._v_rooms.get(),
            "min_w":       self._sz["Min W"].get(),
            "max_w":       self._sz["Max W"].get(),
            "min_d":       self._sz["Min D"].get(),
            "max_d":       self._sz["Max D"].get(),
            "min_h":       self._sz["Min H"].get(),
            "max_h":       self._sz["Max H"].get(),
            "gap_range":   (self._v_gap_min.get(), self._v_gap_max.get()),
            "seed":        self._v_seed.get(),
            "map_name":    self._v_mapname.get(),
            "height_var":  self._v_height.get(),
            "checkpoints": self._v_checks.get(),
        }

    def _on_generate(self):
        def run():
            try:
                cfg = self._collect_cfg()

                # Basic validation
                errs = []
                if cfg["min_w"] >= cfg["max_w"]: errs.append("Min W must be < Max W")
                if cfg["min_d"] >= cfg["max_d"]: errs.append("Min D must be < Max D")
                if cfg["min_h"] >= cfg["max_h"]: errs.append("Min H must be < Max H")
                if cfg["gap_range"][0] > cfg["gap_range"][1]:
                    errs.append("Min gap must be ≤ Max gap")
                if errs:
                    for e in errs: self._log(e, "warn")
                    return

                self._log(f"Generating {cfg['n_rooms']} rooms "
                          f"(seed {cfg['seed']})…", "info")
                t0 = time.perf_counter()
                ms, rooms, bridges = generate_map(cfg)
                dt = time.perf_counter() - t0

                self._map_str = ms
                self._rooms   = rooms
                self._bridges = bridges

                nb = len(rooms)*6 + len(bridges)*4
                kb = len(ms.encode()) / 1024
                self._log(
                    f"Done in {dt:.2f}s — {len(rooms)} rooms, "
                    f"{len(bridges)} bridges, ~{nb} brushes, {kb:.1f} KB",
                    "info")
                self._lbl_stats.config(
                    text=f"rooms={len(rooms)}  bridges={len(bridges)}"
                         f"  brushes≈{nb}  {kb:.1f} KB")

                self.after(0, self._redraw)
                self.after(0, self._do_save)

                if self._v_autorand.get():
                    self.after(200, self._randomize_seed)

            except Exception as ex:
                import traceback; traceback.print_exc()
                self._log(f"Error: {ex}", "error")

        threading.Thread(target=run, daemon=True).start()

    def _on_save(self):
        if not self._map_str:
            self._log("Nothing to save — generate first.", "warn")
            return
        self._do_save(manual=True)

    def _do_save(self, manual=False):
        path = self._out_path.get()
        try:
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(self._map_str)
            self._log(f"{'Saved' if manual else 'Auto-saved'}: {path}", "info")
        except Exception as e:
            self._log(f"Save error: {e}", "error")

    # ── Preview canvas ────────────────────────────────────────────────────────
    def _redraw(self):
        c = self._canvas
        c.delete("all")
        W, H = c.winfo_width(), c.winfo_height()
        if W < 10 or H < 10:
            return
        if not self._rooms:
            c.create_text(W//2, H//2,
                          text="Press ⚡ Generate to see preview",
                          fill=T["text_dim"],
                          font=("Segoe UI", 12), justify="center")
            return

        rooms = self._rooms
        all_x = [r.x1 for r in rooms] + [r.x2 for r in rooms]
        all_y = [r.y1 for r in rooms] + [r.y2 for r in rooms]
        mx, my = min(all_x), min(all_y)
        rw = max(all_x) - mx
        rh = max(all_y) - my

        PAD = 40
        sc  = min((W-PAD*2) / max(rw, 1),
                  (H-PAD*2) / max(rh, 1))

        def tx(v): return PAD + (v - mx) * sc
        def ty(v): return PAD + (v - my) * sc

        # Bridges
        for br in self._bridges:
            hw = DOOR_W // 2
            if br.axis == 'x':
                xmn = min(br.ax, br.bx); xmx = max(br.ax, br.bx)
                cy  = (br.ay + br.by) // 2
                c.create_rectangle(tx(xmn), ty(cy-hw),
                                   tx(xmx), ty(cy+hw),
                                   fill=T["corr_col"],
                                   outline=T["border"], width=1)
            else:
                cx  = (br.ax + br.bx) // 2
                ymn = min(br.ay, br.by); ymx = max(br.ay, br.by)
                c.create_rectangle(tx(cx-hw), ty(ymn),
                                   tx(cx+hw), ty(ymx),
                                   fill=T["corr_col"],
                                   outline=T["border"], width=1)

        # Rooms
        for i, room in enumerate(rooms):
            if i == 0:
                fill, bdr = T["start_col"], T["success"]
            elif i == len(rooms)-1:
                fill, bdr = T["end_col"],   T["accent"]
            else:
                fill, bdr = T["room_col"],  T["border"]

            x1, y1 = tx(room.x1), ty(room.y1)
            x2, y2 = tx(room.x2), ty(room.y2)
            c.create_rectangle(x1, y1, x2, y2,
                               fill=fill, outline=bdr, width=2)
            fs = max(7, min(13, int(min(x2-x1, y2-y1) / 3.5)))
            c.create_text((x1+x2)/2, (y1+y2)/2,
                          text=str(i+1), fill=T["text"],
                          font=("Segoe UI", fs, "bold"))

        # Legend
        items = [("■ Start", T["success"]), ("■ Rooms", T["room_col"]),
                 ("■ End",   T["accent"]),  ("━ Bridge", T["corr_col"])]
        for j, (txt, col) in enumerate(items):
            c.create_text(PAD + j*110, H-16, text=txt,
                          fill=col, font=("Segoe UI", 8), anchor="w")


# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    app = App()
    app.mainloop()