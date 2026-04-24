"""Maya PBR Wrangler.

A small Maya plugin inspired by Blender's Node Wrangler PBR setup workflow.
Select an object, choose PBR texture files, and the tool creates or updates an
Arnold aiStandardSurface material using the maps it can identify.
"""

from __future__ import annotations

import os
import re

import maya.cmds as cmds
import maya.mel as mel


PLUGIN_NAME = "Maya PBR Wrangler"
WINDOW_NAME = "mayaPbrWranglerWindow"


MAP_RULES = {
    "displacement": {
        "label": "Displacement",
        "socket": "Displacement",
        "tags": "disp displacement height",
        "colorspace": "Raw",
    },
    "base_color": {
        "label": "Base Color",
        "socket": "Base Color",
        "tags": "base basecolor diffuse diff albedo color col",
        "colorspace": "sRGB",
    },
    "subsurface_color": {
        "label": "Subsurface Color",
        "socket": "Subsurface Color",
        "tags": "sss subsurface",
        "colorspace": "sRGB",
    },
    "metallic": {
        "label": "Metallic",
        "socket": "Metallic",
        "tags": "metallic metalness metal mtl",
        "colorspace": "Raw",
    },
    "specular": {
        "label": "Specular",
        "socket": "Specular",
        "tags": "specular spec spc",
        "colorspace": "Raw",
    },
    "roughness": {
        "label": "Roughness",
        "socket": "Roughness",
        "tags": "rough roughness rgh",
        "colorspace": "Raw",
    },
    "gloss": {
        "label": "Gloss",
        "socket": "Roughness",
        "tags": "gloss glossy glossiness",
        "colorspace": "Raw",
        "invert_to": "roughness",
    },
    "normal": {
        "label": "Normal",
        "socket": "Normal",
        "tags": "normal nor nrm nrml norm",
        "colorspace": "Raw",
    },
    "bump": {
        "label": "Bump",
        "socket": "Normal",
        "tags": "bump bmp",
        "colorspace": "Raw",
    },
    "transmission": {
        "label": "Transmission",
        "socket": "Transmission",
        "tags": "transmission transparency",
        "colorspace": "Raw",
    },
    "emission": {
        "label": "Emission",
        "socket": "Emission",
        "tags": "emission emissive emit",
        "colorspace": "sRGB",
    },
    "alpha": {
        "label": "Alpha",
        "socket": "Alpha",
        "tags": "alpha opacity",
        "colorspace": "Raw",
    },
    "ambient_occlusion": {
        "label": "Ambient Occlusion",
        "socket": "Ambient Occlusion",
        "tags": "ao ambient occlusion",
        "colorspace": "Raw",
    },
}

NODE_WRANGLER_MATCH_ORDER = (
    "displacement",
    "base_color",
    "subsurface_color",
    "metallic",
    "specular",
    "roughness",
    "gloss",
    "normal",
    "bump",
    "transmission",
    "emission",
    "alpha",
    "ambient_occlusion",
)


def initializePlugin(plugin):
    """Maya plugin entry point."""
    del plugin
    cmds.evalDeferred(show)


def uninitializePlugin(plugin):
    """Maya plugin exit point."""
    del plugin
    if cmds.window(WINDOW_NAME, exists=True):
        cmds.deleteUI(WINDOW_NAME)


def show():
    """Show the tool window."""
    if cmds.window(WINDOW_NAME, exists=True):
        cmds.deleteUI(WINDOW_NAME)

    window = cmds.window(
        WINDOW_NAME,
        title=PLUGIN_NAME,
        sizeable=False,
        widthHeight=(360, 190),
    )
    cmds.columnLayout(adjustableColumn=True, rowSpacing=10, columnAttach=("both", 12))
    cmds.text(
        label="Selecciona un objeto, elige tus mapas PBR y Maya conectara lo que reconozca.",
        align="left",
        wordWrap=True,
        height=42,
    )
    cmds.separator(height=8, style="in")
    cmds.button(
        label="Crear material Arnold nuevo y aplicar texturas",
        height=38,
        command=lambda *_: create_material_from_selected_textures(),
    )
    cmds.button(
        label="Aplicar/cambiar texturas en el material del objeto",
        height=38,
        command=lambda *_: update_existing_material_from_selected_textures(),
    )
    cmds.separator(height=8, style="none")
    cmds.text(
        label="Soporta Base Color, Roughness, Metalness, Normal, Displace/Height, AO, Emission y Opacity.",
        align="left",
        wordWrap=True,
        height=36,
    )
    cmds.showWindow(window)


def create_material_from_selected_textures():
    selection = _selected_mesh_transforms()
    if not selection:
        _warn("Selecciona al menos un objeto mesh antes de crear el material.")
        return

    texture_paths = _pick_texture_files()
    if not texture_paths:
        return

    maps = _classify_texture_paths(texture_paths)
    if not maps:
        _warn("No pude reconocer ningun mapa por nombre de archivo.")
        return

    material, shading_group = _create_ai_standard_surface()
    _connect_maps_to_material(material, shading_group, maps)
    cmds.sets(selection, edit=True, forceElement=shading_group)
    _info("Material creado y aplicado: {0}".format(material))


def update_existing_material_from_selected_textures():
    selection = _selected_mesh_transforms()
    if not selection:
        _warn("Selecciona un objeto mesh con material asignado.")
        return

    material, shading_group = _material_from_object(selection[0])
    if not material or not shading_group:
        _warn("El objeto seleccionado no tiene un material compatible asignado.")
        return

    texture_paths = _pick_texture_files()
    if not texture_paths:
        return

    maps = _classify_texture_paths(texture_paths)
    if not maps:
        _warn("No pude reconocer ningun mapa por nombre de archivo.")
        return

    _connect_maps_to_material(material, shading_group, maps)
    _info("Texturas aplicadas al material existente: {0}".format(material))


def _selected_mesh_transforms():
    transforms = []
    for item in cmds.ls(selection=True, long=True) or []:
        if cmds.nodeType(item) == "mesh":
            parent = cmds.listRelatives(item, parent=True, fullPath=True) or []
            transforms.extend(parent)
        elif cmds.listRelatives(item, shapes=True, type="mesh", fullPath=True):
            transforms.append(item)
    return list(dict.fromkeys(transforms))


def _pick_texture_files():
    filters = "Image Files (*.exr *.tx *.tif *.tiff *.png *.jpg *.jpeg *.tga *.bmp);;All Files (*.*)"
    return cmds.fileDialog2(
        caption="Selecciona mapas PBR",
        fileMode=4,
        fileFilter=filters,
        okCaption="Cargar",
    ) or []


def _create_ai_standard_surface():
    _ensure_mtoa_loaded()
    material = cmds.shadingNode("aiStandardSurface", asShader=True, name="PBR_Arnold_MAT")
    shading_group = cmds.sets(
        renderable=True,
        noSurfaceShader=True,
        empty=True,
        name="{0}SG".format(material),
    )
    cmds.connectAttr("{0}.outColor".format(material), "{0}.surfaceShader".format(shading_group), force=True)
    return material, shading_group


def _material_from_object(transform):
    shapes = cmds.listRelatives(transform, shapes=True, fullPath=True, type="mesh") or []
    shading_groups = []
    for shape in shapes:
        shading_groups.extend(cmds.listConnections(shape, type="shadingEngine") or [])
    if not shading_groups:
        return None, None

    shading_group = shading_groups[0]
    materials = cmds.listConnections("{0}.surfaceShader".format(shading_group), source=True, destination=False) or []
    if not materials:
        return None, None
    return materials[0], shading_group


def _connect_maps_to_material(material, shading_group, maps):
    if "base_color" in maps:
        color_output = _file_out_color(maps["base_color"], "baseColor")
        if "ambient_occlusion" in maps:
            ao_output = _file_out_alpha(maps["ambient_occlusion"], "ao")
            multiply = cmds.shadingNode("multiplyDivide", asUtility=True, name="{0}_AO_multiply".format(material))
            cmds.setAttr("{0}.operation".format(multiply), 1)
            cmds.connectAttr(color_output, "{0}.input1".format(multiply), force=True)
            cmds.connectAttr(ao_output, "{0}.input2X".format(multiply), force=True)
            cmds.connectAttr(ao_output, "{0}.input2Y".format(multiply), force=True)
            cmds.connectAttr(ao_output, "{0}.input2Z".format(multiply), force=True)
            _connect_attr("{0}.output".format(multiply), material, ("baseColor", "color"))
        else:
            _connect_attr(color_output, material, ("baseColor", "color"))

    if "roughness" in maps:
        _connect_attr(_file_out_alpha(maps["roughness"], "roughness"), material, ("specularRoughness", "roughness"))

    if "gloss" in maps:
        reverse = cmds.shadingNode("reverse", asUtility=True, name="{0}_gloss_to_roughness".format(material))
        cmds.connectAttr(_file_out_alpha(maps["gloss"], "gloss"), "{0}.inputX".format(reverse), force=True)
        _connect_attr("{0}.outputX".format(reverse), material, ("specularRoughness", "roughness"))

    if "metallic" in maps:
        _connect_attr(_file_out_alpha(maps["metallic"], "metallic"), material, ("metalness", "metallic"))

    if "specular" in maps:
        _connect_attr(_file_out_alpha(maps["specular"], "specular"), material, ("specular", "specularWeight"))

    if "subsurface_color" in maps:
        _connect_attr(_file_out_color(maps["subsurface_color"], "subsurface"), material, ("subsurfaceColor",))

    if "transmission" in maps:
        _connect_attr(_file_out_alpha(maps["transmission"], "transmission"), material, ("transmission", "transmissionWeight"))

    if "normal" in maps:
        bump = cmds.shadingNode("bump2d", asUtility=True, name="{0}_normal".format(material))
        cmds.setAttr("{0}.bumpInterp".format(bump), 1)
        cmds.setAttr("{0}.bumpDepth".format(bump), 1.0)
        cmds.connectAttr(_file_out_alpha(maps["normal"], "normal"), "{0}.bumpValue".format(bump), force=True)
        _connect_attr("{0}.outNormal".format(bump), material, ("normalCamera",))

    if "bump" in maps and "normal" not in maps:
        bump = cmds.shadingNode("bump2d", asUtility=True, name="{0}_bump".format(material))
        cmds.setAttr("{0}.bumpInterp".format(bump), 0)
        cmds.setAttr("{0}.bumpDepth".format(bump), 0.1)
        cmds.connectAttr(_file_out_alpha(maps["bump"], "bump"), "{0}.bumpValue".format(bump), force=True)
        _connect_attr("{0}.outNormal".format(bump), material, ("normalCamera",))

    if "displacement" in maps:
        displacement = cmds.shadingNode("displacementShader", asShader=True, name="{0}_displacement".format(material))
        cmds.setAttr("{0}.scale".format(displacement), 0.1)
        cmds.connectAttr(_file_out_alpha(maps["displacement"], "displacement"), "{0}.displacement".format(displacement), force=True)
        cmds.connectAttr(
            "{0}.displacement".format(displacement),
            "{0}.displacementShader".format(shading_group),
            force=True,
        )

    if "emission" in maps:
        _connect_attr(_file_out_color(maps["emission"], "emission"), material, ("emissionColor",))
        if cmds.attributeQuery("emission", node=material, exists=True):
            cmds.setAttr("{0}.emission".format(material), 1.0)

    if "alpha" in maps:
        opacity = _file_out_alpha(maps["alpha"], "alpha")
        for channel in ("opacityR", "opacityG", "opacityB"):
            attr = "{0}.{1}".format(material, channel)
            if cmds.objExists(attr):
                cmds.connectAttr(opacity, attr, force=True)


def _file_out_color(path, role):
    file_node = _create_file_node(path, role)
    return "{0}.outColor".format(file_node)


def _file_out_alpha(path, role):
    file_node = _create_file_node(path, role)
    if cmds.objExists("{0}.alphaIsLuminance".format(file_node)):
        cmds.setAttr("{0}.alphaIsLuminance".format(file_node), True)
    return "{0}.outAlpha".format(file_node)


def _create_file_node(path, role):
    file_node = cmds.shadingNode("file", asTexture=True, isColorManaged=True, name="PBR_{0}_file".format(role))
    place2d = cmds.shadingNode("place2dTexture", asUtility=True, name="{0}_place2d".format(file_node))
    _connect_place2d(place2d, file_node)
    cmds.setAttr("{0}.fileTextureName".format(file_node), path, type="string")
    map_type = _classify_texture_paths([path]).keys()
    colorspace = "Raw"
    for key in map_type:
        colorspace = MAP_RULES[key]["colorspace"]
        break
    _set_color_space(file_node, colorspace)
    return file_node


def _connect_place2d(place2d, file_node):
    pairs = (
        ("coverage", "coverage"),
        ("translateFrame", "translateFrame"),
        ("rotateFrame", "rotateFrame"),
        ("mirrorU", "mirrorU"),
        ("mirrorV", "mirrorV"),
        ("stagger", "stagger"),
        ("wrapU", "wrapU"),
        ("wrapV", "wrapV"),
        ("repeatUV", "repeatUV"),
        ("offset", "offset"),
        ("rotateUV", "rotateUV"),
        ("noiseUV", "noiseUV"),
        ("vertexUvOne", "vertexUvOne"),
        ("vertexUvTwo", "vertexUvTwo"),
        ("vertexUvThree", "vertexUvThree"),
        ("vertexCameraOne", "vertexCameraOne"),
        ("outUV", "uv"),
        ("outUvFilterSize", "uvFilterSize"),
    )
    for src, dst in pairs:
        if cmds.objExists("{0}.{1}".format(place2d, src)) and cmds.objExists("{0}.{1}".format(file_node, dst)):
            cmds.connectAttr("{0}.{1}".format(place2d, src), "{0}.{1}".format(file_node, dst), force=True)


def _connect_attr(source_attr, target_node, target_attrs):
    for attr in target_attrs:
        target_attr = "{0}.{1}".format(target_node, attr)
        if cmds.objExists(target_attr):
            cmds.connectAttr(source_attr, target_attr, force=True)
            return True
    return False


def _classify_texture_paths(paths):
    classified = {}
    for map_type in NODE_WRANGLER_MATCH_ORDER:
        rule = MAP_RULES[map_type]
        tags = set(rule["tags"].split())
        for texture_path in paths:
            components = _split_into_node_wrangler_components(os.path.basename(texture_path))
            if tags.intersection(set(components)):
                classified[map_type] = texture_path
                break
    return classified


def _split_into_node_wrangler_components(filename):
    """Match Blender Node Wrangler's Principled Setup filename tokenizing."""
    name = os.path.splitext(filename)[0]
    name = "".join(char for char in name if not char.isdigit())
    name = re.sub(r"([a-z])([A-Z])", r"\g<1> \g<2>", name)
    for separator in ("_", ".", "-", "__", "--", "#"):
        name = name.replace(separator, " ")
    return [component.lower() for component in name.split(" ") if component]


def _set_color_space(file_node, color_space):
    attr = "{0}.colorSpace".format(file_node)
    if not cmds.objExists(attr):
        return
    try:
        cmds.setAttr(attr, color_space, type="string")
    except RuntimeError:
        pass


def _ensure_mtoa_loaded():
    if cmds.pluginInfo("mtoa", query=True, loaded=True):
        return
    try:
        cmds.loadPlugin("mtoa", quiet=True)
    except RuntimeError:
        _warn("No pude cargar mtoa/Arnold. Revisa que Arnold este instalado y habilitado.")


def _warn(message):
    cmds.warning("[{0}] {1}".format(PLUGIN_NAME, message))


def _info(message):
    mel.eval('print "[{0}] {1}\\n"'.format(PLUGIN_NAME, message.replace('"', '\\"')))


if __name__ == "__main__":
    show()
