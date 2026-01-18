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


def sync_or_export_to_blender(method):
    """Export objects to Blender as new bodies (using only label as name)"""
    try:
        doc = App.activeDocument()
        if not doc:
            raise RuntimeError("No active document to export")

        selection = Gui.Selection.getSelectionEx()
        objects_to_export = get_all_objects_to_export(doc, selection)


        if not objects_to_export:
            raise RuntimeError("No objects selected to export")

        meshes, mesh_data = create_meshes(doc, objects_to_export)

        if meshes:
            temp_dir = TemporaryDirectory()
            os.makedirs(temp_dir.name, exist_ok=True)
            object_path = os.path.join(temp_dir.name, f"{doc.Name}.obj")
            Mesh.export(meshes, object_path)

            # create message as JSON
            message_data = {
                "method": method,
                "path": object_path,
                "objects": [{"name": name, "label": label} for name, label in mesh_data]
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


def get_all_objects_to_export(doc, selection):
    """Get all objects to export from the current selection or document"""
    if not selection:
        return None

    objects_to_export = [x.Object for x in selection] or [doc.ActiveObject]
    

    return objects_to_export

def create_meshes(doc, objects_to_export):
    # Create temporary document to store meshes
    tmp_doc = App.newDocument('meshes_to_export', temp=True)
    meshes = []
    mesh_data = []
    angular_deflection = 0.07  # Default angular deflection

    for o in objects_to_export:
        if o.TypeId == 'Mesh::Feature':
            meshes.append(o)
            mesh_data.append((o.Name, o.Label))
        else:
            mesh = tmp_doc.addObject('Mesh::Feature', f'{doc.Name}_{o.Name}')
            mesh.Mesh = MeshPart.meshFromShape(
                o.Shape, LinearDeflection=0.1, AngularDeflection=angular_deflection, Relative=False
            )
            meshes.append(mesh)
            mesh_data.append((o.Name, o.Label))

    return meshes, mesh_data

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