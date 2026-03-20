# Tag Tools
# Copyright (c) 2026 Kyle Obley
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.
#
# License:       GNU General Public License v3.0 (GPL-3.0)
#                https://www.gnu.org/licenses/gpl-3.0.en.html

"""
Script Name:    Tag Tools
Script Version: v1.0
Flame Version:  2025.1
Written by:     Kyle Obley
Creation Date:  20.03.26
Update Date:    20.03.26

License:        GNU General Public License v3.0 (GPL-3.0) - see LICENSE file for details

Script Type:    Media Panel

Description:

    Removes all markers and audio on a sequence.

    The marker code is borrowed from Kieran Hanrahan's http://github.com/khanrahan/delete-all-markers

Menus:

    Flame Media Panel -> Right-click -> Edit Prep

To install:

    Copy script into /opt/Autodesk/shared/python/remove_audio_and_markers

Updates:

    v1.0 20.03.26
        - Initial release.
"""

# ==============================================================================
# [Imports]
# ==============================================================================

import flame

# ==============================================================================
# [Constants]
# ==============================================================================

SCRIPT_NAME    = 'Remove Audio & Markers'
SCRIPT_VERSION = 'v1.0.0'

# ==============================================================================
# [Marker Functions from http://github.com/khanrahan/delete-all-markers]
# ==============================================================================
def delete_sequence_markers(sequence):
    """Delete all timeline markers on the passed in sequence."""
    for marker in sequence.markers:
        flame.delete(marker)


def delete_segment_markers(sequence):
    """Delete all segment markers on the passed in sequence."""
    for version in sequence.versions:
        for track in version.tracks:
            for segment in track.segments:
                for segment_marker in segment.markers:
                    flame.delete(segment_marker)

# ==============================================================================
# [Audio Function]
# ==============================================================================

def delete_sequence_audio(sequence):
    """Delete all audio tracks in a sequence."""
    for track in sequence.audio_tracks:
        if track:
            flame.delete(track)

# ==============================================================================
# [Functions Called Via UI Actions]
# ==============================================================================

def remove_all(selection):
    for sequence in selection:
        delete_sequence_markers(sequence)
        delete_segment_markers(sequence)
        delete_sequence_audio(sequence)


# ==============================================================================
# [Scoping]
# ==============================================================================
def sequence_selected(selection):
    for item in selection:
        if isinstance(item, (flame.PySequence)):
            return True
    return False

# ==============================================================================
# [Flame Menus - Media Panel]
# ==============================================================================
def get_media_panel_custom_ui_actions():
    return [
        {
            "name": "Edit Prep",
            "actions": [
                {
                    "name": "Remove All Audio and Markers",
                    "isVisable": sequence_selected,
                    "isEnabled": sequence_selected,
                    "execute": remove_all
                }
            ]
        }
    ]