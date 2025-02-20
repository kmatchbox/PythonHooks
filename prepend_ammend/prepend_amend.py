"""
Script Name: Prepend & Amend
Script Version: 0.3
Flame Version: 2021
Author: Kyle Obley (info@kyleobley.com)

Creation date: 05.07.23
Modified date: 08.08.24

Description:

    Amend or prepend to a clip name

Change Log:

    v0.3: PySide6 code wasn't implemented correctly.

    v0.2: Added PySide6 code for Flame 2025+

    v0.1: Initial Release

"""

class prepend_amend(object):

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
        self.window.setWindowTitle('Prepend / Amend')
        self.window.setStyleSheet('background: #202020')
        self.window.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint)
        self.window.setAttribute(QtCore.Qt.WA_DeleteOnClose)

        self.window.move((resolution.width() / 2) - (self.window.frameSize().width() / 2),
                         (resolution.height() / 2) - (self.window.frameSize().height() / 2))

        # Labels
        self.prepend_label = QtWidgets.QLabel('Prepend:', self.window)
        self.amend_label = QtWidgets.QLabel('Amend:', self.window)

        # Entries
        self.prepend_entry = QtWidgets.QLineEdit(self.window)
        self.prepend_entry.setMinimumSize(QtCore.QSize(100, 26))
        self.prepend_entry.setStyleSheet('background: #373e47')
        self.amend_entry = QtWidgets.QLineEdit(self.window)
        self.amend_entry.setMinimumSize(QtCore.QSize(100, 26))
        self.amend_entry.setStyleSheet('background: #373e47')

        # Buttons
        self.search_btn = QtWidgets.QPushButton('Rename', self.window)
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

        gridbox01.addWidget(self.prepend_label, 0, 0)
        gridbox01.addWidget(self.prepend_entry, 0, 1)
        gridbox01.addWidget(self.amend_label, 1, 0)
        gridbox01.addWidget(self.amend_entry, 1, 1)

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

        self.window.close()

        prepend_string = self.prepend_entry.text()
        amend_string = self.amend_entry.text()

        for item in clips:

            currentClip = str(item.name.get_value())

            newClipName = prepend_string + currentClip + amend_string
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
                    "name": "Prepend / Amend",
                    "isVisable": clip_selected,
                    "isEnabled": clip_selected,
                    "execute": prepend_amend
                }
            ]
        }
    ]