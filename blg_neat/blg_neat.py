"""
Script Name: BLG / Neat Video Workflow
Script Version: 1.0
Flame Version: 2023
Author: Kyle Obley (info@kyleobley.com)

Creation date: 11.04.23
Modified date: 14.04.26

Description:

    BLG and Neat Video workflows

Change Log:

    v1.0: Fixed issue due to naming the color management node for the Neat workflow
          preventing the hook to be used multiple times within the same batch (i.e. multiple layers)

          On Flame 2026+ now using the API to set the bit-depth (Neat) & tag Rec 709 (BLG)

    v0.9: Fixed base_path error.

    v0.8: Added Neat v5/v6 support.

          Creates write node hardcoded to personal workflow.

          Added option to use render node or write node or both.

    v0.7: Removed GW dependancies.

          Fixed some old coding mistakes

          Hard-coded path of BLG.py to where it's on all systems and not using the flame version preset.

    v0.6: Changed the path to the BLG preset as ADSK changed where that is.

    v0.5: Changed the way we resolve the setup location. We now assume
          that there will be a fx_setup sub-folder in the location of our GW
          hooks.

          Fixed the name for the render node name for the BLG workflow.

    v0.4: Set destination reel based on task.

    v0.3: Added nag warning for Neat if the clip name has clip
          or clean-up in it.

    v0.2: Fixed duration so it took into account start frame.

          Added color management nodes for both routines.

    v0.1: Initial Release.

"""

make_render = False
make_write = True

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
    clip = selection[-1]
    pos_x = clip.pos_x
    pos_y = clip.pos_y

    # Create the nodes and define their positions
    mux_in = flame.batch.create_node("Mux")
    mux_in.name = "ungraded_clip_IN"
    mux_in.pos_x = pos_x + 150
    mux_in.pos_y = pos_y

    blg = flame.batch.create_node("Pybox", blg_path)
    blg.name = "BLG"
    blg.note = "You still need to T-click the clip"
    blg.pos_x = mux_in.pos_x + 150
    blg.pos_y = mux_in.pos_y

    cm = flame.batch.create_node("Colour Mgmt")
    cm.pos_x = mux_in.pos_x + 300
    cm.pos_y = mux_in.pos_y

    # If we're below 2026, load the CM node otherwise set it via the API.
    if version < 2026:
        # Try to load color management setup to tag as rec709
        try:
            cm.load_node_setup(cm_path)
        except:
            print ("ERROR: Can't load CM setup")
    else:
        cm.mode = "Tag Only"

        # Percaution in case ACES 2.0 isn't being used
        try:
            cm.tagged_colour_space = "Rec.1886 Rec.709 - Display"
        else:
            print (f"Colorspace can not be found: Rec.1886 Rec.709 - Display. You must not be using ACES 2.0")

    # Cycle through shelf reels and see if graded renders exists. If not, create it.
    graded_shelf = False
    for reel in flame.batch.shelf_reels:
        if reel.name.get_value() == "graded_renders":
            graded_shelf = True

    if not graded_shelf:
        flame.batch.create_shelf_reel("graded_renders")

    # Needed info for render node
    clip_shot_num = clip.clip.versions[0].tracks[0].segments[0].shot_name
    clip_tape_name = clip.clip.versions[0].tracks[0].segments[0].tape_name
    clip_duration = clip.clip.versions[0].tracks[0].segments[0].source_duration.frame

    # Create render node
    render_node = create_render_node(clip.clip, clip_shot_num, clip_tape_name, clip_duration, "blg")
    render_node_object = flame.batch.get_node(render_node.get_value())
    #render_node_object = flame.batch.get_node(str(render_node).replace("'", ""))
    render_node_object.pos_x = mux_in.pos_x + 450
    render_node_object.pos_y = mux_in.pos_y

    # Connect everything
    flame.batch.connect_nodes(clip, "Default", mux_in, "Default")
    flame.batch.connect_nodes(mux_in, "Default", blg, "Front")
    flame.batch.connect_nodes(blg, "Default", cm, "Front")
    flame.batch.connect_nodes(cm, "Default", render_node_object, "Front")

def neat_workflow(selection):
    import flame
    import os

    script_loc = os.path.abspath(os.path.dirname(__file__))
    setup = "fx_setups/tag_16bit.lut_node"
    cm_path = os.path.join(script_loc,setup)
    version = int(flame.get_version_major())

    # Get the clip & figure out where to start and place everything
    clip_object = selection[0]

    clip = clip_object.clip
    clip_name = clip.name.get_value()

    pos_x = clip_object.pos_x
    pos_y = clip_object.pos_y

    # Let's quickly check the name of the clip and throw a warning
    # if someone is trying to denoise a clip / clean-up
    naughty = False
    keep_going = True
    naughty_words = ['_comp_', '_cleanup_', 'clean_up','clean-up']

    for i in range(len(naughty_words)):
        if naughty_words[i] in clip_name:
            naughty = True

    if naughty:
        dialog = flame.messages.show_in_dialog(
        title ="BLG / Neat Video Workflow",
        message = "Hey-yo! It looks like you're wanting to denoise a clip or clean-up. Are you sure you want to do that?\n\nUnless you have a specific reason to, that's a pretty bad practice.",
        type = "warning",
        buttons = ["Continue"],
        cancel_button = "Cancel")

        if dialog == "Continue":
            keep_going = True

        elif dialog == "Cancel":
            keep_going = False

    # Continue with the rest of the process as either we didn't catch a naughty word
    # or the user is happy with poor clipositing practices.
    if keep_going:


        # Create the nodes and define their positions
        mux_in = flame.batch.create_node("Mux")
        mux_in.pos_x = pos_x + 150
        mux_in.pos_y = pos_y + 150

        neat = flame.batch.create_node("OpenFX")

        # Try to load v6, fallback to v5
        try:
            neat.change_plugin("Reduce Noise v6")
            print ("Neat Video v6 Loaded")
        except:
            neat.change_plugin("Reduce Noise v5")
            print ("Neat Video v5 Loaded")
        neat.pos_x = mux_in.pos_x + 150
        neat.pos_y = mux_in.pos_y

        cm = flame.batch.create_node("Colour Mgmt")
        
        #cm.name = "tag_16bit"
        cm.pos_x = mux_in.pos_x + 300
        cm.pos_y = mux_in.pos_y

        # If we're below 2026, load the CM node otherwise set it via the API.
        if version < 2026:
            # Try to load color management setup to tag as 16bit
            try:
                cm.load_node_setup(cm_path)
            except:
                print ("ERROR: Can't load CM setup")
        else:
            cm.bit_depth = 16

        # Needed info for render & write nodes
        shot_name = clip.versions[0].tracks[0].segments[0].shot_name.get_value()
        tape_name = clip.versions[0].tracks[0].segments[0].tape_name
        duration = clip.versions[0].tracks[0].segments[0].source_duration.frame

        # Create render node if user wants
        if make_render:
            
            render_node = create_render_node(clip, shot_name, tape_name, duration, "neat")
            render_node.pos_x = mux_in.pos_x + 450

            # Push render up a bit if we're also creating a write node
            if make_write:
                render_node.pos_y = mux_in.pos_y + 200
            else:
                render_node.pos_y = mux_in.pos_y

        # Create write node if user wants
        if make_write:
            write_node = create_write_node(clip, shot_name, tape_name, duration, "neat")
            write_node.pos_x = mux_in.pos_x + 450
            write_node.pos_y = mux_in.pos_y


        # Connect everything
        flame.batch.connect_nodes(clip_object, "Default", mux_in, "Default")
        flame.batch.connect_nodes(mux_in, "Default", neat, "Default")
        flame.batch.connect_nodes(neat, "Default", cm, "Front")

        if make_render:
            flame.batch.connect_nodes(cm, "Default", render_node, "Front")

        if make_write:
            flame.batch.connect_nodes(cm, "Default", write_node, "Front")

#
# Create a render node with some known values
#

def create_render_node(clip, shot_num, tape_name, duration, task):
    import flame
    import os

    clip_name = clip.name.get_value()
    #shot_num = shot_num.get_value()
     
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

    render_node.shot_name = shot_num
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

    #return render_node.name
    return render_node

def create_write_node(clip, shot_num, tape_name, duration, task):
    import flame
    import os

    project = flame.project.current_project.name
    base_path = os.path.join("/PROJEKTS", project, "shots")


    clip_name = clip.name.get_value()

    write_node = flame.batch.create_node("Write File")

    write_node.media_path = str(base_path)
    write_node.name = clip_name + "_dn"  
    write_node.media_path_pattern = "<shot name>/plates/full_dn/<name>."
    write_node.destination = ('Batch Reels', 'pre_renders')

    write_node.add_to_workspace = True
    write_node.include_setup = False
    write_node.create_clip = False

    write_node.file_type = "OpenEXR"
    write_node.compress_mode = "DWAA"
    write_node.bit_depth = "16-bit fp"
    write_node.frame_padding = 4

    write_node.shot_name = str(shot_num) 
    write_node.frame_rate = clip.frame_rate
    write_node.source_timecode = clip.start_time
    write_node.record_timecode = clip.start_time
    write_node.tape_name = tape_name
    write_node.range_end = flame.batch.start_frame + (duration - 1)
          
    # Check if we have in/out marks and they're type PyTime
    # otherwise the script will fail
    if isinstance(clip.in_mark, flame.PyTime):
        write_node.in_mark = clip.in_mark
    if isinstance(clip.out_mark, flame.PyTime):
        write_node.out_mark = clip.out_mark

    return write_node

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