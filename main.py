#!/usr/bin/env python3
"""Turnt-o-mapper -- launch entry point."""

import argparse
import sys

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication
from turnt_o_mapper.app import App, DARK_QSS


def main():
    parser = argparse.ArgumentParser(
        description="Turnt-o-mapper: Quake3 .map generator for Turnt and Diabotical .rbe converter")
    parser.add_argument(
        "--hash", type=str, default=None,
        help="Apply a tom1_... config hash on startup")
    parser.add_argument(
        "--auto-generate", action="store_true",
        help="Automatically generate after applying --hash")
    args = parser.parse_args()

    app = QApplication(sys.argv)
    app.setStyleSheet(DARK_QSS)
    window = App()

    if args.hash:
        window._apply_hash(args.hash)
        if args.auto_generate:
            QTimer.singleShot(100, window._on_generate)

    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
