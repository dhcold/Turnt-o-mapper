"""
Diabotical (DBT) .rbe map file importer.

Parses the binary .rbe format, performs greedy block merging, converts
corner and cylinder geometry, maps entities to Quake equivalents, and
produces a complete .map string.

The main entry point is ``run_import()`` which orchestrates the full
pipeline and accepts a ``log_fn`` callback for progress reporting.
"""

import math
import sys
import time
from typing import Dict, List, Optional

# Allow running this file directly (e.g. for quick testing)
try:
    from .constants import ALL_TEXTURES, NODRAW_TEX
    from .brushes import face, box_faces, write_brush
    from .models import Room
except ImportError:
    import os as _os
    sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
    from turnt_o_mapper.constants import ALL_TEXTURES, NODRAW_TEX
    from turnt_o_mapper.brushes import face, box_faces, write_brush
    from turnt_o_mapper.models import Room


# ══════════════════════════════════════════════════════════════════════════════
#  RBE BINARY PARSER
# ══════════════════════════════════════════════════════════════════════════════

def parse_rbe(filepath):
    """Parse a Diabotical .rbe map file from disk.

    Returns ``(blocks, materials, entities, ver)`` where:

    - **blocks** -- list of dicts with keys ``x, y, z`` (grid ints),
      ``type`` (uint8), ``mats`` (dict of face->material-index), ``orient``.
    - **materials** -- list of material name strings (index 0 is ``"default"``).
    - **entities** -- list of dicts with ``name``, ``x, y, z`` (floats),
      rotation/scale fields, and a ``properties`` list.
    - **ver** -- format version integer.
    """
    import struct, gzip as gz

    def ri(f, n=4):
        return int.from_bytes(f.read(n), "little", signed=True)

    def rf(f):
        return struct.unpack('<f', f.read(4))[0]

    with open(filepath, 'rb') as raw:
        raw.read(4)          # magic 'REBM'
        ver      = ri(raw)
        ri(raw)              # u1
        ri(raw)              # padding1

        if ver > 21:
            author_len = ri(raw)
            raw.read(author_len)
            raw.read(8)
            f = gz.GzipFile(fileobj=raw)
        else:
            f = raw

        mat_count = ri(f, 1)
        materials = ["default"]
        for _ in range(mat_count - 1):
            c = ri(f, 4)
            materials.append(f.read(c).decode("utf-8"))

        ri(f, 4)  # u2
        block_count = ri(f, 4)
        blocks = []
        for _ in range(block_count):
            b = {
                "x":    ri(f, 4),
                "y":    ri(f, 4),
                "z":    ri(f, 4),
                "type": ri(f, 1),
            }
            f.read(12)
            b["mats"] = {
                "front":  ri(f, 1),
                "left":   ri(f, 1),
                "back":   ri(f, 1),
                "right":  ri(f, 1),
                "top":    ri(f, 1),
                "bottom": ri(f, 1),
            }
            f.read(1)
            f.read(12)
            if ver > 24:
                f.read(6)
                b["orient"] = ri(f, 1)
                f.read(2)
            else:
                b["orient"] = ri(f, 1)
                f.read(1)
            blocks.append(b)

        u3_count = ri(f, 4)
        for _ in range(u3_count):
            f.read(16)

        entity_count = ri(f, 4)
        entities = []
        for _ in range(entity_count):
            c = ri(f, 4)
            e = {
                "name":   f.read(c).decode("utf-8"),
                "x":      rf(f), "y": rf(f), "z": rf(f),
                "xrot":   rf(f), "yrot": rf(f), "zrot": rf(f),
                "xscale": rf(f), "yscale": rf(f), "zscale": rf(f),
            }
            prop_count = ri(f, 4)
            e["properties"] = []
            for _ in range(prop_count):
                c = ri(f, 4)
                name = f.read(c).decode("utf-8")
                c = ri(f, 4)
                val = f.read(c).decode("utf-8")
                e["properties"].append({"name": name, "val": val})
            entities.append(e)

    return blocks, materials, entities, ver


# ══════════════════════════════════════════════════════════════════════════════
#  GREEDY BLOCK MERGING
# ══════════════════════════════════════════════════════════════════════════════

def greedy_merge(blocks):
    """Merge adjacent blocks into axis-aligned boxes (greedy meshing).

    Blocks are on an integer grid in Diabotical coordinates (Y is up).
    Returns list of ``(x1, y1, z1, x2, y2, z2)`` with exclusive-max values.
    """
    bset = {(b["x"], b["y"], b["z"]) for b in blocks}
    visited = set()
    merged = []

    for (bx, by, bz) in sorted(bset):
        if (bx, by, bz) in visited:
            continue

        x2 = bx
        while (x2 + 1, by, bz) in bset and (x2 + 1, by, bz) not in visited:
            x2 += 1

        z2 = bz
        while all(
            (xi, by, z2 + 1) in bset and (xi, by, z2 + 1) not in visited
            for xi in range(bx, x2 + 1)
        ):
            z2 += 1

        y2 = by
        while all(
            (xi, y2 + 1, zi) in bset and (xi, y2 + 1, zi) not in visited
            for xi in range(bx, x2 + 1)
            for zi in range(bz, z2 + 1)
        ):
            y2 += 1

        for xi in range(bx, x2 + 1):
            for yi in range(by, y2 + 1):
                for zi in range(bz, z2 + 1):
                    visited.add((xi, yi, zi))

        merged.append((bx, by, bz, x2 + 1, y2 + 1, z2 + 1))

    return merged


# ══════════════════════════════════════════════════════════════════════════════
#  CORNER BLOCK CONVERSION
# ══════════════════════════════════════════════════════════════════════════════

def merge_corners(blocks):
    """Group type-3 corner blocks by (x, z, orient) and merge contiguous Y runs.

    Returns list of ``(bx, bz, by_lo, by_hi_excl, orient)`` tuples.
    """
    from collections import defaultdict
    groups = defaultdict(list)
    for b in blocks:
        groups[(b["x"], b["z"], b.get("orient", 0))].append(b["y"])

    result = []
    for (bx, bz, orient), ys in groups.items():
        ys_sorted = sorted(set(ys))
        run_start = ys_sorted[0]
        run_end   = ys_sorted[0]
        for y in ys_sorted[1:]:
            if y == run_end + 1:
                run_end = y
            else:
                result.append((bx, bz, run_start, run_end + 1, orient))
                run_start = run_end = y
        result.append((bx, bz, run_start, run_end + 1, orient))
    return result


def corner_brush(bx, bz, by_lo, by_hi, orient, sx, sy, sz, tex):
    """Generate a 5-face pentahedron brush for a merged DBT corner group.

    Axis mapping: dbt.X -> Q.X, dbt.Z -> Q.Y, dbt.Y -> Q.Z.

    Orientations (0-3) determine which corner of the XY square holds the
    right angle of the triangle.
    """
    qx1, qx2 = bx * sx, (bx + 1) * sx
    qy1, qy2 = bz * sy, (bz + 1) * sy
    n_slabs  = by_hi - by_lo
    qz_bot   = by_lo * sz
    qz_top   = qz_bot + n_slabs * sz

    f_bot = face((qx1, qy1, qz_bot), (qx2, qy1, qz_bot), (qx1, qy2, qz_bot), tex)
    f_top = face((qx2, qy2, qz_top), (qx2, qy1, qz_top), (qx1, qy1, qz_top), tex)

    if orient == 0:
        f_w1  = face((qx2, qy2, qz_top), (qx2, qy2, qz_bot), (qx2, qy1, qz_top), tex)
        f_w2  = face((qx1, qy1, qz_bot), (qx1, qy1, qz_top), (qx2, qy1, qz_bot), tex)
        f_dia = face((qx2, qy2, qz_top), (qx1, qy1, qz_top + 1), (qx1, qy1, qz_top), tex)
    elif orient == 1:
        f_w1  = face((qx2, qy2, qz_top), (qx2, qy2, qz_bot), (qx2, qy1, qz_top), tex)
        f_w2  = face((qx2, qy2, qz_top), (qx1, qy2, qz_top), (qx2, qy2, qz_bot), tex)
        f_dia = face((qx1, qy2, qz_top), (qx2, qy1, qz_top + 1), (qx2, qy1, qz_top), tex)
    elif orient == 2:
        f_w1  = face((qx1, qy1, qz_bot), (qx1, qy2, qz_bot), (qx1, qy1, qz_top), tex)
        f_w2  = face((qx2, qy2, qz_top), (qx1, qy2, qz_top), (qx2, qy2, qz_bot), tex)
        f_dia = face((qx1, qy1, qz_top), (qx2, qy2, qz_top + 1), (qx2, qy2, qz_top), tex)
    else:  # orient == 3
        f_w1  = face((qx1, qy1, qz_bot), (qx1, qy2, qz_bot), (qx1, qy1, qz_top), tex)
        f_w2  = face((qx1, qy1, qz_bot), (qx1, qy1, qz_top), (qx2, qy1, qz_bot), tex)
        f_dia = face((qx1, qy2, qz_top), (qx2, qy1, qz_top), (qx2, qy1, qz_top + 1), tex)

    return write_brush([f_bot, f_top, f_w1, f_w2, f_dia],
                       f"corner o{orient}")


# ══════════════════════════════════════════════════════════════════════════════
#  CYLINDER BRUSH GENERATION
# ══════════════════════════════════════════════════════════════════════════════

def cylinder_brushes(cx, cy, z_bot, z_top, inner_r, outer_r,
                     angle_start, angle_end, step_qu, tex):
    """Generate brushes approximating a hollow cylinder wall arc.

    Returns a list of brush strings.

    Parameters:
        cx, cy: centre of curvature in Quake XY.
        z_bot, z_top: vertical extent.
        inner_r, outer_r: wall radii in Quake units.
        angle_start, angle_end: arc in radians (counter-clockwise).
        step_qu: target arc-length per segment in Quake units.
    """
    arc_len = abs(angle_end - angle_start) * (inner_r + outer_r) / 2
    n_seg = max(1, round(arc_len / step_qu))
    da = (angle_end - angle_start) / n_seg
    brushes = []

    for i in range(n_seg):
        a0 = angle_start + i * da
        a1 = angle_start + (i + 1) * da
        ca0, sa0 = math.cos(a0), math.sin(a0)
        ca1, sa1 = math.cos(a1), math.sin(a1)

        ix0, iy0 = cx + inner_r * ca0, cy + inner_r * sa0
        ix1, iy1 = cx + inner_r * ca1, cy + inner_r * sa1
        ox0, oy0 = cx + outer_r * ca0, cy + outer_r * sa0
        ox1, oy1 = cx + outer_r * ca1, cy + outer_r * sa1
        zb, zt = z_bot, z_top

        A = (ix0, iy0, zb)
        B = (ix1, iy1, zb)
        C = (ox0, oy0, zb)
        D = (ox1, oy1, zb)
        E = (ix0, iy0, zt)
        F = (ix1, iy1, zt)
        G = (ox0, oy0, zt)
        H = (ox1, oy1, zt)

        f_bot   = face(A, C, B, tex)
        f_top   = face(F, G, E, tex)
        f_inner = face(A, B, E, tex)
        f_outer = face(C, G, D, tex)
        f_side0 = face(C, G, A, tex)
        f_side1 = face(B, H, D, tex)

        brushes.append(write_brush(
            [f_bot, f_top, f_inner, f_outer, f_side0, f_side1],
            f"cyl_seg {i}"))

    return brushes


# ══════════════════════════════════════════════════════════════════════════════
#  ENTITY CONVERSION
# ══════════════════════════════════════════════════════════════════════════════

def rbe_entities_to_map(entities, sx, sy, sz, opaque_tex="turnt/turnt_concrete"):
    """Convert Diabotical entities to Quake .map entity strings.

    Handles spawn, start/stop timers, checkpoints, and prop brushes
    (boxes, diagonals, corners, cylinders).

    Returns ``(worldspawn_brushes, entity_lines)``.
    """
    EFX = sx / 40.0
    EFY = sy / 40.0
    EFZ = sz / 20.0
    MIN_HALF = 8.0
    TRIG_TEX = "common/trigger"

    lines = []
    brushes = []
    split_count = 0

    for e in entities:
        nm  = e["name"]
        qx = e["x"] * EFX
        qy = e["z"] * EFY
        qz = e["y"] * EFZ
        props = {p["name"]: p["val"] for p in e.get("properties", [])}

        if nm == "spawn":
            lines += [
                "{",
                '"classname" "info_player_start"',
                f'"origin" "{qx:g} {qy:g} {qz:g}"',
                '"angle" "0"',
                "}",
            ]

        elif nm.startswith("trigger_start"):
            hx = max(MIN_HALF, abs(e["xscale"]) * EFX / 2.0)
            hy = max(MIN_HALF, abs(e["zscale"]) * EFY / 2.0)
            hz = max(MIN_HALF, abs(e["yscale"]) * EFZ / 2.0)
            fs = box_faces(qx - hx, qy - hy, qz - hz,
                           qx + hx, qy + hy, qz + hz,
                           TRIG_TEX, TRIG_TEX, TRIG_TEX,
                           TRIG_TEX, TRIG_TEX, TRIG_TEX)
            lines += [
                "{",
                '"classname" "trigger_multiple"',
                '"target" "target_startTimer"',
                write_brush(fs, f"trigger {nm}"),
                "}",
            ]
            lines += [
                "{",
                '"classname" "target_startTimer"',
                f'"origin" "{qx:g} {qy:g} {qz:g}"',
                '"targetname" "target_startTimer"',
                "}",
            ]

        elif nm.startswith("trigger_end"):
            hx = max(MIN_HALF, abs(e["xscale"]) * EFX / 2.0)
            hy = max(MIN_HALF, abs(e["zscale"]) * EFY / 2.0)
            hz = max(MIN_HALF, abs(e["yscale"]) * EFZ / 2.0)
            fs = box_faces(qx - hx, qy - hy, qz - hz,
                           qx + hx, qy + hy, qz + hz,
                           TRIG_TEX, TRIG_TEX, TRIG_TEX,
                           TRIG_TEX, TRIG_TEX, TRIG_TEX)
            lines += [
                "{",
                '"classname" "trigger_multiple"',
                '"target" "target_stopTimer"',
                write_brush(fs, f"trigger {nm}"),
                "}",
            ]
            lines += [
                "{",
                '"classname" "target_stopTimer"',
                f'"origin" "{qx:g} {qy:g} {qz:g}"',
                '"targetname" "target_stopTimer"',
                "}",
            ]

        elif nm.startswith("trigger_split"):
            split_count += 1
            tname = f"target_checkpoint_{split_count}"
            hx = max(MIN_HALF, abs(e["xscale"]) * EFX / 2.0)
            hy = max(MIN_HALF, abs(e["zscale"]) * EFY / 2.0)
            hz = max(MIN_HALF, abs(e["yscale"]) * EFZ / 2.0)
            fs = box_faces(qx - hx, qy - hy, qz - hz,
                           qx + hx, qy + hy, qz + hz,
                           TRIG_TEX, TRIG_TEX, TRIG_TEX,
                           TRIG_TEX, TRIG_TEX, TRIG_TEX)
            lines += [
                "{",
                '"classname" "trigger_multiple"',
                f'"target" "{tname}"',
                write_brush(fs, f"trigger {nm}"),
                "}",
            ]
            lines += [
                "{",
                '"classname" "target_checkpoint"',
                f'"origin" "{qx:g} {qy:g} {qz:g}"',
                f'"targetname" "{tname}"',
                f'"count" "{split_count}"',
                "}",
            ]

        else:
            model = props.get("model", "").lower()

            prop_tex = None
            prop_shape = None
            if "invisible_cylinder" in model:
                prop_tex = "common/caulk"
                prop_shape = "cylinder"
            elif "invisible_block_diagonal" in model:
                prop_tex = "common/caulk"
                prop_shape = "diagonal"
            elif "invisible_opaque_box_corner" in model:
                prop_tex = opaque_tex
                prop_shape = "corner"
            elif "invisible_opaque_box" in model:
                prop_tex = opaque_tex
                prop_shape = "box"
            elif "invisible_box" in model:
                prop_tex = NODRAW_TEX
                prop_shape = "box"

            if prop_shape is None:
                continue

            # xscale/zscale are half-extents in block units; *2 to get full extent
            # yscale (height) already has *2 for the same reason
            fx = max(MIN_HALF, abs(e.get("xscale", 1.0)) * sx * 2)
            fy = max(MIN_HALF, abs(e.get("zscale", 1.0)) * sy * 2)
            fz = max(MIN_HALF, abs(e.get("yscale", 1.0)) * 2 * sz)

            if prop_shape == "box":
                hx, hy, hz = fx / 2, fy / 2, fz / 2
                fs = box_faces(qx - hx, qy - hy, qz - hz,
                               qx + hx, qy + hy, qz + hz,
                               prop_tex, prop_tex, prop_tex,
                               prop_tex, prop_tex, prop_tex)
                brushes.append(write_brush(fs, f"prop_box {nm}"))

            elif prop_shape == "diagonal":
                ang = math.radians(e.get("yrot", 0.0)) % (2 * math.pi)
                if ang < math.pi / 4 or ang >= 7 * math.pi / 4:
                    x0, x1 = qx, qx + fx
                    y0, y1 = qy - fy, qy
                    z0, z1 = qz, qz + fz
                    f_bot = face((x0, y0, z0), (x1, y0, z0), (x0, y1, z0), prop_tex)
                    f_top = face((x1, y1, z1), (x1, y0, z1), (x0, y0, z1), prop_tex)
                    f_w1  = face((x1, y0, z1), (x1, y0, z0), (x1, y1, z1), prop_tex)
                    f_w2  = face((x0, y0, z0), (x0, y0, z1), (x1, y0, z0), prop_tex)
                    f_dia = face((x1, y1, z1), (x0, y0, z1 + 1), (x0, y0, z1), prop_tex)
                elif ang < 3 * math.pi / 4:
                    x0, x1 = qx, qx + fx
                    y0, y1 = qy, qy + fy
                    z0, z1 = qz, qz + fz
                    f_bot = face((x0, y0, z0), (x1, y0, z0), (x0, y1, z0), prop_tex)
                    f_top = face((x1, y1, z1), (x1, y0, z1), (x0, y0, z1), prop_tex)
                    f_w1  = face((x1, y1, z1), (x1, y1, z0), (x1, y0, z1), prop_tex)
                    f_w2  = face((x1, y1, z1), (x0, y1, z1), (x1, y1, z0), prop_tex)
                    f_dia = face((x0, y1, z1), (x1, y0, z1 + 1), (x1, y0, z1), prop_tex)
                elif ang < 5 * math.pi / 4:
                    x0, x1 = qx - fx, qx
                    y0, y1 = qy, qy + fy
                    z0, z1 = qz, qz + fz
                    f_bot = face((x0, y0, z0), (x1, y0, z0), (x0, y1, z0), prop_tex)
                    f_top = face((x1, y1, z1), (x1, y0, z1), (x0, y0, z1), prop_tex)
                    f_w1  = face((x0, y0, z0), (x0, y1, z0), (x0, y0, z1), prop_tex)
                    f_w2  = face((x1, y1, z1), (x0, y1, z1), (x1, y1, z0), prop_tex)
                    f_dia = face((x0, y0, z1), (x1, y1, z1 + 1), (x1, y1, z1), prop_tex)
                else:
                    x0, x1 = qx - fx, qx
                    y0, y1 = qy - fy, qy
                    z0, z1 = qz, qz + fz
                    f_bot = face((x0, y0, z0), (x1, y0, z0), (x0, y1, z0), prop_tex)
                    f_top = face((x1, y1, z1), (x1, y0, z1), (x0, y0, z1), prop_tex)
                    f_w1  = face((x0, y0, z0), (x0, y1, z0), (x0, y0, z1), prop_tex)
                    f_w2  = face((x0, y0, z0), (x0, y0, z1), (x1, y0, z0), prop_tex)
                    f_dia = face((x0, y1, z1), (x1, y0, z1), (x1, y0, z1 + 1), prop_tex)

                brushes.append(write_brush(
                    [f_bot, f_top, f_w1, f_w2, f_dia],
                    f"diag_prop {nm}"))

            elif prop_shape == "corner":
                ang = math.radians(e.get("yrot", 0.0)) % (2 * math.pi)
                hx, hy, hz = fx / 2, fy / 2, fz / 2
                x0, x1 = qx - hx, qx + hx
                y0, y1 = qy - hy, qy + hy
                z0, z1 = qz - hz, qz + hz

                f_bot = face((x0, y0, z0), (x1, y0, z0), (x0, y1, z0), prop_tex)
                f_top = face((x1, y1, z1), (x1, y0, z1), (x0, y0, z1), prop_tex)

                if ang < math.pi / 4 or ang >= 7 * math.pi / 4:
                    f_w1  = face((x1, y1, z1), (x1, y1, z0), (x1, y0, z1), prop_tex)
                    f_w2  = face((x0, y0, z0), (x0, y0, z1), (x1, y0, z0), prop_tex)
                    f_dia = face((x1, y1, z1), (x0, y0, z1 + 1), (x0, y0, z1), prop_tex)
                elif ang < 3 * math.pi / 4:
                    f_w1  = face((x1, y1, z1), (x1, y1, z0), (x1, y0, z1), prop_tex)
                    f_w2  = face((x1, y1, z1), (x0, y1, z1), (x1, y1, z0), prop_tex)
                    f_dia = face((x0, y1, z1), (x1, y0, z1 + 1), (x1, y0, z1), prop_tex)
                elif ang < 5 * math.pi / 4:
                    f_w1  = face((x0, y0, z0), (x0, y1, z0), (x0, y0, z1), prop_tex)
                    f_w2  = face((x1, y1, z1), (x0, y1, z1), (x1, y1, z0), prop_tex)
                    f_dia = face((x0, y0, z1), (x1, y1, z1 + 1), (x1, y1, z1), prop_tex)
                else:
                    f_w1  = face((x0, y0, z0), (x0, y1, z0), (x0, y0, z1), prop_tex)
                    f_w2  = face((x0, y0, z0), (x0, y0, z1), (x1, y0, z0), prop_tex)
                    f_dia = face((x0, y1, z1), (x1, y0, z1), (x1, y0, z1 + 1), prop_tex)

                brushes.append(write_brush(
                    [f_bot, f_top, f_w1, f_w2, f_dia],
                    f"corner_prop {nm}"))

            elif prop_shape == "cylinder":
                # yrot is in degrees (same as diagonal/corner); convert to radians
                ang = math.radians(e.get("yrot", 0.0))
                outer_r = max(MIN_HALF, abs(e.get("xscale", 1.0)) * sx * 4)
                wall_t  = sx / 2.0
                inner_r = outer_r - wall_t
                z_bot = qz - fz / 2
                z_top = qz + fz / 2
                arc_step = float(sx)
                cyl_strs = cylinder_brushes(
                    qx, qy, z_bot, z_top,
                    inner_r, outer_r,
                    ang, ang + math.pi / 2,
                    arc_step, prop_tex)
                brushes.extend(cyl_strs)

    return brushes, lines


# ══════════════════════════════════════════════════════════════════════════════
#  MAP STRING BUILDER
# ══════════════════════════════════════════════════════════════════════════════

def rbe_to_map_string(merged_with_mat, mat_tex, sx, sy, sz,
                      corner_brushes_list=None,
                      prop_brushes=None, entity_lines=None):
    """Convert greedy-merged DBT boxes to a complete Quake .map string.

    Parameters:
        merged_with_mat: list of ``(x1, y1, z1, x2, y2, z2, mat_idx)``
            in DBT grid coordinates.
        mat_tex: dict mapping ``mat_idx`` -> texture name string.
        corner_brushes_list: pre-built brush strings for corner blocks.
        prop_brushes: brush strings from prop entities (worldspawn geometry).
        entity_lines: entity definition strings (outside worldspawn).
    """
    lines = [
        "// Game: Quake 3",
        "// Format: Quake3 (Valve)",
        "// Imported by Turnt-o-mapper",
        "{",
        '"classname" "worldspawn"',
        '"mapversion" "220"',
    ]
    for bi, (x1, y1, z1, x2, y2, z2, mat_idx) in enumerate(merged_with_mat):
        qx1, qx2 = x1 * sx, x2 * sx
        qy1, qy2 = z1 * sy, z2 * sy
        qz1, qz2 = y1 * sz, y2 * sz
        tex = mat_tex.get(mat_idx, "turnt/turnt_concrete")
        fs = box_faces(qx1, qy1, qz1, qx2, qy2, qz2,
                       tex, tex, tex, tex, tex, tex)
        lines.append(write_brush(fs, f"dbt {bi}"))
    if corner_brushes_list:
        lines.extend(corner_brushes_list)
    if prop_brushes:
        lines.extend(prop_brushes)
    lines.append("}")
    if entity_lines:
        lines.extend(entity_lines)
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════════════
#  IMPORT ORCHESTRATOR
# ══════════════════════════════════════════════════════════════════════════════

def run_import(path, sx, sy, sz, log_fn=None):
    """Run the full RBE -> .map import pipeline.

    Parameters:
        path: filesystem path to the .rbe file.
        sx, sy, sz: Quake units per DBT block along X, Y (dbt Z), Z (dbt Y).
        log_fn: optional ``callable(message, level)`` for progress reporting.
            *level* is one of ``"info"``, ``"warn"``, ``"error"``, ``"plain"``.

    Returns ``(map_string, fake_rooms, warnings)`` where *fake_rooms* is a
    list of :class:`Room` objects representing the merged boxes (for preview),
    and *warnings* is an empty list (reserved for future use).
    """
    _TURNT_POOL = [k for k in ALL_TEXTURES if k.startswith("turnt/turnt_")]

    def _log(msg, level="plain"):
        if log_fn:
            log_fn(msg, level)

    # 0. Show parameters
    _log(f"Scale: 1 block → X={sx}qu  Y={sy}qu  Z(height)={sz}qu  |  "
         f"prop angles: degrees", "info")

    # 1. Parse
    _log(f"Parsing {path} \u2026", "info")
    t0 = time.perf_counter()
    blocks, materials, entities, ver = parse_rbe(path)
    dt = time.perf_counter() - t0
    _log(f"Parsed ver={ver}: {len(blocks):,} blocks, "
         f"{len(materials)} materials, {len(entities)} entities "
         f"in {dt:.2f}s", "info")

    # 2. Filter by type
    CLIP_TEX = {
        2: "common/caulk",
        4: "common/weapclip",
        5: "common/clip",
    }
    solid_blocks  = [b for b in blocks if b["type"] == 1]
    corner_blocks = [b for b in blocks if b["type"] == 3]
    clip_groups   = {t: [b for b in blocks if b["type"] == t] for t in (2, 4, 5)}
    clip_info = ", ".join(f"{len(v):,} type-{k}" for k, v in clip_groups.items() if v)
    _log(f"Filtered: {len(solid_blocks):,} solid, "
         f"{len(corner_blocks):,} corner"
         + (f", {clip_info}" if clip_info else ""))

    # 3. Material -> texture mapping
    mat_groups: Dict[int, list] = {}
    for b in solid_blocks:
        m = b["mats"]["top"]
        mat_groups.setdefault(m, []).append(b)

    mat_tex: Dict[int, str] = {}
    _log("Material \u2192 texture mapping:")
    for pool_i, m_idx in enumerate(sorted(mat_groups.keys())):
        tex = _TURNT_POOL[pool_i % len(_TURNT_POOL)]
        mat_tex[m_idx] = tex
        mat_name = materials[m_idx] if m_idx < len(materials) else "?"
        _log(f"  [{m_idx}] {mat_name!r} \u2192 {tex!r}")

    # 4. Per-material greedy merge
    _log(f"Merging {len(mat_groups)} material groups \u2026")
    t0 = time.perf_counter()
    merged_with_mat = []
    for m_idx, group in mat_groups.items():
        for box in greedy_merge(group):
            merged_with_mat.append((*box, m_idx))
    dt = time.perf_counter() - t0
    _log(f"Merged {len(solid_blocks):,} solid \u2192 "
         f"{len(merged_with_mat):,} brushes in {dt:.2f}s", "info")

    # 4a. Clip blocks
    for btype, btype_blocks in clip_groups.items():
        if not btype_blocks:
            continue
        tex = CLIP_TEX[btype]
        t0 = time.perf_counter()
        clip_merged = greedy_merge(btype_blocks)
        dt = time.perf_counter() - t0
        synth_idx = -btype
        mat_tex[synth_idx] = tex
        for box in clip_merged:
            merged_with_mat.append((*box, synth_idx))
        _log(f"Type {btype}: {len(btype_blocks):,} \u2192 "
             f"{len(clip_merged):,} brushes ({tex}) in {dt:.2f}s", "info")

    # 4b. Corner blocks
    corner_tex = (_TURNT_POOL[len(mat_groups) % len(_TURNT_POOL)]
                  if _TURNT_POOL else "turnt/turnt_concrete")
    t0 = time.perf_counter()
    corner_runs = merge_corners(corner_blocks)
    corner_brush_strs = [
        corner_brush(bx, bz, by_lo, by_hi, orient, sx, sy, sz, corner_tex)
        for (bx, bz, by_lo, by_hi, orient) in corner_runs
    ]
    dt = time.perf_counter() - t0
    _log(f"Corner: {len(corner_blocks):,} slabs \u2192 "
         f"{len(corner_brush_strs):,} brushes in {dt:.2f}s", "info")

    # 5. Entity conversion
    opaque_prop_tex = (_TURNT_POOL[(len(mat_groups) + 1) % len(_TURNT_POOL)]
                       if _TURNT_POOL else "turnt/turnt_concrete")
    prop_brushes, entity_lines = rbe_entities_to_map(
        entities, sx, sy, sz, opaque_tex=opaque_prop_tex)
    n_spawns    = sum(1 for e in entities if e["name"] == "spawn")
    n_start_t   = sum(1 for e in entities if e["name"].startswith("trigger_start"))
    n_end_t     = sum(1 for e in entities if e["name"].startswith("trigger_end"))
    n_checkpoints = sum(1 for e in entities if e["name"].startswith("trigger_split"))

    def _model(ent):
        for p in ent.get("properties", []):
            if p["name"] == "model":
                return p["val"].lower()
        return ""
    n_props = sum(1 for e in entities if "invisible" in _model(e))
    spawn_ok = "✓" if n_spawns else "✗ NOT FOUND"
    _log(f"Entities: spawn {spawn_ok}  |  "
         f"start: {n_start_t}, end: {n_end_t}, checkpoints: {n_checkpoints}, props: {n_props}")

    # 6. Generate .map string
    _log("Generating .map \u2026")
    t0 = time.perf_counter()
    ms = rbe_to_map_string(
        merged_with_mat, mat_tex, sx, sy, sz,
        corner_brushes_list=corner_brush_strs,
        prop_brushes=prop_brushes,
        entity_lines=entity_lines)
    dt = time.perf_counter() - t0
    kb = len(ms.encode()) / 1024
    total_brushes = len(merged_with_mat) + len(corner_brush_strs) + len(prop_brushes)
    _log(f"Map: {total_brushes:,} brushes "
         f"({len(merged_with_mat):,} solid + {len(corner_brush_strs):,} corner), "
         f"{kb:.1f} KB in {dt:.2f}s", "info")

    # 7. Build fake Room objects for preview
    fake_rooms = [
        Room(
            x=x1 * sx, y=z1 * sy, z=y1 * sz,
            w=max(1, (x2 - x1) * sx),
            d=max(1, (z2 - z1) * sy),
            h=max(1, (y2 - y1) * sz),
            idx=i,
        )
        for i, (x1, y1, z1, x2, y2, z2, _mi)
        in enumerate(merged_with_mat)
    ]

    _log(
        f"Import complete — {len(blocks):,} DBT blocks → {total_brushes:,} Q3 brushes "
        f"| spawn {'✓' if n_spawns else '✗'} "
        f"| triggers: start={n_start_t} end={n_end_t} checkpoints={n_checkpoints} "
        f"| {kb:.1f} KB",
        "info"
    )

    return ms, fake_rooms, []
