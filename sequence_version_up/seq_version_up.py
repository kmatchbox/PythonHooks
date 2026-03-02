"""
Script Name: Sequence Verion Up
Script Version: 0.1
Flame Version: 2021
Author: Kyle Obley (info@kyleobley.com)

Creation date: 09.03.21
Modified date: 28.06.25

Description:

    Versions up a sequence following a naming convention. The name must follow the pattern
    of clip_tag##_mmdd to match and be updated.

Change Log:

    v0.1: Initial Release 

"""

# Define tag here
global tag
tag = "sv"

def version_up(selection):
    import flame
    import os
    import re
    from datetime import date

    today = date.today()
    todayShort = today.strftime("%m%d")

    for clips in selection:
        currentClip = clips.name
        currentClipString = str(clips.name)
        
        itemList = []
        foundTag = False

        # Iterate over the values and update both the version and short date
        for item in currentClipString.split("_"):
            
            # We've already updated the version so update date
            if foundTag == True:
                item = todayShort
                foundTag = False
            
            # Find version and increment
            if re.match(fr'{tag}(\d+)', item):
                number = int(item.strip(tag)) + 1
                item = tag + str(number).zfill(2)
                foundTag = True

            itemList.append(item)

        newClipName = "_".join(itemList).strip("'")
        clips.name.set_value(newClipName)   

def version_reset(selection):
    import flame
    import re

    for clips in selection:
        currentClip = clips.name
        currentClipString = str(clips.name)

        itemList = []

        # Iterate over the values and update both the version and short date
        for item in currentClipString.split("_"):
            # Find version and increment
            if re.match(fr'{tag}', item):
                item = tag + "01"

            itemList.append(item)

        newClipName = "_".join(itemList).strip("'")
        clips.name.set_value(newClipName)



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
                    "name": "Sequence - Version Up",
                    "isVisable": clip_selected,
                    "isEnabled": clip_selected,
                    "execute": version_up
                },
                {
                    "name": "Sequence - Reset",
                    "isVisable": clip_selected,
                    "isEnabled": clip_selected,
                    "execute": version_reset
                }
            ]
        }
    ]