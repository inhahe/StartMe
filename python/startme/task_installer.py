import os
import sys
import winreg

TASK_NAME = "StartMe"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def _get_launch_command() -> str:
    """Build the command to launch StartMe.

    Uses launch_startme.py which adds its own directory to sys.path,
    avoiding issues with 'python -m' not finding the package when
    Windows launches from the Run key at logon.
    """
    python = sys.executable
    if python.endswith("pythonw.exe"):
        python = python.replace("pythonw.exe", "python.exe")
    package_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(package_dir)
    launcher = os.path.join(parent_dir, "launch_startme.py")
    return f'"{python}" "{launcher}" --launch'


def install() -> bool:
    """Register StartMe to run at logon via the current user's Run key.

    Uses HKCU\\...\\Run (no admin required) with a dedicated value name
    so it doesn't collide with the apps we manage. StartMe suppresses
    all *other* Run entries via StartupApproved but leaves its own alone.
    """
    try:
        cmd = _get_launch_command()
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            winreg.SetValueEx(key, TASK_NAME, 0, winreg.REG_SZ, cmd)
        return True
    except OSError:
        return False


def is_installed() -> bool:
    """Check if StartMe is registered to run at logon."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            winreg.QueryValueEx(key, TASK_NAME)
            return True
    except FileNotFoundError:
        return False
    except OSError:
        return False


def uninstall() -> bool:
    """Remove StartMe from the Run key."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0,
                            winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, TASK_NAME)
        return True
    except FileNotFoundError:
        return True  # Already gone
    except OSError:
        return False
