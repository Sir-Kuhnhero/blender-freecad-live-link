import sys
import os
import json

import socket
from PySide6 import QtWidgets
import FreeCAD as App
import FreeCADGui as Gui
from PySide6.QtGui import QAction
from tempfile import TemporaryDirectory
import re
from subprocess import Popen
import shlex
import Mesh
import MeshPart
from dataclasses import dataclass

@dataclass
class objectClass:
    name: str = None
    label: str = None
    position:  App.Vector = None
    rotation: App.Rotation = None
    mesh: Mesh = None
    mesh_path: str = None

@dataclass
class objectTreeClass:
    object: objectClass
    children: list['objectTreeClass']

    def to_dict(self):
        return {
            "object": {
                "name": self.object.name,
                "label": self.object.label,
                "position": [self.object.position.x, self.object.position.y, self.object.position.z] if self.object.position else [0, 0, 0],
                "rotation": [self.object.rotation.Q[0], self.object.rotation.Q[1], self.object.rotation.Q[2], self.object.rotation.Q[3]] if self.object.rotation else [1, 0, 0, 0],
                "mesh": self.object.mesh.Name if self.object.mesh else None,
                "mesh_path": self.object.mesh_path
            },
            "children": [child.to_dict() for child in self.children]
        }


def print_object_tree(tree: objectTreeClass, indent=0):
    App.Console.PrintMessage(' ' * indent + f"Object Name: {tree.object.name}, Label: {tree.object.label}, Position: {tree.object.position}, Rotation: {tree.object.rotation}, #children: {len(tree.children)}\n")
    for child in tree.children:
        print_object_tree(child, indent + 4)

def sync_or_export_to_blender(method):
    """Export objects to Blender as new bodies (using only label as name)"""
    try:
        doc = App.activeDocument()
        if not doc:
            raise RuntimeError("No active document to export")

        selection = Gui.Selection.getSelectionEx()
        objects_to_export = [x.Object for x in selection] or [doc.ActiveObject]

        if not objects_to_export:
            raise RuntimeError("No objects selected to export")

        objectTrees = create_objectTree(doc, objects_to_export)

        # print_object_tree(objectTrees[0])

        if objectTrees:
            temp_dir = TemporaryDirectory()
            os.makedirs(temp_dir.name, exist_ok=True)
            objectTrees = export_meshes(doc, temp_dir, objectTrees)

            # create message as JSON
            message_data = {
                "method": method,
                "path": "Soon to be deprecated",
                "objects": [tree.to_dict() for tree in objectTrees]
            }
            message = json.dumps(message_data)
           
            send_message_to_blender(message)

            temp_dir.cleanup()
        else:
            raise RuntimeError("No objects to export")

    finally:
        App.closeDocument('meshes_to_export')
        for x in selection:
            Gui.Selection.addSelection(doc.Name, x.ObjectName)

def create_objectTree(doc, objects_to_export) -> list[objectTreeClass]:
    # Create temporary document to store meshes
    tmp_doc = App.newDocument('meshes_to_export', temp=True)

    objectTrees = []

    angular_deflection = 0.07  # Default angular deflection

    for o in objects_to_export:
        obj = objectClass()
        children = []
        
        # universal properties
        obj.name = o.Name
        obj.label = o.Label
        
        if o.TypeId == 'Mesh::Feature':
            obj.position = o.Placement.Base
            obj.rotation = o.Placement.Rotation
            obj.mesh = o
        elif o.TypeId == 'PartDesign::Body':
            # Create mesh at origin by using shape without placement
            shape_copy = o.Shape.copy()
            shape_copy.Placement = App.Placement()
            
            mesh = tmp_doc.addObject('Mesh::Feature', f'{doc.Name}_{o.Name}')
            mesh.Mesh = MeshPart.meshFromShape(
                shape_copy, LinearDeflection=0.1, AngularDeflection=angular_deflection, Relative=False
            )

            obj.position = o.Placement.Base
            obj.rotation = o.Placement.Rotation
            obj.mesh = mesh
        elif o.TypeId == 'App::Link':
            # Create mesh at origin by using shape without placement
            shape_copy = o.Shape.copy()
            shape_copy.Placement = App.Placement()
            
            mesh = tmp_doc.addObject('Mesh::Feature', f'{doc.Name}_{o.Name}')
            mesh.Mesh = MeshPart.meshFromShape(
                shape_copy, LinearDeflection=0.1, AngularDeflection=angular_deflection, Relative=False
            )

            obj.position = o.Placement.Base
            obj.rotation = o.Placement.Rotation
            obj.mesh = mesh
        elif o.TypeId == 'Assembly::AssemblyObject':
            obj.rotation = o.Placement.Rotation
            obj.position = o.Placement.Base
            children = create_objectTree(doc, o.Group)
        elif o.TypeId == 'Assembly::AssemblyLink':
            obj.rotation = o.Placement.Rotation
            obj.position = o.Placement.Base
            children = create_objectTree(doc, [o.LinkedObject])
        else:
            # Skip unsupported object types (like Joint Groups)
            # App.Console.PrintMessage(f"Skipping unsupported object type: {o.TypeId} ({o.Name})\n")
            continue

        objectTrees.append(objectTreeClass(object=obj, children=children))

    return objectTrees

def export_meshes(doc, temp_dir, objectTrees):
    new_trees: list[objectTreeClass] = []

    for tree in objectTrees:
        if tree.object.mesh:
            object_path = os.path.join(temp_dir.name, f"{tree.object.name}.obj")
            Mesh.export([tree.object.mesh], object_path)
            
            tree.object.mesh_path = object_path
            new_trees.append(tree)
        if tree.children:
            tree.children = export_meshes(doc, temp_dir, tree.children)
            new_trees.append(tree)
    
    return new_trees

def send_message_to_blender(message):
    """Send a message to Blender via socket and return the response"""
    server_address = ('localhost', 25000)
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket.connect(server_address)
    client_socket.sendall(message.encode())

    status_message = client_socket.recv(1024).decode()
    client_socket.close()
    return status_message

def create_menu():
    menu = QtWidgets.QMenu("Blender")

    actionExport = QAction("Export to Blender", menu)
    actionExport.triggered.connect(lambda: sync_or_export_to_blender("export"))
    menu.addAction(actionExport)

    actionSync = QAction("Sync to Blender", menu)
    actionSync.triggered.connect(lambda: sync_or_export_to_blender("sync"))
    menu.addAction(actionSync)

    main_menu = Gui.getMainWindow().menuBar()
    main_menu.addMenu(menu)