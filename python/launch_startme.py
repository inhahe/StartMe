"""Launcher script for StartMe. Used by the Run key at logon.

This script adds the parent directory to sys.path and then runs
the startme package, avoiding issues with 'python -m' not finding
the package when Windows launches from the Run key.
"""
import os
import sys
import traceback

# Add the directory containing this script to sys.path
script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

# Set up early logging in case the import fails
log_file = os.path.join(script_dir, "startme.log")
try:
    with open(log_file, "a") as f:
        f.write(f"\n{'='*60}\n")
        f.write(f"launch_startme.py starting\n")
        f.write(f"  script_dir: {script_dir}\n")
        f.write(f"  sys.executable: {sys.executable}\n")
        f.write(f"  sys.argv: {sys.argv}\n")
        f.write(f"  cwd: {os.getcwd()}\n")
        f.write(f"  sys.path[0]: {sys.path[0]}\n")
except Exception:
    pass

try:
    from startme.__main__ import main
    main()
except Exception:
    tb = traceback.format_exc()
    try:
        with open(log_file, "a") as f:
            f.write(f"CRASH: {tb}\n")
    except Exception:
        pass
    # Also try to show a messagebox
    try:
        import tkinter as tk
        import tkinter.messagebox as mb
        root = tk.Tk()
        root.withdraw()
        mb.showerror("StartMe", f"Launch failed:\n\n{tb}")
        root.destroy()
    except Exception:
        pass
    sys.exit(1)
