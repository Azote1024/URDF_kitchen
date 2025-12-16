"""
File Name: urdf_kitchen_PartsEditor.py
Description: A Python script for configuring connection points of parts for urdf_kitchen_Assembler.py.

Author      : Ninagawa123
Created On  : Nov 24, 2024
Version     : 0.0.2
License     : MIT License
URL         : https://github.com/Ninagawa123/URDF_kitchen_beta
Copyright (c) 2024 Ninagawa123

python3.9
pip install --upgrade pip
pip install numpy
pip install PySide6
pip install vtk
pip install NodeGraphQt
"""

import sys
import signal
import math
import os
import numpy as np
import traceback
import base64
import shutil
import datetime
import xml.etree.ElementTree as ET

import vtk
from vtkmodules.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor

from Qt import QtWidgets, QtCore, QtGui
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QMainWindow, QVBoxLayout, QWidget, 
    QPushButton, QHBoxLayout, QCheckBox, QLineEdit, QLabel, QGridLayout,
    QTextEdit, QButtonGroup, QRadioButton, QColorDialog, QDialog
)
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QTextOption, QColor, QPalette

from utils.urdf_kitchen_config import PartsEditorConfig as Config
from utils.urdf_kitchen_logger import setup_logger
from utils.ui_helpers import apply_dark_theme
from utils.math_utils import calculate_inertia_tensor, format_inertia_for_urdf

from .ui_setup import PartsEditorUI
from .vtk_viewer import VTKViewer

logger = setup_logger(__name__)

# pip install numpy
# pip install PySide6
# pip install vtk
# pip install NodeGraphQt

class PartsEditorMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(Config.WINDOW_TITLE)
        self.setGeometry(*Config.WINDOW_GEOMETRY)
        self.camera_rotation = [0, 0, 0]
        self.absolute_origin = [0, 0, 0]
        self.initial_camera_position = Config.INITIAL_CAMERA_POSITION
        self.initial_camera_focal_point = Config.INITIAL_CAMERA_FOCAL_POINT
        self.initial_camera_view_up = Config.INITIAL_CAMERA_VIEW_UP

        self.num_points = Config.NUM_POINTS
        self.point_coords = [list(self.absolute_origin) for _ in range(self.num_points)]
        self.point_actors = [None] * self.num_points
        self.point_checkboxes = []
        self.point_inputs = []
        self.point_set_buttons = []
        self.point_reset_buttons = []

        self.com_actor = None

        # Initialize UI
        self.ui = PartsEditorUI(self)
        self.ui.setup_ui()

        # Initialize VTK
        self.vtk_viewer = VTKViewer(self)
        self.vtk_viewer.setup_vtk()
        self.vtk_viewer.setup_camera()
        self.vtk_viewer.add_axes()
        self.vtk_viewer.add_instruction_text()

        self.model_bounds = None
        self.stl_actor = None
        self.current_rotation = 0

        self.stl_center = list(self.absolute_origin)

        self.animation_timer = QTimer()
        self.animation_timer.timeout.connect(self.animate_rotation)
        self.animation_frames = 0
        self.total_animation_frames = 12
        self.rotation_per_frame = 0
        self.target_rotation = 0

        self.rotation_types = {'yaw': 0, 'pitch': 1, 'roll': 2}

        self.axes_widget = self.vtk_viewer.add_axes_widget()
        
        self.vtk_viewer.render_window.Render()
        self.vtk_viewer.render_window_interactor.Initialize()
        # TODO: This observer causes the application to close immediately. 
        # The update_all_points_size method might be causing infinite recursion or other issues.
        # self.vtk_widget.GetRenderWindow().AddObserver("ModifiedEvent", self.update_all_points_size)
        
        apply_dark_theme(self)

    def set_point(self, index):
        try:
            x = float(self.point_inputs[index][0].text())
            y = float(self.point_inputs[index][1].text())
            z = float(self.point_inputs[index][2].text())
            self.point_coords[index] = [x, y, z]
            
            if self.point_checkboxes[index].isChecked():
                self.show_point(index)
            else:
                self.update_point_display(index)
            
            logger.info(f"Point {index+1} set to: ({x}, {y}, {z})")
        except ValueError:
            logger.error(f"Invalid input for Point {index+1}. Please enter valid numbers for coordinates.")

    def reset_point_to_origin(self, index):
        self.point_coords[index] = list(self.absolute_origin)
        self.update_point_display(index)
        if self.point_checkboxes[index].isChecked():
            self.show_point(index)
        logger.info(f"Point {index+1} reset to origin {self.absolute_origin}")

    def reset_camera(self):
        self.vtk_viewer.reset_camera()

    def update_point_position(self, index, x, y):
        renderer = self.vtk_viewer.renderer
        camera = renderer.GetActiveCamera()

        # スクリーン座標からワールド座標への変換
        coordinate = vtk.vtkCoordinate()
        coordinate.SetCoordinateSystemToDisplay()
        coordinate.SetValue(x, y, 0)
        world_pos = coordinate.GetComputedWorldValue(renderer)

        # カメラの向きに基づいて、z座標を現在のポイントのz座標に保つ
        camera_pos = np.array(camera.GetPosition())
        focal_point = np.array(camera.GetFocalPoint())
        view_direction = focal_point - camera_pos
        view_direction /= np.linalg.norm(view_direction)

        current_z = self.point_coords[index][2]
        t = (current_z - camera_pos[2]) / view_direction[2]
        new_pos = camera_pos + t * view_direction

        self.point_coords[index] = [new_pos[0], new_pos[1], current_z]
        self.update_point_display(index)

        logger.debug(f"Point {index+1} moved to: ({new_pos[0]:.6f}, {new_pos[1]:.6f}, {current_z:.6f})")

    def update_inertia_from_mass(self, mass):
        # イナーシャを重さから計算する例（適宜調整してください）
        inertia = mass * 0.1  # 例として、重さの0.1倍をイナーシャとする
        self.inertia_input.setText(f"{inertia:.12f}")

    def update_properties(self):
        # 優先順位: Mass > Volume > Inertia > Density
        priority_order = ['mass', 'volume', 'inertia', 'density']
        values = {}

        # チェックされているプロパティの値を取得
        for prop in priority_order:
            checkbox = getattr(self, f"{prop}_checkbox")
            input_field = getattr(self, f"{prop}_input")
            if checkbox.isChecked():
                try:
                    values[prop] = float(input_field.text())
                except ValueError:
                    logger.error(f"Invalid input for {prop}")
                    return

        # 値の計算
        if 'mass' in values and 'volume' in values:
            values['density'] = values['mass'] / values['volume']
        elif 'mass' in values and 'density' in values:
            values['volume'] = values['mass'] / values['density']
        elif 'volume' in values and 'density' in values:
            values['mass'] = values['volume'] * values['density']

        # Inertiaの計算 (簡略化した例: 立方体と仮定)
        if 'mass' in values and 'volume' in values:
            side_length = np.cbrt(values['volume'])
            values['inertia'] = (1/6) * values['mass'] * side_length**2

        # 結果を入力フィールドに反映
        for prop in priority_order:
            input_field = getattr(self, f"{prop}_input")
            if prop in values:
                input_field.setText(f"{values[prop]:.12f}")

    def update_point_display(self, index):
        """ポイントの表示を更新（チェック状態の確認を追加）"""
        if self.point_actors[index]:
            if self.point_checkboxes[index].isChecked():
                self.point_actors[index].SetPosition(self.point_coords[index])
                self.point_actors[index].VisibilityOn()
            else:
                self.point_actors[index].VisibilityOff()
                self.vtk_viewer.renderer.RemoveActor(self.point_actors[index])
        
        for i, coord in enumerate(self.point_coords[index]):
            self.point_inputs[index][i].setText(f"{coord:.6f}")
        
        self.vtk_viewer.render_window.Render()

    def update_all_points_size(self, obj=None, event=None):
        """ポイントのサイズを更新（可視性の厳密な管理を追加）"""
        for index, actor in enumerate(self.point_actors):
            if actor:
                # チェックボックスの状態を確認
                is_checked = self.point_checkboxes[index].isChecked()
                
                # 一旦アクターを削除
                self.vtk_viewer.renderer.RemoveActor(actor)
                
                # 新しいアクターを作成
                self.point_actors[index] = vtk.vtkAssembly()
                self.create_point_coordinate(self.point_actors[index], [0, 0, 0])
                self.point_actors[index].SetPosition(self.point_coords[index])
                
                # チェック状態に応じて可視性を設定
                if is_checked:
                    self.vtk_viewer.renderer.AddActor(self.point_actors[index])
                    self.point_actors[index].VisibilityOn()
                else:
                    self.point_actors[index].VisibilityOff()
        
        self.vtk_viewer.render_window.Render()

    def update_all_points(self):
        """全ポイントの表示を更新（チェック状態の確認を追加）"""
        for i in range(self.num_points):
            if self.point_actors[i]:
                if self.point_checkboxes[i].isChecked():
                    self.point_actors[i].SetPosition(self.point_coords[i])
                    self.point_actors[i].VisibilityOn()
                    self.vtk_viewer.renderer.AddActor(self.point_actors[i])
                else:
                    self.point_actors[i].VisibilityOff()
                    self.vtk_viewer.renderer.RemoveActor(self.point_actors[i])
        
        self.vtk_viewer.render_window.Render()

    def create_point_coordinate(self, assembly, coords):
        origin = coords
        axis_length = self.calculate_sphere_radius() * 36  # 直径の18倍（6倍の3倍）を軸の長さとして使用
        circle_radius = self.calculate_sphere_radius()

        logger.debug(f"Creating point coordinate at {coords}")
        logger.debug(f"Axis length: {axis_length}, Circle radius: {circle_radius}")

        # XYZ軸の作成
        colors = [(1, 0, 0), (0, 1, 0), (0, 0, 1)]  # 赤、緑、青
        for i, color in enumerate(colors):
            for direction in [1, -1]:  # 正方向と負方向の両方
                line_source = vtk.vtkLineSource()
                line_source.SetPoint1(
                    origin[0] - (axis_length / 2) * (i == 0) * direction,
                    origin[1] - (axis_length / 2) * (i == 1) * direction,
                    origin[2] - (axis_length / 2) * (i == 2) * direction
                )
                line_source.SetPoint2(
                    origin[0] + (axis_length / 2) * (i == 0) * direction,
                    origin[1] + (axis_length / 2) * (i == 1) * direction,
                    origin[2] + (axis_length / 2) * (i == 2) * direction
                )

                mapper = vtk.vtkPolyDataMapper()
                mapper.SetInputConnection(line_source.GetOutputPort())

                actor = vtk.vtkActor()
                actor.SetMapper(mapper)
                actor.GetProperty().SetColor(color)
                actor.GetProperty().SetLineWidth(2)

                assembly.AddPart(actor)
                logger.debug(f"Added {['X', 'Y', 'Z'][i]} axis {'positive' if direction == 1 else 'negative'}")

        # XY, XZ, YZ平面の円を作成
        for i in range(3):
            circle = vtk.vtkRegularPolygonSource()
            circle.SetNumberOfSides(50)
            circle.SetRadius(circle_radius)
            circle.SetCenter(origin[0], origin[1], origin[2])
            if i == 0:  # XY平面
                circle.SetNormal(0, 0, 1)
                plane = "XY"
            elif i == 1:  # XZ平面
                circle.SetNormal(0, 1, 0)
                plane = "XZ"
            else:  # YZ平面
                circle.SetNormal(1, 0, 0)
                plane = "YZ"

            mapper = vtk.vtkPolyDataMapper()
            mapper.SetInputConnection(circle.GetOutputPort())

            actor = vtk.vtkActor()
            actor.SetMapper(mapper)
            
            # 円のプロパティを設定(ponintのカーソル表示用)
            actor.GetProperty().SetColor(1, 0, 1)  # 紫色
            actor.GetProperty().SetRepresentationToWireframe()  # 常にワイヤーフレーム表示
            actor.GetProperty().SetLineWidth(6)  # 線の太さを3倍の6に設定
            actor.GetProperty().SetOpacity(0.7)  # 不透明度を少し下げて見やすくする

            # タグ付けのためにUserTransformを設定
            transform = vtk.vtkTransform()
            actor.SetUserTransform(transform)

            assembly.AddPart(actor)
            logger.debug(f"Added {plane} circle")

        logger.debug(f"Point coordinate creation completed")

    def calculate_sphere_radius(self):
        # ビューポートのサイズを取得
        viewport_size = self.vtk_viewer.renderer.GetSize()
        
        # 画面の対角線の長さを計算
        diagonal = math.sqrt(viewport_size[0]**2 + viewport_size[1]**2)
        
        # 対角線の10%をサイズとして設定
        radius = (diagonal * 0.1) / 2  # 半径なので2で割る
        
        # カメラのパラレルスケールでスケーリング
        camera = self.vtk_viewer.renderer.GetActiveCamera()
        parallel_scale = camera.GetParallelScale()
        viewport = self.vtk_viewer.renderer.GetViewport()
        aspect_ratio = (viewport[2] - viewport[0]) / (viewport[3] - viewport[1])
        
        # ビューポートのサイズに基づいて適切なスケールに変換
        scaled_radius = (radius / viewport_size[1]) * parallel_scale * 2
        
        if aspect_ratio > 1:
            scaled_radius /= aspect_ratio
            
        return scaled_radius

    def calculate_screen_diagonal(self):
        viewport_size = self.vtk_viewer.renderer.GetSize()
        return math.sqrt(viewport_size[0]**2 + viewport_size[1]**2)

    def calculate_properties(self):
        # 優先順位: Volume > Density > Mass > Inertia
        priority_order = ['volume', 'density', 'mass', 'inertia']
        values = {}

        # チェックされているプロパティの値を取得
        for prop in priority_order:
            checkbox = getattr(self, f"{prop}_checkbox")
            input_field = getattr(self, f"{prop}_input")
            if checkbox.isChecked():
                try:
                    values[prop] = float(input_field.text())
                except ValueError:
                    logger.error(f"Invalid input for {prop}")
                    return

        # 値の計算
        if 'volume' in values and 'density' in values:
            values['mass'] = values['volume'] * values['density']
        elif 'mass' in values and 'volume' in values:
            values['density'] = values['mass'] / values['volume']
        elif 'mass' in values and 'density' in values:
            values['volume'] = values['mass'] / values['density']

        # Inertiaの計算 (簡略化した例: 立方体と仮定)
        if 'mass' in values and 'volume' in values:
            side_length = np.cbrt(values['volume'])
            values['inertia'] = (1/6) * values['mass'] * side_length**2

        # 結果を入力フィールドに反映
        for prop in priority_order:
            input_field = getattr(self, f"{prop}_input")
            if prop in values:
                input_field.setText(f"{values[prop]:.12f}")

    def calculate_and_update_properties(self):
        try:
            # 現在のチェック状態とテキスト値を取得
            properties = {
                'volume': {
                    'checked': self.volume_checkbox.isChecked(),
                    'value': float(self.volume_input.text()) if self.volume_checkbox.isChecked() else None
                },
                'density': {
                    'checked': self.density_checkbox.isChecked(),
                    'value': float(self.density_input.text()) if self.density_checkbox.isChecked() else None
                },
                'mass': {
                    'checked': self.mass_checkbox.isChecked(),
                    'value': float(self.mass_input.text()) if self.mass_checkbox.isChecked() else None
                }
            }

            # STLからの体積計算（必要な場合に使用）
            stl_volume = None
            if (not properties['volume']['checked'] and 
                ((properties['density']['checked'] and not properties['mass']['checked']) or
                (not properties['density']['checked'] and properties['mass']['checked']))):
                if hasattr(self, 'stl_actor') and self.stl_actor:
                    poly_data = self.stl_actor.GetMapper().GetInput()
                    mass_properties = vtk.vtkMassProperties()
                    mass_properties.SetInputData(poly_data)
                    stl_volume = mass_properties.GetVolume()
                    properties['volume']['value'] = stl_volume
                    self.volume_input.setText(f"{stl_volume:.12f}")

            # 値の計算
            # Case 1: VolumeとMassがチェックされている場合
            if properties['volume']['checked'] and properties['mass']['checked']:
                properties['density']['value'] = properties['mass']['value'] / properties['volume']['value']
                self.density_input.setText(f"{properties['density']['value']:.12f}")

            # Case 2: VolumeとDensityがチェックされている場合
            elif properties['volume']['checked'] and properties['density']['checked']:
                properties['mass']['value'] = properties['volume']['value'] * properties['density']['value']
                self.mass_input.setText(f"{properties['mass']['value']:.12f}")

            # Case 3: DensityとMassがチェックされている場合
            elif properties['density']['checked'] and properties['mass']['checked']:
                properties['volume']['value'] = properties['mass']['value'] / properties['density']['value']
                self.volume_input.setText(f"{properties['volume']['value']:.12f}")

            # Case 4: 単一のチェックケース
            elif stl_volume is not None:
                if properties['density']['checked']:
                    properties['mass']['value'] = stl_volume * properties['density']['value']
                    self.mass_input.setText(f"{properties['mass']['value']:.12f}")
                elif properties['mass']['checked']:
                    properties['density']['value'] = properties['mass']['value'] / stl_volume
                    self.density_input.setText(f"{properties['density']['value']:.12f}")

            # 重心の更新
            # COMチェックボックスの状態に関わらず常に重心を再計算
            self.calculate_center_of_mass()

            # 慣性テンソルを常に更新
            self.calculate_inertia_tensor()

        except (ValueError, ZeroDivisionError) as e:
            logger.error(f"An error occurred during calculation: {str(e)}", exc_info=True)
            return None

        return properties

    def calculate_center_of_mass(self):
        """
        重心を計算して表示する。
        チェックボックスがオンの場合は入力値を使用し、オフの場合は計算値を使用する。
        """
        if not hasattr(self, 'stl_actor') or not self.stl_actor:
            logger.warning("No STL model has been loaded.")
            return

        # 重心の座標を取得（チェックボックスの状態に応じて）
        if hasattr(self, 'com_checkbox') and self.com_checkbox.isChecked():
            try:
                # 入力テキストから座標を取得
                com_text = self.com_input.text().strip('()').split(',')
                if len(com_text) != 3:
                    raise ValueError("Invalid format: Requires 3 coordinates")
                center_of_mass = [float(x.strip()) for x in com_text]
                print(f"Using manual Center of Mass: {center_of_mass}")
            except (ValueError, IndexError) as e:
                print(f"Error parsing Center of Mass input: {e}")
                return None
        else:
            # STLから重心を計算
            poly_data = self.stl_actor.GetMapper().GetInput()
            com_filter = vtk.vtkCenterOfMass()
            com_filter.SetInputData(poly_data)
            com_filter.SetUseScalarsAsWeights(False)
            com_filter.Update()
            center_of_mass = com_filter.GetCenter()
            # 計算された値を入力欄に設定
            self.com_input.setText(f"({center_of_mass[0]:.6f}, {center_of_mass[1]:.6f}, {center_of_mass[2]:.6f})")
            print(f"Calculated Center of Mass: {center_of_mass}")

        # 既存の重心アクターを削除
        if hasattr(self, 'com_actor') and self.com_actor:
            self.vtk_viewer.renderer.RemoveActor(self.com_actor)

        # 重心を可視化（赤い点）
        sphere = vtk.vtkSphereSource()
        sphere.SetCenter(center_of_mass)
        sphere.SetRadius(self.calculate_sphere_radius() * 0.5)

        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputConnection(sphere.GetOutputPort())

        self.com_actor = vtk.vtkActor()
        self.com_actor.SetMapper(mapper)
        self.com_actor.GetProperty().SetColor(1, 0, 0)  # 赤色
        self.com_actor.GetProperty().SetOpacity(0.7)

        self.vtk_viewer.renderer.AddActor(self.com_actor)
        self.vtk_viewer.render_window.Render()

        return center_of_mass

    def calculate_inertia_tensor(self):
        """
        三角形メッシュの慣性テンソルを計算する。
        重心位置を考慮し、正確なイナーシャを算出する。
        
        Returns:
            numpy.ndarray: 3x3の慣性テンソル行列
            None: エラーが発生した場合
        """
        if not hasattr(self, 'stl_actor') or not self.stl_actor:
            logger.warning("No STL model is loaded.")
            return None

        # ポリデータを取得
        poly_data = self.stl_actor.GetMapper().GetInput()

        # 体積と質量を取得して表示
        mass_properties = vtk.vtkMassProperties()
        mass_properties.SetInputData(poly_data)
        mass_properties.Update()
        volume = mass_properties.GetVolume()
        try:
            density = float(self.density_input.text())
        except ValueError:
            logger.error("Invalid density input")
            return None
            
        mass = volume * density
        logger.info(f"Volume: {volume:.6f}, Density: {density:.6f}, Mass: {mass:.6f}")

        # UIまたは計算から重心を取得
        center_of_mass = self.get_center_of_mass()
        if center_of_mass is None:
            logger.error("Error getting center of mass")
            return None

        # 共通ユーティリティを使用して慣性テンソルを計算
        inertia_tensor = calculate_inertia_tensor(poly_data, density, center_of_mass)
        
        if inertia_tensor is None:
            return None

        # 慣性テンソルの値を表示
        logger.info("\nCalculated Inertia Tensor:")
        logger.info(inertia_tensor)

        # URDFフォーマットに変換してUIを更新
        urdf_inertia = format_inertia_for_urdf(inertia_tensor)
        if hasattr(self, 'inertia_tensor_input'):
            self.inertia_tensor_input.setText(urdf_inertia)
            logger.info("Inertia tensor has been updated in UI")
        else:
            logger.warning("inertia_tensor_input not found")

        return inertia_tensor

    def export_urdf(self):
        if not hasattr(self, 'stl_file_path'):
            print("No STL file has been loaded.")
            return

        # STLファイルのパスとファイル名を取得
        stl_dir = os.path.dirname(self.stl_file_path)
        stl_filename = os.path.basename(self.stl_file_path)
        stl_name_without_ext = os.path.splitext(stl_filename)[0]

        # デフォルトのURDFファイル名を設定
        default_urdf_filename = f"{stl_name_without_ext}.xml"
        urdf_file_path, _ = QFileDialog.getSaveFileName(self, "Save URDF File", os.path.join(
            stl_dir, default_urdf_filename), "XML Files (*.xml)")

        if not urdf_file_path:
            return

        try:
            # 色情報の取得と変換
            rgb_values = [float(input.text()) for input in self.color_inputs]
            hex_color = '#{:02X}{:02X}{:02X}'.format(
                int(rgb_values[0] * 255),
                int(rgb_values[1] * 255),
                int(rgb_values[2] * 255)
            )
            rgba_str = f"{rgb_values[0]:.6f} {rgb_values[1]:.6f} {rgb_values[2]:.6f} 1.0"

            # 重心の座標を取得
            try:
                com_text = self.com_input.text().strip('()').split(',')
                com_values = [float(x.strip()) for x in com_text]
                center_of_mass_str = f"{com_values[0]:.6f} {com_values[1]:.6f} {com_values[2]:.6f}"
            except (ValueError, IndexError):
                print("Warning: Invalid center of mass format, using default values")
                center_of_mass_str = "0.000000 0.000000 0.000000"

            # 軸情報の取得
            axis_options = ["1 0 0", "0 1 0", "0 0 1", "0 0 0"]  # fixedのために"0 0 0"を追加
            checked_id = self.axis_group.checkedId()
            if 0 <= checked_id < len(axis_options):
                axis_vector = axis_options[checked_id]
            else:
                print("Warning: No axis selected, using default X axis")
                axis_vector = "1 0 0"

            # URDFの内容を構築
            urdf_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<urdf_part>
    <material name="{hex_color}">
        <color rgba="{rgba_str}" />
    </material>
    <link name="{stl_name_without_ext}">
        <visual>
            <origin xyz="{center_of_mass_str}" rpy="0 0 0"/>
            <material name="{hex_color}" />
        </visual>
        <inertial>
            <origin xyz="{center_of_mass_str}"/>
            <mass value="{self.mass_input.text()}"/>
            <volume value="{self.volume_input.text()}"/>
            {self.inertia_tensor_input.toPlainText().strip()}
        </inertial>
        <center_of_mass>{center_of_mass_str}</center_of_mass>
    </link>"""

            # ポイント要素の追加
            for i, checkbox in enumerate(self.point_checkboxes):
                if checkbox.isChecked():
                    x, y, z = self.point_coords[i]
                    urdf_content += f"""
    <point name="point{i+1}" type="fixed">
        <point_xyz>{x:.6f} {y:.6f} {z:.6f}</point_xyz>
    </point>"""

            # 軸情報の追加
            urdf_content += f"""
    <joint>
        <axis xyz="{axis_vector}" />
    </joint>
</urdf_part>"""

            # ファイルに保存
            with open(urdf_file_path, "w") as f:
                f.write(urdf_content)
            print(f"URDF file saved: {urdf_file_path}")

        except Exception as e:
            print(f"Error during URDF export: {str(e)}")
            traceback.print_exc()


    def get_center_of_mass(self):
        """
        UIまたは計算から重心を取得する
        
        Returns:
            numpy.ndarray: 重心の座標 [x, y, z]
            None: エラーが発生した場合
        """
        if not hasattr(self, 'stl_actor') or not self.stl_actor:
            print("No STL model is loaded.")
            return None

        if hasattr(self, 'com_checkbox') and self.com_checkbox.isChecked():
            try:
                # 入力テキストから座標を取得
                com_text = self.com_input.text().strip('()').split(',')
                if len(com_text) != 3:
                    raise ValueError("Invalid format: Requires 3 coordinates")
                center_of_mass = np.array([float(x.strip()) for x in com_text])
                print(f"Using manual Center of Mass: {center_of_mass}")
                return center_of_mass
            except (ValueError, IndexError) as e:
                print(f"Error parsing Center of Mass input: {e}")
                return None
        
        # チェックされていない場合やエラー時は計算値を使用
        try:
            poly_data = self.stl_actor.GetMapper().GetInput()
            com_filter = vtk.vtkCenterOfMass()
            com_filter.SetInputData(poly_data)
            com_filter.SetUseScalarsAsWeights(False)
            com_filter.Update()
            center_of_mass = np.array(com_filter.GetCenter())
            print(f"Using calculated Center of Mass: {center_of_mass}")
            return center_of_mass
        except Exception as e:
            print(f"Error calculating center of mass: {e}")
            return None




    def apply_camera_rotation(self, camera):
        # カメラの現在の位置と焦点を取得
        position = list(camera.GetPosition())
        focal_point = self.absolute_origin
        
        # 回転行列を作成
        transform = vtk.vtkTransform()
        transform.PostMultiply()
        transform.Translate(*focal_point)
        transform.RotateZ(self.camera_rotation[2])  # Roll
        transform.RotateX(self.camera_rotation[0])  # Pitch
        transform.RotateY(self.camera_rotation[1])  # Yaw
        transform.Translate(*[-x for x in focal_point])
        
        # カメラの位置を回転
        new_position = transform.TransformPoint(position)
        camera.SetPosition(new_position)
        
        # カメラの上方向を更新
        up = [0, 0, 1]
        new_up = transform.TransformVector(up)
        camera.SetViewUp(new_up)



    def load_stl_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Open STL File", "", "STL Files (*.stl)")
        if file_path:
            self.file_name_value.setText(file_path)
            self.show_stl(file_path)

    def show_stl(self, file_path):
        #古いアクターを削除
        if hasattr(self, 'stl_actor') and self.stl_actor:
            self.vtk_viewer.renderer.RemoveActor(self.stl_actor)
        if hasattr(self, 'com_actor') and self.com_actor:
            self.vtk_viewer.renderer.RemoveActor(self.com_actor)
            self.com_actor = None

        # レンダラーをクリア
        # self.vtk_viewer.renderer.Clear() # Clear() clears the image buffer, not props.
        
        # 座標軸の再追加
        if hasattr(self, 'axes_widget') and self.axes_widget:
            self.axes_widget.EnabledOff()
        self.axes_widget = self.vtk_viewer.add_axes_widget()

        self.stl_file_path = file_path

        reader = vtk.vtkSTLReader()
        reader.SetFileName(file_path)
        reader.Update()

        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputConnection(reader.GetOutputPort())
        self.stl_actor = vtk.vtkActor()
        self.stl_actor.SetMapper(mapper)

        self.model_bounds = reader.GetOutput().GetBounds()
        self.vtk_viewer.renderer.AddActor(self.stl_actor)
        
        # STLの体積を取得
        mass_properties = vtk.vtkMassProperties()
        mass_properties.SetInputConnection(reader.GetOutputPort())
        volume = mass_properties.GetVolume()
        
        # 体積をUIに反映（小数点以下12桁）
        self.volume_input.setText(f"{volume:.12f}")
        
        # デフォルトの密度を取得して質量を計算
        density = float(self.density_input.text())
        mass = volume * density  # 体積 × 密度 = 質量
        self.mass_input.setText(f"{mass:.12f}")

        # イナーシャを計算（簡略化：立方体と仮定）
        #side_length = np.cbrt(volume)
        #inertia = (1/6) * mass * side_length**2
        #self.inertia_input.setText(f"{inertia:.12f}")

        # 慣性テンソルを計算
        inertia_tensor = self.calculate_inertia_tensor()

        # カメラのフィッティングと描画更新
        self.fit_camera_to_model()
        self.update_all_points()

        # プロパティを更新
        self.calculate_and_update_properties()

        # 重心を計算して表示
        center_of_mass = self.calculate_center_of_mass()
        # 重心を計算して表示
        self.calculate_center_of_mass()
        
        # 境界ボックスを出力
        print(f"STL model bounding box: [{self.model_bounds[0]:.6f}, {self.model_bounds[1]:.6f}], [{self.model_bounds[2]:.6f}, {self.model_bounds[3]:.6f}], [{self.model_bounds[4]:.6f}, {self.model_bounds[5]:.6f}]")

        # 大原点を表示
        self.show_absolute_origin()

        # ファイル名をフルパスで更新
        self.file_name_value.setText(file_path)
        
        # レンダリングを強制的に更新
        self.vtk_viewer.render_window.Render()
        
    def show_absolute_origin(self):
        # 大原点を表す球を作成
        sphere = vtk.vtkSphereSource()
        sphere.SetCenter(0, 0, 0)
        sphere.SetRadius(0.0005)  # 適切なサイズに調整してください
        sphere.Update()

        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputConnection(sphere.GetOutputPort())

        actor = vtk.vtkActor()
        actor.SetMapper(mapper)
        actor.GetProperty().SetColor(1, 1, 0)  # 黄色

        self.vtk_viewer.renderer.AddActor(actor)
        self.vtk_viewer.render_window.Render()

    def show_point(self, index):
        """ポイントを表示（XMLロード時にも使用）"""
        if not self.point_checkboxes[index].isChecked():
            return

        if self.point_actors[index] is None:
            self.point_actors[index] = vtk.vtkAssembly()
            self.create_point_coordinate(self.point_actors[index], [0, 0, 0])
            self.vtk_viewer.renderer.AddActor(self.point_actors[index])
        
        self.point_actors[index].SetPosition(self.point_coords[index])
        self.point_actors[index].VisibilityOn()
        self.update_point_display(index)

    def rotate_camera(self, angle, rotation_type):
        self.target_rotation = (self.current_rotation + angle) % 360
        self.rotation_per_frame = angle / self.total_animation_frames
        self.animation_frames = 0
        self.current_rotation_type = self.rotation_types[rotation_type]
        self.animation_timer.start(1000 // 60)
        self.camera_rotation[self.rotation_types[rotation_type]] += angle
        self.camera_rotation[self.rotation_types[rotation_type]] %= 360

    def animate_rotation(self):
        self.animation_frames += 1
        if self.animation_frames > self.total_animation_frames:
            self.animation_timer.stop()
            self.current_rotation = self.target_rotation
            return

        camera = self.vtk_viewer.renderer.GetActiveCamera()

        position = list(camera.GetPosition())
        focal_point = self.absolute_origin
        view_up = list(camera.GetViewUp())

        forward = [focal_point[i] - position[i] for i in range(3)]
        right = [
            view_up[1] * forward[2] - view_up[2] * forward[1],
            view_up[2] * forward[0] - view_up[0] * forward[2],
            view_up[0] * forward[1] - view_up[1] * forward[0]
        ]

        if self.current_rotation_type == self.rotation_types['yaw']:
            axis = view_up
        elif self.current_rotation_type == self.rotation_types['pitch']:
            axis = right
        else:  # roll
            axis = forward

        rotation_matrix = vtk.vtkTransform()
        rotation_matrix.Translate(*focal_point)
        rotation_matrix.RotateWXYZ(self.rotation_per_frame, axis)
        rotation_matrix.Translate(*[-x for x in focal_point])

        new_position = rotation_matrix.TransformPoint(position)
        new_up = rotation_matrix.TransformVector(view_up)

        camera.SetPosition(new_position)
        camera.SetViewUp(new_up)

        self.vtk_viewer.render_window.Render()

    def toggle_point(self, state, index):
        """ポイントの表示/非表示を切り替え"""
        if state == Qt.CheckState.Checked.value:
            if self.point_actors[index] is None:
                self.point_actors[index] = vtk.vtkAssembly()
                self.create_point_coordinate(self.point_actors[index], [0, 0, 0])
                self.vtk_viewer.renderer.AddActor(self.point_actors[index])
            self.point_actors[index].SetPosition(self.point_coords[index])
            self.point_actors[index].VisibilityOn()
            self.vtk_viewer.renderer.AddActor(self.point_actors[index])
        else:
            if self.point_actors[index]:
                self.point_actors[index].VisibilityOff()
                self.vtk_viewer.renderer.RemoveActor(self.point_actors[index])
        
        self.vtk_viewer.render_window.Render()

    def get_axis_length(self):
        if self.model_bounds:
            size = max([
                self.model_bounds[1] - self.model_bounds[0],
                self.model_bounds[3] - self.model_bounds[2],
                self.model_bounds[5] - self.model_bounds[4]
            ])
            return size * 0.5
        else:
            return 5  # デフォルトの長さ

    def hide_point(self, index):
        if self.point_actors[index]:
            self.point_actors[index].VisibilityOff()
        self.vtk_viewer.render_window.Render()

    def set_point(self, index):
        try:
            x = float(self.point_inputs[index][0].text())
            y = float(self.point_inputs[index][1].text())
            z = float(self.point_inputs[index][2].text())
            self.point_coords[index] = [x, y, z]

            if self.point_checkboxes[index].isChecked():
                self.show_point(index)
            else:
                self.update_point_display(index)

            print(f"Point {index+1} set to: ({x}, {y}, {z})")
        except ValueError:
            print(f"Invalid input for Point {index+1}. Please enter valid numbers for coordinates.")

    def move_point(self, index, dx, dy, dz):
        new_position = [
            self.point_coords[index][0] + dx,
            self.point_coords[index][1] + dy,
            self.point_coords[index][2] + dz
        ]
        self.point_coords[index] = new_position
        self.update_point_display(index)
        print(f"Point {index+1} moved to: ({new_position[0]:.6f}, {new_position[1]:.6f}, {new_position[2]:.6f})")

    def move_point_screen(self, index, direction, step):
        move_vector = direction * step
        new_position = [
            self.point_coords[index][0] + move_vector[0],
            self.point_coords[index][1] + move_vector[1],
            self.point_coords[index][2] + move_vector[2]
        ]
        self.point_coords[index] = new_position
        self.update_point_display(index)
        print(f"Point {index+1} moved to: ({new_position[0]:.6f}, {new_position[1]:.6f}, {new_position[2]:.6f})")
        
    def update_all_points(self):
        for i in range(self.num_points):
            if self.point_actors[i]:
                self.update_point_display(i)

    def fit_camera_to_model(self):
        """STLモデルが画面にフィットするようにカメラの距離のみを調整"""
        if not self.model_bounds:
            return

        camera = self.vtk_viewer.renderer.GetActiveCamera()
        
        # モデルの中心を計算
        center = [(self.model_bounds[i] + self.model_bounds[i+1]) / 2 for i in range(0, 6, 2)]
        
        # モデルの大きさを計算
        size = max([
            self.model_bounds[1] - self.model_bounds[0],
            self.model_bounds[3] - self.model_bounds[2],
            self.model_bounds[5] - self.model_bounds[4]
        ])

        # 20%の余裕を追加
        size *= 1.4  # 1.0 + 0.2 + 0.2 = 1.4

        # 現在のカメラの方向ベクトルを保持
        current_position = np.array(camera.GetPosition())
        focal_point = np.array(center)  # モデルの中心を焦点に
        direction = current_position - focal_point
        
        # 方向ベクトルを正規化
        direction = direction / np.linalg.norm(direction)
        
        # 新しい位置を計算（方向は保持したまま距離のみ調整）
        new_position = focal_point + direction * size

        # カメラの位置を更新（方向は変えない）
        camera.SetPosition(new_position)
        camera.SetFocalPoint(*center)  # モデルの中心を見る

        # ビューポートのアスペクト比を取得
        viewport = self.vtk_viewer.renderer.GetViewport()
        aspect_ratio = (viewport[2] - viewport[0]) / (viewport[3] - viewport[1])

        # モデルが画面にフィットするようにパラレルスケールを設定
        if aspect_ratio > 1:  # 横長の画面
            camera.SetParallelScale(size / 2)
        else:  # 縦長の画面
            camera.SetParallelScale(size / (2 * aspect_ratio))

        self.vtk_viewer.renderer.ResetCameraClippingRange()
        self.vtk_viewer.render_window.Render()

    def handle_close(self, event):
        print("Window is closing...")
        self.vtk_widget.GetRenderWindow().Finalize()
        self.vtk_widget.close()
        event.accept()

    def get_screen_axes(self):
        camera = self.vtk_viewer.renderer.GetActiveCamera()
        view_up = np.array(camera.GetViewUp())
        forward = np.array(camera.GetDirectionOfProjection())
        
        # NumPyのベクトル演算を使用
        right = np.cross(forward, view_up)
        
        screen_right = right
        screen_up = view_up

        # ドット積の計算にNumPyを使用
        if abs(np.dot(screen_right, [1, 0, 0])) > abs(np.dot(screen_right, [0, 0, 1])):
            horizontal_axis = 'x'
            vertical_axis = 'z' if abs(np.dot(screen_up, [0, 0, 1])) > abs(np.dot(screen_up, [0, 1, 0])) else 'y'
        else:
            horizontal_axis = 'z'
            vertical_axis = 'y'

        return horizontal_axis, vertical_axis, screen_right, screen_up

    def export_stl_with_new_origin(self):
        """
        点1を原点として、STLファイルを新しい座標系で保存する。
        法線の計算を改善し、品質を保証する。
        """
        if not self.stl_actor or not any(self.point_actors):
            print("STL model or points are not set.")
            return

        file_path, _ = QFileDialog.getSaveFileName(self, "Save STL File", "", "STL Files (*.stl)")
        if not file_path:
            return

        try:
            # 現在のSTLモデルのポリデータを取得
            poly_data = self.stl_actor.GetMapper().GetInput()

            # 最初に選択されているポイントを新しい原点として使用
            origin_index = next(i for i, actor in enumerate(self.point_actors) if actor and actor.GetVisibility())
            origin_point = self.point_coords[origin_index]

            # Step 1: 選択されたポイントを原点とする平行移動
            translation = vtk.vtkTransform()
            translation.Translate(-origin_point[0], -origin_point[1], -origin_point[2])

            # Step 2: カメラの向きに基づいて座標系を変更
            camera = self.vtk_viewer.renderer.GetActiveCamera()
            camera_direction = np.array(camera.GetDirectionOfProjection())
            camera_up = np.array(camera.GetViewUp())
            camera_right = np.cross(camera_direction, camera_up)

            # 座標軸の設定
            new_x = -camera_direction  # カメラの向きの逆方向をX軸に
            new_y = camera_right      # カメラの右方向をY軸に
            new_z = camera_up         # カメラの上方向をZ軸に

            # 正規直交基底を確保
            new_x = new_x / np.linalg.norm(new_x)
            new_y = new_y / np.linalg.norm(new_y)
            new_z = new_z / np.linalg.norm(new_z)

            # 変換行列の作成
            rotation_matrix = np.column_stack((new_x, new_y, new_z))
            
            # 直交性を確保
            U, _, Vh = np.linalg.svd(rotation_matrix)
            rotation_matrix = U @ Vh

            # VTKの回転行列に変換
            vtk_matrix = vtk.vtkMatrix4x4()
            for i in range(3):
                for j in range(3):
                    vtk_matrix.SetElement(i, j, rotation_matrix[i, j])
            vtk_matrix.SetElement(3, 3, 1.0)

            # 回転変換を作成
            rotation = vtk.vtkTransform()
            rotation.SetMatrix(vtk_matrix)

            # Step 3: 変換を組み合わせる
            transform = vtk.vtkTransform()
            transform.PostMultiply()
            transform.Concatenate(translation)
            transform.Concatenate(rotation)

            # Step 4: 変換を適用
            transform_filter = vtk.vtkTransformPolyDataFilter()
            transform_filter.SetInputData(poly_data)
            transform_filter.SetTransform(transform)
            transform_filter.Update()

            # Step 5: トライアングルフィルタを適用して面の向きを統一
            triangle_filter = vtk.vtkTriangleFilter()
            triangle_filter.SetInputData(transform_filter.GetOutput())
            triangle_filter.Update()

            # Step 6: クリーンフィルタを適用
            clean_filter = vtk.vtkCleanPolyData()
            clean_filter.SetInputData(triangle_filter.GetOutput())
            clean_filter.Update()

            # Step 7: 法線の再計算
            normal_generator = vtk.vtkPolyDataNormals()
            normal_generator.SetInputData(clean_filter.GetOutput())
            
            # 法線計算の設定
            normal_generator.SetFeatureAngle(60.0)  # 特徴エッジの角度閾値
            normal_generator.SetSplitting(False)    # エッジでの分割を無効化
            normal_generator.SetConsistency(True)   # 法線の一貫性を確保
            normal_generator.SetAutoOrientNormals(True)  # 法線の自動配向
            normal_generator.SetComputePointNormals(True)  # 頂点法線の計算
            normal_generator.SetComputeCellNormals(True)   # 面法線の計算
            normal_generator.SetFlipNormals(False)  # 法線の反転を無効化
            normal_generator.NonManifoldTraversalOn()  # 非マニフォールドの処理を有効化
            
            # 法線の計算を実行
            normal_generator.Update()

            # Step 8: 変換後のデータを取得
            transformed_poly_data = normal_generator.GetOutput()

            # Step 9: 出力の品質チェック
            if transformed_poly_data.GetNumberOfPoints() == 0:
                raise ValueError("The transformed model has no vertices.")

            # STLファイルとして保存
            stl_writer = vtk.vtkSTLWriter()
            stl_writer.SetFileName(file_path)
            stl_writer.SetInputData(transformed_poly_data)
            stl_writer.SetFileTypeToBinary()  # バイナリ形式で保存
            stl_writer.Write()

            print(f"STL file with corrected normals in the new coordinate system has been saved: {file_path}")
            
            # メッシュの品質情報を出力
            print(f"Number of vertices: {transformed_poly_data.GetNumberOfPoints()}")
            print(f"Number of faces: {transformed_poly_data.GetNumberOfCells()}")

        except Exception as e:
            print(f"An error occurred: {str(e)}")
            import traceback
            traceback.print_exc()

    def handle_set_reset(self):
        sender = self.sender()
        is_set = sender.text() == "Set Point"

        for i, checkbox in enumerate(self.point_checkboxes):
            if checkbox.isChecked():
                if is_set:
                    try:
                        new_coords = [float(self.point_inputs[i][j].text()) for j in range(3)]
                        if new_coords != self.point_coords[i]:
                            self.point_coords[i] = new_coords
                            self.update_point_display(i)
                            print(f"Point {i+1} set to: {new_coords}")
                        else:
                            print(f"Point {i+1} coordinates unchanged")
                    except ValueError:
                        print(f"Invalid input for Point {i+1}. Please enter valid numbers.")
                else:  # Reset
                    self.reset_point_to_origin(i)

        if not is_set:
            self.update_all_points_size()

        self.vtk_viewer.render_window.Render()

    def get_mirrored_filename(self, original_path):
        dir_path = os.path.dirname(original_path)
        filename = os.path.basename(original_path)
        name, ext = os.path.splitext(filename)
        
        # ファイル名の先頭を確認して適切な新しいファイル名を生成
        if name.startswith('L_'):
            new_name = 'R_' + name[2:]
        elif name.startswith('l_'):
            new_name = 'r_' + name[2:]
        elif name.startswith('R_'):
            new_name = 'L_' + name[2:]
        elif name.startswith('r_'):
            new_name = 'l_' + name[2:]
        else:
            new_name = 'mirrored_' + name
        
        return os.path.join(dir_path, new_name + ext)


    def export_mirror_stl_xml(self):
        """STLファイルをY軸でミラーリングし、対応するXMLファイルも生成する"""
        if not hasattr(self, 'stl_file_path') or not self.stl_file_path:
            print("No STL file has been loaded.")
            return

        try:
            # 元のファイルのパスとファイル名を取得
            original_dir = os.path.dirname(self.stl_file_path)
            original_filename = os.path.basename(self.stl_file_path)
            name, ext = os.path.splitext(original_filename)

            # 新しいファイル名を生成（L/R反転）
            if name.startswith('L_'):
                new_name = 'R_' + name[2:]
            elif name.startswith('l_'):
                new_name = 'r_' + name[2:]
            elif name.startswith('R_'):
                new_name = 'L_' + name[2:]
            elif name.startswith('r_'):
                new_name = 'l_' + name[2:]
            else:
                new_name = 'mirrored_' + name

            # ミラー化したファイルのパスを設定
            mirrored_stl_path = os.path.join(original_dir, new_name + ext)
            mirrored_xml_path = os.path.join(original_dir, new_name + '.xml')

            # 既存ファイルのチェックとダイアログ表示
            if os.path.exists(mirrored_stl_path) or os.path.exists(mirrored_xml_path):
                existing_files = []
                if os.path.exists(mirrored_stl_path):
                    existing_files.append(f"STL: {mirrored_stl_path}")
                if os.path.exists(mirrored_xml_path):
                    existing_files.append(f"XML: {mirrored_xml_path}")
                
                msg = QMessageBox()
                msg.setIcon(QMessageBox.Question)
                msg.setText("Following files already exist:")
                msg.setInformativeText("\n".join(existing_files) + "\n\nDo you want to overwrite them?")
                msg.setWindowTitle("Confirm Overwrite")
                msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
                
                if msg.exec() == QMessageBox.No:
                    print("Operation cancelled by user")
                    return

            print("\nStarting mirror export process...")
            print(f"Source STL: {self.stl_file_path}")
            
            # STLの読み込みとミラー化
            reader = vtk.vtkSTLReader()
            reader.SetFileName(self.stl_file_path)
            reader.Update()

            # Y軸に対して反転する変換を作成
            transform = vtk.vtkTransform()
            transform.Scale(1, -1, 1)

            # 変換を適用
            transform_filter = vtk.vtkTransformPolyDataFilter()
            transform_filter.SetInputConnection(reader.GetOutputPort())
            transform_filter.SetTransform(transform)
            transform_filter.Update()

            # 頂点の巻き順を反転（法線の向きを修正）
            reverse_sense = vtk.vtkReverseSense()
            reverse_sense.SetInputConnection(transform_filter.GetOutputPort())
            reverse_sense.ReverseCellsOn()
            reverse_sense.ReverseNormalsOn()
            reverse_sense.Update()

            # 法線の再計算
            # AutoOrientNormalsは複雑な形状や複数ボディの場合に誤判定する可能性があるため無効化し、
            # ReverseSenseによる決定論的な反転結果を信頼する
            normal_generator = vtk.vtkPolyDataNormals()
            normal_generator.SetInputConnection(reverse_sense.GetOutputPort())
            normal_generator.ConsistencyOff()      # 入力の整合性を信頼する
            normal_generator.AutoOrientNormalsOff() # 自動判定を無効化
            normal_generator.ComputeCellNormalsOn()
            normal_generator.ComputePointNormalsOn()
            normal_generator.Update()

            # XMLファイルを確認し読み込む
            xml_path = os.path.splitext(self.stl_file_path)[0] + '.xml'
            xml_data = None
            if os.path.exists(xml_path):
                try:
                    tree = ET.parse(xml_path)
                    xml_data = tree.getroot()
                    print(f"Found and loaded XML file: {xml_path}")

                    # XMLから物理パラメータを取得
                    mass = float(xml_data.find(".//mass").get('value'))
                    volume = float(xml_data.find(".//volume").get('value'))
                    
                    # 重心位置を取得（center_of_mass要素から）
                    com_element = xml_data.find(".//center_of_mass")
                    if com_element is not None and com_element.text:
                        x, y, z = map(float, com_element.text.strip().split())
                        center_of_mass = [x, -y, z]  # Y座標のみを反転
                    else:
                        # inertialのorigin要素から取得
                        inertial_origin = xml_data.find(".//inertial/origin")
                        if inertial_origin is not None:
                            xyz = inertial_origin.get('xyz')
                            x, y, z = map(float, xyz.split())
                            center_of_mass = [x, -y, z]  # Y座標のみを反転
                        else:
                            print("Warning: No center of mass information found in XML")
                            center_of_mass = [0, 0, 0]

                    print(f"Original mass: {mass:.6f}, volume: {volume:.6f}")
                    print(f"Original center of mass: {center_of_mass}")

                    # 色情報を取得
                    color_element = xml_data.find(".//material/color")
                    if color_element is not None:
                        rgba_str = color_element.get('rgba')
                        hex_color = xml_data.find(".//material").get('name')
                    else:
                        rgba_str = "1.0 1.0 1.0 1.0"
                        hex_color = "#FFFFFF"

                except ET.ParseError as e:
                    print(f"Error parsing XML file: {xml_path}")
                    print(f"Error details: {str(e)}")
                    return

            # ミラー化したSTLを保存
            print(f"\nSaving mirrored STL to: {mirrored_stl_path}")
            writer = vtk.vtkSTLWriter()
            writer.SetFileName(mirrored_stl_path)
            writer.SetInputData(normal_generator.GetOutput())
            writer.Write()

            print("\nCalculating inertia tensor for mirrored model...")
            # イナーシャテンソルを計算
            inertia_tensor = self.calculate_inertia_tensor_for_mirrored(
                normal_generator.GetOutput(), mass, center_of_mass)

            # XMLファイルの内容を生成
            print(f"\nGenerating XML content...")
            urdf_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<urdf_part>
    <material name="{hex_color}">
        <color rgba="{rgba_str}" />
    </material>
    <link name="{new_name}">
        <visual>
            <origin xyz="{center_of_mass[0]:.6f} {center_of_mass[1]:.6f} {center_of_mass[2]:.6f}" rpy="0 0 0"/>
            <material name="{hex_color}" />
        </visual>
        <inertial>
            <origin xyz="{center_of_mass[0]:.6f} {center_of_mass[1]:.6f} {center_of_mass[2]:.6f}"/>
            <mass value="{mass:.12f}"/>
            <volume value="{volume:.12f}"/>
            {format_inertia_for_urdf(inertia_tensor)}
        </inertial>
        <center_of_mass>{center_of_mass[0]:.6f} {center_of_mass[1]:.6f} {center_of_mass[2]:.6f}</center_of_mass>
    </link>"""

            # ポイントデータを反転してコピー
            if xml_data is not None:
                print("Processing point data...")
                points = xml_data.findall('.//point')
                for point in points:
                    xyz_element = point.find('point_xyz')
                    if xyz_element is not None and xyz_element.text:
                        try:
                            x, y, z = map(float, xyz_element.text.strip().split())
                            mirrored_y = -y  # Y座標のみ反転
                            point_name = point.get('name')
                            urdf_content += f"""
    <point name="{point_name}" type="fixed">
        <point_xyz>{x:.6f} {mirrored_y:.6f} {z:.6f}</point_xyz>
    </point>"""
                            print(f"Processed point: {point_name}")
                        except ValueError:
                            print(f"Error processing point coordinates in XML")

            # 軸情報を取得して適用
            if xml_data is not None:
                print("Processing axis information...")
                axis_element = xml_data.find('.//joint/axis')
                if axis_element is not None:
                    axis_str = axis_element.get('xyz')
                    mirrored_axis = self.mirror_axis_value(axis_str)
                else:
                    mirrored_axis = "1 0 0"
            else:
                mirrored_axis = "1 0 0"

            urdf_content += f"""
    <joint>
        <axis xyz="{mirrored_axis}" />
    </joint>
</urdf_part>"""

            # XMLファイルを保存
            print(f"Saving XML to: {mirrored_xml_path}")
            with open(mirrored_xml_path, "w") as f:
                f.write(urdf_content)

            print("\nMirror export completed successfully:")
            print(f"STL file: {mirrored_stl_path}")
            print(f"XML file: {mirrored_xml_path}")

        except Exception as e:
            print(f"\nAn error occurred during mirror export: {str(e)}")
            traceback.print_exc()
        

    def calculate_inertia_tensor_for_mirrored(self, poly_data, mass, center_of_mass):
        """
        ミラーリングされたモデルの慣性テンソルを計算
        
        Args:
            poly_data: vtkPolyData オブジェクト
            mass: float 質量
            center_of_mass: list[float] 重心座標 [x, y, z]
        
        Returns:
            numpy.ndarray: 3x3 慣性テンソル行列
        """
        # 体積を計算
        mass_properties = vtk.vtkMassProperties()
        mass_properties.SetInputData(poly_data)
        mass_properties.Update()
        total_volume = mass_properties.GetVolume()

        # 実際の質量から密度を逆算
        density = mass / total_volume
        print(f"Calculated density: {density:.6f} from mass: {mass:.6f} and volume: {total_volume:.6f}")

        # Y軸ミラーリングの変換行列
        mirror_matrix = np.array([[1, 0, 0],
                                [0, -1, 0],
                                [0, 0, 1]])

        inertia_tensor = np.zeros((3, 3))
        num_cells = poly_data.GetNumberOfCells()
        print(f"Processing {num_cells} triangles for inertia tensor calculation...")

        for i in range(num_cells):
            cell = poly_data.GetCell(i)
            if cell.GetCellType() == vtk.VTK_TRIANGLE:
                # 三角形の頂点を取得（重心を原点とした座標系で）
                points = [np.array(cell.GetPoints().GetPoint(j)) - np.array(center_of_mass) for j in range(3)]
                
                # 三角形の面積と法線ベクトルを計算
                v1 = points[1] - points[0]
                v2 = points[2] - points[0]
                normal = np.cross(v1, v2)
                area = 0.5 * np.linalg.norm(normal)
                
                if area < 1e-10:  # 極小の三角形は無視
                    continue

                # 三角形の重心
                tri_centroid = np.mean(points, axis=0)

                # 三角形の局所的な慣性テンソルを計算
                covariance = np.zeros((3, 3))
                for p in points:
                    # 点をミラーリング
                    p = mirror_matrix @ p
                    r_squared = np.sum(p * p)
                    for a in range(3):
                        for b in range(3):
                            if a == b:
                                covariance[a, a] += (r_squared - p[a] * p[a]) * area / 12.0
                            else:
                                covariance[a, b] -= (p[a] * p[b]) * area / 12.0

                # ミラーリングされた重心
                tri_centroid = mirror_matrix @ tri_centroid
                
                # 平行軸の定理を適用
                r_squared = np.sum(tri_centroid * tri_centroid)
                parallel_axis_term = np.zeros((3, 3))
                for a in range(3):
                    for b in range(3):
                        if a == b:
                            parallel_axis_term[a, a] = r_squared * area
                        else:
                            parallel_axis_term[a, b] = tri_centroid[a] * tri_centroid[b] * area

                # 局所的な慣性テンソルと平行軸の項を合成
                local_inertia = covariance + parallel_axis_term
                
                # 全体の慣性テンソルに加算
                inertia_tensor += local_inertia

        # 密度を考慮して最終的な慣性テンソルを計算
        inertia_tensor *= density

        # Y軸反転による慣性テンソルの変換
        mirror_tensor = np.array([[1, -1, -1],
                                [-1, 1, 1],
                                [-1, 1, 1]])
        inertia_tensor = inertia_tensor * mirror_tensor

        # 数値誤差の処理
        threshold = 1e-10
        inertia_tensor[np.abs(inertia_tensor) < threshold] = 0.0

        print("\nCalculated Inertia Tensor:")
        print(inertia_tensor)
        return inertia_tensor



    def _load_points_from_xml(self, root):
        """XMLからポイントデータを読み込む"""
        points_with_data = set()
        # './/point'とすることで、どの階層にあるpointタグも検索できる
        points = root.findall('.//point')
        print(f"Found {len(points)} points in XML")

        for i, point in enumerate(points):
            if i >= len(self.point_checkboxes):  # 配列の境界チェック
                break

            xyz_element = point.find('point_xyz')
            if xyz_element is not None and xyz_element.text:
                try:
                    x, y, z = map(float, xyz_element.text.strip().split())
                    print(f"Loading point {i+1}: ({x}, {y}, {z})")

                    # 座標の設定
                    self.point_inputs[i][0].setText(f"{x:.6f}")
                    self.point_inputs[i][1].setText(f"{y:.6f}")
                    self.point_inputs[i][2].setText(f"{z:.6f}")
                    self.point_coords[i] = [x, y, z]
                    points_with_data.add(i)

                    # チェックボックスをオンにする
                    self.point_checkboxes[i].setChecked(True)

                    # ポイントの表示を設定
                    if self.point_actors[i] is None:
                        self.point_actors[i] = vtk.vtkAssembly()
                        self.create_point_coordinate(self.point_actors[i], [0, 0, 0])

                    self.point_actors[i].SetPosition(self.point_coords[i])
                    self.vtk_viewer.renderer.AddActor(self.point_actors[i])
                    self.point_actors[i].VisibilityOn()

                    print(f"Successfully loaded and visualized point {i+1}")

                except (ValueError, IndexError) as e:
                    print(f"Error processing point {i+1}: {e}")
                    continue

        if not points_with_data:
            print("No valid points found in XML")
        else:
            print(f"Successfully loaded {len(points_with_data)} points")

        return points_with_data

    def _apply_color_from_xml(self, root):
        """XMLからカラー情報を適用"""
        color_element = root.find(".//material/color")
        if color_element is not None:
            rgba_str = color_element.get('rgba')
            if rgba_str:
                try:
                    r, g, b, _ = map(float, rgba_str.split())
                    
                    self.color_inputs[0].setText(f"{r:.3f}")
                    self.color_inputs[1].setText(f"{g:.3f}")
                    self.color_inputs[2].setText(f"{b:.3f}")
                    
                    self.update_color_sample()
                    
                    if self.stl_actor:
                        self.stl_actor.GetProperty().SetColor(r, g, b)
                        self.vtk_viewer.render_window.Render()
                    
                    print(f"Material color loaded and applied: R={r:.3f}, G={g:.3f}, B={b:.3f}")
                except (ValueError, IndexError) as e:
                    print(f"Warning: Invalid color format in XML: {rgba_str}")
                    print(f"Error details: {e}")

    def _refresh_display(self):
        """表示を更新する"""
        self.vtk_viewer.renderer.ResetCamera()
        self.fit_camera_to_model()
        self.update_all_points_size()
        self.update_all_points()
        self.calculate_center_of_mass()
        self.vtk_viewer.renderer.ResetCameraClippingRange()
        self.vtk_viewer.render_window.Render()

    def load_parameters_from_xml(self, root):
        """XMLからパラメータを読み込んで設定する共通処理"""
        try:
            # まず全てのポイントをリセット
            for i in range(self.num_points):
                # 座標を0にリセット
                self.point_coords[i] = [0, 0, 0]
                for j in range(3):
                    self.point_inputs[i][j].setText("0.000000")
                # チェックボックスを外す
                self.point_checkboxes[i].setChecked(False)
                # 既存のアクターを削除
                if self.point_actors[i]:
                    self.point_actors[i].VisibilityOff()
                    self.vtk_viewer.renderer.RemoveActor(self.point_actors[i])
                    self.point_actors[i] = None

            has_parameters = False

            # 色情報の読み込み
            material_element = root.find(".//material")
            if material_element is not None:
                color_element = material_element.find("color")
                if color_element is not None:
                    rgba_str = color_element.get('rgba')
                    if rgba_str:
                        try:
                            r, g, b, _ = map(float, rgba_str.split())
                            # 色情報を入力フィールドに設定
                            self.color_inputs[0].setText(f"{r:.3f}")
                            self.color_inputs[1].setText(f"{g:.3f}")
                            self.color_inputs[2].setText(f"{b:.3f}")
                            
                            # カラーサンプルの更新
                            self.update_color_sample()
                            
                            # STLモデルに色を適用
                            if hasattr(self, 'stl_actor') and self.stl_actor:
                                self.stl_actor.GetProperty().SetColor(r, g, b)
                                self.vtk_viewer.render_window.Render()
                            
                            has_parameters = True
                            print(f"Loaded color: R={r:.3f}, G={g:.3f}, B={b:.3f}")
                        except ValueError as e:
                            print(f"Error parsing color values: {e}")

            # 軸情報の読み込み
            joint_element = root.find(".//joint/axis")
            if joint_element is not None:
                axis_str = joint_element.get('xyz')
                if axis_str:
                    try:
                        x, y, z = map(float, axis_str.split())
                        # 対応するラジオボタンを選択
                        if x == 1:
                            self.radio_buttons[0].setChecked(True)
                            print("Set axis to X (roll)")
                        elif y == 1:
                            self.radio_buttons[1].setChecked(True)
                            print("Set axis to Y (pitch)")
                        elif z == 1:
                            self.radio_buttons[2].setChecked(True)
                            print("Set axis to Z (yaw)")
                        else:
                            self.radio_buttons[3].setChecked(True)  # fixed
                            print("Set axis to fixed")
                        has_parameters = True
                    except ValueError as e:
                        print(f"Error parsing axis values: {e}")

            # 体積を取得して設定
            volume_element = root.find(".//volume")
            if volume_element is not None:
                volume = volume_element.get('value')
                self.volume_input.setText(volume)
                self.volume_checkbox.setChecked(True)
                has_parameters = True

            # 質量を取得して設定
            mass_element = root.find(".//mass")
            if mass_element is not None:
                mass = mass_element.get('value')
                self.mass_input.setText(mass)
                self.mass_checkbox.setChecked(True)
                has_parameters = True

            # 重心の取得と設定（優先順位付き）
            com_str = None
            
            # まず<center_of_mass>タグを確認
            com_element = root.find(".//center_of_mass")
            if com_element is not None and com_element.text:
                com_str = com_element.text.strip()
            
            # 次にinertialのorigin要素を確認
            if com_str is None:
                inertial_origin = root.find(".//inertial/origin")
                if inertial_origin is not None:
                    xyz = inertial_origin.get('xyz')
                    if xyz:
                        com_str = xyz
            
            # 最後にvisualのorigin要素を確認
            if com_str is None:
                visual_origin = root.find(".//visual/origin")
                if visual_origin is not None:
                    xyz = visual_origin.get('xyz')
                    if xyz:
                        com_str = xyz

            # 重心値を設定
            if com_str:
                try:
                    x, y, z = map(float, com_str.split())
                    self.com_input.setText(f"({x:.6f}, {y:.6f}, {z:.6f})")
                    print(f"Loaded center of mass: ({x:.6f}, {y:.6f}, {z:.6f})")
                    has_parameters = True
                except ValueError as e:
                    print(f"Error parsing center of mass values: {e}")

            # 慣性テンソルの設定
            inertia_element = root.find(".//inertia")
            if inertia_element is not None:
                inertia_str = ET.tostring(inertia_element, encoding='unicode')
                self.inertia_tensor_input.setText(inertia_str)
                has_parameters = True

            # ポイントデータの読み込み
            points = root.findall(".//point")
            for i, point in enumerate(points):
                if i >= len(self.point_checkboxes):
                    break

                xyz_element = point.find("point_xyz")
                if xyz_element is not None and xyz_element.text:
                    try:
                        x, y, z = map(float, xyz_element.text.strip().split())
                        # 座標値を設定
                        self.point_inputs[i][0].setText(f"{x:.6f}")
                        self.point_inputs[i][1].setText(f"{y:.6f}")
                        self.point_inputs[i][2].setText(f"{z:.6f}")
                        self.point_coords[i] = [x, y, z]
                        
                        # チェックボックスをオンにする
                        self.point_checkboxes[i].setChecked(True)
                        
                        # ポイントを表示
                        if self.point_actors[i] is None:
                            self.point_actors[i] = vtk.vtkAssembly()
                            self.create_point_coordinate(self.point_actors[i], [0, 0, 0])
                        self.point_actors[i].SetPosition(self.point_coords[i])
                        self.vtk_viewer.renderer.AddActor(self.point_actors[i])
                        self.point_actors[i].VisibilityOn()
                        
                        print(f"Loaded point {i+1}: ({x:.6f}, {y:.6f}, {z:.6f})")
                        has_parameters = True
                    except ValueError as e:
                        print(f"Error parsing point {i+1} coordinates: {e}")

            # カメラをリセット
            self.reset_camera()
            
            return has_parameters

        except Exception as e:
            print(f"Error loading parameters: {str(e)}")
            traceback.print_exc()
            return False

    def load_xml_file(self):
        """XMLファイルのみを読み込み、パラメータを反映する"""
        try:
            xml_path, _ = QFileDialog.getOpenFileName(self, "Open XML File", "", "XML Files (*.xml)")
            if not xml_path:
                return

            # XMLファイルを解析
            tree = ET.parse(xml_path)
            root = tree.getroot()
            
            print("Processing XML file...")

            # XMLからパラメータを読み込む
            has_parameters = self.load_parameters_from_xml(root)

            # パラメータがXMLに含まれていない場合のみ再計算を行う
            if not has_parameters:
                self.calculate_and_update_properties()

            # 全てのポイントをリセット
            print("Resetting all points...")
            for i in range(self.num_points):
                # テキストフィールドをクリア
                self.point_inputs[i][0].setText("0.000000")
                self.point_inputs[i][1].setText("0.000000")
                self.point_inputs[i][2].setText("0.000000")
                
                # 内部座標データをリセット
                self.point_coords[i] = [0, 0, 0]
                
                # チェックボックスを解除
                self.point_checkboxes[i].setChecked(False)
                
                # 3Dビューのポイントを非表示にし、アクターを削除
                if self.point_actors[i]:
                    self.point_actors[i].VisibilityOff()
                    self.vtk_viewer.renderer.RemoveActor(self.point_actors[i])
                    self.point_actors[i] = None
            
            print("All points have been reset")

            # データが設定されたポイントを追跡
            points_with_data = set()

            # 各ポイントの座標を読み込む
            points = root.findall('./point')
            print(f"Found {len(points)} points in XML")

            for i, point in enumerate(points):
                xyz_element = point.find('point_xyz')
                if xyz_element is not None and xyz_element.text:
                    try:
                        # 座標テキストを分割して数値に変換
                        x, y, z = map(float, xyz_element.text.strip().split())
                        print(f"Point {i+1}: {x}, {y}, z")

                        # テキストフィールドに値を設定
                        self.point_inputs[i][0].setText(f"{x:.6f}")
                        self.point_inputs[i][1].setText(f"{y:.6f}")
                        self.point_inputs[i][2].setText(f"{z:.6f}")
                        
                        # 内部の座標データを更新
                        self.point_coords[i] = [x, y, z]

                        # チェックボックスを有効化
                        self.point_checkboxes[i].setChecked(True)
                        
                        # ポイントの表示を設定
                        if self.point_actors[i] is None:
                            self.point_actors[i] = vtk.vtkAssembly()
                            self.create_point_coordinate(self.point_actors[i], [0, 0, 0])
                        
                        self.point_actors[i].SetPosition(self.point_coords[i])
                        self.vtk_viewer.renderer.AddActor(self.point_actors[i])
                        self.point_actors[i].VisibilityOn()
                        
                        points_with_data.add(i)
                        print(f"Set point {i+1} coordinates: x={x:.6f}, y={y:.6f}, z={z:.6f}")
                    except Exception as e:
                        print(f"Error processing point {i+1}: {e}")

            # STLモデルが読み込まれている場合のみ色を適用
            if hasattr(self, 'stl_actor') and self.stl_actor:
                color_element = root.find(".//material/color")
                if color_element is not None:
                    rgba_str = color_element.get('rgba')
                    if rgba_str:
                        try:
                            r, g, b, _ = map(float, rgba_str.split())
                            
                            # インプットフィールドに値を設定
                            self.color_inputs[0].setText(f"{r:.3f}")
                            self.color_inputs[1].setText(f"{g:.3f}")
                            self.color_inputs[2].setText(f"{b:.3f}")
                            
                            # カラーサンプルを更新
                            self.update_color_sample()
                            
                            # STLモデルに色を適用
                            self.stl_actor.GetProperty().SetColor(r, g, b)
                            self.vtk_viewer.render_window.Render()
                            
                            print(f"Material color loaded and applied: R={r:.3f}, G={g:.3f}, B={b:.3f}")
                        except (ValueError, IndexError) as e:
                            print(f"Warning: Invalid color format in XML: {rgba_str}")
                            print(f"Error details: {e}")

            # 軸情報の処理
            axis_element = root.find(".//axis")
            if axis_element is not None:
                xyz_str = axis_element.get('xyz')
                if xyz_str:
                    try:
                        x, y, z = map(float, xyz_str.split())
                        if x == 1:
                            self.radio_buttons[0].setChecked(True)
                        elif y == 1:
                            self.radio_buttons[1].setChecked(True)
                        elif z == 1:
                            self.radio_buttons[2].setChecked(True)
                    except ValueError:
                        print(f"Warning: Invalid axis format in XML: {xyz_str}")

            # 表示の更新
            if hasattr(self.vtk_viewer, 'renderer'):
                self.vtk_viewer.renderer.ResetCamera()
                self.update_all_points()
                
                # STLモデルが存在する場合、カメラをフィット
                if hasattr(self, 'stl_actor') and self.stl_actor:
                    self.fit_camera_to_model()
                    
                self.vtk_viewer.renderer.ResetCameraClippingRange()
                self.vtk_viewer.render_window.Render()

            print(f"XML file has been loaded: {xml_path}")
            print(f"Number of set points: {len(points_with_data)}")

        except Exception as e:
            print(f"An error occurred while loading the XML file: {str(e)}")
            traceback.print_exc()

    def refresh_view(self):
        """ビューの更新とカメラのフィッティングを行う"""
        if hasattr(self.vtk_viewer, 'renderer'):
            self.vtk_viewer.renderer.ResetCamera()
            self.update_all_points()
            # STLモデルが存在する場合、カメラをフィット
            if hasattr(self, 'stl_actor') and self.stl_actor:
                self.fit_camera_to_model()
            self.vtk_viewer.renderer.ResetCameraClippingRange()
            self.vtk_viewer.render_window.Render()

    def load_stl_with_xml(self):
        """STLファイルとXMLファイルを一緒に読み込む"""
        try:
            stl_path, _ = QFileDialog.getOpenFileName(self, "Open STL File", "", "STL Files (*.stl)")
            if not stl_path:
                return

            # STLファイルを読み込む
            self.show_stl(stl_path)

            # 対応するXMLファイルのパスを生成
            xml_path = os.path.splitext(stl_path)[0] + '.xml'

            if not os.path.exists(xml_path):
                print(f"Corresponding XML file not found: {xml_path}")
                return

            # XMLファイルを解析
            try:
                tree = ET.parse(xml_path)
                root = tree.getroot()
                
                # XMLからパラメータを読み込む
                has_parameters = self.load_parameters_from_xml(root)
                
                # パラメータがXMLに含まれていない場合のみ再計算を行う
                if not has_parameters:
                    self.calculate_and_update_properties()
                    
                # ポイントデータを読み込む
                points_with_data = self._load_points_from_xml(root)
                
                print(f"XML file loaded: {xml_path}")
                if points_with_data:
                    print(f"Loaded {len(points_with_data)} points")
                
                # 表示を更新
                self.refresh_view()

            except ET.ParseError:
                print(f"Error parsing XML file: {xml_path}")
            except Exception as e:
                print(f"Error processing XML file: {str(e)}")
                traceback.print_exc()

        except Exception as e:
            print(f"An error occurred while loading the file: {str(e)}")
            traceback.print_exc()

    def bulk_convert_l_to_r(self):
        """
        フォルダ内の'l_'または'L_'で始まるSTLファイルを処理し、
        対応する'r_'または'R_'ファイルを生成する。
        既存のファイルは上書きせずスキップする。
        """
        try:
            # フォルダ選択ダイアログを表示
            folder_path = QFileDialog.getExistingDirectory(
                self, "Select Folder for Bulk Conversion")
            if not folder_path:
                return

            print(f"Selected folder: {folder_path}")

            # 処理したファイルの数を追跡
            processed_count = 0
            skipped_count = 0

            # フォルダ内のすべてのSTLファイルを検索
            for file_name in os.listdir(folder_path):
                if file_name.lower().startswith(('l_', 'L_')) and file_name.lower().endswith('.stl'):
                    stl_path = os.path.join(folder_path, file_name)

                    # 新しいファイル名を生成
                    new_name = 'R_' + file_name[2:] if file_name.startswith('L_') else 'r_' + file_name[2:]
                    new_name_without_ext = os.path.splitext(new_name)[0]
                    new_stl_path = os.path.join(folder_path, new_name)
                    new_xml_path = os.path.splitext(new_stl_path)[0] + '.xml'

                    # 既存ファイルのチェック
                    if os.path.exists(new_stl_path) or os.path.exists(new_xml_path):
                        print(f"Skipping {file_name} - Target file(s) already exist")
                        skipped_count += 1
                        continue

                    print(f"Processing: {stl_path}")

                    try:
                        # STLファイルを読み込む
                        reader = vtk.vtkSTLReader()
                        reader.SetFileName(stl_path)
                        reader.Update()

                        # Y軸反転の変換を設定
                        transform = vtk.vtkTransform()
                        transform.Scale(1, -1, 1)

                        # 頂点を変換
                        transformer = vtk.vtkTransformPolyDataFilter()
                        transformer.SetInputConnection(reader.GetOutputPort())
                        transformer.SetTransform(transform)
                        transformer.Update()

                        # 頂点の巻き順を反転（法線の向きを修正）
                        reverse_sense = vtk.vtkReverseSense()
                        reverse_sense.SetInputConnection(transformer.GetOutputPort())
                        reverse_sense.ReverseCellsOn()
                        reverse_sense.ReverseNormalsOn()
                        reverse_sense.Update()

                        # 法線の再計算
                        # AutoOrientNormalsは複雑な形状や複数ボディの場合に誤判定する可能性があるため無効化し、
                        # ReverseSenseによる決定論的な反転結果を信頼する
                        normal_generator = vtk.vtkPolyDataNormals()
                        normal_generator.SetInputConnection(reverse_sense.GetOutputPort())
                        normal_generator.ConsistencyOff()      # 入力の整合性を信頼する
                        normal_generator.AutoOrientNormalsOff() # 自動判定を無効化
                        normal_generator.ComputeCellNormalsOn()
                        normal_generator.ComputePointNormalsOn()
                        normal_generator.Update()

                        # 対応するXMLファイルを探す
                        xml_path = os.path.splitext(stl_path)[0] + '.xml'
                        xml_data = None
                        if os.path.exists(xml_path):
                            try:
                                tree = ET.parse(xml_path)
                                xml_data = tree.getroot()
                                print(f"Found and loaded XML file: {xml_path}")

                                # XMLから物理パラメータを取得
                                mass = float(xml_data.find(".//mass").get('value'))
                                volume = float(xml_data.find(".//volume").get('value'))
                                
                                # 重心位置を取得（center_of_mass要素から）
                                com_element = xml_data.find(".//center_of_mass")
                                if com_element is not None and com_element.text:
                                    x, y, z = map(float, com_element.text.strip().split())
                                    center_of_mass = [x, -y, z]  # Y座標のみを反転
                                else:
                                    # inertialのorigin要素から取得
                                    inertial_origin = xml_data.find(".//inertial/origin")
                                    if inertial_origin is not None:
                                        xyz = inertial_origin.get('xyz')
                                        x, y, z = map(float, xyz.split())
                                        center_of_mass = [x, -y, z]  # Y座標のみを反転

                                # 色情報を取得
                                color_element = xml_data.find(".//material/color")
                                if color_element is not None:
                                    rgba_str = color_element.get('rgba')
                                    hex_color = xml_data.find(".//material").get('name')
                                else:
                                    rgba_str = "1.0 1.0 1.0 1.0"
                                    hex_color = "#FFFFFF"

                            except ET.ParseError:
                                print(f"Error parsing XML file: {xml_path}")
                                continue

                        # ミラー化したSTLを保存
                        writer = vtk.vtkSTLWriter()
                        writer.SetFileName(new_stl_path)
                        writer.SetInputData(normal_generator.GetOutput())
                        writer.Write()

                        # イナーシャテンソルを計算
                        inertia_tensor = self.calculate_inertia_tensor_for_mirrored(
                            normal_generator.GetOutput(), mass, center_of_mass)

                        # XMLファイルの内容を生成
                        urdf_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<urdf_part>
    <material name="{hex_color}">
        <color rgba="{rgba_str}" />
    </material>
    <link name="{new_name_without_ext}">
        <visual>
            <origin xyz="{center_of_mass[0]:.6f} {center_of_mass[1]:.6f} {center_of_mass[2]:.6f}" rpy="0 0 0"/>
            <material name="{hex_color}" />
        </visual>
        <inertial>
            <origin xyz="{center_of_mass[0]:.6f} {center_of_mass[1]:.6f} {center_of_mass[2]:.6f}"/>
            <mass value="{mass:.12f}"/>
            <volume value="{volume:.12f}"/>
            {format_inertia_for_urdf(inertia_tensor)}
        </inertial>
        <center_of_mass>{center_of_mass[0]:.6f} {center_of_mass[1]:.6f} {center_of_mass[2]:.6f}</center_of_mass>
    </link>"""

                        # ポイントデータを反転してコピー
                        if xml_data is not None:
                            points = xml_data.findall('.//point')
                            for point in points:
                                xyz_element = point.find('point_xyz')
                                if xyz_element is not None and xyz_element.text:
                                    try:
                                        x, y, z = map(float, xyz_element.text.strip().split())
                                        mirrored_y = -y  # Y座標のみ反転
                                        point_name = point.get('name')
                                        urdf_content += f"""
    <point name="{point_name}" type="fixed">
        <point_xyz>{x:.6f} {mirrored_y:.6f} {z:.6f}</point_xyz>
    </point>"""
                                    except ValueError:
                                        print(f"Error processing point coordinates in XML")

                        # 軸情報を取得して適用
                        if xml_data is not None:
                            axis_element = xml_data.find('.//joint/axis')
                            if axis_element is not None:
                                axis_str = axis_element.get('xyz')
                                mirrored_axis = self.mirror_axis_value(axis_str)
                            else:
                                mirrored_axis = "1 0 0"
                        else:
                            mirrored_axis = "1 0 0"

                        urdf_content += f"""
    <joint>
        <axis xyz="{mirrored_axis}" />
    </joint>
</urdf_part>"""

                        # XMLファイルを保存
                        with open(new_xml_path, "w") as f:
                            f.write(urdf_content)

                        processed_count += 1
                        print(f"Converted: {file_name} -> {new_name}")
                        print(f"Created XML: {new_xml_path}")

                    except Exception as e:
                        print(f"Error processing file {file_name}: {str(e)}")
                        traceback.print_exc()
                        continue

            # 処理完了メッセージ
            if processed_count > 0 or skipped_count > 0:
                print(f"\nBulk conversion completed.")
                print(f"Processed: {processed_count} files")
                print(f"Skipped: {skipped_count} files (already exist)")
            else:
                print("\nNo files were processed. Make sure there are STL files with 'l_' or 'L_' prefix in the selected folder.")

        except Exception as e:
            print(f"Error during bulk conversion: {str(e)}")
            traceback.print_exc()

    def mirror_axis_value(self, axis_str):
        """
        軸情報を左右反転する際の処理
        回転軸の向きは左右で変更しない
        
        Args:
            axis_str (str): "x y z" 形式の軸情報
        
        Returns:
            str: 変換後の軸情報
        """
        try:
            x, y, z = map(float, axis_str.split())
            # 軸の向きは変更せずにそのまま返す
            return f"{x:.1f} {y:.1f} {z:.1f}"
        except ValueError:
            print(f"Error parsing axis values: {axis_str}")
            return "1 0 0"  # デフォルト値


    def start_rotation_test(self):
        if not hasattr(self, 'stl_actor') or not self.stl_actor:
            return
            
        # 現在の変換行列を保存
        self.original_transform = vtk.vtkTransform()
        self.original_transform.DeepCopy(self.stl_actor.GetUserTransform() 
                                    if self.stl_actor.GetUserTransform() 
                                    else vtk.vtkTransform())
        
        self.test_rotation_angle = 0
        self.rotation_timer.start(16)  # 約60FPS

    def stop_rotation_test(self):
        self.rotation_timer.stop()
        
        # 元の位置に戻す
        if self.stl_actor and self.original_transform:
            self.stl_actor.SetUserTransform(self.original_transform)
            self.vtk_viewer.render_window.Render()

    def update_test_rotation(self):
        if not self.stl_actor:
            return
                
        # 選択された軸を確認
        axis_index = self.axis_group.checkedId()
        
        # fixedが選択されている場合（axis_index == 3）は何もしない
        if axis_index == 3:
            return
                
        # 以下は従来の処理
        rotation_axis = [0, 0, 0]
        rotation_axis[axis_index] = 1
        
        # 回転角度を更新
        self.test_rotation_angle += 2  # 1フレームあたり2度回転
        
        # 回転変換を作成
        transform = vtk.vtkTransform()
        transform.DeepCopy(self.original_transform)
        transform.RotateWXYZ(self.test_rotation_angle, *rotation_axis)
        
        # 変換を適用
        self.stl_actor.SetUserTransform(transform)
        self.vtk_viewer.render_window.Render()

    def update_color_sample(self):
        """カラーサンプルの表示を更新"""
        try:
            rgb_values = [min(255, max(0, int(float(input.text()) * 255))) 
                        for input in self.color_inputs]
            self.color_sample.setStyleSheet(
                f"background-color: rgb({rgb_values[0]},{rgb_values[1]},{rgb_values[2]}); "
                f"border: 1px solid black;"
            )

            # STLモデルに色を適用
            if hasattr(self, 'stl_actor') and self.stl_actor:
                rgb_normalized = [v / 255.0 for v in rgb_values]
                self.stl_actor.GetProperty().SetColor(*rgb_normalized)
                self.vtk_viewer.render_window.Render()

        except ValueError:
            pass

    def show_color_picker(self):
        """カラーピッカーを表示"""
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
            for i, component in enumerate([color.red(), color.green(), color.blue()]):
                self.color_inputs[i].setText(f"{component / 255:.3f}")
            
            if self.current_node:
                self.current_node.node_color = [
                    color.red() / 255.0,
                    color.green() / 255.0,
                    color.blue() / 255.0
                ]
                self.apply_color_to_stl()

    def apply_color_to_stl(self):
        """選択された色をSTLモデルに適用"""
        if not hasattr(self, 'stl_actor') or not self.stl_actor:
            print("No STL model has been loaded.")
            return
        
        try:
            # RGB値を取得（0-1の範囲）
            rgb_values = [float(input.text()) for input in self.color_inputs]
            
            # 値の範囲チェック
            rgb_values = [max(0.0, min(1.0, value)) for value in rgb_values]
            
            # STLモデルの色を変更
            self.stl_actor.GetProperty().SetColor(*rgb_values)
            self.vtk_viewer.render_window.Render()
            print(f"Applied color: RGB({rgb_values[0]:.3f}, {rgb_values[1]:.3f}, {rgb_values[2]:.3f})")
            
        except ValueError as e:
            print(f"Error: Invalid color value - {str(e)}")
        except Exception as e:
            print(f"Error applying color: {str(e)}")



    def process_mirror_properties(self, xml_data, reverse_output, density=1.0):
        """
        ミラーリングされたモデルの物理プロパティを処理する
        Args:
            xml_data: 元のXMLデータ
            reverse_output: 反転後のvtkPolyData
            density: デフォルトの密度（元のXMLに質量情報がない場合に使用）
        Returns:
            tuple: (volume, mass, center_of_mass, inertia_tensor)
        """
        # 体積を計算（新しいジオメトリから）
        mass_properties = vtk.vtkMassProperties()
        mass_properties.SetInputData(reverse_output)
        volume = mass_properties.GetVolume()

        # 質量を元のXMLから取得（ない場合は体積×密度で計算）
        if xml_data is not None:
            mass_element = xml_data.find(".//mass")
            if mass_element is not None:
                mass = float(mass_element.get('value'))
            else:
                mass = volume * density
        else:
            mass = volume * density

        # 重心を計算
        com_filter = vtk.vtkCenterOfMass()
        com_filter.SetInputData(reverse_output)
        com_filter.SetUseScalarsAsWeights(False)
        com_filter.Update()
        center_of_mass = list(com_filter.GetCenter())
        
        # Y座標のみを反転
        center_of_mass[1] = -center_of_mass[1]

        # 慣性テンソルを計算（質量を考慮）
        inertia_tensor = np.zeros((3, 3))
        poly_data = reverse_output
        num_cells = poly_data.GetNumberOfCells()

        # 実際の質量を使用して慣性テンソルを計算
        density_for_inertia = mass / volume  # 実際の質量から密度を逆算
        
        for i in range(num_cells):
            cell = poly_data.GetCell(i)
            if cell.GetCellType() == vtk.VTK_TRIANGLE:
                p1, p2, p3 = [np.array(cell.GetPoints().GetPoint(j)) for j in range(3)]
                centroid = (p1 + p2 + p3) / 3
                r = centroid - np.array(center_of_mass)
                area = 0.5 * np.linalg.norm(np.cross(p2 - p1, p3 - p1))

                # 慣性テンソルの計算
                inertia_tensor[0, 0] += area * (r[1]**2 + r[2]**2)
                inertia_tensor[1, 1] += area * (r[0]**2 + r[2]**2)
                inertia_tensor[2, 2] += area * (r[0]**2 + r[1]**2)
                inertia_tensor[0, 1] -= area * r[0] * r[1]
                inertia_tensor[0, 2] -= area * r[0] * r[2]
                inertia_tensor[1, 2] -= area * r[1] * r[2]

        # 対称性を利用して下三角を埋める
        inertia_tensor[1, 0] = inertia_tensor[0, 1]
        inertia_tensor[2, 0] = inertia_tensor[0, 2]
        inertia_tensor[2, 1] = inertia_tensor[1, 2]

        # 実際の質量に基づいて慣性テンソルをスケーリング
        inertia_tensor *= density_for_inertia

        return volume, mass, center_of_mass, inertia_tensor


class ResultDialog(QDialog):
    def __init__(self, stl_path: str, xml_path: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Export Complete")
        self.setModal(True)

        # ウィンドウサイズを大きく設定
        self.resize(400, 250)  # 幅を600に、高さを200に増加

        # レイアウトを作成
        layout = QVBoxLayout()
        layout.setSpacing(10)  # ウィジェット間の間隔を設定

        # メッセージラベルを作成
        title_label = QLabel("Following files have been saved:")
        title_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(title_label)

        # STLファイルパスを表示
        stl_label = QLabel(f"STL: {stl_path}")
        stl_label.setWordWrap(True)  # 長いパスの折り返しを有効化
        layout.addWidget(stl_label)

        # XMLファイルパスを表示
        xml_label = QLabel(f"XML: {xml_path}")
        xml_label.setWordWrap(True)  # 長いパスの折り返しを有効化
        layout.addWidget(xml_label)

        # スペーサーを追加
        layout.addSpacing(20)

        # Closeボタンを作成
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        close_button.setFixedWidth(100)

        # ボタンを中央に配置するための水平レイアウト
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(close_button)
        button_layout.addStretch()

        layout.addLayout(button_layout)

        self.setLayout(layout)

        # Enterキーでダイアログを閉じられるようにする
        close_button.setDefault(True)

def signal_handler(sig, frame):
    print("Ctrl+C detected, closing application...")
    QApplication.instance().quit()

if __name__ == "__main__":

    # Ctrl+Cのシグナルハンドラを設定
    signal.signal(signal.SIGINT, signal_handler)

    app = QApplication(sys.argv)
    apply_dark_theme(app)

    window = MainWindow()
    window.show()

    # タイマーを設定してシグナルを処理できるようにする
    timer = QTimer()
    timer.start(500)  # 500ミリ秒ごとにイベントループを中断
    timer.timeout.connect(lambda: None)  # ダミー関数を接続

    try:
        sys.exit(app.exec())
    except SystemExit:
        print("Exiting application...")
