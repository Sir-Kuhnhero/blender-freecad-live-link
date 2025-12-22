import sys
import os

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


def export_obj():
    try:
        App.Console.PrintMessage("Starting export to Blender...\n")

        doc = App.activeDocument()
        if not doc:
            raise RuntimeError("No active document to export")

        selection = Gui.Selection.getSelectionEx()
        objects_to_export = [x.Object for x in selection] or [doc.ActiveObject]

        # Create temporary document to store meshes
        tmp_doc = App.newDocument('meshes_to_export', temp=True)
        meshes = []
        mesh_names = []
        angular_deflection = 0.07  # Default angular deflection

        for o in objects_to_export:
            if o.TypeId == 'Mesh::Feature':
                meshes.append(o)
            else:
                mesh = tmp_doc.addObject('Mesh::Feature', f'{doc.Label}_{o.Label}')
                mesh.Mesh = MeshPart.meshFromShape(
                    o.Shape, LinearDeflection=0.1, AngularDeflection=angular_deflection, Relative=False
                )
                meshes.append(mesh)
                mesh_names.append(o.Label)

        if meshes:
            # Use a custom directory to retain the file
            custom_dir = "/tmp/FreeCAD-LiveLink"
            os.makedirs(custom_dir, exist_ok=True)
            object_path = os.path.join(custom_dir, f"{doc.Name}.obj")
            Mesh.export(meshes, object_path)

            # Send the exported mesh path to Blender
            server_address = ('localhost', 25000)
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.connect(server_address)
            client_socket.sendall(object_path.encode())

            App.Console.PrintMessage("Waiting for Blender response...\n")
            status_message = client_socket.recv(1024).decode()
            App.Console.PrintMessage(f"Blender: {status_message}\n")

            App.Console.PrintMessage(f"Temporary file retained at: {object_path}\n")
        else:
            raise RuntimeError("No objects to export")

    finally:
        App.closeDocument('meshes_to_export')
        for x in selection:
            Gui.Selection.addSelection(doc.Name, x.ObjectName)

    App.Console.PrintMessage("Export completed successfully.\n")

def testFunction():
    App.Console.PrintMessage("Test function called from Blender Live Link.\n")

def create_menu():
    menu = QtWidgets.QMenu("Blender")

    action = QAction("Export to Blender", menu)
    action.triggered.connect(export_obj)

    menu.addAction(action)

    main_menu = Gui.getMainWindow().menuBar()
    main_menu.addMenu(menu)