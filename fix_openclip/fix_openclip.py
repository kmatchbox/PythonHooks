"""
Script Name: Fix openClip
Script Version: 0.1
Flame Version: 2023
Author: Kyle Obley (info@kyleobley.com)

Creation date: 05.01.24
Modified date: 05.01.24

Description:

    Changes the <name> field in an openClip to match the filename.

Change Log:

    v0.1: Initial Release

"""

def fix_openclip(selection):
    import os
    import xml.etree.ElementTree as ET

    for item in selection:
        file = item.path
        basename = os.path.splitext(os.path.basename(file))[0]

        # Load XML
        tree = ET.parse(file)
        root = tree.getroot()

        for child in root:

            # Find the root instance of name which is what we're after
            if child.tag == "name":
                print ("File:     ", file)
                print ("Original: ", child.text)
                print ("Modified: ", basename)

                child.text = basename

                # Write out the modified XML
                tree.write(file)

def is_clip(selection):
    import os
    for item in selection:
        if os.path.splitext(item.path)[1] == '.clip':
            return True
        else:
            return False

def get_mediahub_files_custom_ui_actions():
    return [
        {
            "name": "Fix openClip",
            "actions": [
                {
                    "name": "Fix openClip Name",
                    "execute": fix_openclip,
                    "isVisible": is_clip,
                }
            ]
        }
    ]