# StartMe

A Windows startup manager that launches your startup programs sequentially instead of all at once, reducing the boot-time resource stampede.

StartMe suppresses your normal Windows startup entries using the same mechanism as Task Manager (the `StartupApproved` registry keys), then launches each program one at a time, waiting for each to finish initializing before starting the next.

## Features

- **Sequential launching** — Programs start one at a time with CPU idle detection, so each app finishes loading before the next begins
- **Multi-column UI** — Automatically arranges entries into columns based on screen size
- **Drag-and-drop reordering** — Drag entries to control launch order
- **Block persistent apps** — Some apps re-add themselves to startup every time they run. The block feature re-suppresses them on every boot
- **Per-session skip** — Right-click to skip an entry for this session only
- **Start now** — Right-click to launch any individual entry immediately
- **Error reporting** — Failed launches show the error message inline and on hover
- **Settings** — Configurable column width, launch delay, auto-close behavior, overlay/desktop mode
- **Overlay or desktop mode** — Run as a borderless always-on-top overlay, or as a normal desktop window with taskbar entry
- **UAC elevation** — Installs with admin to suppress HKLM and WOW64 startup entries

## Supported startup locations

- `HKCU\...\Run` — Current user registry entries
- `HKLM\...\Run` — Machine-wide registry entries
- `HKLM\...\WOW6432Node\...\Run` — 32-bit app registry entries on 64-bit Windows
- User Startup folder (`shell:startup`)
- Common Startup folder (`shell:common startup`)

Startup folder shortcuts (`.lnk`) are launched via `ShellExecuteW` with the shortcut's working directory preserved.

## Limitations

Apps that use these startup mechanisms are not detected by StartMe and need to be managed through their own settings:

- Windows services (e.g., NVIDIA Display Container)
- UWP/Store app startup tasks (e.g., WhatsApp, Phone Link)

Apps that require admin elevation will still launch, but Windows will show a UAC prompt instead of silently auto-elevating like it does during normal startup. If you prefer silent elevation for these apps, use **"Remove from StartMe"** in the right-click menu to let Windows handle them normally.

## Requirements

- Windows 10/11
- Python 3.12+
- `pywin32` and `psutil` packages

## Installation

```bash
cd python
pip install pywin32 psutil
python -m startme --install
```

The `--install` command:
1. Triggers a UAC prompt for admin access
2. Suppresses all startup entries via `StartupApproved` registry keys
3. Registers StartMe in `HKCU\...\Run` to launch at logon

## Usage

| Command | Description |
|---|---|
| `python -m startme` | Open the UI without launching anything (configure, reorder, block) |
| `python -m startme --launch` | Open the UI and launch all entries sequentially (used at logon) |
| `python -m startme --install` | Suppress startups and register for logon (with UAC elevation) |
| `python -m startme --uninstall` | Re-enable all startups and remove logon registration |

## Right-click menu

| Option | Effect |
|---|---|
| **Start now** | Launch this entry immediately |
| **Skip this session** | Don't launch this entry this time (resets next boot) |
| **Remove from StartMe** | Re-enable in registry, let Windows handle it normally |
| **Remove from startup entirely** | Keep suppressed even after `--uninstall` |
| **Block (even if re-added)** | Re-suppress on every boot, even if the app re-registers itself |

## Settings

Click the gear icon to configure:

- **Column width** — Width of each column in pixels
- **Max columns** — Set to 0 for auto (fits entries to screen height)
- **Delay between launches** — Extra wait time between each app
- **Auto-close** — Automatically close the window after all launches complete
- **Auto-close delay** — How long to wait before closing
- **Overlay mode** — Borderless always-on-top (on) or normal desktop window (off)

Settings are stored in `python/settings.json`.

## How it works

StartMe uses the `StartupApproved` registry keys — the same mechanism Windows Task Manager uses to disable startup entries. The original `Run` key entries are never modified.

| Registry path | Purpose |
|---|---|
| `...\StartupApproved\Run` | Controls `HKCU/HKLM Run` entries |
| `...\StartupApproved\Run32` | Controls `WOW6432Node Run` entries |
| `...\StartupApproved\StartupFolder` | Controls startup folder shortcuts |

Each value is 12 bytes: byte 0 is `0x02` (enabled) or `0x03` (disabled), bytes 4-11 are a FILETIME timestamp.

### Launch detection

StartMe detects when each program finishes initializing using:

1. **`WaitForInputIdle`** — Win32 API that waits until a GUI app's message loop is idle
2. **CPU settle detection** — Polls process CPU usage until it drops below threshold for 3 consecutive checks
3. **Quick-exit detection** — If a process exits within 2 seconds (launcher/updater pattern), moves on immediately

## Debug logging

Logs are written to `python/startme.log` with timestamps, covering startup, enumeration, suppression, and any errors.

## C# version

A WPF (.NET 8) implementation is also included under `src/StartMe/` but is less feature-complete than the Python version.

## Acknowledgments

Built with the help of [Claude Code](https://claude.ai/claude-code).

## License

MIT
