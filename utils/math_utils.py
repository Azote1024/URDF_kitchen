import numpy as np
import vtk
from utils.urdf_kitchen_logger import setup_logger

logger = setup_logger(__name__)

def calculate_inertia_tensor(poly_data, density, center_of_mass):
    """
    三角形メッシュの慣性テンソルを計算する。
    重心位置を考慮し、正確なイナーシャを算出する。
    
    Args:
        poly_data (vtk.vtkPolyData): 対象のポリデータ
        density (float): 密度
        center_of_mass (list or np.ndarray): 重心座標 [x, y, z]
        
    Returns:
        numpy.ndarray: 3x3の慣性テンソル行列
        None: エラーが発生した場合
    """
    if not poly_data:
        logger.warning("No poly_data provided for inertia calculation.")
        return None

    # 三角形化フィルタを適用して、すべてのセルを三角形にする
    triangle_filter = vtk.vtkTriangleFilter()
    triangle_filter.SetInputData(poly_data)
    triangle_filter.Update()
    poly_data = triangle_filter.GetOutput()

    # 慣性テンソルの初期化
    # Covariance matrix terms (C_xx = integral(x^2 dV), etc.)
    C = np.zeros((3, 3))
    
    num_cells = poly_data.GetNumberOfCells()
    logger.debug(f"Processing {num_cells} triangles for inertia calculation...")
    
    for i in range(num_cells):
        cell = poly_data.GetCell(i)
        # points relative to COM (so origin is COM)
        pts = [np.array(cell.GetPoints().GetPoint(j)) - center_of_mass for j in range(3)]
        
        # Signed volume of tetrahedron (origin, p0, p1, p2) * 6
        # det = dot(p0, cross(p1, p2))
        det = np.dot(pts[0], np.cross(pts[1], pts[2]))
        
        # Contribution to covariance
        # Formula for tetrahedron with vertices (0, p0, p1, p2):
        # integral(x_a * x_b) dV = det / 120 * sum_{j,k} (1 + delta_jk) * p_j[a] * p_k[b]
        
        for a in range(3):
            for b in range(a, 3):
                val = 0.0
                for j in range(3):
                    for k in range(3):
                        factor = 2.0 if j == k else 1.0
                        val += factor * pts[j][a] * pts[k][b]
                
                term = (det / 120.0) * val
                C[a, b] += term
                if a != b:
                    C[b, a] += term

    # Convert Covariance to Inertia Tensor
    # I_xx = C_yy + C_zz
    # I_xy = -C_xy
    inertia_tensor = np.zeros((3, 3))
    inertia_tensor[0, 0] = C[1, 1] + C[2, 2]
    inertia_tensor[1, 1] = C[0, 0] + C[2, 2]
    inertia_tensor[2, 2] = C[0, 0] + C[1, 1]
    
    inertia_tensor[0, 1] = inertia_tensor[1, 0] = -C[0, 1]
    inertia_tensor[0, 2] = inertia_tensor[2, 0] = -C[0, 2]
    inertia_tensor[1, 2] = inertia_tensor[2, 1] = -C[1, 2]

    # 密度を考慮して最終的な慣性テンソルを計算
    inertia_tensor *= density

    # 数値誤差の処理
    threshold = 1e-10
    for i in range(3):
        for j in range(3):
            if abs(inertia_tensor[i, j]) < threshold:
                inertia_tensor[i, j] = 0.0

    # 対称性の確認と強制
    inertia_tensor = 0.5 * (inertia_tensor + inertia_tensor.T)
    
    # 対角成分が正であることを確認
    if not all(inertia_tensor[i, i] > 0 for i in range(3)):
        logger.warning("Negative diagonal elements detected in inertia tensor!")
        for i in range(3):
            if inertia_tensor[i, i] <= 0:
                logger.info(f"Fixing negative diagonal element: {inertia_tensor[i, i]} -> {abs(inertia_tensor[i, i])}")
                inertia_tensor[i, i] = abs(inertia_tensor[i, i])

    return inertia_tensor

def format_inertia_for_urdf(inertia_tensor):
    """
    慣性テンソルをURDFフォーマットの文字列に変換する
    
    Args:
        inertia_tensor (numpy.ndarray): 3x3の慣性テンソル行列
    
    Returns:
        str: URDF形式の慣性テンソル文字列
    """
    # 値が非常に小さい場合は0とみなす閾値
    threshold = 1e-10

    # 対角成分
    ixx = inertia_tensor[0][0] if abs(inertia_tensor[0][0]) > threshold else 0
    iyy = inertia_tensor[1][1] if abs(inertia_tensor[1][1]) > threshold else 0
    izz = inertia_tensor[2][2] if abs(inertia_tensor[2][2]) > threshold else 0
    
    # 非対角成分
    ixy = inertia_tensor[0][1] if abs(inertia_tensor[0][1]) > threshold else 0
    ixz = inertia_tensor[0][2] if abs(inertia_tensor[0][2]) > threshold else 0
    iyz = inertia_tensor[1][2] if abs(inertia_tensor[1][2]) > threshold else 0

    return f'<inertia ixx="{ixx:.8f}" ixy="{ixy:.8f}" ixz="{ixz:.8f}" iyy="{iyy:.8f}" iyz="{iyz:.8f}" izz="{izz:.8f}"/>'
