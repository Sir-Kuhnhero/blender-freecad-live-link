# Blender-FreeCAD Live Link
Live link to send a model from FreeCAD to Blender in a single-click.

Final source code of my article [Build your own Live Links for Blender (and more)](https://salaivv.com/2023/06/20/live-link-blender).

![Banner](/banner_live_link.jpg)

## How it works

The Blender addon creates a listening socket as soon as Blender starts up. Upon clicking on `Export to Blender` or `Sync to Blender` in FreeCAD, a temporary directory is created in the system `temp` folder and an OBJ is exported to this temporary directory. Then FreeCAD will send the full path to the exported OBJ to Blender through the socket connection. Blender would then import the model and send back a success message upon which FreeCAD will close the connection and cleanup the temporary directory.

## Installation

1. Place the folder `BlenderLiveLink` inside the Mod directory of FreeCAD installation folder. Refer to [this page](https://wiki.freecad.org/Installing_more_workbenches) in the FreeCAD wiki for platform-specific instructions.
2. Place the folder `FreeCADLiveLink` inside the Blender addons directory. Refer to [this page](https://docs.blender.org/manual/en/latest/advanced/blender_directory_layout.html) in the Blender documentation for platform-specific instructions. Then enable the addon from the your Preferences.

## Usage

Once you have installed the scripts, open a model in FreeCAD and also keep Blender running. Click on the `Blender` menu in FreeCAD menu bar and you will see two commands

1. `Export To Blender`: By using this operation the selected model will be exported as an OBJ and imported into your running Blender instance. If done more than once it adds a new body in blender each time.

2. `Sync to Blender`: By using this operation the selected model will be exported as an OBJ and imported into your running Blender Instance. This function keeps a "link" between the FreeCAD and Blender bodies. If you change the FreeCAD body and use the `Sync to Blender` function again it will update the corresponing mesh in Blender without overriding colours or modifyers. It however will override scalling and rotation changes. it is recomended to use a empty body to containe the synced body in order to be able to move, rotate and scale it.

Both these command support Bodies as well as Assemblies and Nested Assemblies with liked objetcs.

## Notes

This is a forke with the following improvements (WIP)

1. Support for FreeCAD v1.0 to v1.2. I am runnign the newest dev build of 1.2 so that is what I recomend.
2. Seperate Export and Sync options.
    - Export works like the original addon by creating a body of the currently selected FreeCAD body in blender
    - Sync is a new operation that also creates a bodie of the in FreeCAD selected bodies. However it also checks if the body have already been created in blender. If yes then it simply updates the mesh to reflect the changes made in FreeCAD. It does not chage Position, Modifyers and material.  
3. Support for nested Assenblies
