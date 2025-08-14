"""
Script Name: Blanking Check
Script Version: 0.1
Flame Version: 2021

Creation date: 09.02.22
Modified date: 11.11.24

Description:

    Adds a blanking check to a new, top layer.

Change Log:

    v0.1: Initial Release

"""

def add_check(selection):
    import flame
    import os
    for sequence in selection:
        version_num = len(sequence.versions) - 1
        version = sequence.versions[version_num]
        version.create_track(-1)
        seg = version.tracks[-1].segments[0]

        script_loc = os.path.abspath(os.path.dirname(__file__))

        blank_mx_path = os.path.join(script_loc, "fx_setups/blanking.1.glsl")
        blank_mx = seg.create_effect("Matchbox", blank_mx_path)
        blank_mx.load_setup(os.path.join(script_loc, "fx_setups/blanking.matchbox_node"))

        blank_fx = seg.create_effect("2D Transform")
        blank_fx.load_setup(os.path.join(script_loc,"fx_setups/blanking.2dtransform_node"))

        seg.name.set_value("BLANKING___CHK")


def remove_check(selection):
    import flame
    for sequence in selection:
        for version in sequence.versions:
            for track in version.tracks:
                for segment in track.segments:
                    if segment.name == 'BLANKING___CHK':
                        print (f"Removing blanking check on sequence: {sequence.name.get_value()}")
                        flame.delete(track)


def sequence_selected(selection):
    import flame
    for item in selection:
        if isinstance(item, (flame.PySequence)):
            return True
    return False

def get_media_panel_custom_ui_actions():
    return [
        {
            "name": "QC Tools",
            "actions": [
                {
                    "name": "Add Blanking Check",
                    "isVisable": sequence_selected,
                    "isEnabled": sequence_selected,
                    "execute": add_check
                },
                {
                    "name": "Remove Blanking Check",
                    "isVisable": sequence_selected,
                    "isEnabled": sequence_selected,
                    "execute": remove_check
                }
            ]
        }
    ]