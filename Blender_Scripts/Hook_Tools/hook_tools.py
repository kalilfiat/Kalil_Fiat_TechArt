bl_info = {
    "name": "Curve Hook Tools",
    "author": "OpenAI",
    "version": (1, 1, 0),
    "blender": (3, 0, 0),
    "location": "View3D > Sidebar > Hook Tools",
    "description": "Create one hook per selected curve point and remove hooks/empties for the active curve",
    "category": "Object",
}

import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

def get_preferred_parent_collection(obj, context):
    """Return the collection that should own the hook empties.

    Preference order:
    1) First direct user collection of the object.
    2) Scene root collection.
    """
    if obj and obj.users_collection:
        return obj.users_collection[0]
    return context.scene.collection


def ensure_hooks_child_collection(parent_collection):
    hooks_collection_name = f"Hooks_{parent_collection.name}"
    hooks_collection = bpy.data.collections.get(hooks_collection_name)

    if hooks_collection is None:
        hooks_collection = bpy.data.collections.new(hooks_collection_name)

    # Ensure it is linked as child of the parent collection.
    if hooks_collection.name not in [child.name for child in parent_collection.children]:
        try:
            parent_collection.children.link(hooks_collection)
        except RuntimeError:
            # Already linked elsewhere in some edge cases; ignore.
            pass

    hooks_collection.color_tag = 'COLOR_04'
    return hooks_collection


def get_hook_base_name(obj):
    if obj.name.startswith("Spline_"):
        return obj.name.replace("Spline_", "Hook_", 1)
    return f"Hook_{obj.name}"


def collect_selected_curve_points(curve_data):
    selected_points = []

    for spline_index, spline in enumerate(curve_data.splines):
        if spline.type == 'BEZIER':
            for point_index, point in enumerate(spline.bezier_points):
                if point.select_control_point:
                    selected_points.append((spline_index, point_index, 'BEZIER'))
        else:
            for point_index, point in enumerate(spline.points):
                if point.select:
                    selected_points.append((spline_index, point_index, 'POINT'))

    return selected_points


def save_curve_selection_state(curve_data):
    state = []
    for spline in curve_data.splines:
        if spline.type == 'BEZIER':
            pts = []
            for pt in spline.bezier_points:
                pts.append({
                    "control": pt.select_control_point,
                    "left": pt.select_left_handle,
                    "right": pt.select_right_handle,
                })
            state.append(("BEZIER", pts))
        else:
            pts = []
            for pt in spline.points:
                pts.append(pt.select)
            state.append(("POINT", pts))
    return state


def restore_curve_selection_state(curve_data, state):
    for spline, spline_state in zip(curve_data.splines, state):
        spline_type, pts_state = spline_state
        if spline.type == 'BEZIER' and spline_type == 'BEZIER':
            for pt, pt_state in zip(spline.bezier_points, pts_state):
                pt.select_control_point = pt_state["control"]
                pt.select_left_handle = pt_state["left"]
                pt.select_right_handle = pt_state["right"]
        elif spline.type != 'BEZIER' and spline_type == 'POINT':
            for pt, is_selected in zip(spline.points, pts_state):
                pt.select = is_selected


def select_single_curve_point(curve_data, spline_index, point_index, point_type):
    bpy.ops.curve.select_all(action='DESELECT')
    spline = curve_data.splines[spline_index]

    if point_type == 'BEZIER':
        point = spline.bezier_points[point_index]
        point.select_control_point = True
        point.select_left_handle = False
        point.select_right_handle = False
    else:
        spline.points[point_index].select = True


def get_hook_modifiers(obj):
    return [mod for mod in obj.modifiers if mod.type == 'HOOK']


# -----------------------------------------------------------------------------
# Operators
# -----------------------------------------------------------------------------

class CURVE_OT_hook_per_selected_point(bpy.types.Operator):
    bl_idname = "curve.hook_per_selected_point"
    bl_label = "Create Hooks for Selected Points"
    bl_description = "Creates one hook and one Empty for each selected point on the active curve"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = context.active_object

        if obj is None:
            self.report({'ERROR'}, "No active object")
            return {'CANCELLED'}

        if obj.type != 'CURVE':
            self.report({'ERROR'}, "The active object is not a curve")
            return {'CANCELLED'}

        if context.mode != 'EDIT_CURVE':
            self.report({'ERROR'}, "You must be in Curve Edit Mode")
            return {'CANCELLED'}

        curve = obj.data
        selected_points = collect_selected_curve_points(curve)

        if not selected_points:
            self.report({'WARNING'}, "No selected points found")
            return {'CANCELLED'}

        parent_collection = get_preferred_parent_collection(obj, context)
        hooks_collection = ensure_hooks_child_collection(parent_collection)
        hook_base_name = get_hook_base_name(obj)

        selection_state = save_curve_selection_state(curve)
        created_count = 0

        empty_display_type = context.scene.hook_tools_empty_display_type
        empty_display_size = context.scene.hook_tools_empty_display_size
        single_hook_for_selection = context.scene.hook_tools_single_hook_for_selection

        try:
            if single_hook_for_selection:
                if context.mode != 'EDIT_CURVE':
                    bpy.ops.object.mode_set(mode='EDIT')

                before_modifiers = set(mod.name for mod in get_hook_modifiers(obj))
                bpy.ops.object.hook_add_newob()

                new_hook_mod = None
                for mod in reversed(get_hook_modifiers(obj)):
                    if mod.name not in before_modifiers:
                        new_hook_mod = mod
                        break

                if new_hook_mod is not None and new_hook_mod.object is not None:
                    new_empty = new_hook_mod.object
                    final_name = hook_base_name
                    new_empty.name = final_name
                    new_empty.empty_display_type = empty_display_type
                    new_empty.empty_display_size = empty_display_size

                    for col in list(new_empty.users_collection):
                        col.objects.unlink(new_empty)

                    if new_empty not in hooks_collection.objects[:]:
                        hooks_collection.objects.link(new_empty)

                    created_count = 1
            else:
                for i, (spline_index, point_index, point_type) in enumerate(selected_points, start=1):
                    if context.mode != 'EDIT_CURVE':
                        bpy.ops.object.mode_set(mode='EDIT')

                    before_modifiers = set(mod.name for mod in get_hook_modifiers(obj))
                    select_single_curve_point(curve, spline_index, point_index, point_type)
                    bpy.ops.object.hook_add_newob()

                    new_hook_mod = None
                    for mod in reversed(get_hook_modifiers(obj)):
                        if mod.name not in before_modifiers:
                            new_hook_mod = mod
                            break

                    if new_hook_mod is None or new_hook_mod.object is None:
                        continue

                    new_empty = new_hook_mod.object

                    if len(selected_points) == 1:
                        final_name = hook_base_name
                    else:
                        final_name = f"{hook_base_name}-{i:02d}"

                    new_empty.name = final_name
                    new_empty.empty_display_type = empty_display_type
                    new_empty.empty_display_size = empty_display_size

                    for col in list(new_empty.users_collection):
                        col.objects.unlink(new_empty)

                    if new_empty not in hooks_collection.objects[:]:
                        hooks_collection.objects.link(new_empty)

                    created_count += 1

        finally:
            if context.mode != 'EDIT_CURVE':
                bpy.ops.object.mode_set(mode='EDIT')
            restore_curve_selection_state(curve, selection_state)

        self.report({'INFO'}, f"Created {created_count} hooks in {hooks_collection.name}")
        return {'FINISHED'}


class CURVE_OT_remove_hooks_and_empties(bpy.types.Operator):
    bl_idname = "curve.remove_hooks_and_empties"
    bl_label = "Remove Curve Hooks"
    bl_description = "Removes all hook modifiers from the active curve and deletes their associated empties"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = context.active_object

        if obj is None:
            self.report({'ERROR'}, "No active object")
            return {'CANCELLED'}

        if obj.type != 'CURVE':
            self.report({'ERROR'}, "The active object is not a curve")
            return {'CANCELLED'}

        hook_objects_to_delete = []
        for mod in get_hook_modifiers(obj):
            if mod.object is not None and mod.object not in hook_objects_to_delete:
                hook_objects_to_delete.append(mod.object)

        removed_modifiers = 0
        for mod in list(obj.modifiers):
            if mod.type == 'HOOK':
                obj.modifiers.remove(mod)
                removed_modifiers += 1

        removed_objects = 0
        for hook_obj in hook_objects_to_delete:
            if hook_obj.name in bpy.data.objects:
                bpy.data.objects.remove(hook_obj, do_unlink=True)
                removed_objects += 1

        parent_collection = get_preferred_parent_collection(obj, context)
        hooks_collection_name = f"Hooks_{parent_collection.name}"
        hooks_collection = bpy.data.collections.get(hooks_collection_name)
        removed_collection = False

        if hooks_collection is not None:
            if not hooks_collection.objects and not hooks_collection.children:
                for parent in bpy.data.collections:
                    if hooks_collection.name in parent.children.keys():
                        parent.children.unlink(hooks_collection)
                if hooks_collection.name in bpy.data.collections:
                    bpy.data.collections.remove(hooks_collection)
                    removed_collection = True

        msg = f"Removed {removed_modifiers} hook modifiers and {removed_objects} empties"
        if removed_collection:
            msg += "; the empty hooks collection was also deleted"

        self.report({'INFO'}, msg)
        return {'FINISHED'}


# -----------------------------------------------------------------------------
# UI
# -----------------------------------------------------------------------------

class CURVE_PT_hook_tools(bpy.types.Panel):
    bl_label = "Hook Tools"
    bl_idname = "CURVE_PT_hook_tools"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Hook Tools"

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj is not None and obj.type == 'CURVE'

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        obj = context.active_object

        col = layout.column(align=True)
        col.label(text="Empty Settings")
        col.prop(scene, "hook_tools_empty_display_type", text="Shape")
        col.prop(scene, "hook_tools_empty_display_size", text="Size")
        col.prop(scene, "hook_tools_single_hook_for_selection", text="Single Hook for Selection")

        layout.separator()

        parent_collection = get_preferred_parent_collection(obj, context) if obj else None
        if parent_collection:
            layout.label(text=f"Parent: {parent_collection.name}")
            layout.label(text=f"Hooks: Hooks_{parent_collection.name}")

        layout.separator()

        col = layout.column(align=True)
        col.operator("curve.hook_per_selected_point", icon='HOOK')
        col.operator("curve.remove_hooks_and_empties", icon='TRASH')


# -----------------------------------------------------------------------------
# Registration
# -----------------------------------------------------------------------------

classes = (
    CURVE_OT_hook_per_selected_point,
    CURVE_OT_remove_hooks_and_empties,
    CURVE_PT_hook_tools,
)


def register_properties():
    bpy.types.Scene.hook_tools_empty_display_size = FloatProperty(
        name="Empty Size",
        description="Display size for newly created hook empties",
        default=0.15,
        min=0.001,
        soft_max=10.0,
    )

    bpy.types.Scene.hook_tools_empty_display_type = EnumProperty(
        name="Empty Shape",
        description="Display shape for newly created hook empties",
        items=[
            ('PLAIN_AXES', "Plain Axes", ""),
            ('ARROWS', "Arrows", ""),
            ('SINGLE_ARROW', "Single Arrow", ""),
            ('CIRCLE', "Circle", ""),
            ('CUBE', "Cube", ""),
            ('SPHERE', "Sphere", ""),
            ('CONE', "Cone", ""),
            ('IMAGE', "Image", ""),
        ],
        default='PLAIN_AXES',
    )

    bpy.types.Scene.hook_tools_single_hook_for_selection = BoolProperty(
        name="Single Hook for Selection",
        description="Create one single hook for all currently selected points instead of one hook per point",
        default=False,
    )


def unregister_properties():
    if hasattr(bpy.types.Scene, "hook_tools_empty_display_size"):
        del bpy.types.Scene.hook_tools_empty_display_size
    if hasattr(bpy.types.Scene, "hook_tools_empty_display_type"):
        del bpy.types.Scene.hook_tools_empty_display_type
    if hasattr(bpy.types.Scene, "hook_tools_single_hook_for_selection"):
        del bpy.types.Scene.hook_tools_single_hook_for_selection



def register():
    register_properties()
    for cls in classes:
        bpy.utils.register_class(cls)



def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    unregister_properties()


if __name__ == "__main__":
    register()
