from PySide6.QtGui import QColor, QPalette
from utils.urdf_kitchen_config import PartsEditorConfig as Config

def apply_dark_theme(window):
    """シックなダークテーマを適用"""
    # パレットの設定
    palette = window.palette()
    # メインウィンドウ背景：柔らかいダークグレー
    palette.setColor(QPalette.Window, QColor(*Config.PALETTE_WINDOW))
    # テキスト：ダークグレー
    palette.setColor(QPalette.WindowText, QColor(*Config.PALETTE_WINDOW_TEXT))
    # 入力フィールド背景：オフホワイト
    palette.setColor(QPalette.Base, QColor(*Config.PALETTE_BASE))
    palette.setColor(QPalette.AlternateBase, QColor(*Config.PALETTE_ALTERNATE_BASE))
    # ツールチップ
    palette.setColor(QPalette.ToolTipBase, QColor(*Config.PALETTE_TOOLTIP_BASE))
    palette.setColor(QPalette.ToolTipText, QColor(*Config.PALETTE_TOOLTIP_TEXT))
    # 通常のテキスト：ダークグレー
    palette.setColor(QPalette.Text, QColor(*Config.PALETTE_TEXT))
    # ボタン
    palette.setColor(QPalette.Button, QColor(*Config.PALETTE_BUTTON))
    palette.setColor(QPalette.ButtonText, QColor(*Config.PALETTE_BUTTON_TEXT))
    # 選択時のハイライト
    palette.setColor(QPalette.Highlight, QColor(*Config.PALETTE_HIGHLIGHT))
    palette.setColor(QPalette.HighlightedText, QColor(*Config.PALETTE_HIGHLIGHTED_TEXT))
    window.setPalette(palette)

    # VTKビューポートの背景色をシックなグレーに設定
    if hasattr(window, 'renderer'):
        window.renderer.SetBackground(*Config.VTK_BACKGROUND_COLOR)

    # 追加のスタイル設定
    window.setStyleSheet(f"""
        QMainWindow {{
            background-color: {Config.STYLE_MAIN_BG};
        }}
        QPushButton {{
            background-color: {Config.STYLE_BUTTON_BG};
            border: 1px solid {Config.STYLE_BUTTON_BORDER};
            border-radius: 2px;
            padding: 2px 2px;
            color: {Config.STYLE_BUTTON_TEXT};
            min-width: 80px;
        }}
        QPushButton:hover {{
            background-color: {Config.STYLE_BUTTON_HOVER};
            border: 1px solid #AAAAAA;
        }}
        QPushButton:pressed {{
            background-color: {Config.STYLE_BUTTON_PRESSED};
            padding-top: 4px;
            padding-bottom: 4px;
        }}
        QLineEdit {{
            background-color: {Config.STYLE_INPUT_BG};
            border: 1px solid {Config.STYLE_INPUT_BORDER};
            color: {Config.STYLE_INPUT_TEXT};
            padding: 1px;  # パディングを小さく
            border-radius: 2px;
            min-height: 12px;  # 最小の高さを設定
            max-height: 12px;  # 最大の高さを設定
        }}
        QLineEdit:focus {{
            border: 1px solid #999999;
            background-color: #FFFFFF;
        }}
        QLabel {{
            color: {Config.STYLE_INPUT_TEXT};
        }}
        QCheckBox {{
            color: {Config.STYLE_INPUT_TEXT};
            spacing: 10px;
        }}
        QCheckBox::indicator {{
            width: 12px;
            height: 12px;
            background-color: {Config.STYLE_INPUT_BG};
            border: 1px solid {Config.STYLE_INPUT_BORDER};
            border-radius: 2px;
        }}
        QCheckBox::indicator:checked {{
            background-color: #808487;
            border: 1px solid #666666;
        }}
        QRadioButton {{
            color: {Config.STYLE_INPUT_TEXT};
            spacing: 2px;
        }}
        QRadioButton::indicator {{
            width: 12px;
            height: 12px;
            background-color: {Config.STYLE_INPUT_BG};
            border: 1px solid {Config.STYLE_INPUT_BORDER};
            border-radius: 2px;
        }}
        QRadioButton::indicator:checked {{
            background-color: #808487;
            border: 1px solid #666666;
        }}
    """)

    # ファイルダイアログのスタイル
    window.setStyleSheet(window.styleSheet() + f"""
        QFileDialog {{
            background-color: {Config.STYLE_MAIN_BG};
        }}
        QFileDialog QLabel {{
            color: {Config.STYLE_INPUT_TEXT};
        }}
        QFileDialog QLineEdit {{
            background-color: {Config.STYLE_INPUT_BG};
            color: {Config.STYLE_BUTTON_TEXT};
            border: 1px solid {Config.STYLE_INPUT_BORDER};
        }}
        QFileDialog QPushButton {{
            background-color: {Config.STYLE_BUTTON_BG};
            color: {Config.STYLE_BUTTON_TEXT};
            border: 1px solid {Config.STYLE_BUTTON_BORDER};
        }}
        QFileDialog QTreeView {{
            background-color: {Config.STYLE_INPUT_BG};
            color: {Config.STYLE_BUTTON_TEXT};
        }}
        QFileDialog QComboBox {{
            background-color: {Config.STYLE_INPUT_BG};
            color: {Config.STYLE_BUTTON_TEXT};
            border: 1px solid {Config.STYLE_INPUT_BORDER};
        }}
    """)
