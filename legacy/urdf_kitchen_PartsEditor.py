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
from PySide6.QtWidgets import QApplication
from parts_editor import PartsEditorMainWindow

def main():
    app = QApplication(sys.argv)
    window = PartsEditorMainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
