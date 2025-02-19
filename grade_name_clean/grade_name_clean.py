"""
Script Name: Grade Name Clean
Script Version: 0.1
Flame Version: 2021
Author: Kyle Obley (info@kyleobley.com)

Creation date: 01.07.24

Description:

    Clean-up clip names from external graders who have event or some other
    crap added to the name separated by a .

Change Log:

    v0.1: Initial Release 

"""

def clean_up(selection):
    import flame
    import os
    import re

    for clip in selection:
        currentClip = clip.name
        currentClipString = clip.name.get_value()

        # Keep whatever is before the .     
        clip.name.set_value(currentClipString.split(".")[0])

def clip_selected(selection):
    import flame
    for item in selection:
        if isinstance(item, (flame.PySequence, flame.PyClip)):
            return True
    return False

def get_media_panel_custom_ui_actions():
    return [
        {
            "name": "Renaming Tools",
            "actions": [
                {
                    "name": "Grade Name Clean-Up",
                    "isVisable": clip_selected,
                    "isEnabled": clip_selected,
                    "execute": clean_up
                }
            ]
        }
    ]