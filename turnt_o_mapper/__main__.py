import sys

from PyQt6.QtWidgets import QApplication

from turnt_o_mapper.app import App, DARK_QSS


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(DARK_QSS)
    window = App()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
