"""
Physics-driven room placement and bridge building.

This module contains the layout engine that arranges rooms in 2D/3D space
using one of six layout styles (Linear, Zigzag, Snake, Random, Spiral,
Multilevel).  Room dimensions can be derived from a player-speed model
or drawn uniformly from min/max slider values.

It also provides geometric utility functions used by both the layout
engine and the brush generation module (clip intervals, footprint
subtraction, etc.).
"""

import random
from typing import List, Optional, Tuple, Dict

from .constants import (
    FLOOR_TEX, WALL_TEX, CEIL_TEX,
    DOOR_H, WALL_T, MIN_SLOPE_RATIO,
)
from .models import Room, Bridge


# ══════════════════════════════════════════════════════════════════════════════
#  GEOMETRY UTILITIES (used by brushes.py and entities.py as well)
# ══════════════════════════════════════════════════════════════════════════════

def _snap(v, grid=64):
    """Round *v* to the nearest multiple of *grid* (default 64 Quake units)."""
    return round(v / grid) * grid


def _clamp(v, lo, hi):
    """Constrain *v* to the inclusive range [lo, hi]."""
    return max(lo, min(hi, v))


def _xy_overlap(ax1, ay1, ax2, ay2, bx1, by1, bx2, by2) -> bool:
    """Return True if axis-aligned rectangles (a) and (b) overlap in XY."""
    return ax1 < bx2 and ax2 > bx1 and ay1 < by2 and ay2 > by1


def _clip_intervals(lo: int, hi: int, clips) -> list:
    """Subtract a list of (clo, chi) intervals from the segment [lo, hi].

    Returns the list of remaining non-overlapping segments as (start, end) tuples.
    Each element of *clips* is a (clo, chi) pair that removes the intersection
    from the running segment list.

    Example::

        _clip_intervals(0, 100, [(20, 40), (60, 80)])
        # -> [(0, 20), (40, 60), (80, 100)]
    """
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
    """Subtract an obstacle rectangle from *rect*, returning up to 4 pieces.

    Both rectangles are axis-aligned.  Returns the list of (x1,y1,x2,y2)
    sub-rectangles that remain after removing the intersection with the
    obstacle.  If there is no intersection the original rect is returned
    unchanged.
    """
    cx1 = max(rx1, ox1); cy1 = max(ry1, oy1)
    cx2 = min(rx2, ox2); cy2 = min(ry2, oy2)
    if cx1 >= cx2 or cy1 >= cy2:
        return [(rx1, ry1, rx2, ry2)]
    return [(x1, y1, x2, y2) for x1, y1, x2, y2 in [
        (rx1, ry1, cx1, ry2),   # left of obstacle
        (cx2, ry1, rx2, ry2),   # right of obstacle
        (cx1, ry1, cx2, cy1),   # below obstacle (centre strip)
        (cx1, cy2, cx2, ry2),   # above obstacle (centre strip)
    ] if x1 < x2 and y1 < y2]


def _clip_footprint(x1, y1, x2, y2, clips):
    """Return the list of rectangles remaining after subtracting all *clips*.

    Each clip is an (x1, y1, x2, y2) rectangle.  The result is a list of
    non-overlapping sub-rectangles covering the original footprint minus
    the union of all clip regions.  Used for floor / ceiling generation to
    avoid placing geometry inside overlapping rooms.
    """
    rects = [(x1, y1, x2, y2)]
    for cx1, cy1, cx2, cy2 in clips:
        new_rects = []
        for r in rects:
            new_rects.extend(_subtract_rect(*r, cx1, cy1, cx2, cy2))
        rects = new_rects
    return rects


# ══════════════════════════════════════════════════════════════════════════════
#  ROOM DIMENSIONING
# ══════════════════════════════════════════════════════════════════════════════

def _room_dims_from_physics(i: int, cfg: dict) -> Tuple[int, int, int, int, float]:
    """Compute room dimensions for room index *i* based on config.

    When ``cfg['use_physics']`` is True, sizes are derived from the speed
    model (base speed + per-room gain, air time, strafe factor).  Otherwise
    dimensions are drawn uniformly from the min/max slider values.

    Returns:
        (room_len, room_cross, room_h, door_hw, u_i)
        where *room_len* is the long side (travel axis), *room_cross* is the
        lateral dimension, *room_h* is the ceiling height, *door_hw* is the
        half-width of the exit door, and *u_i* is the estimated player speed.
    """
    u_base = cfg.get("u_base", 550.0)
    u_gain = cfg.get("u_gain", 60.0)
    u_i    = u_base + i * u_gain

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


# ══════════════════════════════════════════════════════════════════════════════
#  ROOM PLACEMENT
# ══════════════════════════════════════════════════════════════════════════════

def place_rooms(n: int, cfg: dict) -> List[Room]:
    """Place *n* rooms using a physics-driven layout algorithm.

    Supports six layout styles selectable via ``cfg['layout_style']``:

    - **Linear** -- one straight line along the X axis.
    - **Zigzag** -- alternating X / Y every *rooms_per_turn* rooms.
    - **Snake** -- like Zigzag but segment length is randomised.
    - **Random** -- 4-directional, turning 90 deg left or right randomly.
    - **Spiral** -- always turns right (+X -> -Y -> -X -> +Y -> ...).
    - **Multilevel** -- Random with large Z jumps; route folds back.

    Rooms are separated by a minimum gap of 64 units to guarantee ramp
    corridor space and eliminate Z-fighting between adjacent outer shells.
    Zone-based texturing groups rooms in batches of 4 so each zone shares
    a cohesive texture palette.

    Returns the ordered list of :class:`Room` objects.
    """
    rooms: List[Room] = []
    cx, cy, cz = 0, 0, 0

    # Pick ONE cohesive texture set for the entire map, plus a secondary
    # accent used for outline borders.
    _map_floor = random.choice(FLOOR_TEX)
    _map_wall  = random.choice(WALL_TEX)
    _map_ceil  = random.choice(CEIL_TEX)
    # Accent: pick a different wall texture for outlines
    _accent_candidates = [t for t in WALL_TEX if t != _map_wall]
    _map_accent = random.choice(_accent_candidates) if _accent_candidates else _map_wall

    def _zone_tex(_zone: int):
        return (_map_floor, _map_wall, _map_ceil)

    layout = cfg.get("layout_style", "Zigzag")
    rpt    = max(1, cfg.get("rooms_per_turn", 3))
    t_air  = cfg.get("t_air", 0.68)

    DIRS = [(1, 0), (0, -1), (-1, 0), (0, 1)]
    dir_idx = 0
    dx, dy  = DIRS[dir_idx]

    axis = 'x'
    rooms_in_seg    = 0
    seg_turn_at     = rpt
    rooms_since_corner = 999          # large default so early rooms can have Z var
    rooms_since_ramp   = 999          # ensure >=2 rooms gap between ramps
    prev_was_corner_room = False

    # Spiral ring tracking: each ring = 4 turns (one full revolution).
    # Alternate Z direction per ring and grow gap to expand outward.
    spiral_turns    = 0
    spiral_ring     = 0
    spiral_z_dir    = 1               # 1 = up, -1 = down
    spiral_gap_grow = 0               # extra gap per ring for XY expansion
    ramp_buffer = min(2, (rpt - 1) // 2)  # adaptive: rpt1→0, rpt2→0, rpt3→1, rpt>=5→2

    for i in range(n):
        # Detect corner: turn will happen after this room
        if layout == "Linear":
            is_corner_room = False
        elif layout == "Snake":
            is_corner_room = (rooms_in_seg + 1 >= seg_turn_at)
        else:
            is_corner_room = (rooms_in_seg + 1 >= rpt)

        room_len, room_cross, room_h, door_hw, u_i = _room_dims_from_physics(i, cfg)

        # Corner rooms: constrain dimensions so the room does not
        # protrude beyond the footprint of its neighbours, eliminating
        # misleading "tails" that look like valid routes.
        #   • room_len  (old direction) ≤ width of room X-1
        #   • room_cross (new direction) ≤ depth of room X+1  (forward-look)
        if is_corner_room and i > 0:
            prev = rooms[i - 1]
            prev_cross = prev.d if prev.travel_axis == 'x' else prev.w
            max_d = cfg.get("max_d", 512)
            room_cross = _snap(min(int(room_cross * 1.3), max_d))
            room_len   = _snap(min(room_len, prev_cross, room_cross))
            # Forward-look: cap cross to the next room's expected cross
            # so the corner doesn't extend beyond the post-turn corridor.
            if i + 1 < n:
                _next_len, next_cross, *_ = _room_dims_from_physics(i + 1, cfg)
                room_cross = _snap(min(room_cross, next_cross))
            corr_frac  = cfg.get("corridor_width_frac", 0.67)
            door_hw    = _snap(_clamp(int(room_cross * corr_frac / 2), 32, room_cross // 2))
        elif prev_was_corner_room and i > 0:
            max_d = cfg.get("max_d", 512)
            room_cross = _snap(min(int(room_cross * 1.2), max_d))
            corr_frac  = cfg.get("corridor_width_frac", 0.67)
            door_hw    = _snap(_clamp(int(room_cross * corr_frac / 2), 32, room_cross // 2))

        # Enforce minimum dimensions (corner capping can produce tiny values)
        min_dim = cfg.get("min_d", 192)
        room_len   = max(room_len, min_dim)
        room_cross = max(room_cross, min_dim)

        if layout in ("Random", "Spiral", "Multilevel"):
            if dx != 0:
                w, d   = room_len, room_cross
                t_axis = 'x'
            else:
                w, d   = room_cross, room_len
                t_axis = 'y'
        else:
            t_axis = axis
            if axis == 'x':
                w, d = room_len, room_cross
            else:
                w, d = room_cross, room_len

        # Z variation (only when far enough from corners AND from other ramps).
        # Caps:
        #   - floor dz <= 50 % of previous room height
        #   - ramp angle <= 30 deg given available run-up
        #   - both rooms must be at least 256u long (MIN_FLAT) for ramp space
        if i > 0 and cfg.get("height_var", True):
            prev_room = rooms[i - 1]
            prev_h = prev_room.h
            prev_len = prev_room.w if prev_room.travel_axis == 'x' else prev_room.d
            # Only block ramps if BOTH rooms are too short for any ramp
            too_short = room_len < 192 and prev_len < 192
            if rooms_since_corner <= ramp_buffer or rooms_since_ramp < 2 or too_short:
                dz = 0
            else:
                height_cap = _snap(int(prev_h * 0.5), 32)
                avail_len = 64 + min(room_len, prev_len) // 2
                angle_cap = _snap(int(avail_len / MIN_SLOPE_RATIO), 32)
                if layout == "Multilevel":
                    max_step = _snap(min(height_cap, angle_cap), 64)
                    max_step = max(64, max_step)
                    dz_choices = [max_step // 2, max_step, -max_step // 2, -max_step,
                                  max_step // 4, -max_step // 4]
                elif layout == "Spiral":
                    # Consistent Z direction per ring (up or down)
                    max_step = _snap(min(height_cap, angle_cap), 32)
                    max_step = max(32, max_step)
                    half = max_step // 2
                    sz = spiral_z_dir
                    dz_choices = [sz * half, sz * max_step]
                else:
                    max_step = _snap(min(height_cap, angle_cap), 32)
                    max_step = max(32, max_step)
                    half     = max_step // 2
                    dz_choices = [half, max_step, -half, -max_step]
                dz = random.choice(dz_choices)
                # Early rooms: up-ramps from room 3+ (i>=2), down-ramps from room 2+ (i>=1)
                if dz > 0 and i < 2:
                    dz = 0    # no up-ramps before room 3
                if dz < 0 and i < 1:
                    dz = 0    # no down-ramps before room 2 (dead code: i>0 above)
            cz += dz
            cz  = _snap(cz, 32)
            prev_ceil = rooms[i - 1].z1 + rooms[i - 1].h
            cz = min(cz, prev_ceil - DOOR_H)
            if layout != "Multilevel":
                cz = max(cz, 0)
            else:
                cz = max(cz, -2048)

        # Z collision avoidance for folding layouts.
        # Use a clearance proportional to room height so that floor levels
        # remain visually separated even after ceiling alignment inflates
        # room heights.  This keeps post-alignment Z overlap under ~40 %.
        if layout in ("Random", "Spiral", "Multilevel") and i > 0:
            CLEARANCE = max(64, int(room_h * 0.6))
            prev_room = rooms[i - 1]

            xy_overlaps = [
                r for r in rooms
                if r is not prev_room
                and _xy_overlap(cx, cy, cx + w, cy + d,
                                r.x1, r.y1, r.x2, r.y2)
                and r.z1 < cz + room_h + CLEARANCE
                and cz < r.z1 + r.h + CLEARANCE
            ]
            if xy_overlaps:
                ov_z_ceil  = max(r.z1 + r.h for r in xy_overlaps)
                ov_z_floor = min(r.z1       for r in xy_overlaps)
                z_above = _snap(ov_z_ceil  + CLEARANCE, 32)
                z_below = _snap(ov_z_floor - room_h - CLEARANCE, 32)
                if abs(z_above - prev_room.z1) <= abs(z_below - prev_room.z1):
                    cz = z_above
                else:
                    cz = z_below
                if layout != "Multilevel":
                    cz = max(cz, 0)
                else:
                    cz = max(cz, -2048)

        # Update ramp counter based on ACTUAL height diff (after all Z
        # adjustments including collision avoidance).
        if i > 0 and abs(cz - rooms[i - 1].z1) >= 32:
            rooms_since_ramp = 0
        else:
            rooms_since_ramp += 1

        _ft, _wt, _ct = _zone_tex(i)
        r = Room(x=cx, y=cy, z=cz,
                 w=w, d=d, h=room_h,
                 idx=i,
                 floor_t=_ft, wall_t=_wt, ceil_t=_ct,
                 accent_t=_map_accent,
                 travel_axis=t_axis,
                 speed_in=u_i,
                 door_hw=door_hw)
        rooms.append(r)

        reach = u_i * t_air
        gap   = max(64, _snap(random.uniform(0.0, reach * 0.25)))
        if layout == "Spiral":
            gap += spiral_gap_grow

        # Advance cursor
        if layout in ("Random", "Spiral", "Multilevel"):
            cx += dx * (w + gap)
            cy += dy * (d + gap)
        else:
            if axis == 'x':
                cx += w + gap
            else:
                cy += d + gap

        prev_was_corner_room = is_corner_room
        if is_corner_room:
            rooms_since_corner = 0
        else:
            rooms_since_corner += 1

        # Turn logic
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
                turn = random.choice([-1, 1])
                dir_idx = (dir_idx + turn) % 4
                dx, dy  = DIRS[dir_idx]
            elif layout == "Spiral":
                dir_idx = (dir_idx + 1) % 4
                dx, dy  = DIRS[dir_idx]
                spiral_turns += 1
                if spiral_turns % 4 == 0:
                    spiral_ring += 1
                    spiral_z_dir *= -1       # alternate up/down each ring
                    spiral_gap_grow += 32    # gentle outward expansion
            else:
                prev_axis = axis
                axis = 'y' if axis == 'x' else 'x'
                if layout == "Snake":
                    seg_turn_at = random.randint(max(1, rpt - 1), rpt + 2)
                next_len, next_cross = (
                    _room_dims_from_physics(i + 1, cfg)[:2]
                    if i + 1 < n else (room_len, room_cross)
                )
                if prev_axis == 'x':
                    cy = r.cy() - next_cross // 2
                else:
                    cx = r.cx() - next_cross // 2

    return rooms


# ══════════════════════════════════════════════════════════════════════════════
#  BRIDGE BUILDING
# ══════════════════════════════════════════════════════════════════════════════

def _pick_overlap_center(a1: int, a2: int, b1: int, b2: int,
                         door_hw: int) -> Optional[Tuple[int, int]]:
    """Find the centre of the overlapping span between two ranges.

    Returns ``(center, effective_hw)`` if the overlap is wide enough for a
    door opening (at least 32 units on each side), or ``None`` otherwise.
    The centre is snapped to the grid.
    """
    lo = max(a1, b1)
    hi = min(a2, b2)
    span = hi - lo
    if span <= 0:
        return None
    effective_hw = min(door_hw, span // 2)
    if effective_hw < 32:
        return None
    center = (lo + hi) // 2
    center = _snap(center)
    center = max(lo + effective_hw, min(hi - effective_hw, center))
    return center, effective_hw


def _try_bridge(i: int, j: int, rooms: List[Room]) -> Optional[Bridge]:
    """Attempt to create a bridge between rooms[i] and rooms[j].

    Tests all four possible wall adjacencies (b right/left/above/below a).
    When rooms overlap in XY no bridge is needed (shared open space).
    Returns a :class:`Bridge` or ``None``.
    """
    a, b = rooms[i], rooms[j]

    def _dhw(gap, cross_a, cross_b):
        if gap == 0:
            return min(cross_a, cross_b) // 2
        return min(a.door_hw, b.door_hw)

    if b.x1 >= a.x2:
        gap = b.x1 - a.x2
        dhw = _dhw(gap, a.d, b.d)
        result = _pick_overlap_center(a.y1, a.y2, b.y1, b.y2, dhw)
        if result is not None:
            yc, dhw = result
            return Bridge(i, j, 'x', a.x2, yc, a.z1, b.x1, yc, b.z1,
                          door_hw=dhw,
                          floor_t=a.floor_t, wall_t=a.wall_t, ceil_t=a.ceil_t)
    elif a.x1 >= b.x2:
        gap = a.x1 - b.x2
        dhw = _dhw(gap, a.d, b.d)
        result = _pick_overlap_center(a.y1, a.y2, b.y1, b.y2, dhw)
        if result is not None:
            yc, dhw = result
            return Bridge(i, j, 'x', a.x1, yc, a.z1, b.x2, yc, b.z1,
                          door_hw=dhw,
                          floor_t=a.floor_t, wall_t=a.wall_t, ceil_t=a.ceil_t)
    elif b.y1 >= a.y2:
        gap = b.y1 - a.y2
        dhw = _dhw(gap, a.w, b.w)
        result = _pick_overlap_center(a.x1, a.x2, b.x1, b.x2, dhw)
        if result is not None:
            xc, dhw = result
            return Bridge(i, j, 'y', xc, a.y2, a.z1, xc, b.y1, b.z1,
                          door_hw=dhw,
                          floor_t=a.floor_t, wall_t=a.wall_t, ceil_t=a.ceil_t)
    elif a.y1 >= b.y2:
        gap = a.y1 - b.y2
        dhw = _dhw(gap, a.w, b.w)
        result = _pick_overlap_center(a.x1, a.x2, b.x1, b.x2, dhw)
        if result is not None:
            xc, dhw = result
            return Bridge(i, j, 'y', xc, a.y1, a.z1, xc, b.y2, b.z1,
                          door_hw=dhw,
                          floor_t=a.floor_t, wall_t=a.wall_t, ceil_t=a.ceil_t)
    return None


def build_bridges(rooms: List[Room]):
    """Build sequential bridges plus optional shortcut bridges for multi-route.

    Sequential bridges connect each room[i] to room[i+1].  Shortcut bridges
    connect room[i] to room[i+2] or room[i+3] when their centroids are close
    enough (Manhattan distance < 1200 units), creating parallel paths.

    Returns ``(bridges, all_pairs)`` where *all_pairs* includes containment
    pairs (rooms that share XY space without needing a corridor brush).
    """
    bridges: List[Bridge] = []
    paired: set = set()

    for i in range(len(rooms) - 1):
        br = _try_bridge(i, i + 1, rooms)
        if br is not None:
            bridges.append(br)
            paired.add((i, i + 1))
        else:
            a, b = rooms[i], rooms[i + 1]
            if _xy_overlap(a.x1, a.y1, a.x2, a.y2, b.x1, b.y1, b.x2, b.y2):
                floor_dz = abs(a.z1 - b.z1)
                if floor_dz < 32:
                    # Same level, shared open space — no bridge needed
                    paired.add((i, i + 1))
                else:
                    # Overlapping XY but different Z — need a ramp bridge.
                    # Pick the dominant overlap axis and create one.
                    xov = min(a.x2, b.x2) - max(a.x1, b.x1)
                    yov = min(a.y2, b.y2) - max(a.y1, b.y1)
                    hw = min(a.door_hw, b.door_hw)
                    if xov >= yov:
                        xc = (max(a.x1, b.x1) + min(a.x2, b.x2)) // 2
                        xc = _snap(xc)
                        bridges.append(Bridge(
                            i, i + 1, 'y',
                            xc, a.y2 if a.cy() < b.cy() else a.y1, a.z1,
                            xc, b.y1 if a.cy() < b.cy() else b.y2, b.z1,
                            door_hw=min(hw, xov // 2),
                            floor_t=a.floor_t, wall_t=a.wall_t, ceil_t=a.ceil_t))
                    else:
                        yc = (max(a.y1, b.y1) + min(a.y2, b.y2)) // 2
                        yc = _snap(yc)
                        bridges.append(Bridge(
                            i, i + 1, 'x',
                            a.x2 if a.cx() < b.cx() else a.x1, yc, a.z1,
                            b.x1 if a.cx() < b.cx() else b.x2, yc, b.z1,
                            door_hw=min(hw, yov // 2),
                            floor_t=a.floor_t, wall_t=a.wall_t, ceil_t=a.ceil_t))
                    paired.add((i, i + 1))

    # Collect which rooms already have ramp bridges
    ramp_rooms: set = set()
    for br in bridges:
        if abs(br.bz - br.az) >= 32:
            ramp_rooms.add(br.room_a)
            ramp_rooms.add(br.room_b)

    for i in range(len(rooms)):
        for skip in (2, 3):
            j = i + skip
            if j >= len(rooms):
                break
            if (i, j) in paired:
                continue
            a, b = rooms[i], rooms[j]
            dist = abs(a.cx() - b.cx()) + abs(a.cy() - b.cy())
            if dist < 1200:
                br = _try_bridge(i, j, rooms)
                if br is not None:
                    # Skip shortcut if it would create a ramp and either
                    # endpoint already touches an existing ramp bridge
                    if abs(br.bz - br.az) >= 32:
                        if i in ramp_rooms or j in ramp_rooms:
                            continue
                    bridges.append(br)
                    paired.add((i, j))
                    if abs(br.bz - br.az) >= 32:
                        ramp_rooms.add(i)
                        ramp_rooms.add(j)
                    break

    return bridges, paired
