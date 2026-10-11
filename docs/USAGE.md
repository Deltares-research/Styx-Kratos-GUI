# Usage

A typical session works through the modes from left to right: **Soil → Structures → Mesh →
Staged construction → Calculate → Results**.

## Building a model

- **Soil**: open **Modify soil layers**. **OK** checks the layers and rebuilds the geometry;
  **Cancel** restores the previous layers.
- **Material sets**: pick Fill, loose or dense sand, soft or stiff clay, or Bedrock from the
  **Default library** and click **Add to project**. You can edit each copy separately in
  **Properties…**. Interface presets apply strength reduction and permeability to the selected
  soil material. **OK** saves the project materials; **Cancel** discards your edits.
- **Structures**: **Create interface** adds a zero-thickness contact to the first sheet pile,
  so the wall can slide against the soil instead of being fixed to it. In the Selection
  explorer, the **Side** row chooses which faces get the interface (usually both, for a
  retaining wall). The **Contact** rows set the soil whose strength `R_inter` reduces, the
  virtual thickness, and the permeability. If the model has no sheet pile, the tool draws a
  free interface line through the soil instead. Interfaces are plane strain only, so the tool
  is not available in 3D.

## Meshing

Click **Mesh** to open the Gmsh properties: size, order, 3D algorithm, optimisation,
smoothing, curvature sampling and minimum size. Then choose **Apply and generate**.
<kbd>F9</kbd> meshes again with the saved settings. Check every soil layer you want to include
and give each one its own target size. The checked layers are meshed together, so their shared
surfaces use common nodes. **Refine**, **Coarsen** and **Reset local refinement** adjust the
mesh locally before it is generated.

## Calculating

**Calculate** (in the toolbar, or <kbd>F9</kbd> outside Mesh mode) meshes the project, writes
the deck into a new folder under `~/KratosGUI/runs`, and runs it with Kratos. Every run gets
its own folder. Nothing is overwritten and nothing is deleted. This needs Kratos, so see
[KRATOS_SETUP.md](KRATOS_SETUP.md) first.

## Results

The **Results** tab reads a run back from its folder, so you can also open runs from earlier
sessions (`results runs`, then `results open <n>`).

- **Contours**: choose a phase and a field in the Results panel or the **Choose results**
  window. You can switch between bands and smooth shading, choose a colour map, show the
  deformed mesh, and set **Limits** for the legend's minimum and maximum
  (`results range <min> <max>`).
- **Plot along the wall**: **Plot wall…** or `results plot` shows the bending moment, shear
  force, normal force, displacements and interface tractions against depth, with one panel
  per phase. **Save SVG** and **Save CSV** export the figure or its numbers.
- `results at <node>` prints every field at one node, `results csv` saves the field on screen,
  and `results zip` downloads the whole run folder.

## Scripting

Type commands in the command box at the bottom of the window. `run <file.py>` runs a Python
file that returns a `Project` and loads the result into the viewport. For an example, try
`run tests/models/excavation.py`.
