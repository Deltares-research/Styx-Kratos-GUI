import os
from pathlib import Path
import pytest
from app import importer, gmsh_worker

def test_importer_creates_brep_from_step(tmp_path):
    # Create a small valid STEP file
    step_file = tmp_path / "test.step"
    
    import gmsh
    gmsh.initialize()
    try:
        # Create a valid STEP file using gmsh itself
        gmsh.model.occ.addBox(0, 0, 0, 1, 1, 1)
        gmsh.model.occ.synchronize()
        gmsh.write(str(step_file))
        gmsh.clear()

        res = importer.process_import(str(step_file), ".step")
        assert res["volumes"] == 1
        assert "brep_path" in res
        assert os.path.exists(res["brep_path"])
        # Bounding box of the tetrahedron (0..1 in x, y, z)
        xmin, ymin, zmin, xmax, ymax, zmax = res["bbox"]
        # The bounding box checks might have small tolerance errors, so use approx
        assert xmin == pytest.approx(0.0, abs=1e-5)
        assert xmax == pytest.approx(1.0, abs=1e-5)
        assert zmin == pytest.approx(0.0, abs=1e-5)
        assert zmax == pytest.approx(1.0, abs=1e-5)
    finally:
        gmsh.finalize()
