
import sys
import signal
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer

from stl_sourcer.main_window import MainWindow
from utils.urdf_kitchen_logger import setup_logger

logger = setup_logger("StlSourcer")

def signal_handler(sig, frame):
    logger.info("Ctrl+C detected, closing application...")
    QApplication.instance().quit()

if __name__ == "__main__":
    app = QApplication(sys.argv)

    # Ctrl+Cのシグナルハンドラを設定
    signal.signal(signal.SIGINT, signal_handler)

    window = MainWindow()
    window.show()

    # タイマーを設定してシグナルを処理できるようにする
    timer = QTimer()
    timer.start(500)  # 500ミリ秒ごとにイベントループを中断
    timer.timeout.connect(lambda: None)  # ダミー関数を接続

    try:
        sys.exit(app.exec())
    except SystemExit:
        print("Exiting application...")
