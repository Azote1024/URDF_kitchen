import pytest
from urdf_kitchen_Assembler import BaseLinkNode, LinkNode
from utils.urdf_kitchen_config import AssemblerConfig as Config

def test_base_link_node_init(qapp):
    """
    BaseLinkNodeの初期化テスト
    
    目的:
    ロボットのルートとなるBaseLinkNodeが正しく初期化されることを確認します。
    - ノード名、物理プロパティ、色がデフォルト値であること
    - 出力ポートが1つ存在すること（子ノード接続用）
    - 入力ポートが存在しないこと（ルートノードのため親を持たない）
    """
    node = BaseLinkNode()
    assert node.NODE_NAME == 'BaseLinkNode'
    assert node.volume_value == 0.0
    assert node.mass_value == 0.0
    assert node.node_color == Config.DEFAULT_NODE_COLOR
def test_link_node_init(qapp):
    """
    LinkNodeの初期化テスト
    
    目的:
    一般的なリンクノード（LinkNode）が正しく初期化されることを確認します。
    - 入力ポートが1つ存在すること（親ノード接続用）
    - 初期状態で出力ポートが1つ存在すること
    - 対応する接続ポイントデータ（points）が初期化されていること
    """
    node = LinkNode()
    assert node.NODE_NAME == 'LinkNode'
    
    # 入力ポートは追加できないはず
    assert node.add_input('in') is None

def test_link_node_init(qapp):
    """LinkNodeの初期化テスト"""
    node = LinkNode()
def test_link_node_add_output(qapp):
    """
    LinkNodeの出力ポート追加テスト
    
    目的:
    LinkNodeに出力ポートを追加した際の挙動を確認します。
    - ポート数が正しくインクリメントされること
    - 新しいポート名が連番で生成されること
    - ポートに対応するポイントデータ（座標情報）が追加されること
    """
    node = LinkNode()
    initial_count = node.output_count
    # デフォルトで入力ポートが1つあるはず
    assert node.get_input('in') is not None
    
    # 初期状態で出力ポートが1つ追加されているはず (_add_outputが呼ばれるため)
    assert node.output_count == 1
    assert node.get_output('out_1') is not None
    
    # ポイントデータも初期化されているはず
    assert len(node.points) == 1
    assert node.points[0]['name'] == 'point_1'
    assert node.points[0]['xyz'] == [0.0, 0.0, 0.0]

def test_link_node_max_outputs(qapp):
    """
    LinkNodeの最大出力ポート数テスト
    
    目的:
    出力ポートの追加が設定された上限値（Config.MAX_OUTPUT_PORTS）で制限されることを確認します。
    これにより、UI上の表示崩れやリソースの過剰消費を防ぎます。
    """
    node = LinkNode()
    
    # 最大数まで追加
    # ポート追加
    port_name = node._add_output()
    
    assert node.output_count == initial_count + 1
    assert port_name == f'out_{initial_count + 1}'
    assert node.get_output(port_name) is not None
    
    # ポイントデータも増えているはず
def test_load_project(qapp, sample_project_xml_path):
    """
    プロジェクト読み込みのテスト
    
    目的:
    保存されたプロジェクトファイル（XML）を正しく読み込めるかを確認します。
    - XMLパースエラーが発生しないこと
    - ロボット名などのメタデータが復元されること
    - ノードグラフ上にノードが生成されること
    """
    # モックのSTLViewerを作成
    mock_stl_viewer = MagicMock()pp):
    """LinkNodeの最大出力ポート数テスト"""
    node = LinkNode()
    
    # 最大数まで追加
    for _ in range(Config.MAX_OUTPUT_PORTS):
        node._add_output()
        
    current_count = node.output_count
    assert current_count <= Config.MAX_OUTPUT_PORTS
    
    # さらに追加しようとしても増えないはず
    result = node._add_output()
    assert node.output_count == current_count
    assert result is None

from unittest.mock import MagicMock
from urdf_kitchen_Assembler import CustomNodeGraph

def test_load_project(qapp, sample_project_xml_path):
    """プロジェクト読み込みのテスト"""
    # モックのSTLViewerを作成
    mock_stl_viewer = MagicMock()
    
    # CustomNodeGraphのインスタンス化
    graph = CustomNodeGraph(mock_stl_viewer)
    
    # プロジェクト読み込み
    try:
        graph.load_project(sample_project_xml_path)
    except Exception as e:
        pytest.fail(f"load_project raised exception: {e}")
    
    # ロボット名が読み込まれているか確認
    assert graph.robot_name is not None
    
    # ノードが生成されているか確認
    nodes = graph.all_nodes()
    assert len(nodes) > 0

