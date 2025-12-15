
import sys
import os
import unittest
import numpy as np
import vtk

# Add the root directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.math_utils import calculate_inertia_tensor, format_inertia_for_urdf

class TestMathUtils(unittest.TestCase):
    def test_calculate_inertia_tensor_cube(self):
        # Create a cube source
        cube = vtk.vtkCubeSource()
        cube.SetXLength(1.0)
        cube.SetYLength(1.0)
        cube.SetZLength(1.0)
        cube.Update()
        
        poly_data = cube.GetOutput()
        
        # Density = 1.0
        density = 1.0
        # Center of mass = (0, 0, 0)
        center_of_mass = [0.0, 0.0, 0.0]
        
        inertia_tensor = calculate_inertia_tensor(poly_data, density, center_of_mass)
        
        # For a cube of side a=1 and mass M=1 (since vol=1, den=1)
        # Ixx = Iyy = Izz = (1/6) * M * a^2 = 1/6 = 0.166666...
        expected_val = 1.0 / 6.0
        
        self.assertIsNotNone(inertia_tensor)
        self.assertAlmostEqual(inertia_tensor[0, 0], expected_val, places=4)
        self.assertAlmostEqual(inertia_tensor[1, 1], expected_val, places=4)
        self.assertAlmostEqual(inertia_tensor[2, 2], expected_val, places=4)
        
        # Off-diagonal elements should be 0
        self.assertAlmostEqual(inertia_tensor[0, 1], 0.0, places=4)
        self.assertAlmostEqual(inertia_tensor[0, 2], 0.0, places=4)
        self.assertAlmostEqual(inertia_tensor[1, 2], 0.0, places=4)

    def test_format_inertia_for_urdf(self):
        inertia_tensor = np.array([
            [1.0, 0.1, 0.2],
            [0.1, 2.0, 0.3],
            [0.2, 0.3, 3.0]
        ])
        
        urdf_str = format_inertia_for_urdf(inertia_tensor)
        expected_str = '<inertia ixx="1.00000000" ixy="0.10000000" ixz="0.20000000" iyy="2.00000000" iyz="0.30000000" izz="3.00000000"/>'
        self.assertEqual(urdf_str, expected_str)

if __name__ == '__main__':
    unittest.main()
