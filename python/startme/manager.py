import winreg

from .models import StartupEntry, StartupSource, LaunchStatus
from .settings import Settings
from . import registry, folders, launcher


class StartupManager:
    def __init__(self, settings: Settings | None = None):
        self.entries: list[StartupEntry] = []
        self.settings = settings or Settings.load()

    def enumerate_all(self):
        """Discover all startup entries from registry and folders."""
        all_entries: list[StartupEntry] = []
        all_entries.extend(registry.get_registry_entries(winreg.HKEY_CURRENT_USER))
        all_entries.extend(registry.get_registry_entries(winreg.HKEY_LOCAL_MACHINE))
        all_entries.extend(registry.get_registry_entries(winreg.HKEY_LOCAL_MACHINE, wow64=True))
        all_entries.extend(folders.get_folder_entries(common=False))
        all_entries.extend(folders.get_folder_entries(common=True))

        # Suppress blocked entries (even if they re-added themselves)
        for entry in all_entries:
            key = self._entry_key(entry)
            if key in self.settings.blocked_entries:
                if entry.source in (StartupSource.REGISTRY_HKCU, StartupSource.REGISTRY_HKLM):
                    registry.suppress_entry(entry)
                else:
                    folders.suppress_entry(entry)

        # Filter out excluded, removed, and blocked entries
        self.entries = [
            e for e in all_entries
            if self._entry_key(e) not in self.settings.excluded_entries
            and self._entry_key(e) not in self.settings.removed_entries
            and self._entry_key(e) not in self.settings.blocked_entries
        ]

        # Apply custom ordering
        self._apply_order()

    def _apply_order(self):
        """Sort entries according to saved entry_order."""
        if not self.settings.entry_order:
            return
        order_map = {key: i for i, key in enumerate(self.settings.entry_order)}
        default_pos = len(self.settings.entry_order)
        self.entries.sort(key=lambda e: order_map.get(self._entry_key(e), default_pos))

    def save_current_order(self):
        """Save the current entry list order to settings."""
        self.settings.entry_order = [self._entry_key(e) for e in self.entries]
        self.settings.save()

    def move_entry(self, entry: StartupEntry, direction: int):
        """Move an entry up (-1) or down (+1) in the list. Returns new index or None."""
        try:
            idx = self.entries.index(entry)
        except ValueError:
            return None
        new_idx = idx + direction
        if new_idx < 0 or new_idx >= len(self.entries):
            return None
        self.entries[idx], self.entries[new_idx] = self.entries[new_idx], self.entries[idx]
        self.save_current_order()
        return new_idx

    def suppress_all(self):
        """Suppress all entries. Failures are silently ignored."""
        for entry in self.entries:
            if entry.source in (StartupSource.REGISTRY_HKCU, StartupSource.REGISTRY_HKLM):
                registry.suppress_entry(entry)
            else:
                folders.suppress_entry(entry)

    def enable_all(self):
        """Re-enable all entries (except removed and blocked)."""
        for entry in self.entries:
            key = self._entry_key(entry)
            if key in self.settings.removed_entries:
                continue
            if key in self.settings.blocked_entries:
                continue
            if entry.source in (StartupSource.REGISTRY_HKCU, StartupSource.REGISTRY_HKLM):
                registry.enable_entry(entry)
            else:
                folders.enable_entry(entry)

    def launch_next(self, index: int) -> bool:
        """Launch a single entry by index. Returns True if there are more entries."""
        if index >= len(self.entries):
            return False

        entry = self.entries[index]

        # Check if skipped for this session
        if self._entry_key(entry) in self.settings.session_skipped:
            entry.set_status(LaunchStatus.SKIPPED, error="Skipped for this session")
            return index + 1 < len(self.entries)

        entry.set_status(LaunchStatus.LAUNCHING)

        try:
            error = launcher.launch(entry)
            if error is None:
                entry.set_status(LaunchStatus.LAUNCHED)
            else:
                entry.set_status(LaunchStatus.FAILED, error=error)
        except Exception as ex:
            entry.set_status(LaunchStatus.FAILED, error=str(ex))

        return index + 1 < len(self.entries)

    def skip_session(self, entry: StartupEntry):
        """Skip an entry for this session only."""
        key = self._entry_key(entry)
        if key not in self.settings.session_skipped:
            self.settings.session_skipped.append(key)
        if entry.status == LaunchStatus.PENDING:
            entry.set_status(LaunchStatus.SKIPPED, error="Skipped for this session")

    def exclude_entry(self, entry: StartupEntry):
        """Remove entry from StartMe's management. Re-enables it in registry."""
        key = self._entry_key(entry)
        if key not in self.settings.excluded_entries:
            self.settings.excluded_entries.append(key)
            self.settings.save()
        # Re-enable so it starts normally via Windows
        if entry.source in (StartupSource.REGISTRY_HKCU, StartupSource.REGISTRY_HKLM):
            registry.enable_entry(entry)
        else:
            folders.enable_entry(entry)

    def remove_entry(self, entry: StartupEntry):
        """Remove entry from startup entirely. Stays suppressed even on --uninstall."""
        key = self._entry_key(entry)
        if key not in self.settings.removed_entries:
            self.settings.removed_entries.append(key)
            self.settings.save()
        # Keep it suppressed
        if entry.source in (StartupSource.REGISTRY_HKCU, StartupSource.REGISTRY_HKLM):
            registry.suppress_entry(entry)
        else:
            folders.suppress_entry(entry)

    def block_entry(self, entry: StartupEntry):
        """Block an entry permanently. Re-suppressed on every launch even if re-added."""
        key = self._entry_key(entry)
        if key not in self.settings.blocked_entries:
            self.settings.blocked_entries.append(key)
            self.settings.save()
        # Suppress now
        if entry.source in (StartupSource.REGISTRY_HKCU, StartupSource.REGISTRY_HKLM):
            registry.suppress_entry(entry)
        else:
            folders.suppress_entry(entry)

    def unblock_entry_by_key(self, key: str):
        """Unblock a previously blocked entry by its key."""
        if key in self.settings.blocked_entries:
            self.settings.blocked_entries.remove(key)
            self.settings.save()

    def _entry_key(self, entry: StartupEntry) -> str:
        return self.settings.make_entry_key(entry.name, entry.source_label)
