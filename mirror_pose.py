# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT

import bpy
from bpy.types import Panel, PropertyGroup, Scene
from bpy.props import (
    IntProperty,
    BoolProperty,
    )
from bpy.app.handlers import persistent # Add handler to ensure code runs after Blender launches


# Create an opperator to mirror the controls in a selected layer over a series of frames
#
class mirror_pose(bpy.types.Operator):
    """Mirror Layer Pose"""
    bl_idname = "pose.mirror_pose"
    bl_label = "Mirror Pose"
    bl_options = {'REGISTER'}

    # The start frame
    #
    #
    start_frame: IntProperty(
        name = "Start Frame",
        description = "Frame to start copying poses on.",
        default = -1000)

    # The end frame
    end_frame: IntProperty(
        name = "End Frame",
        description = "Frame to stop copying poses on.",
        default = -1000)

    # whether or not to use a frame range, or the current frame.
    # default is to copy just the current frame.
    range: BoolProperty(
        name = "Copy Range",
        description = "Bake a frame range. If off, it will copy the current frame.",
        default = False
    )

    # Only let this operataor exist if we're in POSE mode.
    @classmethod
    def poll(cls, context):
        return (context.mode == 'POSE')


    def execute(self, context):

        # Get the original selection
        selected = context.active_pose_bone.name
        current_frame = context.scene.frame_current

        # Check and see if we are baking a range of frames. If so
        # then let's set the start and end frames appropriately.
        # if not, then we'll use the current frame.
        if self.range == True:

            # HACK to check for current_frame
            if self.start_frame == -1000:
                self.start_frame = current_frame
            if self.end_frame == -1000:
                self.end_frame = current_frame
        else:
            self.start_frame = current_frame
            self.end_frame = current_frame

        if selected == None:
            print('You have no selected pose bones.')
            return {'CANCELLED'}

        o = context.object
        if o == None:
            print('You have no selected objects.')
            return {'CANCELLED'}

        bone = o.data.bones[selected]

        pose = bpy.ops.pose
        for i in range(self.start_frame, self.end_frame+1):
            context.scene.frame_set(i)

            # select all bones in layer
            pose.select_grouped(type='LAYER')

            # copy the pose
            pose.copy()

            # select the mirrored controls
            pose.select_mirror()

            # paste the pose
            pose.paste(flipped=True)

            # clear the selection
            bpy.ops.pose.select_all(action='DESELECT')

            # select the original
            bone.select=True
            o.data.bones.active = bone

        # success

        return {'FINISHED'}



# register all the classes
def register():
    bpy.utils.register_class(mirror_pose)

def unregister():
    bpy.utils.unregister_class(mirror_pose)


if __name__ == '__main__':
    register()
