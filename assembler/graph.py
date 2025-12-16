
import os
import shutil
import datetime
import traceback
import xml.etree.ElementTree as ET
from PySide6 import QtWidgets, QtCore, QtGui
from PySide6.QtCore import QPointF
from NodeGraphQt import NodeGraph

from utils.urdf_kitchen_config import AssemblerConfig as Config
from utils.urdf_kitchen_logger import setup_logger
from .nodes import BaseLinkNode, LinkNode
from .inspector import InspectorWindow

logger = setup_logger("Assembler")

class CustomNodeGraph(NodeGraph):
    """
    Main class for managing the node graph.
    
    Features:
    - Node creation, deletion, connection management
    - Mouse event handling (range selection, etc.)
    - Project save/load
    - URDF export
    - Automatic node position calculation and STL viewer integration
    """
    def __init__(self, stl_viewer):
        super(CustomNodeGraph, self).__init__()
        self.stl_viewer = stl_viewer
        self.robot_name = "robot_x"
        self.project_dir = None
        self.meshes_dir = None
        self.last_save_dir = None

        self.port_connected.connect(self.on_port_connected)
        self.port_disconnected.connect(self.on_port_disconnected)

        try:
            self.register_node(BaseLinkNode)
            logger.info(f"Registered node type: {BaseLinkNode.NODE_NAME}")

            self.register_node(LinkNode)
            logger.info(f"Registered node type: {LinkNode.NODE_NAME}")

        except Exception as e:
            logger.error(f"Error registering node types: {str(e)}")
            logger.error(traceback.format_exc())

        self._cleanup_handlers = []
        self._cached_positions = {}
        self._selection_cache = set()

        self._selection_start = None
        self._is_selecting = False

        self._view = self.widget

        self._rubber_band = QtWidgets.QRubberBand(
            QtWidgets.QRubberBand.Shape.Rectangle,
            self._view
        )

        self._original_handlers = {
            'press': self._view.mousePressEvent,
            'move': self._view.mouseMoveEvent,
            'release': self._view.mouseReleaseEvent
        }

        self._view.mousePressEvent = self.custom_mouse_press
        self._view.mouseMoveEvent = self.custom_mouse_move
        self._view.mouseReleaseEvent = self.custom_mouse_release

        self.inspector_window = InspectorWindow(stl_viewer=self.stl_viewer)

    def custom_mouse_press(self, event):
        """Custom mouse press event handler"""
        try:
            if event.button() == QtCore.Qt.MouseButton.LeftButton:
                self._selection_start = event.position().toPoint()
                self._is_selecting = True

                if self._rubber_band:
                    rect = QtCore.QRect(self._selection_start, QtCore.QSize())
                    self._rubber_band.setGeometry(rect)
                    self._rubber_band.show()

                if not event.modifiers() & QtCore.Qt.KeyboardModifier.ControlModifier:
                    for node in self.selected_nodes():
                        node.set_selected(False)

            self._original_handlers['press'](event)

        except Exception as e:
            logger.error(f"Error in mouse press: {str(e)}")

    def custom_mouse_move(self, event):
        """Custom mouse move event handler"""
        try:
            if self._is_selecting and self._selection_start:
                current_pos = event.position().toPoint()
                rect = QtCore.QRect(self._selection_start,
                                    current_pos).normalized()
                if self._rubber_band:
                    self._rubber_band.setGeometry(rect)

            self._original_handlers['move'](event)

        except Exception as e:
            logger.error(f"Error in mouse move: {str(e)}")

    def custom_mouse_release(self, event):
        """Custom mouse release event handler"""
        try:
            if event.button() == QtCore.Qt.MouseButton.LeftButton and self._is_selecting:
                if self._rubber_band and self._selection_start:
                    rect = self._rubber_band.geometry()
                    scene_rect = self._view.mapToScene(rect).boundingRect()

                    for node in self.all_nodes():
                        node_pos = node.pos()
                        if isinstance(node_pos, (list, tuple)):
                            node_point = QtCore.QPointF(
                                node_pos[0], node_pos[1])
                        else:
                            node_point = node_pos

                        if scene_rect.contains(node_point):
                            node.set_selected(True)

                    self._rubber_band.hide()

                self._selection_start = None
                self._is_selecting = False

            self._original_handlers['release'](event)

        except Exception as e:
            logger.error(f"Error in mouse release: {str(e)}")

    def cleanup(self):
        """Cleanup resources"""
        try:
            logger.info("Starting cleanup process...")
            
            if hasattr(self, '_view') and self._view:
                if hasattr(self, '_original_handlers'):
                    self._view.mousePressEvent = self._original_handlers['press']
                    self._view.mouseMoveEvent = self._original_handlers['move']
                    self._view.mouseReleaseEvent = self._original_handlers['release']
                    logger.debug("Restored original event handlers")

            try:
                if hasattr(self, '_rubber_band') and self._rubber_band and not self._rubber_band.isHidden():
                    self._rubber_band.hide()
                    self._rubber_band.setParent(None)
                    self._rubber_band.deleteLater()
                    self._rubber_band = None
                    logger.debug("Cleaned up rubber band")
            except Exception as e:
                logger.warning(f"Warning: Rubber band cleanup - {str(e)}")
                
            for node in self.all_nodes():
                try:
                    if self.stl_viewer:
                        self.stl_viewer.remove_stl_for_node(node)
                    self.remove_node(node)
                except Exception as e:
                    logger.error(f"Error cleaning up node: {str(e)}")

            if hasattr(self, 'inspector_window') and self.inspector_window:
                try:
                    self.inspector_window.close()
                    self.inspector_window.deleteLater()
                    self.inspector_window = None
                    logger.debug("Cleaned up inspector window")
                except Exception as e:
                    logger.error(f"Error cleaning up inspector window: {str(e)}")

            try:
                self._cached_positions.clear()
                self._selection_cache.clear()
                if hasattr(self, '_cleanup_handlers'):
                    self._cleanup_handlers.clear()
                logger.debug("Cleared caches")
            except Exception as e:
                logger.error(f"Error clearing caches: {str(e)}")

            logger.info("Cleanup process completed")

        except Exception as e:
            logger.error(f"Error during cleanup: {str(e)}")

    def __del__(self):
        """Destructor"""
        self.cleanup()

    def remove_node(self, node):
        """Remove node with memory leak prevention"""
        if node in self._cached_positions:
            del self._cached_positions[node]
        self._selection_cache.discard(node)

        for port in node.input_ports():
            for connected_port in port.connected_ports():
                self.disconnect_ports(port, connected_port)
        
        for port in node.output_ports():
            for connected_port in port.connected_ports():
                self.disconnect_ports(port, connected_port)

        if self.stl_viewer:
            self.stl_viewer.remove_stl_for_node(node)

        super(CustomNodeGraph, self).remove_node(node)

    def optimize_node_positions(self):
        """Optimize node position calculation"""
        for node in self.all_nodes():
            if node not in self._cached_positions:
                pos = self.calculate_node_position(node)
                self._cached_positions[node] = pos
            node.set_pos(*self._cached_positions[node])

    def setup_custom_view(self):
        """Customize view event handlers"""
        self._view.mousePressEvent_original = self._view.mousePressEvent
        self._view.mouseMoveEvent_original = self._view.mouseMoveEvent
        self._view.mouseReleaseEvent_original = self._view.mouseReleaseEvent
        
        self._view.mousePressEvent = lambda event: self._view_mouse_press(event)
        self._view.mouseMoveEvent = lambda event: self._view_mouse_move(event)
        self._view.mouseReleaseEvent = lambda event: self._view_mouse_release(event)

    def eventFilter(self, obj, event):
        """Event filter for mouse events"""
        if obj is self._view:
            if event.type() == QtCore.QEvent.Type.MouseButtonPress:
                return self._handle_mouse_press(event)
            elif event.type() == QtCore.QEvent.Type.MouseMove:
                return self._handle_mouse_move(event)
            elif event.type() == QtCore.QEvent.Type.MouseButtonRelease:
                return self._handle_mouse_release(event)
        
        return super(CustomNodeGraph, self).eventFilter(obj, event)

    def _handle_mouse_press(self, event):
        """Handle mouse press event"""
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self._selection_start = event.position().toPoint()
            self._is_selecting = True

            if self._rubber_band:
                rect = QtCore.QRect(self._selection_start, QtCore.QSize())
                self._rubber_band.setGeometry(rect)
                self._rubber_band.show()

            if not event.modifiers() & QtCore.Qt.KeyboardModifier.ControlModifier:
                for node in self.selected_nodes():
                    node.set_selected(False)

        return False

    def _handle_mouse_move(self, event):
        """Handle mouse move event"""
        if self._is_selecting and self._selection_start is not None and self._rubber_band:
            current_pos = event.position().toPoint()
            rect = QtCore.QRect(self._selection_start,
                                current_pos).normalized()
            self._rubber_band.setGeometry(rect)

        return False

    def _handle_mouse_release(self, event):
        """Handle mouse release event"""
        if (event.button() == QtCore.Qt.MouseButton.LeftButton and
                self._is_selecting and self._rubber_band):
            try:
                rect = self._rubber_band.geometry()
                scene_rect = self._view.mapToScene(rect).boundingRect()

                for node in self.all_nodes():
                    node_pos = node.pos()
                    if isinstance(node_pos, (list, tuple)):
                        node_point = QtCore.QPointF(node_pos[0], node_pos[1])
                    else:
                        node_point = node_pos

                    if scene_rect.contains(node_point):
                        node.set_selected(True)

                self._rubber_band.hide()

            except Exception as e:
                logger.error(f"Error in mouse release: {str(e)}")
            finally:
                self._selection_start = None
                self._is_selecting = False

        return False

    def _view_mouse_press(self, event):
        """View mouse press event"""
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self._selection_start = event.position().toPoint()
            self._is_selecting = True

            if self._rubber_band:
                rect = QtCore.QRect(self._selection_start, QtCore.QSize())
                self._rubber_band.setGeometry(rect)
                self._rubber_band.show()

            if not event.modifiers() & QtCore.Qt.KeyboardModifier.ControlModifier:
                for node in self.selected_nodes():
                    node.set_selected(False)

        if hasattr(self._view, 'mousePressEvent_original'):
            self._view.mousePressEvent_original(event)

    def _view_mouse_move(self, event):
        """View mouse move event"""
        if self._is_selecting and self._selection_start is not None and self._rubber_band:
            current_pos = event.position().toPoint()
            rect = QtCore.QRect(self._selection_start,
                                current_pos).normalized()
            self._rubber_band.setGeometry(rect)

        if hasattr(self._view, 'mouseMoveEvent_original'):
            self._view.mouseMoveEvent_original(event)

    def _view_mouse_release(self, event):
        """View mouse release event"""
        if (event.button() == QtCore.Qt.MouseButton.LeftButton and
                self._is_selecting and self._rubber_band):
            try:
                rect = self._rubber_band.geometry()
                scene_rect = self._view.mapToScene(rect).boundingRect()

                for node in self.all_nodes():
                    node_pos = node.pos()
                    if isinstance(node_pos, (list, tuple)):
                        node_point = QtCore.QPointF(node_pos[0], node_pos[1])
                    else:
                        node_point = node_pos

                    if scene_rect.contains(node_point):
                        node.set_selected(True)

                self._rubber_band.hide()

            except Exception as e:
                logger.error(f"Error in mouse release: {str(e)}")
            finally:
                self._selection_start = None
                self._is_selecting = False

        if hasattr(self._view, 'mouseReleaseEvent_original'):
            self._view.mouseReleaseEvent_original(event)

    def create_base_link(self):
        """Create initial base_link node"""
        try:
            node_type = f"{BaseLinkNode.__identifier__}.{BaseLinkNode.NODE_NAME}"
            base_node = self.create_node(node_type)
            base_node.set_name('base_link')
            base_node.set_pos(20, 20)
            logger.info("Base Link node created successfully")
            return base_node
        except Exception as e:
            logger.error(f"Error creating base link node: {str(e)}")
            logger.error(traceback.format_exc())
            raise

    def register_nodes(self, node_classes):
        """Register multiple node classes"""
        for node_class in node_classes:
            self.register_node(node_class)
            logger.info(f"Registered node type: {node_class.__identifier__}")

    def on_port_connected(self, input_port, output_port):
        """Handle port connection"""
        logger.debug(f"**Connecting port: {output_port.name()}")
        
        parent_node = output_port.node()
        child_node = input_port.node()
        logger.debug(f"Parent node: {parent_node.name()}, Child node: {child_node.name()}")
        
        try:
            logger.debug("Recalculating all node positions after connection...")
            self.recalculate_all_positions()
            
        except Exception as e:
            logger.error(f"Error in port connection: {str(e)}")
            logger.error(f"Detailed connection information:")
            logger.error(f"  Output port: {output_port.name()} from {parent_node.name()}")
            logger.error(f"  Input port: {input_port.name()} from {child_node.name()}")
            logger.error(traceback.format_exc())

    def on_port_disconnected(self, input_port, output_port):
        """Handle port disconnection"""
        child_node = input_port.node()
        parent_node = output_port.node()
        
        logger.debug(f"\nDisconnecting ports:")
        logger.debug(f"Parent node: {parent_node.name()}, Child node: {child_node.name()}")
        
        try:
            if hasattr(child_node, 'current_transform'):
                del child_node.current_transform
            
            self.stl_viewer.reset_stl_transform(child_node)
            logger.debug(f"Reset position for node: {child_node.name()}")

            logger.debug("Recalculating all node positions after disconnection...")
            self.recalculate_all_positions()

        except Exception as e:
            logger.error(f"Error in port disconnection: {str(e)}")
            logger.error(traceback.format_exc())

    def update_robot_name(self, text):
        """Update robot name"""
        self.robot_name = text
        logger.info(f"Robot name updated to: {text}")

        if hasattr(self, 'widget') and self.widget:
            if self.widget.window():
                title = f"URDF Kitchen - Assembler v0.0.1 - {text}"
                self.widget.window().setWindowTitle(title)

    def get_robot_name(self):
        """Get current robot name"""
        return self.robot_name

    def set_robot_name(self, name):
        """Set robot name"""
        self.robot_name = name
        if hasattr(self, 'name_input') and self.name_input:
            self.name_input.setText(name)
        logger.info(f"Robot name set to: {name}")

    def clean_robot_name(self, name):
        """Remove _description from robot name"""
        if name.endswith('_description'):
            return name[:-12]
        return name

    def update_robot_name_from_directory(self, dir_path):
        """Update robot name from directory"""
        dir_name = os.path.basename(dir_path)
        if dir_name.endswith('_description'):
            robot_name = dir_name[:-12]
            if hasattr(self, 'name_input') and self.name_input:
                self.name_input.setText(robot_name)
            self.robot_name = robot_name
            return True
        return False

    def export_urdf(self):
        """Export URDF file"""
        try:
            message_box = QtWidgets.QMessageBox()
            message_box.setIcon(QtWidgets.QMessageBox.Information)
            message_box.setWindowTitle("Select Directory")
            message_box.setText("Please select the *_description directory that will be the root of the URDF.")
            message_box.exec_()

            description_dir = QtWidgets.QFileDialog.getExistingDirectory(
                self.widget,
                "Select robot description directory (*_description)",
                os.getcwd()
            )

            if not description_dir:
                logger.info("URDF export cancelled")
                return False

            dir_name = os.path.basename(description_dir)
            robot_base_name = self.robot_name

            if dir_name.endswith('_description'):
                actual_robot_name = dir_name[:-12]
                if robot_base_name != actual_robot_name:
                    response = QtWidgets.QMessageBox.question(
                        self.widget,
                        "Robot Name Mismatch",
                        f"Directory suggests robot name '{actual_robot_name}' but current robot name is '{robot_base_name}'.\n"
                        f"Do you want to continue using current name '{robot_base_name}'?",
                        QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
                    )
                    if response == QtWidgets.QMessageBox.No:
                        return False
            else:
                response = QtWidgets.QMessageBox.question(
                    self.widget,
                    "Directory Name Format",
                    f"Selected directory does not end with '_description'.\n"
                    f"Expected format: '*_description'\n"
                    f"Do you want to continue?",
                    QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
                )
                if response == QtWidgets.QMessageBox.No:
                    return False

            if dir_name.endswith('_description'):
                self.update_robot_name_from_directory(description_dir)

            clean_name = self.clean_robot_name(self.robot_name)

            urdf_dir = os.path.join(description_dir, 'urdf')

            if not os.path.exists(urdf_dir):
                try:
                    os.makedirs(urdf_dir)
                    logger.info(f"Created URDF directory: {urdf_dir}")
                except Exception as e:
                    logger.error(f"Error creating URDF directory: {str(e)}")
                    return False

            urdf_file = os.path.join(urdf_dir, f"{clean_name}.urdf")

            with open(urdf_file, 'w', encoding='utf-8') as f:
                f.write('<?xml version="1.0"?>\n')
                f.write(f'<robot name="{clean_name}">\n\n')

                materials = {}
                for node in self.all_nodes():
                    if hasattr(node, 'node_color'):
                        rgb = node.node_color
                        if len(rgb) >= 3:
                            hex_color = '#{:02x}{:02x}{:02x}'.format(
                                int(rgb[0] * 255),
                                int(rgb[1] * 255),
                                int(rgb[2] * 255)
                            )
                            materials[hex_color] = rgb
                
                f.write('<!-- material color setting -->\n')
                for hex_color, rgb in materials.items():
                    f.write(f'<material name="{hex_color}">\n')
                    f.write(f'  <color rgba="{rgb[0]:.3f} {rgb[1]:.3f} {rgb[2]:.3f} 1.0"/>\n')
                    f.write('</material>\n')
                f.write('\n')

                visited_nodes = set()
                base_node = self.get_node_by_name('base_link')
                if base_node:
                    self._write_tree_structure(f, base_node, None, visited_nodes, materials)
                
                f.write('</robot>\n')

                logger.info(f"URDF exported to: {urdf_file}")
                
                QtWidgets.QMessageBox.information(
                    self.widget,
                    "Export Complete",
                    f"URDF file has been exported to:\n{urdf_file}"
                )
                
                return True

        except Exception as e:
            error_msg = f"Error exporting URDF: {str(e)}"
            logger.error(error_msg)
            logger.error(traceback.format_exc())
            
            QtWidgets.QMessageBox.critical(
                self.widget,
                "Export Error",
                error_msg
            )
            return False

    def _write_tree_structure(self, file, node, parent_node, visited_nodes, materials):
        """Write tree structure recursively"""
        if node in visited_nodes:
            return
        visited_nodes.add(node)

        if hasattr(node, 'massless_decoration') and node.massless_decoration:
            return

        if node.name() == "base_link":
            self._write_base_link(file)
        
        for port in node.output_ports():
            for connected_port in port.connected_ports():
                child_node = connected_port.node()
                if child_node not in visited_nodes:
                    if not (hasattr(child_node, 'massless_decoration') and child_node.massless_decoration):
                        self._write_joint(file, node, child_node)
                        file.write('\n')
                        
                        self._write_link(file, child_node, materials)
                        file.write('\n')
                    
                    self._write_tree_structure(file, child_node, node, visited_nodes, materials)

    def _write_base_link(self, file):
        """Write base_link"""
        file.write('  <link name="base_link">\n')
        file.write('    <inertial>\n')
        file.write('      <origin xyz="0 0 0" rpy="0 0 0"/>\n')
        file.write('      <mass value="0.0"/>\n')
        file.write('      <inertia ixx="0.01" ixy="0.0" ixz="0.0" iyy="0.0" iyz="0.0" izz="0.0"/>\n')
        file.write('    </inertial>\n')
        file.write('  </link>\n\n')

    def _write_urdf_node(self, file, node, parent_node, visited_nodes, materials):
        """Write node as URDF recursively"""
        if node in visited_nodes:
            return
        visited_nodes.add(node)

        is_decoration = hasattr(node, 'massless_decoration') and node.massless_decoration

        if is_decoration:
            if parent_node is not None:
                mesh_dir_name = "meshes"
                if self.meshes_dir:
                    dir_name = os.path.basename(self.meshes_dir)
                    if dir_name.startswith('mesh'):
                        mesh_dir_name = dir_name

                stl_filename = os.path.basename(node.stl_file)
                package_path = f"package://{self.robot_name}_description/{mesh_dir_name}/{stl_filename}"

                file.write(f'''
                <visual>
                    <origin xyz="{node.xyz[0]} {node.xyz[1]} {node.xyz[2]}" rpy="{node.rpy[0]} {node.rpy[1]} {node.rpy[2]}" />
                    <geometry>
                        <mesh filename="{package_path}" />
                    </geometry>
                    <material name="#2e2e2e" />
                </visual>
                ''')
            return

        file.write(f'  <link name="{node.name()}">\n')

        if hasattr(node, 'mass_value') and hasattr(node, 'inertia'):
            file.write('    <inertial>\n')
            file.write(f'      <origin xyz="0 0 0" rpy="0 0 0"/>\n')
            file.write(f'      <mass value="{node.mass_value:.6f}"/>\n')
            file.write('      <inertia')
            for key, value in node.inertia.items():
                file.write(f' {key}="{value:.6f}"')
            file.write('/>\n')
            file.write('    </inertial>\n')

        if hasattr(node, 'stl_file') and node.stl_file:
            mesh_dir_name = "meshes"
            if self.meshes_dir:
                dir_name = os.path.basename(self.meshes_dir)
                if dir_name.startswith('mesh'):
                    mesh_dir_name = dir_name

            stl_filename = os.path.basename(node.stl_file)
            package_path = f"package://{self.robot_name}_description/{mesh_dir_name}/{stl_filename}"

            file.write('    <visual>\n')
            file.write(f'      <origin xyz="0 0 0" rpy="0 0 0"/>\n')
            file.write('      <geometry>\n')
            file.write(f'        <mesh filename="{package_path}"/>\n')
            file.write('      </geometry>\n')
            file.write('    </visual>\n')

            file.write('    <collision>\n')
            file.write(f'      <origin xyz="0 0 0" rpy="0 0 0"/>\n')
            file.write('      <geometry>\n')
            file.write(f'        <mesh filename="{package_path}"/>\n')
            file.write('      </geometry>\n')
            file.write('    </collision>\n')

        file.write('  </link>\n\n')

        if parent_node and not is_decoration:
            origin_xyz = [0, 0, 0]
            for port in parent_node.output_ports():
                for connected_port in port.connected_ports():
                    if connected_port.node() == node:
                        origin_xyz = port.get_position()
                        break

            joint_name = f"{parent_node.name()}_to_{node.name()}"
            file.write(f'  <joint name="{joint_name}" type="fixed">\n')
            file.write(f'    <origin xyz="{origin_xyz[0]} {origin_xyz[1]} {origin_xyz[2]}" rpy="0.0 0.0 0.0"/>\n')
            file.write(f'    <parent link="{parent_node.name()}"/>\n')
            file.write(f'    <child link="{node.name()}"/>\n')
            file.write('  </joint>\n\n')

        for port in node.output_ports():
            for connected_port in port.connected_ports():
                child_node = connected_port.node()
                self._write_urdf_node(file, child_node, node, visited_nodes, materials)

    def generate_tree_text(self, node, level=0):
        tree_text = "  " * level + node.name() + "\n"
        for output_port in node.output_ports():
            for connected_port in output_port.connected_ports():
                child_node = connected_port.node()
                tree_text += self.generate_tree_text(child_node, level + 1)
        return tree_text

    def get_node_by_name(self, name):
        for node in self.all_nodes():
            if node.name() == name:
                return node
        return None

    def update_last_stl_directory(self, file_path):
        self.last_stl_directory = os.path.dirname(file_path)

    def show_inspector(self, node, screen_pos=None):
        """Show inspector window for node"""
        try:
            if hasattr(self, 'inspector_window') and self.inspector_window is not None:
                try:
                    self.inspector_window.close()
                    self.inspector_window.deleteLater()
                except:
                    pass
                self.inspector_window = None

            self.inspector_window = InspectorWindow(stl_viewer=self.stl_viewer)
            
            inspector_size = self.inspector_window.sizeHint()

            if self.widget and self.widget.window():
                if hasattr(self, 'last_inspector_position') and self.last_inspector_position:
                    x = self.last_inspector_position.x()
                    y = self.last_inspector_position.y()
                    
                    screen = QtWidgets.QApplication.primaryScreen()
                    screen_geo = screen.availableGeometry()
                    
                    if x < screen_geo.x() or x + inspector_size.width() > screen_geo.right() or \
                    y < screen_geo.y() or y + inspector_size.height() > screen_geo.bottom():
                        main_geo = self.widget.window().geometry()
                        x = main_geo.x() + (main_geo.width() - inspector_size.width()) // 2
                        y = main_geo.y() + 50
                else:
                    main_geo = self.widget.window().geometry()
                    x = main_geo.x() + (main_geo.width() - inspector_size.width()) // 2
                    y = main_geo.y() + 50

                self.inspector_window.setWindowTitle(f"Node Inspector - {node.name()}")
                self.inspector_window.current_node = node
                self.inspector_window.graph = self
                self.inspector_window.update_info(node)
                
                self.inspector_window.move(x, y)
                self.inspector_window.show()
                self.inspector_window.raise_()
                self.inspector_window.activateWindow()

                logger.debug(f"Inspector window displayed for node: {node.name()}")

        except Exception as e:
            logger.error(f"Error showing inspector: {str(e)}")
            logger.error(traceback.format_exc())

    def create_node(self, node_type, name=None, pos=None):
        new_node = super(CustomNodeGraph, self).create_node(node_type, name)

        if pos is None:
            pos = QPointF(0, 0)
        elif isinstance(pos, (tuple, list)):
            pos = QPointF(*pos)

        logger.debug(f"Initial position for new node: {pos}")

        adjusted_pos = self.find_non_overlapping_position(pos)
        logger.debug(f"Adjusted position for new node: {adjusted_pos}")

        new_node.set_pos(adjusted_pos.x(), adjusted_pos.y())

        return new_node

    def find_non_overlapping_position(self, pos, offset_x=50, offset_y=30, items_per_row=16):
        all_nodes = self.all_nodes()
        current_node_count = len(all_nodes)
        
        row = current_node_count // items_per_row
        position_in_row = current_node_count % items_per_row
        
        base_x = pos.x()
        base_y = pos.y() + (row * 200)
        
        new_x = base_x + (position_in_row * offset_x)
        new_y = base_y + (position_in_row * offset_y)
        
        new_pos = QPointF(new_x, new_y)
        
        logger.debug(f"Positioning node {current_node_count + 1}")
        logger.debug(f"Row: {row + 1}, Position in row: {position_in_row + 1}")
        logger.debug(f"Position: ({new_pos.x()}, {new_pos.y()})")
        
        iteration = 0
        while any(self.nodes_overlap(new_pos, node.pos()) for node in all_nodes):
            new_pos += QPointF(5, 5)
            iteration += 1
            if iteration > 10:
                break
        
        return new_pos

    def nodes_overlap(self, pos1, pos2, threshold=5):
        pos1 = self.ensure_qpointf(pos1)
        pos2 = self.ensure_qpointf(pos2)
        overlap = (abs(pos1.x() - pos2.x()) < threshold and
                abs(pos1.y() - pos2.y()) < threshold)
        if overlap:
            logger.debug(f"Overlap detected: pos1={pos1}, pos2={pos2}")
        return overlap

    def ensure_qpointf(self, pos):
        if isinstance(pos, QPointF):
            return pos
        elif isinstance(pos, (tuple, list)):
            return QPointF(*pos)
        else:
            logger.warning(f"Unsupported position type: {type(pos)}")
            return QPointF(0, 0)

    def _save_node_data(self, node, project_dir):
        """Save node data"""
        logger.debug(f"Starting _save_node_data for node: {node.name()}")
        node_elem = ET.Element("node")
        
        try:
            logger.debug(f"  Saving basic info for node: {node.name()}")
            ET.SubElement(node_elem, "id").text = hex(id(node))
            ET.SubElement(node_elem, "name").text = node.name()
            ET.SubElement(node_elem, "type").text = node.__class__.__name__

            if hasattr(node, 'output_count'):
                ET.SubElement(node_elem, "output_count").text = str(node.output_count)
                logger.debug(f"  Saved output_count: {node.output_count}")

            if hasattr(node, 'stl_file') and node.stl_file:
                logger.debug(f"  Processing STL file for node {node.name()}: {node.stl_file}")
                stl_elem = ET.SubElement(node_elem, "stl_file")
                
                try:
                    stl_path = os.path.abspath(node.stl_file)
                    logger.debug(f"    Absolute STL path: {stl_path}")

                    if self.meshes_dir and stl_path.startswith(self.meshes_dir):
                        rel_path = os.path.relpath(stl_path, self.meshes_dir)
                        stl_elem.set('base_dir', 'meshes')
                        stl_elem.text = os.path.join('meshes', rel_path)
                        logger.debug(f"    Using meshes relative path: {rel_path}")
                    else:
                        rel_path = os.path.relpath(stl_path, project_dir)
                        stl_elem.set('base_dir', 'project')
                        stl_elem.text = rel_path
                        logger.debug(f"    Using project relative path: {rel_path}")

                except Exception as e:
                    logger.error(f"    Error processing STL file: {str(e)}")
                    stl_elem.set('error', str(e))

            pos = node.pos()
            pos_elem = ET.SubElement(node_elem, "position")
            if isinstance(pos, (list, tuple)):
                ET.SubElement(pos_elem, "x").text = str(pos[0])
                ET.SubElement(pos_elem, "y").text = str(pos[1])
            else:
                ET.SubElement(pos_elem, "x").text = str(pos.x())
                ET.SubElement(pos_elem, "y").text = str(pos.y())

            if hasattr(node, 'volume_value'):
                ET.SubElement(node_elem, "volume").text = str(node.volume_value)
                logger.debug(f"  Saved volume: {node.volume_value}")

            if hasattr(node, 'mass_value'):
                ET.SubElement(node_elem, "mass").text = str(node.mass_value)
                logger.debug(f"  Saved mass: {node.mass_value}")

            if hasattr(node, 'inertia'):
                inertia_elem = ET.SubElement(node_elem, "inertia")
                for key, value in node.inertia.items():
                    inertia_elem.set(key, str(value))
                logger.debug("  Saved inertia tensor")

            if hasattr(node, 'node_color'):
                color_elem = ET.SubElement(node_elem, "color")
                color_elem.text = ' '.join(map(str, node.node_color))
                logger.debug(f"  Saved color: {node.node_color}")

            if hasattr(node, 'rotation_axis'):
                ET.SubElement(node_elem, "rotation_axis").text = str(node.rotation_axis)
                logger.debug(f"  Saved rotation axis: {node.rotation_axis}")

            if hasattr(node, 'massless_decoration'):
                ET.SubElement(node_elem, "massless_decoration").text = str(node.massless_decoration)
                logger.debug(f"  Saved massless_decoration: {node.massless_decoration}")

            if hasattr(node, 'points'):
                points_elem = ET.SubElement(node_elem, "points")
                for i, point in enumerate(node.points):
                    point_elem = ET.SubElement(points_elem, "point")
                    point_elem.set('index', str(i))
                    ET.SubElement(point_elem, "name").text = point['name']
                    ET.SubElement(point_elem, "type").text = point['type']
                    ET.SubElement(point_elem, "xyz").text = ' '.join(map(str, point['xyz']))
                logger.debug(f"  Saved {len(node.points)} points")

            if hasattr(node, 'cumulative_coords'):
                coords_elem = ET.SubElement(node_elem, "cumulative_coords")
                for coord in node.cumulative_coords:
                    coord_elem = ET.SubElement(coords_elem, "coord")
                    ET.SubElement(coord_elem, "point_index").text = str(coord['point_index'])
                    ET.SubElement(coord_elem, "xyz").text = ' '.join(map(str, coord['xyz']))
                logger.debug(f"  Saved cumulative coordinates")

            logger.debug(f"  Completed saving node data for: {node.name()}")
            return node_elem

        except Exception as e:
            logger.error(f"ERROR in _save_node_data for node {node.name()}: {str(e)}")
            logger.error(traceback.format_exc())
            raise

    def save_project(self, file_path=None):
        """Save project"""
        logger.info("=== Starting Project Save ===")
        try:
            stl_viewer_state = None
            if hasattr(self, 'stl_viewer'):
                logger.debug("Backing up STL viewer state...")
                stl_viewer_state = {
                    'actors': dict(self.stl_viewer.stl_actors),
                    'transforms': dict(self.stl_viewer.transforms)
                }
                self.stl_viewer.stl_actors.clear()
                self.stl_viewer.transforms.clear()

            if not file_path:
                default_filename = f"urdf_pj_{datetime.datetime.now().strftime('%Y%m%d%H%M')}.xml"
                default_dir = self.last_save_dir or self.meshes_dir or os.getcwd()
                file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
                    None,
                    "Save Project",
                    os.path.join(default_dir, default_filename),
                    "XML Files (*.xml)"
                )
                if not file_path:
                    logger.info("Save cancelled by user")
                    return False

            self.project_dir = os.path.dirname(os.path.abspath(file_path))
            self.last_save_dir = self.project_dir
            logger.info(f"Project will be saved to: {file_path}")

            logger.debug("Creating XML structure...")
            root = ET.Element("project")
            
            robot_name_elem = ET.SubElement(root, "robot_name")
            robot_name_elem.text = self.robot_name
            logger.debug(f"Saving robot name: {self.robot_name}")
            
            if self.meshes_dir:
                try:
                    meshes_rel_path = os.path.relpath(self.meshes_dir, self.project_dir)
                    ET.SubElement(root, "meshes_directory").text = meshes_rel_path
                    logger.debug(f"Added meshes directory reference: {meshes_rel_path}")
                except ValueError:
                    ET.SubElement(root, "meshes_directory").text = self.meshes_dir
                    logger.debug(f"Added absolute meshes path: {self.meshes_dir}")

            logger.debug("Saving nodes...")
            nodes_elem = ET.SubElement(root, "nodes")
            total_nodes = len(self.all_nodes())
            
            for i, node in enumerate(self.all_nodes(), 1):
                logger.debug(f"Processing node {i}/{total_nodes}: {node.name()}")
                stl_viewer_backup = node.stl_viewer if hasattr(node, 'stl_viewer') else None
                if hasattr(node, 'stl_viewer'):
                    delattr(node, 'stl_viewer')
                
                node_elem = self._save_node_data(node, self.project_dir)
                nodes_elem.append(node_elem)
                
                if stl_viewer_backup is not None:
                    node.stl_viewer = stl_viewer_backup

            logger.debug("Saving connections...")
            connections = ET.SubElement(root, "connections")
            connection_count = 0
            
            for node in self.all_nodes():
                for port in node.output_ports():
                    for connected_port in port.connected_ports():
                        conn = ET.SubElement(connections, "connection")
                        ET.SubElement(conn, "from_node").text = node.name()
                        ET.SubElement(conn, "from_port").text = port.name()
                        ET.SubElement(conn, "to_node").text = connected_port.node().name()
                        ET.SubElement(conn, "to_port").text = connected_port.name()
                        connection_count += 1
                        logger.debug(f"Added connection: {node.name()}.{port.name()} -> "
                            f"{connected_port.node().name()}.{connected_port.name()}")

            logger.info(f"Total connections saved: {connection_count}")

            logger.debug("Writing to file...")
            tree = ET.ElementTree(root)
            tree.write(file_path, encoding='utf-8', xml_declaration=True)

            if stl_viewer_state and hasattr(self, 'stl_viewer'):
                logger.debug("Restoring STL viewer state...")
                self.stl_viewer.stl_actors = stl_viewer_state['actors']
                self.stl_viewer.transforms = stl_viewer_state['transforms']
                self.stl_viewer.vtkWidget.GetRenderWindow().Render()

            logger.info(f"Project successfully saved to: {file_path}")
            
            QtWidgets.QMessageBox.information(
                None,
                "Save Complete",
                f"Project saved successfully to:\n{file_path}"
            )

            return True

        except Exception as e:
            error_msg = f"Error saving project: {str(e)}"
            print(f"\nERROR: {error_msg}")
            print("Traceback:")
            traceback.print_exc()
            
            if 'stl_viewer_state' in locals() and stl_viewer_state and hasattr(self, 'stl_viewer'):
                print("Restoring STL viewer state after error...")
                self.stl_viewer.stl_actors = stl_viewer_state['actors']
                self.stl_viewer.transforms = stl_viewer_state['transforms']
                self.stl_viewer.vtkWidget.GetRenderWindow().Render()
            
            QtWidgets.QMessageBox.critical(
                None,
                "Save Error",
                error_msg
            )
            return False

    def detect_meshes_directory(self):
        """Detect meshes directory"""
        for node in self.all_nodes():
            if hasattr(node, 'stl_file') and node.stl_file:
                current_dir = os.path.dirname(os.path.abspath(node.stl_file))
                while current_dir and os.path.basename(current_dir).lower() != 'meshes':
                    current_dir = os.path.dirname(current_dir)
                if current_dir and os.path.basename(current_dir).lower() == 'meshes':
                    self.meshes_dir = current_dir
                    print(f"Found meshes directory: {self.meshes_dir}")
                    return

    def load_project(self, file_path=None):
        """Load project"""
        print("\n=== Starting Project Load ===")
        try:
            if not file_path:
                file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
                    None,
                    "Load Project",
                    self.last_save_dir or "",
                    "XML Files (*.xml)"
                )
                
            if not file_path:
                print("Load cancelled by user")
                return False

            print(f"Loading project from: {file_path}")
            
            self.project_dir = os.path.dirname(os.path.abspath(file_path))
            self.last_save_dir = self.project_dir
            
            print("Parsing XML file...")
            tree = ET.parse(file_path)
            root = tree.getroot()

            robot_name_elem = root.find("robot_name")
            if robot_name_elem is not None and robot_name_elem.text:
                self.robot_name = robot_name_elem.text
                if hasattr(self, 'name_input') and self.name_input:
                    self.name_input.setText(self.robot_name)
                print(f"Loaded robot name: {self.robot_name}")
            else:
                print("No robot name found in project file")

            print("Clearing existing nodes...")
            self.clear_graph()

            print("Resolving meshes directory...")
            meshes_dir_elem = root.find("meshes_directory")
            if meshes_dir_elem is not None and meshes_dir_elem.text:
                meshes_path = os.path.normpath(os.path.join(self.project_dir, meshes_dir_elem.text))
                if os.path.exists(meshes_path):
                    self.meshes_dir = meshes_path
                    print(f"Found meshes directory: {meshes_path}")
                else:
                    response = QtWidgets.QMessageBox.question(
                        None,
                        "Meshes Directory Not Found",
                        "The original meshes directory was not found. Would you like to select it?",
                        QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
                    )
                    
                    if response == QtWidgets.QMessageBox.Yes:
                        self.meshes_dir = QtWidgets.QFileDialog.getExistingDirectory(
                            None,
                            "Select Meshes Directory",
                            self.project_dir
                        )
                        if self.meshes_dir:
                            print(f"Selected new meshes directory: {self.meshes_dir}")
                        else:
                            print("Meshes directory selection cancelled")

            print("\nRestoring nodes...")
            nodes_elem = root.find("nodes")
            total_nodes = len(nodes_elem.findall("node"))
            nodes_dict = {}
            
            for i, node_elem in enumerate(nodes_elem.findall("node"), 1):
                print(f"Processing node {i}/{total_nodes}")
                node = self._load_node_data(node_elem)
                if node:
                    nodes_dict[node.name()] = node
                    print(f"Successfully restored node: {node.name()}")

            print("\nRestoring connections...")
            connection_count = 0
            for conn in root.findall(".//connection"):
                from_node = nodes_dict.get(conn.find("from_node").text)
                to_node = nodes_dict.get(conn.find("to_node").text)
                
                if from_node and to_node:
                    from_port = from_node.get_output(conn.find("from_port").text)
                    to_port = to_node.get_input(conn.find("to_port").text)
                    
                    if from_port and to_port:
                        self.connect_ports(from_port, to_port)
                        connection_count += 1
                        print(f"Restored connection: {from_node.name()}.{from_port.name()} -> "
                            f"{to_node.name()}.{to_port.name()}")

            print(f"Total connections restored: {connection_count}")

            print("\nRecalculating positions...")
            self.recalculate_all_positions()
            
            print("Updating 3D view...")
            if self.stl_viewer:
                QtCore.QTimer.singleShot(500, lambda: self.stl_viewer.reset_view_to_fit())

            print(f"\nProject successfully loaded from: {file_path}")
            return True

        except Exception as e:
            error_msg = f"Error loading project: {str(e)}"
            print(f"\nERROR: {error_msg}")
            print("Traceback:")
            traceback.print_exc()
            
            QtWidgets.QMessageBox.critical(
                None,
                "Load Error",
                error_msg
            )
            return False

    def _load_node_data(self, node_elem):
        """Load node data"""
        try:
            node_type = node_elem.find("type").text
            
            if node_type == "BaseLinkNode":
                node = self.create_base_link()
            else:
                node = self.create_node('insilico.nodes.LinkNode')

            name_elem = node_elem.find("name")
            if name_elem is not None:
                node.set_name(name_elem.text)
                print(f"Loading node: {name_elem.text}")

            if isinstance(node, LinkNode):
                points_elem = node_elem.find("points")
                if points_elem is not None:
                    points = points_elem.findall("point")
                    num_points = len(points)
                    print(f"Found {num_points} points")
                    
                    while len(node.output_ports()) < num_points:
                        node._add_output()
                        print(f"Added output port, total now: {len(node.output_ports())}")

                    node.points = []
                    for point_elem in points:
                        point_data = {
                            'name': point_elem.find("name").text,
                            'type': point_elem.find("type").text,
                            'xyz': [float(x) for x in point_elem.find("xyz").text.split()]
                        }
                        node.points.append(point_data)
                        print(f"Restored point: {point_data}")

                    node.output_count = num_points
                    print(f"Set output_count to {num_points}")

            pos_elem = node_elem.find("position")
            if pos_elem is not None:
                x = float(pos_elem.find("x").text)
                y = float(pos_elem.find("y").text)
                node.set_pos(x, y)
                print(f"Set position: ({x}, {y})")

            volume_elem = node_elem.find("volume")
            if volume_elem is not None:
                node.volume_value = float(volume_elem.text)
                print(f"Restored volume: {node.volume_value}")

            mass_elem = node_elem.find("mass")
            if mass_elem is not None:
                node.mass_value = float(mass_elem.text)
                print(f"Restored mass: {node.mass_value}")

            inertia_elem = node_elem.find("inertia")
            if inertia_elem is not None:
                node.inertia = {
                    'ixx': float(inertia_elem.get('ixx', '0.0')),
                    'ixy': float(inertia_elem.get('ixy', '0.0')),
                    'ixz': float(inertia_elem.get('ixz', '0.0')),
                    'iyy': float(inertia_elem.get('iyy', '0.0')),
                    'iyz': float(inertia_elem.get('iyz', '0.0')),
                    'izz': float(inertia_elem.get('izz', '0.0'))
                }
                print(f"Restored inertia tensor")

            color_elem = node_elem.find("color")
            if color_elem is not None and color_elem.text:
                node.node_color = [float(x) for x in color_elem.text.split()]
                print(f"Restored color: {node.node_color}")

            rotation_axis_elem = node_elem.find("rotation_axis")
            if rotation_axis_elem is not None:
                node.rotation_axis = int(rotation_axis_elem.text)
                print(f"Restored rotation axis: {node.rotation_axis}")

            massless_dec_elem = node_elem.find("massless_decoration")
            if massless_dec_elem is not None:
                node.massless_decoration = massless_dec_elem.text.lower() == 'true'
                print(f"Restored massless_decoration: {node.massless_decoration}")

            coords_elem = node_elem.find("cumulative_coords")
            if coords_elem is not None:
                node.cumulative_coords = []
                for coord_elem in coords_elem.findall("coord"):
                    coord_data = {
                        'point_index': int(coord_elem.find("point_index").text),
                        'xyz': [float(x) for x in coord_elem.find("xyz").text.split()]
                    }
                    node.cumulative_coords.append(coord_data)
                print("Restored cumulative coordinates")

            stl_elem = node_elem.find("stl_file")
            if stl_elem is not None and stl_elem.text:
                stl_path = stl_elem.text
                base_dir = stl_elem.get('base_dir', 'project')

                if base_dir == 'meshes' and self.meshes_dir:
                    if stl_path.startswith('meshes/'):
                        stl_path = stl_path[7:]
                    abs_path = os.path.join(self.meshes_dir, stl_path)
                else:
                    abs_path = os.path.join(self.project_dir, stl_path)

                abs_path = os.path.normpath(abs_path)
                if os.path.exists(abs_path):
                    node.stl_file = abs_path
                    if self.stl_viewer:
                        print(f"Loading STL file: {abs_path}")
                        self.stl_viewer.load_stl_for_node(node)
                else:
                    print(f"Warning: STL file not found: {abs_path}")

            print(f"Node {node.name()} loaded successfully")
            return node

        except Exception as e:
            print(f"Error loading node data: {str(e)}")
            traceback.print_exc()
            return None

    def clear_graph(self):
        for node in self.all_nodes():
            self.remove_node(node)

    def connect_ports(self, from_port, to_port):
        """Connect two ports"""
        if from_port and to_port:
            try:
                if hasattr(self, 'connect_nodes'):
                    connection = self.connect_nodes(
                        from_port.node(), from_port.name(),
                        to_port.node(), to_port.name())
                elif hasattr(self, 'add_edge'):
                    connection = self.add_edge(
                        from_port.node().id, from_port.name(),
                        to_port.node().id, to_port.name())
                elif hasattr(from_port, 'connect_to'):
                    connection = from_port.connect_to(to_port)
                else:
                    raise AttributeError("No suitable connection method found")

                if connection:
                    print(
                        f"Connected {from_port.node().name()}.{from_port.name()} to {to_port.node().name()}.{to_port.name()}")
                    return True
                else:
                    print("Failed to connect ports: Connection not established")
                    return False
            except Exception as e:
                print(f"Error connecting ports: {str(e)}")
                return False
        else:
            print("Failed to connect ports: Invalid port(s)")
            return False

    def calculate_cumulative_coordinates(self, node):
        """Calculate cumulative coordinates for node"""
        if isinstance(node, BaseLinkNode):
            return [0, 0, 0]

        input_port = node.input_ports()[0]
        if not input_port.connected_ports():
            return [0, 0, 0]

        parent_port = input_port.connected_ports()[0]
        parent_node = parent_port.node()
        
        parent_coords = self.calculate_cumulative_coordinates(parent_node)
        
        port_name = parent_port.name()
        if '_' in port_name:
            port_index = int(port_name.split('_')[1]) - 1
        else:
            port_index = 0
            
        if 0 <= port_index < len(parent_node.points):
            point_xyz = parent_node.points[port_index]['xyz']
            
            return [
                parent_coords[0] + point_xyz[0],
                parent_coords[1] + point_xyz[1],
                parent_coords[2] + point_xyz[2]
            ]
        return parent_coords

    def import_xmls_from_folder(self):
        """Import all XML files from a folder"""
        message_box = QtWidgets.QMessageBox()
        message_box.setIcon(QtWidgets.QMessageBox.Information)
        message_box.setWindowTitle("Select Directory")
        message_box.setText("Please select the meshes directory.")
        message_box.exec_()

        folder_path = QtWidgets.QFileDialog.getExistingDirectory(
            None, "Select meshes Directory Containing XML Files")
        
        if not folder_path:
            return

        print(f"Importing XMLs from folder: {folder_path}")

        try:
            parent_dir = os.path.dirname(folder_path)
            robot_name = os.path.basename(parent_dir)

            if robot_name.endswith('_description'):
                robot_name = robot_name[:-12]
                print(f"Removed '_description' suffix from robot name")

            self.robot_name = robot_name
            if hasattr(self, 'name_input') and self.name_input:
                self.name_input.setText(robot_name)
            print(f"Set robot name to: {robot_name}")
        except Exception as e:
            print(f"Error extracting robot name: {str(e)}")
        
        xml_files = [f for f in os.listdir(folder_path) if f.endswith('.xml')]
        
        if not xml_files:
            print("No XML files found in the selected folder")
            return
        
        print(f"Found {len(xml_files)} XML files")

        for xml_file in xml_files:
            try:
                xml_path = os.path.join(folder_path, xml_file)
                stl_path = os.path.join(folder_path, xml_file[:-4] + '.stl')
                
                print(f"\nProcessing: {xml_file}")
                
                new_node = self.create_node(
                    'insilico.nodes.LinkNode',
                    name=f'Node_{len(self.all_nodes())}',
                    pos=QtCore.QPointF(0, 0)
                )
                
                tree = ET.parse(xml_path)
                root = tree.getroot()

                if root.tag != 'urdf_part':
                    print(f"Warning: Invalid XML format in {xml_file}")
                    continue

                link_elem = root.find('link')
                if link_elem is not None:
                    link_name = link_elem.get('name')
                    if link_name:
                        new_node.set_name(link_name)
                        print(f"Set link name: {link_name}")

                    inertial_elem = link_elem.find('inertial')
                    if inertial_elem is not None:
                        mass_elem = inertial_elem.find('mass')
                        if mass_elem is not None:
                            new_node.mass_value = float(mass_elem.get('value', '0.0'))
                            print(f"Set mass: {new_node.mass_value}")

                        volume_elem = inertial_elem.find('volume')
                        if volume_elem is not None:
                            new_node.volume_value = float(volume_elem.get('value', '0.0'))
                            print(f"Set volume: {new_node.volume_value}")

                        inertia_elem = inertial_elem.find('inertia')
                        if inertia_elem is not None:
                            new_node.inertia = {
                                'ixx': float(inertia_elem.get('ixx', '0.0')),
                                'ixy': float(inertia_elem.get('ixy', '0.0')),
                                'ixz': float(inertia_elem.get('ixz', '0.0')),
                                'iyy': float(inertia_elem.get('iyy', '0.0')),
                                'iyz': float(inertia_elem.get('iyz', '0.0')),
                                'izz': float(inertia_elem.get('izz', '0.0'))
                            }
                            print("Set inertia tensor")

                        com_elem = link_elem.find('center_of_mass')
                        if com_elem is not None and com_elem.text:
                            com_values = [float(x) for x in com_elem.text.split()]
                            if len(com_values) == 3:
                                new_node.center_of_mass = com_values
                                print(f"Set center of mass: {com_values}")

                material_elem = root.find('.//material/color')
                if material_elem is not None:
                    rgba = material_elem.get('rgba', '1.0 1.0 1.0 1.0').split()
                    new_node.node_color = [float(x) for x in rgba[:3]]
                    print(f"Set color: RGB({new_node.node_color})")
                else:
                    new_node.node_color = [1.0, 1.0, 1.0]
                    print("Using default color: white")

                joint_elem = root.find('.//joint')
                if joint_elem is not None:
                    joint_type = joint_elem.get('type', '')
                    if joint_type == 'fixed':
                        new_node.rotation_axis = 3
                        print("Set rotation axis to Fixed")
                    else:
                        axis_elem = joint_elem.find('axis')
                        if axis_elem is not None:
                            axis_xyz = axis_elem.get('xyz', '1 0 0').split()
                            axis_values = [float(x) for x in axis_xyz]
                            if axis_values[2] == 1:
                                new_node.rotation_axis = 2
                                print("Set rotation axis to Z")
                            elif axis_values[1] == 1:
                                new_node.rotation_axis = 1
                                print("Set rotation axis to Y")
                            else:
                                new_node.rotation_axis = 0
                                print("Set rotation axis to X")
                else:
                    new_node.rotation_axis = 0
                    print("Using default rotation axis: X")

                point_elements = root.findall('point')
                
                additional_ports_needed = len(point_elements) - 1
                for _ in range(additional_ports_needed):
                    new_node._add_output()

                new_node.points = []
                new_node.cumulative_coords = []
                
                for point_elem in point_elements:
                    point_name = point_elem.get('name')
                    point_type = point_elem.get('type')
                    point_xyz_elem = point_elem.find('point_xyz')
                    
                    if point_xyz_elem is not None and point_xyz_elem.text:
                        xyz_values = [float(x) for x in point_xyz_elem.text.strip().split()]
                        new_node.points.append({
                            'name': point_name,
                            'type': point_type,
                            'xyz': xyz_values
                        })
                        new_node.cumulative_coords.append({
                            'point_index': len(new_node.points) - 1,
                            'xyz': [0.0, 0.0, 0.0]
                        })
                        print(f"Added point: {point_name} at {xyz_values}")

                if os.path.exists(stl_path):
                    print(f"Loading corresponding STL file: {stl_path}")
                    new_node.stl_file = stl_path
                    if self.stl_viewer:
                        self.stl_viewer.load_stl_for_node(new_node)
                        if hasattr(new_node, 'node_color'):
                            self.stl_viewer.apply_color_to_node(new_node)
                else:
                    print(f"Warning: STL file not found: {stl_path}")

                print(f"Successfully imported: {xml_file}")

            except Exception as e:
                print(f"Error processing {xml_file}: {str(e)}")
                traceback.print_exc()
                continue

        print("\nImport process completed")

    def recalculate_all_positions(self):
        """Recalculate all node positions"""
        logger.debug("Starting position recalculation for all nodes...")
        
        try:
            base_node = None
            for node in self.all_nodes():
                if isinstance(node, BaseLinkNode):
                    base_node = node
                    break
            
            if not base_node:
                logger.error("Base link node not found")
                return
            
            visited_nodes = set()
            logger.debug(f"Starting from base node: {base_node.name()}")
            self._recalculate_node_positions(base_node, [0, 0, 0], visited_nodes)
            
            if hasattr(self, 'stl_viewer'):
                self.stl_viewer.vtkWidget.GetRenderWindow().Render()
            
            logger.debug("Position recalculation completed")

        except Exception as e:
            logger.error(f"Error during position recalculation: {str(e)}")
            logger.error(traceback.format_exc())

    def _recalculate_node_positions(self, node, parent_coords, visited):
        """Recalculate node positions recursively"""
        if node in visited:
            return
        visited.add(node)
        
        logger.debug(f"Processing node: {node.name()}")
        logger.debug(f"Parent coordinates: {parent_coords}")
        
        try:
            for port_idx, output_port in enumerate(node.output_ports()):
                for connected_port in output_port.connected_ports():
                    child_node = connected_port.node()
                    
                    if hasattr(node, 'points') and port_idx < len(node.points):
                        point_data = node.points[port_idx]
                        point_xyz = point_data['xyz']
                        
                        new_position = [
                            parent_coords[0] + point_xyz[0],
                            parent_coords[1] + point_xyz[1],
                            parent_coords[2] + point_xyz[2]
                        ]
                        
                        logger.debug(f"Child node: {child_node.name()}")
                        logger.debug(f"Point data: {point_xyz}")
                        logger.debug(f"Calculated position: {new_position}")
                        
                        self.stl_viewer.update_stl_transform(child_node, new_position)
                        
                        if hasattr(child_node, 'cumulative_coords'):
                            for coord in child_node.cumulative_coords:
                                coord['xyz'] = new_position.copy()
                        
                        self._recalculate_node_positions(child_node, new_position, visited)
                    else:
                        print(f"Warning: No point data found for port {port_idx} in node {node.name()}")

        except Exception as e:
            print(f"Error processing node {node.name()}: {str(e)}")
            traceback.print_exc()

    def disconnect_ports(self, from_port, to_port):
        """Disconnect ports"""
        try:
            print(f"Disconnecting ports: {from_port.node().name()}.{from_port.name()} -> {to_port.node().name()}.{to_port.name()}")
            
            child_node = to_port.node()
            if child_node:
                self.stl_viewer.reset_stl_transform(child_node)
            
            if hasattr(self, 'disconnect_nodes'):
                success = self.disconnect_nodes(
                    from_port.node(), from_port.name(),
                    to_port.node(), to_port.name())
            elif hasattr(from_port, 'disconnect_from'):
                success = from_port.disconnect_from(to_port)
            else:
                success = False
                print("No suitable disconnection method found")
                
            if success:
                print("Ports disconnected successfully")
                self.on_port_disconnected(to_port, from_port)
                return True
            else:
                print("Failed to disconnect ports")
                return False
                
        except Exception as e:
            print(f"Error disconnecting ports: {str(e)}")
            return False

    def _write_joint(self, file, parent_node, child_node):
        """Write joint"""
        try:
            origin_xyz = [0, 0, 0]
            for port in parent_node.output_ports():
                for connected_port in port.connected_ports():
                    if connected_port.node() == child_node:
                        try:
                            port_name = port.name()
                            if '_' in port_name:
                                parts = port_name.split('_')
                                if len(parts) > 1 and parts[1].isdigit():
                                    port_idx = int(parts[1]) - 1
                                    if port_idx < len(parent_node.points):
                                        origin_xyz = parent_node.points[port_idx]['xyz']
                        except Exception as e:
                            print(f"Warning: Error processing port {port.name()}: {str(e)}")
                        break

            joint_name = f"{parent_node.name()}_to_{child_node.name()}"
            
            if hasattr(child_node, 'rotation_axis'):
                if child_node.rotation_axis == 3:
                    file.write(f'  <joint name="{joint_name}" type="fixed">\n')
                    file.write(f'    <origin xyz="{origin_xyz[0]} {origin_xyz[1]} {origin_xyz[2]}" rpy="0.0 0.0 0.0"/>\n')
                    file.write(f'    <parent link="{parent_node.name()}"/>\n')
                    file.write(f'    <child link="{child_node.name()}"/>\n')
                    file.write('  </joint>\n')
                else:
                    file.write(f'  <joint name="{joint_name}" type="revolute">\n')
                    axis = [0, 0, 0]
                    if child_node.rotation_axis == 0:
                        axis = [1, 0, 0]
                    elif child_node.rotation_axis == 1:
                        axis = [0, 1, 0]
                    else:
                        axis = [0, 0, 1]
                    
                    file.write(f'    <origin xyz="{origin_xyz[0]} {origin_xyz[1]} {origin_xyz[2]}" rpy="0.0 0.0 0.0"/>\n')
                    file.write(f'    <axis xyz="{axis[0]} {axis[1]} {axis[2]}"/>\n')
                    file.write(f'    <parent link="{parent_node.name()}"/>\n')
                    file.write(f'    <child link="{child_node.name()}"/>\n')
                    file.write('    <limit lower="-3.14159" upper="3.14159" effort="0" velocity="0"/>\n')
                    file.write('  </joint>\n')

        except Exception as e:
            print(f"Error writing joint: {str(e)}")
            traceback.print_exc()

    def _write_link(self, file, node, materials):
        """Write link"""
        try:
            file.write(f'  <link name="{node.name()}">\n')
            
            if hasattr(node, 'mass_value') and hasattr(node, 'inertia'):
                file.write('    <inertial>\n')
                file.write('      <origin xyz="0 0 0" rpy="0 0 0"/>\n')
                file.write(f'      <mass value="{node.mass_value:.6f}"/>\n')
                file.write('      <inertia')
                for key, value in node.inertia.items():
                    file.write(f' {key}="{value:.6f}"')
                file.write('/>\n')
                file.write('    </inertial>\n')

            if hasattr(node, 'stl_file') and node.stl_file:
                try:
                    mesh_dir_name = "meshes"
                    if self.meshes_dir:
                        dir_name = os.path.basename(self.meshes_dir)
                        if dir_name.startswith('mesh'):
                            mesh_dir_name = dir_name

                    stl_filename = os.path.basename(node.stl_file)
                    package_path = f"package://{self.robot_name}_description/{mesh_dir_name}/{stl_filename}"

                    file.write('    <visual>\n')
                    file.write('      <origin xyz="0 0 0" rpy="0 0 0"/>\n')
                    file.write('      <geometry>\n')
                    file.write(f'        <mesh filename="{package_path}"/>\n')
                    file.write('      </geometry>\n')
                    if hasattr(node, 'node_color'):
                        hex_color = '#{:02x}{:02x}{:02x}'.format(
                            int(node.node_color[0] * 255),
                            int(node.node_color[1] * 255),
                            int(node.node_color[2] * 255)
                        )
                        file.write(f'      <material name="{hex_color}"/>\n')
                    file.write('    </visual>\n')

                    for port in node.output_ports():
                        for connected_port in port.connected_ports():
                            dec_node = connected_port.node()
                            if hasattr(dec_node, 'massless_decoration') and dec_node.massless_decoration:
                                if hasattr(dec_node, 'stl_file') and dec_node.stl_file:
                                    dec_stl = os.path.basename(dec_node.stl_file)
                                    dec_path = f"package://{self.robot_name}_description/{mesh_dir_name}/{dec_stl}"
                                    
                                    file.write('    <visual>\n')
                                    file.write('      <origin xyz="0 0 0" rpy="0 0 0"/>\n')
                                    file.write('      <geometry>\n')
                                    file.write(f'        <mesh filename="{dec_path}"/>\n')
                                    file.write('      </geometry>\n')
                                    if hasattr(dec_node, 'node_color'):
                                        dec_color = '#{:02x}{:02x}{:02x}'.format(
                                            int(dec_node.node_color[0] * 255),
                                            int(dec_node.node_color[1] * 255),
                                            int(dec_node.node_color[2] * 255)
                                        )
                                        file.write(f'      <material name="{dec_color}"/>\n')
                                    file.write('    </visual>\n')

                    file.write('    <collision>\n')
                    file.write('      <origin xyz="0 0 0" rpy="0 0 0"/>\n')
                    file.write('      <geometry>\n')
                    file.write(f'        <mesh filename="{package_path}"/>\n')
                    file.write('      </geometry>\n')
                    file.write('    </collision>\n')

                except Exception as e:
                    print(f"Error processing STL file for node {node.name()}: {str(e)}")
                    traceback.print_exc()

            file.write('  </link>\n')

        except Exception as e:
            print(f"Error writing link: {str(e)}")
            traceback.print_exc()

    def export_for_unity(self):
        """Export for Unity"""
        try:
            message_box = QtWidgets.QMessageBox()
            message_box.setIcon(QtWidgets.QMessageBox.Information)
            message_box.setWindowTitle("Select Directory")
            message_box.setText("Please select the directory where you want to create the Unity project structure.")
            message_box.exec_()

            base_dir = QtWidgets.QFileDialog.getExistingDirectory(
                self.widget,
                "Select Base Directory for Unity Export"
            )

            if not base_dir:
                print("Unity export cancelled")
                return False

            robot_name = self.get_robot_name()
            unity_dir_name = f"{robot_name}_unity_description"
            unity_dir_path = os.path.join(base_dir, unity_dir_name)

            os.makedirs(unity_dir_path, exist_ok=True)
            print(f"Created Unity description directory: {unity_dir_path}")

            meshes_dir = os.path.join(unity_dir_path, "meshes")
            os.makedirs(meshes_dir, exist_ok=True)
            print(f"Created meshes directory: {meshes_dir}")

            copied_files = []
            for node in self.all_nodes():
                if hasattr(node, 'stl_file') and node.stl_file:
                    if os.path.exists(node.stl_file):
                        stl_filename = os.path.basename(node.stl_file)
                        dest_path = os.path.join(meshes_dir, stl_filename)
                        shutil.copy2(node.stl_file, dest_path)
                        copied_files.append(stl_filename)
                        print(f"Copied STL file: {stl_filename}")

            urdf_file = os.path.join(unity_dir_path, f"{robot_name}.urdf")
            with open(urdf_file, 'w', encoding='utf-8') as f:
                f.write('<?xml version="1.0"?>\n')
                f.write(f'<robot name="{robot_name}">\n\n')

                materials = {}
                for node in self.all_nodes():
                    if hasattr(node, 'node_color'):
                        rgb = node.node_color
                        if len(rgb) >= 3:
                            hex_color = '#{:02x}{:02x}{:02x}'.format(
                                int(rgb[0] * 255),
                                int(rgb[1] * 255),
                                int(rgb[2] * 255)
                            )
                            materials[hex_color] = rgb

                f.write('<!-- material color setting -->\n')
                for hex_color, rgb in materials.items():
                    f.write(f'<material name="{hex_color}">\n')
                    f.write(f'  <color rgba="{rgb[0]:.3f} {rgb[1]:.3f} {rgb[2]:.3f} 1.0"/>\n')
                    f.write('</material>\n')
                f.write('\n')

                visited_nodes = set()
                base_node = self.get_node_by_name('base_link')
                if base_node:
                    self._write_tree_structure_unity(f, base_node, None, visited_nodes, materials, unity_dir_name)

                f.write('</robot>\n')

            print(f"Unity export completed successfully:")
            print(f"- Directory: {unity_dir_path}")
            print(f"- URDF file: {urdf_file}")
            print(f"- Copied {len(copied_files)} STL files")

            QtWidgets.QMessageBox.information(
                self.widget,
                "Unity Export Complete",
                f"URDF files have been exported for Unity URDF-Importer:\n\n"
                f"Directory Path:\n{unity_dir_path}\n\n"
                f"URDF File:\n{urdf_file}\n\n"
                f"The files are ready to be imported using Unity URDF-Importer."
            )

            return True

        except Exception as e:
            error_msg = f"Error exporting for Unity: {str(e)}"
            print(error_msg)
            traceback.print_exc()
            
            QtWidgets.QMessageBox.critical(
                self.widget,
                "Export Error",
                error_msg
            )
            return False

    def _write_tree_structure_unity(self, file, node, parent_node, visited_nodes, materials, unity_dir_name):
        """Write tree structure for Unity"""
        if node in visited_nodes:
            return
        visited_nodes.add(node)

        if hasattr(node, 'massless_decoration') and node.massless_decoration:
            return

        if node.name() == "base_link":
            self._write_base_link(file)
        
        for port in node.output_ports():
            for connected_port in port.connected_ports():
                child_node = connected_port.node()
                if child_node not in visited_nodes:
                    if not (hasattr(child_node, 'massless_decoration') and child_node.massless_decoration):
                        self._write_joint(file, node, child_node)
                        file.write('\n')
                        
                        self._write_link_unity(file, child_node, materials, unity_dir_name)
                        file.write('\n')
                        
                        self._write_tree_structure_unity(file, child_node, node, visited_nodes, materials, unity_dir_name)

    def _write_link_unity(self, file, node, materials, unity_dir_name):
        """Write link for Unity"""
        try:
            file.write(f'  <link name="{node.name()}">\n')
            
            if hasattr(node, 'mass_value') and hasattr(node, 'inertia'):
                file.write('    <inertial>\n')
                file.write('      <origin xyz="0 0 0" rpy="0 0 0"/>\n')
                file.write(f'      <mass value="{node.mass_value:.6f}"/>\n')
                file.write('      <inertia')
                for key, value in node.inertia.items():
                    file.write(f' {key}="{value:.6f}"')
                file.write('/>\n')
                file.write('    </inertial>\n')

            if hasattr(node, 'stl_file') and node.stl_file:
                try:
                    stl_filename = os.path.basename(node.stl_file)
                    package_path = f"package://meshes/{stl_filename}"

                    file.write('    <visual>\n')
                    file.write('      <origin xyz="0 0 0" rpy="0 0 0"/>\n')
                    file.write('      <geometry>\n')
                    file.write(f'        <mesh filename="{package_path}"/>\n')
                    file.write('      </geometry>\n')
                    if hasattr(node, 'node_color'):
                        hex_color = '#{:02x}{:02x}{:02x}'.format(
                            int(node.node_color[0] * 255),
                            int(node.node_color[1] * 255),
                            int(node.node_color[2] * 255)
                        )
                        file.write(f'      <material name="{hex_color}"/>\n')
                    file.write('    </visual>\n')

                    for port in node.output_ports():
                        for connected_port in port.connected_ports():
                            dec_node = connected_port.node()
                            if hasattr(dec_node, 'massless_decoration') and dec_node.massless_decoration:
                                if hasattr(dec_node, 'stl_file') and dec_node.stl_file:
                                    dec_stl = os.path.basename(dec_node.stl_file)
                                    dec_path = f"package://meshes/{dec_stl}"
                                    
                                    file.write('    <visual>\n')
                                    file.write('      <origin xyz="0 0 0" rpy="0 0 0"/>\n')
                                    file.write('      <geometry>\n')
                                    file.write(f'        <mesh filename="{dec_path}"/>\n')
                                    file.write('      </geometry>\n')
                                    if hasattr(dec_node, 'node_color'):
                                        dec_color = '#{:02x}{:02x}{:02x}'.format(
                                            int(dec_node.node_color[0] * 255),
                                            int(dec_node.node_color[1] * 255),
                                            int(dec_node.node_color[2] * 255)
                                        )
                                        file.write(f'      <material name="{dec_color}"/>\n')
                                    file.write('    </visual>\n')

                    file.write('    <collision>\n')
                    file.write('      <origin xyz="0 0 0" rpy="0 0 0"/>\n')
                    file.write('      <geometry>\n')
                    file.write(f'        <mesh filename="{package_path}"/>\n')
                    file.write('      </geometry>\n')
                    file.write('    </collision>\n')

                except Exception as e:
                    print(f"Error processing STL file for node {node.name()}: {str(e)}")
                    traceback.print_exc()

            file.write('  </link>\n')

        except Exception as e:
            print(f"Error writing link: {str(e)}")
            traceback.print_exc()

    def calculate_inertia_tensor_for_mirrored(self, poly_data, mass, center_of_mass):
        """Calculate inertia tensor for mirrored model"""
        try:
            print("\nCalculating inertia tensor for mirrored model...")
            print(f"Mass: {mass:.6f}")
            print(f"Center of Mass (before mirroring): {center_of_mass}")

            mirrored_com = [center_of_mass[0], -center_of_mass[1], center_of_mass[2]]
            print(f"Center of Mass (after mirroring): {mirrored_com}")

            if not hasattr(self, 'inspector_window') or not self.inspector_window:
                self.inspector_window = InspectorWindow(stl_viewer=self.stl_viewer)

            inertia_tensor = self.inspector_window._calculate_base_inertia_tensor(
                poly_data, mass, mirrored_com, is_mirrored=True)

            print("\nMirrored model inertia tensor calculated successfully")
            return inertia_tensor

        except Exception as e:
            print(f"Error calculating mirrored inertia tensor: {str(e)}")
            traceback.print_exc()
            return None
