# STLモデル反転時の法線反転問題に関する考察

## 現状の問題
`urdf_kitchen_PartsEditor.py` の `bulk_convert_l_to_r` や `export_mirror_stl_xml` 機能を使用してモデルをミラーリング（反転）した際、出力されたSTLモデルの一部の法線が内側を向いてしまう（反転してしまう）という問題が発生しています。

## 原因の考察

### 1. 座標系の反転と頂点の巻き順
現在の実装では、`vtkTransform` を使用して Y軸に対して `-1` のスケーリングを行っています。

```python
transform = vtk.vtkTransform()
transform.Scale(1, -1, 1)
```

3次元空間において、奇数個の軸を反転（負のスケールを適用）すると、座標系が「右手系」から「左手系」（あるいはその逆）に変化します。
STLなどの3Dモデルフォーマットでは、面の法線ベクトル（面の向き）は通常、頂点の定義順序（巻き順、Winding Order）によって決定されます（右手の法則）。

座標系が反転すると、幾何学的な形状は鏡像になりますが、頂点の巻き順も幾何学的に反転して解釈されるため、結果として法線ベクトルが本来の「外側」ではなく「内側」を向くことになります。

### 2. vtkPolyDataNormals の限界
現在のコードでは、この問題に対処するために `vtkPolyDataNormals` を使用しています。

```python
normal_generator = vtk.vtkPolyDataNormals()
normal_generator.SetInputData(transformer.GetOutput())
normal_generator.ConsistencyOn()
normal_generator.AutoOrientNormalsOn()
# ...
```

`AutoOrientNormalsOn()` は、閉じた曲面（Closed Surface）であれば、幾何学的な「外側」を計算して法線を修正しようとします。しかし、以下の理由により意図通りに機能しない場合があります：

*   **開いたメッシュ（Open Mesh）**: モデルが完全に閉じていない場合、「外側」の定義が曖昧になり、アルゴリズムが正しく判定できないことがあります。
*   **複雑な形状**: 自己交差や非マニフォールド形状が含まれる場合、計算が失敗することがあります。
*   **一貫性の誤認**: すべての法線が「一貫して内側」を向いている場合、`ConsistencyOn()` はそれを「整合性が取れている」と判断し、反転を行わない可能性があります（`AutoOrientNormals` がそれを補正しようとしますが、確実ではありません）。

## 解決策

最も確実な解決策は、幾何学的な推測に頼るのではなく、**「座標系を反転させたのだから、頂点の巻き順も明示的に反転させる」** という決定論的な処理を行うことです。

VTKにはこのためのフィルタ `vtkReverseSense` が用意されています。

### 修正方針
変換処理のパイプラインに `vtkReverseSense` を追加します。

1.  `vtkTransformPolyDataFilter` で形状を反転（Scale 1, -1, 1）。
2.  **`vtkReverseSense` を適用して、ポリゴンの頂点順序（Normals）を反転させる。**
3.  必要に応じて `vtkPolyDataNormals` で法線を再計算・平滑化する。

```python
# 1. 変換
transformer = vtk.vtkTransformPolyDataFilter()
# ...

# 2. 巻き順の反転 (追加)
reverse_sense = vtk.vtkReverseSense()
reverse_sense.SetInputConnection(transformer.GetOutputPort())
reverse_sense.ReverseCellsOn()  # 頂点順序（巻き順）を反転
reverse_sense.ReverseNormalsOn() # 法線も反転

# 3. 法線の再計算 (既存の処理へ接続)
normal_generator.SetInputConnection(reverse_sense.GetOutputPort())
```

これにより、モデルの形状（閉じた/開いた）に関わらず、数学的に正しい法線の向きが得られるはずです。
