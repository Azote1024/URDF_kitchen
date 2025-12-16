
import sys
import signal
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer

from parts_editor.main_window import PartsEditorMainWindow
from utils.urdf_kitchen_logger import setup_logger
from utils.ui_helpers import apply_dark_theme

logger = setup_logger("PartsEditor")

def signal_handler(sig, frame):
    logger.info("Ctrl+C detected, closing application...")
    QApplication.instance().quit()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Apply theme
    apply_dark_theme(app)

    # Ctrl+C handler
    signal.signal(signal.SIGINT, signal_handler)

    window = PartsEditorMainWindow()
    window.show()

    # Timer for signal handling
    timer = QTimer()
    timer.start(500)
    timer.timeout.connect(lambda: None)

    try:
        sys.exit(app.exec())
    except SystemExit:
        print("Exiting application...")
