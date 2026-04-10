"""
Auto-update helper: checks GitHub Releases for a newer version and
downloads + restarts the binary if the user confirms.
"""

import json
import os
import subprocess
import sys
import tempfile
import threading
import urllib.request
from typing import Callable, Optional

from .__version__ import __version__

REPO    = "dhcold/Turnt-o-mapper"
API_URL = f"https://api.github.com/repos/{REPO}/releases/latest"


def _parse_version(tag: str) -> tuple:
    """Convert a version string like '1.2.3' or 'v1.2.3' to a comparable tuple."""
    try:
        return tuple(int(x) for x in tag.lstrip("v").split("."))
    except ValueError:
        return (0,)


def _current_version() -> tuple:
    return _parse_version(__version__)


def check_for_update(on_update_available: Callable[[str, str], None]) -> None:
    """Start a background thread that checks GitHub Releases API.

    If a newer release is found, calls ``on_update_available(version, url)``
    on the calling thread (via the caller's event loop — use QTimer.singleShot).
    Silently ignores network errors so the app always starts cleanly.
    """
    def _worker():
        try:
            req = urllib.request.Request(
                API_URL,
                headers={"User-Agent": f"Turnt-o-mapper/{__version__}"},
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.load(resp)

            tag = data.get("tag_name", "")
            if not tag:
                return
            if _parse_version(tag) <= _current_version():
                return

            # Find the right asset for this platform
            plat = {
                "win32":  "windows",
                "darwin": "macos",
                "linux":  "linux",
            }.get(sys.platform, "")
            assets = data.get("assets", [])
            asset = next(
                (a for a in assets if plat and plat in a["name"].lower()),
                None,
            )
            url = asset["browser_download_url"] if asset else data.get("html_url", "")
            on_update_available(tag.lstrip("v"), url)
        except Exception:
            pass  # no network, rate-limited, etc. — stay silent

    threading.Thread(target=_worker, daemon=True).start()


def download_and_restart(
    url: str,
    version: str,
    status_cb: Optional[Callable[[str], None]] = None,
) -> None:
    """Download the new binary and relaunch the application.

    Runs in a background thread so the UI stays responsive during the download.
    On completion the new process is launched and the current process exits.
    """
    suffix = ".exe" if sys.platform == "win32" else ""
    tmp = tempfile.mktemp(suffix=suffix, prefix="turnt-update-")

    def _dl():
        try:
            if status_cb:
                status_cb(f"Downloading v{version}…")
            urllib.request.urlretrieve(url, tmp)
            os.chmod(tmp, 0o755)
            if status_cb:
                status_cb("Restarting…")
            subprocess.Popen([tmp])
            sys.exit(0)
        except Exception as ex:
            if status_cb:
                status_cb(f"Update failed: {ex}")

    threading.Thread(target=_dl, daemon=True).start()
