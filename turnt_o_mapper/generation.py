"""
Top-level map generation orchestrator.

``generate_map(cfg)`` is the single entry point that:
1. Places rooms using the layout engine.
2. Builds bridges (corridors / ramps) between adjacent rooms.
3. Centres the map around the origin.
4. Aligns ceiling heights across connected rooms.
5. Generates floor, wall, ceiling, and corridor brushes.
6. Runs connectivity (BFS) and ramp-angle validation.
7. Places spawn, timer, and checkpoint entities.

Returns ``(map_string, rooms, bridges, warnings)``.
"""

import math
import random
from typing import Dict, List

from .constants import DOOR_H, WALL_T, SLOPE_RATIO, MAX_RAMP_ANGLE
from .models import Room, Bridge
from .layout import place_rooms, build_bridges, _snap
from .brushes import (
    room_floor, room_ceiling, room_walls, corridor_brushes,
    _adaptive_ramp_len,
)
from .entities import (
    align_room_ceilings, _add_passthrough_doors,
    _compute_footprint_clips, _compute_wall_clips,
    ent_kv, ent_brush_box,
)


def generate_map(cfg: dict):
    """Generate a complete Quake 3 .map from the given configuration dict.

    *cfg* keys used (all optional with defaults):

    - ``n_rooms`` (int): number of rooms to place.
    - ``seed`` (int|None): random seed for reproducibility.
    - ``layout_style`` (str): one of Linear / Zigzag / Snake / Random /
      Spiral / Multilevel.
    - ``rooms_per_turn``, ``corridor_width_frac``, ``height_var``,
      ``checkpoints``, ``use_physics``, ``u_base``, ``u_gain``, ``t_air``,
      ``strafe_f``: physics and layout parameters.
    - ``min_w`` / ``max_w`` / ``min_d`` / ``max_d`` / ``min_h`` / ``max_h``:
      room size limits.

    Returns:
        ``(map_string, rooms, bridges, warnings)`` where *map_string* is the
        full ``.map`` file content, *rooms* and *bridges* are the placed
        objects, and *warnings* is a list of diagnostic messages.
    """
    seed = cfg.get("seed")
    if seed is not None:
        random.seed(seed)

    rooms              = place_rooms(cfg["n_rooms"], cfg)
    bridges, all_pairs = build_bridges(rooms)

    # ── Centre map so bounding box midpoint is at (0, 0) and min-Z = 0 ──
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

    # ── Update travel_axis from actual bridge connections ────────────────
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
            room.travel_axis = 'x' if room.w >= room.d else 'y'

    # ── Align ceiling heights ───────────────────────────────────────────
    align_room_ceilings(rooms, bridges)

    # ── Per-room door cutout data ───────────────────────────────────────
    room_doors: Dict[int, list] = {i: [] for i in range(len(rooms))}
    for br in bridges:
        hw = br.door_hw
        ra, rb = rooms[br.room_a], rooms[br.room_b]
        dz_br  = abs(br.bz - br.az)

        if dz_br >= 32:
            door_ht_lo = ra.h
            door_ht_hi = rb.h
        else:
            max_ht = min(ra.h, rb.h)
            if random.random() < 0.5:
                ht = max_ht
            else:
                ht = _snap(random.randint(DOOR_H, max(DOOR_H, max_ht)), 32)
            door_ht_lo = door_ht_hi = ht

        br.door_ht = max(door_ht_lo, door_ht_hi)
        if br.axis == 'x':
            ra_wall = 'wx2' if br.ax >= ra.x2 - 1 else 'wx1'
            rb_wall = 'wx1' if br.bx <= rb.x1 + 1 else 'wx2'
            room_doors[br.room_a].append(
                {'wall': ra_wall, 'center': br.ay, 'hw': hw,
                 'ht': door_ht_lo, 'z_bot': br.az})
            room_doors[br.room_b].append(
                {'wall': rb_wall, 'center': br.ay, 'hw': hw,
                 'ht': door_ht_hi, 'z_bot': br.bz})
        else:
            ra_wall = 'wy2' if br.ay >= ra.y2 - 1 else 'wy1'
            rb_wall = 'wy1' if br.by <= rb.y1 + 1 else 'wy2'
            room_doors[br.room_a].append(
                {'wall': ra_wall, 'center': br.ax, 'hw': hw,
                 'ht': door_ht_lo, 'z_bot': br.az})
            room_doors[br.room_b].append(
                {'wall': rb_wall, 'center': br.ax, 'hw': hw,
                 'ht': door_ht_hi, 'z_bot': br.bz})

    _add_passthrough_doors(rooms, bridges, room_doors)

    lines = [
        "// Game: Quake 3",
        "// Format: Quake 3 (Valve)",
        f"// Generated by Turnt-o-mapper | rooms={cfg['n_rooms']} seed={seed}",
        "{",
        '"classname" "worldspawn"',
    ]

    bi = 0

    # ── Pass 1: floors ──────────────────────────────────────────────────
    for room in rooms:
        fc = _compute_footprint_clips(room, rooms, room.z1)
        parts, bi = room_floor(room.x1, room.y1, room.z1,
                               room.x2, room.y2, room.z2,
                               room.floor_t, f"r{room.idx}", bi, clips=fc)
        lines.extend(parts)

    # ── Pass 2: walls ───────────────────────────────────────────────────
    for room in rooms:
        sc = _compute_wall_clips(room, rooms, room_doors.get(room.idx, []))
        parts, bi = room_walls(room.x1, room.y1, room.z1,
                               room.x2, room.y2, room.z2,
                               room.wall_t, f"r{room.idx}", bi,
                               doors=room_doors.get(room.idx),
                               side_clips=sc)
        lines.extend(parts)

    # ── Pass 3: ceilings ────────────────────────────────────────────────
    for room in rooms:
        cc = _compute_footprint_clips(room, rooms, room.z2)
        parts, bi = room_ceiling(room.x1, room.y1, room.z1,
                                 room.x2, room.y2, room.z2,
                                 room.ceil_t, f"r{room.idx}", bi, clips=cc)
        lines.extend(parts)

    # ── Pass 4: corridors / ramps ───────────────────────────────────────
    for br in bridges:
        ra = rooms[br.room_a]; rb = rooms[br.room_b]
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

    # ── Pass 5: Connectivity check (BFS from room 0) ───────────────────
    warnings: List[str] = []
    if rooms:
        adj: Dict[int, set] = {i: set() for i in range(len(rooms))}
        for br in bridges:
            adj[br.room_a].add(br.room_b)
            adj[br.room_b].add(br.room_a)
        for (i, j) in all_pairs:
            adj[i].add(j); adj[j].add(i)
        visited: set = {0}
        queue:   list = [0]
        while queue:
            cur = queue.pop()
            for nb in adj[cur]:
                if nb not in visited:
                    visited.add(nb); queue.append(nb)
        unreachable = [i for i in range(len(rooms)) if i not in visited]
        if unreachable:
            msg = f"\u26a0 {len(unreachable)} unreachable room(s): {unreachable}"
            lines.append(f"// {msg}")
            warnings.append(msg)

    # ── Pass 6: Ramp validation ─────────────────────────────────────────
    for br in bridges:
        dz = abs(br.bz - br.az)
        if dz < 32:
            continue
        ra = rooms[br.room_a]; rb = rooms[br.room_b]
        H = WALL_T
        if br.axis == 'x':
            ra_far = ra.x1 if br.ax >= ra.x2 - 1 else ra.x2
            rb_far = rb.x2 if br.bx <= rb.x1 + 1 else rb.x1
            lo_z = br.az if br.ax <= br.bx else br.bz
            hi_z = br.bz if br.ax <= br.bx else br.az
            lo_far = ra_far if br.ax <= br.bx else rb_far
            hi_far = rb_far if br.ax <= br.bx else ra_far
            hi_x = max(br.ax, br.bx)
            lo_x = min(br.ax, br.bx)
            if lo_z <= hi_z:
                x_hi = hi_x - H
                x_lo_limit = (lo_far + H) if lo_far is not None else (x_hi - int(dz * SLOPE_RATIO))
                max_available = x_hi - x_lo_limit
            else:
                x_lo = lo_x + H
                x_hi_limit = (hi_far - H) if hi_far is not None else (x_lo + int(dz * SLOPE_RATIO))
                max_available = x_hi_limit - x_lo
            ramp_len = _adaptive_ramp_len(dz, max_available)
        else:
            ra_far = ra.y1 if br.ay >= ra.y2 - 1 else ra.y2
            rb_far = rb.y2 if br.by <= rb.y1 + 1 else rb.y1
            lo_zy = br.az if br.ay <= br.by else br.bz
            hi_zy = br.bz if br.ay <= br.by else br.az
            lo_fy = ra_far if br.ay <= br.by else rb_far
            hi_fy = rb_far if br.ay <= br.by else ra_far
            hi_y = max(br.ay, br.by)
            lo_y = min(br.ay, br.by)
            if lo_zy <= hi_zy:
                y_hi = hi_y - H
                y_lo_limit = (lo_fy + H) if lo_fy is not None else (y_hi - int(dz * SLOPE_RATIO))
                max_available = y_hi - y_lo_limit
            else:
                y_lo = lo_y + H
                y_hi_limit = (hi_fy - H) if hi_fy is not None else (y_lo + int(dz * SLOPE_RATIO))
                max_available = y_hi_limit - y_lo
            ramp_len = _adaptive_ramp_len(dz, max_available)
        if ramp_len > 0:
            angle = math.degrees(math.atan2(dz, ramp_len))
            if angle > MAX_RAMP_ANGLE:
                msg = (f"\u26a0 Ramp r{br.room_a}\u2192r{br.room_b}: "
                       f"angle {angle:.1f}\u00b0 exceeds {MAX_RAMP_ANGLE}\u00b0 "
                       f"(dz={dz}, len={ramp_len}, avail={max_available})")
                lines.append(f"// {msg}")
                warnings.append(msg)
        if br.axis == 'x' and not (ra.x1 - 1 <= br.ax <= ra.x2 + 1):
            msg = (f"\u26a0 Ramp r{br.room_a}\u2192r{br.room_b}: "
                   f"ax={br.ax} outside room_a X [{ra.x1},{ra.x2}]")
            lines.append(f"// {msg}")
            warnings.append(msg)
        elif br.axis == 'y' and not (ra.y1 - 1 <= br.ay <= ra.y2 + 1):
            msg = (f"\u26a0 Ramp r{br.room_a}\u2192r{br.room_b}: "
                   f"ay={br.ay} outside room_a Y [{ra.y1},{ra.y2}]")
            lines.append(f"// {msg}")
            warnings.append(msg)

    # ── Entities ────────────────────────────────────────────────────────
    ei    = 1
    first = rooms[0]
    last  = rooms[-1]

    SL = 8
    first_doors = room_doors.get(0, [])
    exit_wall = first_doors[0]['wall'] if first_doors else 'wx2'
    if exit_wall == 'wx2':
        spawn_x = first.x1 + 32; spawn_y = first.cy(); spawn_angle = "0"
        sx1 = first.x1 + 64;  sx2 = sx1 + SL; sy1 = first.y1; sy2 = first.y2
    elif exit_wall == 'wx1':
        spawn_x = first.x2 - 32; spawn_y = first.cy(); spawn_angle = "180"
        sx1 = first.x2 - 64 - SL; sx2 = sx1 + SL; sy1 = first.y1; sy2 = first.y2
    elif exit_wall == 'wy2':
        spawn_x = first.cx(); spawn_y = first.y1 + 32; spawn_angle = "90"
        sx1 = first.x1; sx2 = first.x2; sy1 = first.y1 + 64; sy2 = sy1 + SL
    else:
        spawn_x = first.cx(); spawn_y = first.y2 - 32; spawn_angle = "270"
        sx1 = first.x1; sx2 = first.x2; sy1 = first.y2 - 64 - SL; sy2 = sy1 + SL
    spawn_z = first.z1 + 32
    lines.append(f"\n// entity {ei}")
    lines.append(ent_kv(classname="info_player_start",
                        origin=f"{spawn_x} {spawn_y} {spawn_z}",
                        angle=spawn_angle))
    ei += 1

    lines.append(f"\n// entity {ei}")
    lines.append(ent_brush_box("trigger_multiple",
        sx1, sy1, first.z1, sx2, sy2, first.z2,
        target="target_startTimer"))
    ei += 1

    lines.append(f"\n// entity {ei}")
    lines.append(ent_kv(classname="target_startTimer",
                        origin=f"{(sx1+sx2)//2} {(sy1+sy2)//2} {first.z1 + first.h // 2}",
                        targetname="target_startTimer"))
    ei += 1

    if last.travel_axis == 'x':
        ex1 = last.x2 - SL;  ex2 = last.x2
        ey1 = last.y1;       ey2 = last.y2
    else:
        ex1 = last.x1;       ex2 = last.x2
        ey1 = last.y2 - SL;  ey2 = last.y2
    lines.append(f"\n// entity {ei}")
    lines.append(ent_brush_box("trigger_multiple",
        ex1, ey1, last.z1, ex2, ey2, last.z2,
        target="target_stopTimer"))
    ei += 1

    lines.append(f"\n// entity {ei}")
    lines.append(ent_kv(classname="target_stopTimer",
                        origin=f"{last.cx()} {last.cy()} {last.z1 + last.h // 2}",
                        targetname="target_stopTimer"))
    ei += 1

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
                tx1, ty1, room.z1, tx2, ty2, room.z2,
                target=tname))
            ei += 1
            lines.append(f"\n// entity {ei}")
            lines.append(ent_kv(classname="target_checkpoint",
                                origin=f"{room.cx()} {room.cy()} {room.z1 + room.h // 2}",
                                targetname=tname,
                                count=str(cp_n)))
            ei += 1

    return "\n".join(lines), rooms, bridges, warnings
