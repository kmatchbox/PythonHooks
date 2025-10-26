# Collect Media

The script will go through all the non-shared libraries within the **current workspace** and scrape everything to find clips. This includes folders, reels, reel groups, batches and desktops. All founds sources are added to a file. At the end you can use this file to run rsync to copy everything to a backup location of your choice. The original folder structure is kept. There is an option to grab only uncached media or everything (so cached and uncached)

### Important To Know
- Unable to get anything that is inside a BFX so all clips that have one applied will not be picked up. Upvote [FI-02664](https://feedback.autodesk.com/project/feedback/view.html?cap=5afe6c845cb3447ab36ccbd7f0688f84&uf=0d2c2e67dcab48f7a08c87b58ce5debd&slsid=fcf9f70a2b6f432a8aa27217113ec8f1) to allow that.
- Only grabs the used version of a versioned clip, not every version available.
- Only works on the current workspace.
- Flame returns the path of an image sequence as the first frame in the sequence, not the first frame being used within said image sequence. For now the safest route is to find the last frame in the sequence on disk and use that to populate the list.
- A backup of collect_media.txt is created on every run in case you need to roll-back.

### Who This Is Not Right For:
Someone who uses BFX.

**Workaround:** Have a reference to the original clip either in the timeline or someone within a library.

## Version 1.0 Changes (October 2025)

**New Output Location:** `~/collect_media/{project_name}/{YYYYMMDD}/`

### What Changed
- Output moved from `/opt/Autodesk/project/` to user's home directory
- Automatic directory creation
- Organized by project and date
- Fixes FileNotFoundError and permission issues

### Migration
The output location has changed. Update your rsync scripts:
- Old: `/opt/Autodesk/project/{project}/status/collected_media.txt`
- New: `~/collect_media/{project}/{YYYYMMDD}/collected_media.txt`

### How To Use:
1. Main menu > Collect Media

## Summary
Fixes FileNotFoundError by moving output from `/opt/Autodesk/project/` to `~/collect_media/{project}/{YYYYMMDD}/`

