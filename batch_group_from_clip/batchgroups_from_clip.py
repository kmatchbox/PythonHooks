"""
Script Name: Batchgroups From Clips
Script Version: 1.5
Flame Version: 2025

Creation date: 03.08.21
Modified date: 26.01.26

Description:

    Creates a batchgroup from selected clips.

Change Log:

    v1.5: Fixed git merge.

    v1.4: Replaces any spaces in input with _.

    v1.3: Added option to the manu for fast comp creation (comp, frame 1001) as it's the most used
          and far faster to create batchgrups for a large number of shots.

          Added support for either making a render node, write node or both.

    v1.2: Can now have multiple selections. Forgot to use self. for the clip so it kept
          taking the first selection. Dumb mistake.

    v1.1: Added a pop-up to replace the various menu options. This allows the user
          to also specifiy their own task which means the the rest of the workflow works
          correctly. Sadly, this results in the ability to create one shot at a time.
          Need to find fix.

          Fixed a naming issue with comps, was using previous logic that no longer
          applies now that we're using v000.

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

make_render = False
make_write = True

class batchgroup_ui(object):

    def __init__(self, selection):
        self.main_window(selection)
        

    def main_window(self, selection):
        import flame
        import os
        from functools import partial

        self.currnet_clip = selection
        
        current_clip_name = selection.name.get_value()

        # Try to import PySide6, otherwise import PySide2
        try:
            from PySide6 import QtCore, QtGui, QtWidgets
        except ImportError:
            from PySide2 import QtCore, QtGui, QtWidgets

        # Get resolution depending on PySide version
        if QtCore.__version_info__[0] < 6:
            mainWindow = QtWidgets.QDesktopWidget()
            QAction = QtWidgets.QAction
        else:
            mainWindow = QtGui.QGuiApplication.primaryScreen()
            QAction = QtGui.QAction

        resolution = mainWindow.screenGeometry()

        # Define tasks
        self.tasks = ["comp", "cleanup", "matte", "screen", "other"]

        # Define start frames
        self.start_frame = ["1001", "1"]

        # Overall UI
        self.window = QtWidgets.QWidget()
        self.window.setMinimumSize(QtCore.QSize(200, 150))
        self.window.setMaximumSize(QtCore.QSize(300, 150))
        
        self.window.setWindowTitle(current_clip_name)
        self.window.setStyleSheet('background: #202020')
        self.window.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint)
        self.window.setAttribute(QtCore.Qt.WA_DeleteOnClose)

        self.window.move((resolution.width() / 2) - (self.window.frameSize().width() / 2),
                         (resolution.height() / 2) - (self.window.frameSize().height() / 2))


        # Labels
        self.task_label = QtWidgets.QLabel('Task:', self.window)
        self.start_frame_label = QtWidgets.QLabel('Start Frame:', self.window)
        self.other_label = QtWidgets.QLabel('Other:', self.window)
        self.other_label.setVisible(False)

        
        self.task_label.setAlignment(QtCore.Qt.AlignRight)
        self.start_frame_label.setAlignment(QtCore.Qt.AlignRight)
        self.other_label.setAlignment(QtCore.Qt.AlignRight)

        # Other field
        self.other_entry = QtWidgets.QLineEdit(self.window)
        self.other_entry.setMinimumSize(QtCore.QSize(150, 26))
        self.other_entry.setMaximumSize(QtCore.QSize(150, 26))
        self.other_entry.setStyleSheet('background: #202020')
        self.other_entry.setVisible(False)


        #### Task Menu ####

        # Toggle the other field if the task is other
        def task_change (task):
            if task == "other":
                self.other_entry.setStyleSheet('background: #373e47')
                self.other_entry.setEnabled(True)
                self.other_entry.setVisible(True)
                self.other_label.setVisible(True)
            else:
                self.other_entry.setStyleSheet('background: #202020')
                self.other_entry.setVisible(False)
                self.other_entry.setEnabled(False)
                self.other_entry.setText("")
                self.other_label.setVisible(False)
 

        # Task list drop-down
        self.task_menu = QtWidgets.QComboBox(self.window)
        self.task_menu.setMinimumSize(QtCore.QSize(150, 26))
        self.task_menu.setMaximumSize(QtCore.QSize(150, 26))
        self.task_menu.setStyleSheet('QComboBox {color: #9a9a9a; background-color: #24303d; font: 12pt "Discreet"}'
                                     'QComboBox::item:selected {color: #6a6a6a; background-color: #24303d;}')

        # Fill the task drop-down
        for i in range(len(self.tasks)):
            self.task_menu.addItem(self.tasks[i], i)

        self.task_menu.setCurrentIndex(0)

        ### Start Frame Manu ###

        # Start frame list drop-down
        self.start_frame_menu = QtWidgets.QComboBox(self.window)
        self.start_frame_menu.setMinimumSize(QtCore.QSize(150, 26))
        self.start_frame_menu.setMaximumSize(QtCore.QSize(150, 26))
        self.start_frame_menu.setStyleSheet('QComboBox {color: #9a9a9a; background-color: #24303d; font: 12pt "Discreet"}'
                                     'QComboBox::item:selected {color: #6a6a6a; background-color: #24303d;}')

        # Fill the start frame drop-down
        self.start_frame_menu.addItem("1001", 0)
        self.start_frame_menu.addItem("1", 1)
        self.start_frame_menu.setCurrentIndex(0)


        self.task_menu.currentTextChanged.connect(task_change)

        # Create / Cancel Buttons
        self.create_btn = QtWidgets.QPushButton('Create', self.window)
        self.create_btn.setMinimumSize(QtCore.QSize(110, 26))
        self.create_btn.setMaximumSize(QtCore.QSize(110, 26))
        self.create_btn.setStyleSheet('background: #732020')
        self.create_btn.clicked.connect(self.push_to_create)

        self.cancel_btn = QtWidgets.QPushButton('Cancel', self.window)
        self.cancel_btn.setMinimumSize(QtCore.QSize(110, 26))
        self.cancel_btn.setMaximumSize(QtCore.QSize(110, 26))
        self.cancel_btn.setStyleSheet('background: #373737')
        self.cancel_btn.clicked.connect(self.cancel)

        # Layout
        gridbox01 = QtWidgets.QGridLayout()
        gridbox01.setVerticalSpacing(10)
        gridbox01.setAlignment(QtCore.Qt.AlignLeft)
        gridbox01.setHorizontalSpacing(10)

        gridbox01.addWidget(self.task_label, 0, 0)
        gridbox01.addWidget(self.task_menu, 0, 1)
        gridbox01.addWidget(self.other_label, 1, 0)
        gridbox01.addWidget(self.other_entry, 1, 1)
        gridbox01.addWidget(self.start_frame_label, 2, 0)
        gridbox01.addWidget(self.start_frame_menu, 2, 1)

        hbox = QtWidgets.QHBoxLayout()
        hbox.addWidget(self.cancel_btn)
        hbox.addWidget(self.create_btn)

        vbox = QtWidgets.QVBoxLayout()
        vbox.setContentsMargins(10, 10, 10, 10)
        vbox.addLayout(gridbox01)
        vbox.addLayout(hbox)

        self.window.setLayout(vbox)

        self.window.show()

    def cancel (self):
        self.window.close()

    def push_to_create (self):
        import flame

        self.window.close()

        clip = self.currnet_clip
        task = str(self.task_menu.currentText())
        other = str(self.other_entry.text())
        start_frame = int(self.start_frame_menu.currentText())

        if other and task == "other":
            task = other

        # Replace and spaces with underscores
        task = task.replace(" ", "_")

        # Create the batchgroup
        create_batch_group(clip, task, start_frame)



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
        
    # Change the iteration naming
    current_iteration = batchgroup.current_iteration
    current_iteration.name = "<batch name>_v<iteration###>"

    # Create a render node with a few pre-set attributes.
    if make_render:
        render_node_object = create_render_node(clip, shot_num, tape_name, task)
        render_node_object.pos_x = 900
        if make_write:
            render_node_object.pos_y = 200

    # Create a write node with the correct attributes
    if make_write:
        write_node_object = create_write_node(clip, shot_num, tape_name, task)
        write_node_object.pos_x = 900


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

    if make_render:
        flame.batch.connect_nodes(mux_out, 'Default', render_node_object, 'Default')

    if make_write:
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

    return render_node

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

    write_node.add_to_workspace = True
    write_node.include_setup = True

    # Check if we have in/out marks and they're type PyTime
    # otherwise the script will fail
    if isinstance(clip.in_mark, flame.PyTime):
        write_node.in_mark = clip.in_mark
    if isinstance(clip.out_mark, flame.PyTime):
        write_node.out_mark = clip.out_mark

    write_node.media_path = str(base_path)
    write_node.name = "<batch name>_v<iteration###>"
    write_node.create_clip_path = "<shot name>/comps/<batch name>"
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

# Launch the UI for each clip selected to deal with multiple at the same time.
def launch_ui(selection):

    # Launch the UI. This will spawn multiple windows but they're under each other.
    for clip in selection:
        batchgroup_ui(clip)

# Frame 1001 defines
def create_comp_f1001(selection):
    for clip in selection:
        create_batch_group(clip, "comp", 1001)

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
            "actions": [
                {
                    "name": "Create Batchgroup (Comp, 1001)",
                    "isVisable": scope_clip,
                    "isEnabled": scope_clip,
                    "execute": create_comp_f1001
                },
                {
                    "name": "Create Batchgroup (Options)",
                    "isVisable": scope_clip,
                    "isEnabled": scope_clip,
                    "execute": launch_ui
                }                
            ]
        }
    ]