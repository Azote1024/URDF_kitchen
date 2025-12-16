
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QPushButton, QCheckBox, QLineEdit, QLabel, 
    QGridLayout, QTextEdit, QButtonGroup, QRadioButton, QWidget
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QTextOption
from vtkmodules.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor
from utils.urdf_kitchen_config import PartsEditorConfig as Config

class PartsEditorUI:
    def __init__(self, main_window):
        self.mw = main_window

    def setup_ui(self):
        # Central Widget & Main Layout
        central_widget = QWidget(self.mw)
        self.mw.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # File Name Label
        self.mw.file_name_label = QLabel("File:")
        self.mw.file_name_value = QLabel("No file loaded")
        self.mw.file_name_value.setWordWrap(True)
        file_name_layout = QVBoxLayout()
        file_name_layout.addWidget(self.mw.file_name_label)
        file_name_layout.addWidget(self.mw.file_name_value)
        main_layout.addLayout(file_name_layout)

        # Content Layout
        content_layout = QHBoxLayout()
        main_layout.addLayout(content_layout)

        # Left Widget (UI)
        left_widget = QWidget()
        self.mw.left_layout = QVBoxLayout(left_widget)
        content_layout.addWidget(left_widget, 1)

        # Right Widget (VTK)
        self.mw.vtk_widget = QVTKRenderWindowInteractor(central_widget)
        content_layout.addWidget(self.mw.vtk_widget, 4)

        # Setup Components
        self.setup_buttons()
        self.setup_stl_properties_ui()
        self.setup_points_ui()

    def setup_buttons(self):
        button_layout = QVBoxLayout()
        button_layout.setSpacing(10)

        # First row
        first_row_widget = QWidget()
        first_row_layout = QHBoxLayout()
        first_row_layout.setContentsMargins(0, 0, 0, 0)
        first_row_layout.setSpacing(5)
        
        first_row = QHBoxLayout()
        button_layout.addLayout(first_row)

        # Load STL
        self.mw.load_button = QPushButton("Load STL")
        self.mw.load_button.clicked.connect(self.mw.load_stl_file)
        first_row.addWidget(self.mw.load_button)

        # Load XML
        self.mw.load_xml_button = QPushButton("ImportXML")
        self.mw.load_xml_button.clicked.connect(self.mw.load_xml_file)
        first_row.addWidget(self.mw.load_xml_button)

        first_row_widget.setLayout(first_row_layout)

        # Load STL with XML
        self.mw.load_stl_xml_button = QPushButton("Load STL with XML")
        self.mw.load_stl_xml_button.clicked.connect(self.mw.load_stl_with_xml)
        button_layout.addWidget(self.mw.load_stl_xml_button)

        # Spacer
        spacer = QWidget()
        spacer.setFixedHeight(0)
        button_layout.addWidget(spacer)
        
        # Export XML
        self.mw.export_urdf_button = QPushButton("Export XML")
        self.mw.export_urdf_button.clicked.connect(self.mw.export_urdf)
        button_layout.addWidget(self.mw.export_urdf_button)
        
        # Export Mirror
        self.mw.export_mirror_button = QPushButton("Export mirror STL with XML")
        self.mw.export_mirror_button.clicked.connect(self.mw.export_mirror_stl_xml)
        button_layout.addWidget(self.mw.export_mirror_button)

        # Bulk Convert
        self.mw.bulk_convert_button = QPushButton("Batch convert \"l_\" to \"r_\" in /meshes")
        self.mw.bulk_convert_button.clicked.connect(self.mw.bulk_convert_l_to_r)
        button_layout.addWidget(self.mw.bulk_convert_button)

        # Export STL
        self.mw.export_stl_button = QPushButton("Save STL (Point 1 as origin)")
        self.mw.export_stl_button.clicked.connect(self.mw.export_stl_with_new_origin)
        button_layout.addWidget(self.mw.export_stl_button)

        self.mw.left_layout.addLayout(button_layout)

    def setup_stl_properties_ui(self):
        grid_layout = QGridLayout()
        grid_layout.setVerticalSpacing(3)
        grid_layout.setHorizontalSpacing(5)
        grid_layout.setContentsMargins(0, 0, 0, 0)
        grid_layout.setColumnMinimumWidth(0, 15)

        properties = [
            ("Volume (m^3):", "volume"),
            ("Density (kg/m^3):", "density"),
            ("Mass (kg):", "mass"),
            ("Center of Mass:", "com"),
            ("Inertia Tensor:", "inertia_tensor")
        ]

        for i, (label_text, prop_name) in enumerate(properties):
            if prop_name != "inertia_tensor":
                checkbox = QCheckBox()
                setattr(self.mw, f"{prop_name}_checkbox", checkbox)
                
                label = QLabel(label_text)
                input_field = QLineEdit("0.000000")
                setattr(self.mw, f"{prop_name}_input", input_field)
                
                grid_layout.addWidget(checkbox, i, 0)
                grid_layout.addWidget(label, i, 1)
                grid_layout.addWidget(input_field, i, 2)
            else:
                label = QLabel(label_text)
                grid_layout.addWidget(label, i, 1)

        # Inertia Tensor
        self.mw.inertia_tensor_input = QTextEdit()
        self.mw.inertia_tensor_input.setReadOnly(True)
        self.mw.inertia_tensor_input.setFixedHeight(40)
        self.mw.inertia_tensor_input.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.mw.inertia_tensor_input.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.mw.inertia_tensor_input.setWordWrapMode(QTextOption.WrapMode.WrapAnywhere)
        grid_layout.addWidget(QLabel("Inertia Tensor:"), len(properties) - 1, 1)
        grid_layout.addWidget(self.mw.inertia_tensor_input, len(properties) - 1, 2)
        
        font = self.mw.inertia_tensor_input.font()
        font.setPointSize(10)
        self.mw.inertia_tensor_input.setFont(font)

        self.mw.density_input.setText("1.000000")

        # Calculate Button
        pre_calculate_spacer = QWidget()
        pre_calculate_spacer.setFixedHeight(2)
        grid_layout.addWidget(pre_calculate_spacer, len(properties), 0, 1, 3)

        self.mw.calculate_button = QPushButton("Calculate")
        self.mw.calculate_button.clicked.connect(self.mw.calculate_and_update_properties)
        grid_layout.addWidget(self.mw.calculate_button, len(properties) + 1, 1, 1, 2)

        spacer = QWidget()
        spacer.setFixedHeight(2)
        grid_layout.addWidget(spacer, len(properties) + 2, 0, 1, 3)

        # Axis Layout
        axis_layout = QHBoxLayout()
        self.mw.axis_group = QButtonGroup(self.mw)
        axis_label = QLabel("Axis:")
        axis_layout.addWidget(axis_label)
        
        radio_texts = ["X:roll", "Y:pitch", "Z:yaw", "fixed"]
        self.mw.radio_buttons = []
        for i, text in enumerate(radio_texts):
            radio = QRadioButton(text)
            self.mw.axis_group.addButton(radio, i)
            axis_layout.addWidget(radio)
            self.mw.radio_buttons.append(radio)
        self.mw.radio_buttons[0].setChecked(True)

        # Rotate Test Button
        self.mw.rotate_test_button = QPushButton("Rotate Test")
        self.mw.rotate_test_button.pressed.connect(self.mw.start_rotation_test)
        self.mw.rotate_test_button.released.connect(self.mw.stop_rotation_test)
        axis_layout.addWidget(self.mw.rotate_test_button)
        
        grid_layout.addLayout(axis_layout, len(properties) + 3, 0, 1, 3)

        # Rotation Timer
        self.mw.rotation_timer = QTimer()
        self.mw.rotation_timer.timeout.connect(self.mw.update_test_rotation)
        self.mw.original_transform = None
        self.mw.test_rotation_angle = 0

        # Color Layout
        color_layout = QHBoxLayout()
        color_layout.addWidget(QLabel("Color:"))
        
        self.mw.color_inputs = []
        for label in ['R:', 'G:', 'B:']:
            color_layout.addWidget(QLabel(label))
            color_input = QLineEdit("1.0")
            color_input.setFixedWidth(50)
            color_input.textChanged.connect(self.mw.update_color_sample)
            self.mw.color_inputs.append(color_input)
            color_layout.addWidget(color_input)
        
        self.mw.color_sample = QLabel()
        self.mw.color_sample.setFixedSize(30, 20)
        self.mw.color_sample.setStyleSheet("background-color: rgb(255,255,255); border: 1px solid black;")
        color_layout.addWidget(self.mw.color_sample)
        
        pick_button = QPushButton("Pick")
        pick_button.clicked.connect(self.mw.show_color_picker)
        color_layout.addWidget(pick_button)
        
        apply_button = QPushButton("Apply")
        apply_button.clicked.connect(self.mw.apply_color_to_stl)
        color_layout.addWidget(apply_button)
        
        color_layout.addStretch()
        grid_layout.addLayout(color_layout, len(properties) + 4, 0, 1, 3)

        self.mw.left_layout.addLayout(grid_layout)

    def setup_points_ui(self):
        points_layout = QGridLayout()
        points_layout.setContentsMargins(0, 0, 0, 0)
        points_layout.setVerticalSpacing(3)
        points_layout.setHorizontalSpacing(15)

        for i in range(self.mw.num_points):
            row = i
            checkbox = QCheckBox(f"Point {i+1}")
            checkbox.setMinimumWidth(80)
            # Use lambda to capture i
            checkbox.stateChanged.connect(lambda state, index=i: self.mw.toggle_point(state, index))
            self.mw.point_checkboxes.append(checkbox)
            points_layout.addWidget(checkbox, row, 0)

            inputs = []
            for j, axis in enumerate(['X', 'Y', 'Z']):
                h_layout = QHBoxLayout()
                h_layout.setSpacing(2)
                h_layout.setContentsMargins(0, 0, 0, 0)
                
                label = QLabel(f"{axis}:")
                label.setFixedWidth(15)
                h_layout.addWidget(label)
                
                input_field = QLineEdit("0.000000")
                input_field.setFixedWidth(80)
                input_field.editingFinished.connect(lambda index=i: self.mw.update_point_from_text(index))
                inputs.append(input_field)
                h_layout.addWidget(input_field)
                
                points_layout.addLayout(h_layout, row, j + 1)
            self.mw.point_inputs.append(inputs)

            # Set Button
            set_button = QPushButton("Set")
            set_button.setFixedWidth(40)
            set_button.clicked.connect(lambda checked, index=i: self.mw.set_point_to_com(index))
            self.mw.point_set_buttons.append(set_button)
            points_layout.addWidget(set_button, row, 4)

            # Reset Button
            reset_button = QPushButton("Reset")
            reset_button.setFixedWidth(40)
            reset_button.clicked.connect(lambda checked, index=i: self.mw.reset_point(index))
            self.mw.point_reset_buttons.append(reset_button)
            points_layout.addWidget(reset_button, row, 5)

        self.mw.left_layout.addLayout(points_layout)