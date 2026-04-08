#!/usr/bin/env python3
"""
Turnt-o-mapper — Turnt .map generator
v3.0 — new layouts, all-face textures, Z-fight fix, ramps, WASD cam, multi-route, game launcher
"""

import random, os, math, threading, time, json, subprocess
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple
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
               "turnt/turnt_tech","turnt/turnt_teal"]
WALL_TEX   = ["turnt/turnt_concrete","turnt/turnt_tech","turnt/turnt_white",
               "turnt/turnt_cyan","turnt/turnt_mint","turnt/turnt_violet"]
CEIL_TEX   = ["turnt/turnt_sky","turnt/turnt_white","turnt/turnt_tech"]
HIDDEN_TEX = "common/caulk"
NODRAW_TEX = "common/nodrawnonsolid"
TRIGGER_TEX = "common/trigger"

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

def room_floor(x1,y1,z1, x2,y2,z2, floor_t, tag, bi, clips=()):
    """Floor brush(es) — inner XY footprint minus any later-room clip regions."""
    H   = WALL_T
    oz1 = z1 - H
    parts = []
    for rx1,ry1,rx2,ry2 in _clip_footprint(x1, y1, x2, y2, clips):
        if rx1 < rx2 and ry1 < ry2 and oz1 < z1:
            fs = box_faces(rx1,ry1,oz1, rx2,ry2,z1,
                           floor_t,floor_t,floor_t,floor_t,floor_t,floor_t)
            parts.append(write_brush(fs, f"brush {bi} {tag}_floor"))
            bi += 1
    return parts, bi


def room_ceiling(x1,y1,z1, x2,y2,z2, ceil_t, tag, bi, clips=()):
    """Ceiling brush(es) — inner XY footprint minus any later-room clip regions."""
    H   = WALL_T
    oz2 = z2 + H
    parts = []
    for rx1,ry1,rx2,ry2 in _clip_footprint(x1, y1, x2, y2, clips):
        if rx1 < rx2 and ry1 < ry2 and z2 < oz2:
            fs = box_faces(rx1,ry1,z2, rx2,ry2,oz2,
                           ceil_t,ceil_t,ceil_t,ceil_t,ceil_t,ceil_t)
            parts.append(write_brush(fs, f"brush {bi} {tag}_ceil"))
            bi += 1
    return parts, bi


def room_walls(x1,y1,z1, x2,y2,z2, wall_t, tag, bi, doors=None, skip_sides=None,
               side_clips=None):
    """4 side walls with optional door cutouts and partial overlap clipping.

    side_clips: {wall_name: [(clo, chi), ...]}
        Intervals along the wall's variable axis (Y for wx1/wx2, X for wy1/wy2)
        that are covered by overlapping rooms and should not be generated.
        Walls are split into segments around these intervals rather than
        being omitted entirely.
    """
    H   = WALL_T
    ox1,oy1,oz1 = x1-H, y1-H, z1-H
    ox2,oy2,oz2 = x2+H, y2+H, z2+H
    parts = []

    door_map = {}
    if doors:
        for d in doors:
            door_map.setdefault(d['wall'], []).append(d)

    def rb(ax1,ay1,az1, ax2,ay2,az2, lbl=""):
        nonlocal bi
        if ax1 >= ax2 or ay1 >= ay2 or az1 >= az2:
            return
        fs = box_faces(ax1,ay1,az1,ax2,ay2,az2,
                       wall_t,wall_t,wall_t,wall_t,wall_t,wall_t)
        parts.append(write_brush(fs, f"brush {bi} {tag}_{lbl}"))
        bi += 1

    def _gen_wall_y(bx1, bx2, by1, by2, bz1, bz2, wall_name):
        """One Y-extent segment of a wx1/wx2 wall, with door cutout."""
        ds = door_map.get(wall_name)
        if not ds:
            rb(bx1, by1, bz1, bx2, by2, bz2, lbl=wall_name)
            return
        d = ds[0]
        yc = d['center'];  hw = d['hw']
        eff_lo = max(yc - hw, by1)
        eff_hi = min(yc + hw, by2)
        if eff_lo >= eff_hi:          # door doesn't touch this segment
            rb(bx1, by1, bz1, bx2, by2, bz2, lbl=wall_name)
            return
        z_b = d['z_bot'];  z_t = min(z_b + d['ht'], bz2)
        if z_b > bz1:
            rb(bx1, by1,    bz1, bx2, by2,    z_b, lbl=f"{wall_name}_bot")
        if z_t < bz2:
            rb(bx1, by1,    z_t, bx2, by2,    bz2, lbl=f"{wall_name}_top")
        if eff_lo > by1:
            rb(bx1, by1,    z_b, bx2, eff_lo, z_t, lbl=f"{wall_name}_l")
        if eff_hi < by2:
            rb(bx1, eff_hi, z_b, bx2, by2,    z_t, lbl=f"{wall_name}_r")

    def _gen_wall_x(bx1, bx2, by1, by2, bz1, bz2, wall_name):
        """One X-extent segment of a wy1/wy2 wall, with door cutout."""
        ds = door_map.get(wall_name)
        if not ds:
            rb(bx1, by1, bz1, bx2, by2, bz2, lbl=wall_name)
            return
        d = ds[0]
        xc = d['center'];  hw = d['hw']
        eff_lo = max(xc - hw, bx1)
        eff_hi = min(xc + hw, bx2)
        if eff_lo >= eff_hi:          # door doesn't touch this segment
            rb(bx1, by1, bz1, bx2, by2, bz2, lbl=wall_name)
            return
        z_b = d['z_bot'];  z_t = min(z_b + d['ht'], bz2)
        if z_b > bz1:
            rb(bx1,    by1, bz1, bx2,    by2, z_b, lbl=f"{wall_name}_bot")
        if z_t < bz2:
            rb(bx1,    by1, z_t, bx2,    by2, bz2, lbl=f"{wall_name}_top")
        if eff_lo > bx1:
            rb(bx1,    by1, z_b, eff_lo, by2, z_t, lbl=f"{wall_name}_l")
        if eff_hi < bx2:
            rb(eff_hi, by1, z_b, bx2,    by2, z_t, lbl=f"{wall_name}_r")

    def wall_y(bx1, bx2, full_y1, full_y2, bz1, bz2, wall_name):
        """wx1/wx2 wall — generate only the Y segments not covered by clips."""
        clips_1d = (side_clips or {}).get(wall_name, [])
        for seg_y1, seg_y2 in _clip_intervals(full_y1, full_y2, clips_1d):
            _gen_wall_y(bx1, bx2, seg_y1, seg_y2, bz1, bz2, wall_name)

    def wall_x(bx1, bx2, by1, by2, bz1, bz2, wall_name):
        """wy1/wy2 wall — generate only the X segments not covered by clips.
        Clips are in inner-face X space (x1..x2); outer slab (ox1/ox2)
        is preserved at the original wall boundaries.
        """
        clips_1d = (side_clips or {}).get(wall_name, [])
        for seg_x1, seg_x2 in _clip_intervals(x1, x2, clips_1d):
            sbx1 = bx1 if seg_x1 <= x1 else seg_x1
            sbx2 = bx2 if seg_x2 >= x2 else seg_x2
            _gen_wall_x(sbx1, sbx2, by1, by2, bz1, bz2, wall_name)

    # Generate the 4 walls; skip any that are entirely inside an overlapping room.
    skip = skip_sides or set()
    if 'wx1' not in skip:
        wall_y(ox1, x1,  y1, y2, oz1, oz2, 'wx1')   # left  wall (x-min side)
    if 'wx2' not in skip:
        wall_y(x2,  ox2, y1, y2, oz1, oz2, 'wx2')   # right wall (x-max side)
    if 'wy1' not in skip:
        wall_x(ox1, ox2, oy1, y1, oz1, oz2, 'wy1')  # front wall (y-min side)
    if 'wy2' not in skip:
        wall_x(ox1, ox2, y2,  oy2, oz1, oz2, 'wy2') # back  wall (y-max side)

    return parts, bi

def _ramp_brushes(x0, y0, z0, x1, y1, z1,
                   axis, hw, door_ht,
                   floor_t, ceil_t, wall_t,
                   tag, bi, *,
                   enc_lo, enc_hi):
    """5-face pentahedron floor-wedge ramp.

    x0/y0/z0 .. x1/y1/z1  — full ramp extent (may reach inside adjacent rooms).
    enc_lo / enc_hi        — corridor-gap bounds; enclosure brushes (ceiling,
                             side walls) are placed only in this section so
                             they don't double up with room geometry.

    Face winding verified: all inward normals computed by (p2-p1)×(p3-p1).
    """
    H = WALL_T
    parts = []

    def ramp5(f1, f2, f3, f4, f5, lbl):
        nonlocal bi
        faces = [face(a, b, c, floor_t) for (a, b, c) in (f1, f2, f3, f4, f5)]
        parts.append(write_brush(faces, f"brush {bi} {tag}_{lbl}"))
        bi += 1

    def cb(ax1, ay1, az1, ax2, ay2, az2,
           nx=None, px=None, ny=None, py=None, nz=None, pz=None, lbl=""):
        nonlocal bi
        if ax1 >= ax2 or ay1 >= ay2 or az1 >= az2:
            return
        _nx = nx or wall_t; _px = px or wall_t
        _ny = ny or wall_t; _py = py or wall_t
        _nz = nz or ceil_t; _pz = pz or wall_t
        fs = box_faces(ax1, ay1, az1, ax2, ay2, az2, _nx, _px, _ny, _py, _nz, _pz)
        parts.append(write_brush(fs, f"brush {bi} {tag}_{lbl}"))
        bi += 1

    if axis == 'y':
        # Normalise so y0 < y1 (travel along +Y)
        if y0 > y1:
            y0, y1 = y1, y0
            z0, z1 = z1, z0
        ylo, yhi = y0, y1           # caller already provides correct extent
        if ylo >= yhi:
            return parts, bi
        cx  = (x0 + x1) // 2
        xlo, xhi = cx - hw, cx + hw
        za, zb   = z0, z1
        bot      = min(za, zb) - H

        if za <= zb:
            # upramp: ylo@za(low) → yhi@zb(high)
            ramp5(
                ((xlo,yhi,za), (xlo,yhi,zb), (xlo,ylo,za)),   # left  x=xlo, +X
                ((xlo,yhi,zb), (xhi,yhi,zb), (xhi,ylo,za)),   # slope
                ((xhi,ylo,za), (xhi,yhi,za), (xlo,yhi,za)),   # bottom z=za, +Z
                ((xhi,yhi,za), (xhi,yhi,zb), (xlo,yhi,zb)),   # back  y=yhi, −Y
                ((xhi,ylo,za), (xhi,yhi,zb), (xhi,yhi,za)),   # right x=xhi, −X
                "ramp",
            )
        else:
            # downramp: ylo@za(high) → yhi@zb(low)
            ramp5(
                ((xlo,yhi,zb), (xlo,ylo,za), (xlo,ylo,zb)),          # left  x=xlo, +X
                ((xlo,ylo,zb), (xlo,ylo,za), (xhi,ylo,za)),          # front y=ylo, +Y
                ((xlo,yhi,bot),(xlo,ylo,bot),(xhi,ylo,bot)),          # virtual bottom, +Z
                ((xhi,ylo,za), (xlo,ylo,za), (xlo,yhi,zb)),          # slope
                ((xhi,ylo,zb), (xhi,ylo,za), (xhi,yhi,zb)),          # right x=xhi, −X
                "ramp",
            )

        # Enclosure only in corridor gap
        z_lo, z_hi = min(za, zb), max(za, zb)
        ceil_top = z_hi + door_ht
        elo, ehi = enc_lo + H, enc_hi - H
        if elo < ehi:
            cb(xlo, elo, ceil_top, xhi, ehi, ceil_top + H,
               nx=ceil_t, px=ceil_t, ny=ceil_t, py=ceil_t, nz=ceil_t, pz=ceil_t,
               lbl="ramp_ce")
            cb(xlo - H, elo, z_lo - H, xlo, ehi, ceil_top + H, lbl="ramp_w1")
            cb(xhi,     elo, z_lo - H, xhi + H, ehi, ceil_top + H, lbl="ramp_w2")

    else:  # axis == 'x'
        # Normalise so x0 < x1 (travel along +X)
        if x0 > x1:
            x0, x1 = x1, x0
            z0, z1 = z1, z0
        xlo, xhi = x0, x1           # caller already provides correct extent
        if xlo >= xhi:
            return parts, bi
        cy  = (y0 + y1) // 2
        ylo, yhi = cy - hw, cy + hw
        za, zb   = z0, z1
        bot      = min(za, zb) - H

        if za <= zb:
            # upramp: xlo@za(low) → xhi@zb(high)
            ramp5(
                ((xlo,ylo,za), (xhi,ylo,zb), (xhi,ylo,za)),   # front y=ylo, +Y
                ((xlo,yhi,za), (xhi,yhi,za), (xhi,yhi,zb)),   # back  y=yhi, −Y
                ((xhi,ylo,za), (xhi,yhi,za), (xlo,yhi,za)),   # bottom z=za, +Z
                ((xhi,yhi,zb), (xhi,yhi,za), (xhi,ylo,za)),   # end   x=xhi, −X
                ((xhi,yhi,zb), (xhi,ylo,zb), (xlo,ylo,za)),   # slope
                "ramp",
            )
        else:
            # downramp: xlo@za(high) → xhi@zb(low)
            ramp5(
                ((xlo,ylo,zb), (xlo,ylo,za), (xhi,ylo,za)),          # front y=ylo, +Y
                ((xlo,yhi,zb), (xlo,yhi,za), (xlo,ylo,zb)),          # end   x=xlo, +X
                ((xhi,ylo,bot),(xhi,yhi,bot),(xlo,yhi,bot)),          # virtual bottom, +Z
                ((xhi,ylo,zb), (xlo,ylo,za), (xlo,yhi,za)),          # slope
                ((xlo,yhi,zb), (xhi,yhi,zb), (xhi,yhi,za)),          # back  y=yhi, −Y
                "ramp",
            )

        # Enclosure only in corridor gap
        z_lo, z_hi = min(za, zb), max(za, zb)
        ceil_top = z_hi + door_ht
        elo, ehi = enc_lo + H, enc_hi - H
        if elo < ehi:
            cb(elo, ylo, ceil_top, ehi, yhi, ceil_top + H,
               nx=ceil_t, px=ceil_t, ny=ceil_t, py=ceil_t, nz=ceil_t, pz=ceil_t,
               lbl="ramp_ce")
            cb(elo, ylo - H, z_lo - H, ehi, ylo, ceil_top + H, lbl="ramp_w1")
            cb(elo, yhi,     z_lo - H, ehi, yhi + H, ceil_top + H, lbl="ramp_w2")

    return parts, bi


def _wallramp_brushes(room, bi):
    """Add 45° wedge ramps at the base of room walls for trick-jump surfaces.

    Three variants placed randomly: floor-corner ramps (diagonal wedge in XY),
    side-wall ramps (rising along the travel axis), and back-wall ramps.
    """
    parts = []
    H   = WALL_T
    rw  = room.wall_t
    rf  = room.floor_t
    sz  = 64  # ramp footprint

    def wx(xlo,xhi,ylo,yhi,zlo,zhi,lbl):
        nonlocal bi
        bot = zlo - H
        f1 = face((xlo,ylo,bot),(xhi,ylo,bot),(xlo,yhi,bot),
                  rf, (-1,0,0),0,(0,-1,0),0)
        f2 = face((xlo,ylo,zlo),(xlo,yhi,zlo),(xhi,ylo,zhi),
                  rf, (0,1,0),0,(0,0,-1),0)
        f3 = face((xlo,ylo,bot),(xlo,ylo,zlo),(xlo,yhi,bot),
                  rw, (0,1,0),0,(0,0,-1),0)
        f4 = face((xhi,yhi,bot),(xhi,yhi,zhi),(xhi,ylo,bot),
                  rw, (0,-1,0),0,(0,0,-1),0)
        f5 = face((xlo,ylo,bot),(xhi,ylo,bot),(xhi,ylo,zhi),
                  rw, (-1,0,0),0,(0,0,-1),0)
        f6 = face((xlo,yhi,bot),(xlo,yhi,zlo),(xhi,yhi,bot),
                  rw, (1,0,0),0,(0,0,-1),0)
        parts.append(write_brush([f1,f2,f3,f4,f5,f6], f"brush {bi} wr_{lbl}"))
        bi += 1

    def wy(ylo,yhi,xlo,xhi,zlo,zhi,lbl):
        nonlocal bi
        bot = zlo - H
        f1 = face((xlo,ylo,bot),(xhi,ylo,bot),(xlo,yhi,bot),
                  rf, (-1,0,0),0,(0,-1,0),0)
        f2 = face((xlo,ylo,zlo),(xhi,ylo,zlo),(xlo,yhi,zhi),
                  rf, (1,0,0),0,(0,0,-1),0)
        f3 = face((xlo,ylo,bot),(xlo,yhi,bot),(xlo,ylo,zlo),
                  rw, (0,-1,0),0,(0,0,-1),0)
        f4 = face((xhi,yhi,bot),(xhi,ylo,bot),(xhi,yhi,zhi),
                  rw, (0,1,0),0,(0,0,-1),0)
        f5 = face((xlo,ylo,bot),(xlo,ylo,zlo),(xhi,ylo,bot),
                  rw, (0,0,-1),0,(1,0,0),0)
        f6 = face((xlo,yhi,bot),(xhi,yhi,bot),(xlo,yhi,zhi),
                  rw, (0,0,1),0,(1,0,0),0)
        parts.append(write_brush([f1,f2,f3,f4,f5,f6], f"brush {bi} wr_{lbl}"))
        bi += 1

    x1,y1,z1 = room.x1, room.y1, room.z1
    x2,y2    = room.x2, room.y2
    cx,cy    = room.cx(), room.cy()

    # Ramps at y1/y2 walls: slope along Y (into/out of room) — use wy()
    if random.random() < 0.5:
        wy(y1, y1+sz, cx-sz, cx+sz, z1, z1+sz, "wy1_ramp")
    if random.random() < 0.5:
        wy(y2-sz, y2, cx-sz, cx+sz, z1, z1+sz, "wy2_ramp")
    # Ramps at x1/x2 walls: slope along X (into/out of room) — use wx()
    if random.random() < 0.5:
        wx(x1, x1+sz, cy-sz, cy+sz, z1, z1+sz, "wx1_ramp")
    if random.random() < 0.5:
        wx(x2-sz, x2, cy-sz, cy+sz, z1, z1+sz, "wx2_ramp")

    return parts, bi


SLOPE_RATIO = 4.0   # horizontal / vertical ≈ 14° — shallow enough for crouchslide


def corridor_brushes(ax,ay,az, bx,by,bz,
                     axis, floor_t, ceil_t, wall_t,
                     door_hw=64, door_ht=DOOR_H,
                     ra_far=None, rb_far=None,
                     tag="", bi=0):
    """Build a corridor (flat) or a full-length ramp (when az != bz).

    For ramps the wedge is extended to achieve ~14° slope, reaching INTO the
    adjacent rooms as needed.  Only enclosure brushes (ceiling/side-walls) are
    restricted to the corridor gap so they don't double-up with room geometry.

    ra_far / rb_far — the inner far-wall coordinate of each room (limits how far
                      the ramp may extend into that room).
    """
    H  = WALL_T
    dz = abs(bz - az)

    if dz >= 32:
        # ── Extended ramp: full slope length, not just the corridor gap ──────
        lo_x  = min(ax, bx);  hi_x  = max(ax, bx)
        lo_z  = az if ax <= bx else bz
        hi_z  = bz if ax <= bx else az
        lo_far = ra_far if ax <= bx else rb_far
        hi_far = rb_far if ax <= bx else ra_far

        if axis == 'x':
            ramp_len = max(int(dz * SLOPE_RATIO), hi_x - lo_x)
            if lo_z <= hi_z:          # upramp: extends into lo-side room
                x_hi = hi_x - H
                x_lo = x_hi - ramp_len
                if lo_far is not None:
                    x_lo = max(x_lo, lo_far + H)
            else:                     # downramp: extends into hi-side room
                x_lo = lo_x + H
                x_hi = x_lo + ramp_len
                if hi_far is not None:
                    x_hi = min(x_hi, hi_far - H)
            return _ramp_brushes(x_lo, ay, lo_z, x_hi, by, hi_z,
                                 axis, door_hw, door_ht,
                                 floor_t, ceil_t, wall_t,
                                 tag=tag, bi=bi,
                                 enc_lo=lo_x, enc_hi=hi_x)
        else:  # axis == 'y'
            lo_y  = min(ay, by);  hi_y  = max(ay, by)
            lo_zy = az if ay <= by else bz
            hi_zy = bz if ay <= by else az
            lo_fy = ra_far if ay <= by else rb_far
            hi_fy = rb_far if ay <= by else ra_far
            ramp_len = max(int(dz * SLOPE_RATIO), hi_y - lo_y)
            if lo_zy <= hi_zy:        # upramp: extends into lo-side room
                y_hi = hi_y - H
                y_lo = y_hi - ramp_len
                if lo_fy is not None:
                    y_lo = max(y_lo, lo_fy + H)
            else:                     # downramp: extends into hi-side room
                y_lo = lo_y + H
                y_hi = y_lo + ramp_len
                if hi_fy is not None:
                    y_hi = min(y_hi, hi_fy - H)
            return _ramp_brushes(ax, y_lo, lo_zy, bx, y_hi, hi_zy,
                                 axis, door_hw, door_ht,
                                 floor_t, ceil_t, wall_t,
                                 tag=tag, bi=bi,
                                 enc_lo=lo_y, enc_hi=hi_y)

    # ── flat corridor ────────────────────────────────────────────────────────
    H   = WALL_T
    hw  = door_hw
    parts = []
    zf = min(az, bz)
    zc = zf + door_ht   # ceiling matches door height

    def cb(ax1,ay1,az1, ax2,ay2,az2,
           nx=wall_t,px=wall_t,ny=wall_t,py=wall_t,nz=ceil_t,pz=floor_t, lbl=""):
        nonlocal bi
        if ax1>=ax2 or ay1>=ay2 or az1>=az2:
            return
        fs = box_faces(ax1,ay1,az1,ax2,ay2,az2, nx,px,ny,py,nz,pz)
        parts.append(write_brush(fs, f"brush {bi} {tag}_{lbl}"))
        bi += 1

    if axis == 'x':
        xmn = min(ax,bx) + H   # trim: start after room-A outer shell
        xmx = max(ax,bx) - H   # trim: end before room-B outer shell
        if xmn >= xmx:
            return parts, bi
        cy = (ay + by) // 2
        cb(xmn, cy-hw,   zf-H, xmx, cy+hw,   zf,
           nx=floor_t,px=floor_t,ny=floor_t,py=floor_t,nz=floor_t,pz=floor_t, lbl="fl")
        cb(xmn, cy-hw,   zc,   xmx, cy+hw,   zc+H,
           nx=ceil_t,px=ceil_t,ny=ceil_t,py=ceil_t,nz=ceil_t,pz=ceil_t, lbl="ce")
        cb(xmn, cy-hw-H, zf,   xmx, cy-hw,   zc,
           nx=wall_t,px=wall_t,ny=wall_t,py=wall_t,nz=wall_t,pz=wall_t, lbl="w1")
        cb(xmn, cy+hw,   zf,   xmx, cy+hw+H, zc,
           nx=wall_t,px=wall_t,ny=wall_t,py=wall_t,nz=wall_t,pz=wall_t, lbl="w2")
    else:
        cx = (ax + bx) // 2
        ymn = min(ay,by) + H
        ymx = max(ay,by) - H
        if ymn >= ymx:
            return parts, bi
        cb(cx-hw,   ymn, zf-H, cx+hw,   ymx, zf,
           nx=floor_t,px=floor_t,ny=floor_t,py=floor_t,nz=floor_t,pz=floor_t, lbl="fl")
        cb(cx-hw,   ymn, zc,   cx+hw,   ymx, zc+H,
           nx=ceil_t,px=ceil_t,ny=ceil_t,py=ceil_t,nz=ceil_t,pz=ceil_t, lbl="ce")
        cb(cx-hw-H, ymn, zf,   cx-hw,   ymx, zc,
           nx=wall_t,px=wall_t,ny=wall_t,py=wall_t,nz=wall_t,pz=wall_t, lbl="w1")
        cb(cx+hw,   ymn, zf,   cx+hw+H, ymx, zc,
           nx=wall_t,px=wall_t,ny=wall_t,py=wall_t,nz=wall_t,pz=wall_t, lbl="w2")

    return parts, bi

# ══════════════════════════════════════════════════════════════════════════════
#  DATA CLASSES
# ══════════════════════════════════════════════════════════════════════════════
@dataclass
class Room:
    x:int; y:int; z:int
    w:int; d:int; h:int
    idx:int = 0
    floor_t:      str   = "turnt/turnt_concrete"
    wall_t:       str   = "turnt/turnt_tech"
    ceil_t:       str   = "turnt/turnt_sky"
    travel_axis:  str   = 'x'    # direction of player travel through this room
    speed_in:     float = 550.0  # estimated UPS on entry (for sizing / debug)
    door_hw:      int   = 64     # half-width of the door on exit wall

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
    door_hw: int = 64
    door_ht: int = DOOR_H
    floor_t: str = "turnt/turnt_asphalt"
    wall_t:  str = "turnt/turnt_concrete"
    ceil_t:  str = "turnt/turnt_sky"

# ══════════════════════════════════════════════════════════════════════════════
#  LAYOUT ENGINE  (physics-driven)
# ══════════════════════════════════════════════════════════════════════════════
def _snap(v, grid=64):
    return round(v / grid) * grid

def _clamp(v, lo, hi):
    return max(lo, min(hi, v))

def _xy_overlap(ax1, ay1, ax2, ay2, bx1, by1, bx2, by2) -> bool:
    return ax1 < bx2 and ax2 > bx1 and ay1 < by2 and ay2 > by1

def _clip_intervals(lo: int, hi: int, clips) -> list:
    """Subtract list of (clo, chi) intervals from [lo, hi]. Returns remaining segments."""
    segs = [(lo, hi)]
    for clo, chi in clips:
        new_segs = []
        for a, b in segs:
            ov_lo = max(a, clo)
            ov_hi = min(b, chi)
            if ov_lo >= ov_hi:
                new_segs.append((a, b))
            else:
                if a < ov_lo:
                    new_segs.append((a, ov_lo))
                if ov_hi < b:
                    new_segs.append((ov_hi, b))
        segs = new_segs
    return segs


def _subtract_rect(rx1, ry1, rx2, ry2, ox1, oy1, ox2, oy2):
    """Subtract obstacle from rect. Returns up to 4 surrounding pieces."""
    cx1 = max(rx1, ox1); cy1 = max(ry1, oy1)
    cx2 = min(rx2, ox2); cy2 = min(ry2, oy2)
    if cx1 >= cx2 or cy1 >= cy2:
        return [(rx1, ry1, rx2, ry2)]
    return [(x1,y1,x2,y2) for x1,y1,x2,y2 in [
        (rx1, ry1, cx1, ry2),   # left of obstacle
        (cx2, ry1, rx2, ry2),   # right of obstacle
        (cx1, ry1, cx2, cy1),   # below obstacle (centre strip)
        (cx1, cy2, cx2, ry2),   # above obstacle (centre strip)
    ] if x1 < x2 and y1 < y2]

def _clip_footprint(x1, y1, x2, y2, clips):
    """Return list of rects after subtracting all clip regions."""
    rects = [(x1, y1, x2, y2)]
    for cx1,cy1,cx2,cy2 in clips:
        new_rects = []
        for r in rects:
            new_rects.extend(_subtract_rect(*r, cx1, cy1, cx2, cy2))
        rects = new_rects
    return rects


def _room_dims_from_physics(i: int, cfg: dict) -> Tuple[int, int, int, int, float]:
    """Return (room_len, room_cross, room_h, door_hw, u_i) for room index i.

    When cfg['use_physics'] is True, room sizes are calculated from speed
    parameters (acceleration model).  Otherwise, dimensions are drawn uniformly
    from the min/max slider values — Room Settings are the primary control.
    """
    u_base   = cfg.get("u_base",  550.0)
    u_gain   = cfg.get("u_gain",   60.0)
    u_i      = u_base + i * u_gain   # used for speed label in viewer

    min_w = cfg.get("min_w", 256);  max_w = cfg.get("max_w", 1536)
    min_d = cfg.get("min_d", 192);  max_d = cfg.get("max_d", 512)
    min_h = cfg.get("min_h", 192);  max_h = cfg.get("max_h", 512)

    corr_frac = cfg.get("corridor_width_frac", 0.67)

    if cfg.get("use_physics", False):
        t_air    = cfg.get("t_air",    0.68)
        strafe_f = cfg.get("strafe_f", 0.15)
        size_var = random.uniform(0.6, 1.5)
        h_var    = random.uniform(0.8, 1.6)

        room_len   = _snap(_clamp(u_i * t_air * 1.15 * size_var, min_w, max_w))
        room_cross = _snap(_clamp(u_i * strafe_f * size_var,      min_d, max_d))
        jump_z     = (u_i * 0.42) ** 2 / (2 * 800)
        room_h     = _snap(_clamp((jump_z + 128) * h_var,         min_h, max_h))
    else:
        room_len   = _snap(random.uniform(min_w, max(min_w, max_w)))
        room_cross = _snap(random.uniform(min_d, max(min_d, max_d)))
        room_h     = _snap(random.uniform(min_h, max(min_h, max_h)))

    door_hw = _snap(_clamp(int(room_cross * corr_frac / 2), 32, room_cross // 2))
    return room_len, room_cross, room_h, door_hw, u_i


def place_rooms(n: int, cfg: dict) -> List[Room]:
    """Physics-driven layout with multiple style options.

    Layouts:
      Linear    — one straight line
      Zigzag    — strict alternating X/Y every rpt rooms
      Snake     — like Zigzag but segment length is random (rpt±2)
      Random    — 4-directional: turn 90° left or right randomly each time
      Spiral    — always turn right: +X → −Y → −X → +Y → …
      Multilevel— Random with large Z jumps; route folds back at diff heights

    Min gap = 64 units (one snap grid) to guarantee ramp corridor space and
    eliminate Z-fighting between adjacent room outer shells.
    """
    rooms: List[Room] = []
    cx, cy, cz = 0, 0, 0

    # Zone-based texture cache: rooms in the same zone share a texture palette
    # so the map looks cohesive rather than random per room.
    ZONE_SIZE = 4
    _zone_cache: Dict[int, tuple] = {}
    def _zone_tex(zone: int):
        if zone not in _zone_cache:
            _zone_cache[zone] = (
                random.choice(FLOOR_TEX),
                random.choice(WALL_TEX),
                random.choice(CEIL_TEX),
            )
        return _zone_cache[zone]

    layout = cfg.get("layout_style", "Zigzag")
    rpt    = max(1, cfg.get("rooms_per_turn", 3))
    t_air  = cfg.get("t_air", 0.68)

    # --- 4-directional heading (dx, dy) for Random / Spiral / Multilevel ---
    # Right-turn order: (+X,0) → (0,-Y) → (-X,0) → (0,+Y) → …
    DIRS = [(1,0), (0,-1), (-1,0), (0,1)]
    dir_idx = 0   # start heading +X
    dx, dy  = DIRS[dir_idx]

    # Zigzag / Snake still use 2-axis flip
    axis = 'x'
    rooms_in_seg  = 0
    seg_turn_at   = rpt   # Snake randomises this per segment

    for i in range(n):
        # --- Detect corner room: turn will happen after this room ---
        if layout == "Linear":
            is_corner_room = False
        elif layout == "Snake":
            is_corner_room = (rooms_in_seg + 1 >= seg_turn_at)
        else:
            is_corner_room = (rooms_in_seg + 1 >= rpt)

        room_len, room_cross, room_h, door_hw, u_i = _room_dims_from_physics(i, cfg)

        # Widen corner rooms — VQ3 crouchslide needs space to turn
        if is_corner_room and i > 0:
            corner_scale = random.uniform(1.3, 1.6)
            max_w = cfg.get("max_w", 1536)
            max_d = cfg.get("max_d", 512)
            room_len   = _snap(min(int(room_len   * corner_scale), max_w))
            room_cross = _snap(min(int(room_cross * corner_scale), max_d))
            corr_frac  = cfg.get("corridor_width_frac", 0.67)
            door_hw    = _snap(_clamp(int(room_cross * corr_frac / 2), 32, room_cross // 2))

        if layout in ("Random", "Spiral", "Multilevel"):
            # heading determines which room dimension is "long" vs "cross"
            if dx != 0:   # moving along X
                w, d    = room_len, room_cross
                t_axis  = 'x'
            else:          # moving along Y
                w, d    = room_cross, room_len
                t_axis  = 'y'
        else:
            t_axis = axis
            if axis == 'x':
                w, d = room_len, room_cross
            else:
                w, d = room_cross, room_len

        # --- Z variation ---
        if i > 0 and cfg.get("height_var", True):
            prev_h = rooms[i-1].h
            # No consecutive height changes — prevents double-step runs
            prev_had_dz = (i >= 2 and rooms[i-1].z1 != rooms[i-2].z1)
            if prev_had_dz:
                dz = 0
            else:
                if layout == "Multilevel":
                    # Large steps for multilevel — use previous room height as scale
                    max_step = max(128, int(prev_h * 0.75))
                    max_step = _snap(max_step, 64)
                    dz_choices = [0, max_step//2, max_step, -max_step//2, -max_step,
                                   max_step//4, -max_step//4, 0, 0]
                else:
                    # Up to 50% of previous room height per step
                    max_step = max(64, int(prev_h * 0.5))
                    max_step = _snap(max_step, 32)
                    half    = max_step // 2
                    dz_choices = [0, 0, half, max_step, -half, -max_step]
                dz = random.choice(dz_choices)
                # Second room (i==1) can only go down from the first, not up
                if i == 1:
                    dz = min(dz, 0)
            cz += dz
            cz  = _snap(cz, 32)
            # Clamp so floor doesn't exceed previous room's ceiling minus DOOR_H
            prev_ceil = rooms[i-1].z1 + rooms[i-1].h
            cz = min(cz, prev_ceil - DOOR_H)
            if layout != "Multilevel":
                cz = max(cz, 0)
            else:
                cz = max(cz, -2048)

        # --- Z collision avoidance for folding layouts ---
        # When Random/Spiral/Multilevel routes double back, push the new room
        # above or below rooms it ACTUALLY conflicts with in 3D.
        # Exclude rooms[i-1]: it's the room we're bridging from, so XY overlap
        # near the shared wall is expected and the ramp handles height.
        if layout in ("Random", "Spiral", "Multilevel") and i > 0:
            CLEARANCE = 64
            prev_room = rooms[i - 1]
            # Find rooms that overlap in XY AND in Z with the candidate placement
            real_conflicts = [
                r for r in rooms
                if r is not prev_room
                and _xy_overlap(cx, cy, cx + w, cy + d, r.x1, r.y1, r.x2, r.y2)
                and r.z1 < cz + room_h + CLEARANCE
                and cz < r.z1 + r.h + CLEARANCE
            ]
            if real_conflicts:
                # Push by only as much as needed to clear the conflicting rooms
                ov_z_ceil  = max(r.z1 + r.h for r in real_conflicts)
                ov_z_floor = min(r.z1       for r in real_conflicts)
                z_above = _snap(ov_z_ceil  + CLEARANCE, 32)
                z_below = _snap(ov_z_floor - room_h - CLEARANCE, 32)
                # Stay as close to prev_room.z1 as possible so ramps can reach
                if abs(z_above - prev_room.z1) <= abs(z_below - prev_room.z1):
                    cz = z_above
                else:
                    cz = z_below
                if layout != "Multilevel":
                    cz = max(cz, 0)
                else:
                    cz = max(cz, -2048)

        _ft, _wt, _ct = _zone_tex(i // ZONE_SIZE)
        r = Room(x=cx, y=cy, z=cz,
                 w=w, d=d, h=room_h,
                 idx=i,
                 floor_t=_ft,
                 wall_t =_wt,
                 ceil_t =_ct,
                 travel_axis=t_axis,
                 speed_in=u_i,
                 door_hw=door_hw)
        rooms.append(r)

        # --- gap: minimum 64 to avoid Z-fighting; ramps may extend into rooms ---
        reach = u_i * t_air
        gap   = max(64, _snap(random.uniform(0.0, reach * 0.25)))

        # --- advance cursor ---
        if layout in ("Random", "Spiral", "Multilevel"):
            cx += dx * (w + gap)
            cy += dy * (d + gap)
        else:
            if axis == 'x':
                cx += w + gap
            else:
                cy += d + gap

        # --- decide turn ---
        rooms_in_seg += 1
        do_turn = False

        if layout == "Linear":
            do_turn = False

        elif layout == "Zigzag":
            do_turn = (rooms_in_seg >= rpt)

        elif layout == "Snake":
            do_turn = (rooms_in_seg >= seg_turn_at)

        elif layout in ("Random", "Multilevel"):
            do_turn = (rooms_in_seg >= rpt)

        elif layout == "Spiral":
            do_turn = (rooms_in_seg >= rpt)

        if do_turn:
            rooms_in_seg = 0

            if layout in ("Random", "Multilevel"):
                # 90° left or right, never reverse
                turn = random.choice([-1, 1])
                dir_idx = (dir_idx + turn) % 4
                dx, dy  = DIRS[dir_idx]

            elif layout == "Spiral":
                # always turn right
                dir_idx = (dir_idx + 1) % 4
                dx, dy  = DIRS[dir_idx]

            else:
                # Zigzag / Snake — 2-axis flip
                prev_axis = axis
                axis = 'y' if axis == 'x' else 'x'
                if layout == "Snake":
                    seg_turn_at = random.randint(max(1, rpt - 1), rpt + 2)

                # align perpendicular cursor to last room centre
                next_len, next_cross = _room_dims_from_physics(i+1, cfg)[:2] if i+1 < n else (room_len, room_cross)
                if prev_axis == 'x':
                    cy = r.cy() - next_cross // 2
                else:
                    cx = r.cx() - next_cross // 2

    return rooms


def _pick_overlap_center(a1: int, a2: int, b1: int, b2: int,
                         door_hw: int) -> Optional[Tuple[int, int]]:
    lo = max(a1, b1)
    hi = min(a2, b2)
    span = hi - lo
    if span <= 0:
        return None
    # Reduce door_hw to fit the overlap, minimum 32u
    effective_hw = min(door_hw, span // 2)
    if effective_hw < 32:
        return None
    center = (lo + hi) // 2
    center = _snap(center)
    center = max(lo + effective_hw, min(hi - effective_hw, center))
    return center, effective_hw


def _try_bridge(i: int, j: int, rooms: List['Room']) -> Optional['Bridge']:
    """Attempt to build a bridge between rooms[i] and rooms[j].

    When rooms are directly adjacent (gap = 0), the opening spans the full
    shared edge width — no separate corridor brush is generated (corridor_brushes
    returns empty when ax == bx / ay == by).
    When rooms overlap in XY, no bridge is needed (they share open space).
    """
    a, b = rooms[i], rooms[j]

    def _dhw(gap, cross_a, cross_b):
        """Door half-width: full-edge when gap=0, physics-based otherwise."""
        if gap == 0:
            return min(cross_a, cross_b) // 2
        return min(a.door_hw, b.door_hw)

    if b.x1 >= a.x2:                        # b is to the right of a
        gap = b.x1 - a.x2
        dhw = _dhw(gap, a.d, b.d)
        result = _pick_overlap_center(a.y1, a.y2, b.y1, b.y2, dhw)
        if result is not None:
            yc, dhw = result
            return Bridge(i, j, 'x', a.x2, yc, a.z1, b.x1, yc, b.z1,
                          door_hw=dhw,
                          floor_t=a.floor_t, wall_t=a.wall_t, ceil_t=a.ceil_t)
    elif a.x1 >= b.x2:                      # b is to the left of a
        gap = a.x1 - b.x2
        dhw = _dhw(gap, a.d, b.d)
        result = _pick_overlap_center(a.y1, a.y2, b.y1, b.y2, dhw)
        if result is not None:
            yc, dhw = result
            return Bridge(i, j, 'x', a.x1, yc, a.z1, b.x2, yc, b.z1,
                          door_hw=dhw,
                          floor_t=a.floor_t, wall_t=a.wall_t, ceil_t=a.ceil_t)
    elif b.y1 >= a.y2:                      # b is above a in Y
        gap = b.y1 - a.y2
        dhw = _dhw(gap, a.w, b.w)
        result = _pick_overlap_center(a.x1, a.x2, b.x1, b.x2, dhw)
        if result is not None:
            xc, dhw = result
            return Bridge(i, j, 'y', xc, a.y2, a.z1, xc, b.y1, b.z1,
                          door_hw=dhw,
                          floor_t=a.floor_t, wall_t=a.wall_t, ceil_t=a.ceil_t)
    elif a.y1 >= b.y2:                      # b is below a in Y
        gap = a.y1 - b.y2
        dhw = _dhw(gap, a.w, b.w)
        result = _pick_overlap_center(a.x1, a.x2, b.x1, b.x2, dhw)
        if result is not None:
            xc, dhw = result
            return Bridge(i, j, 'y', xc, a.y1, a.z1, xc, b.y2, b.z1,
                          door_hw=dhw,
                          floor_t=a.floor_t, wall_t=a.wall_t, ceil_t=a.ceil_t)
    # Rooms overlap in XY — open space is shared, no bridge needed
    return None


def build_bridges(rooms: List['Room']) -> List['Bridge']:
    """Build sequential bridges plus optional shortcut bridges (multi-route).

    Shortcuts connect rooms i → i+2 or i → i+3 when they are spatially close,
    creating parallel paths the player can discover.
    """
    bridges: List[Bridge] = []
    paired: set = set()

    # Sequential bridges
    for i in range(len(rooms) - 1):
        br = _try_bridge(i, i + 1, rooms)
        if br is not None:
            bridges.append(br)
            paired.add((i, i + 1))

    # Shortcut bridges (multi-route): skip 1–2 rooms if geographically close
    for i in range(len(rooms)):
        for skip in (2, 3):
            j = i + skip
            if j >= len(rooms):
                break
            if (i, j) in paired:
                continue
            a, b = rooms[i], rooms[j]
            # Only connect if centroid Manhattan distance is small enough
            dist = abs(a.cx() - b.cx()) + abs(a.cy() - b.cy())
            if dist < 1200:
                br = _try_bridge(i, j, rooms)
                if br is not None:
                    bridges.append(br)
                    paired.add((i, j))
                    break   # one shortcut per room is enough

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
                   TRIGGER_TEX, TRIGGER_TEX, TRIGGER_TEX,
                   TRIGGER_TEX, TRIGGER_TEX, TRIGGER_TEX)
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
def align_room_ceilings(rooms: List['Room'], bridges: List['Bridge']):
    """Raise room ceilings so all connected rooms share the same ceiling Z.

    Uses a fixed-point loop so ceiling heights propagate correctly even
    through shortcut bridges that are processed after sequential ones.
    Also guarantees each room is tall enough for any ramp corridor to fit.
    """
    n = len(rooms)
    ceil_z = [r.z1 + r.h for r in rooms]

    changed = True
    while changed:
        changed = False
        for br in bridges:
            a, b = rooms[br.room_a], rooms[br.room_b]
            ia, ib = br.room_a, br.room_b
            # Min ceiling = higher floor + DOOR_H + WALL_T (ramp headroom)
            z_hi = max(a.z1, b.z1)
            min_ceil = z_hi + DOOR_H + WALL_T
            target = max(ceil_z[ia], ceil_z[ib], min_ceil)
            if ceil_z[ia] < target:
                ceil_z[ia] = target; changed = True
            if ceil_z[ib] < target:
                ceil_z[ib] = target; changed = True

    for i, room in enumerate(rooms):
        room.h = _snap(ceil_z[i]) - room.z1


def generate_map(cfg: dict):
    seed = cfg.get("seed")
    if seed is not None:
        random.seed(seed)

    rooms   = place_rooms(cfg["n_rooms"], cfg)
    bridges = build_bridges(rooms)

    # ── Center map so bounding box midpoint is at (0, 0) and min-Z = 0 ────────
    if rooms:
        x_min = min(r.x1 for r in rooms)
        x_max = max(r.x2 for r in rooms)
        y_min = min(r.y1 for r in rooms)
        y_max = max(r.y2 for r in rooms)
        z_min = min(r.z1 for r in rooms)
        dx = -((x_min + x_max) // 2)
        dy = -((y_min + y_max) // 2)
        dz = -z_min
        for r in rooms:
            r.x += dx; r.y += dy; r.z += dz
        for br in bridges:
            br.ax += dx; br.bx += dx
            br.ay += dy; br.by += dy
            br.az += dz; br.bz += dz

    # ── Update travel_axis from actual bridge connections ─────────────────────
    # Do a preliminary pass using bridge directions (no door data yet).
    # Overrides the layout-direction guess; prevents deadzones / "tails".
    for i, room in enumerate(rooms):
        x_walls: set = set()
        y_walls: set = set()
        for br in bridges:
            if br.room_a == i:
                if br.axis == 'x': x_walls.add('wx2')
                else:              y_walls.add('wy2')
            elif br.room_b == i:
                if br.axis == 'x': x_walls.add('wx1')
                else:              y_walls.add('wy1')
        if x_walls and not y_walls:
            room.travel_axis = 'x'
        elif y_walls and not x_walls:
            room.travel_axis = 'y'
        elif x_walls and y_walls:
            # Corner room — align long axis with bridge direction
            room.travel_axis = 'x' if room.w >= room.d else 'y'
        # else: isolated room (no bridges), keep original axis

    # ── Align ceiling heights so adjacent rooms feel continuous ───────────────
    align_room_ceilings(rooms, bridges)

    # ── Per-room door cutout data (from bridges) ──────────────────────────────
    # Computed AFTER align_room_ceilings so door heights match the final room.h.
    # z_bot references the BRIDGE endpoint Z so the cutout aligns with the
    # corridor floor even when rooms are at different heights.
    room_doors: Dict[int, list] = {i: [] for i in range(len(rooms))}
    for br in bridges:
        hw = br.door_hw
        ra, rb = rooms[br.room_a], rooms[br.room_b]
        dz_br  = abs(br.bz - br.az)

        if dz_br >= 32:
            # Ramp bridge: open both walls to their full room height so the ramp
            # surface never hits a ceiling on the way through.
            door_ht_lo = ra.h
            door_ht_hi = rb.h
        else:
            # Flat corridor: random door height between DOOR_H and full room height
            max_ht = min(ra.h, rb.h)
            if random.random() < 0.5:
                ht = max_ht
            else:
                ht = _snap(random.randint(DOOR_H, max(DOOR_H, max_ht)), 32)
            door_ht_lo = door_ht_hi = ht

        br.door_ht = max(door_ht_lo, door_ht_hi)  # corridor ceiling = tallest
        if br.axis == 'x':
            ra_wall = 'wx2' if br.ax >= ra.x2 - 1 else 'wx1'
            rb_wall = 'wx1' if br.bx <= rb.x1 + 1 else 'wx2'
            room_doors[br.room_a].append(
                {'wall':ra_wall,'center':br.ay,'hw':hw,'ht':door_ht_lo,'z_bot':br.az})
            room_doors[br.room_b].append(
                {'wall':rb_wall,'center':br.ay,'hw':hw,'ht':door_ht_hi,'z_bot':br.bz})
        else:
            ra_wall = 'wy2' if br.ay >= ra.y2 - 1 else 'wy1'
            rb_wall = 'wy1' if br.by <= rb.y1 + 1 else 'wy2'
            room_doors[br.room_a].append(
                {'wall':ra_wall,'center':br.ax,'hw':hw,'ht':door_ht_lo,'z_bot':br.az})
            room_doors[br.room_b].append(
                {'wall':rb_wall,'center':br.ax,'hw':hw,'ht':door_ht_hi,'z_bot':br.bz})

    # ── Compute clip regions: for each room, collect footprints of later rooms
    #    that overlap it in both XY AND Z.  Rooms at different height levels
    #    (e.g. Multilevel/Spiral passing above) must NOT clip each other.
    room_clips: Dict[int, list] = {i: [] for i in range(len(rooms))}
    for i in range(len(rooms)):
        ri = rooms[i]
        for j in range(i + 1, len(rooms)):
            rj = rooms[j]
            z_overlap = ri.z1 < rj.z2 and rj.z1 < ri.z2
            if z_overlap and _xy_overlap(ri.x1, ri.y1, ri.x2, ri.y2,
                                         rj.x1, rj.y1, rj.x2, rj.y2):
                room_clips[i].append((rj.x1, rj.y1, rj.x2, rj.y2))

    lines = [
        "// Game: Quake 3",
        "// Format: Valve",
        f"// Generated by Turnt-o-mapper v3 | rooms={cfg['n_rooms']} seed={seed}",
        "// entity 0",
        "{",
        '"mapversion" "220"',
        '"classname" "worldspawn"',
        '"_ambient" "15"',
        f'"message" "{cfg.get("map_name","turnt_map")}"',
    ]

    bi = 0

    # ── Pass 1: floors ────────────────────────────────────────────────────────
    for room in rooms:
        clips = room_clips[room.idx]
        parts, bi = room_floor(room.x1,room.y1,room.z1, room.x2,room.y2,room.z2,
                               room.floor_t, f"r{room.idx}", bi, clips=clips)
        lines.extend(parts)

    # ── Pass 2: walls ─────────────────────────────────────────────────────────
    for room in rooms:
        clips = room_clips[room.idx]
        # Fully contained: all clip rects together cover the whole room footprint
        contained = any(
            cx1 <= room.x1 and room.x2 <= cx2 and cy1 <= room.y1 and room.y2 <= cy2
            for cx1,cy1,cx2,cy2 in clips
        ) if clips else False

        if not contained:
            # Compute per-side clip intervals: only the portions of each wall
            # surface that are inside a later room's XY footprint are removed.
            # This preserves the rest of the wall ("broken box") instead of
            # discarding the entire side.
            side_clips: Dict[str, list] = {}
            for cx1,cy1,cx2,cy2 in clips:
                if cx1 < room.x1 < cx2:
                    ylo = max(room.y1, cy1); yhi = min(room.y2, cy2)
                    if ylo < yhi:
                        side_clips.setdefault('wx1', []).append((ylo, yhi))
                if cx1 < room.x2 < cx2:
                    ylo = max(room.y1, cy1); yhi = min(room.y2, cy2)
                    if ylo < yhi:
                        side_clips.setdefault('wx2', []).append((ylo, yhi))
                if cy1 < room.y1 < cy2:
                    xlo = max(room.x1, cx1); xhi = min(room.x2, cx2)
                    if xlo < xhi:
                        side_clips.setdefault('wy1', []).append((xlo, xhi))
                if cy1 < room.y2 < cy2:
                    xlo = max(room.x1, cx1); xhi = min(room.x2, cx2)
                    if xlo < xhi:
                        side_clips.setdefault('wy2', []).append((xlo, xhi))

            # Never clip a wall segment that contains a door opening —
            # the player must always be able to pass through the bridge.
            for door in room_doors.get(room.idx, []):
                w_name = door['wall']
                if w_name not in side_clips:
                    continue
                # Door spans [center-hw, center+hw] along the wall's variable axis
                dlo = door['center'] - door['hw']
                dhi = door['center'] + door['hw']
                preserved = []
                for clo, chi in side_clips[w_name]:
                    if clo < dlo:
                        preserved.append((clo, min(chi, dlo)))
                    if chi > dhi:
                        preserved.append((max(clo, dhi), chi))
                side_clips[w_name] = preserved

            parts, bi = room_walls(room.x1,room.y1,room.z1, room.x2,room.y2,room.z2,
                                   room.wall_t, f"r{room.idx}", bi,
                                   doors=room_doors.get(room.idx),
                                   side_clips=side_clips)
            lines.extend(parts)
            # Wall-ramp wedges disabled — only directional ramps generated
            # if random.random() < 0.4:
            #     wr_parts, bi = _wallramp_brushes(room, bi)
            #     lines.extend(wr_parts)

    # ── Pass 3: ceilings ──────────────────────────────────────────────────────
    for room in rooms:
        clips = room_clips[room.idx]
        parts, bi = room_ceiling(room.x1,room.y1,room.z1, room.x2,room.y2,room.z2,
                                 room.ceil_t, f"r{room.idx}", bi, clips=clips)
        lines.extend(parts)

    # ── Pass 4: corridors / ramps ─────────────────────────────────────────────
    for br in bridges:
        ra = rooms[br.room_a]; rb = rooms[br.room_b]
        # Far-wall limits: how deep the ramp may extend into each room
        if br.axis == 'x':
            ra_far = ra.x1 if br.ax >= ra.x2 - 1 else ra.x2
            rb_far = rb.x2 if br.bx <= rb.x1 + 1 else rb.x1
        else:
            ra_far = ra.y1 if br.ay >= ra.y2 - 1 else ra.y2
            rb_far = rb.y2 if br.by <= rb.y1 + 1 else rb.y1
        parts, bi = corridor_brushes(
            br.ax, br.ay, br.az,
            br.bx, br.by, br.bz,
            br.axis, br.floor_t, br.ceil_t, br.wall_t,
            door_hw=br.door_hw, door_ht=br.door_ht,
            ra_far=ra_far, rb_far=rb_far,
            tag=f"br{br.room_a}_{br.room_b}", bi=bi)
        lines.extend(parts)

    lines.append("}")  # end worldspawn

    # ── Entities ─────────────────────────────────────────────────────────────
    ei    = 1
    first = rooms[0]
    last  = rooms[-1]

    # --- spawn — place at entry edge of first room, minimal prerun distance
    # Determine exit wall from room_doors[0], spawn on opposite side facing exit.
    SL = 8   # slab thickness
    first_doors = room_doors.get(0, [])
    exit_wall = first_doors[0]['wall'] if first_doors else 'wx2'
    if exit_wall == 'wx2':     # exit right → spawn near left wall, face East
        spawn_x = first.x1 + 32; spawn_y = first.cy(); spawn_angle = "0"
        sx1 = first.x1 + 64;  sx2 = sx1 + SL; sy1 = first.y1; sy2 = first.y2
    elif exit_wall == 'wx1':   # exit left → spawn near right wall, face West
        spawn_x = first.x2 - 32; spawn_y = first.cy(); spawn_angle = "180"
        sx1 = first.x2 - 64 - SL; sx2 = sx1 + SL; sy1 = first.y1; sy2 = first.y2
    elif exit_wall == 'wy2':   # exit top → spawn near bottom wall, face North
        spawn_x = first.cx(); spawn_y = first.y1 + 32; spawn_angle = "90"
        sx1 = first.x1; sx2 = first.x2; sy1 = first.y1 + 64; sy2 = sy1 + SL
    else:                       # wy1: exit bottom → spawn near top wall, face South
        spawn_x = first.cx(); spawn_y = first.y2 - 32; spawn_angle = "270"
        sx1 = first.x1; sx2 = first.x2; sy1 = first.y2 - 64 - SL; sy2 = sy1 + SL
    spawn_z = first.z1 + 32
    lines.append(f"\n// entity {ei}")
    lines.append(ent_kv(classname="info_player_start",
                        origin=f"{spawn_x} {spawn_y} {spawn_z}",
                        angle=spawn_angle))
    ei += 1

    # --- trigger_startTimer — thin line slab perpendicular to travel axis.
    # Placed just 8 units in front of spawn — essentially zero prerun zone.
    lines.append(f"\n// entity {ei}")
    lines.append(ent_brush_box("trigger_multiple",
        sx1, sy1, first.z1,
        sx2, sy2, first.z2,
        target="target_startTimer"))
    ei += 1

    # --- target_startTimer
    lines.append(f"\n// entity {ei}")
    lines.append(ent_kv(classname="target_startTimer",
                        origin=f"{(sx1+sx2)//2} {(sy1+sy2)//2} {first.z1 + first.h // 2}",
                        targetname="target_startTimer"))
    ei += 1

    # --- trigger_stopTimer — thin line slab at exit edge of last room
    if last.travel_axis == 'x':
        ex1 = last.x2 - SL;  ex2 = last.x2
        ey1 = last.y1;         ey2 = last.y2
    else:
        ex1 = last.x1;         ex2 = last.x2
        ey1 = last.y2 - SL;   ey2 = last.y2
    lines.append(f"\n// entity {ei}")
    lines.append(ent_brush_box("trigger_multiple",
        ex1, ey1, last.z1,
        ex2, ey2, last.z2,
        target="target_stopTimer"))
    ei += 1

    # --- target_stopTimer
    lines.append(f"\n// entity {ei}")
    lines.append(ent_kv(classname="target_stopTimer",
                        origin=f"{last.cx()} {last.cy()} {last.z1 + last.h // 2}",
                        targetname="target_stopTimer"))
    ei += 1

    # --- checkpoints — one every 10 rooms (rooms 10, 20, 30, …)
    if cfg.get("checkpoints", True):
        cp_num = 0
        for cp_n, room in enumerate(rooms[1:-1], start=1):
            if cp_n % 10 != 0:
                continue
            cp_num += 1
            tname = f"target_checkpoint_{cp_n}"
            if room.travel_axis == 'x':
                tx1 = room.x1;       tx2 = room.x1 + SL
                ty1 = room.y1;       ty2 = room.y2
            else:
                tx1 = room.x1;       tx2 = room.x2
                ty1 = room.y1;       ty2 = room.y1 + SL
            lines.append(f"\n// entity {ei}")
            lines.append(ent_brush_box("trigger_multiple",
                tx1, ty1, room.z1,
                tx2, ty2, room.z2,
                target=tname))
            ei += 1
            lines.append(f"\n// entity {ei}")
            lines.append(ent_kv(classname="target_checkpoint",
                                origin=f"{room.cx()} {room.cy()} {room.z1 + room.h // 2}",
                                targetname=tname,
                                count=str(cp_n)))
            ei += 1

    return "\n".join(lines), rooms, bridges

# ══════════════════════════════════════════════════════════════════════════════
#  3D VIEWER
# ══════════════════════════════════════════════════════════════════════════════
class Viewer3D(tk.Canvas):
    """
    Lightweight isometric/perspective wireframe viewer for Room + Bridge lists.
    Mouse drag → rotate   |   scroll → zoom   |   preset buttons → snap views
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
        # WASD pan offsets (screen-space pixels)
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
        # grab keyboard focus on click so WASD works immediately
        self.bind("<ButtonPress-1>",  lambda e: (self.focus_set(), self._on_press(e)))
        self.bind("<KeyPress>",       self._on_key_press)
        self.bind("<KeyRelease>",     self._on_key_release)

        self._wasd_start()

    # ── WASD camera ───────────────────────────────────────────────────────────
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

    # ── public API ────────────────────────────────────────────────────────────
    def load(self, rooms: List[Room], bridges: List[Bridge]):
        self._rooms   = rooms
        self._bridges = bridges
        self._pan_x   = 0.0
        self._pan_y   = 0.0
        self._fit()
        self._draw()

    def set_preset(self, name: str):
        elev, azim = self.PRESETS.get(name, (30.0, 45.0))
        self._elev = elev
        self._azim = azim
        self._draw()

    # ── internal ──────────────────────────────────────────────────────────────
    def _fit(self):
        """Reset zoom so the whole map fits the canvas."""
        if not self._rooms:
            return
        xs = [r.x1 for r in self._rooms] + [r.x2 for r in self._rooms]
        ys = [r.y1 for r in self._rooms] + [r.y2 for r in self._rooms]
        zs = [r.z1 for r in self._rooms] + [r.z2 for r in self._rooms]
        span = max(max(xs)-min(xs), max(ys)-min(ys), max(zs)-min(zs), 1)
        W = self.winfo_width()  or 400
        H = self.winfo_height() or 400
        self._zoom = min(W, H) * 0.55 / span
        self._cx3d = (min(xs)+max(xs)) / 2
        self._cy3d = (min(ys)+max(ys)) / 2
        self._cz3d = (min(zs)+max(zs)) / 2

    def _project(self, x, y, z) -> Tuple[float, float]:
        """3-D → 2-D via rotation matrix (elev / azim) + isometric projection."""
        # centre on map centroid
        x -= self._cx3d
        y -= self._cy3d
        z -= self._cz3d

        az = math.radians(self._azim)
        el = math.radians(self._elev)

        # rotate around Z (azimuth)
        xr =  x * math.cos(az) + y * math.sin(az)
        yr = -x * math.sin(az) + y * math.cos(az)
        zr =  z

        # rotate around new X (elevation)
        xf =  xr
        yf =  yr * math.cos(el) - zr * math.sin(el)
        zf =  yr * math.sin(el) + zr * math.cos(el)

        W = self.winfo_width()  or 400
        H = self.winfo_height() or 400
        sx = W / 2 + xf * self._zoom + self._pan_x
        sy = H / 2 - zf * self._zoom + self._pan_y
        return sx, sy

    def _box_edges(self, x1,y1,z1, x2,y2,z2):
        """Return list of (p2d_a, p2d_b) screen-coord pairs for a box."""
        corners = [
            (x1,y1,z1),(x2,y1,z1),(x2,y2,z1),(x1,y2,z1),
            (x1,y1,z2),(x2,y1,z2),(x2,y2,z2),(x1,y2,z2),
        ]
        proj = [self._project(*c) for c in corners]
        edges = [
            (0,1),(1,2),(2,3),(3,0),   # bottom face
            (4,5),(5,6),(6,7),(7,4),   # top face
            (0,4),(1,5),(2,6),(3,7),   # verticals
        ]
        return [(proj[a], proj[b]) for a,b in edges]

    def _draw(self):
        self.delete("all")
        W = self.winfo_width()
        H = self.winfo_height()
        if W < 10 or H < 10 or not self._rooms:
            if not self._rooms:
                self.create_text(W//2 if W>10 else 200,
                                 H//2 if H>10 else 150,
                                 text="Generate a map to see 3D view",
                                 fill=T["text_dim"],
                                 font=("Segoe UI", 11))
            return

        n = len(self._rooms)

        # depth-sort rooms by projected Z of centroid (painter's algorithm)
        def depth(r):
            _, sy = self._project(r.cx(), r.cy(), (r.z1+r.z2)/2)
            return sy
        sorted_rooms = sorted(self._rooms, key=depth, reverse=True)

        # draw bridges first (behind rooms)
        for br in self._bridges:
            hw = br.door_hw
            if br.axis == 'x':
                bx1,by1,bz1 = min(br.ax,br.bx), br.ay-hw, min(br.az,br.bz)
                bx2,by2,bz2 = max(br.ax,br.bx), br.ay+hw, min(br.az,br.bz)+DOOR_H
            else:
                bx1,by1,bz1 = br.ax-hw, min(br.ay,br.by), min(br.az,br.bz)
                bx2,by2,bz2 = br.ax+hw, max(br.ay,br.by), min(br.az,br.bz)+DOOR_H
            for pa, pb in self._box_edges(bx1,by1,bz1, bx2,by2,bz2):
                self.create_line(pa[0],pa[1],pb[0],pb[1],
                                 fill=T["corr_col"], width=1)

        # draw rooms
        for room in sorted_rooms:
            idx = room.idx
            if idx == 0:
                col, edge_col = T["start_col"], T["success"]
            elif idx == n - 1:
                col, edge_col = T["end_col"], T["accent"]
            else:
                # shade mid rooms by speed: faster = brighter blue
                t_speed = (room.speed_in - 550) / max(1, (550 + 60*n) - 550)
                t_speed = max(0.0, min(1.0, t_speed))
                # interpolate #1e3960 → #2a5a9e
                r_c = int(0x1e + t_speed*(0x2a-0x1e))
                g_c = int(0x39 + t_speed*(0x5a-0x39))
                b_c = int(0x60 + t_speed*(0x9e-0x60))
                col = f"#{r_c:02x}{g_c:02x}{b_c:02x}"
                edge_col = T["room_bdr"]

            edges = self._box_edges(room.x1,room.y1,room.z1,
                                    room.x2,room.y2,room.z2)
            # filled top face (stipple for transparency effect)
            top_pts = [
                self._project(room.x1,room.y1,room.z2),
                self._project(room.x2,room.y1,room.z2),
                self._project(room.x2,room.y2,room.z2),
                self._project(room.x1,room.y2,room.z2),
            ]
            flat_top = [c for pt in top_pts for c in pt]
            self.create_polygon(flat_top, fill=col,
                                outline=edge_col, width=1,
                                stipple="gray25")
            # wireframe edges
            for pa, pb in edges:
                self.create_line(pa[0],pa[1],pb[0],pb[1],
                                 fill=edge_col, width=1)

            # room number label at projected centroid
            sx, sy = self._project(room.cx(), room.cy(), room.z2)
            self.create_text(sx, sy-8, text=str(idx+1),
                             fill=T["text"], font=("Segoe UI", 7, "bold"))

        # compass / info
        self.create_text(8, 8,
            text=(f"elev={self._elev:.0f}°  azim={self._azim:.0f}°  zoom={self._zoom*100:.0f}%"
                  f"   WASD=pan  drag=rotate  scroll=zoom"),
            fill=T["text_dim"], font=("Consolas", 7), anchor="nw")

    # ── mouse interaction ─────────────────────────────────────────────────────
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


# ══════════════════════════════════════════════════════════════════════════════
#  GUI
# ══════════════════════════════════════════════════════════════════════════════
IMG_EXTS = {".jpg",".jpeg",".png",".bmp",".tga",".gif",".tiff"}

_CFG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "turnt_config.json")

def _load_app_cfg() -> dict:
    try:
        with open(_CFG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _save_app_cfg(data: dict):
    try:
        with open(_CFG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Turnt-o-mapper")
        self.configure(bg=T["bg"])
        self.minsize(860, 600)
        self.resizable(True, True)

        self._map_str        = ""
        self._last_map_path  = ""        # path of last saved .map (for launcher)
        self._rooms:   List[Room]   = []
        self._bridges: List[Bridge] = []

        app_cfg = _load_app_cfg()

        self._tex_folder = tk.StringVar(value="")
        self._out_path   = tk.StringVar(
            value=os.path.join(os.getcwd(), "generated.map"))
        self._game_exe   = tk.StringVar(value=app_cfg.get("game_exe", ""))
        self._tex_paths: Dict[str, str]    = {}
        self._thumb_refs: Dict[str, object] = {}

        self._floor_sel: Dict[str, tk.BooleanVar] = {}
        self._wall_sel:  Dict[str, tk.BooleanVar] = {}
        self._ceil_sel:  Dict[str, tk.BooleanVar] = {}

        self._build_styles()
        self._build_ui()
        self._randomize_seed(silent=True)
        self._log("Turnt-o-mapper ready. Configure and hit Generate!", "info")

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
        s.configure("H1.TLabel",      background=bg,  foreground=acc, font=("Segoe UI", 22, "bold"))
        s.configure("H2.TLabel",      background=bgp, foreground=acc, font=("Segoe UI", 10, "bold"))
        s.configure("H3.TLabel",      background=bgc, foreground=acc, font=("Segoe UI",  9, "bold"))
        s.configure("TNotebook",      background=bg,  borderwidth=0)
        s.configure("TNotebook.Tab",  background=bgp, foreground=dim, padding=[14, 7],  font=("Segoe UI", 9, "bold"))
        s.map("TNotebook.Tab", background=[("selected", bgc)], foreground=[("selected", acc)])
        s.configure("TCheckbutton",   background=bgp, foreground=txt, indicatorcolor=bgc, font=("Segoe UI", 9))
        s.map("TCheckbutton", indicatorcolor=[("selected", acc)])
        s.configure("TScale",         background=bgp, troughcolor=T["bg_input"], sliderthickness=13, sliderrelief="flat")
        s.configure("TEntry",         fieldbackground=T["bg_input"], foreground=txt, insertcolor=txt, bordercolor=brd, relief="flat", padding=5)
        s.configure("TSeparator",     background=brd)
        s.configure("Vertical.TScrollbar",background=brd, troughcolor=bg, bordercolor=bg, arrowcolor=dim, relief="flat")
        s.configure("Horizontal.TScrollbar", background=brd, troughcolor=bg, bordercolor=bg, arrowcolor=dim, relief="flat")

    # ── master layout ─────────────────────────────────────────────────────────
    def _build_ui(self):
        # Header
        hdr = tk.Frame(self, bg=T["bg_panel"])
        hdr.pack(fill="x")
        tk.Frame(hdr, bg=T["accent"], height=3).pack(fill="x")
        hdr_inner = tk.Frame(hdr, bg=T["bg_panel"], pady=12)
        hdr_inner.pack(fill="x", padx=18)
        tk.Label(hdr_inner, text="TURNT-O-MAPPER",
                 bg=T["bg_panel"], fg=T["text"],
                 font=("Segoe UI", 20, "bold")).pack(side="left")
        tk.Frame(hdr_inner, bg=T["accent"], width=2).pack(
            side="left", fill="y", padx=12, pady=2)
        tk.Label(hdr_inner, text="Turnt .map generator",
                 bg=T["bg_panel"], fg=T["text_dim"],
                 font=("Segoe UI", 9)).pack(side="left")

        body = ttk.Frame(self)
        body.pack(fill="both", expand=True, padx=12, pady=(8, 8))
        body.columnconfigure(0, weight=2, minsize=340)
        body.columnconfigure(1, weight=3)
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
        nb.add(t1, text="  Generate  ")
        nb.add(t2, text="  Textures  ")
        nb.add(t3, text="  Settings  ")

        self._tab_generate(t1)
        self._tab_textures(t2)
        self._tab_settings(t3)

        # ─ Tab: Generate ───────────────────────────────────────────────────
    def _tab_generate(self, p):
        # ── Rooms + seed (fixed top section, no scroll) ──────────────────────
        self._v_rooms = tk.IntVar(value=10)
        self._slider(p, "Number of rooms", self._v_rooms, 2, 100)

        # Seed row
        sr = ttk.Frame(p, style="P.TFrame")
        sr.pack(fill="x", pady=(2, 4))
        self._v_seed_lock = tk.BooleanVar(value=False)
        ttk.Checkbutton(sr, text="Lock seed",
                        variable=self._v_seed_lock,
                        command=self._toggle_seed).pack(side="left")
        self._v_seed = tk.IntVar(value=0)
        self._seed_spin = self._spinbox(sr, self._v_seed,
                                        0, 9_999_999, 1,
                                        state="disabled", pack=False)
        self._seed_spin.pack(side="left", padx=(8, 0))

        # Action buttons
        self._btn(p, "Generate map", self._on_generate,
                  color=T["accent"],
                  font=("Segoe UI", 11, "bold")).pack(fill="x", pady=(6, 4))
        r2 = ttk.Frame(p, style="P.TFrame")
        r2.pack(fill="x", pady=(0, 4))
        self._btn(r2, "Save .map", self._on_save,
                  color=T["success"]).pack(side="left", fill="x",
                                           expand=True, padx=(0, 4))
        self._btn(r2, "New seed", self._randomize_seed,
                  color=T["accent2"]).pack(side="left", fill="x", expand=True)
        self._launch_btn = self._btn(p, "Launch map in game",
                                     self._on_launch_game,
                                     color=T["warning"],
                                     font=("Segoe UI", 9, "bold"))
        self._launch_btn.pack(fill="x", pady=(0, 2))

        ttk.Separator(p, orient="horizontal").pack(fill="x", pady=(4, 0))

        # ── Scrollable parameters area ────────────────────────────────────────
        canvas = tk.Canvas(p, bg=T["bg_panel"], highlightthickness=0)
        vsb    = ttk.Scrollbar(p, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        inner = tk.Frame(canvas, bg=T["bg_panel"])
        win   = canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>",
                   lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>",
                    lambda e: canvas.itemconfig(win, width=e.width))
        for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            canvas.bind(seq, lambda e, c=canvas: c.yview_scroll(
                -1 if (e.delta > 0 or e.num == 4) else 1, "units"))
        q = inner

        # ── Room settings ─────────────────────────────────────────────────────
        self._sec(q, "Room settings")
        g = ttk.Frame(q, style="P.TFrame")
        g.pack(fill="x", pady=(0, 2))
        labels  = ["Min W", "Max W", "Min D", "Max D", "Min H", "Max H"]
        defvals = [ 384,    2048,     256,     768,     256,     640 ]
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
        tk.Label(q, text="Long side = travel axis  |  Short side = lateral sweep",
                 bg=T["bg_panel"], fg=T["text_dim"],
                 font=("Segoe UI", 7)).pack(anchor="w", pady=(0, 2))

        # Min door height + corridor width in one row
        dc = ttk.Frame(q, style="P.TFrame")
        dc.pack(fill="x", pady=(0, 4))
        dc.columnconfigure(0, weight=1)
        dc.columnconfigure(1, weight=2)
        df = ttk.Frame(dc, style="P.TFrame")
        df.grid(row=0, column=0, padx=(0, 6), sticky="ew")
        ttk.Label(df, text="Min door height (qu)", style="P.TLabel",
                  font=("Segoe UI", 7)).pack(anchor="w")
        self._v_door_h = tk.IntVar(value=128)
        self._spinbox(df, self._v_door_h, 64, 512, 32)
        cw_f = ttk.Frame(dc, style="P.TFrame")
        cw_f.grid(row=0, column=1, sticky="ew")
        ttk.Label(cw_f, text="Corridor width", style="P.TLabel",
                  font=("Segoe UI", 7)).pack(anchor="w")
        self._v_corr_frac = tk.DoubleVar(value=0.67)
        cw_lbl_var = tk.StringVar(value="67%")
        def _update_cw_lbl(*_):
            v = self._v_corr_frac.get()
            cw_lbl_var.set("100% (open)" if v >= 0.98 else f"{int(v*100)}%")
        self._v_corr_frac.trace_add("write", _update_cw_lbl)
        cw_inner = ttk.Frame(cw_f, style="P.TFrame")
        cw_inner.pack(fill="x")
        ttk.Scale(cw_inner, from_=0.25, to=1.0, variable=self._v_corr_frac,
                  orient="horizontal").pack(side="left", fill="x", expand=True)
        ttk.Label(cw_inner, textvariable=cw_lbl_var, style="Pd.TLabel",
                  font=("Segoe UI", 8)).pack(side="left", padx=(4, 0))

        # Checkboxes
        self._v_height = tk.BooleanVar(value=True)
        self._v_checks = tk.BooleanVar(value=True)
        self._v_autorand = tk.BooleanVar(value=True)
        for text, var in [
            ("Height variation between rooms", self._v_height),
            ("Add trigger_checkpoint entities", self._v_checks),
        ]:
            ttk.Checkbutton(q, text=text, variable=var).pack(anchor="w", pady=1)

        ttk.Separator(q, orient="horizontal").pack(fill="x", pady=(6, 2))

        # ── Physics ───────────────────────────────────────────────────────────
        self._sec(q, "Physics")
        # "Use acceleration model" toggle — when ON, room sizes are derived from
        # physics speed; when OFF, dimensions are drawn purely from min/max sliders.
        self._v_use_physics = tk.BooleanVar(value=False)
        phy_hdr = ttk.Frame(q, style="P.TFrame")
        phy_hdr.pack(fill="x", pady=(0, 4))
        tk.Checkbutton(
            phy_hdr, text="Use acceleration model",
            variable=self._v_use_physics,
            bg=T["bg_card"], fg=T["text"], selectcolor=T["bg_input"],
            activebackground=T["bg_card"], activeforeground=T["accent"],
            font=("Segoe UI", 8), anchor="w", relief="flat",
            command=self._toggle_physics,
        ).pack(side="left")
        pg = ttk.Frame(q, style="P.TFrame")
        pg.pack(fill="x", pady=(0, 4))
        pg.columnconfigure(0, weight=1)
        pg.columnconfigure(1, weight=1)
        phy_params = [
            ("Base speed (UPS)",      "_v_u_base",   550, 100, 2000, 10),
            ("Speed gain / room",     "_v_u_gain",    60,   0,  300,  5),
            ("Air time (×0.01 s)",    "_v_t_air",     68,  30,  150,  1),
            ("Strafe factor (×0.01)", "_v_strafe_f",  20,   5,   40,  1),
            ("Rooms per segment",     "_v_rpt",        3,   1,   10,  1),
        ]
        self._phy_widgets: list = []
        for row_i, (lbl, attr, dflt, lo, hi, inc) in enumerate(phy_params):
            r, c = divmod(row_i, 2)
            f = ttk.Frame(pg, style="P.TFrame")
            f.grid(row=r, column=c, padx=3, pady=2, sticky="ew")
            ttk.Label(f, text=lbl, style="P.TLabel",
                      font=("Segoe UI", 7)).pack(anchor="w")
            v = tk.IntVar(value=dflt)
            setattr(self, attr, v)
            sb = self._spinbox(f, v, lo, hi, inc)
            self._phy_widgets.append(sb)
        # start disabled (physics off by default)
        self._toggle_physics()

        ttk.Separator(q, orient="horizontal").pack(fill="x", pady=(6, 2))

        # ── Layout style (prominent) ──────────────────────────────────────────
        self._sec(q, "Layout style")
        self._v_layout = tk.StringVar(value="Zigzag")
        layouts = ["Linear", "Zigzag", "Snake", "Random", "Spiral", "Multilevel"]
        layout_grid = ttk.Frame(q, style="P.TFrame")
        layout_grid.pack(fill="x", pady=(0, 6))
        self._layout_btns: Dict[str, tk.Button] = {}

        def _select_layout(name):
            self._v_layout.set(name)
            for n, btn in self._layout_btns.items():
                btn.config(
                    bg=T["accent"] if n == name else T["bg_card"],
                    fg=T["btn_fg"] if n == name else T["text_dim"],
                    relief="flat")

        for col, name in enumerate(layouts):
            btn = tk.Button(
                layout_grid, text=name,
                bg=T["accent"] if name == "Zigzag" else T["bg_card"],
                fg=T["btn_fg"] if name == "Zigzag" else T["text_dim"],
                font=("Segoe UI", 8, "bold"),
                relief="flat", cursor="hand2", padx=4, pady=4,
                activebackground=T["lbx_sel"],
                command=lambda n=name: _select_layout(n))
            btn.grid(row=col // 3, column=col % 3, padx=2, pady=2, sticky="ew")
            layout_grid.columnconfigure(col % 3, weight=1)
            self._layout_btns[name] = btn

    # ─ Tab: Textures ──────────────────────────────────────────────────
    def _tab_textures(self, p):
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

        # ─ Tab: Settings ───────────────────────────────────────────────────
    def _tab_settings(self, p):
        def _path_row(parent, label, var, browse_cmd):
            self._sec(parent, label)
            row = ttk.Frame(parent, style="P.TFrame")
            row.pack(fill="x", pady=(0, 8))
            ttk.Entry(row, textvariable=var,
                      font=("Consolas", 8)).pack(side="left", fill="x", expand=True)
            self._btn(row, "…", browse_cmd, w=4,
                      color=T["accent2"]).pack(side="left", padx=(6, 0))

        # ── Output file ───────────────────────────────────────────────────────
        _path_row(p, "Output .map file", self._out_path, self._browse_out)

        # ── Texture folder ────────────────────────────────────────────────────
        _path_row(p, "Texture folder (for preview)", self._tex_folder,
                  self._browse_tex_folder)

        # ── Game folder ───────────────────────────────────────────────────────
        _path_row(p, "Game executable", self._game_exe, self._browse_game_exe)

        # ── Generation ────────────────────────────────────────────────────────
        self._sec(p, "Generation")
        ttk.Checkbutton(p, text="Auto-randomize seed after each generation",
                        variable=self._v_autorand).pack(anchor="w", pady=2)

    # ── RIGHT PANEL ───────────────────────────────────────────────────────────
    def _build_right(self, p):
        # ── top section: tabbed previews (2D + 3D)
        pc = ttk.Frame(p, style="P.TFrame")
        pc.grid(row=0, column=0, sticky="nsew", pady=(0, 6))
        pc.rowconfigure(2, weight=1)
        pc.columnconfigure(0, weight=1)

        ph = ttk.Frame(pc, style="P.TFrame", padding=(10, 4))
        ph.grid(row=0, column=0, sticky="ew")
        ttk.Label(ph, text="MAP PREVIEW", style="H2.TLabel").pack(side="left")
        self._lbl_stats = ttk.Label(ph, text="", style="Pd.TLabel",
                                    font=("Segoe UI", 8))
        self._lbl_stats.pack(side="right")

        # Legend row
        leg = tk.Frame(pc, bg=T["bg_panel"], padx=10, pady=2)
        leg.grid(row=1, column=0, sticky="ew")
        for color, label in [
            (T["start_col"], "Start"),
            (T["room_col"],  "Room"),
            (T["end_col"],   "End"),
            (T["corr_col"],  "Corridor"),
        ]:
            tk.Label(leg, bg=color, width=2, relief="flat").pack(side="left")
            tk.Label(leg, text=f" {label}   ",
                     bg=T["bg_panel"], fg=T["text_dim"],
                     font=("Segoe UI", 7)).pack(side="left")

        # Notebook for 2D / 3D tabs
        view_nb = ttk.Notebook(pc)
        view_nb.grid(row=2, column=0, sticky="nsew", padx=6, pady=(0, 6))

        # -- 2D tab
        tab2d = ttk.Frame(view_nb, style="P.TFrame")
        view_nb.add(tab2d, text="  2D  ")
        tab2d.rowconfigure(1, weight=1)
        tab2d.columnconfigure(0, weight=1)

        # 2D controls bar
        bar2d = ttk.Frame(tab2d, style="P.TFrame", padding=(4, 2))
        bar2d.grid(row=0, column=0, sticky="ew")
        self._btn(bar2d, "Fit", self._2d_fit,
                  color=T["accent2"], font=("Segoe UI", 8, "bold"), pady=2
                  ).pack(side="left", padx=2)
        tk.Label(bar2d, text="  scroll=zoom  drag=pan  dbl-click=fit",
                 bg=T["bg_panel"], fg=T["text_dim"],
                 font=("Segoe UI", 7)).pack(side="left", padx=6)

        self._canvas = tk.Canvas(tab2d, bg=T["prev_bg"],
                                 highlightthickness=0)
        self._canvas.grid(row=1, column=0, sticky="nsew")
        self._canvas.bind("<Configure>",     lambda e: self._redraw())
        # Zoom
        self._canvas.bind("<MouseWheel>",    self._2d_on_scroll)
        self._canvas.bind("<Button-4>",      self._2d_on_scroll)
        self._canvas.bind("<Button-5>",      self._2d_on_scroll)
        # Pan
        self._canvas.bind("<ButtonPress-1>",   self._2d_pan_start)
        self._canvas.bind("<B1-Motion>",       self._2d_pan_move)
        # Fit on double-click
        self._canvas.bind("<Double-Button-1>", lambda e: self._2d_fit())
        # 2D pan/zoom state
        self._2d_zoom  = 1.0
        self._2d_pan_x = 0.0
        self._2d_pan_y = 0.0
        self._2d_drag_x = 0
        self._2d_drag_y = 0

        # -- 3D tab
        tab3d = ttk.Frame(view_nb, style="P.TFrame")
        view_nb.add(tab3d, text="  3D  ")
        tab3d.rowconfigure(1, weight=1)
        tab3d.columnconfigure(0, weight=1)

        # preset buttons bar
        btn_bar = ttk.Frame(tab3d, style="P.TFrame", padding=(4,3))
        btn_bar.grid(row=0, column=0, sticky="ew")
        self._viewer3d = Viewer3D(tab3d)
        self._viewer3d.grid(row=1, column=0, sticky="nsew")

        for preset_name in ("Iso", "Top", "Front", "Side"):
            self._btn(btn_bar, preset_name,
                      lambda n=preset_name: self._viewer3d.set_preset(n),
                      color=T["accent2"],
                      font=("Segoe UI", 8, "bold"), pady=2
                      ).pack(side="left", padx=2)
        tk.Label(btn_bar,
                 text="  drag=rotate  scroll=zoom  WASD=pan (click 3D first)",
                 bg=T["bg_panel"], fg=T["text_dim"],
                 font=("Segoe UI", 7)).pack(side="left", padx=6)

        # switch to 3D tab when map is generated (bind notebook tab change)
        view_nb.bind("<<NotebookTabChanged>>",
                     lambda e: self._on_tab_change(view_nb))
        self._view_nb = view_nb

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

    def _on_tab_change(self, nb):
        """Refresh 3D viewer when its tab is activated."""
        try:
            if nb.tab(nb.select(), "text").strip() == "3D" and self._rooms:
                self._viewer3d.load(self._rooms, self._bridges)
        except Exception:
            pass

    # ── 2D zoom/pan ───────────────────────────────────────────────────────────
    def _2d_on_scroll(self, e):
        if e.num == 4 or e.delta > 0:
            factor = 1.15
        else:
            factor = 1.0 / 1.15
        self._2d_zoom = max(0.05, min(self._2d_zoom * factor, 80.0))
        self._redraw()

    def _2d_pan_start(self, e):
        self._2d_drag_x = e.x
        self._2d_drag_y = e.y

    def _2d_pan_move(self, e):
        dx = e.x - self._2d_drag_x
        dy = e.y - self._2d_drag_y
        self._2d_pan_x += dx
        self._2d_pan_y += dy
        self._2d_drag_x = e.x
        self._2d_drag_y = e.y
        self._redraw()

    def _2d_fit(self):
        """Reset zoom/pan so the whole map fits the canvas."""
        self._2d_zoom  = 1.0
        self._2d_pan_x = 0.0
        self._2d_pan_y = 0.0
        self._redraw()

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

    def _toggle_physics(self):
        st = "normal" if self._v_use_physics.get() else "disabled"
        for sb in self._phy_widgets:
            sb.config(state=st)

    def _toggle_seed(self):
        st = "normal" if self._v_seed_lock.get() else "disabled"
        self._seed_spin.config(state=st)

    def _randomize_seed(self, silent=False):
        if self._v_seed_lock.get():
            return  # don't override a locked seed
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

    def _browse_game_exe(self):
        p = filedialog.askopenfilename(
            title="Select game executable",
            filetypes=[("Executable", "*.exe *.sh *.app"), ("All", "*.*")])
        if p:
            self._game_exe.set(p)
            _save_app_cfg({"game_exe": p})

    def _on_launch_game(self):
        exe  = self._game_exe.get().strip()
        path = self._last_map_path or self._out_path.get()
        if not exe:
            self._log("Set the game executable path first.", "warn")
            return
        if not path or not os.path.isfile(path):
            self._log("Save a map first (or generate + auto-save).", "warn")
            return
        try:
            cmd = [exe, "--", f"--import={path}"]
            subprocess.Popen(cmd)
            self._log(f"Launched: {' '.join(cmd)}", "info")
        except Exception as ex:
            self._log(f"Launch failed: {ex}", "error")

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
        global DOOR_H
        DOOR_H = self._v_door_h.get()
        return {
            "n_rooms":      self._v_rooms.get(),
            # room size clamp limits
            "min_w":        self._sz["Min W"].get(),
            "max_w":        self._sz["Max W"].get(),
            "min_d":        self._sz["Min D"].get(),
            "max_d":        self._sz["Max D"].get(),
            "min_h":        self._sz["Min H"].get(),
            "max_h":        self._sz["Max H"].get(),
            # physics
            "use_physics":  self._v_use_physics.get(),
            "u_base":       float(self._v_u_base.get()),
            "u_gain":       float(self._v_u_gain.get()),
            "t_air":        self._v_t_air.get() / 100.0,
            "strafe_f":     self._v_strafe_f.get() / 100.0,
            # layout
            "rooms_per_turn": self._v_rpt.get(),
            "layout_style":   self._v_layout.get(),
            # misc
            "seed":         self._v_seed.get() if self._v_seed_lock.get() else None,
            "map_name":     "turnt_map",
            "height_var":   self._v_height.get(),
            "checkpoints":  self._v_checks.get(),
            "corridor_width_frac": self._v_corr_frac.get(),
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
                if errs:
                    for e in errs: self._log(e, "warn")
                    return

                u_end = cfg["u_base"] + (cfg["n_rooms"]-1) * cfg["u_gain"]
                self._log(
                    f"Generating {cfg['n_rooms']} rooms | "
                    f"u: {cfg['u_base']:.0f}→{u_end:.0f} UPS | "
                    f"layout: {cfg['layout_style']} | seed {cfg['seed']}…",
                    "info")
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
                self.after(0, lambda: self._viewer3d.load(self._rooms, self._bridges))

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
            self._last_map_path = path
            self._log(f"{'Saved' if manual else 'Auto-saved'}: {path}", "info")
        except Exception as e:
            self._log(f"Save error: {e}", "error")

        # ── Preview canvas (2D) ───────────────────────────────────────────────────
    def _redraw(self):
        c = self._canvas
        c.delete("all")
        W, H = c.winfo_width(), c.winfo_height()
        if W < 10 or H < 10:
            return
        if not self._rooms:
            c.create_text(W//2, H//2,
                          text="Press Generate map to see preview",
                          fill=T["text_dim"],
                          font=("Segoe UI", 12), justify="center")
            return

        rooms   = self._rooms
        bridges = self._bridges
        all_x = [r.x1 for r in rooms] + [r.x2 for r in rooms]
        all_y = [r.y1 for r in rooms] + [r.y2 for r in rooms]
        mx, my = min(all_x), min(all_y)
        rw = max(all_x) - mx
        rh = max(all_y) - my

        PAD = 44
        sc_base = min((W - PAD*2 - 24) / max(rw, 1),
                      (H - PAD*2 - 20) / max(rh, 1))
        sc = sc_base * self._2d_zoom

        # Pan offset: 0,0 centres the map at zoom=1; user pan shifts from there
        cx_base = PAD + self._2d_pan_x
        cy_base = H - PAD + self._2d_pan_y

        def tx(v): return cx_base + (v - mx) * sc
        def ty(v): return cy_base - (v - my) * sc

        # Z range for height colour coding
        all_z   = [r.z1 for r in rooms]
        z_min   = min(all_z)
        z_max   = max(all_z)
        z_range = max(z_max - z_min, 1)

        # Build per-room wall→(center,hw) table for arrow drawing
        room_exits: Dict[int, list] = {}   # room_idx → [(wall, center, hw), …]
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

        # ── Rooms ─────────────────────────────────────────────────────────────
        n = len(rooms)
        for i, room in enumerate(rooms):
            if i == 0:
                fill, bdr = T["start_col"], T["success"]
            elif i == n - 1:
                fill, bdr = T["end_col"], T["accent"]
            else:
                # Blue-cyan gradient — by speed when physics enabled, flat otherwise
                if self._v_use_physics.get():
                    t_s = (room.speed_in - 550) / max(1, 60 * n)
                    t_s = max(0.0, min(1.0, t_s))
                else:
                    t_s = 0.0
                t_z = (room.z1 - z_min) / z_range
                r_c = max(0, min(255, int(0x1e + t_s*(0x18-0x1e))))
                g_c = max(0, min(255, int(0x3a + t_s*(0x70-0x3a) + t_z*0x35)))
                b_c = max(0, min(255, int(0x62 + t_s*(0x90-0x62))))
                fill = f"#{r_c:02x}{g_c:02x}{b_c:02x}"
                bdr  = T["room_bdr"]

            # Screen coords — ty flips Y so larger world-Y is higher on screen
            ls = tx(room.x1); rs = tx(room.x2)
            ts = ty(room.y2); bs = ty(room.y1)   # top-screen = max world-Y
            c.create_rectangle(ls, ts, rs, bs,
                               fill=fill, outline=bdr, width=2)

            pw = rs - ls   # pixel width
            ph = bs - ts   # pixel height
            cxs = (ls + rs) / 2
            cys = (ts + bs) / 2
            fs  = max(7, min(14, int(min(pw, ph) / 4)))

            # ── Room number — top-left ─────────────────────────────────────
            c.create_text(ls + 4, ts + 3,
                          text=str(i+1),
                          fill="white",
                          font=("Segoe UI", max(8, fs), "bold"),
                          anchor="nw")

            # ── Z height — top-right ───────────────────────────────────────
            z_label = f"z{room.z1:+d}" if room.z1 != 0 else "z0"
            c.create_text(rs - 4, ts + 3,
                          text=z_label,
                          fill="#7fb8d0",
                          font=("Consolas", max(6, fs-2)),
                          anchor="ne")

            # ── Speed — bottom-left (only when physics model is active) ───
            if self._v_use_physics.get():
                c.create_text(ls + 4, bs - 3,
                              text=f"{room.speed_in:.0f}u",
                              fill=T["accent2"],
                              font=("Segoe UI", max(6, fs-2), "bold"),
                              anchor="sw")

            # ── Exit / entry arrows on door walls ─────────────────────────
            exits = room_exits.get(i, [])
            AW = max(2, int(min(pw, ph) * 0.05))

            for wall_name, center, hw in exits:
                # Classify: exits are walls where a lower-indexed room connects out
                is_exit = any(
                    br.room_a == i
                    for br in bridges
                    if (br.axis == 'x' and br.ay == center and wall_name in ('wx1','wx2')) or
                       (br.axis == 'y' and br.ax == center and wall_name in ('wy1','wy2'))
                )
                arrow_col = "#ffdd33" if is_exit else "#66aacc"
                a_w = AW if is_exit else max(1, AW-1)

                if wall_name == 'wx2':        # right wall →
                    cx_d = rs; cy_d = ty(center)
                    c.create_line(cxs, cys, cx_d, cy_d,
                                  fill=arrow_col, width=a_w,
                                  arrow="last", arrowshape=(9,11,4))
                elif wall_name == 'wx1':      # left wall ←
                    cx_d = ls; cy_d = ty(center)
                    c.create_line(cxs, cys, cx_d, cy_d,
                                  fill=arrow_col, width=a_w,
                                  arrow="last", arrowshape=(9,11,4))
                elif wall_name == 'wy2':      # back wall (high Y) ↑ on screen
                    cx_d = tx(center); cy_d = ts
                    c.create_line(cxs, cys, cx_d, cy_d,
                                  fill=arrow_col, width=a_w,
                                  arrow="last", arrowshape=(9,11,4))
                elif wall_name == 'wy1':      # front wall (low Y) ↓ on screen
                    cx_d = tx(center); cy_d = bs
                    c.create_line(cxs, cys, cx_d, cy_d,
                                  fill=arrow_col, width=a_w,
                                  arrow="last", arrowshape=(9,11,4))

        # ── Z-height scale bar (right edge) ───────────────────────────────────
        if z_min != z_max:
            sx = W - 18
            for py in range(int(PAD), int(H - PAD)):
                t = 1.0 - (py - PAD) / max(H - PAD*2, 1)
                gv = int(0x28 + t * 0x88)
                c.create_line(sx, py, sx+10, py,
                              fill=f"#1e{gv:02x}60")
            c.create_text(sx+5, PAD-2,   text=f"+{z_max}",
                          fill=T["text_dim"], font=("Consolas", 7), anchor="s")
            c.create_text(sx+5, H-PAD+2, text=f"{z_min}",
                          fill=T["text_dim"], font=("Consolas", 7), anchor="n")

        # ── Legend ────────────────────────────────────────────────────────────
        items = [("■ Start", T["success"]), ("■ Rooms", T["room_col"]),
                 ("■ End",   T["accent"]),  ("━ Bridge", T["corr_col"]),
                 ("→ Exit", "#ffdd33"),     ("→ Entry", "#66aacc")]
        for j, (txt, col) in enumerate(items):
            c.create_text(PAD + j*88, H-13, text=txt,
                          fill=col, font=("Segoe UI", 8), anchor="w")


# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    app = App()
    app.mainloop()