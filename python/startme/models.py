from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Callable


class LaunchStatus(Enum):
    PENDING = auto()
    LAUNCHING = auto()
    LAUNCHED = auto()
    FAILED = auto()
    SKIPPED = auto()


class StartupSource(Enum):
    REGISTRY_HKCU = auto()
    REGISTRY_HKLM = auto()
    USER_STARTUP_FOLDER = auto()
    COMMON_STARTUP_FOLDER = auto()


@dataclass
class StartupEntry:
    name: str = ""
    command: str = ""
    executable_path: str = ""
    arguments: str = ""
    source: StartupSource = StartupSource.REGISTRY_HKCU
    requires_admin: bool = False
    is_wow64: bool = False
    shortcut_path: str = ""  # Full path to .lnk file (startup folder entries only)
    status: LaunchStatus = LaunchStatus.PENDING
    error_message: str = ""
    _on_status_changed: Callable | None = field(default=None, repr=False)

    def set_status(self, new_status: LaunchStatus, error: str = ""):
        self.status = new_status
        self.error_message = error
        if self._on_status_changed:
            self._on_status_changed(self)

    @property
    def source_label(self) -> str:
        return {
            StartupSource.REGISTRY_HKCU: "Registry",
            StartupSource.REGISTRY_HKLM: "Registry (Machine)",
            StartupSource.USER_STARTUP_FOLDER: "Startup Folder",
            StartupSource.COMMON_STARTUP_FOLDER: "Common Startup Folder",
        }.get(self.source, "Unknown")
