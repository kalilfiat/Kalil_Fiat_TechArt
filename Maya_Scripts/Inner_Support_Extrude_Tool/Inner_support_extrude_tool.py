import maya.cmds as cmds


class InnerSupportExtrudeToolV31:
    WINDOW_NAME = "innerSupportExtrudeToolV31Win"

    def __init__(self):
        self.original_object = None
        self.base_backup_object = None
        self.face_indices = []
        self.is_editing = False
        self.is_updating = False
        self.ui = {}

    def show(self):
        if cmds.window(self.WINDOW_NAME, exists=True):
            cmds.deleteUI(self.WINDOW_NAME)

        cmds.window(
            self.WINDOW_NAME,
            title="Inner Support Extrude Tool v3.1",
            sizeable=True,
            resizeToFitChildren=False,
            widthHeight=(430, 720)
        )

        scroll = cmds.scrollLayout(
            horizontalScrollBarThickness=0,
            verticalScrollBarThickness=16,
            childResizable=True
        )

        main = cmds.columnLayout(
            adjustableColumn=True,
            rowSpacing=8,
            columnOffset=("both", 10),
            parent=scroll
        )

        cmds.text(label="Inner Support Extrude Tool", align="center", height=28, font="boldLabelFont")
        cmds.separator(height=8, style="in")

        self.ui["status"] = cmds.text(label="Select faces, then press Start Edit.", align="left", height=34)

        cmds.button(label="Start Edit From Selection", height=34, command=lambda *_: self.start_edit_from_selection())

        cmds.separator(height=10, style="in")
        cmds.text(label="Shape", align="left", font="boldLabelFont")

        self.ui["outer_inset"] = cmds.floatSliderGrp(
            label="Outer Inset", field=True,
            minValue=0.05, maxValue=0.99, value=0.72,
            step=0.01, columnWidth3=(140, 60, 160),
            dragCommand=lambda *_: self.on_value_changed(),
            changeCommand=lambda *_: self.on_value_changed()
        )

        self.ui["outer_support"] = cmds.floatSliderGrp(
            label="Outer Support", field=True,
            minValue=0.05, maxValue=1.00, value=0.93,
            step=0.01, columnWidth3=(140, 60, 160),
            dragCommand=lambda *_: self.on_value_changed(),
            changeCommand=lambda *_: self.on_value_changed()
        )

        self.ui["top_support"] = cmds.floatSliderGrp(
            label="Top Support", field=True,
            minValue=0.00, maxValue=1.00, value=0.08,
            step=0.01, columnWidth3=(140, 60, 160),
            dragCommand=lambda *_: self.on_value_changed(),
            changeCommand=lambda *_: self.on_value_changed()
        )

        self.ui["entrance_support"] = cmds.floatSliderGrp(
            label="Entrance Support", field=True,
            minValue=0.00, maxValue=1.00, value=0.08,
            step=0.01, columnWidth3=(140, 60, 160),
            dragCommand=lambda *_: self.on_value_changed(),
            changeCommand=lambda *_: self.on_value_changed()
        )

        self.ui["inner_support"] = cmds.floatSliderGrp(
            label="Inner Support", field=True,
            minValue=0.05, maxValue=1.00, value=0.88,
            step=0.01, columnWidth3=(140, 60, 160),
            dragCommand=lambda *_: self.on_value_changed(),
            changeCommand=lambda *_: self.on_value_changed()
        )

        cmds.separator(height=10, style="in")
        cmds.text(label="Depth", align="left", font="boldLabelFont")

        self.ui["depth"] = cmds.floatSliderGrp(
            label="Depth", field=True,
            minValue=-5.00, maxValue=5.00, value=-0.40,
            step=0.01, columnWidth3=(140, 60, 160),
            dragCommand=lambda *_: self.on_value_changed(),
            changeCommand=lambda *_: self.on_value_changed()
        )

        cmds.separator(height=10, style="in")
        cmds.text(label="Options", align="left", font="boldLabelFont")

        self.ui["delete_cap"] = cmds.checkBox(
            label="Delete final cap / create hole",
            value=False,
            changeCommand=lambda *_: self.on_value_changed()
        )

        self.ui["wireframe_on_shaded"] = cmds.checkBox(
            label="Wireframe on Shaded",
            value=False,
            changeCommand=lambda *_: self.toggle_wireframe_on_shaded()
        )

        self.ui["live_update"] = cmds.checkBox(label="Live Update", value=True)
        self.ui["keep_faces_selected"] = cmds.checkBox(label="Keep working faces selected", value=True)

        cmds.separator(height=10, style="in")

        cmds.rowLayout(numberOfColumns=2, columnWidth2=(195, 195), columnAlign2=("center", "center"))
        cmds.button(label="Update Preview", height=34, width=185, command=lambda *_: self.update_preview())
        cmds.button(label="Reset Values", height=34, width=185, command=lambda *_: self.reset_values())
        cmds.setParent(main)

        cmds.separator(height=10, style="in")

        cmds.rowLayout(numberOfColumns=2, columnWidth2=(195, 195), columnAlign2=("center", "center"))
        cmds.button(label="Apply", height=38, width=185, command=lambda *_: self.apply_edit())
        cmds.button(label="Cancel / Restore", height=38, width=185, command=lambda *_: self.cancel_edit())
        cmds.setParent(main)

        cmds.separator(height=10, style="in")

        cmds.text(
            label="Tip: select faces, Start Edit, adjust values, then Apply.",
            align="center",
            height=34
        )

        cmds.showWindow(self.WINDOW_NAME)

    def get_values(self):
        return {
            "outer_inset": cmds.floatSliderGrp(self.ui["outer_inset"], query=True, value=True),
            "outer_support": cmds.floatSliderGrp(self.ui["outer_support"], query=True, value=True),
            "top_support": cmds.floatSliderGrp(self.ui["top_support"], query=True, value=True),
            "entrance_support": cmds.floatSliderGrp(self.ui["entrance_support"], query=True, value=True),
            "inner_support": cmds.floatSliderGrp(self.ui["inner_support"], query=True, value=True),
            "depth": cmds.floatSliderGrp(self.ui["depth"], query=True, value=True),
            "delete_cap": cmds.checkBox(self.ui["delete_cap"], query=True, value=True),
            "keep_faces_selected": cmds.checkBox(self.ui["keep_faces_selected"], query=True, value=True),
        }

    def get_live_update(self):
        return cmds.checkBox(self.ui["live_update"], query=True, value=True)

    def reset_values(self):
        cmds.floatSliderGrp(self.ui["outer_inset"], edit=True, value=0.72)
        cmds.floatSliderGrp(self.ui["outer_support"], edit=True, value=0.93)
        cmds.floatSliderGrp(self.ui["top_support"], edit=True, value=0.08)
        cmds.floatSliderGrp(self.ui["entrance_support"], edit=True, value=0.08)
        cmds.floatSliderGrp(self.ui["inner_support"], edit=True, value=0.88)
        cmds.floatSliderGrp(self.ui["depth"], edit=True, value=-0.40)
        cmds.checkBox(self.ui["delete_cap"], edit=True, value=False)
        self.on_value_changed()

    def toggle_wireframe_on_shaded(self):
        state = cmds.checkBox(self.ui["wireframe_on_shaded"], query=True, value=True)
        panels = cmds.getPanel(type="modelPanel") or []

        for panel in panels:
            try:
                cmds.modelEditor(panel, edit=True, wireframeOnShaded=state)
            except Exception:
                pass

    def on_value_changed(self):
        if self.is_updating:
            return

        if self.is_editing and self.get_live_update():
            self.update_preview()

    def start_edit_from_selection(self):
        selection = cmds.ls(selection=True, flatten=True) or []
        faces = [s for s in selection if ".f[" in s]

        if not faces:
            cmds.warning("Select one or more polygon faces first.")
            return

        objects = list(set([f.split(".")[0] for f in faces]))

        if len(objects) != 1:
            cmds.warning("Select faces from only one mesh.")
            return

        self.cleanup_backup()

        self.original_object = objects[0]
        self.face_indices = self.extract_face_indices(faces)

        backup = cmds.duplicate(self.original_object, name=self.original_object + "_INNER_SUPPORT_BASE")[0]
        self.base_backup_object = backup
        cmds.hide(self.base_backup_object)

        self.is_editing = True
        self.set_status("{} face(s) captured on: {}".format(len(self.face_indices), self.original_object))

        self.update_preview()

    def apply_edit(self):
        if not self.is_editing:
            cmds.warning("No active edit session.")
            return

        self.cleanup_backup()
        self.is_editing = False
        self.set_status("Applied to: {}".format(self.original_object))
        cmds.inViewMessage(amg="Inner Support Extrude applied.", pos="midCenter", fade=True)

    def cancel_edit(self):
        if not self.is_editing:
            cmds.warning("No active edit session.")
            return

        self.restore_from_backup()
        self.cleanup_backup()
        self.is_editing = False
        self.set_status("Restored original mesh.")

    def cleanup_backup(self):
        if self.base_backup_object and cmds.objExists(self.base_backup_object):
            cmds.delete(self.base_backup_object)

        self.base_backup_object = None

    def set_status(self, text):
        if "status" in self.ui and cmds.text(self.ui["status"], exists=True):
            cmds.text(self.ui["status"], edit=True, label=text)

    def restore_from_backup(self):
        if not self.original_object or not self.base_backup_object:
            return

        if not cmds.objExists(self.original_object) or not cmds.objExists(self.base_backup_object):
            return

        temp_name = self.original_object + "_TEMP_TO_DELETE"

        cmds.rename(self.original_object, temp_name)
        restored = cmds.duplicate(self.base_backup_object, name=self.original_object)[0]
        cmds.showHidden(restored)

        if cmds.objExists(temp_name):
            cmds.delete(temp_name)

        self.original_object = restored

    def restore_geometry_only(self):
        if not self.original_object or not self.base_backup_object:
            return

        if not cmds.objExists(self.original_object) or not cmds.objExists(self.base_backup_object):
            return

        original_name = self.original_object
        temp_name = original_name + "_LIVE_TEMP_DELETE"

        cmds.rename(original_name, temp_name)
        restored = cmds.duplicate(self.base_backup_object, name=original_name)[0]
        cmds.showHidden(restored)

        if cmds.objExists(temp_name):
            cmds.delete(temp_name)

        self.original_object = restored

    def update_preview(self):
        if not self.is_editing:
            cmds.warning("Press Start Edit From Selection first.")
            return

        self.is_updating = True

        try:
            self.restore_geometry_only()

            face_selection = self.build_face_selection(self.original_object, self.face_indices)
            cmds.select(face_selection, replace=True)

            self.run_extrude_chain(face_selection, self.get_values())

            if not self.get_values()["keep_faces_selected"]:
                cmds.select(clear=True)

        except Exception as e:
            cmds.warning("Preview update failed: {}".format(e))

        self.is_updating = False

    def run_extrude_chain(self, face_selection, values):
        cmds.select(face_selection, replace=True)

        depth = values["depth"]
        top_support = values["top_support"]
        entrance_support = values["entrance_support"]

        direction = -1 if depth < 0 else 1

        top_depth = direction * abs(top_support)
        entrance_depth = direction * abs(entrance_support)

        remaining_depth = depth - top_depth - entrance_depth

        # 01 - Main inset
        cmds.polyExtrudeFacet(
            constructionHistory=False,
            keepFacesTogether=True,
            localScaleX=values["outer_inset"],
            localScaleY=values["outer_inset"],
            localScaleZ=values["outer_inset"]
        )

        # 02 - Outer/front support loop
        cmds.polyExtrudeFacet(
            constructionHistory=False,
            keepFacesTogether=True,
            localScaleX=values["outer_support"],
            localScaleY=values["outer_support"],
            localScaleZ=values["outer_support"]
        )

        # 03 - Top support loop
        if abs(top_support) > 0.0001:
            cmds.polyExtrudeFacet(
                constructionHistory=False,
                keepFacesTogether=True,
                localTranslateZ=top_depth
            )

        # 04 - Main depth
        cmds.polyExtrudeFacet(
            constructionHistory=False,
            keepFacesTogether=True,
            localTranslateZ=remaining_depth
        )

        # 05 - Entrance / lower support loop
        if abs(entrance_support) > 0.0001:
            cmds.polyExtrudeFacet(
                constructionHistory=False,
                keepFacesTogether=True,
                localTranslateZ=entrance_depth
            )

        # 06 - Inner/back support loop
        cmds.polyExtrudeFacet(
            constructionHistory=False,
            keepFacesTogether=True,
            localScaleX=values["inner_support"],
            localScaleY=values["inner_support"],
            localScaleZ=values["inner_support"]
        )

        # 07 - Optional cap delete
        if values["delete_cap"]:
            current = cmds.ls(selection=True, flatten=True) or []
            if current:
                cmds.delete(current)

    def extract_face_indices(self, faces):
        indices = []

        for face in faces:
            clean = face.split(".f[")[-1].replace("]", "")

            if ":" in clean:
                start, end = clean.split(":")
                indices.extend(range(int(start), int(end) + 1))
            else:
                indices.append(int(clean))

        return sorted(list(set(indices)))

    def build_face_selection(self, obj, indices):
        return ["{}.f[{}]".format(obj, i) for i in indices]


tool = InnerSupportExtrudeToolV31()
tool.show()