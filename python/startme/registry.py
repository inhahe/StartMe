import os
import struct
import time
import winreg
from datetime import datetime, timezone

from .models import StartupEntry, StartupSource

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_KEY_WOW64 = r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Run"
APPROVED_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run"
APPROVED_RUN_KEY_WOW64 = r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run32"
APPROVED_FOLDER_KEY = r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\StartupFolder"

# Map source to registry hive
_HIVE_MAP = {
    StartupSource.REGISTRY_HKCU: winreg.HKEY_CURRENT_USER,
    StartupSource.REGISTRY_HKLM: winreg.HKEY_LOCAL_MACHINE,
    StartupSource.USER_STARTUP_FOLDER: winreg.HKEY_CURRENT_USER,
    StartupSource.COMMON_STARTUP_FOLDER: winreg.HKEY_LOCAL_MACHINE,
}


def get_registry_entries(hive_const: int, wow64: bool = False) -> list[StartupEntry]:
    """Read startup entries from a Run registry key."""
    entries = []
    is_hklm = hive_const == winreg.HKEY_LOCAL_MACHINE
    source = StartupSource.REGISTRY_HKLM if is_hklm else StartupSource.REGISTRY_HKCU
    key_path = RUN_KEY_WOW64 if wow64 else RUN_KEY

    try:
        with winreg.OpenKey(hive_const, key_path) as key:
            i = 0
            while True:
                try:
                    name, value, _ = winreg.EnumValue(key, i)
                    i += 1
                    if not value:
                        continue
                    # Skip our own entry — we don't want to suppress ourselves
                    if name == "StartMe":
                        continue
                    exe_path, arguments = parse_command(str(value))
                    entries.append(StartupEntry(
                        name=name,
                        command=str(value),
                        executable_path=exe_path,
                        arguments=arguments,
                        source=source,
                        requires_admin=is_hklm,
                        is_wow64=wow64,
                    ))
                except OSError:
                    break
    except OSError:
        pass
    except PermissionError:
        pass

    return entries


def suppress_entry(entry: StartupEntry):
    """Disable a registry Run entry via StartupApproved."""
    approved_key = APPROVED_RUN_KEY_WOW64 if entry.is_wow64 else APPROVED_RUN_KEY
    _write_approved(entry.name, approved_key, _HIVE_MAP[entry.source], disabled=True)


def enable_entry(entry: StartupEntry):
    """Re-enable a registry Run entry via StartupApproved."""
    approved_key = APPROVED_RUN_KEY_WOW64 if entry.is_wow64 else APPROVED_RUN_KEY
    _write_approved(entry.name, approved_key, _HIVE_MAP[entry.source], disabled=False)


def suppress_folder_entry(link_filename: str, hive_const: int):
    """Disable a startup folder entry via StartupApproved."""
    _write_approved(link_filename, APPROVED_FOLDER_KEY, hive_const, disabled=True)


def enable_folder_entry(link_filename: str, hive_const: int):
    """Re-enable a startup folder entry via StartupApproved."""
    _write_approved(link_filename, APPROVED_FOLDER_KEY, hive_const, disabled=False)


def _write_approved(value_name: str, key_path: str, hive_const: int, disabled: bool):
    """Write a 12-byte StartupApproved value."""
    try:
        with winreg.CreateKey(hive_const, key_path) as key:
            data = _build_approved_bytes(disabled)
            winreg.SetValueEx(key, value_name, 0, winreg.REG_BINARY, data)
    except (PermissionError, OSError):
        pass


def _build_approved_bytes(disabled: bool) -> bytes:
    """Build the 12-byte StartupApproved binary value."""
    flag = 0x03 if disabled else 0x02
    if disabled:
        # FILETIME: 100-nanosecond intervals since 1601-01-01
        # Python's time.time() is seconds since 1970-01-01
        # Offset between 1601 and 1970 in 100-ns intervals
        EPOCH_DIFF = 116444736000000000
        ft = int(time.time() * 10_000_000) + EPOCH_DIFF
        return struct.pack("<I", flag) + struct.pack("<Q", ft)
    else:
        return struct.pack("<I", flag) + b"\x00" * 8


def parse_command(command: str) -> tuple[str, str]:
    """Parse a command string into (executable_path, arguments)."""
    command = os.path.expandvars(command.strip())

    if command.startswith('"'):
        end_quote = command.find('"', 1)
        if end_quote > 0:
            exe = command[1:end_quote]
            args = command[end_quote + 1:].strip()
            return exe, args

    # If the whole thing is a valid file path, return it directly
    if os.path.isfile(command):
        return command, ""

    # No quotes — try progressively longer substrings up to each space
    space_idx = command.find(" ")
    if space_idx < 0:
        return command, ""

    idx = space_idx
    while 0 <= idx < len(command):
        candidate = command[:idx]
        if os.path.isfile(candidate) or os.path.isfile(candidate + ".exe"):
            return candidate, command[idx + 1:].strip()
        idx = command.find(" ", idx + 1)
        idx = command.find(" ", idx + 1)

    # Fallback: split on first space
    return command[:space_idx], command[space_idx + 1:].strip()
