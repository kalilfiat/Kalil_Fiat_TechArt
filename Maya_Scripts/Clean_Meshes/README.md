# Clean Meshes (Maya Script)

Simple Python script for Autodesk Maya that performs basic cleanup on all mesh objects in the scene.

## Features

* Deletes construction history
* Centers pivots
* Works only on mesh geometry (safe for rigs, lights, cameras, etc.)

## Usage

1. Open **Maya**
2. Open **Script Editor**
3. Switch to the **Python** tab
4. Copy and paste the script below
5. Press **Run**

The script will process all mesh objects in the scene.

## Script

```python
import maya.cmds as cmds

mesh_shapes = cmds.ls(type="mesh", long=True) or []
print("Mesh shapes found:", mesh_shapes)

mesh_transforms = set()
for shape in mesh_shapes:
    parents = cmds.listRelatives(shape, parent=True, fullPath=True) or []
    for p in parents:
        mesh_transforms.add(p)

print("Transforms found:", sorted(mesh_transforms))

for obj in sorted(mesh_transforms):
    print("Processing:", obj)
    cmds.delete(obj, constructionHistory=True)
    cmds.xform(obj, centerPivots=True)

print("Done")
```

## Notes

* Only affects objects with mesh shapes
* Safe for modeling workflows
* Does nothing if no meshes are found
* Outputs debug info in Script Editor

## Optional

To make it easier to use, you can create a shelf button:

```python
import maya.cmds as cmds

# paste main script here or import it
```

## License

Free to use and modify.
