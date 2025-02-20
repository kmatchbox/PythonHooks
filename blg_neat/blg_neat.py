"""
Script Name: BLG / Neat Video Workflow
Script Version: 0.7
Flame Version: 2023
Author: Kyle Obley (info@kyleobley.com)

Creation date: 11.04.23
Modified date: 04.02.25

Description:

    BLG and Neat Video workflows

Change Log:

    v0.7: Removed GW dependancies.

          Fixed some old coding mistakes

          Hard-coded path of BLG.py to where it's on all systems and not using the flame version preset.

    v0.6: Changed the path to the BLG preset as ADSK changed where that is.

    v0.5: Changed the way we resolve the setup location. We now assume
          that there will be a fx_setup sub-folder in the location of our GW
          hooks.

          Fixed the name for the render node name for the BLG workflow.

    v0.4: Set destination reel based on task.

    v0.3: Added nag warning for Neat if the clip name has comp
          or clean-up in it.

    v0.2: Fixed duration so it took into account start frame.

          Added color management nodes for both routines.

    v0.1: Initial Release.

"""

def blg_workflow(selection):
    import flame
    import os

    #flame_version = flame.get_version()

    # Path the pybox as installed the Filmlight
    blg_path = "/usr/fl/blgflame/share/BLG.py"

    script_loc = os.path.abspath(os.path.dirname(__file__))
    setup = "fx_setups/tag_rec709.lut_node"
    cm_path = os.path.join(script_loc,setup)


    # Figure out where to start and place everything
    comp = selection[-1]
    pos_x = comp.pos_x
    pos_y = comp.pos_y

    # Create the nodes and define their positions
    mux_in = flame.batch.create_node("Mux")
    mux_in.name = "ungraded_comp_IN"
    mux_in.pos_x = pos_x + 150
    mux_in.pos_y = pos_y

    blg = flame.batch.create_node("Pybox", blg_path)
    blg.name = "BLG"
    blg.note = "You still need to T-click the comp"
    blg.pos_x = mux_in.pos_x + 150
    blg.pos_y = mux_in.pos_y

    cm = flame.batch.create_node("Colour Mgmt")
    cm.name = "tag_rec709"
    cm.pos_x = mux_in.pos_x + 300
    cm.pos_y = mux_in.pos_y

    # Try to load color management setup to tag as rec709
    try:
        cm.load_node_setup(cm_path)
    except:
        print ("ERROR: Can't load CM setup")

    # Cycle through shelf reels and see if graded renders exists. If not, create it.
    graded_shelf = False
    for reel in flame.batch.shelf_reels:
        if reel.name.get_value() == "graded_renders":
            graded_shelf = True

    if not graded_shelf:
        flame.batch.create_shelf_reel("graded_renders")

    # Needed info for render node
    comp_shot_num = comp.clip.versions[0].tracks[0].segments[0].shot_name
    comp_tape_name = comp.clip.versions[0].tracks[0].segments[0].tape_name
    comp_duration = comp.clip.versions[0].tracks[0].segments[0].source_duration.frame

    # Create render node
    render_node = create_render_node(comp.clip, comp_shot_num, comp_tape_name, comp_duration, "blg")
    render_node_object = flame.batch.get_node(render_node.get_value())
    #render_node_object = flame.batch.get_node(str(render_node).replace("'", ""))
    render_node_object.pos_x = mux_in.pos_x + 450
    render_node_object.pos_y = mux_in.pos_y

    # Connect everything
    flame.batch.connect_nodes(comp, "Default", mux_in, "Default")
    flame.batch.connect_nodes(mux_in, "Default", blg, "Front")
    flame.batch.connect_nodes(blg, "Default", cm, "Front")
    flame.batch.connect_nodes(cm, "Default", render_node_object, "Front")

def neat_workflow(selection):
    import flame
    import os

    script_loc = os.path.abspath(os.path.dirname(__file__))
    setup = "fx_setups/tag_16bit.lut_node"
    cm_path = os.path.join(script_loc,setup)

    # Get the clip & figure out where to start and place everything
    comp = selection[-1]
    pos_x = comp.pos_x
    pos_y = comp.pos_y

    # Let's quickly check the name of the clip and throw a warning
    # if someone is trying to denoise a comp / clean-up
    naughty = False
    keep_going = True
    naughty_words = ['_comp_', '_cleanup_', 'clean_up','clean-up']

    comp_name = comp.name.get_value()

    for i in range(len(naughty_words)):
        if naughty_words[i] in comp_name:
            naughty = True

    if naughty:
        dialog = flame.messages.show_in_dialog(
        title ="BLG / Neat Video Workflow",
        message = "Hey-yo! It looks like you're wanting to denoise a comp or clean-up. Are you sure you want to do that?\n\nUnless you have a specific reason to, that's a pretty bad practice.",
        type = "warning",
        buttons = ["Continue"],
        cancel_button = "Cancel")

        if dialog == "Continue":
            keep_going = True

        elif dialog == "Cancel":
            keep_going = False

    # Continue with the rest of the process as either we didn't catch a naughty word
    # or the user is happy with poor compositing practices.
    if keep_going:

        # Create the nodes and define their positions
        mux_in = flame.batch.create_node("Mux")
        mux_in.pos_x = pos_x + 150
        mux_in.pos_y = pos_y + 150

        neat = flame.batch.create_node("OpenFX")
        neat.change_plugin("Reduce Noise v5")
        neat.pos_x = mux_in.pos_x + 150
        neat.pos_y = mux_in.pos_y

        cm = flame.batch.create_node("Colour Mgmt")
        cm.name = "tag_16bit"
        cm.pos_x = mux_in.pos_x + 300
        cm.pos_y = mux_in.pos_y

        # Try to load color management setup to tag as 16bit
        try:
            cm.load_node_setup(cm_path)
        except:
            print ("ERROR: Can't load CM setup")

        # Needed info for render node
        comp_shot_num = comp.clip.versions[0].tracks[0].segments[0].shot_name
        comp_tape_name = comp.clip.versions[0].tracks[0].segments[0].tape_name
        comp_duration = comp.clip.versions[0].tracks[0].segments[0].source_duration.frame

        # Create render node
        render_node = create_render_node(comp.clip, comp_shot_num, comp_tape_name, comp_duration, "neat")
        render_node_object = flame.batch.get_node(str(render_node).replace("'", ""))
        render_node_object.pos_x = mux_in.pos_x + 450
        render_node_object.pos_y = mux_in.pos_y

        # Connect everything
        flame.batch.connect_nodes(comp, "Default", mux_in, "Default")
        flame.batch.connect_nodes(mux_in, "Default", neat, "Default")
        flame.batch.connect_nodes(neat, "Default", cm, "Front")
        flame.batch.connect_nodes(cm, "Default", render_node_object, "Front")

#
# Create a render node with some known values
#

def create_render_node(clip, shot_num, tape_name, duration, task):
    import flame
    import os

    clip_name = clip.name.get_value()
    shot_num = shot_num.get_value()
    #clip_name = str(clip.name).replace("'", "")
    #shot_num = str(shot_num).replace("'", "")
     
    # Convert the bit-depth from what clip returns (int) so we can use it for the render node
    bit_depth = str(clip.bit_depth) + "-bit"
    if clip.bit_depth == 16 or clip.bit_depth == 32:
        bit_depth = bit_depth + " fp"

    render_node = flame.batch.create_node("Render")

    # Set the name and destination based on task
    if task == "blg":
        render_node.name = "<batch iteration>_Grd-v"
        render_node.destination = ('Batch Reels', 'graded_renders')
    else:
        render_node.name = clip_name + "_dn"
        render_node.destination = ('Batch Reels', 'pre_renders')

    render_node.shot_name = str(shot_num)
    render_node.source_timecode = clip.start_time
    render_node.record_timecode = clip.start_time
    render_node.tape_name = tape_name
    render_node.bit_depth = bit_depth
    render_node.range_end = flame.batch.start_frame + (duration - 1)
    
    # Check if we have in/out marks and they're type PyTime
    # otherwise the script will fail
    if isinstance(clip.in_mark, flame.PyTime):
        render_node.in_mark = clip.in_mark
    if isinstance(clip.out_mark, flame.PyTime):
        render_node.out_mark = clip.out_mark

    return render_node.name

# Scope for clip only
def scope_clip(selection):
    import flame
    for item in selection:
        if isinstance(item, flame.PyClipNode):
            return True


def get_batch_custom_ui_actions():
    return [
          {
                "name": "BLG / Neat Video",
                "actions": [
                     {
                          "name": "BLG",
                          "isVisible": scope_clip,
                          "execute": blg_workflow
                     },
                     {
                          "name": "Neat Video",
                          "isVisible": scope_clip,
                          "execute": neat_workflow
                     }
                ]
          }
     ]