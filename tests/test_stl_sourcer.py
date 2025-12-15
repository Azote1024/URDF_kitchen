import pytest
from urdf_kitchen_StlSourcer import MainWindow
from utils.urdf_kitchen_config import StlSourcerConfig as Config

def test_mainwindow_init(qapp):
    """
    MainWindowの初期化テスト
    
    目的:
    StlSourcerのメインウィンドウが正しく起動し、初期状態が適切であることを確認します。
    - ウィンドウタイトルが設定通りであること
    - ポイント数などの内部変数が設定値と一致していること
    - UI要素（ラベル、ボタン）が正しい初期テキストを持っていること
    """
    window = MainWindow()
    assert window.windowTitle() == Config.WINDOW_TITLE
    assert window.num_points == Config.NUM_POINTS
    assert len(window.point_coords) == Config.NUM_POINTS
    assert len(window.point_actors) == Config.NUM_POINTS
    
    # UI要素の確認
    assert window.file_name_label.text() == "File: No file loaded"
    assert window.load_button.text() == "Load STL File"
    assert window.export_stl_button.text() == "Save as reoriented STL"
