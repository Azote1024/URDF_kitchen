import vtk
import os
import numpy as np

def process_stl_deterministic(input_path, output_path):
    reader = vtk.vtkSTLReader()
    reader.SetFileName(input_path)
    reader.Update()

    # 1. Mirror Geometry
    transform = vtk.vtkTransform()
    transform.Scale(1, -1, 1)

    transformer = vtk.vtkTransformPolyDataFilter()
    transformer.SetInputConnection(reader.GetOutputPort())
    transformer.SetTransform(transform)
    transformer.Update()

    # 2. Reverse Winding (Deterministic fix)
    reverse_sense = vtk.vtkReverseSense()
    reverse_sense.SetInputConnection(transformer.GetOutputPort())
    reverse_sense.ReverseCellsOn()   # Flip winding order
    reverse_sense.ReverseNormalsOn() # Flip normals to match new winding
    reverse_sense.Update()

    # 3. Compute Normals (WITHOUT AutoOrient)
    # We trust that step 2 resulted in correct orientation.
    normal_generator = vtk.vtkPolyDataNormals()
    normal_generator.SetInputConnection(reverse_sense.GetOutputPort())
    normal_generator.ComputeCellNormalsOn()
    normal_generator.ComputePointNormalsOn()
    normal_generator.AutoOrientNormalsOff() # Disable guessing
    normal_generator.ConsistencyOff()       # Disable consistency check (trust input)
    normal_generator.SplittingOff()         # Keep original topology
    normal_generator.Update()

    writer = vtk.vtkSTLWriter()
    writer.SetFileName(output_path)
    writer.SetInputData(normal_generator.GetOutput())
    writer.Write()

def main():
    input_file = r"c:\Users\nitro\Documents\GitHub\URDF_kitchen\memo\temp_test_data\l_arm_lower.stl"
    output_file = r"c:\Users\nitro\Documents\GitHub\URDF_kitchen\memo\temp_test_data\r_arm_lower_deterministic.stl"
    
    if not os.path.exists(input_file):
        print(f"Input file not found: {input_file}")
        return

    print(f"Processing {input_file}...")
    process_stl_deterministic(input_file, output_file)
    print(f"Saved to {output_file}")

if __name__ == "__main__":
    main()
