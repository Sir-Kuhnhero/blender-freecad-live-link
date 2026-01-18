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
    name: str
    label: str
    position:  App.Vector
    rotation: App.Rotation
    mesh: Mesh

@dataclass
class objectTreeClass:
    object: objectClass
    children: list['objectTreeClass']

    def to_dict(self):
        return {
            "object": {
                "name": self.object.name,
                "label": self.object.label,
                "position": [self.object.position.x, self.object.position.y, self.object.position.z],
                "rotation": [self.object.rotation.Q[0], self.object.rotation.Q[1], self.object.rotation.Q[2], self.object.rotation.Q[3]],
            },
            "children": [child.to_dict() for child in self.children]
        }


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

        if objectTrees:
            temp_dir = TemporaryDirectory()
            os.makedirs(temp_dir.name, exist_ok=True)
            object_path = export_meshes(doc, temp_dir, objectTrees)

            # create message as JSON
            message_data = {
                "method": method,
                "path": object_path,
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
        # TODO recursifly add children to the object tree
        if o.TypeId == 'Mesh::Feature':
            obj = objectClass(name=o.Name, label=o.Label, position=o.Placement.Base, rotation=o.Placement.Rotation, mesh=o)
        else:
            mesh = tmp_doc.addObject('Mesh::Feature', f'{doc.Name}_{o.Name}')
            mesh.Mesh = MeshPart.meshFromShape(
                o.Shape, LinearDeflection=0.1, AngularDeflection=angular_deflection, Relative=False
            )
            obj = objectClass(name=o.Name, label=o.Label, position=o.Placement.Base, rotation=o.Placement.Rotation, mesh=mesh)
        
        objectTrees.append(objectTreeClass(object=obj, children=[]))

    return objectTrees

def export_meshes(doc, temp_dir, objectTrees):
    mesh_objects = []
    for tree in objectTrees:
        if tree.object.mesh:
            mesh_objects.append(tree.object.mesh)
        if tree.children:
            export_meshes(doc, temp_dir, tree.children)

    object_path = os.path.join(temp_dir.name, f"{doc.Name}.obj")
    Mesh.export(mesh_objects, object_path)
    return object_path

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