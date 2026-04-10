"""
Application configuration persistence.

Reads and writes ``turnt_config.json`` located next to the main entry point.
The config stores all UI settings (room sizes, physics params, paths, etc.)
so they survive between sessions.
"""

import json
import os

_CFG_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "turnt_config.json",
)


def load_app_cfg() -> dict:
    """Load the application config from *turnt_config.json*.

    Returns an empty dict if the file does not exist or is malformed.
    """
    try:
        with open(_CFG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_app_cfg(data: dict):
    """Merge *data* into the existing config file and persist to disk.

    Keys in *data* overwrite existing keys; keys not present in *data*
    are preserved from the previous save.  Silently ignores write errors.
    """
    try:
        existing = load_app_cfg()
        existing.update(data)
        with open(_CFG_FILE, "w", encoding="utf-8") as f:
            json.dump(existing, f, indent=2)
    except Exception:
        pass
