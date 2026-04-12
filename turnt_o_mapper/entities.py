"""
Quake 3 entity generation and room geometry post-processing.

Provides:
- ``ent_kv`` / ``ent_brush_box`` -- serialise point / brush entities.
- ``align_room_ceilings`` -- raise ceilings so connected rooms match.
- ``_add_passthrough_doors`` -- punch door openings for bridges that
  cross through intermediate rooms.
- ``_compute_footprint_clips`` / ``_compute_wall_clips`` -- determine
  which regions of a room's floor/ceiling/walls overlap with other rooms
  and should be omitted.
"""

from typing import Dict, List

from .constants import TRIGGER_TEX, DOOR_H, WALL_T
from .models import Room, Bridge
from .brushes import box_faces, write_brush
from .layout import _snap


def ent_kv(**kv):
    """Serialise a point entity as key-value pairs in Quake .map format.

    Example output::

        {
        "classname" "info_player_start"
        "origin" "0 0 32"
        }
    """
    lines = ["{"]
    for k, v in kv.items():
        lines.append(f'"{k}" "{v}"')
    lines.append("}")
    return "\n".join(lines)


def ent_brush_box(cls, x1, y1, z1, x2, y2, z2, target="", extra=None):
    """Create a trigger brush entity (e.g. trigger_multiple) as an AABB.

    Parameters:
        cls: entity classname (e.g. ``"trigger_multiple"``).
        x1..z2: bounding box extents.
        target: optional target entity name.
        extra: optional dict of additional key-value pairs.

    Returns the complete entity string ready to append to the .map.
    """
    fs = box_faces(x1, y1, z1, x2, y2, z2,
                   TRIGGER_TEX, TRIGGER_TEX, TRIGGER_TEX,
                   TRIGGER_TEX, TRIGGER_TEX, TRIGGER_TEX)
    br = write_brush(fs)
    kv = {"classname": cls}
    if target:
        kv["target"] = target
    if extra:
        kv.update(extra)
    lines = ["{"]
    for k, v in kv.items():
        lines.append(f'"{k}" "{v}"')
    lines.append(br)
    lines.append("}")
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════════════
#  CEILING ALIGNMENT
# ══════════════════════════════════════════════════════════════════════════════

def align_room_ceilings(rooms: List[Room], bridges: List[Bridge]):
    """Raise room ceilings so all bridged rooms share the same ceiling Z.

    Uses a fixed-point loop so heights propagate through multi-hop connections
    (including shortcut bridges processed after sequential ones).  Also
    guarantees each room is tall enough for any ramp corridor to fit
    (floor + DOOR_H + WALL_T).

    Modifies ``room.h`` in place.
    """
    n = len(rooms)
    ceil_z = [r.z1 + r.h for r in rooms]

    changed = True
    while changed:
        changed = False
        for br in bridges:
            a, b = rooms[br.room_a], rooms[br.room_b]
            ia, ib = br.room_a, br.room_b
            z_hi = max(a.z1, b.z1)
            min_ceil = z_hi + DOOR_H + WALL_T
            target = max(ceil_z[ia], ceil_z[ib], min_ceil)
            if ceil_z[ia] < target:
                ceil_z[ia] = target; changed = True
            if ceil_z[ib] < target:
                ceil_z[ib] = target; changed = True

    for i, room in enumerate(rooms):
        room.h = _snap(ceil_z[i]) - room.z1


# ══════════════════════════════════════════════════════════════════════════════
#  PASSTHROUGH DOORS
# ══════════════════════════════════════════════════════════════════════════════

def _add_passthrough_doors(rooms, bridges, room_doors):
    """Add door cutouts to rooms whose walls are crossed by a bridge corridor.

    When room B is fully inside room A, a bridge from B to C travels through
    A's wall.  Without an explicit cutout, A's wall would block the path.
    This function scans every bridge against every *other* room and adds door
    entries to ``room_doors`` so that ``room_walls()`` will carve the opening.

    Modifies *room_doors* in place.
    """
    for br in bridges:
        z_bot = min(br.az, br.bz)
        ht    = br.door_ht
        hw    = br.door_hw

        if br.axis == 'x':
            x_lo = min(br.ax, br.bx)
            x_hi = max(br.ax, br.bx)
            yc   = br.ay
            for r in rooms:
                if r.idx in (br.room_a, br.room_b):
                    continue
                if not (z_bot < r.z2 and z_bot + ht > r.z1):
                    continue
                if x_lo < r.x2 < x_hi and yc - hw < r.y2 and yc + hw > r.y1:
                    room_doors[r.idx].append(
                        {'wall': 'wx2', 'center': yc, 'hw': hw,
                         'ht': ht, 'z_bot': z_bot})
                if x_lo < r.x1 < x_hi and yc - hw < r.y2 and yc + hw > r.y1:
                    room_doors[r.idx].append(
                        {'wall': 'wx1', 'center': yc, 'hw': hw,
                         'ht': ht, 'z_bot': z_bot})
        else:
            y_lo = min(br.ay, br.by)
            y_hi = max(br.ay, br.by)
            xc   = br.ax
            for r in rooms:
                if r.idx in (br.room_a, br.room_b):
                    continue
                if not (z_bot < r.z2 and z_bot + ht > r.z1):
                    continue
                if y_lo < r.y2 < y_hi and xc - hw < r.x2 and xc + hw > r.x1:
                    room_doors[r.idx].append(
                        {'wall': 'wy2', 'center': xc, 'hw': hw,
                         'ht': ht, 'z_bot': z_bot})
                if y_lo < r.y1 < y_hi and xc - hw < r.x2 and xc + hw > r.x1:
                    room_doors[r.idx].append(
                        {'wall': 'wy1', 'center': xc, 'hw': hw,
                         'ht': ht, 'z_bot': z_bot})


# ══════════════════════════════════════════════════════════════════════════════
#  FOOTPRINT / WALL CLIP COMPUTATION
# ══════════════════════════════════════════════════════════════════════════════

def _compute_footprint_clips(room, all_rooms, face_z, bridge_clips=(),
                              adjacent_indices=()):
    """Return XY rectangles to subtract from a room's floor or ceiling.

    A region is clipped ONLY when the other room is directly adjacent
    (connected by a bridge) and its Z range strictly contains *face_z*.
    Non-adjacent rooms that happen to share XY space are left alone --
    the map compiler resolves those via CSG.

    Parameters:
        bridge_clips: ``(x1, y1, x2, y2, z_floor)`` footprints of
            corridor / ramp brushes.
        adjacent_indices: set of room indices directly connected to
            *room* via a bridge.
    """
    clips = []
    for j in all_rooms:
        if j is room:
            continue
        if j.idx not in adjacent_indices:
            continue
        if not (j.z1 < face_z < j.z2):
            continue
        xlo = max(room.x1, j.x1); xhi = min(room.x2, j.x2)
        ylo = max(room.y1, j.y1); yhi = min(room.y2, j.y2)
        if xlo < xhi and ylo < yhi:
            clips.append((xlo, ylo, xhi, yhi))

    for bfp in bridge_clips:
        if len(bfp) == 7:
            bx1, by1, bx2, by2, bz_floor, ba_idx, bb_idx = bfp
            # Don't clip rooms connected to this bridge OR rooms
            # between the endpoints (passthrough rooms hit by shortcuts)
            lo_idx = min(ba_idx, bb_idx)
            hi_idx = max(ba_idx, bb_idx)
            if lo_idx <= room.idx <= hi_idx:
                continue
        else:
            bx1, by1, bx2, by2, bz_floor = bfp
        if abs(face_z - bz_floor) > WALL_T:
            continue
        xlo = max(room.x1, bx1); xhi = min(room.x2, bx2)
        ylo = max(room.y1, by1); yhi = min(room.y2, by2)
        if xlo < xhi and ylo < yhi:
            clips.append((xlo, ylo, xhi, yhi))

    return clips


def _compute_wall_clips(room, all_rooms, doors, adjacent_indices=()):
    """Compute wall-clip intervals.

    Two clip sources:

    1. **Nearby rooms** (in *adjacent_indices*): standard wall clipping
       where another room's boundary penetrates this room's wall.

    2. **Far-apart rooms**: if another room's floor level is inside this
       room's Z range AND the rooms overlap in XY, the wall is clipped in
       the overlap area so the other route's floor remains passable.

    Returns a dict compatible with ``room_walls()``::

        {'wx1': [(ylo, yhi), ...], 'wx2': [...],
         'wy1': [(xlo, xhi), ...], 'wy2': [...]}
    """
    clips: Dict[str, list] = {}

    for j in all_rooms:
        if j is room:
            continue
        if not (j.z1 < room.z2 and j.z2 > room.z1):
            continue

        is_nearby = j.idx in adjacent_indices

        if is_nearby:
            # Standard: clip where j's boundary is inside room's wall
            if j.x1 < room.x1 < j.x2:
                ylo = max(room.y1, j.y1); yhi = min(room.y2, j.y2)
                if ylo < yhi:
                    clips.setdefault('wx1', []).append((ylo, yhi))
            if j.x1 < room.x2 < j.x2:
                ylo = max(room.y1, j.y1); yhi = min(room.y2, j.y2)
                if ylo < yhi:
                    clips.setdefault('wx2', []).append((ylo, yhi))
            if j.y1 < room.y1 < j.y2:
                xlo = max(room.x1, j.x1); xhi = min(room.x2, j.x2)
                if xlo < xhi:
                    clips.setdefault('wy1', []).append((xlo, xhi))
            if j.y1 < room.y2 < j.y2:
                xlo = max(room.x1, j.x1); xhi = min(room.x2, j.x2)
                if xlo < xhi:
                    clips.setdefault('wy2', []).append((xlo, xhi))
        else:
            # Far-apart: clip wall where j's floor zone passes through,
            # so the other route remains walkable.
            if not (room.z1 <= j.z1 < room.z2):
                continue  # j's floor not inside this room's Z range
            # Clip each wall in the XY overlap area
            ylo = max(room.y1, j.y1); yhi = min(room.y2, j.y2)
            xlo = max(room.x1, j.x1); xhi = min(room.x2, j.x2)
            if ylo < yhi:
                if room.x1 >= j.x1 and room.x1 <= j.x2:
                    clips.setdefault('wx1', []).append((ylo, yhi))
                if room.x2 >= j.x1 and room.x2 <= j.x2:
                    clips.setdefault('wx2', []).append((ylo, yhi))
            if xlo < xhi:
                if room.y1 >= j.y1 and room.y1 <= j.y2:
                    clips.setdefault('wy1', []).append((xlo, xhi))
                if room.y2 >= j.y1 and room.y2 <= j.y2:
                    clips.setdefault('wy2', []).append((xlo, xhi))

    # Preserve door openings
    for door in doors:
        w_name = door['wall']
        if w_name not in clips:
            continue
        center = door['center']
        hw     = door['hw']
        dlo, dhi = center - hw, center + hw
        kept = []
        for clo, chi in clips[w_name]:
            if chi <= dlo or clo >= dhi:
                kept.append((clo, chi))
            else:
                if clo < dlo:
                    kept.append((clo, dlo))
                if chi > dhi:
                    kept.append((dhi, chi))
        clips[w_name] = kept

    return clips
