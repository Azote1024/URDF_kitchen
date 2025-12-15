import pytest
from urdf_kitchen_PartsEditor import MainWindow
from utils.urdf_kitchen_config import PartsEditorConfig as Config

def test_mainwindow_init(qapp):
    """
    MainWindowの初期化テスト
    
    目的:
    PartsEditorのメインウィンドウが正しく起動し、初期状態が適切であることを確認します。
    - ウィンドウタイトルが設定通りであること
    - 質量や体積などの物理パラメータ入力欄が0で初期化されていること
    - 主要な操作ボタン（Load, Export等）が存在し、正しいラベルが表示されていること
    """
    window = MainWindow()
    assert window.windowTitle() == Config.WINDOW_TITLE
    
    # デフォルト値の確認
    # mass_value, volume_value 属性は存在せず、UI上のテキストとして保持されている
    assert float(window.mass_input.text()) == 0.0
    assert float(window.volume_input.text()) == 0.0
    assert window.current_rotation == 0
    
    # UI要素の確認
    assert window.file_name_label.text() == "File:"
    assert window.load_button.text() == "Load STL"
    assert window.export_urdf_button.text() == "Export XML"
