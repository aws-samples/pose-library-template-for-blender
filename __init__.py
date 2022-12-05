# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT

"""
Pose Library Template for Blender

Creates a template for building and re-building a Pose Library for the Asset Browser.
"""

bl_info = {
    'name': 'Pose Library Template for Blender',
    'author': 'sjason@amazon.com',
    'description': 'Blender Pose Library Template Generator',
    'blender': (3, 2, 0),
    'version': (1, 0, 0),
    'location': 'View3D',
    'wiki_url': '',
    'category': '3D View'
}

from importlib import reload

from . import (
    create_pose_library,
    mirror_pose,
    library_template_UI,
    message_box,
)

classes = [
    library_template_UI,
    create_pose_library,
    mirror_pose,
    message_box,
]

for cls in classes:
    reload(cls)

def register():

    for cls in classes:
        cls.register()

def unregister():

    classes.reverse()
    for cls in classes:
        cls.unregister()

