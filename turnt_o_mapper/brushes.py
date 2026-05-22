"""
Low-level Quake 3 .map brush geometry generation.

Provides functions for creating individual brush faces, axis-aligned boxes,
room floors / ceilings / walls (with door cutouts and overlap clipping),
ramp wedges, wall-ramps, and flat/ramped corridors between rooms.

All output is plain text in the Valve 220 .map format.
"""

import math
import random

from .constants import (
    WALL_T, DOOR_H, HIDDEN_TEX,
    SLOPE_RATIO, MIN_RAMP_ANGLE, MAX_RAMP_ANGLE, MIN_SLOPE_RATIO,
    RAMP_TEX, OUTLINE_W,
)
from .layout import _clip_footprint, _clip_intervals


# ══════════════════════════════════════════════════════════════════════════════
#  PRIMITIVE HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def fv(v):
    """Format a 3-component vector as a Quake face-vertex string ``( x y z )``."""
    return f"( {v[0]:g} {v[1]:g} {v[2]:g} )"


def face(p1, p2, p3, tex,
         ua=(1, 0, 0), uo=0,
         va=(0, 0, -1), vo=0,
         rot=0, sx=.5, sy=.5):
    """Build a single texture-mapped face definition from three coplanar points.

    The face normal is computed by the engine as ``(p2-p1) x (p3-p1)`` and
    must point *inward* (towards the solid interior of the brush).

    Parameters:
        p1, p2, p3: three (x, y, z) tuples defining the face plane.
        tex: texture name string.
        ua, uo, va, vo: U/V axis directions and offsets for texture mapping.
        rot: texture rotation in degrees.
        sx, sy: texture scale factors.
    """
    u = f"[ {ua[0]} {ua[1]} {ua[2]} {uo} ]"
    v = f"[ {va[0]} {va[1]} {va[2]} {vo} ]"
    return f"{fv(p1)} {fv(p2)} {fv(p3)} {tex} {u} {v} {rot} {sx} {sy}"


def box_faces(x1, y1, z1, x2, y2, z2, nx, px, ny, py, nz, pz):
    """Generate six face definitions for an axis-aligned box.

    Each face's three vertices produce an *inward-pointing* normal via
    ``(p2-p1) x (p3-p1)``.  TrenchBroom / Quake treats the solid region
    as the positive half-space in the direction the normal points.

    Parameters:
        x1..z2: bounding box extents.
        nx, px, ny, py, nz, pz: texture names for -X, +X, -Y, +Y, -Z, +Z faces.
    """
    return [
        face((x1, y1, z1), (x1, y2, z1), (x1, y1, z2), nx, (0,  1, 0), 0, (0, 0, -1), 0),
        face((x2, y2, z2), (x2, y2, z1), (x2, y1, z2), px, (0, -1, 0), 0, (0, 0, -1), 0),
        face((x1, y1, z1), (x1, y1, z2), (x2, y1, z1), ny, (-1, 0, 0), 0, (0, 0, -1), 0),
        face((x2, y2, z2), (x1, y2, z2), (x2, y2, z1), py, ( 1, 0, 0), 0, (0, 0, -1), 0),
        face((x1, y1, z1), (x2, y1, z1), (x1, y2, z1), nz, (-1, 0, 0), 0, (0, -1, 0), 0),
        face((x2, y2, z2), (x2, y1, z2), (x1, y2, z2), pz, ( 1, 0, 0), 0, (0, -1, 0), 0),
    ]


def write_brush(faces, cmt=""):
    """Wrap a list of face strings into a complete brush block.

    Optionally prepends a ``// comment`` line for readability in the .map file.
    """
    ln = []
    if cmt:
        ln.append(f"// {cmt}")
    ln.append("{")
    ln.extend(faces)
    ln.append("}")
    return "\n".join(ln)


# ══════════════════════════════════════════════════════════════════════════════
#  ROOM COMPONENTS
# ══════════════════════════════════════════════════════════════════════════════

def room_floor(x1, y1, z1, x2, y2, z2, floor_t, tag, bi, clips=(),
               accent_t=None):
    """Generate floor brush(es) for a room with outline border.

    Outline borders are drawn along the ORIGINAL room edges (x1/y1/x2/y2),
    then clipped.  This avoids z-fighting at clip boundaries where a
    neighbouring room's floor would coincide with an outline strip.

    Returns ``(brush_strings, next_brush_index)``.
    """
    H   = WALL_T
    OL  = OUTLINE_W
    oz1 = z1 - H

    def _emit(rx1, ry1, rx2, ry2, tex, lbl):
        nonlocal bi
        if rx1 >= rx2 or ry1 >= ry2:
            return
        fs = box_faces(rx1, ry1, oz1, rx2, ry2, z1,
                       tex, tex, tex, tex, tex, tex)
        parts.append(write_brush(fs, f"brush {bi} {tag}_{lbl}"))
        bi += 1

    parts = []
    if accent_t and (x2 - x1) > 2 * OL and (y2 - y1) > 2 * OL:
        # Interior rectangle (main texture) — then clip
        ix1, iy1 = x1 + OL, y1 + OL
        ix2, iy2 = x2 - OL, y2 - OL
        for rx1, ry1, rx2, ry2 in _clip_footprint(ix1, iy1, ix2, iy2, clips):
            _emit(rx1, ry1, rx2, ry2, floor_t, "floor")

        # Four border strips along original edges — then clip each
        borders = [
            (x1, y1, x2, iy1),   # bottom
            (x1, iy2, x2, y2),   # top
            (x1, iy1, ix1, iy2), # left
            (ix2, iy1, x2, iy2), # right
        ]
        for bx1, by1, bx2, by2 in borders:
            for rx1, ry1, rx2, ry2 in _clip_footprint(bx1, by1, bx2, by2, clips):
                _emit(rx1, ry1, rx2, ry2, accent_t, "floor_ol")
    else:
        for rx1, ry1, rx2, ry2 in _clip_footprint(x1, y1, x2, y2, clips):
            _emit(rx1, ry1, rx2, ry2, floor_t, "floor")
    return parts, bi


def room_ceiling(x1, y1, z1, x2, y2, z2, ceil_t, tag, bi, clips=()):
    """Generate ceiling brush(es) for a room, minus any clip regions.

    The ceiling slab is WALL_T thick, sitting just above z2.

    Returns ``(brush_strings, next_brush_index)``.
    """
    H   = WALL_T
    oz2 = z2 + H
    parts = []
    for rx1, ry1, rx2, ry2 in _clip_footprint(x1, y1, x2, y2, clips):
        if rx1 < rx2 and ry1 < ry2 and z2 < oz2:
            fs = box_faces(rx1, ry1, z2, rx2, ry2, oz2,
                           ceil_t, ceil_t, ceil_t, ceil_t, ceil_t, ceil_t)
            parts.append(write_brush(fs, f"brush {bi} {tag}_ceil"))
            bi += 1
    return parts, bi


def room_walls(x1, y1, z1, x2, y2, z2, wall_t, tag, bi, doors=None,
               skip_sides=None, side_clips=None):
    """Generate the four side walls of a room with door cutouts and clipping.

    Each wall is WALL_T thick, extending from oz1 (z1-WALL_T) up to z2
    (not z2+WALL_T, so walls never protrude above the ceiling into rooms above).

    Parameters:
        doors: list of door dicts ``{wall, center, hw, ht, z_bot}``.
        skip_sides: set of wall names to omit entirely (e.g. ``{'wx1'}``).
        side_clips: ``{wall_name: [(clo, chi), ...]}`` intervals along each
            wall's variable axis that are covered by overlapping rooms and
            should not be generated.

    Returns ``(brush_strings, next_brush_index)``.
    """
    H   = WALL_T
    ox1, oy1, oz1 = x1 - H, y1 - H, z1 - H
    ox2, oy2, oz2 = x2 + H, y2 + H, z2 + H
    parts = []

    door_map = {}
    if doors:
        for d in doors:
            door_map.setdefault(d['wall'], []).append(d)

    def rb(ax1, ay1, az1, ax2, ay2, az2, lbl=""):
        nonlocal bi
        if ax1 >= ax2 or ay1 >= ay2 or az1 >= az2:
            return
        fs = box_faces(ax1, ay1, az1, ax2, ay2, az2,
                       wall_t, wall_t, wall_t, wall_t, wall_t, wall_t)
        parts.append(write_brush(fs, f"brush {bi} {tag}_{lbl}"))
        bi += 1

    def _gen_wall_y(bx1, bx2, by1, by2, bz1, bz2, wall_name):
        """wx1/wx2 wall segment -- carve out all door openings sorted by Y."""
        ds = door_map.get(wall_name)
        if not ds:
            rb(bx1, by1, bz1, bx2, by2, bz2, lbl=wall_name)
            return
        sorted_ds = sorted(ds, key=lambda d: d['center'])
        cur_y = by1
        any_door = False
        for d in sorted_ds:
            yc = d['center'];  hw = d['hw']
            eff_lo = max(yc - hw, by1)
            eff_hi = min(yc + hw, by2)
            if eff_lo >= eff_hi:
                continue
            any_door = True
            z_b = d['z_bot'];  z_t = min(z_b + d['ht'], bz2)
            if cur_y < eff_lo:
                rb(bx1, cur_y,  bz1, bx2, eff_lo, bz2, lbl=f"{wall_name}_s")
            if z_b > bz1:
                rb(bx1, eff_lo, bz1, bx2, eff_hi, z_b, lbl=f"{wall_name}_bot")
            if z_t < bz2:
                rb(bx1, eff_lo, z_t, bx2, eff_hi, bz2, lbl=f"{wall_name}_top")
            cur_y = max(cur_y, eff_hi)
        if not any_door:
            rb(bx1, by1, bz1, bx2, by2, bz2, lbl=wall_name)
            return
        if cur_y < by2:
            rb(bx1, cur_y, bz1, bx2, by2, bz2, lbl=f"{wall_name}_s")

    def _gen_wall_x(bx1, bx2, by1, by2, bz1, bz2, wall_name):
        """wy1/wy2 wall segment -- carve out all door openings sorted by X."""
        ds = door_map.get(wall_name)
        if not ds:
            rb(bx1, by1, bz1, bx2, by2, bz2, lbl=wall_name)
            return
        sorted_ds = sorted(ds, key=lambda d: d['center'])
        cur_x = bx1
        any_door = False
        for d in sorted_ds:
            xc = d['center'];  hw = d['hw']
            eff_lo = max(xc - hw, bx1)
            eff_hi = min(xc + hw, bx2)
            if eff_lo >= eff_hi:
                continue
            any_door = True
            z_b = d['z_bot'];  z_t = min(z_b + d['ht'], bz2)
            if cur_x < eff_lo:
                rb(cur_x,  by1, bz1, eff_lo, by2, bz2, lbl=f"{wall_name}_s")
            if z_b > bz1:
                rb(eff_lo, by1, bz1, eff_hi, by2, z_b, lbl=f"{wall_name}_bot")
            if z_t < bz2:
                rb(eff_lo, by1, z_t, eff_hi, by2, bz2, lbl=f"{wall_name}_top")
            cur_x = max(cur_x, eff_hi)
        if not any_door:
            rb(bx1, by1, bz1, bx2, by2, bz2, lbl=wall_name)
            return
        if cur_x < bx2:
            rb(cur_x, by1, bz1, bx2, by2, bz2, lbl=f"{wall_name}_s")

    def wall_y(bx1, bx2, full_y1, full_y2, bz1, bz2, wall_name):
        """wx1/wx2 wall -- generate only the Y segments not covered by clips."""
        clips_1d = (side_clips or {}).get(wall_name, [])
        for seg_y1, seg_y2 in _clip_intervals(full_y1, full_y2, clips_1d):
            _gen_wall_y(bx1, bx2, seg_y1, seg_y2, bz1, bz2, wall_name)

    def wall_x(bx1, bx2, by1, by2, bz1, bz2, wall_name):
        """wy1/wy2 wall -- generate only the X segments not covered by clips."""
        clips_1d = (side_clips or {}).get(wall_name, [])
        for seg_x1, seg_x2 in _clip_intervals(x1, x2, clips_1d):
            sbx1 = bx1 if seg_x1 <= x1 else seg_x1
            sbx2 = bx2 if seg_x2 >= x2 else seg_x2
            _gen_wall_x(sbx1, sbx2, by1, by2, bz1, bz2, wall_name)

    skip = skip_sides or set()
    if 'wx1' not in skip:
        wall_y(ox1, x1,  y1, y2, oz1, z2, 'wx1')
    if 'wx2' not in skip:
        wall_y(x2,  ox2, y1, y2, oz1, z2, 'wx2')
    if 'wy1' not in skip:
        wall_x(ox1, ox2, oy1, y1, oz1, z2, 'wy1')
    if 'wy2' not in skip:
        wall_x(ox1, ox2, y2,  oy2, oz1, z2, 'wy2')

    return parts, bi


# ══════════════════════════════════════════════════════════════════════════════
#  RAMPS
# ══════════════════════════════════════════════════════════════════════════════

def _ramp_brushes(x0, y0, z0, x1, y1, z1,
                  axis, hw, door_ht,
                  floor_t, ceil_t, wall_t,
                  tag, bi, *,
                  enc_lo, enc_hi):
    """Generate a 5-face pentahedron floor-wedge ramp with enclosure.

    The ramp slopes from (x0,y0,z0) to (x1,y1,z1).  Enclosure brushes
    (ceiling slab and two side walls) are placed only within the
    ``[enc_lo, enc_hi]`` corridor gap so they don't double up with room
    geometry.

    Returns ``(brush_strings, next_brush_index)``.
    """
    H = WALL_T
    parts = []

    ramp_tex = RAMP_TEX

    def ramp5(f1, f2, f3, f4, f5, lbl):
        nonlocal bi
        faces = [face(a, b, c, ramp_tex) for (a, b, c) in (f1, f2, f3, f4, f5)]
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
        fs = box_faces(ax1, ay1, az1, ax2, ay2, az2,
                       _nx, _px, _ny, _py, _nz, _pz)
        parts.append(write_brush(fs, f"brush {bi} {tag}_{lbl}"))
        bi += 1

    if axis == 'y':
        if y0 > y1:
            y0, y1 = y1, y0
            z0, z1 = z1, z0
        ylo, yhi = y0, y1
        if ylo >= yhi:
            return parts, bi
        cx  = (x0 + x1) // 2
        xlo, xhi = cx - hw, cx + hw
        za, zb   = z0, z1

        if za <= zb:
            ramp5(
                ((xlo, yhi, za), (xlo, yhi, zb), (xlo, ylo, za)),
                ((xlo, yhi, zb), (xhi, yhi, zb), (xhi, ylo, za)),
                ((xhi, ylo, za), (xhi, yhi, za), (xlo, yhi, za)),
                ((xhi, yhi, za), (xhi, yhi, zb), (xlo, yhi, zb)),
                ((xhi, ylo, za), (xhi, yhi, zb), (xhi, yhi, za)),
                "ramp",
            )
        else:
            ramp5(
                ((xlo, yhi, zb), (xlo, ylo, za), (xlo, ylo, zb)),
                ((xlo, ylo, zb), (xlo, ylo, za), (xhi, ylo, za)),
                ((xlo, yhi, zb), (xlo, ylo, zb), (xhi, ylo, zb)),
                ((xhi, ylo, za), (xlo, ylo, za), (xlo, yhi, zb)),
                ((xhi, ylo, zb), (xhi, ylo, za), (xhi, yhi, zb)),
                "ramp",
            )

        z_lo, z_hi = min(za, zb), max(za, zb)
        ceil_top = z_hi + door_ht
        elo, ehi = enc_lo + H, enc_hi - H
        if elo < ehi:
            cb(xlo, elo, ceil_top, xhi, ehi, ceil_top + H,
               nx=ceil_t, px=ceil_t, ny=ceil_t, py=ceil_t, nz=ceil_t, pz=ceil_t,
               lbl="ramp_ce")
            cb(xlo - H, elo, z_lo - H, xlo, ehi, ceil_top + H, lbl="ramp_w1")
            cb(xhi,     elo, z_lo - H, xhi + H, ehi, ceil_top + H, lbl="ramp_w2")
            cb(xlo, elo, z_lo - H, xhi, ehi, z_lo,
               nx=floor_t, px=floor_t, ny=floor_t, py=floor_t,
               nz=floor_t, pz=floor_t, lbl="ramp_fl")

    else:  # axis == 'x'
        if x0 > x1:
            x0, x1 = x1, x0
            z0, z1 = z1, z0
        xlo, xhi = x0, x1
        if xlo >= xhi:
            return parts, bi
        cy  = (y0 + y1) // 2
        ylo, yhi = cy - hw, cy + hw
        za, zb   = z0, z1

        if za <= zb:
            ramp5(
                ((xlo, ylo, za), (xhi, ylo, zb), (xhi, ylo, za)),
                ((xlo, yhi, za), (xhi, yhi, za), (xhi, yhi, zb)),
                ((xhi, ylo, za), (xhi, yhi, za), (xlo, yhi, za)),
                ((xhi, yhi, zb), (xhi, yhi, za), (xhi, ylo, za)),
                ((xhi, yhi, zb), (xhi, ylo, zb), (xlo, ylo, za)),
                "ramp",
            )
        else:
            ramp5(
                ((xlo, ylo, zb), (xlo, ylo, za), (xhi, ylo, za)),
                ((xlo, yhi, zb), (xlo, yhi, za), (xlo, ylo, zb)),
                ((xhi, ylo, zb), (xhi, yhi, zb), (xlo, yhi, zb)),
                ((xhi, ylo, zb), (xlo, ylo, za), (xlo, yhi, za)),
                ((xlo, yhi, zb), (xhi, yhi, zb), (xhi, yhi, za)),
                "ramp",
            )

        z_lo, z_hi = min(za, zb), max(za, zb)
        ceil_top = z_hi + door_ht
        elo, ehi = enc_lo + H, enc_hi - H
        if elo < ehi:
            cb(elo, ylo, ceil_top, ehi, yhi, ceil_top + H,
               nx=ceil_t, px=ceil_t, ny=ceil_t, py=ceil_t, nz=ceil_t, pz=ceil_t,
               lbl="ramp_ce")
            cb(elo, ylo - H, z_lo - H, ehi, ylo, ceil_top + H, lbl="ramp_w1")
            cb(elo, yhi,     z_lo - H, ehi, yhi + H, ceil_top + H, lbl="ramp_w2")
            cb(elo, ylo, z_lo - H, ehi, yhi, z_lo,
               nx=floor_t, px=floor_t, ny=floor_t, py=floor_t,
               nz=floor_t, pz=floor_t, lbl="ramp_fl")

    return parts, bi


def _wallramp_brushes(room, bi):
    """Generate 45-degree wedge ramps at the base of room walls.

    Randomly places ramps on each of the four walls for trick-jump surfaces.

    Returns ``(brush_strings, next_brush_index)``.
    """
    parts = []
    H   = WALL_T
    rw  = room.wall_t
    rf  = room.floor_t
    sz  = 64

    def wx(xlo, xhi, ylo, yhi, zlo, zhi, lbl):
        nonlocal bi
        bot = zlo - H
        f1 = face((xlo, ylo, bot), (xhi, ylo, bot), (xlo, yhi, bot), rf, (-1, 0, 0), 0, (0, -1, 0), 0)
        f2 = face((xlo, ylo, zlo), (xlo, yhi, zlo), (xhi, ylo, zhi), rf, (0, 1, 0), 0, (0, 0, -1), 0)
        f3 = face((xlo, ylo, bot), (xlo, ylo, zlo), (xlo, yhi, bot), rw, (0, 1, 0), 0, (0, 0, -1), 0)
        f4 = face((xhi, yhi, bot), (xhi, yhi, zhi), (xhi, ylo, bot), rw, (0, -1, 0), 0, (0, 0, -1), 0)
        f5 = face((xlo, ylo, bot), (xhi, ylo, bot), (xhi, ylo, zhi), rw, (-1, 0, 0), 0, (0, 0, -1), 0)
        f6 = face((xlo, yhi, bot), (xlo, yhi, zlo), (xhi, yhi, bot), rw, (1, 0, 0), 0, (0, 0, -1), 0)
        parts.append(write_brush([f1, f2, f3, f4, f5, f6], f"brush {bi} wr_{lbl}"))
        bi += 1

    def wy(ylo, yhi, xlo, xhi, zlo, zhi, lbl):
        nonlocal bi
        bot = zlo - H
        f1 = face((xlo, ylo, bot), (xhi, ylo, bot), (xlo, yhi, bot), rf, (-1, 0, 0), 0, (0, -1, 0), 0)
        f2 = face((xlo, ylo, zlo), (xhi, ylo, zlo), (xlo, yhi, zhi), rf, (1, 0, 0), 0, (0, 0, -1), 0)
        f3 = face((xlo, ylo, bot), (xlo, yhi, bot), (xlo, ylo, zlo), rw, (0, -1, 0), 0, (0, 0, -1), 0)
        f4 = face((xhi, yhi, bot), (xhi, ylo, bot), (xhi, yhi, zhi), rw, (0, 1, 0), 0, (0, 0, -1), 0)
        f5 = face((xlo, ylo, bot), (xlo, ylo, zlo), (xhi, ylo, bot), rw, (0, 0, -1), 0, (1, 0, 0), 0)
        f6 = face((xlo, yhi, bot), (xhi, yhi, bot), (xlo, yhi, zhi), rw, (0, 0, 1), 0, (1, 0, 0), 0)
        parts.append(write_brush([f1, f2, f3, f4, f5, f6], f"brush {bi} wr_{lbl}"))
        bi += 1

    x1, y1, z1 = room.x1, room.y1, room.z1
    x2, y2     = room.x2, room.y2
    cx, cy     = room.cx(), room.cy()

    if random.random() < 0.5:
        wy(y1, y1 + sz, cx - sz, cx + sz, z1, z1 + sz, "wy1_ramp")
    if random.random() < 0.5:
        wy(y2 - sz, y2, cx - sz, cx + sz, z1, z1 + sz, "wy2_ramp")
    if random.random() < 0.5:
        wx(x1, x1 + sz, cy - sz, cy + sz, z1, z1 + sz, "wx1_ramp")
    if random.random() < 0.5:
        wx(x2 - sz, x2, cy - sz, cy + sz, z1, z1 + sz, "wx2_ramp")

    return parts, bi


def _adaptive_ramp_len(dz: int, max_available: int) -> int:
    """Choose ramp horizontal length — as gentle as possible.

    Computes the ideal length for the shallowest angle (MIN_RAMP_ANGLE,
    10°).  If that doesn't fit, uses all available space — the ramp gets
    steeper but never exceeds 30° (layout caps dz accordingly).
    """
    if max_available <= 0:
        return max(abs(dz), 1)
    ideal_len = int(dz / math.tan(math.radians(MIN_RAMP_ANGLE)))
    return min(ideal_len, max_available)


def compute_bridge_footprint(ax, ay, az, bx, by, bz,
                             axis, door_hw=64,
                             ra_far=None, rb_far=None):
    """Compute the GAP-ZONE footprint of a bridge corridor.

    Returns ``(fp_x1, fp_y1, fp_x2, fp_y2, z_floor)`` covering ONLY the
    gap between room walls (where the corridor/ramp floor brush sits).
    Room floors inside rooms are kept intact — only the gap is clipped.
    """
    H  = WALL_T
    hw = door_hw
    z_floor = min(az, bz)

    if axis == 'x':
        xmn = min(ax, bx) + H
        xmx = max(ax, bx) - H
        cy = (ay + by) // 2
        if xmn >= xmx:
            return None
        return (xmn, cy - hw, xmx, cy + hw, z_floor)
    else:
        ymn = min(ay, by) + H
        ymx = max(ay, by) - H
        cx = (ax + bx) // 2
        if ymn >= ymx:
            return None
        return (cx - hw, ymn, cx + hw, ymx, z_floor)


def corridor_brushes(ax, ay, az, bx, by, bz,
                     axis, floor_t, ceil_t, wall_t,
                     door_hw=64, door_ht=DOOR_H,
                     ra_far=None, rb_far=None,
                     tag="", bi=0):
    """Build a flat corridor or a full-length ramp between two rooms.

    For height differences >= 32 units the corridor becomes a ramp whose
    wedge extends *into* the adjacent rooms to achieve a shallow slope
    (~14 deg).  Only enclosure brushes (ceiling / side walls) are
    restricted to the corridor gap so they don't double up with room
    geometry.

    Parameters:
        ax..bz: bridge endpoint coordinates.
        axis: travel direction ('x' or 'y').
        ra_far / rb_far: inner far-wall coordinate of each room (limits
            how deep the ramp may extend into that room).

    Returns ``(brush_strings, next_brush_index)``.
    """
    H  = WALL_T
    dz = abs(bz - az)

    if dz >= 32:
        lo_x  = min(ax, bx);  hi_x  = max(ax, bx)
        lo_z  = az if ax <= bx else bz
        hi_z  = bz if ax <= bx else az
        lo_far = ra_far if ax <= bx else rb_far
        hi_far = rb_far if ax <= bx else ra_far

        def _clamp_dz(actual_len, cur_dz, cur_lo, cur_hi):
            """Keep ramp endpoints pinned to room floors.

            Layout already caps dz so the angle stays reasonable.
            A steeper-than-ideal ramp is always better than one that
            floats in the air and cannot be reached via crouchslide.
            """
            return cur_lo, cur_hi

        if axis == 'x':
            if lo_z <= hi_z:
                x_hi = hi_x - H
                x_lo_limit = (lo_far + H) if lo_far is not None else (x_hi - int(dz * SLOPE_RATIO))
                max_available = x_hi - x_lo_limit
                ramp_len = _adaptive_ramp_len(dz, max_available)
                x_lo = max(x_hi - ramp_len, x_lo_limit)
            else:
                x_lo = lo_x + H
                x_hi_limit = (hi_far - H) if hi_far is not None else (x_lo + int(dz * SLOPE_RATIO))
                max_available = x_hi_limit - x_lo
                ramp_len = _adaptive_ramp_len(dz, max_available)
                x_hi = min(x_lo + ramp_len, x_hi_limit)
            actual_len = x_hi - x_lo
            lo_z, hi_z = _clamp_dz(actual_len, dz, lo_z, hi_z)
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
            if lo_zy <= hi_zy:
                y_hi = hi_y - H
                y_lo_limit = (lo_fy + H) if lo_fy is not None else (y_hi - int(dz * SLOPE_RATIO))
                max_available = y_hi - y_lo_limit
                ramp_len = _adaptive_ramp_len(dz, max_available)
                y_lo = max(y_hi - ramp_len, y_lo_limit)
            else:
                y_lo = lo_y + H
                y_hi_limit = (hi_fy - H) if hi_fy is not None else (y_lo + int(dz * SLOPE_RATIO))
                max_available = y_hi_limit - y_lo
                ramp_len = _adaptive_ramp_len(dz, max_available)
                y_hi = min(y_lo + ramp_len, y_hi_limit)
            actual_len = y_hi - y_lo
            lo_zy, hi_zy = _clamp_dz(actual_len, dz, lo_zy, hi_zy)
            return _ramp_brushes(ax, y_lo, lo_zy, bx, y_hi, hi_zy,
                                 axis, door_hw, door_ht,
                                 floor_t, ceil_t, wall_t,
                                 tag=tag, bi=bi,
                                 enc_lo=lo_y, enc_hi=hi_y)

    # Flat corridor
    hw  = door_hw
    parts = []
    zf = min(az, bz)
    zc = zf + door_ht

    def cb(ax1, ay1, az1, ax2, ay2, az2,
           nx=wall_t, px=wall_t, ny=wall_t, py=wall_t, nz=ceil_t, pz=floor_t, lbl=""):
        nonlocal bi
        if ax1 >= ax2 or ay1 >= ay2 or az1 >= az2:
            return
        fs = box_faces(ax1, ay1, az1, ax2, ay2, az2, nx, px, ny, py, nz, pz)
        parts.append(write_brush(fs, f"brush {bi} {tag}_{lbl}"))
        bi += 1

    if axis == 'x':
        xmn = min(ax, bx) + H
        xmx = max(ax, bx) - H
        if xmn >= xmx:
            return parts, bi
        cy = (ay + by) // 2
        cb(xmn, cy - hw,     zf - H, xmx, cy + hw,     zf,
           nx=floor_t, px=floor_t, ny=floor_t, py=floor_t, nz=floor_t, pz=floor_t, lbl="fl")
        cb(xmn, cy - hw,     zc,     xmx, cy + hw,     zc + H,
           nx=ceil_t, px=ceil_t, ny=ceil_t, py=ceil_t, nz=ceil_t, pz=ceil_t, lbl="ce")
        cb(xmn, cy - hw - H, zf,     xmx, cy - hw,     zc,
           nx=wall_t, px=wall_t, ny=wall_t, py=wall_t, nz=wall_t, pz=wall_t, lbl="w1")
        cb(xmn, cy + hw,     zf,     xmx, cy + hw + H, zc,
           nx=wall_t, px=wall_t, ny=wall_t, py=wall_t, nz=wall_t, pz=wall_t, lbl="w2")
    else:
        cx = (ax + bx) // 2
        ymn = min(ay, by) + H
        ymx = max(ay, by) - H
        if ymn >= ymx:
            return parts, bi
        cb(cx - hw,     ymn, zf - H, cx + hw,     ymx, zf,
           nx=floor_t, px=floor_t, ny=floor_t, py=floor_t, nz=floor_t, pz=floor_t, lbl="fl")
        cb(cx - hw,     ymn, zc,     cx + hw,     ymx, zc + H,
           nx=ceil_t, px=ceil_t, ny=ceil_t, py=ceil_t, nz=ceil_t, pz=ceil_t, lbl="ce")
        cb(cx - hw - H, ymn, zf,     cx - hw,     ymx, zc,
           nx=wall_t, px=wall_t, ny=wall_t, py=wall_t, nz=wall_t, pz=wall_t, lbl="w1")
        cb(cx + hw,     ymn, zf,     cx + hw + H, ymx, zc,
           nx=wall_t, px=wall_t, ny=wall_t, py=wall_t, nz=wall_t, pz=wall_t, lbl="w2")

    return parts, bi
