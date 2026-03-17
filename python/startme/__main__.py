import logging
import os
import sys
import traceback
import tkinter.messagebox as messagebox

from .manager import StartupManager
from . import task_installer
from .elevation import is_admin, relaunch_as_admin

# Set up file logging next to the package
_LOG_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_LOG_FILE = os.path.join(_LOG_DIR, "startme.log")

logging.basicConfig(
    filename=_LOG_FILE,
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("startme")


def _show_error(msg: str):
    """Show an error messagebox."""
    log.error(msg)
    import tkinter as tk
    root = tk.Tk()
    root.withdraw()
    messagebox.showerror("StartMe", msg)
    root.destroy()


def main():
    log.info("=" * 60)
    log.info(f"StartMe starting. argv={sys.argv}")
    log.info(f"  executable: {sys.executable}")
    log.info(f"  cwd: {os.getcwd()}")
    log.info(f"  is_admin: {is_admin()}")
    try:
        _main()
    except Exception:
        tb = traceback.format_exc()
        log.critical(f"Unhandled exception:\n{tb}")
        _show_error(f"StartMe crashed:\n\n{tb}")
        sys.exit(1)


def _main():
    args = [a.lower() for a in sys.argv[1:]]
    log.info(f"Parsed args: {args}")

    # Handle --dir flag (used by the Run key command to set working directory)
    for i, arg in enumerate(args):
        if arg == "--dir" and i + 1 < len(args):
            new_dir = sys.argv[i + 2]
            log.info(f"Changing directory to: {new_dir}")
            os.chdir(new_dir)
            break

    manager = StartupManager()

    if "--install" in args:
        # Elevate if not already admin
        if not is_admin():
            if relaunch_as_admin():
                sys.exit(0)  # Elevated process will handle it
            else:
                # User cancelled UAC — fall through to install without admin
                pass

        manager.enumerate_all()

        if not task_installer.install():
            import tkinter as tk
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror(
                "StartMe",
                "Failed to register startup entry."
            )
            root.destroy()
            sys.exit(1)

        manager.suppress_all()

        msg = (
            f"StartMe installed.\n"
            f"{len(manager.entries)} startup items will be managed.\n\n"
            f"Startup programs will launch sequentially on next logon."
        )

        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        messagebox.showinfo("StartMe", msg)
        root.destroy()
        sys.exit(0)

    elif "--uninstall" in args:
        # Elevate if not already admin
        if not is_admin():
            if relaunch_as_admin():
                sys.exit(0)
            else:
                pass  # Try without admin

        manager.enumerate_all()
        manager.enable_all()
        task_installer.uninstall()

        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        messagebox.showinfo(
            "StartMe",
            "StartMe uninstalled.\nAll startup items have been re-enabled."
        )
        root.destroy()
        sys.exit(0)

    else:
        auto_launch = "--launch" in args
        log.info(f"Launch mode: auto_launch={auto_launch}")

        manager.enumerate_all()
        log.info(f"Enumerated {len(manager.entries)} entries")

        if not manager.entries:
            log.info("No entries found")
            if auto_launch:
                sys.exit(0)
            pass

        if auto_launch:
            log.info("Suppressing all entries")
            manager.suppress_all()

        log.info("Creating UI window")
        from .ui import StartMeWindow
        window = StartMeWindow(manager, auto_launch=auto_launch)
        log.info("Starting mainloop")
        window.run()
        log.info("Mainloop exited")


if __name__ == "__main__":
    main()
