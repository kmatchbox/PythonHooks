"""
Script Name: Clean Batchgroups
Script Version: 0.4
Flame Version: 2023
Author: Kyle Obley (info@kyleobley.com)

Creation date: 24.05.23
Modified date: 28.09.26

Description:

Prepare batchgroups for archiving by removing everything but
the last 3 iterations, renders or both.

Chnage Log:

    v0.4: Added option to find rendered, managed clips.

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

def find_managed_media(selection):
    import flame

    for batch_group in selection:
        for reel in batch_group.shelf_reels:
            for clip in reel.clips:

                batch_group_name = batch_group.name.get_value()
                name = clip.name.get_value()
                cached = clip.cached

                # Some ditry hack to get around audio for the moment for the path and duration
                try:
                    path = clip.versions[0].tracks[0].segments[0].file_path
                except:
                    path = ""

                if cached == "Cached" or path == "":
                    print (f"Found: {name} in {batch_group_name}")
                    clip.colour = (255, 0, 0)
                    batch_group.colour = (255, 0, 0)


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
                },
                {
                    "name": "Find Managed Media",
                    "order": 7,
                    "isVisible": scope_batch,
                    "minimumVersion": "2023.2.0.0",
                    "execute": find_managed_media
                }
           ]
        }
    ]