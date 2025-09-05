"""
Script Name: Save Batchgroups to Location
Script Version: 1.0

Flame Version: 2023

Creation date: 05.09.25
Modified date: 05.09.25

Description:

Go through all the selected batchgroups on the desktop and save
them to the specific folder provided by the user.

Chnage Log:

    v1.0: Initial Release

"""


def save_batch(selection):
    import flame
    import os
    from PySide6 import QtWidgets

    # Prompt user for destination

    project_home = os.path.join("/opt/Autodesk/project", flame.project.current_project.name)

    dlg = QtWidgets.QFileDialog()
    init_dir = project_home
    dlg.setDirectory(init_dir)
    dlg.setOption(QtWidgets.QFileDialog.DontUseNativeDialog, True)
    dlg.setOption(QtWidgets.QFileDialog.ShowDirsOnly, True)
    dlg.setFileMode(QtWidgets.QFileDialog.Directory)
    selected_dirs = []
    if dlg.exec():
        selected_dirs = dlg.selectedFiles()

    destination = selected_dirs[0]

    counter = 0

    # Go through and save each batchgroup to disk
    for batch in selection:
        if batch:
            batch_name = batch.name.get_value()
            batch_name = batch_name.replace(" ", "_")
            current_iteration = batch.current_iteration.name.get_value()
            current_iteration = current_iteration.replace(' ', '_')
            shot_path = os.path.join(destination, batch_name)
            iteration_path = os.path.join(shot_path, current_iteration)

            if not os.path.isdir(shot_path):
                os.mkdir(shot_path)

            batch.open()
            batch.save_setup(iteration_path)

            print (f"\nBatch:      {batch_name}")
            print (f"Saved to:   {iteration_path}")

            # Close the previous batch to keep things tiddy
            if counter > 0:
                if prev_batch:
                    try:
                        prev_batch.close()
                        print (f"Closing:  {prev_batch.name.get_value()}")
                    except:
                        print (f"Last batchgroup, can't close {batch_name}")

            counter += 1
            prev_batch = batch


def scope_batch(selection):
    import flame
    for item in selection:
        if isinstance(item, flame.PyBatch) and isinstance(item.parent, flame.PyDesktop):
            return True
    return False

def get_media_panel_custom_ui_actions():
    return [
        {
            "name": "Archiving Prep",
            "actions": [
                {
                    "name": "Save batchgroup to ...",
                    "order": 1,
                    "isVisible": scope_batch,
                    "minimumVersion": "2023.2.0.0",
                    "execute": save_batch
                }
           ]
        }
    ]