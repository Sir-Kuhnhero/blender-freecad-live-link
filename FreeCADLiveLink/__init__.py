import bpy
from bpy.app.handlers import persistent
import socket
import threading
import time
import json
from dataclasses import dataclass

@dataclass
class objectClass:
    name: str = None
    label: str = None
    position: list = None
    rotation: list = None
    mesh: str = None

@dataclass
class objectTreeClass:
    object: objectClass
    children: list['objectTreeClass']

@dataclass
class importedObject:
    name: str = None
    label: str = None
    import_object = None

class importCall:
    path = None
    method = None
    trees: list[objectTreeClass] = None 
    objects: list[importedObject] ## Soon to be deprictated
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

def find_object_by_name(name, parent=None):
    """Find an existing object in Blender by its name in parentheses, recursively searching the hierarchy"""
    
    # Determine which objects to search at this level
    if parent is not None:
        # Search within parent's direct children
        objects_to_search = [child for child in bpy.data.objects if child.parent == parent]
    else:
        # Search only root-level objects (no parent)
        objects_to_search = [obj for obj in bpy.data.objects if obj.parent is None]
    
    # Check each object at this level
    for obj in objects_to_search:
        # Check if object name has the format name(name)
        if '(' in obj.name and ')' in obj.name:
            # Extract the name from parentheses
            start = obj.name.find('(')
            end = obj.name.find(')')
            existing_name = obj.name[start+1:end]

            if existing_name == name:
                return obj
        
        # Recursively search this object's children
        result = find_object_by_name(name, parent=obj)
        if result:
            return result
    
    return None

def import_objectTree(tree: objectTreeClass, parent=None):
    try:
        global import_call

        obj = tree.object
        bl_obj = None
        
        if obj.mesh == None:
            # No mesh to import, create an empty object with sphere display
            bl_obj = bpy.data.objects.new(obj.label or "Empty", None)
            bl_obj.empty_display_type = 'SPHERE'
            bpy.context.collection.objects.link(bl_obj)
        else:
            # import mesh from tree.mesh using Blender 4.0+ operator
            bpy.ops.wm.obj_import(filepath=obj.mesh, forward_axis='Y', up_axis='Z')
            bl_obj = bpy.context.selected_objects[0]
        
        if obj.rotation:
            bl_obj.rotation_mode = 'QUATERNION'
            # Freecad uses (x, y, z, w) and Blender uses (w, x, y, z)
            bl_obj.rotation_quaternion = (obj.rotation[3], obj.rotation[0], obj.rotation[1], obj.rotation[2])
        if obj.position:
            bl_obj.location = (obj.position[0], obj.position[1], obj.position[2])

        if parent:
            bl_obj.parent = parent       
        else:
            # Apply scale to parent objects
            bl_obj.scale = (0.01, 0.01, 0.01)
            #bpy.ops.object.transform_apply(scale=True)

        # Determine which object to use for parenting children
        final_obj = bl_obj
        
        if import_call.method == "sync":
            new_name = f"{obj.label}({obj.name})"
            existing_obj = find_object_by_name(obj.name, parent=parent)
            if existing_obj:
                # Sync: Replace the existing object's mesh data
                old_mesh = existing_obj.data
                new_mesh = bl_obj.data

                new_position = bl_obj.location
                new_rotation = bl_obj.rotation_quaternion
                existing_obj.location = new_position
                existing_obj.rotation_mode = 'QUATERNION'
                existing_obj.rotation_quaternion = new_rotation
                
                # Only replace mesh data if both objects have meshes
                if old_mesh is not None and new_mesh is not None:
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
                    
                    # Clean up the old mesh
                    if old_mesh.users == 0:
                        bpy.data.meshes.remove(old_mesh)
                elif old_mesh is None and new_mesh is None:
                    # Both are empties, just update the name
                    existing_obj.name = new_name
                
                # Remove the temporary imported object
                bpy.data.objects.remove(bl_obj, do_unlink=True)
                
                # Use the existing object for parenting children
                final_obj = existing_obj
            else:
                # New object in sync mode: use name(label) format
                bl_obj.name = new_name
                final_obj = bl_obj
        elif import_call.method == "export":
            bl_obj.name = obj.label or "ExportedObject"
            final_obj = bl_obj

        for child in tree.children:
            import_objectTree(child, parent=final_obj)

    except Exception as e:
        print(f"Import error: {e}") 

def obj_data_monitor():
    global import_call

    if import_call.path != None:
        try:
            for tree in import_call.trees:
                import_objectTree(tree)
            import_call.path = None
            import_call.trees = None
            import_call.status = 'SUCCESS'    
        except Exception as e:
            print(str(e))
            import_call.status = 'FAILURE'    
    return 1.0

def create_objectTree_from_dict(data) -> objectTreeClass:
    obj_data = data.get("object", {})
    obj = objectClass(
        name=obj_data.get("name"),
        label=obj_data.get("label"),
        position=obj_data.get("position"),
        rotation=obj_data.get("rotation"),
        mesh=obj_data.get("mesh_path"),
    )

    children_data = data.get("children", [])
    children = [create_objectTree_from_dict(child) for child in children_data]

    return objectTreeClass(object=obj, children=children)

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

        # Receive data in chunks until complete
        data_chunks = []
        while True:
            chunk = connection.recv(4096)
            if not chunk:
                break
            data_chunks.append(chunk)
            # Check if we received a complete JSON message
            try:
                json.loads(b''.join(data_chunks).decode())
                break  # Valid JSON received, stop reading
            except json.JSONDecodeError:
                continue  # Incomplete JSON, keep reading
        
        data = b''.join(data_chunks).decode()
        print(f"Received data: {data}")

        # Parse the JSON data
        try:
            message_data = json.loads(data)
            method = message_data.get("method")
            import_call.path = message_data.get("path")
            objects_data = message_data.get("objects", [])

            if method == "sync" or method == "export":
                import_call.method = method
                import_call.trees = []
                for obj_tree in objects_data:
                    import_call.trees.append(create_objectTree_from_dict(obj_tree))
            else:
                import_call.method = None
                import_call.trees = []
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