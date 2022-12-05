# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT

import bpy
from bpy.types import Operator
from bpy.props import StringProperty


class POSE_OT_MessageBox(Operator):
    """Pops up a message for the viewer"""
    bl_idname = "wm.message_box"
    bl_label = "Info"

    message : StringProperty(name="Message", default="My message", description = "Message to display.")
    icon    : StringProperty(name="Icon", default="INFO")
    title   : StringProperty(name="Title", default="Info", description = "Title to display in the message box.")

    def max_chars(self):
        self.max = 0
        for line in self.message.splitlines():
            self.max = max(self.max, len(line))

        self.max = self.max * 6
    def draw(self, context):
        self.bl_label = self.title
        layout = self.layout

        box = layout.box()
        row = box.row(align=False)
        row.label(text="", icon=self.icon)
        col = row.column(align=True)
        for line in self.message.splitlines():
            col.label(text=line)

    def execute(self, context):
        return {'FINISHED'}

    def invoke(self, context, event):
        wm = context.window_manager
        self.max_chars()
        return wm.invoke_props_dialog(self, width=self.max)


def register():
    bpy.utils.register_class(POSE_OT_MessageBox)

def unregister():

    bpy.utils.unregister_class(POSE_OT_MessageBox)


if __name__ == '__main__':
    register()

