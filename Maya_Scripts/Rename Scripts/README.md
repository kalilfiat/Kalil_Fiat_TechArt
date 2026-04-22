# Maya Naming Tools

Simple MEL scripts for adding naming prefixes to meshes and materials in Autodesk Maya.

## Included Scripts

### 1. Add SM_ Prefix to Meshes
Renames all mesh objects in the Outliner with the prefix:

SM_

Example:

Cube → SM_Cube  
Object01 → SM_Object01

Objects that already have the prefix are ignored.

---

### 2. Add M_ Prefix to Materials
Renames all user materials in the scene with the prefix:

M_

Example:

Metal → M_Metal  
Wood → M_Wood

Default Maya materials such as lambert1 are ignored.

---

## Installation / Usage

1. Open the script file.
2. Copy the MEL code.
3. Paste it into Maya Script Editor (MEL tab).
4. Select the code.
5. Middle-mouse drag it to a Shelf to create a button.
6. Click the button to run.

---

## Notes

- Works on the current scene.
- Existing prefixed names are skipped.
- Use carefully in scenes that depend on strict naming conventions.