# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT

import ast
import datetime
import getpass
import json
import os
import subprocess
import textwrap
import tempfile

import bpy
from bpy.app.handlers import \
    persistent  # Add handler to ensure code runs after Blender launches

from bpy.props import (BoolProperty, CollectionProperty, EnumProperty,
                       FloatVectorProperty, IntProperty, PointerProperty,
                       StringProperty)

from bpy.types import Menu, Operator, PropertyGroup, UIList
from bpy_extras.io_utils import ExportHelper, ImportHelper


# -------------------------------------------------------------------
#   Properties
# -------------------------------------------------------------------

#
class CUSTOM_PoseProps(PropertyGroup):
    """Group of properties representing an item in the category list."""

    # because I want to sort by frame number, I need to call out the "name" first

    name: StringProperty(
        name="Name",
        description = "Name of the pose",
        default="New Pose"
    )
    description: StringProperty(
        name = "Description",
        description = "Description of the pose",
        default = ""
    )
    skip: BoolProperty(
        name = "Skip",
        description = "Skip this pose",
        default = False
    )


# -------------------------------------------------------------------
#   Operators
# -------------------------------------------------------------------
class CATEGORY_OT_Clear(Operator):
    """Clear the Pose Library Categorys and Poses."""

    bl_idname = "category.clear"
    bl_label = "Clear Categorys"
    bl_options = {'REGISTER'}

    cameras: BoolProperty(
        name="Clear Cameras",
        description="Include cameras when clearing.",
        default=False,
    )

    poses: BoolProperty(
        name = "Clear Poses",
        description = "Clears all poses. If Categories is true, poses will be cleared by default.",
        default = True
    )

    categories: BoolProperty (
        name = "Clear Categories",
        description = "Clear categories.",
        default = True
    )

    @classmethod
    def poll(cls, context):
        if len(context.scene.timeline_markers) > 0:
            return True
        else:
            return False

    def clearCameras(self):
        """Clear all cameras from the scene"""
        cam = bpy.data.cameras
        cameras = cam.items()

        for name, camera in cameras:
            try:
                cam.remove(camera, do_unlink=True)
            except:
                self.report({'WARNING'}, f"Could not remove {name}. Skipping.")

    def clearCategories(self, context):
        """Clear all existing categorys"""
        context.scene.timeline_markers.clear()

    def clearPoses(self, context):
        markers = context.scene.timeline_markers
        for marker in markers:
            marker.poses.clear()

    def execute(self, context):

        if self.cameras:
            self.clearCameras()

        if not self.categories:
            if self.poses:
                self.clearPoses(context)
        else:
            self.clearCategories(context)

        return {'FINISHED'}

class CATEGORY_OT_Export(Operator, ExportHelper):
    """Export the Pose Library Categorys and Poses."""

    bl_idname = "category.export"
    bl_label = "Export Categorys"
    bl_options = {'REGISTER'}

    # ExportHelper mixin class uses this
    filename_ext = ".json"
    tempdir = tempfile.gettempdir()
    tmp_py = os.path.join(tempdir, "lib_cam_export.py")

    filter_glob: StringProperty(
        default="*.json",
        options={'HIDDEN'},
        maxlen=255,  # Max internal buffer length, longer would be clamped.
    )

    include_cameras: BoolProperty(
        name="Include Cameras",
        description="Include cameras when exporting.",
        default=False,
    )


    @classmethod
    def poll(cls, context):
        if len(context.scene.timeline_markers) > 0:
            return True
        else:
            return False

    def getPoses(self, context):
        """Builds a json file structure of markers and poses"""
        markers = context.scene.timeline_markers
        self.data = {}
        self.cameras = []
        # store some information about the file
        self.data['info'] = {
            "description"   : "This file contains pose data for Blender's Pose Library.",
            "user"          : get_user(),
            "filepath"      : bpy.data.filepath,
            "date"          : date()
        }
        # Create overall settings
        self.data['settings'] = {
            "category_start_frame"   : context.scene.category_start_frame,
            "category_increments"    : context.scene.category_increments,
            "category_active_index"  : context.scene.category_active_index,
            "category_activate_layers": context.scene.category_activate_layers,
            "category_hide_ignore"  : context.scene.category_hide_ignore,
            "pose_increments"       : context.scene.pose_increments,
            "pose_include_neutral"  : context.scene.pose_include_neutral
        }
        poses = []
        for m, marker in enumerate(markers):

            build_category = {
                "index"     : m,
                "category"   : marker.name,
                "ignore"    : ast.literal_eval(marker.ignore), # convert string to array
                'layers'    : ast.literal_eval(marker.layers), # convert string to array
                'mirror'    : marker.mirror,
                'camera'    : str(marker.camera.name)

            }
            if marker.camera and self.include_cameras:
                self.cameras.append(str(marker.camera.name))

            pose_list = marker.poses

            build_list = []
            for p, pose in enumerate(pose_list):
                build_pose ={
                    'index': p,
                    'name': pose.name,
                    'description': pose.description,
                }
                build_list.append(build_pose)
            build_category['pose'] = build_list

            poses.append(build_category)

        self.data['poses'] = poses

    def createCameraPythonScript(self, context, path, name):
        filepath = os.path.join(path, (name + "_cameras.blend"))
        lines = [
            'import bpy',
            'import os',
            (f'blendfile = "{self.mytempfile}"'),
            (f'category = "\\\Object\\\\"'),
            (f'objects = {self.cameras}'),
            '# prev context',
            'mode = bpy.context.mode',
            '',
            'if not mode=="OBJECT":',
            '    bpy.ops.object.mode_set(mode="OBJECT")',
            '',
            '# delete everything in the file',
            'for obj in bpy.data.objects:',
            '    obj.select_set(True)',
            '',
            'bpy.ops.object.delete()',
            '',
            '# grab the camera objects from the mayu.blend file',
            '',
            'for object in objects:',
            '    bpy.ops.wm.append(',
            '        filepath=(blendfile + category + object),',
            '        directory = (blendfile + category),',
            '        filename = object)',
            (f'bpy.ops.wm.save_as_mainfile(filepath="{filepath}", check_existing=False)')
        ]

        x = '\n'.join(lines)

        with open(self.tmp_py,"w+") as f:
            f.writelines(x)

    def exportCamera(self, context):
        path = os.path.dirname(self.filepath)
        base = os.path.basename(self.filepath)
        name = os.path.splitext(base)[0]
        self.data['camera_file'] = {
            "path": path,
            "file": f"{name}_cameras.blend"
        }

        self.createCameraPythonScript(context, path, name)

    def run_export_camera_command(self):
        self.blender_cmd = bpy.app.binary_path

        subprocess.Popen([f"{self.blender_cmd}","--background", "--python",f"{self.tmp_py}"])



    def execute(self, context):
        self.mytempfile = save_tempfile()

        self.getPoses(context)

        if len(self.data) > 0:
            if self.include_cameras:
                # Export cameras
                self.exportCamera(context)

            #bpy.ops.category.open_filebrowser()
            json_object = json.dumps(self.data, indent=4)

            # Writing to sample.json
            with open(self.filepath, "w") as outfile:
                outfile.write(json_object)

            # Now run blender in the background with that python script
            self.run_export_camera_command()


        return {'FINISHED'}

class CATEGORY_OT_Import(Operator):
    """Import the Pose Library Categorys and Poses."""

    bl_idname = "category.do_import"
    bl_label = "Import Categorys"
    bl_options = {'REGISTER'}

    filepath: StringProperty(
        name = "Filepath",
        description = "Path of the library json file.",
        default = ""
    )

    include_cameras: BoolProperty(
        name="Include Cameras",
        description="Include cameras when importing.",
        default=False,
    )

    def read(self, context):
        """Reads the JSON file """
        f = open(self.filepath)
        self.data = json.load(f)
        f.close()

    def createSettings(self, context):
        """Apply the settings"""
        scene = context.scene

        # now update them.
        for i in self.data['settings']:
            setattr(scene, i, self.data['settings'][f"{i}"])

    def addPoses(self,context):
        for i in self.data['poses']:
            # create the markers first
            name = i['category']
            ignore = str(i['ignore'])
            layers = str(i['layers'])
            mirror = i['mirror']
            camera = i['camera']

            bpy.ops.category.new_item(
                new_name = name,
                camera = camera,
                layers = layers,
                ignore = ignore,
                mirror = mirror,
                skip_poses = True)

            # Now create the poses
            for p in i['pose']:
                name = p['name']
                description = p['description']

                bpy.ops.category.new_pose(new_name = name, description = description)

    def gatherCameras(self):
        self.camerasToImport = []
        for p in self.data['poses']:
            self.camerasToImport.append(p['camera'])

    def importCameras(self):
        """Import the camera from the camera file"""
        path = self.data['camera_file']['path']
        file = self.data['camera_file']['file']

        # See if the camera file is next to the json file first.
        # if so, then we'll use that.
        # if not, we'll try the full path.
        blendfile = os.path.join(os.path.dirname(self.filepath), file)

        if not os.path.isfile(blendfile):
            print('file not local')
            # nope, let's try the fullpath
            blendfile = os.path.join(path,file)
            if not os.path.isfile(blendfile):
                print('failed')
                self.report({'WARNING'}, f"Camera file: {blendfile} could not be found.")
                return False

        # now defne the category and objects
        category = "\\Object\\"
        objects = self.camerasToImport

        for object in objects:
            print(f"importing {object} from {blendfile}")
            try:
                bpy.ops.wm.append(
                    filepath=(blendfile + category + object),
                    directory = (blendfile + category),
                    filename = object)
            except:
                print(f'Something failed when trying to bring in {object}')

    def execute(self, context):
        self.cwd = os.path.dirname(__file__)

        if self.filepath == "":
            self.filepath = os.path.join(self.cwd, "templates", "library.json")

        self.read(context)

        if len(context.scene.timeline_markers) > 0:
            bpy.ops.category.clear(cameras = self.include_cameras, categories = True)

        if self.include_cameras:
            self.gatherCameras()
            self.importCameras()

        self.createSettings(context)
        #self.clearCategorys(context)
        self.addPoses(context)

        return {'FINISHED'}

class CATEGORY_OT_Import_Prompt(Operator, ImportHelper):
    """Prompt User for Import File."""

    bl_idname = "category.do_import_prompt"
    bl_label = "Import Categorys"
    bl_options = {'REGISTER'}

    # ExportHelper mixin class uses this
    filename_ext = ".json"

    filter_glob: StringProperty(
        default="*.json",
        options={'HIDDEN'},
        maxlen=255,  # Max internal buffer length, longer would be clamped.
    )

    include_cameras: BoolProperty(
        name="Include Cameras",
        description="Include cameras when importing.",
        default=False,
    )

    def execute(self, context):

        if not self.filepath:
            return {'FINISHED'}

        bpy.ops.category.do_import(filepath = self.filepath, include_cameras = self.include_cameras)

        return {'FINISHED'}

class CATEGORY_OT_SetIgnoreControls(Operator):
    """Uses the selection to choose controls to ignore"""
    bl_idname = "category.set_ignore_controls"
    bl_label = "Set controls to ignore"

    @classmethod
    def poll(cls, context):
        # only work if in POSE mode and you have a bone selected.
        return (context.mode == 'POSE' and context.active_pose_bone != None)

    def getSelectedBones(self, context):
        self.ignore_bones = []

        for bone in context.selected_pose_bones:
            self.ignore_bones.append(bone.name)

    def execute(self, context):
        # find out the active layers for the selected armature
        self.getSelectedBones(context)

        scene = context.scene
        category = scene.timeline_markers[scene.category_active_index]
        category.ignore = str(self.ignore_bones)

        return {'FINISHED'}

class CATEGORY_OT_PickLayers(Operator):
    """Opens the layers picker"""
    bl_idname = "category.pick_layers"
    bl_label = "Select Armature Layers"
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        return context.mode == "POSE"

    def execute(self, context):
        if is_active_cloudrig(context):
            try:
                bpy.ops.pose.cloudrig_select_layers('INVOKE_DEFAULT')
            except:
                bpy.ops.armature.armature_layers()

        else:
            bpy.ops.armature.armature_layers()

        return {'FINISHED'}

class CATEGORY_OT_SelectCamera(Operator):
    """Selects the camera for the active layer"""
    bl_idname = "category.select_camera"
    bl_label = "Select Camera"

    def execute(self, context):
        # get the current marker
        marker = get_marker(context)

        camera = marker.camera
        camera.select_set(True)
        print(camera)
        return {'FINISHED'}

class CATEGORY_OT_SetActiveLayers(Operator):
    """Sets the category to use the active display layers"""
    bl_idname = "category.set_active_layers"
    bl_label = "Set active layers"
    bl_options = {'REGISTER'}

    def execute(self, context):
        # find out the active layers for the selected armature
        arm = get_arm(context)
        layers = get_current_layers(arm)

        scene = context.scene
        category = scene.timeline_markers[scene.category_active_index]

        category.layers = str(layers)

        return {'FINISHED'}


class CATEGORY_OT_FixMarkers(Operator):
    """Fix all markers to work with the library by making sure they're linked to cameras and they have names."""
    bl_idname = "category.fix_markers"
    bl_label = "Fix Category Markers"


    @classmethod
    def poll(cls, context):
        if len(context.scene.timeline_markers) > 0:
            return True
        else:
            return False

    def execute(self, context):
        scene = context.scene
        markers = scene.timeline_markers

        for marker in markers:
            if not marker.camera_pointer:
                if marker.camera.name:
                    marker.camera_pointer = bpy.data.objects[f'{marker.camera.name}']

            if marker.name == "" and not marker.camera.name == "":
                marker.name = marker.camera.name
        return {'FINISHED'}

class CATEGORY_OT_Remove(Operator):
    """Go to the selected frame"""
    bl_idname = "category.remove"
    bl_label = "Remove this category"

    frame : IntProperty()

    @classmethod
    def poll(cls, context):
        markers_exist = len(context.scene.timeline_markers)
        if markers_exist > 0:
            return True
        else:
            return False

    def execute(self, context):
        scene = context.scene
        frameToDel = self.frame
        if not self.frame:
            # get the index of the marker selected
            index = scene.category_active_index

            # now find out what the frame number is
            frameToDel = scene.timeline_markers[index].frame

        for marker in scene.timeline_markers:
            if marker.frame == frameToDel:
                scene.timeline_markers.remove(marker)
                break

        num_markers = len(scene.timeline_markers)
        if scene.category_active_index == num_markers and not num_markers == 0:
            scene.category_active_index = len(scene.timeline_markers) -1
        else:
            # iterate through the rest of the categorys and reset the frame
            for i, marker in enumerate(scene.timeline_markers):
                new_frame = scene.category_start_frame
                if i > 0:
                    new_frame = i * scene.category_increments + scene.category_start_frame
                marker.frame = new_frame

        return {'FINISHED'}

class CATEGORY_OT_NewCam(Operator):
    """Add a new camera for the category"""
    bl_idname = "category.new_cam"
    bl_label = "Add a new camera for the category"

    name: StringProperty(
        name = "Camera Name",
        default="Camera"
    )

    lens : IntProperty(
        name = "Lens",
        default = 85
    )

    location: FloatVectorProperty (
        name = 'location',
        default = (0, -3, 1)
    )

    rotation_euler: FloatVectorProperty(
        name = 'rotation_euler',
        default = (1.5, 0, 0)
    )

    use_category: BoolProperty(
        name = "Category",
        default = False
    )

    def execute(self, context):
        mode = context.mode
        if not mode == 'OBJECT':
            bpy.ops.object.mode_set(mode ='OBJECT')

        if self.use_category:
            marker = get_marker(context)
            name = marker.name
            self.name = (f"{name}_cam")
        cam = bpy.data.cameras.new(self.name)

        cam_obj = bpy.data.objects.new(self.name, cam)
        cam_obj.location = self.location
        cam_obj.rotation_euler = self.rotation_euler
        context.scene.collection.objects.link(cam_obj)

        # save this to the window manager for later use
        bpy.context.window_manager['new_camera'] = cam_obj

        if not mode == 'OBJECT':
            bpy.ops.object.mode_set(mode=mode)

        if self.use_category:
            marker = get_marker(context)
            index = context.scene.category_active_index

            marker.camera_pointer = cam_obj

        return {'FINISHED'}

class CATEGORY_OT_NewItem(Operator):
    """Add a new item to the list."""

    bl_idname = "category.new_item"
    bl_label = "Add a new category"
    bl_property = "new_name"

    new_name    :   StringProperty(
        name="Category Name:",
        default="All")

    mirror: EnumProperty(
        items=(('NONE', 'None', "No Mirror"),
                ('L', 'L -> R', "Copy the Left controls to the Right."),
                ('R', 'R -> L', "Copy the Right controls to the Left.")),
        name="Mirror",
        description="Mirror controls when creating library poses.",
        default=None,

    )

    new_camera  :   BoolProperty(
        name="Create New Camera",
        default=False
    )

    camera : StringProperty(
        name = "Camera",
        default="",
        options={'HIDDEN'}

    )

    insert  : BoolProperty(
        default = False,
        name = "Insert",
        description = "Insert in the middle of the list.",
        options={'HIDDEN'}
    )

    ignore : StringProperty(
        name = "Ignore",
        default = "[]",
        description = "Controls to ignore.",
        options={'HIDDEN'}

    )

    layers : StringProperty(
        name = "layers",
        default = "[]",
        description = "Bone layers.",
        options={'HIDDEN'}

    )

    skip_poses: BoolProperty(
        default= False,
        name = "Skip Poses",
        description = "Skips creating a default pose, used mainly when importing.",
        options={'HIDDEN'}
    )


    def create_camera(self):

        # First see if there is an existing scene camera.
        # if not, create one.

        if not self.scene.camera:
            bpy.ops.category.new_cam(name = self.new_name)
            cam_obj = bpy.context.window_manager['new_camera']

            # attach to the scene camera
            self.scene.camera = cam_obj

        # now check and see if we're making a new camera
        if self.new_camera:
            new_cam = duplicate(self.scene.camera, collection=self.scene.collection)
            cam_name = (f"{self.new_name}_cam")
            new_cam.name = cam_name
            new_cam.data.name = cam_name

            # attach to the scene camera
            self.scene.camera = new_cam

    def execute(self, context):

        self.scene = context.scene

        start_frame = self.scene.category_start_frame
        increment = self.scene.category_increments
        active_index = self.scene.category_active_index
        markers = self.scene.timeline_markers
        insert_index = len(markers) # set the default insert instance to be the end.
        shuffle = False

        # if there is no existing marker, go ahead and create one
        if not markers:
            # Create the marker
            marker = self.scene.timeline_markers.new(name=self.new_name, frame=start_frame)
        else:
            # markers exist.
            # get the number of current markers, and create a new one at the end
            # - note this is temporary until we figure out how to insert
            num_markers = len(markers)

            # check and see if the active index is less than the number of markers -
            # if so, we'll need to shuffle
            if (active_index < num_markers -1) and (self.insert == True):
                shuffle = True
                insert_index = active_index

            new_frame = num_markers * increment + start_frame
            marker = self.scene.timeline_markers.new(name=self.new_name, frame=new_frame)

        # if a camera was specified, exists, and new camera wasn't
        # specified, then we'll use it.
        if (not self.new_camera) and (not self.camera == "") and (self.scene.objects.get(self.camera)):
            self.scene.camera = self.scene.objects.get(self.camera)
        else:
            # if new camera was suggested, or one doesn't exist, we'll have to create one
            self.create_camera()

        # Now add the current camera
        marker.camera = self.scene.camera
        marker.camera_pointer = self.scene.camera

        # select the newly created item
        #self.scene.category_active_index = len(self.scene.timeline_markers) -1

        # set the appropriate layers
        if self.layers == "[]":
            arm = get_arm(context)
            layers = get_current_layers(arm)
            marker.layers = (str(layers))

        else:
            marker.layers = self.layers

        marker.ignore = self.ignore

        # mirror
        marker.mirror = self.mirror

        # Now shuffle all markers down if needed
        if shuffle:
            bpy.ops.category.move_item(direction='DOWN', insert=True, insert_index=insert_index)

            # select the original item
            self.scene.category_active_index = insert_index + 1

        else:
            # select the newly created item
            self.scene.category_active_index = len(self.scene.timeline_markers) -1

        if not self.skip_poses:

            # Create a .neutral pose on the same frame
            new_name = "New Pose"
            description = ''
            if self.scene.pose_include_neutral:
                new_name =".neutral"
                description = 'Neutral pose.'
                bpy.ops.category.new_pose(new_name=new_name, description= description)

        return{'FINISHED'}

    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self)


class CATEGORY_OT_MoveItem(Operator):
    """Move an item in the list."""

    bl_idname = "category.move_item"
    bl_label = "Move an item in the list"

    direction   : EnumProperty(items=(('UP', 'Up', ""),
                                              ('DOWN', 'Down', ""),))

    insert      : BoolProperty(default=False, name="Insert", description = "Insert category.")
    insert_index : IntProperty(name = "Insert Index", description = "Insertion index if insert=True.")

    @classmethod
    def poll(cls, context):
        return context.scene.timeline_markers

    def move_index(self, context):
        """ Move index of an item render queue while clamping it. """
        scene = context.scene
        index = scene.category_active_index
        list_length = len(scene.timeline_markers) - 1  # (index starts at 0)
        new_index = index + (-1 if self.direction == 'UP' else 1)

        scene.category_active_index = max(0, min(new_index, list_length))

    def move(self, context, timeline_markers, neighbor, index):
        # because there is no way to actually move a timeline_marker in the list, instead we
        # will shuffle the data by creating a new timeline_marker
        new_marker = timeline_markers.new(name="tmp", frame=-1000)

        # get the properties we want from the index and move them to the new_marker
        props = ['name', 'pose_active_index', 'camera_pointer', 'layers', 'mirror', 'ignore']

        for prop in props:
            # copy the current index attributes to the temporary one
            value = getattr(timeline_markers[index], prop)
            setattr(new_marker, prop, value)

            # copy the neighbor's attributes to the index
            value = getattr(timeline_markers[neighbor], prop)
            setattr(timeline_markers[index], prop, value)

            # copy the temporary attributes to the neighbor
            value = getattr(new_marker, prop)
            setattr(timeline_markers[neighbor], prop, value)

        # Now adjust the poses - this can't just be compied because it's a
        # CollectionProperty
        #
        # index to temporary
        for pose in timeline_markers[index].poses:
            new_pose = new_marker.poses.add()
            new_pose.name = pose.name

        try:
            del timeline_markers[index]['poses']
        except:
            pass

        # neighbor to index
        for pose in timeline_markers[neighbor].poses:
            new_pose2 = timeline_markers[index].poses.add()
            new_pose2.name  = pose.name
        try:
            del timeline_markers[neighbor]['poses']
        except:
            pass

        # temporary to neighbor
        for pose in new_marker.poses:
            new_pose3 = timeline_markers[neighbor].poses.add()
            new_pose3.name = pose.name

        # delete the temporary marker
        marker = len(timeline_markers) -1
        timeline_markers.remove(new_marker)

    def execute(self, context):
        scene = context.scene
        my_list = scene.timeline_markers
        index = context.scene.category_active_index

        if not self.insert:
            neighbor = index + (-1 if self.direction == 'UP' else 1)
            self.move(context, my_list, neighbor, index)
            self.move_index(context)

        else:
            # iterate backwards from the last marker to the index
            for i in reversed(range(index + 2, len(my_list)+1)):
                neighbor = i -1
                self.move(context, my_list, neighbor, i)

        # update frames in category
        return{'FINISHED'}

class POSE_OT_NewItem(Operator):
    """Add a new item to the list."""

    bl_idname = "category.new_pose"
    bl_label = "Add a new pose"
    bl_property = "new_name"

    new_name    :   StringProperty(
        name="Pose Name",
        default="Pose")

    description : StringProperty(
        name = "Description",
        default = ""
    )

    category_index : IntProperty(
        default = -1,
        name = "Category Index",
        description = "Specify the category index. Used when importing.",
        options = {'HIDDEN'}
    )

    insert  : BoolProperty(
        default = False,
        name = "Insert",
        description = "Insert in the middle of the list.",
        options={'HIDDEN'}
    )

    skip : BoolProperty(
        default = False,
        name = "Skip Pose",
        description = "Skip this pose when generating the library."
    )

    @classmethod
    def poll(cls, context):
        # make sure we have a category selected
        scene = context.scene

        if not scene.category_active_index == "":
            return True
        else:
            return False

    def execute(self, context):
        # Get the current info
        marker = get_marker(context)

        pose = get_pose(marker)

        scene = context.scene
        poses = marker.poses
        pose_increment = scene.pose_increments

        pose_index = marker.pose_active_index

        shuffle = False
        # create the marker
        #
        new_name = self.new_name

         # if insert is on, move it to the one after the index
        num_poses = len(marker.poses)
        if (pose_index < num_poses -1) and (self.insert == True):
            print ('inserting?')
            shuffle = True
            insert_index = pose_index

        # set the appropriate layers
        pose = marker.poses.add()
        pose.name = new_name
        pose.description = self.description
        pose.skip = self.skip
        #pose.name = frame

        if shuffle:
            bpy.ops.category.move_pose(direction='DOWN', insert=True)
            marker.pose_active_index = insert_index + 1

        else:
            # select the last one
            marker.pose_active_index = len(marker.poses) -1

        return{'FINISHED'}

    def invoke(self, context, event):
        wm = context.window_manager
        marker = get_marker(context)
        pose = get_pose(marker)
        if pose:
            self.new_name = pose.name
        else:
            if context.scene.pose_include_neutral:
                self.new_name = ".neutral"
            else:
                self.new_name = "New Pose"
        return wm.invoke_props_dialog(self)

class POSE_OT_MoveItem(Operator):
    """Move an item in the list."""

    bl_idname = "category.move_pose"
    bl_label = "Move an item in the list"

    direction   : bpy.props.EnumProperty(items=(('UP', 'Up', ""),
                                              ('DOWN', 'Down', ""),))

    insert      : bpy.props.BoolProperty(default=False, name="Insert", description = "Insert category.")

    @classmethod
    def poll(cls, context):
        marker = get_marker(context)
        if len(marker.poses) > 0:
            return True
        else:
            return False

    def move_index(self, context):
        """ Move index of an item render queue while clamping it. """

        marker = get_marker(context)

        poses = marker.poses
        index = marker.pose_active_index

        list_length = len(poses) - 1  # (index starts at 0)
        new_index = index + (-1 if self.direction == 'UP' else 1)

        marker.pose_active_index = max(0, min(new_index, list_length))

    def execute(self, context):
        marker = get_marker(context)
        pose_list = marker.poses

        index = marker.pose_active_index

        if not self.insert:
            neighbor = index + (-1 if self.direction == 'UP' else 1)
            pose_list.move(neighbor, index)
            self.move_index(context)
        else:
            # iterate backwards from the last pose to the index
            for i in reversed(range(index + 2, len(pose_list)+1)):
                neighbor = i -1
                pose_list.move(neighbor, i)

        return{'FINISHED'}

class POSE_OT_Remove(Operator):
    """Go to the selected pose"""
    bl_idname = "category.remove_pose"
    bl_label = "Remove this pose"

    pose_index : IntProperty()


    def execute(self, context):
        scene = context.scene

        # get the index of the marker selected
        marker = get_marker(context)
        marker.poses.remove(self.pose_index)
        orig_len = len(marker.poses)

        if self.pose_index == orig_len:
            marker.pose_active_index = len(marker.poses) -1

        return {'FINISHED'}

class POSE_OT_Skip(Operator):
    """Toggle skipping of the selected pose"""
    bl_idname = "category.skip_pose"
    bl_label = "Toggle skipping of this pose"

    pose_index : IntProperty()

    def execute(self, context):

        # get the index of the marker selected
        marker = get_marker(context)

        marker.poses[self.pose_index].skip = not marker.poses[self.pose_index].skip

        return {'FINISHED'}

# -------------------------------------------------------------------
#   Menus
# -------------------------------------------------------------------

class CATEGORY_MT_context_menu(Menu):
    bl_label = "Category Menu"

    def draw(self, _context):
        layout = self.layout
        layout.label(text = 'Category Menu')
        layout.separator()
        layout.operator('category.new_item', text='Add Category', icon='BOOKMARKS' )
        layout.operator('category.remove', text='Delete Category', icon='X')
        layout.separator()

        layout.operator('category.clear', text="Clear all Categories", icon="CANCEL").categories = True
        layout.operator('category.clear', text="Clear all Categories and Cameras", icon="CANCEL").cameras = True

        layout.separator()
        layout.separator()
        layout.operator('category.export', icon="EXPORT")
        layout.operator('category.export', icon="CAMERA_DATA", text="Export Categorys & Cameras").include_cameras = True
        layout.separator()
        layout.operator('category.do_import_prompt', icon="IMPORT")
        layout.operator('category.do_import_prompt', icon="CAMERA_DATA", text = "Import Categorys & Cameras").include_cameras = True
        op = layout.operator('category.do_import', icon='IMPORT', text="Import Default Template").include_cameras = True
        layout.separator()
        layout.separator()
        layout.operator('category.fix_markers', text='Fix broken categorys', icon='ACTION_TWEAK' )
        layout.separator()
        mb = layout.operator('wm.message_box', text="Help", icon="QUESTION")
        msg = """Categories define different "types" of poses.
For example: Body, Face, Hands, All.

Please create a category by choosing the "Add" button. """
        mb.message = msg
        mb.icon = "QUESTION"

class POSE_MT_context_menu(Menu):
    bl_label = "Pose Menu"

    def draw(self, _context):
        layout = self.layout
        layout.label(text = 'Pose Menu')
        layout.separator()

        layout.operator('category.new_pose', text='Add Pose', icon='ARMATURE_DATA' )
        layout.operator('category.remove_pose', text='Delete Pose', icon='X')
        layout.separator()
        clear = layout.operator('category.clear', text="Clear all Poses", icon="CANCEL")
        clear.poses = True
        clear.categories = False
        layout.separator()

        mb = layout.operator('wm.message_box', text="Help", icon="QUESTION")
        msg = """Each category can contain multiple poses.

For example, a "Face" category may contain "happy", "mad", "confused".

A library pose will be automatically generated for each frame."""
        mb.message = msg
        mb.icon = "QUESTION"

# -------------------------------------------------------------------
#   UI Lists
# -------------------------------------------------------------------


class POSE_UL_list(UIList):
    """Poses UIList."""

    def draw_item(self, context, layout, data, item, icon, active_data,
                  active_propname, index):
        #self.use_filter_show = False

        marker_list = context.scene.timeline_markers
        marker_index = context.scene.category_active_index
        pose_increment = context.scene.pose_increments
        frame = marker_list[marker_index].frame + (index * pose_increment)
        skip = getattr(item, "skip")

        if self.layout_type in {'DEFAULT', 'COMPACT'}:

            main_row = layout.row(align=False)
            s1 = main_row.row(align=True)
            s1.alignment = 'LEFT'

            s2 = main_row.row(align=True)
            s2.alignment = 'RIGHT'

            s3 = main_row.row(align=True)
            s3.alignment = 'RIGHT'

            s1.enabled = not skip
            s2.enabled = not skip

            row = s1
            row.label(text=f"{frame}", icon="ARMATURE_DATA")

            row.prop(item, "name", text="", emboss=False)

            row = s2
            row.scale_x = 100
            row.prop(item, "description", text="", emboss=False)

            row = s3
            skip_icon = "HIDE_OFF"
            if skip:
                skip_icon = "HIDE_ON"

            row.operator('category.skip_pose', text = '', icon=skip_icon, emboss = False).pose_index = index
            row.operator('category.remove_pose', text='', icon='X', emboss=False).pose_index = index

        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'
            layout.label(text=item.name)

class CATEGORY_UL_list(UIList):

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        self.use_filter_show = False
        scene = data
        ob = item
        #print(data, item, active_data, active_propname)

        layout.use_property_split = True

        if self.layout_type in {'DEFAULT', 'COMPACT'}:

            main_row = layout.row(align=False)
            s1 = main_row.row(align=True)
            s1.alignment = 'LEFT'

            s2 = main_row.row(align=True)
            s2.alignment = 'RIGHT'

            s3 = main_row.row(align=True)
            s3.alignment = 'RIGHT'
            row = s1

            row.label(text=f"{ob.frame}", icon="BOOKMARKS")

            row = s2
            row.scale_x = 10
            row.prop(ob, "name", text="", emboss=False)

            row = s3
            op = row.operator('category.remove', text='', icon='X', emboss=False).frame = ob.frame

# -------------------------------------------------------------------
#   Settings UI
# -------------------------------------------------------------------

class VIEW3D_PT_FP_libUI(bpy.types.Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Pose Library"
    bl_options = {'DEFAULT_CLOSED'}

    bl_label="Pose Library Template"

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        layout.use_property_split = False
        layout.use_property_decorate = False  # No animation.

        doc_box(lines = [
            'Welcome to the Pose Library Template Creator.'
        ], parent = layout)

        box = layout.box()
        row = box.row()
        row.label(text='Overall Settings', icon = 'SETTINGS')

        settings_area = row.column()

        category = settings_area.column(align=True)
        category.prop(scene, "category_start_frame", text = "Category Start Frame")
        category.prop(scene, "category_increments", text = "Frames Between Categorys")

        props = settings_area.column(align=True)
        props.prop(scene, "pose_increments", text = "Frames Between Poses")
        props.prop(scene, "pose_include_neutral", text = "Include a .neutral pose in each category.")



    def execute(self, context):

        return {'FINISHED'}

class VIEW3D_PT_FP_libViewUI(bpy.types.Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Pose Library"
    bl_options = {'DEFAULT_CLOSED'}

    bl_label="Helpful Shortcuts"

    def draw(self, context):
        layout = self.layout
        layout.use_property_decorate = False
        scene = context.scene

        shortcut_area = layout.column(align = False)

        # 3D View
        box = shortcut_area.box()
        area = box.column()
        row = area.row()
        row.label(text='3D view', icon = 'CAMERA_STEREO')

        settings_area = row.column(align=False)
        view_box = settings_area.column()
        view = context.space_data

        # add the camera lock option
        icon = 'CAMERA_DATA'
        if view.lock_camera:
            icon = 'OUTLINER_OB_CAMERA'
        view_box.operator('view3d.view_camera', text = "Toggle Camera View", icon='OUTLINER_OB_CAMERA')
        view_box.operator('view3d.view_selected', icon="ZOOM_SELECTED").use_all_regions=False
        view_box.prop(view, "lock_camera", text="Lock Camera View")


        # Mode
        box = shortcut_area.box()
        area = box.column(align=False)
        row = area.row()
        obj = context.active_object
        # mode_string = context.mode
        object_mode = 'OBJECT' if obj is None else obj.mode
        has_pose_mode = (
            (object_mode == 'POSE') or
            (object_mode == 'WEIGHT_PAINT' and context.pose_object is not None)
        )
        act_mode_item = bpy.types.Object.bl_rna.properties["mode"].enum_items[object_mode]
        act_mode_i18n_context = bpy.types.Object.bl_rna.properties["mode"].translation_context

        row.label(text='Mode', icon = act_mode_item.icon)

        settings_area = row.column()
        view_box = settings_area.column(align=False)
        view = context.space_data


        view_box.operator_menu_enum(
            "object.mode_set", "mode",
            text=bpy.app.translations.pgettext_iface(act_mode_item.name, act_mode_i18n_context),
            icon=act_mode_item.icon,
        )

        # Mode
        box = shortcut_area.box()
        area = box.column()

        row = area.row()
        obj = context.active_object
        row.label(text='Category', icon = "BOOKMARKS")
        settings_area = row.column()
        view_box = settings_area.column(align=False)

        view_box.prop(scene, "category_activate_layers", text="Auto Layer Switch")
        view_box.prop(scene, "category_hide_ignore", text="Hide Ignore Controls")


    def execute(self, context):

        return {'FINISHED'}
# -------------------------------------------------------------------
#   CATEGORY UI
# -------------------------------------------------------------------

class VIEW3D_PT_FP_libCategoryUI(bpy.types.Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Pose Library"

    bl_label="Categories"


    def draw(self, context):

        layout = self.layout
        scene = context.scene
        view = context.space_data

        layout.use_property_split = True
        layout.use_property_decorate = False  # No animation.

        min_rows = 6
        draw_fac = 0.5

        try:
            category = scene.timeline_markers[scene.category_active_index]
        except:
            category = 0
            pass

        if not category:
            ''' Build out a category for messaging if no categorys exist'''
            col = layout.column()
            row = col.row(align=True)

            msg = ["No categories exist yet.",
                "",
                "Categories define different \"types\" of poses.",
                "For example: Body, Face, Hands, All.",
                "",
                "Please create a category by choosing the 'Add' button,",
                "or import a default template."
                "" ]

            doc_box(icon = 'INFO',
                lines = msg,
                parent = row)

            row2 = col.row()
            row2.operator('category.new_item', text='Add First Category', icon='BOOKMARKS' )
            op = row2.operator('category.do_import', icon='IMPORT', text="Import Default Template").include_cameras = True
        else:
            col = layout.column()

            row = col.row(align=True)

            split = row.split(factor=draw_fac)




            # --- LEFT ----
            left = split.box()
            left.template_list(
                "CATEGORY_UL_list",   # listtype_name
                "",                 # list_id
                scene,              # dataptr: Data from which to take the property,
                "timeline_markers", # propname: propertyname,
                scene,              # active_dataptr: data from which to take the integer property of active data
                "category_active_index",   # active_propname: Identifier of the integer property in active data
                item_dyntip_propname="camera",               # item_dyntip_propname='',
                rows=min_rows,                      # rows=5,
            )

            button_row = left.row()
            main_button = button_row.row()
            split_button = main_button.split(align=True)
            split_button.operator('category.new_item', text='Add', icon='BOOKMARKS' )
            split_button.operator('category.new_item', text='Insert', icon='RIGHTARROW' ).insert = True
            nav_buttons = button_row.row()
            split_nav = nav_buttons.split(align = True)
            split_nav.operator('category.move_item', text='', icon="TRIA_UP").direction = 'UP'
            split_nav.operator('category.move_item', text='', icon="TRIA_DOWN").direction = 'DOWN'

            right_category = split.column()

            settings_box = right_category.box()
            # Camera
            tmp = settings_box.row(align=True)
            tmp.prop(category,"camera_pointer", text="Camera", icon="CAMERA_DATA")
            tmp.operator('category.select_camera', text='', icon='RESTRICT_SELECT_OFF')
            op= tmp.operator('category.new_cam', text = "", icon = 'ADD').use_category = True

            # Display Layers
            tmp = settings_box.row(align=True)
            tmp.prop(category, "layers", text="Bone Layers", emboss=True)
            tmp.operator('category.set_active_layers', text = '', icon="PASTEDOWN")
            tmp.operator('category.pick_layers', text = '', icon="BONE_DATA")

            # Mirror controls
            settings_box.prop(category, "mirror", text = "Mirror ")

            # Ignore controls
            tmp = settings_box.row(align=True)
            tmp.prop(category, "ignore", text = "Ignore")
            tmp.operator('category.set_ignore_controls', text='', icon='PASTEDOWN')

        # --- SIDEBAR ---
        row.menu("CATEGORY_MT_context_menu", icon='DOWNARROW_HLT', text="")

    def execute(self, context):

        return {'FINISHED'}

class VIEW3D_PT_FP_libPoseUI(bpy.types.Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Pose Library"

    bl_label="Poses"

    @classmethod
    def poll(cls, context):
        # only work if timeline markers exist
        return (len(context.scene.timeline_markers) > 0)

    def draw(self, context):

        layout = self.layout
        scene = context.scene
        view = context.space_data

        layout.use_property_split = True
        layout.use_property_decorate = False  # No animation.

        min_rows = 6

        category = scene.timeline_markers[scene.category_active_index]

        number_poses = len(category.poses)
        # if there is less than one pose, display this message.
        #
        if number_poses < 2:
            doc_box(lines = ['Each category can contain multiple poses.',
                "For example, a \"Face\" category may contain \"happy\", \"mad\", \"confused\".",
                "A library pose will be automatically generated for each frame."],
            parent = layout)

        pose_row = layout.row(align = True)
        right = pose_row.box()

        row2 = right.row()
        row2.alignment='EXPAND'
        row2.use_property_split = False

        row2.template_list(
                listtype_name = "POSE_UL_list",
                list_id = "",
                dataptr = category,
                propname = "poses",
                active_dataptr = category,
                active_propname = "pose_active_index",
                rows=min_rows,

                )

        button_row2 = right.row()
        main_button2 = button_row2.row()
        split_button2 = main_button2.split(align=True)
        split_button2.operator('category.new_pose', text='Add', icon='ARMATURE_DATA' ).insert = False
        split_button2.operator('category.new_pose', text='Insert', icon='RIGHTARROW' ).insert = True
        nav_buttons2 = button_row2.row()
        split_nav2 = nav_buttons2.split(align = True)
        split_nav2.operator('category.move_pose', text='', icon="TRIA_UP").direction = 'UP'
        split_nav2.operator('category.move_pose', text='', icon="TRIA_DOWN").direction = 'DOWN'

        # --- SIDEBAR ---
        pose_row.menu("POSE_MT_context_menu", icon='DOWNARROW_HLT', text="")

        # --- END POSE CATEGORY
        layout.separator()
        button_area = layout.box()
        button_area.scale_y = 2

        button_area.operator('pose.create_pose_library', icon="ASSET_MANAGER")

    def execute(self, context):

        return {'FINISHED'}

# -------------------------------------------------------------------
#   Helpful Functions
# -------------------------------------------------------------------
def _label_multiline(context, text, parent):
    chars = int(context.region.width / 7)   # 7 pix on 1 character
    wrapper = textwrap.TextWrapper(width=chars)
    text_lines = wrapper.wrap(text=text)
    for text_line in text_lines:
        parent.label(text=text_line)

def date():
    """Returns date and time in a nice format"""
    now = datetime.datetime.utcnow()

    return (now.strftime("%b %d, %Y - %I:%M:%S %p UTC"))

def doc_box(icon = 'INFO', lines = [], parent = None):
    """Creates a box with text and an icon"""
    if not parent:
        print('You must specify a parent.')
        return False
    box = parent.box()
    row = box.row()

    row.label(text="", icon=icon)

    col = row.column(align=True)
    for line in lines:
        col.label(text = line)

def duplicate(obj, data=True, actions=True, collection=None):
    """Duplicate an object and it's data"""
    obj_copy = obj.copy()
    if data:
        obj_copy.data = obj_copy.data.copy()
    if actions and obj_copy.animation_data:
        obj_copy.animation_data.action = obj_copy.animation_data.action.copy()

    collection.objects.link(obj_copy)
    return obj_copy

def fix_blank_controls(self, context, origin):
    """Make sure the controls aren't left blank"""
    result = getattr(self, origin)
    if result.strip() == "":
        setattr(self, origin, "[]")

def get_arm(context):
    mode = context.mode
    if mode == 'POSE':
        return context.pose_object.data
    else:
        # no armature is selected, so we'll just grab the first one
        # visible in the scene
        objs = bpy.data.objects
        for obj in objs:
            if obj.type == 'ARMATURE':
                if obj.visible_get():
                    return obj.data
    return False

def get_current_layers(arm):
    layersOn = []
    for i in range(0,32):
        if arm.layers[i]:
            layersOn.append(i)
    return layersOn

def get_marker(context):
    return context.scene.timeline_markers[context.scene.category_active_index]

def get_pose(marker):
    try:
        return marker.poses[marker.pose_active_index]
    except:
        return False

def get_user():
    """Returns the user"""
    return (getpass.getuser())

def go_to_frame(self, context, origin):
    result = getattr(self, origin)
    scene = context.scene
    marker_list = scene.timeline_markers
    selected_index = scene.category_active_index
    activate_layers = scene.category_activate_layers
    hide_ignore = scene.category_hide_ignore
    pose_increment = scene.pose_increments
    marker = marker_list[selected_index]
    pose_active_index = marker.pose_active_index

    if self.name == 'Scene':
        scene.frame_current = marker.frame
    else:
        # set the frame
        scene.frame_current = marker.frame + (pose_increment * pose_active_index)

        # set the name
        marker.pose_active_name = marker.poses[pose_active_index].name
    if activate_layers:
        toggle_display_layers(context)



def is_active_cloudrig(context):
    """ If the active object is a cloudrig, return it. """
    rig = context.pose_object or context.object
    if rig and is_cloudrig(rig):
        return rig

def is_camera(scene, obj):
    if obj.type == 'CAMERA':
        return True
    else:
        return False


def is_cloudrig(obj):
    """Return whether obj is marked as being compatible with cloudrig file."""
    return obj.type=='ARMATURE' and (
            ('rig_id' in obj.data and obj.data['rig_id'] == 'cloudrig') or \
            ('cloudrig' in obj.data)
        )
def mirror_callback(self, context):
    return (
        ('NONE', 'None', "No Mirror"),
        ('L', 'L -> R', "Copy the Left controls to the Right."),
        ('R', 'R -> L', "Copy the Right controls to the Left."),
    )
def save_tempfile():
    """Sometimes you need to save and reopen the file to clear out old datablocks."""
    tempdir = tempfile.gettempdir()
    mytempfile = os.path.join(tempdir, "_tempfile.blend")

    bpy.ops.wm.save_as_mainfile(filepath=mytempfile, copy=True)

    return mytempfile

def toggle_display_layers(context):
    marker = get_marker(context)
    layers = marker.layers
    arm = get_arm(context)

    for i in range(0,32):
        if i in ast.literal_eval(layers):
            arm.layers[i] = True
        else:
            arm.layers[i] = False

    # now work with ignore layers
    #
    # first reveal all hidden controls
    bpy.ops.pose.reveal()

    # now hide all controls we should ignore
    if context.scene.category_hide_ignore:
        ignore_bones = ast.literal_eval(marker.ignore)
        for control in ignore_bones:
            arm.bones[control].hide = True


def update_marker(self, context):
    # get the value of the object
    self.camera = self.camera_pointer


def update_marker_frame(self, context):
    """Update the category start frame"""
    scene = context.scene
    category_start_frame = scene.category_start_frame
    category_increments = scene.category_increments
    markers = scene.timeline_markers
    for i, marker in enumerate(markers):
        marker.frame = i*category_increments + category_start_frame


# Create all the properties

def create_properties():
    """Create properties to help with category and pose creation"""

    # Scene.category properties
    #
    bpy.types.Scene.category_start_frame = IntProperty(  default = 100,
                                                        description = "Frame to start your categorys.",
                                                        update=update_marker_frame)
    bpy.types.Scene.category_increments  = IntProperty(  default = 100,
                                                        description = "Number of frames between each category. Recommended 50 or 100 so there is room for poses.",
                                                        update=update_marker_frame)
    bpy.types.Scene.category_active_index = IntProperty( update=lambda s, c: go_to_frame(s, c, 'category_active_index'))

    bpy.types.Scene.category_activate_layers = BoolProperty(default = True,
                                                        name="Switch Layers",
                                                        description="Switch display layers when changing selection")
    bpy.types.Scene.category_hide_ignore = BoolProperty(default = True,
                                                        name="Hide Ignore Controls",
                                                        description="Hides ignored controls when changing selection",
                                                        update = lambda s, c: go_to_frame(s, c, 'category_active_index'))

    bpy.types.Scene.pose_increments = IntProperty(      default = 1,
                                                        description = "Number of frames between each pose.")
    bpy.types.Scene.pose_include_neutral = BoolProperty(default = True,
                                                        description = "Include a .neutral pose at the start of each category.")

    # TimelineMarker properties
    #
    bpy.types.TimelineMarker.pose_active_index = IntProperty(update=lambda s, c: go_to_frame(s, c, 'pose_active_index'))

    bpy.types.TimelineMarker.pose_active_name = StringProperty()
    bpy.types.TimelineMarker.camera_pointer = PointerProperty(type=bpy.types.Object, name="Camera", poll=is_camera, update=update_marker)
    bpy.types.TimelineMarker.layers = StringProperty(name="Visible Layers",
        default="[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27]",
        description = "List of layers to include",
        update = lambda s, c: fix_blank_controls(s, c, 'layers')
    )

    bpy.types.TimelineMarker.mirror = EnumProperty(
            items=mirror_callback,
            name="Mirror",
            description="Mirror controls when creating library poses.",
            default=None,
            options=set(),
            update=None,
            get=None,
            set=None)

    bpy.types.TimelineMarker.ignore = StringProperty(
        name = "Ignore Controls",
        default="[]",
        description = "Comma-separated set of controls to ignore when making library poses. Ex: Iris*, Pupil*",
        update = lambda s, c: fix_blank_controls(s, c, 'ignore')
        )

    bpy.types.TimelineMarker.poses = CollectionProperty(type=CUSTOM_PoseProps)


# -------------------------------------------------------------------
#   Registration
# -------------------------------------------------------------------

classes = (
            CUSTOM_PoseProps,
            CATEGORY_OT_Clear,
            CATEGORY_OT_Export,
            CATEGORY_OT_Import,
            CATEGORY_OT_Import_Prompt,
            CATEGORY_OT_Remove,
            CATEGORY_OT_NewItem,
            CATEGORY_OT_NewCam,
            CATEGORY_OT_MoveItem,
            CATEGORY_OT_SelectCamera,
            CATEGORY_MT_context_menu,
            POSE_UL_list,
            POSE_OT_NewItem,
            POSE_OT_MoveItem,
            POSE_OT_Remove,
            POSE_OT_Skip,
            POSE_MT_context_menu,
            VIEW3D_PT_FP_libUI,
            VIEW3D_PT_FP_libViewUI,
            VIEW3D_PT_FP_libCategoryUI,
            VIEW3D_PT_FP_libPoseUI,
            CATEGORY_UL_list,
            CATEGORY_OT_FixMarkers,
            CATEGORY_OT_SetActiveLayers,
            CATEGORY_OT_SetIgnoreControls,
            CATEGORY_OT_PickLayers,
           )

# register all the classes
def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    create_properties()

def unregister():

    unreg = bpy.utils.unregister_class
    for cls in classes:
        bpy.utils.unregister_class(cls)

    del bpy.types.Scene.category_start_frame
    del bpy.types.Scene.category_increments
    del bpy.types.Scene.category_active_index
    del bpy.types.Scene.category_activate_layers
    del bpy.types.Scene.category_hide_ignore
    del bpy.types.Scene.pose_increments
    del bpy.types.Scene.pose_include_neutral


if __name__ == '__main__':
    register()
    bpy.context.scene.fix_markers = True
