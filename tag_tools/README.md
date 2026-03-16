# Tag Tools

A collection of tools to easily set and use tags to keep track of the internal name, client name and audio files used within a sequence. The idea being our name is never the same as what the client wants. By leveraging the open nature of tags, we can now attach these values to a sequnce as well as injecting it into the QuickTime's `com.apple.quicktime.comment` metadata track. This allows us to be able to track back what sequence was used to create the file as well as which audio files were used.

The tags used are the following: internal_name, client_name and audio.

## How To Use ##

All operations require that all the sequnces/files you want to modify are selected.

### Setting  Tags ###
**Tagging Tools > Set/Get > Current Name → Internal Name**

Set the current sequence name as the internal name.

**Tagging Tools > Set/Get > Current Name → Client Name**

Set the current sequence name as the client name.

**Tagging Tools > Set/Get > Current Name → Both (Split internal__client)**

Set both tags at once. The script assumes that you have a double underscore separating the internal and client names. Eg. `xxx_30_wip01__ABC_1000_030`.

**Tagging Tools > Set/Get > Current Audio → Audio**

Sets an audio tag that lists every audio file used within the sequence. Currently this is only the basename and not the full path.

**Tagging Tools > Set/Get > Get tags from QuickTime**

Get all metadata in `com.apple.quicktime.comment` and set them as tags. This only works for QTs that have been brought into Flame. The idea being that it will be useful when one needs to track the original name of a file back.

### Renaming Tools ###
**Tagging Tools > Rename Clip From Tag > Internal Name / Client Name**

Rename the selected sequence(s) on either the desktop or within the Media Hub to the choosen option. This allows you to easily rename the sequences to/from each other.

### Exporting QuickTimes with Tags ###
**Tagging Tools > Export Sequences With Tags > Open Export Window**

This is a custom export wrapper to be able to inject the tags as metadata. You need to select the destination path as well as the export profile to use.

The export profiles that are shown are pulled from the project & shared movie_file presets.

Currently this is hardcoded to export in the foreground despite the button implying otherwise. I haven't been able to get the backburner post action working yet which is needed to call our qt_metadata library and link the sequence with the exported QuickTime.

### CSV Support ###
**Tagging Tools > CSV Import/Export > Export**

Creates a CSV semi-populated CSV file of all the selected sequnces containing the internal name. Open the file in a spreadsheet editor and you can now copy/paste the client name from your delivery list. Export the file again as a CSV.

**Tagging Tools > CSV Import/Export > Import**

Imports the above CSV you've now added the client name to and matches the internal name to the name of the selected sequence(s) and then pairs that with the client name. This will only set the client_name tag.


### Misc ###
**Tagging Tools > Dump metadata to terminal**

Dumps the metadata of the selected QuickTimes within the Media Hub to the terminal. Useful for checking what metadata has been set.

### qt_metadata Library ###
This is the secret sauce and written with Claude. It allows you to modify metadata tracks within QuickTimes. It can be used as both a library within a Python script or on it's own. Read the documentation within the file itself for more information.

You could easily leverage this for your own uses and you're only limited by your imagination!