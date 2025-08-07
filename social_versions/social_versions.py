"""
Script Name: Social Versions
Script Version: 0.4
Flame Version: 2025
Author: Kyle Obley (info@kyleobley.com)

Creation Date: 05.02.25
Modified Date: 07.08.25

Description:

    Creates social timelines based on other, selected timelines.

Change Log:

    v0.4: Fixed the script failing when setting the color of the sequence.

    v0.3: Get existing colour coding and apply it to the new sequence.

    v0.2: Fixed the width & height mismatch. Swapped them on some formats.

          Added name instead of width x height.

          Relaces 16x9 with name if found in sequence name.

    v0.1: Initial release.

"""
#-------------------------------------
# [Imports]
#-------------------------------------
import flame

#-------------------------------------

def create_11(selection):
    create_timeline(selection, 1080, 1080, "1x1")

def create_45(selection):
    create_timeline(selection, 1350, 1080, "4x5")

def create_916(selection):
    create_timeline(selection, 1920, 1080, "9x16")

#-------------------------------------
# [Main Function]
#-------------------------------------

def create_timeline(selection, height, width, aspect_ratio_name):

    # Get current reel_group via parent.
    reel_group_parent = selection[0].parent.parent

    # Check if a reel for our resolution exists already. If not, create one
    new_reel_name_exists = False
    new_reel_name = str(height) + "x" + str(width)
    new_reel_name = aspect_ratio_name

    for reel in reel_group_parent.reels:
        if reel.name == new_reel_name:
            new_reel_name_exists = True
            target_reel = reel

    # Reel doesn't exist, create one
    if not new_reel_name_exists:
        target_reel = reel_group_parent.create_reel(new_reel_name)

    # Iterate through each sequence and create the actual timelines
    for sequence in selection:

        # Check if 16x9 is in name. If so, replace with aspect ratio. If not, append.
        sequence_name = sequence.name.get_value()

        if "16x9" in sequence_name:
            new_sequence_name = sequence_name.replace("16x9", aspect_ratio_name)
        else:
            new_sequence_name = sequence_name + "_" + aspect_ratio_name

        # Get frame-rate & start time
        frame_rate = sequence.frame_rate
        start_time = sequence.start_time

        start_tc = flame.PyTime(str(sequence.start_time), sequence.frame_rate)
        
        num_video_trks = len(sequence.versions[0].tracks)
        num_audio_trks = 1

        new_sequence = target_reel.create_sequence(
            name = new_sequence_name,
            height = height,
            width = width,
            bit_depth = sequence.bit_depth,
            frame_rate = frame_rate,
            ratio = (width / height),
            video_tracks = num_video_trks,
            audio_tracks = num_audio_trks,
            scan_mode = "P",
            start_at = start_tc
            )

        # Set the sequence colour
        new_sequence.colour = sequence.colour

        # Overwrite with previous sequence
        new_sequence.overwrite(sequence, flame.PyTime(1))
        
        # Bring positioner to first frame and top version/layer
        new_sequence.current_time = flame.PyTime(1)
        new_sequence.primary_track = new_sequence.versions[-1].tracks[-1]


#-------------------------------------
# [Scope]
#-------------------------------------
def sequence_selected(selection):
    for item in selection:
        if isinstance(item, (flame.PySequence)):
            return True
    return False

#-------------------------------------
# [Media Panel Menu]
#-------------------------------------
def get_media_panel_custom_ui_actions():
    return [
        {
            "name": "Social Versions",
            "actions": [
                {
                    "name": "Create 1x1",
                    "isVisable": sequence_selected,
                    "isEnabled": sequence_selected,
                    "execute": create_11
                },
                {
                    "name": "Create 4x5",
                    "isVisable": sequence_selected,
                    "isEnabled": sequence_selected,
                    "execute": create_45
                },
                {
                    "name": "Create 9x16",
                    "isVisable": sequence_selected,
                    "isEnabled": sequence_selected,
                    "execute": create_916
                },
            ]
        }
    ]