# BLG / Neat Video Workflow

Creating either workflow is a bit time consuming finding the various nodes, connecting them, etc. with consistent naming.

### Important:
The fx_setups folder needs to be kept along side this hook.

### How To Use:
1. In batch, select a source clip
2. Right-click > BLG / Neat Video
3. Select either option

### What It Does (BLG):
1. Creates and attaches the BLG plugin to the source clip.
2. Adds a color management node after that sets the tag as rec 709.
3. Add a render node with `_Grd_v` to account for different grade versions.
4. Resulting clip will be put into a `graded_renders` shelf.

### What It Does (Neat):
1. Creates and attaches the Neat Video plugin to the source clip.
2. Adds a color management node after that sets the tag as 16-bit.
3. Add a render node with source clip name and `_dn` at the end.
4. Resulting clip will be put into a `pre_renders` reel which brings it back in to the batchgroup automatically.