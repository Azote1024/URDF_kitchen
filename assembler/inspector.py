
import os
import traceback
import xml.etree.ElementTree as ET
import numpy as np
import vtk
from PySide6 import QtWidgets, QtCore, QtGui

from utils.urdf_kitchen_config import AssemblerConfig as Config
from utils.urdf_kitchen_logger import setup_logger
from .nodes import LinkNode, BaseLinkNode

logger = setup_logger("Assembler")

class InspectorWindow(QtWidgets.QWidget):
    """
    Node Inspector Window for displaying and editing node details.
    
    Features:
    - Edit node name
    - Display physical properties (mass, volume, inertia)
    - Associate STL files and display settings
    - Edit connection point (port) coordinates
    - Change node color
    """
    
    def __init__(self, parent=None, stl_viewer=None):
        super(InspectorWindow, self).__init__(parent)
        self.setWindowTitle("Node Inspector")
        self.setMinimumWidth(400)
        self.setMinimumHeight(600)

        self.setWindowFlags(self.windowFlags() |
                            QtCore.Qt.WindowStaysOnTopHint)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)

        self.current_node = None
        self.stl_viewer = stl_viewer
        self.port_widgets = []

        # Initialize UI
        self.setup_ui()

        # Set focus policy to accept keyboard focus
        self.setFocusPolicy(QtCore.Qt.StrongFocus)

    def setup_ui(self):
        """Initialize UI"""
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 5, 10, 5)

        # Scroll Area
        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)

        # Scroll Content Widget
        scroll_content = QtWidgets.QWidget()
        content_layout = QtWidgets.QVBoxLayout(scroll_content)
        content_layout.setSpacing(30)
        content_layout.setContentsMargins(5, 5, 5, 5)

        # Node Name Section
        name_layout = QtWidgets.QHBoxLayout()
        name_layout.addWidget(QtWidgets.QLabel("Node Name:"))
        self.name_edit = QtWidgets.QLineEdit()
        self.name_edit.setPlaceholderText("Enter node name")
        self.name_edit.editingFinished.connect(self.update_node_name)
        name_layout.addWidget(self.name_edit)

        content_layout.addLayout(name_layout)
        content_layout.addSpacing(5)

        # Physical Properties Section
        physics_layout = QtWidgets.QGridLayout()
        physics_layout.addWidget(QtWidgets.QLabel("Volume:"), 0, 0)
        self.volume_input = QtWidgets.QLineEdit()
        self.volume_input.setReadOnly(True)
        physics_layout.addWidget(self.volume_input, 0, 1)

        physics_layout.addWidget(QtWidgets.QLabel("Mass:"), 1, 0)
        self.mass_input = QtWidgets.QLineEdit()
        self.mass_input.setValidator(QtGui.QDoubleValidator())
        physics_layout.addWidget(self.mass_input, 1, 1)
        content_layout.addLayout(physics_layout)

        # Rotation Axis Section
        rotation_layout = QtWidgets.QHBoxLayout()
        rotation_layout.addWidget(QtWidgets.QLabel("Rotation Axis:   "))
        self.axis_group = QtWidgets.QButtonGroup(self)
        for i, axis in enumerate(['X (Roll)', 'Y (Pitch)', 'Z (Yaw)', 'Fixed']):
            radio = QtWidgets.QRadioButton(axis)
            self.axis_group.addButton(radio, i)
            rotation_layout.addWidget(radio)
        content_layout.addLayout(rotation_layout)

        # Rotation Test Button
        rotation_test_layout = QtWidgets.QHBoxLayout()
        rotation_test_layout.addStretch()
        self.rotation_test_button = QtWidgets.QPushButton("Rotation Test")
        self.rotation_test_button.setFixedWidth(120)
        self.rotation_test_button.pressed.connect(self.start_rotation_test)
        self.rotation_test_button.released.connect(self.stop_rotation_test) 
        rotation_test_layout.addWidget(self.rotation_test_button)
        content_layout.addLayout(rotation_test_layout)

        # Massless Decoration Checkbox
        massless_layout = QtWidgets.QHBoxLayout()
        self.massless_checkbox = QtWidgets.QCheckBox("Massless Decoration")
        self.massless_checkbox.setChecked(False)
        massless_layout.addWidget(self.massless_checkbox)
        content_layout.addLayout(massless_layout)

        self.massless_checkbox.stateChanged.connect(self.update_massless_decoration)

        # Color Section
        color_layout = QtWidgets.QHBoxLayout()
        color_layout.addWidget(QtWidgets.QLabel("Color:"))

        # Color Sample Chip
        self.color_sample = QtWidgets.QLabel()
        self.color_sample.setFixedSize(20, 20)
        self.color_sample.setStyleSheet(
        "background-color: rgb(255,255,255); border: 1px solid black;")
        color_layout.addWidget(self.color_sample)

        # R,G,B Inputs
        color_layout.addWidget(QtWidgets.QLabel("   R:"))
        self.color_inputs = []
        for label in ['', 'G:', 'B:']:
            if label:
                color_layout.addWidget(QtWidgets.QLabel(label))
            color_input = QtWidgets.QLineEdit("1.0")
            color_input.setFixedWidth(50)
            color_input.setValidator(QtGui.QDoubleValidator(0.0, 1.0, 3))
            self.color_inputs.append(color_input)
            color_layout.addWidget(color_input)

        color_layout.addStretch()
        content_layout.addLayout(color_layout)

        # Color Picker Button
        pick_button = QtWidgets.QPushButton("Pick")
        pick_button.clicked.connect(self.show_color_picker)
        pick_button.setFixedWidth(40)
        color_layout.addWidget(pick_button)

        # Apply Button
        apply_button = QtWidgets.QPushButton("Set")
        apply_button.clicked.connect(self.apply_color_to_stl)
        apply_button.setFixedWidth(40)
        color_layout.addWidget(apply_button)
        
        color_layout.addStretch()
        content_layout.addLayout(color_layout)

        # Output Ports Section
        ports_layout = QtWidgets.QVBoxLayout()
        self.ports_layout = QtWidgets.QVBoxLayout()
        ports_layout.addLayout(self.ports_layout)

        # SET Button Layout
        set_button_layout = QtWidgets.QHBoxLayout()
        set_button_layout.addStretch()
        set_button = QtWidgets.QPushButton("SET")
        set_button.clicked.connect(self.apply_port_values)
        set_button_layout.addWidget(set_button)
        ports_layout.addLayout(set_button_layout)
        content_layout.addLayout(ports_layout)

        self.port_widgets = []

        # Point Controls Section
        point_layout = QtWidgets.QHBoxLayout()
        point_layout.addWidget(QtWidgets.QLabel("Point Controls:"))
        self.add_point_btn = QtWidgets.QPushButton("[+] Add")
        self.remove_point_btn = QtWidgets.QPushButton("[-] Remove")
        point_layout.addWidget(self.add_point_btn)
        point_layout.addWidget(self.remove_point_btn)
        self.add_point_btn.clicked.connect(self.add_point)
        self.remove_point_btn.clicked.connect(self.remove_point)
        content_layout.addLayout(point_layout)

        # File Controls Section
        file_layout = QtWidgets.QHBoxLayout()
        self.load_stl_btn = QtWidgets.QPushButton("Load STL")
        self.load_xml_btn = QtWidgets.QPushButton("Load XML")
        self.load_xml_with_stl_btn = QtWidgets.QPushButton("Load XML with STL")
        file_layout.addWidget(self.load_stl_btn)
        file_layout.addWidget(self.load_xml_btn)
        file_layout.addWidget(self.load_xml_with_stl_btn)
        self.load_stl_btn.clicked.connect(self.load_stl)
        self.load_xml_btn.clicked.connect(self.load_xml)
        self.load_xml_with_stl_btn.clicked.connect(self.load_xml_with_stl)
        content_layout.addLayout(file_layout)

        # Set content to scroll area
        scroll_area.setWidget(scroll_content)
        main_layout.addWidget(scroll_area)

        # Spacing adjustments
        name_layout.setSpacing(2)
        physics_layout.setSpacing(2)
        rotation_layout.setSpacing(2)
        color_layout.setSpacing(2)
        ports_layout.setSpacing(2)
        point_layout.setSpacing(2)
        file_layout.setSpacing(2)

        physics_layout.setVerticalSpacing(2)
        physics_layout.setHorizontalSpacing(2)

        for line_edit in self.findChildren(QtWidgets.QLineEdit):
            line_edit.setStyleSheet("QLineEdit { padding-left: 2px; padding-top: 0px; padding-bottom: 0px; }")

    def setup_validators(self):
        """Setup validators for numerical inputs"""
        try:
            mass_validator = QtGui.QDoubleValidator()
            mass_validator.setBottom(0.0)
            self.mass_input.setValidator(mass_validator)

            volume_validator = QtGui.QDoubleValidator()
            volume_validator.setBottom(0.0)
            self.volume_input.setValidator(volume_validator)

            rgb_validator = QtGui.QDoubleValidator(0.0, 1.0, 3)
            for color_input in self.color_inputs:
                color_input.setValidator(rgb_validator)

            coord_validator = QtGui.QDoubleValidator()
            for port_widget in self.port_widgets:
                for input_field in port_widget.findChildren(QtWidgets.QLineEdit):
                    input_field.setValidator(coord_validator)

            logger.debug("Input validators setup completed")

        except Exception as e:
            logger.error(f"Error setting up validators: {str(e)}")
            logger.error(traceback.format_exc())

    def apply_color_to_stl(self):
        """Apply selected color to STL model and color sample"""
        if not self.current_node:
            logger.warning("No node selected")
            return
        
        try:
            rgb_values = [float(input.text()) for input in self.color_inputs]
            rgb_values = [max(0.0, min(1.0, value)) for value in rgb_values]
            
            self.current_node.node_color = rgb_values
            
            rgb_display = [int(v * 255) for v in rgb_values]
            self.color_sample.setStyleSheet(
                f"background-color: rgb({rgb_display[0]},{rgb_display[1]},{rgb_display[2]}); "
                f"border: 1px solid black;"
            )
            
            if self.stl_viewer and hasattr(self.stl_viewer, 'stl_actors'):
                if self.current_node in self.stl_viewer.stl_actors:
                    actor = self.stl_viewer.stl_actors[self.current_node]
                    actor.GetProperty().SetColor(*rgb_values)
                    self.stl_viewer.vtkWidget.GetRenderWindow().Render()
                    logger.info(f"Applied color: RGB({rgb_values[0]:.3f}, {rgb_values[1]:.3f}, {rgb_values[2]:.3f})")
                else:
                    logger.warning("No STL model found for this node")
            
        except ValueError as e:
            logger.error(f"Error: Invalid color value - {str(e)}")
        except Exception as e:
            logger.error(f"Error applying color: {str(e)}")
            logger.error(traceback.format_exc())

    def update_color_sample(self):
        """Update color sample display"""
        try:
            rgb_values = [min(255, max(0, int(float(input.text()) * 255))) 
                        for input in self.color_inputs]
            self.color_sample.setStyleSheet(
                f"background-color: rgb({rgb_values[0]},{rgb_values[1]},{rgb_values[2]}); "
                f"border: 1px solid black;"
            )
            
            if self.current_node:
                self.current_node.node_color = [float(input.text()) for input in self.color_inputs]
                
        except ValueError as e:
            logger.error(f"Error updating color sample: {str(e)}")
            logger.error(traceback.format_exc())

    def update_port_coordinate(self, port_index, coord_index, value):
        """Update port coordinate"""
        try:
            if self.current_node and hasattr(self.current_node, 'points'):
                if 0 <= port_index < len(self.current_node.points):
                    try:
                        new_value = float(value)
                        self.current_node.points[port_index]['xyz'][coord_index] = new_value
                        logger.debug(
                            f"Updated port {port_index+1} coordinate {coord_index} to {new_value}")
                    except ValueError:
                        logger.warning("Invalid coordinate value")
        except Exception as e:
            logger.error(f"Error updating coordinate: {str(e)}")

    def update_info(self, node):
        """Update node information"""
        self.current_node = node

        try:
            # Node Name
            self.name_edit.setText(node.name())

            # Volume & Mass
            if hasattr(node, 'volume_value'):
                self.volume_input.setText(f"{node.volume_value:.6f}")
                logger.debug(f"Volume set to: {node.volume_value}")

            if hasattr(node, 'mass_value'):
                self.mass_input.setText(f"{node.mass_value:.6f}")
                logger.debug(f"Mass set to: {node.mass_value}")

            # Rotation Axis
            if hasattr(node, 'rotation_axis'):
                axis_button = self.axis_group.button(node.rotation_axis)
                if axis_button:
                    axis_button.setChecked(True)
                    logger.debug(f"Rotation axis set to: {node.rotation_axis}")
            else:
                node.rotation_axis = 0
                if self.axis_group.button(0):
                    self.axis_group.button(0).setChecked(True)
                    logger.debug("Default rotation axis set to X (0)")

            # Massless Decoration
            if hasattr(node, 'massless_decoration'):
                self.massless_checkbox.setChecked(node.massless_decoration)
                logger.debug(f"Massless decoration set to: {node.massless_decoration}")
            else:
                node.massless_decoration = False
                self.massless_checkbox.setChecked(False)
                logger.debug("Default massless decoration set to False")

            # Color settings
            if hasattr(node, 'node_color') and node.node_color:
                logger.debug(f"Setting color: {node.node_color}")
                for i, value in enumerate(node.node_color[:3]):
                    self.color_inputs[i].setText(f"{value:.3f}")
                
                rgb_display = [int(v * 255) for v in node.node_color[:3]]
                self.color_sample.setStyleSheet(
                    f"background-color: rgb({rgb_display[0]},{rgb_display[1]},{rgb_display[2]}); "
                    f"border: 1px solid black;"
                )
                self.apply_color_to_stl()
            else:
                node.node_color = Config.DEFAULT_NODE_COLOR
                for color_input in self.color_inputs:
                    color_input.setText("1.000")
                self.color_sample.setStyleSheet(
                    "background-color: rgb(255,255,255); border: 1px solid black;"
                )
                logger.debug("Default color set to white")

            for button in self.axis_group.buttons():
                button.clicked.connect(lambda checked, btn=button: self.update_rotation_axis(btn))

            # Output Ports
            self.update_output_ports(node)

            self.axis_group.buttonClicked.connect(self.on_axis_selection_changed)

            self.setup_validators()

            logger.debug(f"Inspector window updated for node: {node.name()}")

        except Exception as e:
            logger.error(f"Error updating inspector info: {str(e)}")
            logger.error(traceback.format_exc())

    def update_rotation_axis(self, button):
        """Handle rotation axis selection change"""
        if self.current_node:
            self.current_node.rotation_axis = self.axis_group.id(button)
            logger.debug(f"Updated rotation axis to: {self.current_node.rotation_axis}")

    def on_axis_selection_changed(self, button):
        """Event handler for rotation axis selection change"""
        if self.current_node:
            if self.stl_viewer and self.current_node in self.stl_viewer.transforms:
                current_transform = self.stl_viewer.transforms[self.current_node]
                current_position = current_transform.GetPosition()
            else:
                current_position = [0, 0, 0]

            axis_id = self.axis_group.id(button)
            self.current_node.rotation_axis = axis_id

            axis_types = ['X (Roll)', 'Y (Pitch)', 'Z (Yaw)', 'Fixed']
            if 0 <= axis_id < len(axis_types):
                logger.debug(f"Rotation axis changed to: {axis_types[axis_id]}")
            else:
                logger.warning(f"Invalid rotation axis ID: {axis_id}")

            if self.stl_viewer:
                if self.current_node in self.stl_viewer.transforms:
                    transform = self.stl_viewer.transforms[self.current_node]
                    transform.Identity()
                    transform.Translate(*current_position)
                    
                    if hasattr(self.current_node, 'current_rotation'):
                        angle = self.current_node.current_rotation
                        if axis_id == 0:
                            transform.RotateX(angle)
                        elif axis_id == 1:
                            transform.RotateY(angle)
                        elif axis_id == 2:
                            transform.RotateZ(angle)
                    
                    if self.current_node in self.stl_viewer.stl_actors:
                        self.stl_viewer.stl_actors[self.current_node].SetUserTransform(transform)
                        self.stl_viewer.vtkWidget.GetRenderWindow().Render()
                        logger.debug(f"Updated transform for node {self.current_node.name()} at position {current_position}")
                        
    def show_color_picker(self):
        """Show color picker dialog"""
        try:
            current_color = QtGui.QColor(
                *[min(255, max(0, int(float(input.text()) * 255))) 
                for input in self.color_inputs]
            )
        except ValueError:
            current_color = QtGui.QColor(255, 255, 255)
        
        color = QtWidgets.QColorDialog.getColor(
            initial=current_color,
            parent=self,
            options=QtWidgets.QColorDialog.DontUseNativeDialog
        )
        
        if color.isValid():
            rgb_values = [color.red() / 255.0, color.green() / 255.0, color.blue() / 255.0]
            
            for i, value in enumerate(rgb_values):
                self.color_inputs[i].setText(f"{value:.3f}")
            
            self.color_sample.setStyleSheet(
                f"background-color: rgb({color.red()},{color.green()},{color.blue()}); "
                f"border: 1px solid black;"
            )
            
            if self.current_node:
                self.current_node.node_color = rgb_values
                
            self.apply_color_to_stl()
            
            logger.info(f"Color picker: Selected RGB({rgb_values[0]:.3f}, {rgb_values[1]:.3f}, {rgb_values[2]:.3f})")

    def update_node_name(self):
        """Update node name"""
        if self.current_node:
            new_name = self.name_edit.text()
            old_name = self.current_node.name()
            if new_name != old_name:
                self.current_node.set_name(new_name)
                logger.info(f"Node name updated from '{old_name}' to '{new_name}'")

    def add_point(self):
        """Add a point"""
        if self.current_node and hasattr(self.current_node, '_add_output'):
            new_port_name = self.current_node._add_output()
            if new_port_name:
                self.update_info(self.current_node)
                logger.info(f"Added new port: {new_port_name}")

    def remove_point(self):
        """Remove a point"""
        if self.current_node and hasattr(self.current_node, 'remove_output'):
            self.current_node.remove_output()
            self.update_info(self.current_node)
            logger.info("Removed last port")

    def load_stl(self):
        """Load STL file"""
        if self.current_node:
            file_name, _ = QtWidgets.QFileDialog.getOpenFileName(
                self, "Open STL File", "", "STL Files (*.stl)")
            if file_name:
                self.current_node.stl_file = file_name
                if self.stl_viewer:
                    self.stl_viewer.load_stl_for_node(self.current_node)

    def closeEvent(self, event):
        """Handle window close event"""
        try:
            for widget in self.findChildren(QtWidgets.QWidget):
                if widget is not self:
                    widget.setParent(None)
                    widget.deleteLater()

            self.current_node = None
            self.stl_viewer = None
            self.port_widgets.clear()

            event.accept()

        except Exception as e:
            logger.error(f"Error in closeEvent: {str(e)}")
            event.accept()

    def load_xml(self):
        """Load XML file"""
        if not self.current_node:
            logger.warning("No node selected")
            return

        file_name, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Open XML File", "", "XML Files (*.xml)")

        if not file_name:
            return

        try:
            tree = ET.parse(file_name)
            root = tree.getroot()

            if root.tag != 'urdf_part':
                logger.error("Invalid XML format: Root element should be 'urdf_part'")
                return

            logger.info("Loading XML file...")

            link_elem = root.find('link')
            if link_elem is not None:
                link_name = link_elem.get('name')
                if link_name:
                    self.current_node.set_name(link_name)
                    self.name_edit.setText(link_name)
                    logger.debug(f"Set link name: {link_name}")

                inertial_elem = link_elem.find('inertial')
                if inertial_elem is not None:
                    volume_elem = inertial_elem.find('volume')
                    if volume_elem is not None:
                        volume = float(volume_elem.get('value', '0.0'))
                        self.current_node.volume_value = volume
                        self.volume_input.setText(f"{volume:.6f}")
                        logger.debug(f"Set volume: {volume}")

                    mass_elem = inertial_elem.find('mass')
                    if mass_elem is not None:
                        mass = float(mass_elem.get('value', '0.0'))
                        self.current_node.mass_value = mass
                        self.mass_input.setText(f"{mass:.6f}")
                        logger.debug(f"Set mass: {mass}")

                    inertia_elem = inertial_elem.find('inertia')
                    if inertia_elem is not None:
                        self.current_node.inertia = {
                            'ixx': float(inertia_elem.get('ixx', '0')),
                            'ixy': float(inertia_elem.get('ixy', '0')),
                            'ixz': float(inertia_elem.get('ixz', '0')),
                            'iyy': float(inertia_elem.get('iyy', '0')),
                            'iyz': float(inertia_elem.get('iyz', '0')),
                            'izz': float(inertia_elem.get('izz', '0'))
                        }
                        logger.debug("Set inertia tensor")

            material_elem = root.find('.//material/color')
            if material_elem is not None:
                rgba = material_elem.get('rgba', '1.0 1.0 1.0 1.0').split()
                rgb_values = [float(x) for x in rgba[:3]]
                self.current_node.node_color = rgb_values
                for i, value in enumerate(rgb_values):
                    self.color_inputs[i].setText(f"{value}")
                self.update_color_sample()
                self.apply_color_to_stl()
                logger.debug(f"Set color: RGB({rgb_values[0]:.3f}, {rgb_values[1]:.3f}, {rgb_values[2]:.3f})")

            joint_elem = root.find('joint')
            if joint_elem is not None:
                joint_type = joint_elem.get('type', '')
                if joint_type == 'fixed':
                    self.current_node.rotation_axis = 3
                    if self.axis_group.button(3):
                        self.axis_group.button(3).setChecked(True)
                    logger.debug("Set rotation axis to Fixed")
                else:
                    axis_elem = joint_elem.find('axis')
                    if axis_elem is not None:
                        axis_xyz = axis_elem.get('xyz', '1 0 0').split()
                        axis_values = [float(x) for x in axis_xyz]
                        if axis_values[2] == 1:
                            self.current_node.rotation_axis = 2
                            self.axis_group.button(2).setChecked(True)
                            logger.debug("Set rotation axis to Z")
                        elif axis_values[1] == 1:
                            self.current_node.rotation_axis = 1
                            self.axis_group.button(1).setChecked(True)
                            logger.debug("Set rotation axis to Y")
                        else:
                            self.current_node.rotation_axis = 0
                            self.axis_group.button(0).setChecked(True)
                            logger.debug("Set rotation axis to X")
                        logger.debug(f"Set rotation axis from xyz: {axis_xyz}")

            points = root.findall('point')
            num_points = len(points)
            logger.debug(f"Found {num_points} points in XML")

            current_ports = len(self.current_node.output_ports())
            logger.debug(f"Current ports: {current_ports}, Required points: {num_points}")

            if isinstance(self.current_node, LinkNode):
                while current_ports < num_points:
                    self.current_node._add_output()
                    current_ports += 1
                    logger.debug(f"Added new port, total now: {current_ports}")

                while current_ports > num_points:
                    self.current_node.remove_output()
                    current_ports -= 1
                    logger.debug(f"Removed port, total now: {current_ports}")

                self.current_node.points = []
                for point_elem in points:
                    point_name = point_elem.get('name')
                    point_type = point_elem.get('type')
                    point_xyz_elem = point_elem.find('point_xyz')

                    if point_xyz_elem is not None and point_xyz_elem.text:
                        xyz_values = [float(x) for x in point_xyz_elem.text.strip().split()]
                        self.current_node.points.append({
                            'name': point_name,
                            'type': point_type,
                            'xyz': xyz_values
                        })
                        logger.debug(f"Added point {point_name}: {xyz_values}")

                self.current_node.cumulative_coords = []
                for i in range(len(self.current_node.points)):
                    self.current_node.cumulative_coords.append({
                        'point_index': i,
                        'xyz': [0.0, 0.0, 0.0]
                    })

                self.current_node.output_count = len(self.current_node.points)
                logger.debug(f"Updated output_count to: {self.current_node.output_count}")

            self.update_info(self.current_node)
            logger.info(f"XML file loaded: {file_name}")

        except Exception as e:
            logger.error(f"Error loading XML: {str(e)}")
            logger.error(traceback.format_exc())
            
    def load_xml_with_stl(self):
        """Load XML file and corresponding STL file"""
        if not self.current_node:
            logger.warning("No node selected")
            return

        xml_file, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Open XML File", "", "XML Files (*.xml)")

        if not xml_file:
            return

        try:
            xml_dir = os.path.dirname(xml_file)
            xml_name = os.path.splitext(os.path.basename(xml_file))[0]
            stl_path = os.path.join(xml_dir, f"{xml_name}.stl")

            tree = ET.parse(xml_file)
            root = tree.getroot()

            if root.tag != 'urdf_part':
                logger.error("Invalid XML format: Root element should be 'urdf_part'")
                return

            link_elem = root.find('link')
            if link_elem is not None:
                link_name = link_elem.get('name')
                if link_name:
                    self.current_node.set_name(link_name)
                    self.name_edit.setText(link_name)

                mass_elem = link_elem.find('mass')
                if mass_elem is not None:
                    mass = float(mass_elem.get('value', '0.0'))
                    self.current_node.mass_value = mass
                    self.mass_input.setText(f"{mass:.6f}")

                volume_elem = root.find('.//volume')
                if volume_elem is not None:
                    volume = float(volume_elem.get('value', '0.0'))
                    self.current_node.volume_value = volume
                    self.volume_input.setText(f"{volume:.6f}")

                inertia_elem = link_elem.find('inertia')
                if inertia_elem is not None:
                    self.current_node.inertia = {
                        'ixx': float(inertia_elem.get('ixx', '0')),
                        'ixy': float(inertia_elem.get('ixy', '0')),
                        'ixz': float(inertia_elem.get('ixz', '0')),
                        'iyy': float(inertia_elem.get('iyy', '0')),
                        'iyz': float(inertia_elem.get('iyz', '0')),
                        'izz': float(inertia_elem.get('izz', '0'))
                    }

            material_elem = root.find('.//material/color')
            if material_elem is not None:
                rgba = material_elem.get('rgba', '1.0 1.0 1.0 1.0').split()
                rgb_values = [float(x) for x in rgba[:3]]
                self.current_node.node_color = rgb_values
                for i, value in enumerate(rgb_values):
                    self.color_inputs[i].setText(f"{value}")
                self.update_color_sample()
                logger.debug(f"Set color: RGB({rgb_values[0]:.3f}, {rgb_values[1]:.3f}, {rgb_values[2]:.3f})")

            joint_elem = root.find('.//joint/axis')
            if joint_elem is not None:
                axis_xyz = joint_elem.get('xyz', '1 0 0').split()
                axis_values = [float(x) for x in axis_xyz]
                if axis_values[2] == 1:
                    self.current_node.rotation_axis = 2
                    self.axis_group.button(2).setChecked(True)
                elif axis_values[1] == 1:
                    self.current_node.rotation_axis = 1
                    self.axis_group.button(1).setChecked(True)
                else:
                    self.current_node.rotation_axis = 0
                    self.axis_group.button(0).setChecked(True)
                logger.debug(f"Set rotation axis: {self.current_node.rotation_axis} from xyz: {axis_xyz}")

            points = root.findall('point')
            num_points = len(points)
            logger.debug(f"Found {num_points} points")

            current_ports = len(self.current_node.points)
            if num_points > current_ports:
                ports_to_add = num_points - current_ports
                for _ in range(ports_to_add):
                    self.add_point()
            elif num_points < current_ports:
                ports_to_remove = current_ports - num_points
                for _ in range(ports_to_remove):
                    self.remove_point()

            self.current_node.points = []
            for point_elem in points:
                point_name = point_elem.get('name')
                point_type = point_elem.get('type')
                point_xyz_elem = point_elem.find('point_xyz')

                if point_xyz_elem is not None and point_xyz_elem.text:
                    xyz_values = [float(x) for x in point_xyz_elem.text.strip().split()]
                    self.current_node.points.append({
                        'name': point_name,
                        'type': point_type,
                        'xyz': xyz_values
                    })
                    logger.debug(f"Added point {point_name}: {xyz_values}")

            if os.path.exists(stl_path):
                logger.info(f"Found corresponding STL file: {stl_path}")
                self.current_node.stl_file = stl_path
                if self.stl_viewer:
                    self.stl_viewer.load_stl_for_node(self.current_node)
                    self.apply_color_to_stl()
            else:
                logger.warning(f"Warning: STL file not found: {stl_path}")
                msg_box = QtWidgets.QMessageBox()
                msg_box.setIcon(QtWidgets.QMessageBox.Warning)
                msg_box.setWindowTitle("STL File Not Found")
                msg_box.setText("STL file not found in the same directory.")
                msg_box.setInformativeText("Would you like to select the STL file manually?")
                msg_box.setStandardButtons(QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
                msg_box.setDefaultButton(QtWidgets.QMessageBox.Yes)

                if msg_box.exec() == QtWidgets.QMessageBox.Yes:
                    stl_file, _ = QtWidgets.QFileDialog.getOpenFileName(
                        self, "Select STL File", xml_dir, "STL Files (*.stl)")
                    if stl_file:
                        self.current_node.stl_file = stl_file
                        if self.stl_viewer:
                            self.stl_viewer.load_stl_for_node(self.current_node)
                            self.apply_color_to_stl()
                        logger.info(f"Manually selected STL file: {stl_file}")
                    else:
                        logger.info("STL file selection cancelled")
                else:
                    logger.info("STL file loading skipped")

            self.update_info(self.current_node)
            logger.info(f"XML file loaded: {xml_file}")

        except Exception as e:
            logger.error(f"Error loading XML with STL: {str(e)}")
            logger.error(traceback.format_exc())

    def apply_port_values(self):
        """Apply Output Ports values"""
        if not self.current_node:
            logger.warning("No node selected")
            return

        try:
            for i, port_widget in enumerate(self.port_widgets):
                coord_inputs = []
                for child in port_widget.findChildren(QtWidgets.QLineEdit):
                    coord_inputs.append(child)

                if len(coord_inputs) >= 3:
                    try:
                        x = float(coord_inputs[0].text())
                        y = float(coord_inputs[1].text())
                        z = float(coord_inputs[2].text())

                        if hasattr(self.current_node, 'points') and i < len(self.current_node.points):
                            self.current_node.points[i]['xyz'] = [x, y, z]
                            logger.debug(
                                f"Updated point {i+1} coordinates to: ({x:.6f}, {y:.6f}, {z:.6f})")

                            if hasattr(self.current_node, 'cumulative_coords') and i < len(self.current_node.cumulative_coords):
                                if isinstance(self.current_node, BaseLinkNode):
                                    self.current_node.cumulative_coords[i]['xyz'] = [
                                        x, y, z]
                                else:
                                    self.current_node.cumulative_coords[i]['xyz'] = [
                                        0.0, 0.0, 0.0]

                    except ValueError:
                        logger.warning(f"Invalid numerical input for point {i+1}")
                        continue

            if hasattr(self.current_node, 'graph') and self.current_node.graph:
                self.current_node.graph.recalculate_all_positions()
                logger.debug("Node positions recalculated")

            if self.stl_viewer:
                self.stl_viewer.vtkWidget.GetRenderWindow().Render()
                logger.debug("3D view updated")

        except Exception as e:
            logger.error(f"Error applying port values: {str(e)}")
            logger.error(traceback.format_exc())

    def create_port_widget(self, port_number, x=0.0, y=0.0, z=0.0):
        """Create widget for Output Port"""
        port_layout = QtWidgets.QHBoxLayout()
        port_layout.setSpacing(5)
        port_layout.setContentsMargins(0, 1, 0, 1)

        port_name = QtWidgets.QLabel(f"out_{port_number}")
        port_name.setFixedWidth(45)
        port_layout.addWidget(port_name)

        coords = []
        for label, value in [('X:', x), ('Y:', y), ('Z:', z)]:
            coord_pair = QtWidgets.QHBoxLayout()
            coord_pair.setSpacing(2)
            
            coord_label = QtWidgets.QLabel(label)
            coord_label.setFixedWidth(15)
            coord_pair.addWidget(coord_label)

            coord_input = QtWidgets.QLineEdit(f"{value:.6f}")
            coord_input.setFixedWidth(70)
            coord_input.setFixedHeight(20)
            coord_input.setStyleSheet("QLineEdit { padding-left: 2px; padding-top: 0px; padding-bottom: 0px; }")
            coord_input.setValidator(QtGui.QDoubleValidator())
            coord_input.textChanged.connect(
                lambda text, idx=port_number-1, coord=len(coords):
                self.update_port_coordinate(idx, coord, text))
            coord_pair.addWidget(coord_input)
            coords.append(coord_input)

            port_layout.addLayout(coord_pair)
            
            if label != 'Z:':
                port_layout.addSpacing(15)

        port_layout.addStretch()

        port_widget = QtWidgets.QWidget()
        port_widget.setFixedHeight(25)
        port_widget.setLayout(port_layout)
        return port_widget, coords

    def update_output_ports(self, node):
        """Update Output Ports section"""
        for widget in self.port_widgets:
            self.ports_layout.removeWidget(widget)
            widget.setParent(None)
            widget.deleteLater()
        self.port_widgets.clear()

        if hasattr(node, 'points'):
            for i, point in enumerate(node.points):
                port_widget, _ = self.create_port_widget(
                    i + 1,
                    point['xyz'][0],
                    point['xyz'][1],
                    point['xyz'][2]
                )
                self.ports_layout.addWidget(port_widget)
                self.port_widgets.append(port_widget)

    def update_massless_decoration(self, state):
        """Update Massless Decoration state"""
        if self.current_node:
            self.current_node.massless_decoration = bool(state)
            logger.debug(f"Set massless_decoration to {bool(state)} for node: {self.current_node.name()}")

    def moveEvent(self, event):
        """Handle window move event"""
        super(InspectorWindow, self).moveEvent(event)
        if hasattr(self, 'graph') and self.graph:
            self.graph.last_inspector_position = self.pos()

    def keyPressEvent(self, event):
        """Handle key press event"""
        if event.key() == QtCore.Qt.Key.Key_Escape:
            self.close()
        else:
            super(InspectorWindow, self).keyPressEvent(event)

    def start_rotation_test(self):
        """Start rotation test"""
        if self.current_node and self.stl_viewer:
            self.stl_viewer.store_current_transform(self.current_node)
            self.stl_viewer.start_rotation_test(self.current_node)

    def stop_rotation_test(self):
        """Stop rotation test"""
        if self.current_node and self.stl_viewer:
            self.stl_viewer.stop_rotation_test(self.current_node)

    def _calculate_base_inertia_tensor(self, poly_data, mass, center_of_mass, is_mirrored=False):
        """
        Common implementation for basic inertia tensor calculation.
        """
        mass_properties = vtk.vtkMassProperties()
        mass_properties.SetInputData(poly_data)
        mass_properties.Update()
        total_volume = mass_properties.GetVolume()

        density = mass / total_volume
        logger.debug(f"Calculated density: {density:.6f} from mass: {mass:.6f} and volume: {total_volume:.6f}")

        inertia_tensor = np.zeros((3, 3))
        num_cells = poly_data.GetNumberOfCells()
        logger.debug(f"Processing {num_cells} triangles for inertia tensor calculation...")

        for i in range(num_cells):
            cell = poly_data.GetCell(i)
            if cell.GetCellType() == vtk.VTK_TRIANGLE:
                points = [np.array(cell.GetPoints().GetPoint(j)) - np.array(center_of_mass) for j in range(3)]

                if is_mirrored:
                    points = [[p[0], -p[1], p[2]] for p in points]

                v1 = np.array(points[1]) - np.array(points[0])
                v2 = np.array(points[2]) - np.array(points[0])
                normal = np.cross(v1, v2)
                area = 0.5 * np.linalg.norm(normal)
                
                if area < 1e-10:
                    continue

                tri_centroid = np.mean(points, axis=0)
                
                covariance = np.zeros((3, 3))
                for p in points:
                    r_squared = np.sum(p * p)
                    for a in range(3):
                        for b in range(3):
                            if a == b:
                                covariance[a, a] += (r_squared - p[a] * p[a]) * area / 12.0
                            else:
                                covariance[a, b] -= (p[a] * p[b]) * area / 12.0

                r_squared = np.sum(tri_centroid * tri_centroid)
                parallel_axis_term = np.zeros((3, 3))
                for a in range(3):
                    for b in range(3):
                        if a == b:
                            parallel_axis_term[a, a] = r_squared * area
                        else:
                            parallel_axis_term[a, b] = tri_centroid[a] * tri_centroid[b] * area

                local_inertia = covariance + parallel_axis_term
                
                inertia_tensor += local_inertia

        inertia_tensor *= density

        threshold = 1e-10
        inertia_tensor[np.abs(inertia_tensor) < threshold] = 0.0

        inertia_tensor = 0.5 * (inertia_tensor + inertia_tensor.T)

        for i in range(3):
            if inertia_tensor[i, i] <= 0:
                logger.warning(f"Warning: Non-positive diagonal element detected at position ({i},{i})")
                inertia_tensor[i, i] = abs(inertia_tensor[i, i])

        return inertia_tensor

    def calculate_inertia_tensor(self):
        """
        Calculate inertia tensor for normal model.
        """
        if not self.current_node or not hasattr(self.current_node, 'stl_file'):
            logger.warning("No STL model is loaded.")
            return None

        try:
            if self.stl_viewer and self.current_node in self.stl_viewer.stl_actors:
                actor = self.stl_viewer.stl_actors[self.current_node]
                poly_data = actor.GetMapper().GetInput()
            else:
                logger.warning("No STL actor found for current node")
                return None

            mass_properties = vtk.vtkMassProperties()
            mass_properties.SetInputData(poly_data)
            mass_properties.Update()
            volume = mass_properties.GetVolume()
            density = float(self.density_input.text())
            mass = volume * density

            com_filter = vtk.vtkCenterOfMass()
            com_filter.SetInputData(poly_data)
            com_filter.SetUseScalarsAsWeights(False)
            com_filter.Update()
            center_of_mass = np.array(com_filter.GetCenter())

            logger.info("Calculating inertia tensor for normal model...")
            logger.debug(f"Volume: {volume:.6f}, Mass: {mass:.6f}")
            logger.debug(f"Center of Mass: {center_of_mass}")

            inertia_tensor = self._calculate_base_inertia_tensor(
                poly_data, mass, center_of_mass, is_mirrored=False)

            urdf_inertia = self.format_inertia_for_urdf(inertia_tensor)
            if hasattr(self, 'inertia_tensor_input'):
                self.inertia_tensor_input.setText(urdf_inertia)
                logger.info("Inertia tensor has been updated in UI")
            else:
                logger.warning("Warning: inertia_tensor_input not found")

            return inertia_tensor

        except Exception as e:
            logger.error(f"Error calculating inertia tensor: {str(e)}")
            logger.error(traceback.format_exc())
            return None
