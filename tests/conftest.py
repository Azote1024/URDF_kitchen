import os
import sys
import pytest
from Qt import QtWidgets

# プロジェクトルートをsys.pathに追加して、メインスクリプトをインポート可能にする
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

@pytest.fixture(scope="session")
def qapp():
    """QApplication instance for the test session."""
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication(sys.argv)
    yield app

@pytest.fixture
def sample_data_dir():
    """サンプルデータのディレクトリパスを提供するフィクスチャ"""
    return os.path.join(project_root, 'roborecipe2_description', 'meshes')

@pytest.fixture
def sample_urdf_path():
    """サンプルURDFファイルのパスを提供するフィクスチャ"""
    return os.path.join(project_root, 'roborecipe2_description', 'urdf', 'roborecipe2.urdf')

@pytest.fixture
def sample_project_xml_path():
    """サンプルプロジェクトXMLファイルのパスを提供するフィクスチャ"""
    return os.path.join(project_root, 'roborecipe2_description', 'urdf_pj_sample.xml')
