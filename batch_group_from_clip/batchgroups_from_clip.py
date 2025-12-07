"""
Script Name: Batchgroups From Clips
Script Version: 1.0
Flame Version: 2025

Creation date: 03.08.21
Modified date: 02.12.25

Description:

    Creates a batchgroup from selected clips.

Change Log:

    v1.0: Added a write node upon creation. This is hard-coded to my paths and folder structure.

    v0.9: Re-added the options for screen comps, cleanup & matte.
    
    v0.8: Added support for tags.

    v0.7: Fixed issue with single frames

          Code clean-up

    v0.6: Set every output to 16bit to save space due to the difference between
          EXR (PIZ) and DPX.

          Added option for screen comps

    v0.5: Added option to start at frame 1

    v0.4: Added in/out mark to render node now the API allows it

    v0.3: Fixed the iteration name so we don't get cleanup__comp__
          
          Added bit-depth support to match the render to the source clip.

    v0.2: Add ability to define task and set the names accordingly. Currently only cleanup & matte.

    v0.1: Initial Release.

"""

def create_batch_group(clip, task, frame):
    import flame

    try:
        clip_duration = clip.versions[0].tracks[0].segments[0].source_duration.frame
    except:
        clip_duration = 1

    clip_shot_num = clip.versions[0].tracks[0].segments[0].shot_name
    tape_name = clip.versions[0].tracks[0].segments[0].tape_name

    # Define variables to create the batchgroup
    schematic_reels_list = ["plates", "mattes", "pre_renders"]
    shelf_reels_list = ["batch_renders"]
    shot_name = clip.name.get_value()
    shot_num = clip_shot_num.get_value()

    batch_start_frame = frame
    batch_duration = clip_duration

    # Create batchgroup
    if task == "comp":
        batchgroup = flame.batch.create_batch_group(str(shot_name),
                                                    start_frame=batch_start_frame,
                                                    duration=batch_duration,
                                                    reels=schematic_reels_list,
                                                    shelf_reels=shelf_reels_list)
    else:
        shot_name_task = shot_name + "_" + task
        batchgroup = flame.batch.create_batch_group(str(shot_name_task),
                                                    start_frame=batch_start_frame,
                                                    duration=batch_duration,
                                                    reels=schematic_reels_list,
                                                    shelf_reels=shelf_reels_list)
        
        # Change the iteration naming if it's not a comp
        current_iteration = batchgroup.current_iteration
        current_iteration.name = "<batch name>_v<iteration###>"

    # Create a render node with a few pre-set attributes.
    render_node = create_render_node(clip, shot_num, tape_name, task)

    render_node_object = flame.batch.get_node(render_node.get_value())
    render_node_object.pos_x = 900

    # Create a write node with the correct attributes
    write_node_object = create_write_node(clip, shot_num, tape_name, task)
    write_node_object.pos_x = 900
    write_node_object.pos_y = render_node_object.pos_y - 300


    loaded_plate = load_clip_in_batch(clip)
    loaded_plate_object = flame.batch.get_node(loaded_plate.get_value())
    loaded_plate_object.pos_x = -900

    mux_in = flame.batch.create_node("Mux")
    mux_in.name = "Plate_IN"
    mux_in.pos_x = -660
    mux_in.set_context(1,'Default')
    mux_out = flame.batch.create_node("Mux")
    mux_out.name = "Render_Out"
    mux_out.pos_x = 600
    mux_out.set_context(4,'Default')

    # Connect all nodes
    flame.batch.connect_nodes(loaded_plate_object, 'Default', mux_in, 'Default')
    flame.batch.connect_nodes(mux_in, 'Default', mux_out, 'Default')
    flame.batch.connect_nodes(mux_out, 'Default', render_node_object, 'Default')
    flame.batch.connect_nodes(mux_out, 'Default', write_node_object, 'Default')

def create_render_node(clip, shot_num, tape_name, task):
    import flame
    import os

    sequence_name = clip.name.get_value()

    # Just set everything to 16bit, makes Flame use EXR (Piz) which is way better than DPX
    bit_depth = "16-bit fp"

    render_node = flame.batch.create_node("Render")

    if task == "comp":
        render_node.name = "<batch name>_comp_v<iteration###>"
    else:
        render_node.name = "<batch name>_v<iteration###>"

    render_node.shot_name = str(shot_num)
    render_node.frame_rate = clip.frame_rate
    render_node.source_timecode = clip.start_time
    render_node.record_timecode = clip.start_time
    render_node.tape_name = tape_name
    render_node.bit_depth = bit_depth
    render_node.tags = clip.tags

    # Check if we have in/out marks and they're type PyTime
    # otherwise the script will fail
    if isinstance(clip.in_mark, flame.PyTime):
        render_node.in_mark = clip.in_mark
    if isinstance(clip.out_mark, flame.PyTime):
        render_node.out_mark = clip.out_mark

    return render_node.name

def create_write_node(clip, shot_num, tape_name, task):
    import flame
    import os

    project = flame.project.current_project.name
    base_path = os.path.join("/PROJEKTS", project, "shots")

    write_node = flame.batch.create_node("Write File")

    write_node.shot_name = str(shot_num)
    write_node.frame_rate = clip.frame_rate
    write_node.source_timecode = clip.start_time
    write_node.record_timecode = clip.start_time
    write_node.tape_name = tape_name
    write_node.version_mode = "Follow Iteration"
    write_node.version_name = "v<version>"
    write_node.frame_padding = 4
    write_node.file_type = "OpenEXR"
    write_node.compress_mode = "DWAA"
    write_node.bit_depth = "16-bit fp"

    write_node.add_to_workspace = False
    write_node.include_setup = True

    # Check if we have in/out marks and they're type PyTime
    # otherwise the script will fail
    if isinstance(clip.in_mark, flame.PyTime):
        write_node.in_mark = clip.in_mark
    if isinstance(clip.out_mark, flame.PyTime):
        write_node.out_mark = clip.out_mark

    if task == "comp":
        write_node.name = "<batch name>_" + task + "_v<iteration###>"
        write_node.create_clip_path = "<shot name>/comps/<batch name>_" + task
    
    # It's something other than a comp.
    else:
        write_node.name = "<batch name>_v<iteration###>"
        write_node.create_clip_path = "<shot name>/comps/<batch name>"

    write_node.media_path = str(base_path)
    write_node.media_path_pattern = "<shot name>/comps/flame/" + task + "/<version name>/<name>."
    write_node.include_setup_path = "<shot name>/comp_scripts/flame/" + task + "/<batch iteration>"

    return write_node


def load_clip_in_batch(clip):
    import flame
    desk = flame.project.current_project.current_workspace.desktop  
    current_batchgroup = desk.current_batch_group.get_value()
    dest_reel_for_clip = current_batchgroup.reels[0]
    loaded_clip = flame.media_panel.copy(clip, dest_reel_for_clip)
    return loaded_clip[0].name

# Frame 1 defines
def create_comp_f1(selection):
    for clip in selection:
        create_batch_group(clip, "comp", 1)

def create_matte_f1(selection):
    for clip in selection:
        create_batch_group(clip, "matte", 1)

def create_cleanup_f1(selection):
    for clip in selection:
        create_batch_group(clip, "cleanup", 1)

def create_screen_f1(selection):
    for clip in selection:
        create_batch_group(clip, "screen", 1)

# Frame 1001 defines
def create_comp_f1001(selection):
    for clip in selection:
        create_batch_group(clip, "comp", 1001)

def create_cleanup_f1001(selection):
    for clip in selection:
        create_batch_group(clip, "cleanup", 1001)

def create_matte_f1001(selection):
    for clip in selection:
        create_batch_group(clip, "matte", 1001)

def create_screen_f1001(selection):
    for clip in selection:
        create_batch_group(clip, "screen", 1001)

def scope_clip(selection):
        import flame
        for item in selection:
            if isinstance(item, flame.PyClip):
                if not isinstance(item, flame.PySequence):
                    return True
        return False

def get_media_panel_custom_ui_actions():
    return [
        {
        "name": "Create Batchgroup",
            "hierarchy": [],
            "actions": [],
        },
        {
            "name": "Comp",
            "hierarchy": ["Create Batchgroup"],
            "order": 1,
            "actions": [    
                {
                    "name": "Frame 1",
                    "order": 1,
                    "isVisable": scope_clip,
                    "isEnabled": scope_clip,
                    "minimumVersion": "2025.2",
                    "execute": create_comp_f1                },
                {
                    "name": "Frame 1001",
                    "order": 2,
                    "isVisable": scope_clip,
                    "isEnabled": scope_clip,
                    "minimumVersion": "2025.2",
                    "execute": create_comp_f1001
                }
           ]
        },
        {
            "name": "Clean-up",
            "hierarchy": ["Create Batchgroup"],
            "order": 2,
            "actions": [
                {
                    "name": "Frame 1",
                    "order": 1,
                    "isVisable": scope_clip,
                    "isEnabled": scope_clip,
                    "minimumVersion": "2025.2",
                    "execute": create_cleanup_f1
                },
                {
                    "name": "Frame 1001",
                    "order": 2,
                    "isVisable": scope_clip,
                    "isEnabled": scope_clip,
                    "minimumVersion": "2025.2",
                    "execute": create_cleanup_f1001
                }
           ]
        },
        {
            "name": "Screen Comp",
            "hierarchy": ["Create Batchgroup"],
            "order": 3,
            "actions": [
                {
                    "name": "Frame 1",
                    "order": 1,
                    "isVisable": scope_clip,
                    "isEnabled": scope_clip,
                    "minimumVersion": "2025.2",
                    "execute": create_screen_f1
                },
                {
                    "name": "Frame 1001",
                    "order": 2,
                    "isVisable": scope_clip,
                    "isEnabled": scope_clip,
                    "minimumVersion": "2025.2",
                    "execute": create_screen_f1001
                }
           ]
        },
        {
            "name": "Matte",
            "hierarchy": ["Create Batchgroup"],
            "order": 4,
            "separator": "below",
            "actions": [
                {
                    "name": "Frame 1",
                    "order": 1,
                    "isVisable": scope_clip,
                    "isEnabled": scope_clip,
                    "minimumVersion": "2025.2",
                    "execute": create_matte_f1
                },
                {
                    "name": "Frame 1001",
                    "order": 2,
                    "isVisable": scope_clip,
                    "isEnabled": scope_clip,
                    "minimumVersion": "2025.2",
                    "execute": create_matte_f1001
                }
           ]
        }
    ]