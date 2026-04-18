import maya.cmds as cmds

def clean_meshes(delete_history=True, center_pivot=True, freeze_transforms=False):
    mesh_shapes = cmds.ls(type="mesh", long=True) or []
    if not mesh_shapes:
        cmds.warning("No se encontraron meshes en la escena.")
        return

    mesh_transforms = set()

    for shape in mesh_shapes:
        parents = cmds.listRelatives(shape, parent=True, fullPath=True) or []
        for p in parents:
            mesh_transforms.add(p)

    if not mesh_transforms:
        cmds.warning("No se encontraron transforms de meshes.")
        return

    processed = 0

    for obj in sorted(mesh_transforms):
        if not cmds.objExists(obj):
            continue

        try:
            if delete_history:
                cmds.delete(obj, constructionHistory=True)

            if center_pivot:
                cmds.xform(obj, centerPivots=True)

            if freeze_transforms:
                cmds.makeIdentity(obj, apply=True, t=True, r=True, s=True, n=False)

            processed += 1

        except Exception as e:
            print("No se pudo procesar {}: {}".format(obj, e))

    cmds.inViewMessage(
        amg="Limpieza aplicada a {} mesh objects.".format(processed),
        pos="midCenter",
        fade=True
    )

clean_meshes(delete_history=True, center_pivot=True, freeze_transforms=False)