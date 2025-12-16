
import traceback
import vtk
from PySide6 import QtWidgets, QtCore, QtGui
from vtk.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor

from utils.urdf_kitchen_logger import setup_logger
from .nodes import BaseLinkNode

logger = setup_logger("Assembler")

class STLViewerWidget(QtWidgets.QWidget):
    """
    Widget for displaying and manipulating STL models.
    Uses VTK for 3D rendering.
    """

    def __init__(self, parent=None):
        super(STLViewerWidget, self).__init__(parent)
        self.stl_actors = {}
        self.transforms = {}
        self.base_connected_node = None
        self.text_actors = []

        layout = QtWidgets.QVBoxLayout(self)
        self.vtkWidget = QVTKRenderWindowInteractor(self)
        layout.addWidget(self.vtkWidget)

        self.renderer = vtk.vtkRenderer()
        self.vtkWidget.GetRenderWindow().AddRenderer(self.renderer)
        self.iren = self.vtkWidget.GetRenderWindow().GetInteractor()

        style = vtk.vtkInteractorStyleTrackballCamera()
        self.iren.SetInteractorStyle(style)

        button_layout = QtWidgets.QVBoxLayout()

        self.reset_button = QtWidgets.QPushButton("Reset Angle")
        self.reset_button.clicked.connect(self.reset_camera)
        button_layout.addWidget(self.reset_button)

        bg_layout = QtWidgets.QHBoxLayout()
        bg_label = QtWidgets.QLabel("background-color:")
        bg_layout.addWidget(bg_label)

        self.bg_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.bg_slider.setMinimum(-100)
        self.bg_slider.setMaximum(100)
        self.bg_slider.setValue(-80)
        self.bg_slider.valueChanged.connect(self.update_background)
        bg_layout.addWidget(self.bg_slider)

        button_layout.addLayout(bg_layout)
        layout.addLayout(button_layout)

        self.setup_camera()
        self.coordinate_axes_actor = self.create_coordinate_axes()
        self.renderer.AddActor(self.coordinate_axes_actor)

        self.rotation_timer = QtCore.QTimer()
        self.rotation_timer.timeout.connect(self.update_rotation)
        self.rotating_node = None
        self.original_transforms = {}
        self.current_angle = 0

        light1 = vtk.vtkLight()
        light1.SetPosition(0.5, 0.5, 1.0)
        light1.SetIntensity(0.7)
        light1.SetLightTypeToSceneLight()
        
        light2 = vtk.vtkLight()
        light2.SetPosition(-1.0, -0.5, 0.2)
        light2.SetIntensity(0.7)
        light2.SetLightTypeToSceneLight()
        
        light3 = vtk.vtkLight()
        light3.SetPosition(0.3, -1.0, 0.2)
        light3.SetIntensity(0.7)
        light3.SetLightTypeToSceneLight()

        light4 = vtk.vtkLight()
        light4.SetPosition(1.0, 0.0, 0.3)
        light4.SetIntensity(0.3)
        light4.SetLightTypeToSceneLight()

        self.renderer.SetAmbient(0.7, 0.7, 0.7)
        self.renderer.LightFollowCameraOff()
        self.renderer.AddLight(light1)
        self.renderer.AddLight(light2)
        self.renderer.AddLight(light3)
        self.renderer.AddLight(light4)

        initial_bg = (-80 + 100) / 200.0
        self.renderer.SetBackground(initial_bg, initial_bg, initial_bg)
        
        self.iren.Initialize()

    def store_current_transform(self, node):
        """Store current transform"""
        if node in self.transforms:
            current_transform = vtk.vtkTransform()
            current_transform.DeepCopy(self.transforms[node])
            self.original_transforms[node] = current_transform

    def start_rotation_test(self, node):
        """Start rotation test"""
        if node in self.stl_actors:
            self.rotating_node = node
            self.current_angle = 0
            self.rotation_timer.start(16)

    def stop_rotation_test(self, node):
        """Stop rotation test"""
        self.rotation_timer.stop()
        
        if self.rotating_node in self.stl_actors:
            if hasattr(self.rotating_node, 'node_color'):
                self.stl_actors[self.rotating_node].GetProperty().SetColor(*self.rotating_node.node_color)
            
            if self.rotating_node in self.original_transforms:
                self.transforms[self.rotating_node].DeepCopy(self.original_transforms[self.rotating_node])
                self.stl_actors[self.rotating_node].SetUserTransform(self.transforms[self.rotating_node])
                del self.original_transforms[self.rotating_node]
            
            self.vtkWidget.GetRenderWindow().Render()
        
        self.rotating_node = None

    def update_rotation(self):
        """Update rotation"""
        if self.rotating_node and self.rotating_node in self.stl_actors:
            node = self.rotating_node
            transform = self.transforms[node]
            
            position = transform.GetPosition()
            
            is_fixed = hasattr(node, 'rotation_axis') and node.rotation_axis == 3
            
            if is_fixed:
                is_red = (self.current_angle // 24) % 2 == 0
                if is_red:
                    self.stl_actors[node].GetProperty().SetColor(1.0, 0.0, 0.0)
                else:
                    self.stl_actors[node].GetProperty().SetColor(1.0, 1.0, 1.0)
            else:
                transform.Identity()
                transform.Translate(position)
                
                self.current_angle += 5
                if hasattr(node, 'rotation_axis'):
                    if node.rotation_axis == 0:
                        transform.RotateX(self.current_angle)
                    elif node.rotation_axis == 1:
                        transform.RotateY(self.current_angle)
                    elif node.rotation_axis == 2:
                        transform.RotateZ(self.current_angle)
                
                self.stl_actors[node].SetUserTransform(transform)
                
            self.vtkWidget.GetRenderWindow().Render()
            self.current_angle += 1

    def reset_camera(self):
        """Reset camera view to fit all STL models"""
        if not self.renderer.GetActors().GetNumberOfItems():
            self.setup_camera()
            return

        bounds = [float('inf'), float('-inf'), 
                float('inf'), float('-inf'), 
                float('inf'), float('-inf')]
        
        actors = self.renderer.GetActors()
        actors.InitTraversal()
        actor = actors.GetNextActor()
        while actor:
            actor_bounds = actor.GetBounds()
            bounds[0] = min(bounds[0], actor_bounds[0])
            bounds[1] = max(bounds[1], actor_bounds[1])
            bounds[2] = min(bounds[2], actor_bounds[2])
            bounds[3] = max(bounds[3], actor_bounds[3])
            bounds[4] = min(bounds[4], actor_bounds[4])
            bounds[5] = max(bounds[5], actor_bounds[5])
            actor = actors.GetNextActor()

        center = [(bounds[1] + bounds[0]) / 2,
                (bounds[3] + bounds[2]) / 2,
                (bounds[5] + bounds[4]) / 2]

        diagonal = ((bounds[1] - bounds[0]) ** 2 +
                (bounds[3] - bounds[2]) ** 2 +
                (bounds[5] - bounds[4]) ** 2) ** 0.5

        camera = self.renderer.GetActiveCamera()
        camera.ParallelProjectionOn()
        
        distance = diagonal
        camera.SetPosition(center[0] + distance, center[1], center[2])
        camera.SetFocalPoint(center[0], center[1], center[2])
        camera.SetViewUp(0, 0, 1)
        
        camera.SetParallelScale(diagonal * 0.5)

        self.renderer.ResetCameraClippingRange()
        self.vtkWidget.GetRenderWindow().Render()

        logger.info("Camera reset complete - All STL models fitted to view")

    def reset_view_to_fit(self):
        """Reset view to fit all STL models"""
        self.reset_camera()
        self.vtkWidget.GetRenderWindow().Render()

    def create_coordinate_axes(self):
        """Create coordinate axes"""
        base_assembly = vtk.vtkAssembly()
        length = 0.1
        text_offset = 0.02
        
        for i, (color, _) in enumerate([
            ((1,0,0), "X"),
            ((0,1,0), "Y"),
            ((0,0,1), "Z")
        ]):
            line = vtk.vtkLineSource()
            line.SetPoint1(0, 0, 0)
            end_point = [0, 0, 0]
            end_point[i] = length
            line.SetPoint2(*end_point)
            
            mapper = vtk.vtkPolyDataMapper()
            mapper.SetInputConnection(line.GetOutputPort())
            
            actor = vtk.vtkActor()
            actor.SetMapper(mapper)
            actor.GetProperty().SetColor(*color)
            actor.GetProperty().SetLineWidth(2)
            
            base_assembly.AddPart(actor)

        for i, (color, label) in enumerate([
            ((1,0,0), "X"),
            ((0,1,0), "Y"),
            ((0,0,1), "Z")
        ]):
            text_position = [0, 0, 0]
            text_position[i] = length + text_offset
            
            text_actor = vtk.vtkBillboardTextActor3D()
            text_actor.SetInput(label)
            text_actor.SetPosition(*text_position)
            text_actor.GetTextProperty().SetColor(*color)
            text_actor.GetTextProperty().SetFontSize(12)
            text_actor.GetTextProperty().SetJustificationToCentered()
            text_actor.GetTextProperty().SetVerticalJustificationToCentered()
            text_actor.SetScale(0.02)
            
            self.renderer.AddActor(text_actor)
            if not hasattr(self, 'text_actors'):
                self.text_actors = []
            self.text_actors.append(text_actor)
        
        return base_assembly

    def update_coordinate_axes(self, position):
        """Update coordinate axes position"""
        transform = vtk.vtkTransform()
        transform.Identity()
        transform.Translate(position[0], position[1], position[2])
        self.coordinate_axes_actor.SetUserTransform(transform)
        
        if hasattr(self, 'text_actors'):
            for i, text_actor in enumerate(self.text_actors):
                original_pos = list(text_actor.GetPosition())
                text_actor.SetPosition(
                    original_pos[0] + position[0],
                    original_pos[1] + position[1],
                    original_pos[2] + position[2]
                )
        
        self.vtkWidget.GetRenderWindow().Render()

    def update_stl_transform(self, node, point_xyz):
        """Update STL position"""
        if isinstance(node, BaseLinkNode):
            return

        if node in self.stl_actors and node in self.transforms:
            logger.debug(f"Updating transform for node {node.name()} to position {point_xyz}")
            transform = self.transforms[node]
            transform.Identity()
            transform.Translate(point_xyz[0], point_xyz[1], point_xyz[2])
            
            self.stl_actors[node].SetUserTransform(transform)

            if hasattr(node, 'graph'):
                base_node = node.graph.get_node_by_name('base_link')
                if base_node:
                    for port in base_node.output_ports():
                        for connected_port in port.connected_ports():
                            if connected_port.node() == node:
                                self.base_connected_node = node
                                self.update_coordinate_axes(point_xyz)
                                break

            self.vtkWidget.GetRenderWindow().Render()
        else:
            if not isinstance(node, BaseLinkNode):
                logger.warning(f"Warning: No STL actor or transform found for node {node.name()}")

    def reset_stl_transform(self, node):
        """Reset STL position"""
        if isinstance(node, BaseLinkNode):
            return

        if node in self.transforms:
            logger.debug(f"Resetting transform for node {node.name()}")
            transform = self.transforms[node]
            transform.Identity()
            
            self.stl_actors[node].SetUserTransform(transform)
            
            if node == self.base_connected_node:
                self.update_coordinate_axes([0, 0, 0])
                self.base_connected_node = None
            
            self.vtkWidget.GetRenderWindow().Render()
        else:
            if not isinstance(node, BaseLinkNode):
                logger.warning(f"Warning: No transform found for node {node.name()}")

    def load_stl_for_node(self, node):
        """Load STL file for node"""
        if isinstance(node, BaseLinkNode):
            return

        if node.stl_file:
            logger.info(f"Loading STL for node: {node.name()}, file: {node.stl_file}")
            reader = vtk.vtkSTLReader()
            reader.SetFileName(node.stl_file)

            mapper = vtk.vtkPolyDataMapper()
            mapper.SetInputConnection(reader.GetOutputPort())

            actor = vtk.vtkActor()
            actor.SetMapper(mapper)

            transform = vtk.vtkTransform()
            transform.Identity()
            actor.SetUserTransform(transform)

            if node in self.stl_actors:
                self.renderer.RemoveActor(self.stl_actors[node])

            self.stl_actors[node] = actor
            self.transforms[node] = transform
            self.renderer.AddActor(actor)

            self.apply_color_to_node(node)

            self.reset_camera()
            self.vtkWidget.GetRenderWindow().Render()
            logger.info(f"STL file loaded and rendered: {node.stl_file}")

    def apply_color_to_node(self, node):
        """Apply color to node's STL model"""
        if node in self.stl_actors:
            if not hasattr(node, 'node_color') or node.node_color is None:
                node.node_color = [1.0, 1.0, 1.0]

            actor = self.stl_actors[node]
            actor.GetProperty().SetColor(*node.node_color)
            logger.debug(f"Applied color to node {node.name()}: RGB({node.node_color[0]:.3f}, {node.node_color[1]:.3f}, {node.node_color[2]:.3f})")
            self.vtkWidget.GetRenderWindow().Render()

    def remove_stl_for_node(self, node):
        """Remove STL for node"""
        if node in self.stl_actors:
            self.renderer.RemoveActor(self.stl_actors[node])
            del self.stl_actors[node]
            if node in self.transforms:
                del self.transforms[node]
                
            if node == self.base_connected_node:
                self.update_coordinate_axes([0, 0, 0])
                self.base_connected_node = None
                
            self.vtkWidget.GetRenderWindow().Render()
            logger.info(f"Removed STL for node: {node.name()}")

    def setup_camera(self):
        """Setup camera"""
        camera = self.renderer.GetActiveCamera()
        camera.ParallelProjectionOn()
        camera.SetPosition(1, 0, 0)
        camera.SetFocalPoint(0, 0, 0)
        camera.SetViewUp(0, 0, 1)

    def cleanup(self):
        """Cleanup STL viewer resources"""
        if hasattr(self, 'renderer'):
            if self.renderer:
                for actor in self.renderer.GetActors():
                    self.renderer.RemoveActor(actor)
                
                for actor in self.text_actors:
                    self.renderer.RemoveActor(actor)
                self.text_actors.clear()

        if hasattr(self, 'iren'):
            if self.iren:
                self.iren.TerminateApp()

        if hasattr(self, 'vtkWidget'):
            if self.vtkWidget:
                self.vtkWidget.close()

        self.stl_actors.clear()
        self.transforms.clear()

    def __del__(self):
        """Destructor"""
        self.cleanup()

    def update_rotation_axis(self, node, axis_id):
        """Update rotation axis for node"""
        try:
            logger.debug(f"Updating rotation axis for node {node.name()} to axis {axis_id}")
            
            if node in self.stl_actors and node in self.transforms:
                transform = self.transforms[node]
                actor = self.stl_actors[node]
                
                current_position = list(actor.GetPosition())
                
                transform.Identity()
                
                transform.Translate(*current_position)
                
                actor.SetUserTransform(transform)
                
                self.vtkWidget.GetRenderWindow().Render()
                logger.debug(f"Successfully updated rotation axis for node {node.name()}")
            else:
                logger.warning(f"No STL actor or transform found for node {node.name()}")
                
        except Exception as e:
            logger.error(f"Error updating rotation axis: {str(e)}")
            logger.error(traceback.format_exc())

    def update_background(self, value):
        """Update background color"""
        normalized_value = (value + 100) / 200.0
        self.renderer.SetBackground(normalized_value, normalized_value, normalized_value)
        self.vtkWidget.GetRenderWindow().Render()

    def open_urdf_loader_website(self):
        """Open URDF Loaders website"""
        url = QtCore.QUrl(
            "https://gkjohnson.github.io/urdf-loaders/javascript/example/bundle/")
        QtGui.QDesktopServices.openUrl(url)
