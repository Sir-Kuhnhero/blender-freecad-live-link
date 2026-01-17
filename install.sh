#!/bin/bash

FREECAD_ADDONS_DIRECTORY="$HOME/.local/share/FreeCAD/v1-2/Mod"
BLENDER_ADDONS_DIRECTORY="$HOME/.var/app/org.blender.Blender/config/blender/5.0/scripts/addons"

if [ -d "$FREECAD_ADDONS_DIRECTORY" ]; then
    echo "Installing FreeCAD addons..."
    cp -r ./BlenderLiveLink "$FREECAD_ADDONS_DIRECTORY/"
else
    echo "FreeCAD addons directory not found. Skipping FreeCAD addon installation."
fi

if [ -d "$BLENDER_ADDONS_DIRECTORY" ]; then
    echo "Installing Blender addons..."
    cp -r ./FreeCADLiveLink "$BLENDER_ADDONS_DIRECTORY/"
else
    echo "Blender addons directory not found. Skipping Blender addon installation."
fi