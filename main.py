#!/usr/bin/env python3
"""
Turnt-o-mator — Quake 3 / Turnt Defrag Map Generator
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
    ox1,oy1,oz1 = x1-H, y1-H, z1-H
    ox2,oy2,oz2 = x2+H, y2+H, z2+H
    parts = []

    door_map = {}
    if doors:
        for d in doors:
            door_map.setdefault(d['wall'], []).append(d)

    has_door = set(door_map.keys())

    def rb(ax1,ay1,az1, ax2,ay2,az2,
           nx=wall_t,px=wall_t,ny=wall_t,py=wall_t,nz=floor_t,pz=floor_t, lbl=""):
        """All faces get real textures — no caulk hiding faces from visibility."""
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
        # section below door opening (floor thickness to door base)
        if z_b > bz1:
            rb(bx1, by1, bz1, bx2, by2, z_b, lbl=f"{wall_name}_bot", **face_kw)
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
        # section below door opening
        if z_b > bz1:
            rb(bx1, by1, bz1, bx2, by2, z_b, lbl=f"{wall_name}_bot", **face_kw)
        if z_t < bz2:
            rb(bx1,   by1, z_t, bx2,   by2, bz2,  lbl=f"{wall_name}_top", **face_kw)
        if xc - hw > bx1:
            rb(bx1,   by1, z_b, xc-hw, by2, z_t,  lbl=f"{wall_name}_l",   **face_kw)
        if xc + hw < bx2:
            rb(xc+hw, by1, z_b, bx2,   by2, z_t,  lbl=f"{wall_name}_r",   **face_kw)

    # Floor and ceiling — inner footprint only (no XY extension) to avoid
    # Z-fighting with neighbouring room brushes at the shared boundary plane.
    rb(x1,y1,oz1, x2,y2,z1,
       nx=floor_t,px=floor_t,ny=floor_t,py=floor_t,nz=floor_t,pz=floor_t,
       lbl="floor")
    rb(x1,y1,z2, x2,y2,oz2,
       nx=ceil_t,px=ceil_t,ny=ceil_t,py=ceil_t,nz=ceil_t,pz=ceil_t,
       lbl="ceil")

    # Walls extend the full Z range (oz1→oz2) so they cover floor+ceiling
    # thickness under their own footprint — no separate corner brushes needed.
    # On door sides the outer caulk shell is collapsed to zero thickness to
    # prevent co-planar face overlap with the corridor brushes.
    wx1_outer_x2 = x1  if 'wx1' in has_door else ox1
    wx2_outer_x1 = x2  if 'wx2' in has_door else ox2
    wy1_outer_y2 = y1  if 'wy1' in has_door else oy1
    wy2_outer_y1 = y2  if 'wy2' in has_door else oy2

    wall_y(ox1,          wx1_outer_x2, y1,y2, oz1,oz2, 'wx1',
           nx=wall_t,px=wall_t,ny=wall_t,py=wall_t,nz=wall_t,pz=wall_t)
    wall_y(wx2_outer_x1, ox2,          y1,y2, oz1,oz2, 'wx2',
           nx=wall_t,px=wall_t,ny=wall_t,py=wall_t,nz=wall_t,pz=wall_t)
    wall_x(ox1,ox2, oy1,          wy1_outer_y2, oz1,oz2, 'wy1',
           nx=wall_t,px=wall_t,ny=wall_t,py=wall_t,nz=wall_t,pz=wall_t)
    wall_x(ox1,ox2, wy2_outer_y1, oy2,          oz1,oz2, 'wy2',
           nx=wall_t,px=wall_t,ny=wall_t,py=wall_t,nz=wall_t,pz=wall_t)

    return parts, bi

def _ramp_brushes(x0, y0, z0, x1, y1, z1,
                   axis, hw, floor_t, ceil_t, wall_t,
                   tag, bi):
    """Ramp corridor between two Z-different endpoints.

    Floor = angled wedge brush.  Ceiling = matching inverted wedge.
    Side walls are axis-aligned boxes enclosing the passage.
    All visible faces carry real textures (no caulk hiding).
    """
    H   = WALL_T
    parts = []

    if axis == 'x':
        if x0 > x1:
            x0,x1 = x1,x0; z0,z1 = z1,z0
        xmn, xmx = x0 + H, x1 - H          # trim to avoid room-shell overlap
        if xmn >= xmx:
            return parts, bi
        cy = (y0 + y1) // 2
        z_lo, z_hi = (z0, z1) if z0 <= z1 else (z1, z0)
        going_up   = (z1 >= z0)
    else:
        if y0 > y1:
            y0,y1 = y1,y0; z0,z1 = z1,z0
        ymn, ymx = y0 + H, y1 - H
        if ymn >= ymx:
            return parts, bi
        cx = (x0 + x1) // 2
        z_lo, z_hi = (z0, z1) if z0 <= z1 else (z1, z0)
        going_up   = (z1 >= z0)

    ceil_top = z_hi + DOOR_H

    def cb(ax1,ay1,az1, ax2,ay2,az2,
           nx=wall_t,px=wall_t,ny=wall_t,py=wall_t,nz=ceil_t,pz=floor_t, lbl=""):
        nonlocal bi
        if ax1>=ax2 or ay1>=ay2 or az1>=az2:
            return
        fs = box_faces(ax1,ay1,az1,ax2,ay2,az2, nx,px,ny,py,nz,pz)
        parts.append(write_brush(fs, f"brush {bi} {tag}_{lbl}"))
        bi += 1

    def wedge_x(xlo, xhi, ylo, yhi, zlo, zhi, f_tex, lbl):
        """Floor wedge: surface rises from zlo@xlo to zhi@xhi."""
        nonlocal bi
        bot = z_lo - H
        f1 = face((xlo,ylo,bot),(xhi,ylo,bot),(xlo,yhi,bot),
                  f_tex, (-1,0,0),0,(0,-1,0),0)
        f2 = face((xlo,ylo,zlo),(xlo,yhi,zlo),(xhi,ylo,zhi),
                  f_tex, (0,1,0),0,(0,0,-1),0)
        f3 = face((xlo,ylo,bot),(xlo,ylo,zlo),(xlo,yhi,bot),
                  wall_t, (0,1,0),0,(0,0,-1),0)
        f4 = face((xhi,yhi,bot),(xhi,yhi,zhi),(xhi,ylo,bot),
                  wall_t, (0,-1,0),0,(0,0,-1),0)
        f5 = face((xlo,ylo,bot),(xhi,ylo,bot),(xhi,ylo,zhi),
                  wall_t, (-1,0,0),0,(0,0,-1),0)
        f6 = face((xlo,yhi,bot),(xlo,yhi,zlo),(xhi,yhi,bot),
                  wall_t, (1,0,0),0,(0,0,-1),0)
        parts.append(write_brush([f1,f2,f3,f4,f5,f6], f"brush {bi} {tag}_{lbl}"))
        bi += 1

    def wedge_x_ceil(xlo, xhi, ylo, yhi, zlo, zhi, c_tex, lbl):
        """Ceiling wedge: underside drops from zhi@xlo to zlo@xhi (mirror of floor)."""
        nonlocal bi
        top = z_hi + DOOR_H + H
        # slope plane normal points downward into the solid
        f1 = face((xlo,ylo,top),(xlo,yhi,top),(xhi,ylo,top),
                  c_tex, (-1,0,0),0,(0,-1,0),0)
        f2 = face((xlo,ylo,zhi),(xhi,ylo,zlo),(xlo,yhi,zhi),
                  c_tex, (0,1,0),0,(0,0,-1),0)
        f3 = face((xlo,ylo,top),(xlo,yhi,top),(xlo,ylo,zhi),
                  wall_t, (0,1,0),0,(0,0,-1),0)
        f4 = face((xhi,yhi,top),(xhi,ylo,top),(xhi,yhi,zlo),
                  wall_t, (0,-1,0),0,(0,0,-1),0)
        f5 = face((xlo,ylo,top),(xlo,ylo,zhi),(xhi,ylo,top),
                  wall_t, (-1,0,0),0,(0,0,-1),0)
        f6 = face((xlo,yhi,top),(xhi,yhi,top),(xlo,yhi,zhi),
                  wall_t, (1,0,0),0,(0,0,-1),0)
        parts.append(write_brush([f1,f2,f3,f4,f5,f6], f"brush {bi} {tag}_{lbl}"))
        bi += 1

    def wedge_y(ylo, yhi, xlo, xhi, zlo, zhi, f_tex, lbl):
        """Floor wedge: surface rises from zlo@ylo to zhi@yhi."""
        nonlocal bi
        bot = z_lo - H
        f1 = face((xlo,ylo,bot),(xhi,ylo,bot),(xlo,yhi,bot),
                  f_tex, (-1,0,0),0,(0,-1,0),0)
        f2 = face((xlo,ylo,zlo),(xhi,ylo,zlo),(xlo,yhi,zhi),
                  f_tex, (1,0,0),0,(0,0,-1),0)
        f3 = face((xlo,ylo,bot),(xlo,yhi,bot),(xlo,ylo,zlo),
                  wall_t, (0,-1,0),0,(0,0,-1),0)
        f4 = face((xhi,yhi,bot),(xhi,ylo,bot),(xhi,yhi,zhi),
                  wall_t, (0,1,0),0,(0,0,-1),0)
        f5 = face((xlo,ylo,bot),(xlo,ylo,zlo),(xhi,ylo,bot),
                  wall_t, (0,0,-1),0,(1,0,0),0)
        f6 = face((xlo,yhi,bot),(xhi,yhi,bot),(xlo,yhi,zhi),
                  wall_t, (0,0,1),0,(1,0,0),0)
        parts.append(write_brush([f1,f2,f3,f4,f5,f6], f"brush {bi} {tag}_{lbl}"))
        bi += 1

    def wedge_y_ceil(ylo, yhi, xlo, xhi, zlo, zhi, c_tex, lbl):
        """Ceiling wedge for Y-axis ramp."""
        nonlocal bi
        top = z_hi + DOOR_H + H
        f1 = face((xlo,ylo,top),(xlo,yhi,top),(xhi,ylo,top),
                  c_tex, (-1,0,0),0,(0,-1,0),0)
        f2 = face((xlo,ylo,zhi),(xlo,yhi,zlo),(xhi,ylo,zhi),
                  c_tex, (1,0,0),0,(0,0,-1),0)
        f3 = face((xlo,ylo,top),(xlo,ylo,zhi),(xlo,yhi,top),
                  wall_t, (0,-1,0),0,(0,0,-1),0)
        f4 = face((xhi,yhi,top),(xhi,yhi,zhi),(xhi,ylo,top),
                  wall_t, (0,1,0),0,(0,0,-1),0)
        f5 = face((xlo,ylo,top),(xhi,ylo,top),(xlo,ylo,zhi),
                  wall_t, (0,0,-1),0,(1,0,0),0)
        f6 = face((xlo,yhi,top),(xlo,yhi,zlo),(xhi,yhi,top),
                  wall_t, (0,0,1),0,(1,0,0),0)
        parts.append(write_brush([f1,f2,f3,f4,f5,f6], f"brush {bi} {tag}_{lbl}"))
        bi += 1

    if axis == 'x':
        if going_up:
            wedge_x(xmn, xmx, cy-hw, cy+hw, z_lo, z_hi, floor_t, "ramp_fl")
            wedge_x_ceil(xmn, xmx, cy-hw, cy+hw, z_lo+DOOR_H, z_hi+DOOR_H, ceil_t, "ramp_ce")
        else:
            wedge_x(xmn, xmx, cy-hw, cy+hw, z_hi, z_lo, floor_t, "ramp_fl")
            wedge_x_ceil(xmn, xmx, cy-hw, cy+hw, z_hi+DOOR_H, z_lo+DOOR_H, ceil_t, "ramp_ce")

        # side walls — full height so ramp is enclosed on both sides
        cb(xmn, cy-hw-H, z_lo-H, xmx, cy-hw,   ceil_top+H,
           nx=wall_t,px=wall_t,ny=wall_t,py=wall_t,nz=wall_t,pz=wall_t, lbl="w1")
        cb(xmn, cy+hw,   z_lo-H, xmx, cy+hw+H, ceil_top+H,
           nx=wall_t,px=wall_t,ny=wall_t,py=wall_t,nz=wall_t,pz=wall_t, lbl="w2")

    else:  # axis == 'y'
        if going_up:
            wedge_y(ymn, ymx, cx-hw, cx+hw, z_lo, z_hi, floor_t, "ramp_fl")
            wedge_y_ceil(ymn, ymx, cx-hw, cx+hw, z_lo+DOOR_H, z_hi+DOOR_H, ceil_t, "ramp_ce")
        else:
            wedge_y(ymn, ymx, cx-hw, cx+hw, z_hi, z_lo, floor_t, "ramp_fl")
            wedge_y_ceil(ymn, ymx, cx-hw, cx+hw, z_hi+DOOR_H, z_lo+DOOR_H, ceil_t, "ramp_ce")

        cb(cx-hw-H, ymn, z_lo-H, cx-hw,   ymx, ceil_top+H,
           nx=wall_t,px=wall_t,ny=wall_t,py=wall_t,nz=wall_t,pz=wall_t, lbl="w1")
        cb(cx+hw,   ymn, z_lo-H, cx+hw+H, ymx, ceil_top+H,
           nx=wall_t,px=wall_t,ny=wall_t,py=wall_t,nz=wall_t,pz=wall_t, lbl="w2")

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

    # Ramps along X-walls (at y1 and y2 sides), placed at room mid-X
    if random.random() < 0.5:
        wx(cx-sz, cx+sz, y1, y1+sz, z1, z1+sz, "wx_lo")
    if random.random() < 0.5:
        wx(cx-sz, cx+sz, y2-sz, y2, z1, z1+sz, "wx_hi")
    # Ramps along Y-walls (at x1 and x2 sides)
    if random.random() < 0.5:
        wy(cy-sz, cy+sz, x1, x1+sz, z1, z1+sz, "wy_lo")
    if random.random() < 0.5:
        wy(cy-sz, cy+sz, x2-sz, x2, z1, z1+sz, "wy_hi")

    return parts, bi


def corridor_brushes(ax,ay,az, bx,by,bz,
                     axis, floor_t, ceil_t, wall_t,
                     door_hw=64,
                     tag="", bi=0):
    """Build a corridor (flat) or ramp (when az != bz) between two rooms.

    Corridor brush extents are trimmed by WALL_T on each end so they do NOT
    overlap the room outer shells — this eliminates Z-fighting entirely.
    """
    dz = abs(bz - az)

    if dz >= 32:
        return _ramp_brushes(ax, ay, az,
                             bx, by, bz,
                             axis, door_hw,
                             floor_t, ceil_t, wall_t,
                             tag=tag, bi=bi)

    # ── flat corridor ────────────────────────────────────────────────────────
    H   = WALL_T
    hw  = door_hw
    parts = []
    zf = min(az, bz)
    zc = zf + DOOR_H

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


def _room_dims_from_physics(i: int, cfg: dict) -> Tuple[int, int, int, int, float]:
    """Return (room_len, room_cross, room_h, door_hw, u_i) for room index i.

    A ±40% random size variance is applied so large rooms can appear early
    and the route feels more organic / unpredictable.
    """
    u_base   = cfg.get("u_base",    550.0)
    u_gain   = cfg.get("u_gain",     60.0)
    t_air    = cfg.get("t_air",      0.68)
    strafe_f = cfg.get("strafe_f",   0.15)

    u_i = u_base + i * u_gain

    # random size multiplier — allows big rooms early, keeps small rooms late
    size_var = random.uniform(0.6, 1.5)
    h_var    = random.uniform(0.8, 1.6)

    raw_len = u_i * t_air * 1.15 * size_var
    room_len = _snap(_clamp(raw_len,
                            cfg.get("min_w", 256),
                            cfg.get("max_w", 1536)))

    raw_cross = u_i * strafe_f * size_var
    room_cross = _snap(_clamp(raw_cross,
                              cfg.get("min_d", 192),
                              cfg.get("max_d", 512)))

    jump_z = (u_i * 0.42) ** 2 / (2 * 800)
    raw_h  = (jump_z + 128) * h_var
    room_h = _snap(_clamp(raw_h,
                          cfg.get("min_h", 192),
                          cfg.get("max_h", 512)))

    # door_hw must be strictly < room_cross/2 so it fits through adjacent rooms.
    # Use 1/3 of cross-width: gives a door that is 2/3 of the room width,
    # leaving wall sections on each side and satisfying _pick_overlap_center.
    door_hw = _snap(_clamp(room_cross // 3, 32, 128))
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
        room_len, room_cross, room_h, door_hw, u_i = _room_dims_from_physics(i, cfg)

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
            if layout == "Multilevel":
                dz_choices = [0, 64, 128, 256, -64, -128, -256, 0, 0]
            else:
                dz_choices = [0, 0, 0, 32, 64, -32, -64]
            cz += random.choice(dz_choices)
            cz  = _snap(cz, 32)
            if layout != "Multilevel":
                cz = max(cz, 0)     # normal layouts: don't go below origin
            else:
                cz = max(cz, -2048) # multilevel: allow going down, but bounded

        r = Room(x=cx, y=cy, z=cz,
                 w=w, d=d, h=room_h,
                 idx=i,
                 floor_t=random.choice(FLOOR_TEX),
                 wall_t =random.choice(WALL_TEX),
                 ceil_t =random.choice(CEIL_TEX),
                 travel_axis=t_axis,
                 speed_in=u_i,
                 door_hw=door_hw)
        rooms.append(r)

        # --- gap: minimum 64 to avoid Z-fighting + guarantee ramp space ---
        reach = u_i * t_air
        gap   = max(_snap(random.uniform(0.0, reach * 0.35)), 64)

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
                         door_hw: int) -> Optional[int]:
    lo = max(a1, b1)
    hi = min(a2, b2)
    if hi - lo < door_hw * 2:
        return None
    center = (lo + hi) // 2
    center = _snap(center)
    center = max(lo + door_hw, min(hi - door_hw, center))
    return center


def _try_bridge(i: int, j: int, rooms: List['Room']) -> Optional['Bridge']:
    """Attempt to build a bridge between rooms[i] and rooms[j].

    Returns a Bridge or None if no spatial overlap allows a corridor.
    """
    a, b = rooms[i], rooms[j]
    dhw  = min(a.door_hw, b.door_hw)

    if b.x1 >= a.x2:                        # b is to the right of a
        yc = _pick_overlap_center(a.y1, a.y2, b.y1, b.y2, dhw)
        if yc is not None:
            return Bridge(i, j, 'x', a.x2, yc, a.z1, b.x1, yc, b.z1,
                          door_hw=dhw,
                          floor_t=random.choice(FLOOR_TEX),
                          wall_t =random.choice(WALL_TEX),
                          ceil_t =random.choice(CEIL_TEX))
    elif a.x1 >= b.x2:                      # b is to the left of a
        yc = _pick_overlap_center(a.y1, a.y2, b.y1, b.y2, dhw)
        if yc is not None:
            return Bridge(i, j, 'x', a.x1, yc, a.z1, b.x2, yc, b.z1,
                          door_hw=dhw,
                          floor_t=random.choice(FLOOR_TEX),
                          wall_t =random.choice(WALL_TEX),
                          ceil_t =random.choice(CEIL_TEX))
    elif b.y1 >= a.y2:                      # b is above a in Y
        xc = _pick_overlap_center(a.x1, a.x2, b.x1, b.x2, dhw)
        if xc is not None:
            return Bridge(i, j, 'y', xc, a.y2, a.z1, xc, b.y1, b.z1,
                          door_hw=dhw,
                          floor_t=random.choice(FLOOR_TEX),
                          wall_t =random.choice(WALL_TEX),
                          ceil_t =random.choice(CEIL_TEX))
    elif a.y1 >= b.y2:                      # b is below a in Y
        xc = _pick_overlap_center(a.x1, a.x2, b.x1, b.x2, dhw)
        if xc is not None:
            return Bridge(i, j, 'y', xc, a.y1, a.z1, xc, b.y2, b.z1,
                          door_hw=dhw,
                          floor_t=random.choice(FLOOR_TEX),
                          wall_t =random.choice(WALL_TEX),
                          ceil_t =random.choice(CEIL_TEX))
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
        f"// Generated by Turnt-o-mator v3 | rooms={cfg['n_rooms']} seed={seed}",
        "// entity 0",
        "{",
        '"mapversion" "220"',
        '"classname" "worldspawn"',
        '"_ambient" "15"',
        f'"message" "{cfg.get("map_name","turnt_map")}"',
    ]

    bi = 0
    # Build per-room door cutout data from bridges.
    # z_bot references the BRIDGE endpoint Z so the cutout aligns with the
    # actual corridor floor even when rooms are at different heights.
    room_doors: Dict[int, list] = {i: [] for i in range(len(rooms))}
    for br in bridges:
        hw = br.door_hw
        if br.axis == 'x':
            room_doors[br.room_a].append(
                {'wall':'wx2','center':br.ay,'hw':hw,'ht':DOOR_H,'z_bot':br.az})
            room_doors[br.room_b].append(
                {'wall':'wx1','center':br.ay,'hw':hw,'ht':DOOR_H,'z_bot':br.bz})
        else:
            room_doors[br.room_a].append(
                {'wall':'wy2','center':br.ax,'hw':hw,'ht':DOOR_H,'z_bot':br.az})
            room_doors[br.room_b].append(
                {'wall':'wy1','center':br.ax,'hw':hw,'ht':DOOR_H,'z_bot':br.bz})

    for room in rooms:
        parts, bi = hollow_box(room.x1, room.y1, room.z1,
                               room.x2, room.y2, room.z2,
                               room.floor_t, room.ceil_t, room.wall_t,
                               tag=f"r{room.idx}", bi=bi,
                               doors=room_doors.get(room.idx))
        lines.extend(parts)

        # Add wall-ramp wedges (~40 % chance per room)
        if random.random() < 0.4:
            wr_parts, bi = _wallramp_brushes(room, bi)
            lines.extend(wr_parts)

    for br in bridges:
        parts, bi = corridor_brushes(
            br.ax, br.ay, br.az,
            br.bx, br.by, br.bz,
            br.axis, br.floor_t, br.ceil_t, br.wall_t,
            door_hw=br.door_hw,
            tag=f"br{br.room_a}_{br.room_b}", bi=bi)
        lines.extend(parts)

    lines.append("}")  # end worldspawn

    # ── Entities ─────────────────────────────────────────────────────────────
    ei    = 1
    first = rooms[0]
    last  = rooms[-1]

    # --- spawn
    spawn_x, spawn_y, spawn_z = first.cx(), first.cy(), first.z1 + 32
    lines.append(f"\n// entity {ei}")
    lines.append(ent_kv(classname="info_player_start",
                        origin=f"{spawn_x} {spawn_y} {spawn_z}",
                        angle="0"))
    ei += 1

    # --- trigger_startTimer — thin line slab perpendicular to travel axis.
    # Player walks/jumps through it to start the timer.  8 units thick,
    # full room width and height so it's impossible to miss.
    SL = 8   # slab thickness
    if first.travel_axis == 'x':
        sx1 = spawn_x + 48;  sx2 = spawn_x + 48 + SL
        sy1 = first.y1;       sy2 = first.y2
    else:
        sx1 = first.x1;       sx2 = first.x2
        sy1 = spawn_y + 48;   sy2 = spawn_y + 48 + SL
    lines.append(f"\n// entity {ei}")
    lines.append(ent_brush_box("trigger_startTimer",
        sx1, sy1, first.z1,
        sx2, sy2, first.z2,
        target="start_t"))
    ei += 1

    # --- target_startTimer
    lines.append(f"\n// entity {ei}")
    lines.append(ent_kv(classname="target_startTimer",
                        origin=f"{(sx1+sx2)//2} {(sy1+sy2)//2} {first.z1 + first.h // 2}",
                        targetname="start_t"))
    ei += 1

    # --- trigger_stopTimer — thin line slab at exit edge of last room
    if last.travel_axis == 'x':
        ex1 = last.x2 - SL;  ex2 = last.x2
        ey1 = last.y1;         ey2 = last.y2
    else:
        ex1 = last.x1;         ex2 = last.x2
        ey1 = last.y2 - SL;   ey2 = last.y2
    lines.append(f"\n// entity {ei}")
    lines.append(ent_brush_box("trigger_stopTimer",
        ex1, ey1, last.z1,
        ex2, ey2, last.z2,
        target="stop_t"))
    ei += 1

    # --- target_stopTimer
    lines.append(f"\n// entity {ei}")
    lines.append(ent_kv(classname="target_stopTimer",
                        origin=f"{last.cx()} {last.cy()} {last.z1 + last.h // 2}",
                        targetname="stop_t"))
    ei += 1

    # --- checkpoints — thin line slabs at entry of each mid room
    if cfg.get("checkpoints", True):
        for cp_n, room in enumerate(rooms[1:-1], start=1):
            tname = f"cp{cp_n}_t"
            if room.travel_axis == 'x':
                tx1 = room.x1;       tx2 = room.x1 + SL
                ty1 = room.y1;       ty2 = room.y2
            else:
                tx1 = room.x1;       tx2 = room.x2
                ty1 = room.y1;       ty2 = room.y1 + SL
            lines.append(f"\n// entity {ei}")
            lines.append(ent_brush_box("trigger_checkpoint",
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
        self.title("Turnt-o-mator")
        self.configure(bg=T["bg"])
        self.minsize(1200, 750)
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
        self._btn(row, "...", self._browse_out, w=4,
                  color=T["accent2"]).pack(side="left", padx=(6, 0))

        # Action buttons
        bf = ttk.Frame(p, style="P.TFrame")
        bf.pack(fill="x", pady=(10, 0))
        self._btn(bf, "Generate map", self._on_generate,
                  color=T["accent"],
                  font=("Segoe UI", 11, "bold")).pack(fill="x", pady=(0, 8))
        r2 = ttk.Frame(bf, style="P.TFrame")
        r2.pack(fill="x")
        self._btn(r2, "Save", self._on_save,
                  color=T["success"]).pack(side="left", fill="x",
                                           expand=True, padx=(0, 4))
        self._btn(r2, "New seed", self._randomize_seed,
                  color=T["accent2"]).pack(side="left", fill="x", expand=True)

        # Game launcher
        ttk.Separator(p).pack(fill="x", pady=(10, 6))
        ttk.Label(p, text="Launch game", style="H2.TLabel").pack(anchor="w", pady=(0,4))
        gx_row = ttk.Frame(p, style="P.TFrame")
        gx_row.pack(fill="x", pady=(0, 4))
        ttk.Entry(gx_row, textvariable=self._game_exe,
                  font=("Consolas", 8)).pack(side="left", fill="x", expand=True)
        self._btn(gx_row, "...", self._browse_game_exe, w=4,
                  color=T["accent2"]).pack(side="left", padx=(4, 0))
        self._launch_btn = self._btn(p, "Launch game with map",
                                     self._on_launch_game,
                                     color=T["warning"],
                                     font=("Segoe UI", 9, "bold"))
        self._launch_btn.pack(fill="x")

        # ─ Tab: Layout ─────────────────────────────────────────────────────
    def _tab_layout(self, p):
        self._v_rooms = tk.IntVar(value=6)
        self._slider(p, "Number of rooms", self._v_rooms, 2, 30)

        # ── Physics & layout ─────────────────────────────────────────────────
        self._sec(p, "Player physics & layout")
        pg = ttk.Frame(p, style="P.TFrame")
        pg.pack(fill="x", pady=(0, 4))
        pg.columnconfigure(0, weight=1)
        pg.columnconfigure(1, weight=1)

        phy_params = [
            ("Base speed (UPS)",     "_v_u_base",    550,  100, 2000,  10),
            ("Speed gain / room",    "_v_u_gain",     60,    0,  300,   5),
            ("Air time (×0.01 s)",   "_v_t_air",      68,   30,  150,   1),
            ("Strafe factor (×0.01)","_v_strafe_f",   15,    5,   40,   1),
            ("Rooms per segment",    "_v_rpt",          3,    1,   10,   1),
        ]
        for row_i, (lbl, attr, dflt, lo, hi, inc) in enumerate(phy_params):
            r, c = divmod(row_i, 2)
            f = ttk.Frame(pg, style="P.TFrame")
            f.grid(row=r, column=c, padx=3, pady=2, sticky="ew")
            ttk.Label(f, text=lbl, style="P.TLabel",
                      font=("Segoe UI", 7)).pack(anchor="w")
            v = tk.IntVar(value=dflt)
            setattr(self, attr, v)
            self._spinbox(f, v, lo, hi, inc)

        # Layout style dropdown
        ls_row = ttk.Frame(pg, style="P.TFrame")
        ls_row.grid(row=3, column=0, columnspan=2, padx=3, pady=2, sticky="ew")
        ttk.Label(ls_row, text="Layout style", style="P.TLabel",
                  font=("Segoe UI", 7)).pack(anchor="w")
        self._v_layout = tk.StringVar(value="Zigzag")
        om = tk.OptionMenu(ls_row, self._v_layout,
                           "Linear", "Zigzag", "Snake", "Random", "Spiral", "Multilevel")
        om.config(bg=T["bg_input"], fg=T["text"], activebackground=T["lbx_sel"],
                  relief="flat", font=("Segoe UI", 9), highlightthickness=0)
        om["menu"].config(bg=T["bg_input"], fg=T["text"])
        om.pack(fill="x")

        # ── Room size clamp limits ────────────────────────────────────────────
        self._sec(p, "Room size clamp limits (qu)")
        g = ttk.Frame(p, style="P.TFrame")
        g.pack(fill="x", pady=(0, 4))
        labels  = ["Min W", "Max W", "Min D", "Max D", "Min H", "Max H"]
        defvals = [ 256,    1536,     192,     512,     192,     512 ]
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

        tk.Label(p,
                 text="Long side = travel axis  |  Short side = lateral sweep",
                 bg=T["bg_panel"], fg=T["text_dim"],
                 font=("Segoe UI", 7)).pack(anchor="w", pady=(0, 6))

        # ── Seed ─────────────────────────────────────────────────────────────
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
            ("Add trigger_checkpoint entities", self._v_checks),
            ("Auto-randomize seed after each generation", self._v_autorand),
        ]:
            ttk.Checkbutton(p, text=text, variable=var).pack(anchor="w", pady=2)

        self._sec(p, "Door height (qu)")
        g = ttk.Frame(p, style="P.TFrame")
        g.pack(fill="x", pady=(0, 8))
        f = ttk.Frame(g, style="P.TFrame")
        f.grid(row=0, column=0, padx=4, sticky="ew")
        g.columnconfigure(0, weight=1)
        ttk.Label(f, text="Door height", style="P.TLabel",
                  font=("Segoe UI", 7)).pack(anchor="w")
        self._v_door_h = tk.IntVar(value=128)
        self._spinbox(f, self._v_door_h, 64, 512, 32)

        self._sec(p, "Preview legend")
        for color, label in [
            (T["start_col"], "Start room"),
            (T["room_col"],  "Mid rooms  (brighter = faster)"),
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

        self._sec(p, "Physics info")
        tk.Label(p,
                 text="Room length  = u × t_air × 1.15\n"
                      "Room width   = u × strafe_factor\n"
                      "Gap          = rand(0 .. u × t_air × 0.35)\n"
                      "Door hw      = room_cross / 2  (clamped 64–192)",
                 bg=T["bg_panel"], fg=T["text_dim"],
                 font=("Consolas", 7), justify="left").pack(anchor="w", pady=4)

    # ── RIGHT PANEL ───────────────────────────────────────────────────────────
    def _build_right(self, p):
        # ── top section: tabbed previews (2D + 3D)
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

        # Notebook for 2D / 3D tabs
        view_nb = ttk.Notebook(pc)
        view_nb.grid(row=1, column=0, sticky="nsew", padx=6, pady=(0, 6))
        pc.rowconfigure(1, weight=1)

        # -- 2D tab
        tab2d = ttk.Frame(view_nb, style="P.TFrame")
        view_nb.add(tab2d, text="  2D  ")
        tab2d.rowconfigure(0, weight=1)
        tab2d.columnconfigure(0, weight=1)

        self._canvas = tk.Canvas(tab2d, bg=T["prev_bg"],
                                 highlightthickness=0)
        self._canvas.grid(row=0, column=0, sticky="nsew")
        self._canvas.bind("<Configure>", lambda e: self._redraw())

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
            "u_base":       float(self._v_u_base.get()),
            "u_gain":       float(self._v_u_gain.get()),
            "t_air":        self._v_t_air.get() / 100.0,
            "strafe_f":     self._v_strafe_f.get() / 100.0,
            # layout
            "rooms_per_turn": self._v_rpt.get(),
            "layout_style":   self._v_layout.get(),
            # misc
            "seed":         self._v_seed.get(),
            "map_name":     self._v_mapname.get(),
            "height_var":   self._v_height.get(),
            "checkpoints":  self._v_checks.get(),
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
        def ty(v): return H - PAD - (v - my) * sc

        # Bridges
        for br in self._bridges:
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

        # Rooms
        n = len(rooms)
        for i, room in enumerate(rooms):
            if i == 0:
                fill, bdr = T["start_col"], T["success"]
            elif i == n - 1:
                fill, bdr = T["end_col"], T["accent"]
            else:
                # colour shifts blue→cyan as speed increases
                t_s = (room.speed_in - 550) / max(1, 60 * n)
                t_s = max(0.0, min(1.0, t_s))
                r_c = int(0x1e + t_s*(0x18-0x1e))
                g_c = int(0x39 + t_s*(0x70-0x39))
                b_c = int(0x60 + t_s*(0x90-0x60))
                fill = f"#{r_c:02x}{g_c:02x}{b_c:02x}"
                bdr  = T["room_bdr"]

            x1s, y1s = tx(room.x1), ty(room.y1)
            x2s, y2s = tx(room.x2), ty(room.y2)
            c.create_rectangle(x1s, y1s, x2s, y2s,
                               fill=fill, outline=bdr, width=2)

            # travel direction arrow
            cxs = (x1s + x2s) / 2
            cys = (y1s + y2s) / 2
            fs  = max(7, min(13, int(min(abs(x2s-x1s), abs(y2s-y1s)) / 3.5)))
            arrow = "→" if room.travel_axis == 'x' else "↑"
            c.create_text(cxs, cys - fs * 0.7,
                          text=str(i+1), fill=T["text"],
                          font=("Segoe UI", fs, "bold"))
            c.create_text(cxs, cys + fs * 0.7,
                          text=arrow, fill=T["accent"],
                          font=("Segoe UI", max(7, fs-1)))

            # speed label
            c.create_text(cxs, cys + fs * 2.0,
                          text=f"{room.speed_in:.0f}",
                          fill=T["text_dim"],
                          font=("Segoe UI", max(6, fs-2)))

        # Legend
        items = [("■ Start", T["success"]), ("■ Rooms", T["room_col"]),
                 ("■ End",   T["accent"]),  ("━ Bridge", T["corr_col"])]
        for j, (txt, col) in enumerate(items):
            c.create_text(PAD + j*100, H-14, text=txt,
                          fill=col, font=("Segoe UI", 8), anchor="w")


# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    app = App()
    app.mainloop()