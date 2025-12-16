
import sys
import signal
from PySide6 import QtWidgets, QtGui
from PySide6.QtGui import QPalette, QColor

from assembler.main_window import AssemblerWindow
from utils.urdf_kitchen_config import AssemblerConfig as Config

def apply_dark_theme(app):
    dark_palette = QPalette()
    dark_palette.setColor(QPalette.Window, QColor(*Config.PALETTE_WINDOW))
    dark_palette.setColor(QPalette.WindowText, QColor(*Config.PALETTE_WINDOW_TEXT))
    dark_palette.setColor(QPalette.Base, QColor(*Config.PALETTE_BASE))
    dark_palette.setColor(QPalette.AlternateBase, QColor(*Config.PALETTE_ALTERNATE_BASE))
    dark_palette.setColor(QPalette.ToolTipBase, QColor(*Config.PALETTE_TOOLTIP_BASE))
    dark_palette.setColor(QPalette.ToolTipText, QColor(*Config.PALETTE_TOOLTIP_TEXT))
    dark_palette.setColor(QPalette.Text, QColor(*Config.PALETTE_TEXT))
    dark_palette.setColor(QPalette.Button, QColor(*Config.PALETTE_BUTTON))
    dark_palette.setColor(QPalette.ButtonText, QColor(*Config.PALETTE_BUTTON_TEXT))
    dark_palette.setColor(QPalette.BrightText, QColor(*Config.PALETTE_BRIGHT_TEXT))
    dark_palette.setColor(QPalette.Highlight, QColor(*Config.PALETTE_HIGHLIGHT))
    dark_palette.setColor(QPalette.HighlightedText, QColor(*Config.PALETTE_HIGHLIGHTED_TEXT))
    app.setPalette(dark_palette)

def signal_handler(signum, frame):
    print("\nCtrl+C pressed. Closing all windows and exiting...")
    QtWidgets.QApplication.quit()

if __name__ == '__main__':
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    app = QtWidgets.QApplication(sys.argv)
    apply_dark_theme(app)

    window = AssemblerWindow()
    app.aboutToQuit.connect(window.graph.cleanup)
    window.show()

    sys.exit(app.exec())
