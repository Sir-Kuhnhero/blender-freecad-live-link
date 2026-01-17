import bpy
from bpy.app.handlers import persistent
import socket
import threading
import time

bl_info = {
    "name": "FreeCAD Live Link",
    "description": "Live link for FreeCAD",
    "author": "Salai Vedha Viradhan",
    "version": (0, 1, 0),
    "blender": (2, 80, 0),
    "category": "Import-Export"
}

obj_path = None
object_data = None
import_status = None
is_sync_mode = False

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
        global obj_path
        global is_sync_mode
        
        # Import the OBJ file
        bpy.ops.wm.obj_import(filepath=obj_path, forward_axis='Y', up_axis='Z')

        # Get the newly imported objects (they are selected after import)
        imported_objects = [obj for obj in bpy.data.objects if obj.select_get() == True]
        
        # Apply scale to all imported objects
        for obj in imported_objects:
            obj.scale = (0.01, 0.01, 0.01)
        
        bpy.ops.object.transform_apply(scale=True)
        
        if is_sync_mode:
            # SYNC MODE: Use name(label) format and update existing objects
            if object_data:
                for i, obj_info in enumerate(object_data):
                    if i < len(imported_objects):
                        name, label = obj_info
                        new_name = f"{label}({name})"
                        
                        # Check if an object with this label already exists
                        existing_obj = find_object_by_name(name)
                        
                        if existing_obj:
                            # Sync: Replace the existing object's mesh data
                            old_mesh = existing_obj.data
                            existing_obj.data = imported_objects[i].data
                            existing_obj.name = new_name
                            
                            # Remove the temporary imported object
                            bpy.data.objects.remove(imported_objects[i], do_unlink=True)
                            
                            # Clean up the old mesh
                            if old_mesh.users == 0:
                                bpy.data.meshes.remove(old_mesh)
                        else:
                            # New object in sync mode: use name(label) format
                            imported_objects[i].name = new_name
        else:
            # EXPORT MODE: Use only label as name (makes them not sync targets)
            if object_data:
                for i, label in enumerate(object_data):
                    if i < len(imported_objects):
                        imported_objects[i].name = label
                        
    except Exception as e:
        print(f"Import error: {e}")

def obj_data_monitor():
    global obj_path
    global object_data
    global import_status

    if obj_path != None:
        try:
            import_obj()
            obj_path = None
            object_data = None
            import_status = 'SUCCESS'    
        except Exception as e:
            print(str(e))
            import_status = 'FAILURE'    
    return 1.0

def receive_data():
    global obj_path
    global object_data
    global import_status
    global is_sync_mode

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_address = ('localhost', 25000)
    server_socket.bind(server_address)

    while True:
        server_socket.listen(5)
        print("Listening for OBJs...")

        connection, client_address = server_socket.accept()
        print("Connected with FreeCAD instance:", client_address)

        data = connection.recv(1024).decode()
        print(f"Received data: {data}")

        # Parse the data format
        # SYNC format: OBJ_PATH|{name1,label1},{name2,label2},...
        # EXPORT format: OBJ_PATH|label1,label2,...
        if '|' in data:
            parts = data.split('|', 1)
            obj_path = parts[0]
            
            # Parse object data
            if len(parts) > 1 and parts[1]:
                # Check if it's sync mode (contains braces) or export mode (plain labels)
                if '{' in parts[1]:
                    # SYNC MODE: Parse {name,label} pairs
                    is_sync_mode = True
                    object_data = []
                    import re
                    matches = re.findall(r'\{([^,]+),([^}]+)\}', parts[1])
                    for name, label in matches:
                        object_data.append((name, label))
                else:
                    # EXPORT MODE: Parse plain comma-separated labels
                    is_sync_mode = False
                    object_data = [label.strip() for label in parts[1].split(',') if label.strip()]
            else:
                is_sync_mode = False
                object_data = []
        else:
            # Fallback for old format (just path)
            obj_path = data
            object_data = []
            is_sync_mode = False
        
        import_status = 'IMPORTING'

        while import_status != None:
            if import_status == 'SUCCESS':
                connection.sendall("Successfully imported OBJ!".encode())
                break
            elif import_status == 'FAILURE':
                connection.sendall("Failed imported OBJ.".encode())
                break
            else:
                time.sleep(3)
                continue

        import_status = None
        connection.close()

def cleanup_threads():
    threads_cleaned = False
    while not threads_cleaned:
        time.sleep(2)
        for thread in threading.enumerate():
            if thread.getName() == "MainThread" and thread.is_alive() == False:
                cleanup_socket = socket.socket()
                cleanup_socket.connect(('localhost', 25000))
                cleanup_socket.send(b"Quit Blender!")
                cleanup_socket.close()
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