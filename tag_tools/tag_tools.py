"""
Script Name: Tag Tools
Script Version: 1.0
Flame Version: 2025

Creation date: 12.03.26
Modified date: 12.03.26

Description:

    Manages tags on sequences to be used later in QTs with the objective
    of being able to track original sequence name from Flame vs client name
    as well as audio.

    Provides renaming tools to be able 

Change Log:

    v1.0: Initial Release

"""

#-------------------------------------
# [Imports]
#-------------------------------------
import flame
import sys
import os
from qt_metadata_lib import QuickTimeFile


# Primary function to set tag names. This is versitale and can be used for anything.
# This will also check if the tag already exists and update it accordingly.
def set_tag(sequence, tag_name, value):
    
    # Create an empty tags
    tags = []

    # Get existing tags
    tags = sequence.tags.get_value()

    print(f"[ Tagging Tools ] Sequence:      {sequence.name.get_value()}")
    print(f"[ Tagging Tools ] Current tags:  {tags}")

    # Look for existing tags that match our tag name.
    # Remove it if found.
    for item in tags[:]: 
        if item.startswith(f"{tag_name}:"):
            print(f"[ Tagging Tools ] Existing tag:  {item}")
            tags.remove(item)

    # Set name tag. The name type and name are seperated
    # by : so we can treat it like a key pair.
    new_tag = ":".join([tag_name, value])

    # Add the new tag
    tags.append(new_tag)

    # Set tag
    sequence.tags = tags
    print(f"[ Tagging Tools ] Updated tags:  {sequence.tags}")


# Set sequence name tags for both internal & client
def set_name_tag_to_current(sequence, tag_name):
    # Get sequence name
    name = sequence.name.get_value()
    set_tag(sequence, tag_name, name)

# Rename sequence based on tag for both internal & client
def rename_sequence(sequence, tag_name):
    
    # Create an empty tags
    tags = []

    # Get tags
    tags = sequence.tags.get_value()

    found_tag = False

    # Look for existing tags that match our tag name.
    for item in tags[:]: 
        if item.startswith(f"{tag_name}:"):
            found_tag = True
            new_name = item.split(":", 1)[1]

    # Foudn the tag, rename sequence.
    if found_tag:
        print(f"Current name:  {sequence.name.get_value()}")
        print(f"New name:      {new_name}")

        # Change the actual name
        sequence.name.set_value(new_name)
    else:
        print(f"Error: The tag {tag_name} doesn't exist in this sequence: {sequence.name.get_value()}")


# Functions to guide the real work
def set_internal_name(selection):
    for item in selection:
        set_name_tag_to_current(item, "internal_name")

def set_client_name(selection):
    for item in selection:
        set_name_tag_to_current(item, "client_name")

def rename_to_internal_name(selection):
    for item in selection:
        rename_sequence(item, "internal_name")

def rename_to_client_name(selection):
    for item in selection:
        rename_sequence(item, "client_name")

def set_internal_and_client_name(selection):
    for item in selection:
        name = item.name.get_value()

        # Check that we have our seperator
        if "__" in name:

            # Get internal and client names
            internal = name.split("__")[0]
            client = name.split("__")[1]

            # Set internal
            set_tag(item, "internal_name", internal)

            # Set client
            set_tag(item, "client_name", client)
        else:
            print(f"[ Tagging Tools ] Error: The seuqnece {name} is missing __ seperating the internal and client names.")


def set_audio(selection):
    for item in selection:

        audio_list = []

        if item.audio_tracks:
            for track in item.audio_tracks:
                if track:
                    for channel in track.channels:
                        for audio in channel.segments:
                            if audio:
                                if audio.file_path and audio.file_path != '':
                                    # Get the basename, the whole path would be too long
                                    audio_file = os.path.basename(audio.file_path)
                                    audio_list.append(audio_file)
                                    print(f"[ Tagging Tools ] Found audio file:  {audio_file}")


            # Sort the list to remove duplicates
            audio_list = sorted(set(audio_list))

            # Convert the list to a string
            audio_files = ",".join(audio_list)

            # Set tag
            set_tag(item, "audio_files", audio_files)

        else:
            print(f"[ Tagging Tools ] The seuqnece {item.name.get_value()} has no audio files.")



# Set the tags within the QT file itself
# Not used yet.
def set_qt_tags(selection, tags):
    qt = QuickTimeFile(selection)
    print(qt.get_metadata("com.apple.quicktime.comment"))

    qt.set_metadata("com.apple.quicktime.comment", "int_name:xxx_30_xx01_0303")
    qt.save()

    print(qt.get_metadata("com.apple.quicktime.comment"))


#-------------------------------------
# [Scope]
#-------------------------------------
def sequence_selected(selection):
    for item in selection:
        if isinstance(item, (flame.PySequence)):
            return True
    return False

def get_media_panel_custom_ui_actions():
    return [

        {
            "name": "Set Tag",
            "hierarchy": ["Tagging Tools"],
            "order": 1,
            "actions": [
                {
                    "name": "Current Name -> Internal Name",
                    "order": 1,
                    "isVisable": sequence_selected,
                    "isEnabled": sequence_selected,
                    "execute": set_internal_name,
                    "minimumVersion": "2025.1"
                },
                {
                    "name": "Current Name -> Client Name",
                    "order": 2,
                    "isVisable": sequence_selected,
                    "isEnabled": sequence_selected,
                    "execute": set_client_name,
                    "minimumVersion": "2025.1"
                },
                {
                    "name": "Current Name -> Both (Split internal__client)",
                    "order": 2,
                    "isVisable": sequence_selected,
                    "isEnabled": sequence_selected,
                    "execute": set_internal_and_client_name,
                    "minimumVersion": "2025.1"
                },
                {
                    "name": "Current Audio -> Audio",
                    "order": 3,
                    "isVisable": sequence_selected,
                    "isEnabled": sequence_selected,
                    "execute": set_audio,
                    "minimumVersion": "2025.1"
                }
           ]
        },
        {
            "name": "Rename Clip From Tag",
            "hierarchy": ["Tagging Tools"],
            "order": 2,
            "actions": [
                {
                    "name": "Internal Name",
                    "order": 1,
                    "isVisable": sequence_selected,
                    "isEnabled": sequence_selected,
                    "execute": rename_to_internal_name,
                    "minimumVersion": "2025.1"
                },
                {
                    "name": "Client Name",
                    "order": 2,
                    "isVisable": sequence_selected,
                    "isEnabled": sequence_selected,
                    "execute": rename_to_client_name,
                    "minimumVersion": "2025.1"
                }
           ]
        }
    ]
