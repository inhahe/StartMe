import json
import os
from dataclasses import dataclass, field

SETTINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "settings.json")


@dataclass
class Settings:
    # Entries excluded from StartMe management (re-enabled in registry, start normally)
    excluded_entries: list[str] = field(default_factory=list)

    # Entries removed from startup entirely (stay suppressed even on --uninstall)
    removed_entries: list[str] = field(default_factory=list)

    # Blocked entries: suppressed on EVERY launch, even if the app re-adds itself
    # to the registry. Unlike removed_entries, these are actively re-suppressed.
    blocked_entries: list[str] = field(default_factory=list)

    # Custom launch order: list of entry keys in desired order.
    # Entries not in this list appear after ordered entries, in discovery order.
    entry_order: list[str] = field(default_factory=list)

    # Entries skipped for current session only (runtime-only, not saved)
    session_skipped: list[str] = field(default_factory=list)

    # Max columns: 0 = auto (fit to screen), or a fixed number
    max_columns: int = 0

    # Column width in pixels
    column_width: int = 340

    # Delay between launches in seconds (0 = no extra delay)
    launch_delay: float = 0.0

    # Auto-close window after all launches complete
    auto_close: bool = True

    # Auto-close delay in seconds
    auto_close_delay: float = 2.5

    # Overlay mode: True = borderless, topmost, no taskbar (original behavior)
    # False = normal window with title bar, taskbar entry, not topmost
    overlay_mode: bool = True

    def save(self):
        data = {
            "excluded_entries": self.excluded_entries,
            "removed_entries": self.removed_entries,
            "blocked_entries": self.blocked_entries,
            "entry_order": self.entry_order,
            "max_columns": self.max_columns,
            "column_width": self.column_width,
            "launch_delay": self.launch_delay,
            "auto_close": self.auto_close,
            "auto_close_delay": self.auto_close_delay,
            "overlay_mode": self.overlay_mode,
        }
        path = os.path.abspath(SETTINGS_FILE)
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    @classmethod
    def load(cls) -> "Settings":
        path = os.path.abspath(SETTINGS_FILE)
        if not os.path.isfile(path):
            return cls()
        try:
            with open(path) as f:
                data = json.load(f)
            return cls(
                excluded_entries=data.get("excluded_entries", []),
                removed_entries=data.get("removed_entries", []),
                blocked_entries=data.get("blocked_entries", []),
                entry_order=data.get("entry_order", []),
                max_columns=data.get("max_columns", 0),
                column_width=data.get("column_width", 340),
                launch_delay=data.get("launch_delay", 0.0),
                auto_close=data.get("auto_close", True),
                auto_close_delay=data.get("auto_close_delay", 2.5),
                overlay_mode=data.get("overlay_mode", True),
            )
        except (json.JSONDecodeError, OSError):
            return cls()

    def make_entry_key(self, name: str, source_label: str) -> str:
        """Create a unique key for identifying an entry across sessions."""
        return f"{source_label}::{name}"
