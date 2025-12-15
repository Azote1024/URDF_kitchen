"""
URDF Kitchen 設定ファイル
各ツールの定数、色設定、初期パラメータを管理します。
"""

class PartsEditorConfig:
    """
    urdf_kitchen_PartsEditor.py 用の設定クラス
    """
    # --- ウィンドウ設定 ---
    WINDOW_TITLE = "URDF Kitchen - PartsEditor v0.0.1 -"
    WINDOW_GEOMETRY = (0, 0, 1200, 600)  # (x, y, width, height)
    NUM_POINTS = 8  # 接続ポイントの数
    
    # --- カメラ初期設定 ---
    INITIAL_CAMERA_POSITION = [10, 0, 0]
    INITIAL_CAMERA_FOCAL_POINT = [0, 0, 0]
    INITIAL_CAMERA_VIEW_UP = [0, 0, 1]
    
    # --- VTK設定 ---
    VTK_BACKGROUND_COLOR = (0.05, 0.05, 0.07)  # 背景色 (R, G, B) 0.0-1.0

    # --- パレットカラー設定 (R, G, B) 0-255 ---
    PALETTE_WINDOW = (70, 80, 80)           # ウィンドウ背景
    PALETTE_WINDOW_TEXT = (240, 240, 237)   # ウィンドウテキスト
    PALETTE_BASE = (240, 240, 237)          # 入力フィールド背景など
    PALETTE_ALTERNATE_BASE = (230, 230, 227) # 代替背景色
    PALETTE_TOOLTIP_BASE = (240, 240, 237)  # ツールチップ背景
    PALETTE_TOOLTIP_TEXT = (51, 51, 51)     # ツールチップテキスト
    PALETTE_TEXT = (51, 51, 51)             # 通常テキスト
    PALETTE_BUTTON = (240, 240, 237)        # ボタン背景
    PALETTE_BUTTON_TEXT = (51, 51, 51)      # ボタンテキスト
    PALETTE_HIGHLIGHT = (150, 150, 150)     # 選択ハイライト
    PALETTE_HIGHLIGHTED_TEXT = (240, 240, 237) # 選択テキスト

    # --- スタイルシート用カラーコード ---
    STYLE_MAIN_BG = "#404244"
    
    # ボタン
    STYLE_BUTTON_BG = "#F0F0ED"
    STYLE_BUTTON_BORDER = "#BBBBB7"
    STYLE_BUTTON_TEXT = "#333333"
    STYLE_BUTTON_HOVER = "#E6E6E3"
    STYLE_BUTTON_PRESSED = "#DDDDD9"
    
    # 入力フィールド
    STYLE_INPUT_BG = "#F0F0ED"
    STYLE_INPUT_BORDER = "#BBBBB7"
    STYLE_INPUT_TEXT = "#F0F0ED" 


class StlSourcerConfig:
    """
    urdf_kitchen_StlSourcer.py 用の設定クラス
    """
    # --- ウィンドウ設定 ---
    WINDOW_TITLE = "URDF kitchen - StlSourcer v0.0.1 -"
    WINDOW_GEOMETRY = (100, 100, 700, 700)
    NUM_POINTS = 1
    
    # --- カメラ初期設定 ---
    INITIAL_CAMERA_POSITION = [10, 0, 0]
    INITIAL_CAMERA_FOCAL_POINT = [0, 0, 0]
    INITIAL_CAMERA_VIEW_UP = [0, 0, 1]

    # --- スタイルシート用カラーコード ---
    STYLE_MAIN_BG = "#2b2b2b"
    STYLE_LABEL_COLOR = "#ffffff"
    
    # ボタン（グラデーション）
    STYLE_BUTTON_GRADIENT_START = "#5a5a5a"
    STYLE_BUTTON_GRADIENT_END = "#3a3a3a"
    STYLE_BUTTON_TEXT = "#ffffff"
    STYLE_BUTTON_BORDER = "#707070"
    
    # 入力フィールド
    STYLE_INPUT_BG = "#3a3a3a"
    STYLE_INPUT_TEXT = "#ffffff"
    STYLE_INPUT_BORDER = "#5a5a5a"
    
    # チェックボックス
    STYLE_CHECKBOX_TEXT = "#ffffff"
    STYLE_CHECKBOX_CHECKED = "#4a90e2"


class AssemblerConfig:
    """
    urdf_kitchen_Assembler.py 用の設定クラス
    """
    # --- パレットカラー設定 (R, G, B) 0-255 ---
    PALETTE_WINDOW = (53, 53, 53)
    PALETTE_WINDOW_TEXT = (255, 255, 255)
    PALETTE_BASE = (42, 42, 42)
    PALETTE_ALTERNATE_BASE = (66, 66, 66)
    PALETTE_TOOLTIP_BASE = (255, 255, 255)
    PALETTE_TOOLTIP_TEXT = (255, 255, 255)
    PALETTE_TEXT = (255, 255, 255)
    PALETTE_BUTTON = (53, 53, 53)
    PALETTE_BUTTON_TEXT = (255, 255, 255)
    PALETTE_BRIGHT_TEXT = (255, 0, 0)
    PALETTE_HIGHLIGHT = (42, 130, 218)
    PALETTE_HIGHLIGHTED_TEXT = (0, 0, 0)

    # --- ノード設定 ---
    DEFAULT_NODE_COLOR = [1.0, 1.0, 1.0]  # デフォルトのノード色 (RGB 0.0-1.0)
    MAX_OUTPUT_PORTS = 8  # 最大出力ポート数
