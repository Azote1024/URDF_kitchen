import vtk
from utils.urdf_kitchen_logger import setup_logger

logger = setup_logger(__name__)

class CustomInteractorStyle(vtk.vtkInteractorStyleTrackballCamera):
    def __init__(self, parent=None):
        super(CustomInteractorStyle, self).__init__()
        self.parent = parent
        self.AddObserver("CharEvent", self.on_char_event)
        self.AddObserver("KeyPressEvent", self.on_key_press)
        self.AddObserver("MouseMoveEvent", self.on_mouse_move)

    def on_char_event(self, obj, event):
        key = self.GetInteractor().GetKeySym()
        if key == "t":
            logger.info("[T] Toggle wireframe.")
            self.toggle_wireframe()
        elif key == "r":
            logger.info("[R] Reset camera.")
            if self.parent:
                self.parent.reset_camera()
        elif key == "a":
            logger.info("[A] Rotate 90° left.")
            if self.parent:
                self.parent.rotate_camera(90, 'yaw')
        elif key == "d":
            logger.info("[D] Rotate 90° right.")
            if self.parent:
                self.parent.rotate_camera(-90, 'yaw')
        elif key == "w":
            logger.info("[W] Rotate 90° up.")
            if self.parent:
                self.parent.rotate_camera(-90, 'pitch')
        elif key == "s":
            logger.info("[S] Rotate 90° down.")
            if self.parent:
                self.parent.rotate_camera(90, 'pitch')
        elif key == "q":
            logger.info("[Q] Rotate 90° counterclockwise.")
            if self.parent:
                self.parent.rotate_camera(90, 'roll')
        elif key == "e":
            logger.info("[E] Rotate 90° clockwise.")
            if self.parent:
                self.parent.rotate_camera(-90, 'roll')
        else:
            self.OnChar()
            
    def on_key_press(self, obj, event):
        key = self.GetInteractor().GetKeySym()
        shift_pressed = self.GetInteractor().GetShiftKey()
        ctrl_pressed = self.GetInteractor().GetControlKey()
        
        step = 0.01  # デフォルトのステップ (10mm)
        if shift_pressed and ctrl_pressed:
            step = 0.0001  # 0.1mm
        elif shift_pressed:
            step = 0.001  # 1mm
        
        if self.parent and hasattr(self.parent, 'get_screen_axes'):
            horizontal_axis, vertical_axis, screen_right, screen_up = self.parent.get_screen_axes()
            for i, checkbox in enumerate(self.parent.point_checkboxes):
                if checkbox.isChecked():
                    if key == "Up":
                        self.parent.move_point_screen(i, screen_up, step)
                    elif key == "Down":
                        self.parent.move_point_screen(i, screen_up, -step)
                    elif key == "Left":
                        self.parent.move_point_screen(i, screen_right, -step)
                    elif key == "Right":
                        self.parent.move_point_screen(i, screen_right, step)
        
        self.OnKeyPress()
        
    def toggle_wireframe(self):
        if not self.GetInteractor():
            return
        renderer = self.GetInteractor().GetRenderWindow().GetRenderers().GetFirstRenderer()
        if not renderer:
            return
        actors = renderer.GetActors()
        actors.InitTraversal()
        actor = actors.GetNextItem()

        while actor:
            # STLアクターの場合のみ表示モードを切り替える
            # parent.stl_actor が存在する場合はそれを使用、なければ UserTransform がないものを対象とする (StlSourcer互換)
            is_target = False
            if self.parent and hasattr(self.parent, 'stl_actor') and self.parent.stl_actor:
                if actor == self.parent.stl_actor:
                    is_target = True
            elif not actor.GetUserTransform():
                is_target = True

            if is_target:
                if actor.GetProperty().GetRepresentation() == vtk.VTK_SURFACE:
                    actor.GetProperty().SetRepresentationToWireframe()
                else:
                    actor.GetProperty().SetRepresentationToSurface()
            actor = actors.GetNextItem()
        
        self.GetInteractor().GetRenderWindow().Render()
    
    def on_mouse_move(self, obj, event):
        if self.parent and hasattr(self.parent, 'update_point_position'):
            x, y = self.GetInteractor().GetEventPosition()
            for i, checkbox in enumerate(self.parent.point_checkboxes):
                if checkbox.isChecked():
                    self.parent.update_point_position(i, x, y)
        self.OnMouseMove()
