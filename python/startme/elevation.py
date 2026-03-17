import ctypes
import os
import sys


def is_admin() -> bool:
    """Check if the current process has admin privileges."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def relaunch_as_admin(extra_args: list[str] | None = None) -> bool:
    """Re-launch the current script elevated via UAC prompt.
    Returns True if the elevated process was launched, False on failure/cancel."""
    python = sys.executable
    # Use pythonw.exe to avoid a console window flash
    pythonw = python.replace("python.exe", "pythonw.exe")
    if not os.path.isfile(pythonw):
        pythonw = python

    script_args = sys.argv[1:]
    if extra_args:
        script_args.extend(extra_args)

    # Pass --dir so the elevated process can find the package
    cwd = os.getcwd()
    params = f'-m startme --dir "{cwd}" {" ".join(script_args)}'

    # ShellExecuteW with "runas" triggers UAC
    ret = ctypes.windll.shell32.ShellExecuteW(
        None,       # hwnd
        "runas",    # operation
        pythonw,    # file (pythonw = no console)
        params,     # parameters
        cwd,        # working directory
        1,          # SW_SHOWNORMAL
    )

    # ShellExecuteW returns >32 on success
    return ret > 32
