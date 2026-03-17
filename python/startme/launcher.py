import ctypes
import ctypes.wintypes
import os
import subprocess
import time

import psutil

from .models import StartupEntry, StartupSource

# Win32 API
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
shell32 = ctypes.windll.shell32

INPUT_IDLE_TIMEOUT_MS = 15_000
CPU_SETTLE_TIMEOUT_S = 30.0
CPU_POLL_INTERVAL_S = 0.5
CPU_THRESHOLD_PERCENT = 5.0
SETTLED_CHECKS_REQUIRED = 3


def launch(entry: StartupEntry) -> str | None:
    """Launch a startup entry and wait for it to settle.
    Returns None on success, or an error message string on failure.

    - Startup folder .lnk entries: launched via os.startfile() to preserve
      the shortcut's working directory, elevation flags, and other properties.
    - Registry entries: launched via subprocess with cwd set to the
      executable's directory (mimicking how Explorer launches them).
    """
    is_folder = entry.source in (
        StartupSource.USER_STARTUP_FOLDER,
        StartupSource.COMMON_STARTUP_FOLDER,
    )

    if is_folder and entry.shortcut_path:
        return _launch_shortcut(entry)
    else:
        return _launch_command(entry)


def _launch_shortcut(entry: StartupEntry) -> str | None:
    """Launch a .lnk shortcut by resolving its properties and launching
    the target directly with the correct working directory, elevation, etc."""
    cwd = None
    show_cmd = 1  # SW_SHOWNORMAL
    try:
        import win32com.client
        shell_obj = win32com.client.Dispatch("WScript.Shell")
        sc = shell_obj.CreateShortcut(entry.shortcut_path)
        if sc.WorkingDirectory:
            cwd = os.path.expandvars(sc.WorkingDirectory)
        show_cmd = sc.WindowStyle or 1
    except Exception:
        pass

    # If no working directory from shortcut, use the executable's directory
    if not cwd and entry.executable_path and os.path.isfile(entry.executable_path):
        cwd = os.path.dirname(entry.executable_path)

    try:
        # Launch the shortcut file itself via ShellExecute with explicit cwd
        # This preserves elevation flags from the shortcut
        ret = shell32.ShellExecuteW(
            None,                    # hwnd
            None,                    # operation (default = open)
            entry.shortcut_path,     # file (.lnk)
            None,                    # parameters
            cwd,                     # working directory
            show_cmd,                # show command
        )
        if ret <= 32:
            return f"ShellExecute failed (code {ret})"
    except OSError as ex:
        return f"OS error: {ex}"

    # os.startfile returns immediately; find the process by exe name
    # Wait a moment for it to appear
    time.sleep(1.5)

    pid = _find_process_by_exe(entry.executable_path)
    if pid:
        _wait_for_input_idle(pid)
        _wait_for_cpu_settle(pid)

    return None


def _launch_command(entry: StartupEntry) -> str | None:
    """Launch a registry Run command with the exe's directory as cwd."""
    # Set working directory to the executable's folder
    cwd = None
    if entry.executable_path and os.path.isfile(entry.executable_path):
        cwd = os.path.dirname(entry.executable_path)

    try:
        cmd = entry.command if entry.arguments else entry.executable_path
        proc = subprocess.Popen(
            cmd,
            shell=True,
            start_new_session=True,
            cwd=cwd,
        )
    except FileNotFoundError:
        return f"File not found: {entry.executable_path}"
    except PermissionError:
        return f"Access denied: {entry.executable_path}"
    except OSError as ex:
        return f"OS error: {ex}"
    except Exception as ex:
        return str(ex)

    pid = proc.pid

    # If process exits almost immediately (launcher/updater pattern)
    try:
        proc.wait(timeout=2.0)
        if proc.returncode != 0:
            return f"Exited with code {proc.returncode}"
        return None
    except subprocess.TimeoutExpired:
        pass

    # Phase 1: WaitForInputIdle for GUI apps
    try:
        _wait_for_input_idle(pid)
    except Exception:
        pass

    # Phase 2: Wait for CPU to settle
    _wait_for_cpu_settle(pid)

    return None


def _find_process_by_exe(exe_path: str) -> int | None:
    """Find a running process by its executable path."""
    if not exe_path:
        return None
    exe_name = os.path.basename(exe_path).lower()
    try:
        for proc in psutil.process_iter(["pid", "name", "exe"]):
            try:
                if proc.info["name"] and proc.info["name"].lower() == exe_name:
                    return proc.info["pid"]
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    except Exception:
        pass
    return None


def _wait_for_input_idle(pid: int):
    """Call Win32 WaitForInputIdle on the process."""
    PROCESS_QUERY_INFORMATION = 0x0400
    SYNCHRONIZE = 0x00100000

    handle = kernel32.OpenProcess(
        PROCESS_QUERY_INFORMATION | SYNCHRONIZE, False, pid
    )
    if not handle:
        return

    try:
        user32.WaitForInputIdle(handle, INPUT_IDLE_TIMEOUT_MS)
    finally:
        kernel32.CloseHandle(handle)


def _wait_for_cpu_settle(pid: int):
    """Wait until the process CPU usage drops below threshold."""
    try:
        ps_proc = psutil.Process(pid)
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return

    deadline = time.monotonic() + CPU_SETTLE_TIMEOUT_S
    settled_count = 0

    try:
        ps_proc.cpu_percent(interval=None)
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return

    while time.monotonic() < deadline and settled_count < SETTLED_CHECKS_REQUIRED:
        time.sleep(CPU_POLL_INTERVAL_S)

        try:
            if not ps_proc.is_running():
                return
            cpu = ps_proc.cpu_percent(interval=None)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return

        if cpu < CPU_THRESHOLD_PERCENT:
            settled_count += 1
        else:
            settled_count = 0
