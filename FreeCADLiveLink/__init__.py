import bpy
from bpy.app.handlers import persistent
import socket
import threading
import time
import json
from dataclasses import dataclass

@dataclass
class importedObject:
    name: str
    label: str
    import_object = None

class importCall:
    path = None
    method = None
    objects: list[importedObject]
    status = None


bl_info = {
    "name": "FreeCAD Live Link",
    "description": "Live link for FreeCAD",
    "author": "Salai Vedha Viradhan",
    "version": (0, 1, 0),
    "blender": (2, 80, 0),
    "category": "Import-Export"
}


import_call = importCall()

def find_object_by_name(name):
    """Find an existing object in Blender by its name in parentheses"""
    for obj in bpy.data.objects:
        # Check if object name has the format name(name)
        if '(' in obj.name and ')' in obj.name:
            # Extract the name from parentheses
            start = obj.name.find('(')
            end = obj.name.find(')')
            existing_name = obj.name[start+1:end]
            if existing_name == name:
                return obj
    return None

def import_obj():
    try:
        global import_call

        # Import the OBJ file
        bpy.ops.wm.obj_import(filepath=import_call.path, forward_axis='Y', up_axis='Z')

        # Get the newly imported objects (they are selected after import)
        imported_objects = [obj for obj in bpy.data.objects if obj.select_get() == True]

        # Apply scale to all imported objects
        for obj in imported_objects:
            obj.scale = (0.01, 0.01, 0.01)

        for i in range(len(imported_objects)):
            import_call.objects[i].import_object = imported_objects[i]
        
        
        bpy.ops.object.transform_apply(scale=True)
        
        if import_call.method:
            # SYNC MODE: Use name(label) format and update existing objects
            if import_call.objects:
                for object in import_call.objects:
                    new_name = f"{object.label}({object.name})"
                    
                    # Check if an object with this label already exists
                    existing_obj = find_object_by_name(object.name)
                    
                    if existing_obj:
                        # Sync: Replace the existing object's mesh data
                        old_mesh = existing_obj.data
                        new_mesh = object.import_object.data
                        
                        # Store existing materials
                        old_materials = [slot.material for slot in existing_obj.material_slots]
                        
                        # Replace mesh data
                        existing_obj.data = new_mesh
                        existing_obj.name = new_name
                        
                        # Restore materials to the updated mesh
                        if old_materials:
                            for i, mat in enumerate(old_materials):
                                if i < len(existing_obj.material_slots):
                                    existing_obj.material_slots[i].material = mat
                                else:
                                    # Add new material slot if needed
                                    existing_obj.data.materials.append(mat)
                        
                        # Remove the temporary imported object
                        bpy.data.objects.remove(object.import_object, do_unlink=True)
                        
                        # Clean up the old mesh
                        if old_mesh.users == 0:
                            bpy.data.meshes.remove(old_mesh)
                    else:
                        # New object in sync mode: use name(label) format
                        object.import_object.name = new_name
        else:
            # EXPORT MODE: Use only label as name (makes them not sync targets)
            if import_call.objects:
                for object in import_call.objects:
                    object.import_object.name = object.label
                        
    except Exception as e:
        print(f"Import error: {e}")

def obj_data_monitor():
    global import_call

    if import_call.path != None:
        try:
            import_obj()
            import_call.path = None
            import_call.objects = None
            import_call.status = 'SUCCESS'    
        except Exception as e:
            print(str(e))
            import_call.status = 'FAILURE'    
    return 1.0

def receive_data():

    global import_call

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_address = ('localhost', 25000)
    
    try:
        server_socket.bind(server_address)
    except OSError as e:
        print(f"Failed to bind socket: {e}. Port may already be in use.")
        return

    while True:
        server_socket.listen(5)
        print("Listening for OBJs...")

        connection, client_address = server_socket.accept()
        print("Connected with FreeCAD instance:", client_address)

        data = connection.recv(1024).decode()
        print(f"Received data: {data}")

        # Parse the JSON data
        try:
            message_data = json.loads(data)
            method = message_data.get("method")
            import_call.path = message_data.get("path")
            objects_data = message_data.get("objects", [])

            if method == "sync":
                import_call.method = True
                import_call.objects = []
                for obj in objects_data:
                    obj_data = obj.get("object", obj)  # Handle nested structure
                    import_call.objects.append(importedObject(obj_data["name"], obj_data["label"]))
            elif method == "export":
                import_call.method = False
                import_call.objects = []
                for obj in objects_data:
                    obj_data = obj.get("object", obj)  # Handle nested structure
                    import_call.objects.append(importedObject(obj_data["name"], obj_data["label"]))
            else:
                import_call.method = False
                import_call.objects = []
        except json.JSONDecodeError as e:
            print(f"JSON decode error: {e}")
            raise ValueError("Invalid JSON format received")

        import_call.status = 'IMPORTING'

        while import_call.status != None:
            if import_call.status == 'SUCCESS':
                connection.sendall("Successfully imported OBJ!".encode())
                break
            elif import_call.status == 'FAILURE':
                connection.sendall("Failed imported OBJ.".encode())
                break
            else:
                time.sleep(3)
                continue

        import_call.status = None
        connection.close()

def cleanup_threads():
    threads_cleaned = False
    while not threads_cleaned:
        time.sleep(2)
        for thread in threading.enumerate():
            if thread.getName() == "MainThread" and thread.is_alive() == False:
                try:
                    cleanup_socket = socket.socket()
                    cleanup_socket.connect(('localhost', 25000))
                    cleanup_socket.send(b"Quit Blender!")
                    cleanup_socket.close()
                except (ConnectionRefusedError, OSError) as e:
                    print(f"Cleanup connection failed: {e}")
                threads_cleaned = True
                break

@persistent
def start_live_link(scene):
    threading.Thread(target=receive_data, args=()).start()
    threading.Thread(target=cleanup_threads, args=()).start()
    bpy.app.timers.register(obj_data_monitor)

def register():
    bpy.app.handlers.load_post.append(start_live_link)

def unregister():
    bpy.app.handlers.load_post.remove(start_live_link)