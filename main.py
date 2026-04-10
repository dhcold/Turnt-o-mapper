#!/usr/bin/env python3
"""Turnt-o-mapper -- launch entry point."""

import sys
from PyQt6.QtWidgets import QApplication
from turnt_o_mapper.app import App, DARK_QSS

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyleSheet(DARK_QSS)
    window = App()
    window.show()
    sys.exit(app.exec())
