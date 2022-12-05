# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT

import bpy
import ast
import re


from pose_library import pose_creation

class PoseLibrary_Create(bpy.types.Operator):
    """Create Pose Library"""
    bl_idname = "pose.create_pose_library"
    bl_label = "Create Pose Library"
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        # only work if in POSE mode and you have a bone selected.
        return (context.mode == 'POSE' and context.active_pose_bone != None)

    def getPoses(self, context):
        markers = context.scene.timeline_markers

        self.poses = []
        for m, marker in enumerate(markers):
            pose_list = marker.poses

            for p, pose in enumerate(pose_list):
                self.poses.append({
                    'marker_index': m,
                    'marker_name': marker.name,
                    'marker_frame': marker.frame,
                    'marker_ignore': ast.literal_eval(marker.ignore), # convert string to array
                    'marker_layers': ast.literal_eval(marker.layers), # convert string to array
                    'marker_mirror': marker.mirror,
                    'pose_index': p,
                    'pose_name': pose.name,
                    'pose_frame': marker.frame + p,
                    'pose_description': pose.description,
                    'pose_skip': pose.skip
                })

    def getSelectedArmature(self, context):
        try:
            self.arm = context.pose_object.data
        except:
            return False

    def storeCurrentLayers(self):
        layersOn = []
        for i in range(0,32):
            if self.arm.layers[i]:
                layersOn.append(i)
        self.layersOn = layersOn

    def setPoseLayers(self, layersOn):
        for i in range(0,32):
            if i in layersOn:
                self.arm.layers[i] = True
            else:
                self.arm.layers[i] = False

    def mirrorPose(self, context, mirror):
        # Based on the mirror specified:
        # - Store the original selection
        # - Select the controls that match that side
        # - copy the pose
        # - select the mirrored controls
        # - paste flipped
        # - re-select the original slection

        # store orig bones
        orig_bones = context.selected_pose_bones

        pose = bpy.ops.pose

        # clear selection
        pose.select_all(action='DESELECT')

        # select all bones on the mirrored side
        bpy.ops.object.select_pattern(pattern=f'*[{mirror}]')

        # copy the pose
        pose.copy()

        # select the mirrored controls
        pose.select_mirror()

        # paste the pose
        pose.paste(flipped=True)

        # set a keyframe
        bpy.ops.anim.keyframe_insert_menu(type='WholeCharacterSelected')

        # clear the selection
        pose.select_all(action='DESELECT')

        # reselect orig bones
        pose.select_all(action='SELECT')

    def deselectIgnoredBones(self,  ignore_bones):

        selected_pose_bones = bpy.context.selected_pose_bones

        for bone in selected_pose_bones:
            # check if the name matches ignore_bones
            # if so, deselect it

            name = bone.name

            for ignore in ignore_bones:
                if bool(re.fullmatch(ignore, name)):
                    bone.bone.select=False
                    print(f'Ignoring: {name}')

    def createLibPoses(self, context):

        self.poses_new = 0
        self.poses_failed = 0
        self.poses_skipped = 0

        for i, item in enumerate(self.poses):
            prefix = item['marker_name']
            layers = item['marker_layers']
            mirror = item['marker_mirror']
            ignore_bones = item['marker_ignore']
            frame = item['pose_frame']
            name = item['pose_name']
            description = item['pose_description']
            skip = item['pose_skip']

            if skip:
                self.poses_skipped += 1
                continue
            # set the layers for the specified pose
            self.setPoseLayers(layers)

            # select the controls in the layers
            bpy.ops.pose.select_all(action='SELECT')

            # Deselect the controls that are to be ignored
            if len(ignore_bones) > 0:
                self.deselectIgnoredBones(ignore_bones)

            # Set the frame
            #self.report({'INFO'},  (f"Setting frame to {frame}"))
            context.scene.frame_set(int(frame))
            new_name = (f"{prefix} - {name}")

            # delete the existing pose asset if it already exists
            if new_name in bpy.data.actions.keys():
                print(f'Pose exists: {new_name}. Deleting...')
                action = bpy.data.actions[new_name]
                bpy.data.actions.remove(action)

            # if mirror is not none, we'll need to copy poses from the mirror side
            # to the other side.
            if mirror != "":
                self.mirrorPose(context,mirror)

            # create the pose
            try:
                new_pose = pose_creation.create_pose_asset_from_context(context, new_name)
                new_pose.asset_data.description = description
                self.poses_new += 1
            except:
                self.poses_failed += 1


    def execute(self, context):

        # get all the poses specified
        self.getPoses(context)

        # get the selected armature
        self.getSelectedArmature(context)

        # store the current layers
        self.storeCurrentLayers()

        # create poses
        self.createLibPoses(context)

        # reset the current layers
        self.setPoseLayers(self.layersOn)

        # return result
        message = "you have updated the pose library.\n\n"
        message += (f"{self.poses_new} pose(s) created successfully.\n")
        message += (f"{self.poses_failed} pose(s) failed.\n")
        message += (f"{self.poses_skipped} poses(s) skipped.\n")
        bpy.ops.wm.message_box('INVOKE_DEFAULT',
            message = message)
        return {'FINISHED'}

classes = [
    PoseLibrary_Create
]
def register():

    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():

    classes.reverse()
    for cls in classes:
        bpy.utils.unregister_class(cls)

if __name__ == '__main__':
    register()
