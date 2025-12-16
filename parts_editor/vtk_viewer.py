
import vtk
import numpy as np
from utils.urdf_kitchen_config import PartsEditorConfig as Config
from utils.vtk_helpers import CustomInteractorStyle

class VTKViewer:
    def __init__(self, main_window):
        self.mw = main_window
        self.renderer = None
        self.render_window = None
        self.render_window_interactor = None

    def setup_vtk(self):
        self.renderer = vtk.vtkRenderer()
        self.renderer.SetBackground(*Config.VTK_BACKGROUND_COLOR)
        self.render_window = self.mw.vtk_widget.GetRenderWindow()
        self.render_window.AddRenderer(self.renderer)

        self.render_window_interactor = self.render_window.GetInteractor()

        style = CustomInteractorStyle(self.mw)
        self.render_window_interactor.SetInteractorStyle(style)

    def setup_camera(self):
        camera = self.renderer.GetActiveCamera()
        camera.SetPosition(self.mw.absolute_origin[0] + self.mw.initial_camera_position[0],
                           self.mw.absolute_origin[1] + self.mw.initial_camera_position[1],
                           self.mw.absolute_origin[2] + self.mw.initial_camera_position[2])
        camera.SetFocalPoint(*self.mw.absolute_origin)
        camera.SetViewUp(*self.mw.initial_camera_view_up)
        camera.SetParallelScale(5)
        camera.ParallelProjectionOn()
        self.renderer.ResetCameraClippingRange()

    def reset_camera(self):
        camera = self.renderer.GetActiveCamera()
        camera.SetPosition(self.mw.absolute_origin[0] + self.mw.initial_camera_position[0],
                           self.mw.absolute_origin[1] + self.mw.initial_camera_position[1],
                           self.mw.absolute_origin[2] + self.mw.initial_camera_position[2])
        camera.SetFocalPoint(*self.mw.absolute_origin)
        camera.SetViewUp(*self.mw.initial_camera_view_up)
        
        self.mw.camera_rotation = [0, 0, 0]
        self.mw.current_rotation = 0
        
        self.renderer.ResetCameraClippingRange()
        self.render_window.Render()
        if hasattr(self.mw, 'update_all_points'):
            self.mw.update_all_points()

    def add_axes(self):
        if not hasattr(self.mw, 'axes_actors'):
            self.mw.axes_actors = []

        # Remove existing axes actors
        for actor in self.mw.axes_actors:
            self.renderer.RemoveActor(actor)
        self.mw.axes_actors.clear()

        axis_length = 5
        colors = [(1, 0, 0), (0, 1, 0), (0, 0, 1)]
        for i, color in enumerate(colors):
            for direction in [1, -1]:
                line_source = vtk.vtkLineSource()
                line_source.SetPoint1(*self.mw.absolute_origin)
                end_point = np.array(self.mw.absolute_origin)
                end_point[i] += axis_length * direction
                line_source.SetPoint2(*end_point)

                mapper = vtk.vtkPolyDataMapper()
                mapper.SetInputConnection(line_source.GetOutputPort())

                actor = vtk.vtkActor()
                actor.SetMapper(mapper)
                actor.GetProperty().SetColor(color)
                actor.GetProperty().SetLineWidth(1)
                
                self.renderer.AddActor(actor)
                self.mw.axes_actors.append(actor)

    def add_axes_widget(self):
        axes = vtk.vtkAxesActor()
        axes.SetTotalLength(0.3, 0.3, 0.3)
        axes.SetShaftTypeToLine()
        axes.SetNormalizedShaftLength(1, 1, 1)
        axes.SetNormalizedTipLength(0.1, 0.1, 0.1)
        
        axes.GetXAxisCaptionActor2D().GetTextActor().SetTextScaleModeToNone()
        axes.GetYAxisCaptionActor2D().GetTextActor().SetTextScaleModeToNone()
        axes.GetZAxisCaptionActor2D().GetTextActor().SetTextScaleModeToNone()
        
        widget = vtk.vtkOrientationMarkerWidget()
        widget.SetOrientationMarker(axes)
        widget.SetInteractor(self.render_window_interactor)
        widget.SetViewport(0.7, 0.7, 1.0, 1.0)
        widget.EnabledOn()
        widget.InteractiveOff()
        
        return widget

    def add_instruction_text(self):
        # Top Left Text
        text_actor_top = vtk.vtkTextActor()
        text_actor_top.SetInput(
            "[W/S]: Up/Down Rotate\n"
            "[A/D]: Left/Right Rotate\n"
            "[Q/E]: Roll\n"
            "[R]: Reset Camera\n"
            "[T]: Wireframe\n\n"
            "[Drag]: Rotate\n"
            "[Shift + Drag]: Move View\n"
        )
        text_actor_top.GetTextProperty().SetFontSize(14)
        text_actor_top.GetTextProperty().SetColor(0.3, 0.8, 1.0)
        text_actor_top.GetPositionCoordinate().SetCoordinateSystemToNormalizedViewport()
        text_actor_top.SetPosition(0.03, 0.97)
        text_actor_top.GetTextProperty().SetJustificationToLeft()
        text_actor_top.GetTextProperty().SetVerticalJustificationToTop()
        self.renderer.AddActor(text_actor_top)

        # Bottom Left Text
        text_actor_bottom = vtk.vtkTextActor()
        text_actor_bottom.SetInput(
            "[Arrows] : Move Point 10mm\n"
            " +[Shift]: Move Point 1mm\n"
            "  +[Ctrl]: Move Point 0.1mm\n\n"
        )
        text_actor_bottom.GetTextProperty().SetFontSize(14)
        text_actor_bottom.GetTextProperty().SetColor(0.3, 0.8, 1.0)
        text_actor_bottom.GetPositionCoordinate().SetCoordinateSystemToNormalizedViewport()
        text_actor_bottom.SetPosition(0.03, 0.03)
        text_actor_bottom.GetTextProperty().SetJustificationToLeft()
        text_actor_bottom.GetTextProperty().SetVerticalJustificationToBottom()
        self.renderer.AddActor(text_actor_bottom)
