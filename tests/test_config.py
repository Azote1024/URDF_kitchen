import pytest
from utils.urdf_kitchen_config import AssemblerConfig, PartsEditorConfig

def test_assembler_config_values():
    """
    AssemblerConfigの定数テスト
    
    目的:
    Assemblerで使用される設定値が適切な型と範囲であることを確認します。
    - ノードの色設定がRGB形式（3要素のリスト/タプル）であること
    - 最大出力ポート数が正の整数であること
    """
    assert isinstance(AssemblerConfig.DEFAULT_NODE_COLOR, (list, tuple))
    assert len(AssemblerConfig.DEFAULT_NODE_COLOR) == 3
    assert all(0 <= c <= 255 for c in AssemblerConfig.DEFAULT_NODE_COLOR)
    
    assert isinstance(AssemblerConfig.MAX_OUTPUT_PORTS, int)
    assert AssemblerConfig.MAX_OUTPUT_PORTS > 0

def test_parts_editor_config_values():
    """
    PartsEditorConfigの定数テスト
    
    目的:
    PartsEditorで使用される設定値が適切であることを確認します。
    - ウィンドウタイトルが空でない文字列であること
    """
    assert isinstance(PartsEditorConfig.WINDOW_TITLE, str)
    assert len(PartsEditorConfig.WINDOW_TITLE) > 0
