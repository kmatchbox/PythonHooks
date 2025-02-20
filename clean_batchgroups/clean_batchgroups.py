"""
Script Name: Clean Batchgroups
Script Version: 0.3
Flame Version: 2023
Author: Kyle Obley (info@kyleobley.com)

Creation date: 24.05.23
Modified date: 11.02.25

Description:

Prepare batchgroups for archiving by removing everything but
the last 3 iterations, renders or both.

Chnage Log:

    v0.3: Added option for retaining only 1 iteration.

    v0.2: Added option for retaining only 1 render.

    v0.1: Initial Release

"""

def clean_batch_group(selection):
    import flame

    for batch_group in selection:
        for iteration in batch_group.batch_iterations[:-3]:
            print ("Deleting Iteration: ", iteration.name.get_value())
            flame.delete(iteration, confirm=False)

def clean_batch_group_one(selection):
    import flame

    for batch_group in selection:
        for iteration in batch_group.batch_iterations[:-1]:
            print ("Deleting Iteration: ", iteration.name.get_value())
            flame.delete(iteration, confirm=False)

def clean_renders(selection):
    import flame

    for batch_group in selection:
        for reel in batch_group.shelf_reels:
            current_reel = reel.name.get_value()
            if current_reel == "Batch Renders" or current_reel == "batch_renders":
                for clip in reel.clips[:-3]:
                    print ("Deleting Render:    ", clip.name.get_value())
                    flame.delete(clip, confirm=False)

def clean_renders_one(selection):
    import flame

    for batch_group in selection:
        for reel in batch_group.shelf_reels:
            current_reel = reel.name.get_value()
            if current_reel == "Batch Renders" or current_reel == "batch_renders":
                for clip in reel.clips[:-1]:
                    print ("Deleting Render:    ", clip.name.get_value())
                    flame.delete(clip, confirm=False)

def clean_both(selection):
    import flame

    clean_batch_group(selection)
    clean_renders(selection)


def scope_batch(selection):
    import flame

    for item in selection:
        if isinstance(item, flame.PyBatch):
            return True
    return False

def get_media_panel_custom_ui_actions():
    return [
        {
            "name": "Archiving Prep",
            "actions": [
                {
                    "name": "Clean Iterations",
                    "order": 2,
                    "isVisible": scope_batch,
                    "minimumVersion": "2023.2.0.0",
                    "execute": clean_batch_group
                },
                {
                    "name": "Clean Iterations (Leave 1)",
                    "order": 3,
                    "isVisible": scope_batch,
                    "minimumVersion": "2023.2.0.0",
                    "execute": clean_batch_group_one
                },
                {
                    "name": "Clean Renders",
                    "order": 4,
                    "isVisible": scope_batch,
                    "minimumVersion": "2023.2.0.0",
                    "execute": clean_renders
                },
                {
                    "name": "Clean Renders (Leave 1)",
                    "order": 5,
                    "isVisible": scope_batch,
                    "minimumVersion": "2023.2.0.0",
                    "execute": clean_renders_one
                },
                {
                    "name": "Clean Both",
                    "order": 6,
                    "isVisible": scope_batch,
                    "minimumVersion": "2023.2.0.0",
                    "execute": clean_both
                }
           ]
        }
    ]