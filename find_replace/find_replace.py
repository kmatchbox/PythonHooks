"""
Script Name: Find and Replace
Script Version: 0.4
Flame Version: 2019
Author: Kyle Obley (info@kyleobley.com)

Creation date: 04.01.21
Modified date: 08.08.24

Description:

    Finds a given string on any clip or sequence and replaces
    it with another string. If you leave the replace string
    blank, it will remove all instances of the search string.

    Useful for batch renaming sequences when versioning.

Change Log:

    v0.4: PySide6 code wasn't implemented correctly.

    v0.3: Added PySide6 code for Flame 2025+

    v0.2: Changed method of renaming so we no longer duplicate
          the clip but just set the name.

    v0.1: Initial Release

"""

class find_replace(object):

    def __init__(self, selection):
        self.main_window(selection)
        global clips
        clips = selection

    def main_window(self, selection):
        
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

        self.window = QtWidgets.QWidget()
        self.window.setMinimumSize(QtCore.QSize(300, 150))
        self.window.setMaximumSize(QtCore.QSize(300, 150))
        self.window.setWindowTitle('Find and Replace')
        self.window.setStyleSheet('background: #202020')
        self.window.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint)
        self.window.setAttribute(QtCore.Qt.WA_DeleteOnClose)

        self.window.move((resolution.width() / 2) - (self.window.frameSize().width() / 2),
                         (resolution.height() / 2) - (self.window.frameSize().height() / 2))

        # Labels
        self.find_label = QtWidgets.QLabel('Find:', self.window)
        self.replace_label = QtWidgets.QLabel('Replace:', self.window)

        # Entries
        self.find_entry = QtWidgets.QLineEdit(self.window)
        self.find_entry.setMinimumSize(QtCore.QSize(100, 26))
        self.find_entry.setStyleSheet('background: #373e47')
        self.replace_entry = QtWidgets.QLineEdit(self.window)
        self.replace_entry.setMinimumSize(QtCore.QSize(100, 26))
        self.replace_entry.setStyleSheet('background: #373e47')

        # Buttons
        self.search_btn = QtWidgets.QPushButton('Search', self.window)
        self.search_btn.setMinimumSize(QtCore.QSize(110, 26))
        self.search_btn.setMaximumSize(QtCore.QSize(110, 26))
        self.search_btn.setStyleSheet('background: #732020')
        self.search_btn.clicked.connect(self.fnr)

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

        gridbox01.addWidget(self.find_label, 0, 0)
        gridbox01.addWidget(self.find_entry, 0, 1)
        gridbox01.addWidget(self.replace_label, 1, 0)
        gridbox01.addWidget(self.replace_entry, 1, 1)

        hbox03 = QtWidgets.QHBoxLayout()
        hbox03.addWidget(self.cancel_btn)
        hbox03.addWidget(self.search_btn)

        vbox = QtWidgets.QVBoxLayout()
        vbox.setContentsMargins(10, 10, 10, 10)
        vbox.addLayout(gridbox01)
        vbox.addLayout(hbox03)

        self.window.setLayout(vbox)

        self.window.show()

    def cancel (self):
        self.window.close()

    def fnr (self):
        import flame
        import re

        self.window.close()

        # Do the actual work of matching the string and and replacing if found

        find_string = self.find_entry.text()
        replace_string = self.replace_entry.text()

        for item in clips:

            currentClip = str(item.name)
            
            if currentClip.__contains__(find_string):
                newClipName = currentClip.replace(find_string, replace_string).strip("'")

                item.name.set_value(newClipName)
                
    

def clip_selected(selection):
    import flame
    for item in selection:
        if isinstance(item, (flame.PySequence, flame.PyClip)):
            return True
    return False

def get_media_panel_custom_ui_actions():
    return [
        {
            "name": "Renaming Tools",
            "actions": [
                {
                    "name": "Find and Replace",
                    "isVisable": clip_selected,
                    "isEnabled": clip_selected,
                    "execute": find_replace
                }
            ]
        }
    ]