import os
import winreg

from .models import StartupEntry, StartupSource
from . import registry


def _get_startup_folder(common: bool) -> str:
    """Get the startup folder path."""
    if common:
        # shell:common startup
        try:
            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders"
            ) as key:
                return winreg.QueryValueEx(key, "Common Startup")[0]
        except OSError:
            return ""
    else:
        # shell:startup
        return os.path.join(
            os.environ.get("APPDATA", ""),
            r"Microsoft\Windows\Start Menu\Programs\Startup"
        )


def _resolve_shortcut(lnk_path: str) -> tuple[str, str]:
    """Resolve a .lnk shortcut to (target_path, arguments) using COM."""
    try:
        import win32com.client
        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortcut(lnk_path)
        target = shortcut.TargetPath or ""
        arguments = shortcut.Arguments or ""
        return target, arguments
    except Exception:
        return "", ""


def get_folder_entries(common: bool) -> list[StartupEntry]:
    """Enumerate startup entries from a startup folder."""
    entries = []
    folder = _get_startup_folder(common)
    source = StartupSource.COMMON_STARTUP_FOLDER if common else StartupSource.USER_STARTUP_FOLDER

    if not folder or not os.path.isdir(folder):
        return entries

    for filename in os.listdir(folder):
        filepath = os.path.join(folder, filename)
        if not os.path.isfile(filepath):
            continue

        name = os.path.splitext(filename)[0]
        ext = os.path.splitext(filename)[1].lower()

        if ext == ".lnk":
            exe_path, arguments = _resolve_shortcut(filepath)
            if not exe_path:
                continue
            shortcut = filepath
        elif ext == ".exe":
            exe_path = filepath
            arguments = ""
            shortcut = ""
        elif ext in (".bat", ".cmd", ".vbs", ".ps1"):
            exe_path = filepath
            arguments = ""
            shortcut = ""
        else:
            continue

        entries.append(StartupEntry(
            name=name,
            command=f'"{exe_path}" {arguments}'.strip(),
            executable_path=exe_path,
            arguments=arguments,
            source=source,
            requires_admin=common,
            shortcut_path=shortcut,
        ))

    return entries


def suppress_entry(entry: StartupEntry):
    """Suppress a startup folder entry via StartupApproved\\StartupFolder."""
    link_filename = _find_link_filename(entry)
    hive = (winreg.HKEY_LOCAL_MACHINE
            if entry.source == StartupSource.COMMON_STARTUP_FOLDER
            else winreg.HKEY_CURRENT_USER)
    registry.suppress_folder_entry(link_filename, hive)


def enable_entry(entry: StartupEntry):
    """Re-enable a startup folder entry."""
    link_filename = _find_link_filename(entry)
    hive = (winreg.HKEY_LOCAL_MACHINE
            if entry.source == StartupSource.COMMON_STARTUP_FOLDER
            else winreg.HKEY_CURRENT_USER)
    registry.enable_folder_entry(link_filename, hive)


def _find_link_filename(entry: StartupEntry) -> str:
    """Find the .lnk filename for a startup folder entry."""
    common = entry.source == StartupSource.COMMON_STARTUP_FOLDER
    folder = _get_startup_folder(common)

    if folder and os.path.isdir(folder):
        for filename in os.listdir(folder):
            if (os.path.splitext(filename)[0].lower() == entry.name.lower()
                    and filename.lower().endswith(".lnk")):
                return filename

    return entry.name + ".lnk"
