
import sys
import signal
import traceback
from PySide6 import QtWidgets, QtCore, QtGui
from NodeGraphQt import NodeGraph

from .graph import CustomNodeGraph
from .vtk_viewer import STLViewerWidget
from .nodes import BaseLinkNode
from utils.urdf_kitchen_logger import setup_logger

logger = setup_logger("AssemblerWindow")

class AssemblerWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("URDF Kitchen - Assembler - v0.0.1")
        self.resize(1200, 600)

        # Central Widget
        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QtWidgets.QHBoxLayout(central_widget)

        # STL Viewer & Graph
        self.stl_viewer = STLViewerWidget(central_widget)
        self.graph = CustomNodeGraph(self.stl_viewer)
        self.graph.setup_custom_view()

        # Create Base Link
        try:
            self.graph.create_base_link()
        except Exception as e:
            logger.error(f"Failed to create base link: {e}")

        # Left Panel
        left_panel = QtWidgets.QWidget()
        left_panel.setFixedWidth(145)
        left_layout = QtWidgets.QVBoxLayout(left_panel)

        # Name Input
        name_label = QtWidgets.QLabel("Name:")
        left_layout.addWidget(name_label)
        self.name_input = QtWidgets.QLineEdit("robot_x")
        self.name_input.setFixedWidth(120)
        self.name_input.setStyleSheet("QLineEdit { padding-left: 3px; padding-top: 0px; padding-bottom: 0px; }")
        left_layout.addWidget(self.name_input)

        # Connect name input
        self.name_input.textChanged.connect(self.graph.update_robot_name)
        self.graph.name_input = self.name_input

        # Buttons
        self.buttons = {}
        button_configs = [
            ("--spacer1--", None),
            ("Import XMLs", self.graph.import_xmls_from_folder),
            ("--spacer2--", None),
            ("Add Node", self.add_node),
            ("Delete Node", self.delete_selected_node),
            ("Recalc Positions", self.graph.recalculate_all_positions),
            ("--spacer3--", None),
            ("Load Project", self.load_project),
            ("Save Project", self.graph.save_project),
            ("--spacer4--", None),
            ("Export URDF", self.graph.export_urdf),
            ("Export for Unity", self.graph.export_for_unity),
            ("--spacer5--", None),
            ("open urdf-loaders", self.open_urdf_loaders)
        ]

        for text, handler in button_configs:
            if text.startswith("--spacer"):
                spacer = QtWidgets.QWidget()
                spacer.setFixedHeight(1)
                left_layout.addWidget(spacer)
            else:
                btn = QtWidgets.QPushButton(text)
                btn.setFixedWidth(120)
                if handler:
                    btn.clicked.connect(handler)
                left_layout.addWidget(btn)
                self.buttons[text] = btn

        left_layout.addStretch()

        # Splitter
        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        splitter.addWidget(self.graph.widget)
        splitter.addWidget(self.stl_viewer)
        splitter.setSizes([800, 400])

        main_layout.addWidget(left_panel)
        main_layout.addWidget(splitter)

        self.center_window()

    def add_node(self):
        self.graph.create_node(
            'insilico.nodes.LinkNode',
            name=f'Node_{len(self.graph.all_nodes())}',
            pos=QtCore.QPointF(0, 0)
        )

    def delete_selected_node(self):
        selected_nodes = self.graph.selected_nodes()
        if selected_nodes:
            for node in selected_nodes:
                if isinstance(node, BaseLinkNode):
                    QtWidgets.QMessageBox.warning(
                        self, "Warning", "BaseLinkNode cannot be deleted.")
                    continue
                self.graph.remove_node(node)

    def load_project(self):
        self.graph.load_project()

    def open_urdf_loaders(self):
        QtGui.QDesktopServices.openUrl(
            QtCore.QUrl("https://gkjohnson.github.io/urdf-loaders/javascript/example/bundle/")
        )

    def center_window(self):
        frame_geo = self.frameGeometry()
        screen = self.screen().availableGeometry().center()
        frame_geo.moveCenter(screen)
        self.move(frame_geo.topLeft())

    def closeEvent(self, event):
        self.graph.cleanup()
        super().closeEvent(event)
