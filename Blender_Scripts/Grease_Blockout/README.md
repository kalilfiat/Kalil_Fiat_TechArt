!\[ImagePreview](./assets/image/GreaseBlockoutThumbnail.png)



\# Grease Blockout v1.0



A procedural Blender addon written in \*\*Python\*\* designed to generate rough blockout meshes directly from Grease Pencil drawings for fast concepting, early modeling, and Technical Art workflows.



\## Problem This Solves (Production Context)



Early blockout is often slower than it should be.



Artists frequently sketch ideas in 2D, then rebuild those forms manually as simple 3D volumes just to explore proportions, silhouettes, or composition.



That introduces repetitive setup work during the phase where iteration should be fastest.



\*\*Grease Blockout reduces sketch-to-volume generation to one-click operations.\*\*



It allows Grease Pencil drawings to become rough 3D masses instantly, helping artists move from idea to spatial blockout without interrupting creative flow.



Useful for concepting, environment planning, character massing, and exploratory Technical Art workflows.



\---



\## Main Features



\### Sketch To Mesh Generation



Convert closed Grease Pencil drawings into 3D blockout meshes.



Features include:



\- Adjustable thickness  

\- Depth direction control  

\- Automatic mesh generation from active sketch layer  

\- Automatic organization in target collection



Example:



```text

2D Sketch Shape

↓

3D Blockout Mesh

```



\---



\### Symmetry Tools



Optional mirrored generation across:



\- X Axis  

\- Y Axis  

\- Z Axis



Useful for symmetrical forms and fast iteration.



\---



\### Voxel Remesh Integration



Optional automatic voxel remesh generation.



Includes presets:



\- Coarse  

\- Medium  

\- Fine



Can also be applied manually after generation.



This helps turn raw extruded forms into more unified blockout masses.



\---



\### Sketch Layer Workflow



Drawing management tools include:



\- New Blank Sketch Layer  

\- Clear Current Sketch  

\- Clear All Sketches  

\- Replace Same Sketch Mesh



Allows iterative blockout exploration while keeping source sketches organized.



\---



\### Grid Snap



Snap Grease Pencil strokes to configurable world grid.



Useful for:



\- Architectural blockouts  

\- Modular planning  

\- Cleaner proportions  

\- Technical layouts



\---



\### Random Soft Material Assignment



Optional random soft color assignment for generated meshes.



Useful for quick visual separation between masses.



\---



\## Technical Design Notes



This tool was designed around several production concerns:



\### 1. Non-Destructive Sketch Workflow



Grease Pencil drawings remain the editable source.



Generated meshes are derived outputs, not destructive conversions.



\---



\### 2. Source Tracking



Generated meshes store:



\- Source drawing object  

\- Source layer  

\- Source frame



This enables mesh replacement and controlled iteration.



\---



\### 3. Collection Organization



Generated geometry is automatically organized inside a dedicated collection.



Avoids scene clutter during rapid exploration.



\---



\### 4. Replace Logic



When enabled:



```text

Same sketch

↓

Replaces previous generated mesh

```



Prevents duplicate buildup while iterating.



\---



\### 5. Modular Architecture



The addon is separated into systems for:



\- Drawing management  

\- Mesh generation  

\- Symmetry  

\- Remeshing  

\- Grid snapping  

\- UI



Designed for future additions such as:



\- Multi-layer mass generation  

\- Mirror drawing  

\- Boolean union blockouts  

\- Sculpt-ready mode  

\- Geometry Nodes extensions



\---



\## Installation and Usage



1\. Open Blender  

2\. Go to Edit > Preferences > Add-ons  

3\. Click Install  

4\. Select `grease\_blockout.py`  

5\. Enable the addon  

6\. Open:



```text

View3D > Sidebar > Blockout

```



\---



\## Available Tools



\- Create / Activate Draw Object  

\- Draw Mode  

\- Generate Mesh  

\- New Blank Sketch Layer  

\- Clear Current Sketch  

\- Clear All Sketches  

\- Snap Active Sketch To Grid  

\- Apply Voxel Remesh



\---



\## Blockout Controls



Settings available:



\- Thickness  

\- Direction  

\- Symmetry  

\- Grid Size  

\- Voxel Size  

\- Mesh Prefix  

\- Auto Remesh  

\- Random Soft Color  

\- Replace Same Sketch Mesh



\---



\## Pipeline Notes



Recommended for workflows involving:



\- Blender  

\- Grease Pencil blockouts  

\- Technical Art prototyping  

\- Environment planning  

\- Character massing  

\- Early concept development



\---



\## License



Free to use and modify.

