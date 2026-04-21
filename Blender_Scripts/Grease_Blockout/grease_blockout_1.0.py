bl_info = {
    "name": "Grease Blockout",
    "author": "Codex",
    "version": (1, 0, 0),
    "blender": (5, 1, 0),
    "location": "View3D > Sidebar > Blockout",
    "description": "Create rough blockout meshes from Grease Pencil drawings.",
    "category": "Object",
}

import colorsys
import random
import re

import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, PointerProperty, StringProperty
from bpy.types import Operator, Panel, PropertyGroup
from mathutils import Matrix, Vector


ADDON_PREFIX = "GBM"
DEFAULT_COLLECTION_NAME = "Blockout_Masses"
DEFAULT_GP_NAME = "Blockout_Draw"
DEFAULT_LAYER_PREFIX = "Sketch"
MASS_MATERIAL_NAME = "Blockout_Mass_Material"
GP_OBJECT_TYPES = {"GREASEPENCIL", "GPENCIL"}
PROP_HELPER = f"{ADDON_PREFIX}_helper"
PROP_GENERATED = f"{ADDON_PREFIX}_generated"
PROP_SOURCE = f"{ADDON_PREFIX}_source"
PROP_SOURCE_LAYER = f"{ADDON_PREFIX}_source_layer"
PROP_SOURCE_FRAME = f"{ADDON_PREFIX}_source_frame"
LEGACY_SETTING_KEYS = ("use_voxel_remesh", "smooth_shading")
REMESH_PRESETS = {
    "COARSE": 0.25,
    "MEDIUM": 0.12,
    "FINE": 0.05,
}


class GBM_Settings(PropertyGroup):
    target_collection: PointerProperty(
        name="Target Collection",
        type=bpy.types.Collection,
        description="Collection where generated blockout meshes will be stored",
    )

    thickness: FloatProperty(
        name="Thickness",
        description="Depth of the generated mesh along the drawing plane normal",
        default=0.5,
        min=0.001,
        soft_max=5.0,
        unit="LENGTH",
    )

    depth_direction: EnumProperty(
        name="Direction",
        description="Direction where thickness is added relative to the drawing plane",
        items=(
            ("CENTER", "Centered", "Add depth evenly on both sides of the drawing"),
            ("FORWARD", "Forward", "Add depth along the drawing normal"),
            ("BACKWARD", "Backward", "Add depth opposite the drawing normal"),
        ),
        default="CENTER",
    )

    symmetry_axis: EnumProperty(
        name="Symmetry",
        description="Mirror the generated result across a world axis",
        items=(
            ("NONE", "Off", "Do not mirror the generated mesh"),
            ("X", "X", "Mirror across the X axis"),
            ("Y", "Y", "Mirror across the Y axis"),
            ("Z", "Z", "Mirror across the Z axis"),
        ),
        default="NONE",
    )

    random_soft_color: BoolProperty(
        name="Random Soft Color",
        description="Give each generated mesh a soft random material color",
        default=True,
    )

    auto_voxel_remesh: BoolProperty(
        name="Auto Remesh New Meshes",
        description="Automatically apply voxel remesh when a mesh is generated",
        default=True,
    )

    new_layer_after_generate: BoolProperty(
        name="New Layer After Generate",
        description="Create and activate a blank sketch layer after generating a mesh",
        default=False,
    )

    replace_same_sketch_mass: BoolProperty(
        name="Replace Same Sketch Mesh",
        description="Replace the previous generated mesh from the same sketch layer/frame",
        default=True,
    )

    voxel_size: FloatProperty(
        name="Voxel Size",
        description="Voxel size used by the one-click remesh operator",
        default=0.12,
        min=0.001,
        soft_max=1.0,
        unit="LENGTH",
    )

    grid_size: FloatProperty(
        name="Grid Size",
        description="World-space grid size used by Snap Active Sketch To Grid",
        default=0.25,
        min=0.001,
        soft_max=5.0,
        unit="LENGTH",
    )

    naming_prefix: StringProperty(
        name="Mesh Prefix",
        description="Prefix used for generated mesh names",
        default="Mesh",
    )

    grease_pencil_name: StringProperty(
        name="Draw Object",
        description="Name used for the helper Grease Pencil object",
        default=DEFAULT_GP_NAME,
    )


def _is_gp_object(obj):
    return obj is not None and obj.type in GP_OBJECT_TYPES


def _cleanup_legacy_settings(settings):
    for key in LEGACY_SETTING_KEYS:
        if key in settings:
            del settings[key]
    if settings.naming_prefix == "Mass":
        settings.naming_prefix = "Mesh"


def _clean_name_prefix(prefix, fallback):
    prefix = (prefix or "").strip()
    return prefix if prefix else fallback


def _draw_stroke_placement(layout, context):
    tool_settings = context.scene.tool_settings
    if hasattr(tool_settings, "gpencil_stroke_placement_view3d"):
        layout.prop(tool_settings, "gpencil_stroke_placement_view3d", text="Stroke Placement")


def _snap_value(value, grid_size):
    if grid_size <= 0.0:
        return value
    return round(value / grid_size) * grid_size


def _snap_point_to_grid(point, grid_size):
    return Vector(
        (
            _snap_value(point.x, grid_size),
            _snap_value(point.y, grid_size),
            _snap_value(point.z, grid_size),
        )
    )


def _set_point_position(point, value):
    if hasattr(point, "position"):
        point.position = value
    elif hasattr(point, "co"):
        point.co = value


def _collection_contains(root_collection, target_collection):
    if root_collection == target_collection:
        return True
    return any(_collection_contains(child, target_collection) for child in root_collection.children)


def _ensure_collection_in_scene(context, collection):
    if collection and not _collection_contains(context.scene.collection, collection):
        context.scene.collection.children.link(collection)


def _get_target_collection(context, create=True):
    settings = context.scene.gbm_settings
    collection = settings.target_collection
    if collection is None and create:
        collection = bpy.data.collections.get(DEFAULT_COLLECTION_NAME)
        if collection is None:
            collection = bpy.data.collections.new(DEFAULT_COLLECTION_NAME)
        _ensure_collection_in_scene(context, collection)
        settings.target_collection = collection
    elif collection is not None:
        _ensure_collection_in_scene(context, collection)
    return collection or context.scene.collection


def _move_object_to_collection(obj, collection):
    if obj.name not in {item.name for item in collection.objects}:
        collection.objects.link(obj)

    for user_collection in list(obj.users_collection):
        if user_collection != collection:
            user_collection.objects.unlink(obj)


def _set_active_object(context, obj):
    if obj is None:
        return
    for item in context.view_layer.objects:
        item.select_set(False)
    obj.select_set(True)
    context.view_layer.objects.active = obj


def _exit_to_object_mode():
    active = bpy.context.view_layer.objects.active
    if active and active.mode != "OBJECT":
        try:
            bpy.ops.object.mode_set(mode="OBJECT")
        except RuntimeError:
            pass


def _next_numbered_name(existing_names, prefix):
    pattern = re.compile(r"^" + re.escape(prefix) + r"_(\d{3,})$")
    used_numbers = {
        int(match.group(1))
        for name in existing_names
        for match in [pattern.match(name)]
        if match
    }

    number = 1
    while number in used_numbers:
        number += 1

    return f"{prefix}_{number:03d}"


def _next_object_name(collection, prefix):
    names = {obj.name for obj in collection.objects}
    names.update(bpy.data.objects.keys())
    return _next_numbered_name(names, prefix)


def _next_layer_name(gp_data, prefix=DEFAULT_LAYER_PREFIX):
    names = {layer.name for layer in gp_data.layers}
    return _next_numbered_name(names, prefix)


def _active_gp_layer(gp_data):
    layers = gp_data.layers
    active = getattr(layers, "active", None)
    if active is not None:
        return active
    return layers[0] if len(layers) else None


def _set_active_gp_layer(gp_data, layer):
    layers = gp_data.layers
    if hasattr(layers, "active"):
        try:
            layers.active = layer
        except Exception:
            pass


def _new_gp_layer(gp_data, name):
    layers = gp_data.layers
    try:
        layer = layers.new(name=name, set_active=True)
    except TypeError:
        try:
            layer = layers.new(name, set_active=True)
        except TypeError:
            layer = layers.new(name)
            _set_active_gp_layer(gp_data, layer)
    return layer


def _frame_at(layer, frame_number):
    if hasattr(layer, "get_frame_at"):
        try:
            return layer.get_frame_at(frame_number)
        except Exception:
            pass

    for frame in layer.frames:
        if getattr(frame, "frame_number", None) == frame_number:
            return frame
    return None


def _current_or_active_frame(layer, frame_number):
    if hasattr(layer, "current_frame"):
        try:
            frame = layer.current_frame()
            if frame is not None:
                return frame
        except Exception:
            pass

    frame = getattr(layer, "active_frame", None)
    if frame is not None:
        return frame

    return _frame_at(layer, frame_number)


def _ensure_frame(layer, frame_number):
    frame = _frame_at(layer, frame_number)
    if frame is not None:
        return frame

    try:
        return layer.frames.new(frame_number)
    except TypeError:
        return layer.frames.new(frame_number, active=True)


def _ensure_gp_layer_and_frame(context, gp_obj):
    gp_data = gp_obj.data
    layer = _active_gp_layer(gp_data)
    if layer is None:
        layer = _new_gp_layer(gp_data, f"{DEFAULT_LAYER_PREFIX}_001")
    _ensure_frame(layer, context.scene.frame_current)
    return layer


def _create_blank_sketch_layer(context, gp_obj):
    layer_name = _next_layer_name(gp_obj.data)
    layer = _new_gp_layer(gp_obj.data, layer_name)
    _ensure_frame(layer, context.scene.frame_current)
    return layer


def _find_existing_gp_object(context):
    settings = context.scene.gbm_settings
    target_collection = _get_target_collection(context, create=False)
    active = context.view_layer.objects.active

    if _is_gp_object(active):
        return active

    preferred_name = _clean_name_prefix(settings.grease_pencil_name, DEFAULT_GP_NAME)
    obj = bpy.data.objects.get(preferred_name)
    if _is_gp_object(obj):
        return obj

    if target_collection:
        for item in target_collection.objects:
            if _is_gp_object(item) and item.get(PROP_HELPER):
                return item
        for item in target_collection.objects:
            if _is_gp_object(item):
                return item

    for item in context.scene.objects:
        if _is_gp_object(item) and item.get(PROP_HELPER):
            return item

    return None


def _create_gp_with_operator(context, name):
    _exit_to_object_mode()
    before_names = set(bpy.data.objects.keys())

    add_op = getattr(bpy.ops.object, "grease_pencil_add", None)
    if add_op is not None:
        try:
            add_op(type="EMPTY", align="VIEW")
        except TypeError:
            add_op()
    else:
        legacy_add_op = getattr(bpy.ops.object, "gpencil_add", None)
        if legacy_add_op is None:
            return None
        try:
            legacy_add_op(type="EMPTY", align="VIEW")
        except TypeError:
            legacy_add_op()

    created = context.view_layer.objects.active
    if created is None or created.name in before_names:
        new_objects = [obj for obj in bpy.data.objects if obj.name not in before_names]
        created = new_objects[0] if new_objects else None

    if created:
        created.name = name
        created.data.name = f"{name}_Data"
    return created


def _create_gp_manually(context, name, collection):
    gp_data = None
    grease_pencils_v3 = getattr(bpy.data, "grease_pencils_v3", None)
    if grease_pencils_v3 is not None:
        gp_data = grease_pencils_v3.new(f"{name}_Data")
    elif hasattr(bpy.data, "grease_pencils"):
        gp_data = bpy.data.grease_pencils.new(f"{name}_Data")

    if gp_data is None:
        return None

    obj = bpy.data.objects.new(name, gp_data)
    collection.objects.link(obj)
    return obj


def _get_or_create_gp_object(context):
    settings = context.scene.gbm_settings
    collection = _get_target_collection(context, create=True)
    name = _clean_name_prefix(settings.grease_pencil_name, DEFAULT_GP_NAME)

    gp_obj = _find_existing_gp_object(context)
    if gp_obj is None:
        gp_obj = _create_gp_with_operator(context, name)
    if gp_obj is None:
        gp_obj = _create_gp_manually(context, name, collection)
    if gp_obj is None:
        return None

    gp_obj[PROP_HELPER] = True
    _move_object_to_collection(gp_obj, collection)
    _set_active_object(context, gp_obj)
    _ensure_gp_layer_and_frame(context, gp_obj)
    return gp_obj


def _enter_gp_draw_mode(context, gp_obj):
    _set_active_object(context, gp_obj)
    if gp_obj.mode in {"PAINT_GREASE_PENCIL", "PAINT_GPENCIL"}:
        return True

    _exit_to_object_mode()

    for mode in ("PAINT_GREASE_PENCIL", "PAINT_GPENCIL"):
        try:
            bpy.ops.object.mode_set(mode=mode)
            if gp_obj.mode in {"PAINT_GREASE_PENCIL", "PAINT_GPENCIL"}:
                return True
        except (AttributeError, RuntimeError, TypeError, ValueError):
            pass

    paint_toggle = getattr(bpy.ops.grease_pencil, "paintmode_toggle", None)
    if paint_toggle is not None:
        try:
            paint_toggle()
            if gp_obj.mode in {"PAINT_GREASE_PENCIL", "PAINT_GPENCIL"}:
                return True
        except (AttributeError, RuntimeError):
            pass

    legacy_gpencil_ops = getattr(bpy.ops, "gpencil", None)
    legacy_paint_toggle = getattr(legacy_gpencil_ops, "paintmode_toggle", None)
    if legacy_paint_toggle is not None:
        try:
            legacy_paint_toggle()
            if gp_obj.mode in {"PAINT_GREASE_PENCIL", "PAINT_GPENCIL"}:
                return True
        except (AttributeError, RuntimeError):
            pass

    return False


def _enter_gp_draw_mode_later(gp_obj_name):
    def _switch_mode():
        gp_obj = bpy.data.objects.get(gp_obj_name)
        if gp_obj is None:
            return None

        try:
            _enter_gp_draw_mode(bpy.context, gp_obj)
        except Exception:
            return None

        return None

    bpy.app.timers.register(_switch_mode, first_interval=0.01)


def _point_position(point):
    value = getattr(point, "position", None)
    if value is None:
        value = getattr(point, "co", None)
    return Vector(value) if value is not None else None


def _stroke_is_cyclic(stroke):
    if hasattr(stroke, "cyclic"):
        return bool(stroke.cyclic)
    return bool(getattr(stroke, "use_cyclic", False))


def _dedupe_points(points, tolerance=0.0001):
    if not points:
        return []

    cleaned = [points[0]]
    for point in points[1:]:
        if (point - cleaned[-1]).length > tolerance:
            cleaned.append(point)

    if len(cleaned) > 2 and (cleaned[0] - cleaned[-1]).length <= tolerance:
        cleaned.pop()

    return cleaned


def _layer_matrix(layer):
    matrix = getattr(layer, "matrix_local", None)
    return matrix if matrix is not None else Matrix.Identity(4)


def _strokes_from_frame(frame):
    drawing = getattr(frame, "drawing", None)
    if drawing is not None:
        return getattr(drawing, "strokes", [])
    return getattr(frame, "strokes", [])


def _drawing_from_frame(frame):
    return getattr(frame, "drawing", None)


def _clear_frame_strokes(frame):
    drawing = _drawing_from_frame(frame)
    if drawing is not None and hasattr(drawing, "remove_strokes"):
        try:
            drawing.remove_strokes()
            return True
        except RuntimeError:
            return False

    strokes = getattr(frame, "strokes", None)
    if strokes is not None:
        try:
            strokes.clear()
            return True
        except Exception:
            return False

    return False


def _extract_active_layer_paths(context, gp_obj):
    gp_data = gp_obj.data
    layer = _active_gp_layer(gp_data)
    if layer is None:
        return [], None

    frame = _current_or_active_frame(layer, context.scene.frame_current)
    if frame is None:
        return [], layer

    transform = gp_obj.matrix_world @ _layer_matrix(layer)
    paths = []

    for stroke in _strokes_from_frame(frame):
        points = []
        for point in getattr(stroke, "points", []):
            position = _point_position(point)
            if position is not None:
                points.append(transform @ position)

        points = _dedupe_points(points)
        if len(points) >= 3:
            paths.append(
                {
                    "points": points,
                    "cyclic": _stroke_is_cyclic(stroke),
                }
            )

    return paths, layer


def _newell_normal(points):
    normal = Vector((0.0, 0.0, 0.0))
    for index, current in enumerate(points):
        nxt = points[(index + 1) % len(points)]
        normal.x += (current.y - nxt.y) * (current.z + nxt.z)
        normal.y += (current.z - nxt.z) * (current.x + nxt.x)
        normal.z += (current.x - nxt.x) * (current.y + nxt.y)

    if normal.length <= 0.000001:
        return None
    normal.normalize()
    return normal


def _fallback_normal(gp_obj):
    normal = gp_obj.matrix_world.to_3x3() @ Vector((0.0, 0.0, 1.0))
    if normal.length <= 0.000001:
        normal = Vector((0.0, 0.0, 1.0))
    normal.normalize()
    return normal


def _depth_offsets(normal, thickness, direction):
    if direction == "FORWARD":
        return normal * thickness, Vector((0.0, 0.0, 0.0))
    if direction == "BACKWARD":
        return Vector((0.0, 0.0, 0.0)), -normal * thickness

    half_depth = thickness * 0.5
    return normal * half_depth, -normal * half_depth


def _build_prism_mesh_data(paths, thickness, fallback_normal, direction):
    verts = []
    faces = []

    for path in paths:
        points = path["points"]
        normal = _newell_normal(points) or fallback_normal
        front_offset, back_offset = _depth_offsets(normal, thickness, direction)
        front = []
        back = []

        for point in points:
            front.append(len(verts))
            verts.append(point + front_offset)

        for point in points:
            back.append(len(verts))
            verts.append(point + back_offset)

        faces.append(tuple(front))
        faces.append(tuple(reversed(back)))

        count = len(points)
        for index in range(count):
            nxt = (index + 1) % count
            faces.append((front[index], front[nxt], back[nxt], back[index]))

    return verts, faces


def _default_mesh_material():
    material = bpy.data.materials.get(MASS_MATERIAL_NAME)
    if material is None:
        material = bpy.data.materials.new(MASS_MATERIAL_NAME)
        material.diffuse_color = (0.72, 0.56, 0.45, 1.0)
    return material


def _random_soft_material(name):
    hue = random.random()
    saturation = random.uniform(0.28, 0.45)
    value = random.uniform(0.72, 0.92)

    red, green, blue = colorsys.hsv_to_rgb(hue, saturation, value)
    material = bpy.data.materials.new(f"{name}_Material")
    material.diffuse_color = (red, green, blue, 1.0)
    return material


def _add_voxel_remesh_modifier(obj, voxel_size, smooth_shading):
    modifier = obj.modifiers.new("MVP Voxel Remesh", "REMESH")
    modifier.mode = "VOXEL"
    modifier.voxel_size = voxel_size
    if hasattr(modifier, "use_smooth_shade"):
        modifier.use_smooth_shade = smooth_shading
    return modifier


def _set_mesh_flat_shading(obj):
    if obj and obj.type == "MESH":
        for polygon in obj.data.polygons:
            polygon.use_smooth = False


def _source_frame_number(frame, fallback):
    return str(getattr(frame, "frame_number", fallback))


def _remove_object_and_data(obj):
    mesh = obj.data if obj.type == "MESH" else None
    bpy.data.objects.remove(obj, do_unlink=True)
    if mesh and mesh.users == 0:
        bpy.data.meshes.remove(mesh)


def _remove_previous_meshes_for_source(context, gp_obj, layer, frame_number):
    collection = _get_target_collection(context, create=True)
    source_frame = str(frame_number)

    for obj in list(collection.objects):
        if not obj.get(PROP_GENERATED):
            continue
        if obj.get(PROP_SOURCE) != gp_obj.name:
            continue
        if obj.get(PROP_SOURCE_LAYER) != layer.name:
            continue

        stored_frame = obj.get(PROP_SOURCE_FRAME)
        if stored_frame is not None and str(stored_frame) != source_frame:
            continue

        _remove_object_and_data(obj)


def _apply_object_stack_to_mesh(context, obj):
    depsgraph = context.evaluated_depsgraph_get()
    evaluated_obj = obj.evaluated_get(depsgraph)
    baked_mesh = bpy.data.meshes.new_from_object(evaluated_obj, depsgraph=depsgraph)
    old_mesh = obj.data

    if not baked_mesh.materials and old_mesh:
        for material in old_mesh.materials:
            baked_mesh.materials.append(material)

    for modifier in reversed(obj.modifiers):
        obj.modifiers.remove(modifier)

    obj.data = baked_mesh
    if old_mesh and old_mesh.users == 0:
        bpy.data.meshes.remove(old_mesh)

    _set_mesh_flat_shading(obj)
    return True


def _add_mirror_modifier(obj, axis):
    if axis == "NONE":
        return None

    modifier = obj.modifiers.new("GBM Mirror", "MIRROR")
    axis_flags = [False, False, False]
    axis_index = {"X": 0, "Y": 1, "Z": 2}.get(axis)
    if axis_index is None:
        obj.modifiers.remove(modifier)
        return None

    axis_flags[axis_index] = True
    modifier.use_axis = axis_flags
    if hasattr(modifier, "use_clip"):
        modifier.use_clip = True
    if hasattr(modifier, "use_mirror_merge"):
        modifier.use_mirror_merge = True
    if hasattr(modifier, "merge_threshold"):
        modifier.merge_threshold = 0.0001
    return modifier


def _apply_symmetry_to_object(context, obj, axis):
    if axis == "NONE":
        return True

    modifier = _add_mirror_modifier(obj, axis)
    if modifier is None:
        return False

    return _apply_object_stack_to_mesh(context, obj)


def _apply_voxel_remesh_to_object(context, obj, voxel_size):
    if obj is None or obj.type != "MESH":
        return False

    modifier = _add_voxel_remesh_modifier(obj, voxel_size, False)
    if modifier is None:
        return False

    return _apply_object_stack_to_mesh(context, obj)


def _create_generated_mesh_object(context, gp_obj, paths):
    settings = context.scene.gbm_settings
    collection = _get_target_collection(context, create=True)
    prefix = _clean_name_prefix(settings.naming_prefix, "Mesh")
    name = _next_object_name(collection, prefix)

    verts, faces = _build_prism_mesh_data(
        paths,
        settings.thickness,
        _fallback_normal(gp_obj),
        settings.depth_direction,
    )
    mesh = bpy.data.meshes.new(f"{name}_Mesh")
    mesh.from_pydata([tuple(vertex) for vertex in verts], [], faces)
    mesh.validate(clean_customdata=False)
    mesh.update()

    obj = bpy.data.objects.new(name, mesh)
    obj[PROP_GENERATED] = True
    obj[PROP_SOURCE] = gp_obj.name
    collection.objects.link(obj)
    if settings.random_soft_color:
        obj.data.materials.append(_random_soft_material(name))
    else:
        obj.data.materials.append(_default_mesh_material())

    _set_mesh_flat_shading(obj)
    if settings.symmetry_axis != "NONE":
        _apply_symmetry_to_object(context, obj, settings.symmetry_axis)
    if settings.auto_voxel_remesh:
        _apply_voxel_remesh_to_object(context, obj, settings.voxel_size)
    return obj


class GBM_OT_activate_grease_pencil(Operator):
    bl_idname = "gbm.activate_grease_pencil"
    bl_label = "Create / Activate Draw Object"
    bl_description = "Create or activate the helper Grease Pencil object"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        gp_obj = _get_or_create_gp_object(context)
        if gp_obj is None:
            self.report({"ERROR"}, "Could not create a Grease Pencil object.")
            return {"CANCELLED"}

        if not _enter_gp_draw_mode(context, gp_obj):
            self.report({"ERROR"}, "Could not enter Grease Pencil Draw Mode.")
            return {"CANCELLED"}

        self.report({"INFO"}, f"Active draw object: {gp_obj.name}")
        return {"FINISHED"}


class GBM_OT_enter_draw_mode(Operator):
    bl_idname = "gbm.enter_draw_mode"
    bl_label = "Draw Mode"
    bl_description = "Activate Grease Pencil and enter Draw Mode"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        gp_obj = _get_or_create_gp_object(context)
        if gp_obj is None:
            self.report({"ERROR"}, "Could not create a Grease Pencil object.")
            return {"CANCELLED"}

        if not _enter_gp_draw_mode(context, gp_obj):
            self.report({"ERROR"}, "Could not enter Grease Pencil Draw Mode.")
            return {"CANCELLED"}

        return {"FINISHED"}


class GBM_OT_new_sketch_layer(Operator):
    bl_idname = "gbm.new_sketch_layer"
    bl_label = "New Blank Sketch Layer"
    bl_description = "Create a fresh active Grease Pencil layer for the next sketch"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        gp_obj = _get_or_create_gp_object(context)
        if gp_obj is None:
            self.report({"ERROR"}, "Could not create a Grease Pencil object.")
            return {"CANCELLED"}

        _exit_to_object_mode()
        layer = _create_blank_sketch_layer(context, gp_obj)
        _enter_gp_draw_mode(context, gp_obj)
        self.report({"INFO"}, f"Ready to draw on {layer.name}")
        return {"FINISHED"}


class GBM_OT_clear_current_sketch(Operator):
    bl_idname = "gbm.clear_current_sketch"
    bl_label = "Clear Current Sketch"
    bl_description = "Clear strokes from the active Grease Pencil layer on the current frame"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        gp_obj = _find_existing_gp_object(context)
        if gp_obj is None:
            self.report({"ERROR"}, "No Grease Pencil draw object found.")
            return {"CANCELLED"}

        _set_active_object(context, gp_obj)
        _exit_to_object_mode()
        layer = _ensure_gp_layer_and_frame(context, gp_obj)
        frame = _current_or_active_frame(layer, context.scene.frame_current)

        if frame is None or not _clear_frame_strokes(frame):
            _enter_gp_draw_mode(context, gp_obj)
            self.report({"WARNING"}, "Could not clear the current sketch.")
            return {"CANCELLED"}

        _enter_gp_draw_mode(context, gp_obj)
        self.report({"INFO"}, f"Cleared sketch layer {layer.name}")
        return {"FINISHED"}


class GBM_OT_clear_all_sketches(Operator):
    bl_idname = "gbm.clear_all_sketches"
    bl_label = "Clear All Sketches"
    bl_description = "Clear all sketches from this addon's Grease Pencil draw object"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        gp_obj = _find_existing_gp_object(context)
        if gp_obj is None:
            self.report({"ERROR"}, "No Grease Pencil draw object found.")
            return {"CANCELLED"}

        _set_active_object(context, gp_obj)
        _exit_to_object_mode()

        cleared = 0
        for layer in gp_obj.data.layers:
            for frame in layer.frames:
                if _clear_frame_strokes(frame):
                    cleared += 1

        _ensure_gp_layer_and_frame(context, gp_obj)
        _enter_gp_draw_mode(context, gp_obj)

        if cleared == 0:
            self.report({"INFO"}, "No sketches to clear.")
        else:
            self.report({"INFO"}, f"Cleared sketches from {cleared} frame(s).")
        return {"FINISHED"}


class GBM_OT_snap_active_sketch(Operator):
    bl_idname = "gbm.snap_active_sketch"
    bl_label = "Snap Active Sketch To Grid"
    bl_description = "Snap the active sketch layer on the current frame to the configured world grid"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        settings = context.scene.gbm_settings
        gp_obj = _find_existing_gp_object(context)
        if gp_obj is None:
            self.report({"ERROR"}, "No Grease Pencil draw object found.")
            return {"CANCELLED"}

        _set_active_object(context, gp_obj)
        _exit_to_object_mode()
        layer = _ensure_gp_layer_and_frame(context, gp_obj)
        frame = _current_or_active_frame(layer, context.scene.frame_current)
        if frame is None:
            _enter_gp_draw_mode(context, gp_obj)
            self.report({"WARNING"}, "No active sketch frame to snap.")
            return {"CANCELLED"}

        strokes = list(_strokes_from_frame(frame))
        if not strokes:
            _enter_gp_draw_mode(context, gp_obj)
            self.report({"WARNING"}, "Draw something first, then snap the sketch to the grid.")
            return {"CANCELLED"}

        transform = gp_obj.matrix_world @ _layer_matrix(layer)
        inverse_transform = transform.inverted_safe()
        snapped_points = 0

        for stroke in strokes:
            for point in getattr(stroke, "points", []):
                position = _point_position(point)
                if position is None:
                    continue
                world_position = transform @ position
                snapped_world = _snap_point_to_grid(world_position, settings.grid_size)
                snapped_local = inverse_transform @ snapped_world
                _set_point_position(point, snapped_local)
                snapped_points += 1

        _enter_gp_draw_mode(context, gp_obj)
        self.report({"INFO"}, f"Snapped {snapped_points} point(s) to the grid.")
        return {"FINISHED"}


class GBM_OT_generate_mass(Operator):
    bl_idname = "gbm.generate_mass"
    bl_label = "Generate Mesh"
    bl_description = "Convert the active Grease Pencil sketch layer into a rough 3D blockout mesh"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        settings = context.scene.gbm_settings
        gp_obj = _find_existing_gp_object(context)
        if gp_obj is None:
            self.report({"ERROR"}, "No Grease Pencil draw object found.")
            return {"CANCELLED"}

        _set_active_object(context, gp_obj)
        _exit_to_object_mode()
        _ensure_gp_layer_and_frame(context, gp_obj)

        paths, layer = _extract_active_layer_paths(context, gp_obj)
        if not paths:
            _enter_gp_draw_mode(context, gp_obj)
            self.report({"WARNING"}, "Draw a closed shape on the active Grease Pencil layer first.")
            return {"CANCELLED"}

        frame = _current_or_active_frame(layer, context.scene.frame_current) if layer is not None else None
        source_frame = _source_frame_number(frame, context.scene.frame_current)
        if settings.replace_same_sketch_mass and layer is not None:
            _remove_previous_meshes_for_source(context, gp_obj, layer, source_frame)

        mesh_obj = _create_generated_mesh_object(context, gp_obj, paths)
        if layer is not None:
            mesh_obj[PROP_SOURCE_LAYER] = layer.name
            mesh_obj[PROP_SOURCE_FRAME] = source_frame

        if settings.new_layer_after_generate:
            _create_blank_sketch_layer(context, gp_obj)
        elif layer is not None:
            _set_active_gp_layer(gp_obj.data, layer)
        _set_active_object(context, gp_obj)
        _enter_gp_draw_mode_later(gp_obj.name)
        self.report({"INFO"}, f"Created {mesh_obj.name}")
        return {"FINISHED"}


class GBM_OT_apply_voxel_remesh(Operator):
    bl_idname = "gbm.apply_voxel_remesh"
    bl_label = "Apply Voxel Remesh"
    bl_description = "Apply a voxel remesh to the selected generated mesh"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        settings = context.scene.gbm_settings
        targets = [obj for obj in context.selected_objects if obj.type == "MESH"]
        if not targets and context.object and context.object.type == "MESH":
            targets = [context.object]

        if not targets:
            self.report({"ERROR"}, "Select a generated mesh first.")
            return {"CANCELLED"}

        _exit_to_object_mode()
        processed = 0

        for obj in targets:
            if _apply_voxel_remesh_to_object(context, obj, settings.voxel_size):
                processed += 1
            else:
                self.report({"WARNING"}, f"Could not apply remesh to {obj.name}.")

        if processed == 0:
            return {"CANCELLED"}

        self.report({"INFO"}, f"Voxel remeshed {processed} object(s).")
        return {"FINISHED"}


class GBM_OT_set_voxel_preset(Operator):
    bl_idname = "gbm.set_voxel_preset"
    bl_label = "Set Voxel Preset"
    bl_description = "Set voxel size to a blockout-friendly preset"
    bl_options = {"REGISTER", "UNDO"}

    preset: StringProperty(default="MEDIUM")

    def execute(self, context):
        preset = self.preset if self.preset in REMESH_PRESETS else "MEDIUM"
        context.scene.gbm_settings.voxel_size = REMESH_PRESETS[preset]
        self.report({"INFO"}, f"Voxel size set to {REMESH_PRESETS[preset]:.2f}")
        return {"FINISHED"}


class GBM_PT_blockout_panel(Panel):
    bl_idname = "GBM_PT_blockout_panel"
    bl_label = "Grease Blockout"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Blockout"

    def draw(self, context):
        layout = self.layout
        settings = context.scene.gbm_settings
        _cleanup_legacy_settings(settings)

        layout.prop(settings, "target_collection")
        _draw_stroke_placement(layout, context)

        layout.separator()
        layout.operator("gbm.activate_grease_pencil")
        layout.operator("gbm.enter_draw_mode")
        layout.operator("gbm.generate_mass")
        layout.prop(settings, "new_layer_after_generate")
        layout.prop(settings, "replace_same_sketch_mass")
        layout.operator("gbm.clear_current_sketch")
        layout.operator("gbm.clear_all_sketches")
        layout.operator("gbm.new_sketch_layer")
        snap_column = layout.column(align=True)
        snap_column.operator("gbm.snap_active_sketch")
        snap_column.prop(settings, "grid_size")

        layout.separator()
        layout.prop(settings, "thickness")
        layout.prop(settings, "depth_direction")
        layout.prop(settings, "symmetry_axis")
        layout.prop(settings, "naming_prefix")
        layout.prop(settings, "random_soft_color")

        layout.separator()
        layout.prop(settings, "voxel_size")
        row = layout.row(align=True)
        preset = row.operator("gbm.set_voxel_preset", text="Coarse")
        preset.preset = "COARSE"
        preset = row.operator("gbm.set_voxel_preset", text="Medium")
        preset.preset = "MEDIUM"
        preset = row.operator("gbm.set_voxel_preset", text="Fine")
        preset.preset = "FINE"
        layout.prop(settings, "auto_voxel_remesh")
        layout.operator("gbm.apply_voxel_remesh")


classes = (
    GBM_Settings,
    GBM_OT_activate_grease_pencil,
    GBM_OT_enter_draw_mode,
    GBM_OT_new_sketch_layer,
    GBM_OT_clear_current_sketch,
    GBM_OT_clear_all_sketches,
    GBM_OT_snap_active_sketch,
    GBM_OT_generate_mass,
    GBM_OT_apply_voxel_remesh,
    GBM_OT_set_voxel_preset,
    GBM_PT_blockout_panel,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.gbm_settings = PointerProperty(type=GBM_Settings)


def unregister():
    if hasattr(bpy.types.Scene, "gbm_settings"):
        del bpy.types.Scene.gbm_settings
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
