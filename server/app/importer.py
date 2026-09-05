import math
import os
import uuid
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / ".data"

def process_import(filepath: str, extension: str) -> dict:
    """Run inside the gmsh worker. Merges the file, ensures it's a solid, and saves a .brep.
    
    Returns:
        dict: {"brep_path": str, "volumes": int, "bbox": [xmin, ymin, zmin, xmax, ymax, zmax]}
    """
    import gmsh
    
    DATA_DIR.mkdir(exist_ok=True)
    
    gmsh.clear()
    gmsh.model.add("import_temp")
    
    try:
        gmsh.merge(filepath)
    except Exception as e:
        raise RuntimeError(f"Gmsh failed to merge file: {e}")
        
    ext = extension.lower()
    if ext in (".stl", ".obj"):
        # We must recover topology from the triangulated surface mesh
        # Classify surfaces by an angle (e.g., 40 degrees)
        gmsh.model.mesh.classifySurfaces(40 * math.pi / 180, True, True, math.pi)
        # Create geometry from the classified mesh
        gmsh.model.mesh.createGeometry()
        # Create topology (volumes from closed surfaces)
        gmsh.model.occ.synchronize()
        gmsh.model.mesh.createTopology()
        
    gmsh.model.occ.synchronize()
    
    volumes = gmsh.model.getEntities(3)
    if not volumes:
        raise ValueError("Imported model contains no 3D volumes. Ensure the file contains solid geometry, not just surfaces.")
        
    # Get bounding box of all volumes
    boxes = [gmsh.model.getBoundingBox(3, tag) for _, tag in volumes]
    bbox = (
        min(b[0] for b in boxes), min(b[1] for b in boxes), min(b[2] for b in boxes),
        max(b[3] for b in boxes), max(b[4] for b in boxes), max(b[5] for b in boxes),
    )
    
    brep_filename = f"{uuid.uuid4().hex}.brep"
    brep_path = DATA_DIR / brep_filename
    
    # Export the OCC geometry as a BREP file so it can be re-imported cheaply during build.py
    gmsh.write(str(brep_path))
    
    return {
        "brep_path": str(brep_path),
        "volumes": len(volumes),
        "bbox": bbox
    }
