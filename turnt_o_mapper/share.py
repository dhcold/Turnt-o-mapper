"""Shareable generation config hash: encode / decode.

Format: ``tom1_`` + base64url(zlib(JSON-with-short-keys))

The hash is ~60-80 characters — compact enough to paste in chat.
"""

from __future__ import annotations

import base64
import json
import math
import zlib

VERSION_PREFIX = "tom1_"
MAX_DECOMPRESS = 4096  # safety cap (bytes)

# ── Short key mapping ────────────────────────────────────────────────────────
_LONG_TO_SHORT: dict[str, str] = {
    "n_rooms":            "r",
    "min_w":              "a",
    "max_w":              "b",
    "min_d":              "c",
    "max_d":              "d",
    "min_h":              "e",
    "max_h":              "f",
    "use_physics":        "p",
    "u_base":             "g",
    "u_gain":             "h",
    "t_air":              "i",
    "strafe_f":           "j",
    "rooms_per_turn":     "k",
    "layout_style":       "l",
    "seed":               "s",
    "height_var":         "v",
    "checkpoints":        "x",
    "corridor_width_frac":"w",
}

_SHORT_TO_LONG: dict[str, str] = {v: k for k, v in _LONG_TO_SHORT.items()}

# ── Layout name ↔ index ─────────────────────────────────────────────────────
_LAYOUT_NAMES = ["Linear", "Zigzag", "Snake", "Random", "Spiral", "Multilevel"]
_LAYOUT_INDEX: dict[str, int] = {n: i for i, n in enumerate(_LAYOUT_NAMES)}

# ── Validation ranges  (short_key → (type, min, max)) ───────────────────────
_VALIDATORS: dict[str, tuple] = {
    "r": (int,   2,    200),
    "a": (int,   64,   8192),
    "b": (int,   64,   8192),
    "c": (int,   64,   8192),
    "d": (int,   64,   8192),
    "e": (int,   64,   8192),
    "f": (int,   64,   8192),
    "p": (bool,  None, None),
    "g": (float, 50,   3000),
    "h": (float, 0,    500),
    "i": (float, 0.05, 2.0),
    "j": (float, 0.01, 1.0),
    "k": (int,   1,    20),
    "l": (int,   0,    len(_LAYOUT_NAMES) - 1),
    "s": (int,   0,    9_999_999),
    "v": (bool,  None, None),
    "x": (bool,  None, None),
    "w": (float, 0.1,  1.0),
}


# ── Public API ───────────────────────────────────────────────────────────────

def encode_cfg(cfg: dict) -> str:
    """Encode a generation cfg dict into a ``tom1_…`` hash string."""
    compact: dict = {}
    for long_key, short_key in _LONG_TO_SHORT.items():
        if long_key not in cfg:
            continue
        val = cfg[long_key]
        # Convert layout name → index
        if long_key == "layout_style":
            val = _LAYOUT_INDEX.get(val, 0)
        # Round floats to 4 decimal places to keep JSON short
        if isinstance(val, float):
            val = round(val, 4)
        compact[short_key] = val

    raw = json.dumps(compact, separators=(",", ":")).encode("utf-8")
    compressed = zlib.compress(raw, 9)
    b64 = base64.urlsafe_b64encode(compressed).rstrip(b"=").decode("ascii")
    return VERSION_PREFIX + b64


def decode_hash(hash_str: str) -> dict:
    """Decode a ``tom1_…`` hash string back into a cfg dict.

    Raises ``ValueError`` on any parse / validation error.
    Unknown keys are silently dropped.
    """
    hash_str = hash_str.strip()
    if not hash_str.startswith(VERSION_PREFIX):
        raise ValueError(f"Expected prefix '{VERSION_PREFIX}'")

    b64 = hash_str[len(VERSION_PREFIX):]
    # Restore base64 padding
    b64 += "=" * (-len(b64) % 4)

    try:
        compressed = base64.urlsafe_b64decode(b64)
    except Exception as exc:
        raise ValueError(f"Base64 decode failed: {exc}") from exc

    # Decompress with size cap
    try:
        dec = zlib.decompressobj(zlib.MAX_WBITS)
        raw = dec.decompress(compressed, MAX_DECOMPRESS)
        if dec.unconsumed_tail:
            raise ValueError("Decompressed payload too large")
    except zlib.error as exc:
        raise ValueError(f"Zlib decompress failed: {exc}") from exc

    try:
        compact = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON parse failed: {exc}") from exc

    if not isinstance(compact, dict):
        raise ValueError("Payload is not a JSON object")

    # Map short keys → long keys, validate
    result: dict = {}
    for short_key, val in compact.items():
        if short_key not in _SHORT_TO_LONG:
            continue  # unknown key — skip
        long_key = _SHORT_TO_LONG[short_key]
        vtype, vmin, vmax = _VALIDATORS.get(short_key, (None, None, None))

        if vtype is bool:
            val = bool(val)
        elif vtype is int:
            try:
                val = int(val)
            except (TypeError, ValueError):
                continue
            if vmin is not None:
                val = max(vmin, min(val, vmax))
        elif vtype is float:
            try:
                val = float(val)
            except (TypeError, ValueError):
                continue
            if vmin is not None:
                val = max(vmin, min(val, vmax))

        # Convert layout index → name
        if long_key == "layout_style":
            if 0 <= val < len(_LAYOUT_NAMES):
                val = _LAYOUT_NAMES[val]
            else:
                val = _LAYOUT_NAMES[0]

        result[long_key] = val

    return result
