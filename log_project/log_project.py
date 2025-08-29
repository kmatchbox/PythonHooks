"""
Script Name: Log Project
Script Version: 1.8
Flame Version: 2021

Creation date: 28.08.25
Modified date: 28.08.25

Description:

    Writes the project name to a log file every time the application is launched.

Change Log:

    v1.0: Inital release

"""

def appInitialized(project):
    import flame
    import os
    import socket


    log_base = "/SHVFX/archives/_nightly/logs"

    # Get full Flame version for arching purposes later
    # New log format = project:flame_ver
    # 0000_development:2025.2.2
        
    flame_ver = flame.get_version()
    log_text = project + ":" + flame_ver

    # Host name for logfile
    log_name = socket.gethostname() + ".log"

    f2 = os.path.join (log_base, log_name)

    try:
        open(f2, "a+").write(log_text + "\n")
    except:
        print(f"Error writting to log file: {f2}")
        pass