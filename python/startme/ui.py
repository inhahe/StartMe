import ctypes
import ctypes.wintypes
import math
import threading
import tkinter as tk

from .models import StartupEntry, LaunchStatus, StartupSource
from .manager import StartupManager
from .settings import Settings
from . import task_installer

# Colors
BG_COLOR = "#181820"
HEADER_COLOR = "#E0E0E0"
SUBTITLE_COLOR = "#666666"
ITEM_COLOR = "#D0D0D0"
SOURCE_COLOR = "#555555"
STATUS_BAR_BG = "#222230"
STATUS_COLOR = "#999999"
FAILED_BG = "#2A1518"
LAUNCHING_BG = "#252530"
BUTTON_BG = "#2A2A35"
BUTTON_FG = "#AAAAAA"
BUTTON_HOVER = "#3A3A48"
DIVIDER_COLOR = "#4488CC"
DRAG_DIM_FG = "#666666"

STATUS_COLORS = {
    LaunchStatus.PENDING: "#666666",
    LaunchStatus.LAUNCHING: "#1E90FF",
    LaunchStatus.LAUNCHED: "#32CD32",
    LaunchStatus.FAILED: "#FF4500",
    LaunchStatus.SKIPPED: "#444444",
}

# Enable DPI awareness for sharp rendering
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


class StartMeWindow:
    def __init__(self, manager: StartupManager, auto_launch: bool = False):
        self.manager = manager
        self.settings = manager.settings
        self.auto_launch = auto_launch
        self.dots: list[tk.Canvas] = []
        self.item_frames: list[tk.Frame] = []
        self.source_labels: list[tk.Label] = []
        self.error_labels: list[tk.Label] = []
        self._tooltip_window: tk.Toplevel | None = None
        self._launch_started = False
        self._column_frames: list[tk.Frame] = []
        self._canvases: list[tk.Canvas] = []
        self._item_col_idx: list[int] = []  # which column each item is in

        # Drag state
        self._drag_entry_idx: int | None = None
        self._drag_insert_idx: int | None = None
        self._divider: tk.Toplevel | None = None

        self.root = tk.Tk()
        self.root.title("StartMe")
        self.root.configure(bg=BG_COLOR)

        if self.settings.overlay_mode:
            self.root.overrideredirect(True)
            self.root.attributes("-topmost", True)
            self.root.attributes("-alpha", 0.92)
        else:
            # Normal desktop window — show on taskbar, not topmost
            self.root.attributes("-alpha", 0.95)

        self._update_geometry()
        self._build_ui()

        for entry in self.manager.entries:
            entry._on_status_changed = self._on_entry_status_changed

    def _update_geometry(self):
        rect = ctypes.wintypes.RECT()
        ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0)
        self._work_top = rect.top
        self._work_height = rect.bottom - rect.top
        self._work_width = rect.right - rect.left

        col_width = self.settings.column_width
        item_height, header_footer = self._measure_sizes()
        item_height += 4
        header_footer += 20
        self._item_height = item_height
        available = self._work_height - header_footer
        items_per_col = max(1, int(available / item_height))

        n_entries = len(self.manager.entries)
        if self.settings.max_columns > 0:
            num_cols = self.settings.max_columns
        else:
            num_cols = max(1, math.ceil(n_entries / items_per_col))

        max_cols_by_width = max(1, (self._work_width - 40) // col_width)
        num_cols = min(num_cols, max_cols_by_width)

        self._num_columns = num_cols
        self._items_per_column = items_per_col
        width = col_width * num_cols + 40
        width = min(width, self._work_width)

        items_in_tallest = math.ceil(n_entries / num_cols) if num_cols > 0 else n_entries
        needed_height = items_in_tallest * item_height + header_footer
        height = min(needed_height, self._work_height)

        self.root.geometry(f"{width}x{height}+0+{self._work_top}")

    def _measure_sizes(self) -> tuple[int, int]:
        f = tk.Frame(self.root, bg=BG_COLOR, padx=8, pady=4)
        d = tk.Canvas(f, width=12, height=12, bg=BG_COLOR, highlightthickness=0)
        d.pack(side=tk.LEFT, padx=(0, 10), pady=2)
        tf = tk.Frame(f, bg=BG_COLOR)
        tf.pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Label(tf, text="X", font=("Segoe UI", 10), bg=BG_COLOR).pack(fill=tk.X)
        tk.Label(tf, text="X", font=("Segoe UI", 8), bg=BG_COLOR).pack(fill=tk.X)
        f.pack()
        self.root.update_idletasks()
        item_h = f.winfo_reqheight() + 2

        h1 = tk.Label(self.root, text="X", font=("Segoe UI", 18, "bold"), bg=BG_COLOR)
        h2 = tk.Label(self.root, text="X", font=("Segoe UI", 9), bg=BG_COLOR)
        sf = tk.Frame(self.root, bg=BG_COLOR, padx=12, pady=8)
        sl = tk.Label(sf, text="X", font=("Segoe UI", 10), bg=BG_COLOR)
        sl.pack()
        h1.pack(); h2.pack(); sf.pack()
        self.root.update_idletasks()
        padding = 24 + 4 + 12 + 14
        hf_h = h1.winfo_reqheight() + h2.winfo_reqheight() + sf.winfo_reqheight() + padding

        for w in (f, h1, h2, sf):
            w.destroy()
        return item_h, hf_h

    def _build_ui(self):
        container = tk.Frame(self.root, bg=BG_COLOR, padx=20, pady=12)
        container.pack(fill=tk.BOTH, expand=True)

        # Header — also the window drag handle in overlay mode
        header = tk.Frame(container, bg=BG_COLOR)
        header.pack(fill=tk.X, pady=(4, 0))

        title = tk.Label(
            header, text="StartMe", font=("Segoe UI", 18, "bold"),
            fg=HEADER_COLOR, bg=BG_COLOR, anchor="w"
        )
        title.pack(side=tk.LEFT)

        if self.settings.overlay_mode:
            for w in (header, title):
                w.bind("<Button-1>", self._start_window_drag)
                w.bind("<B1-Motion>", self._on_window_drag)

        btn_frame = tk.Frame(header, bg=BG_COLOR)
        btn_frame.pack(side=tk.RIGHT)

        # Settings and launch buttons always shown
        self._make_button(btn_frame, "\u2699", self._open_settings, "Settings").pack(side=tk.LEFT, padx=2)

        self._launch_btn = self._make_button(btn_frame, "\u25B6", self._manual_launch, "Launch all")
        if not self.auto_launch:
            self._launch_btn.pack(side=tk.LEFT, padx=2)
            self._launch_btn.configure(fg="#32CD32")

        # Minimize and close only in overlay mode (normal mode has title bar buttons)
        if self.settings.overlay_mode:
            self._make_button(btn_frame, "\u2500", self._minimize, "Minimize").pack(side=tk.LEFT, padx=2)
            self._make_button(btn_frame, "\u2715", self._close, "Close").pack(side=tk.LEFT, padx=2)

        subtitle = tk.Label(
            container, text="Sequential Startup Manager",
            font=("Segoe UI", 9), fg=SUBTITLE_COLOR, bg=BG_COLOR, anchor="w"
        )
        subtitle.pack(fill=tk.X, pady=(2, 10))

        if self.settings.overlay_mode:
            subtitle.bind("<Button-1>", self._start_window_drag)
            subtitle.bind("<B1-Motion>", self._on_window_drag)

        # Action bar (only in default/interactive mode)
        if not self.auto_launch:
            self._build_action_bar(container)

        # Multi-column items area
        self._columns_outer = tk.Frame(container, bg=BG_COLOR)
        self._columns_outer.pack(fill=tk.BOTH, expand=True)
        self._rebuild_columns()

        # Status bar
        status_frame = tk.Frame(container, bg=STATUS_BAR_BG, padx=12, pady=8)
        status_frame.pack(fill=tk.X, pady=(10, 4))

        self.status_label = tk.Label(
            status_frame, text="Preparing...", font=("Segoe UI", 10),
            fg=STATUS_COLOR, bg=STATUS_BAR_BG, anchor="w"
        )
        self.status_label.pack(fill=tk.X)

    def _build_action_bar(self, container):
        """Build the install/uninstall/launch action bar for interactive mode."""
        bar = tk.Frame(container, bg="#1E1E28", padx=12, pady=8)
        bar.pack(fill=tk.X, pady=(0, 10))

        installed = task_installer.is_installed()

        # Status indicator
        self._install_status = tk.Label(
            bar,
            text="\u2713 Installed \u2014 will run at logon" if installed
                 else "\u2717 Not installed \u2014 will not run at logon",
            font=("Segoe UI", 9),
            fg="#32CD32" if installed else "#FF6B6B",
            bg="#1E1E28", anchor="w"
        )
        self._install_status.pack(side=tk.LEFT)

        # Buttons (right-aligned)
        def make_action_btn(parent, text, command, fg_color=BUTTON_FG):
            btn = tk.Label(
                parent, text=text, font=("Segoe UI", 9),
                fg=fg_color, bg=BUTTON_BG, padx=10, pady=3, cursor="hand2"
            )
            btn.bind("<Button-1>", lambda e: command())
            btn.bind("<Enter>", lambda e: btn.configure(bg=BUTTON_HOVER))
            btn.bind("<Leave>", lambda e: btn.configure(bg=BUTTON_BG))
            return btn

        if installed:
            make_action_btn(bar, "Uninstall", self._do_uninstall, "#FF6B6B").pack(side=tk.RIGHT, padx=2)
        else:
            make_action_btn(bar, "Install", self._do_install, "#32CD32").pack(side=tk.RIGHT, padx=2)

    def _do_install(self):
        """Run install from the UI."""
        from .elevation import is_admin, relaunch_as_admin
        import subprocess

        # Need admin for HKLM suppression
        if not is_admin():
            if relaunch_as_admin(extra_args=["--install"]):
                # Elevated process will handle it; we stay open
                # Wait a moment then refresh the status
                self.root.after(3000, self._refresh_action_bar)
                return
            # User cancelled UAC — install without admin

        self.manager.enumerate_all()
        if not task_installer.install():
            self.status_label.config(text="Failed to register startup entry.")
            return
        self.manager.suppress_all()
        self.status_label.config(
            text=f"Installed! {len(self.manager.entries)} entries will be managed at next logon."
        )
        self._refresh_action_bar()

    def _do_uninstall(self):
        """Run uninstall from the UI."""
        from .elevation import is_admin, relaunch_as_admin

        if not is_admin():
            if relaunch_as_admin(extra_args=["--uninstall"]):
                self.root.after(3000, self._refresh_action_bar)
                return

        self.manager.enumerate_all()
        self.manager.enable_all()
        task_installer.uninstall()
        self.status_label.config(text="Uninstalled. All startup items re-enabled.")
        self._refresh_action_bar()

    def _refresh_action_bar(self):
        """Update the action bar to reflect current install status."""
        installed = task_installer.is_installed()
        if hasattr(self, "_install_status"):
            self._install_status.config(
                text="\u2713 Installed \u2014 will run at logon" if installed
                     else "\u2717 Not installed \u2014 will not run at logon",
                fg="#32CD32" if installed else "#FF6B6B",
            )
            # Rebuild the parent frame to update the button
            bar = self._install_status.master
            # Remove old buttons
            for w in bar.winfo_children():
                if w != self._install_status:
                    w.destroy()

            def make_action_btn(parent, text, command, fg_color=BUTTON_FG):
                btn = tk.Label(
                    parent, text=text, font=("Segoe UI", 9),
                    fg=fg_color, bg=BUTTON_BG, padx=10, pady=3, cursor="hand2"
                )
                btn.bind("<Button-1>", lambda e: command())
                btn.bind("<Enter>", lambda e: btn.configure(bg=BUTTON_HOVER))
                btn.bind("<Leave>", lambda e: btn.configure(bg=BUTTON_BG))
                return btn

            if installed:
                make_action_btn(bar, "Uninstall", self._do_uninstall, "#FF6B6B").pack(side=tk.RIGHT, padx=2)
            else:
                make_action_btn(bar, "Install", self._do_install, "#32CD32").pack(side=tk.RIGHT, padx=2)

    def _rebuild_columns(self):
        for w in self._columns_outer.winfo_children():
            w.destroy()
        self.dots.clear()
        self.item_frames.clear()
        self.source_labels.clear()
        self.error_labels.clear()
        self._column_frames.clear()
        self._canvases.clear()
        self._item_col_idx.clear()

        entries = self.manager.entries
        n = len(entries)
        cols = self._num_columns
        per_col = math.ceil(n / cols) if cols > 0 else n
        col_width = self.settings.column_width

        for col_idx in range(cols):
            self._columns_outer.columnconfigure(col_idx, weight=1, uniform="col")

            col_outer = tk.Frame(self._columns_outer, bg=BG_COLOR, width=col_width)
            col_outer.grid(row=0, column=col_idx, sticky="nsew",
                           padx=(0, 8 if col_idx < cols - 1 else 0))
            col_outer.grid_propagate(False)

            canvas = tk.Canvas(col_outer, bg=BG_COLOR, highlightthickness=0)
            col_frame = tk.Frame(canvas, bg=BG_COLOR)

            col_frame.bind(
                "<Configure>",
                lambda e, c=canvas: c.configure(scrollregion=c.bbox("all"))
            )
            canvas.create_window((0, 0), window=col_frame, anchor="nw", tags="inner")
            canvas.bind("<Configure>",
                        lambda e, c=canvas: c.itemconfigure("inner", width=e.width))

            canvas.pack(fill=tk.BOTH, expand=True)
            self._canvases.append(canvas)
            self._column_frames.append(col_frame)

            start = col_idx * per_col
            end = min(start + per_col, n)
            for i in range(start, end):
                self._add_item(col_frame, entries[i], i)
                self._item_col_idx.append(col_idx)

        self._columns_outer.rowconfigure(0, weight=1)

        def _on_mousewheel(event):
            for c in self._canvases:
                c.yview_scroll(int(-1 * (event.delta / 120)), "units")
        self.root.bind_all("<MouseWheel>", _on_mousewheel)

    def _make_button(self, parent, text, command, tooltip_text=""):
        btn = tk.Label(
            parent, text=text, font=("Segoe UI", 12),
            fg=BUTTON_FG, bg=BUTTON_BG, padx=8, pady=2, cursor="hand2"
        )
        btn.bind("<Button-1>", lambda e: command())
        if tooltip_text:
            btn.bind("<Enter>", lambda e, t=tooltip_text: (
                btn.configure(bg=BUTTON_HOVER),
                self._show_simple_tooltip(e, t)
            ))
            btn.bind("<Leave>", lambda e: (
                btn.configure(bg=BUTTON_BG),
                self._hide_tooltip()
            ))
        else:
            btn.bind("<Enter>", lambda e: btn.configure(bg=BUTTON_HOVER))
            btn.bind("<Leave>", lambda e: btn.configure(bg=BUTTON_BG))
        return btn

    def _add_item(self, parent, entry: StartupEntry, flat_idx: int):
        frame = tk.Frame(parent, bg=BG_COLOR, padx=8, pady=4)
        frame.pack(fill=tk.X, pady=1)

        # Status dot
        dot_canvas = tk.Canvas(
            frame, width=12, height=12, bg=BG_COLOR, highlightthickness=0
        )
        dot_canvas.pack(side=tk.LEFT, padx=(0, 10), pady=2)
        color = STATUS_COLORS[entry.status]
        dot_canvas.create_oval(2, 2, 10, 10, fill=color, outline="", tags="dot")

        # Text area
        text_frame = tk.Frame(frame, bg=BG_COLOR)
        text_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)

        tk.Label(
            text_frame, text=entry.name, font=("Segoe UI", 10),
            fg=ITEM_COLOR, bg=BG_COLOR, anchor="w"
        ).pack(fill=tk.X)

        source_label = tk.Label(
            text_frame, text=entry.source_label, font=("Segoe UI", 8),
            fg=SOURCE_COLOR, bg=BG_COLOR, anchor="w"
        )
        source_label.pack(fill=tk.X)

        error_label = tk.Label(
            text_frame, text="", font=("Segoe UI", 8),
            fg="#FF6B6B", bg=BG_COLOR, anchor="w", wraplength=260
        )

        # Right-click context menu
        menu = tk.Menu(self.root, tearoff=0, bg="#2A2A35", fg="#D0D0D0",
                       activebackground="#3A3A48", activeforeground="white",
                       font=("Segoe UI", 9))
        menu.add_command(label="\u25B6 Start now",
                         command=lambda e=entry: self._ctx_start_now(e))
        menu.add_separator()
        menu.add_command(label="Skip this session",
                         command=lambda e=entry: self._ctx_skip_session(e))
        menu.add_command(label="Remove from StartMe",
                         command=lambda e=entry: self._ctx_exclude(e))
        menu.add_command(label="Remove from startup entirely",
                         command=lambda e=entry: self._ctx_remove(e))
        menu.add_separator()
        menu.add_command(label="\u26D4 Block (even if re-added)",
                         command=lambda e=entry: self._ctx_block(e))

        # Bind drag and context menu to frame and all children
        self._bind_item_events(frame, menu, flat_idx)

        self.dots.append(dot_canvas)
        self.item_frames.append(frame)
        self.source_labels.append(source_label)
        self.error_labels.append(error_label)

    def _bind_item_events(self, widget, menu, flat_idx: int):
        """Bind drag-to-reorder and right-click menu to a widget and its children."""
        widget.bind("<Button-1>", lambda e, i=flat_idx: self._item_drag_start(e, i))
        widget.bind("<B1-Motion>", self._item_drag_motion)
        widget.bind("<ButtonRelease-1>", self._item_drag_end)
        widget.bind("<Button-3>", lambda e, m=menu: m.tk_popup(e.x_root, e.y_root))

        for child in widget.winfo_children():
            self._bind_item_events(child, menu, flat_idx)

    # -- Drag and drop reordering --

    def _ctx_start_now(self, entry: StartupEntry):
        """Launch a single entry immediately in a background thread."""
        idx = self._find_entry_index(entry)
        if idx is None:
            return
        if entry.status in (LaunchStatus.LAUNCHING, LaunchStatus.LAUNCHED):
            return  # Already launching or launched

        def _do_launch():
            entry.set_status(LaunchStatus.LAUNCHING)
            try:
                from . import launcher
                error = launcher.launch(entry)
                if error is None:
                    entry.set_status(LaunchStatus.LAUNCHED)
                else:
                    entry.set_status(LaunchStatus.FAILED, error=error)
            except Exception as ex:
                entry.set_status(LaunchStatus.FAILED, error=str(ex))

        import threading
        threading.Thread(target=_do_launch, daemon=True).start()

    def _item_drag_start(self, event, flat_idx: int):
        """Start dragging an item."""
        if self._launch_started:
            return
        self._drag_entry_idx = flat_idx
        self._drag_insert_idx = None
        # Dim the dragged item
        self._set_frame_bg(flat_idx, "#101018")
        frame = self.item_frames[flat_idx]
        for child in frame.winfo_children():
            if isinstance(child, tk.Label):
                child.configure(fg=DRAG_DIM_FG)
            if hasattr(child, "winfo_children"):
                for gc in child.winfo_children():
                    if isinstance(gc, tk.Label):
                        gc.configure(fg=DRAG_DIM_FG)

    def _item_drag_motion(self, event):
        """Update divider position as mouse moves."""
        if self._drag_entry_idx is None:
            return

        # Find which flat index the cursor is nearest to
        insert_idx = self._find_insert_index(event.x_root, event.y_root)

        if insert_idx == self._drag_insert_idx:
            return  # No change
        self._drag_insert_idx = insert_idx

        # Position the divider line
        self._show_divider(insert_idx)

    def _item_drag_end(self, event):
        """Drop the item at the current position."""
        if self._drag_entry_idx is None:
            return

        src = self._drag_entry_idx
        dst = self._drag_insert_idx
        self._drag_entry_idx = None
        self._drag_insert_idx = None
        self._hide_divider()

        if dst is None or dst == src or dst == src + 1:
            # No move needed — just rebuild to reset colors
            self._rebuild_columns()
            for e in self.manager.entries:
                e._on_status_changed = self._on_entry_status_changed
            return

        # Reorder: remove from src, insert at dst
        entries = self.manager.entries
        entry = entries.pop(src)
        # Adjust dst if it was after src
        if dst > src:
            dst -= 1
        entries.insert(dst, entry)
        self.manager.save_current_order()

        self._rebuild_columns()
        for e in self.manager.entries:
            e._on_status_changed = self._on_entry_status_changed

    def _find_insert_index(self, x_root: int, y_root: int) -> int:
        """Find the flat insertion index for a cursor position."""
        n = len(self.item_frames)
        if n == 0:
            return 0

        # Determine which column the cursor is over
        target_col = 0
        best_col_dist = float("inf")
        for ci, canvas in enumerate(self._canvases):
            try:
                cx = canvas.winfo_rootx()
                cw = canvas.winfo_width()
            except tk.TclError:
                continue
            # Check if x is within this column
            if cx <= x_root <= cx + cw:
                target_col = ci
                best_col_dist = 0
                break
            # Otherwise find nearest column
            dist = min(abs(x_root - cx), abs(x_root - (cx + cw)))
            if dist < best_col_dist:
                best_col_dist = dist
                target_col = ci

        # Get indices of items in the target column
        col_items = [i for i in range(n) if self._item_col_idx[i] == target_col]
        if not col_items:
            return 0

        # Find closest gap within this column
        best_idx = col_items[0]
        best_dist = float("inf")

        for i in col_items:
            frame = self.item_frames[i]
            try:
                fy = frame.winfo_rooty()
                fh = frame.winfo_height()
            except tk.TclError:
                continue

            # Top edge = insertion before this item
            dist_top = abs(y_root - fy)
            if dist_top < best_dist:
                best_dist = dist_top
                best_idx = i

            # Bottom edge = insertion after this item
            dist_bot = abs(y_root - (fy + fh))
            if dist_bot < best_dist:
                best_dist = dist_bot
                best_idx = i + 1

        return best_idx

    def _show_divider(self, insert_idx: int):
        """Show a horizontal divider line at the given insertion point."""
        self._hide_divider()

        if insert_idx is None:
            return

        n = len(self.item_frames)
        if n == 0:
            return

        # Figure out the y position and width for the divider
        if insert_idx < n:
            ref_frame = self.item_frames[insert_idx]
            try:
                y = ref_frame.winfo_rooty() - 2
                x = ref_frame.winfo_rootx()
                w = ref_frame.winfo_width()
            except tk.TclError:
                return
        elif n > 0:
            ref_frame = self.item_frames[n - 1]
            try:
                y = ref_frame.winfo_rooty() + ref_frame.winfo_height()
                x = ref_frame.winfo_rootx()
                w = ref_frame.winfo_width()
            except tk.TclError:
                return
        else:
            return

        self._divider = tk.Toplevel(self.root)
        self._divider.overrideredirect(True)
        self._divider.attributes("-topmost", True)
        self._divider.configure(bg=DIVIDER_COLOR)
        self._divider.geometry(f"{w}x3+{x}+{y}")
        # Make it click-through
        self._divider.attributes("-alpha", 0.9)

    def _hide_divider(self):
        if self._divider:
            self._divider.destroy()
            self._divider = None

    # -- Window dragging (header only) --

    def _start_window_drag(self, event):
        self._win_drag_x = event.x_root - self.root.winfo_x()
        self._win_drag_y = event.y_root - self.root.winfo_y()

    def _on_window_drag(self, event):
        x = event.x_root - self._win_drag_x
        y = event.y_root - self._win_drag_y
        self.root.geometry(f"+{x}+{y}")

    # -- Context menu actions --

    def _ctx_skip_session(self, entry: StartupEntry):
        self.manager.skip_session(entry)

    def _ctx_exclude(self, entry: StartupEntry):
        self.manager.exclude_entry(entry)
        idx = self._find_entry_index(entry)
        if idx is not None:
            self._strike_item(idx, "Removed from StartMe")

    def _ctx_remove(self, entry: StartupEntry):
        self.manager.remove_entry(entry)
        idx = self._find_entry_index(entry)
        if idx is not None:
            self._strike_item(idx, "Removed from startup")

    def _ctx_block(self, entry: StartupEntry):
        self.manager.block_entry(entry)
        idx = self._find_entry_index(entry)
        if idx is not None:
            self._strike_item(idx, "Blocked permanently")

    def _find_entry_index(self, entry: StartupEntry) -> int | None:
        try:
            return self.manager.entries.index(entry)
        except ValueError:
            return None

    def _strike_item(self, idx: int, label_text: str):
        frame = self.item_frames[idx]
        frame.configure(bg="#1A1A20")
        for child in frame.winfo_children():
            child.configure(bg="#1A1A20")
            if isinstance(child, tk.Label):
                child.configure(fg="#444444")
            if hasattr(child, "winfo_children"):
                for gc in child.winfo_children():
                    gc.configure(bg="#1A1A20")
                    if isinstance(gc, tk.Label):
                        gc.configure(fg="#444444")
        self.source_labels[idx].config(text=label_text, fg="#666633")
        dot = self.dots[idx]
        dot.delete("dot")
        dot.create_oval(2, 2, 10, 10, fill="#333333", outline="", tags="dot")

    # -- Close --

    def _close(self):
        self.root.destroy()

    # -- Minimize --

    def _minimize(self):
        self.root.withdraw()
        self._restore_btn = tk.Toplevel(self.root)
        self._restore_btn.overrideredirect(True)
        self._restore_btn.attributes("-topmost", True)
        self._restore_btn.attributes("-alpha", 0.85)
        self._restore_btn.configure(bg=BUTTON_BG)

        y = self._work_top + self._work_height // 2 - 20
        self._restore_btn.geometry(f"28x40+0+{y}")

        lbl = tk.Label(
            self._restore_btn, text="\u25B6", font=("Segoe UI", 14),
            fg=BUTTON_FG, bg=BUTTON_BG, cursor="hand2"
        )
        lbl.pack(fill=tk.BOTH, expand=True)
        lbl.bind("<Button-1>", lambda e: self._restore())
        lbl.bind("<Enter>", lambda e: lbl.configure(bg=BUTTON_HOVER))
        lbl.bind("<Leave>", lambda e: lbl.configure(bg=BUTTON_BG))

    def _restore(self):
        if hasattr(self, "_restore_btn") and self._restore_btn:
            self._restore_btn.destroy()
            self._restore_btn = None
        self.root.deiconify()

    # -- Settings dialog --

    def _open_settings(self):
        dlg = tk.Toplevel(self.root)
        dlg.title("StartMe Settings")
        dlg.transient(self.root)
        dlg.configure(bg=BG_COLOR)
        dlg.attributes("-topmost", True)
        dlg.geometry("420x460")
        dlg.resizable(False, False)

        pad = {"padx": 16, "pady": 4}

        tk.Label(dlg, text="Settings", font=("Segoe UI", 14, "bold"),
                 fg=HEADER_COLOR, bg=BG_COLOR).pack(anchor="w", padx=16, pady=(12, 8))

        row = tk.Frame(dlg, bg=BG_COLOR)
        row.pack(fill=tk.X, **pad)
        tk.Label(row, text="Column width (px):", fg=ITEM_COLOR, bg=BG_COLOR,
                 font=("Segoe UI", 10)).pack(side=tk.LEFT)
        col_width_var = tk.StringVar(value=str(self.settings.column_width))
        tk.Entry(row, textvariable=col_width_var, width=6, bg="#2A2A35", fg="white",
                 insertbackground="white", font=("Segoe UI", 10)).pack(side=tk.RIGHT)

        row = tk.Frame(dlg, bg=BG_COLOR)
        row.pack(fill=tk.X, **pad)
        tk.Label(row, text="Max columns (0 = auto):", fg=ITEM_COLOR, bg=BG_COLOR,
                 font=("Segoe UI", 10)).pack(side=tk.LEFT)
        max_cols_var = tk.StringVar(value=str(self.settings.max_columns))
        tk.Entry(row, textvariable=max_cols_var, width=6, bg="#2A2A35", fg="white",
                 insertbackground="white", font=("Segoe UI", 10)).pack(side=tk.RIGHT)

        row = tk.Frame(dlg, bg=BG_COLOR)
        row.pack(fill=tk.X, **pad)
        tk.Label(row, text="Delay between launches (sec):", fg=ITEM_COLOR, bg=BG_COLOR,
                 font=("Segoe UI", 10)).pack(side=tk.LEFT)
        delay_var = tk.StringVar(value=str(self.settings.launch_delay))
        tk.Entry(row, textvariable=delay_var, width=6, bg="#2A2A35", fg="white",
                 insertbackground="white", font=("Segoe UI", 10)).pack(side=tk.RIGHT)

        auto_close_var = tk.BooleanVar(value=self.settings.auto_close)
        row = tk.Frame(dlg, bg=BG_COLOR)
        row.pack(fill=tk.X, **pad)
        tk.Checkbutton(row, text="Auto-close when done", variable=auto_close_var,
                       fg=ITEM_COLOR, bg=BG_COLOR, selectcolor="#2A2A35",
                       activebackground=BG_COLOR, activeforeground=ITEM_COLOR,
                       font=("Segoe UI", 10)).pack(side=tk.LEFT)

        row = tk.Frame(dlg, bg=BG_COLOR)
        row.pack(fill=tk.X, **pad)
        tk.Label(row, text="Auto-close delay (sec):", fg=ITEM_COLOR, bg=BG_COLOR,
                 font=("Segoe UI", 10)).pack(side=tk.LEFT)
        close_delay_var = tk.StringVar(value=str(self.settings.auto_close_delay))
        tk.Entry(row, textvariable=close_delay_var, width=6, bg="#2A2A35", fg="white",
                 insertbackground="white", font=("Segoe UI", 10)).pack(side=tk.RIGHT)

        # Overlay mode
        overlay_var = tk.BooleanVar(value=self.settings.overlay_mode)
        row = tk.Frame(dlg, bg=BG_COLOR)
        row.pack(fill=tk.X, **pad)
        tk.Checkbutton(row, text="Overlay mode (borderless, always on top)",
                       variable=overlay_var,
                       fg=ITEM_COLOR, bg=BG_COLOR, selectcolor="#2A2A35",
                       activebackground=BG_COLOR, activeforeground=ITEM_COLOR,
                       font=("Segoe UI", 10)).pack(side=tk.LEFT)

        tk.Frame(dlg, bg="#333", height=1).pack(fill=tk.X, padx=16, pady=(12, 8))

        n_excl = len(self.settings.excluded_entries)
        n_rem = len(self.settings.removed_entries)
        n_blk = len(self.settings.blocked_entries)

        row = tk.Frame(dlg, bg=BG_COLOR)
        row.pack(fill=tk.X, padx=16, pady=2)
        tk.Label(row, text=f"Excluded: {n_excl}  |  Removed: {n_rem}  |  Blocked: {n_blk}",
                 fg=SOURCE_COLOR, bg=BG_COLOR, font=("Segoe UI", 9)).pack(side=tk.LEFT)

        if n_excl + n_rem > 0:
            btn = tk.Label(row, text="Reset excluded/removed", fg="#FF6B6B", bg=BG_COLOR,
                           font=("Segoe UI", 9, "underline"), cursor="hand2")
            btn.pack(side=tk.RIGHT)
            btn.bind("<Button-1>", lambda e: self._reset_exclusions(dlg))

        if n_blk > 0:
            tk.Label(dlg, text="Blocked entries:", fg=ITEM_COLOR, bg=BG_COLOR,
                     font=("Segoe UI", 10)).pack(anchor="w", padx=16, pady=(8, 2))

            blocked_frame = tk.Frame(dlg, bg="#1E1E28")
            blocked_frame.pack(fill=tk.X, padx=16, pady=2)

            for bkey in list(self.settings.blocked_entries):
                bf = tk.Frame(blocked_frame, bg="#1E1E28", padx=6, pady=3)
                bf.pack(fill=tk.X)
                display = bkey.split("::")[-1] if "::" in bkey else bkey
                tk.Label(bf, text=display, fg="#AA6666", bg="#1E1E28",
                         font=("Segoe UI", 9)).pack(side=tk.LEFT)
                ubtn = tk.Label(bf, text="Unblock", fg="#6688BB", bg="#1E1E28",
                                font=("Segoe UI", 8, "underline"), cursor="hand2")
                ubtn.pack(side=tk.RIGHT)
                ubtn.bind("<Button-1>", lambda e, k=bkey, d=dlg: self._unblock(k, d))

        btn_row = tk.Frame(dlg, bg=BG_COLOR)
        btn_row.pack(fill=tk.X, padx=16, pady=(16, 12))

        def save():
            try:
                self.settings.column_width = int(col_width_var.get())
                self.settings.max_columns = int(max_cols_var.get())
                self.settings.launch_delay = float(delay_var.get())
                self.settings.auto_close = auto_close_var.get()
                self.settings.auto_close_delay = float(close_delay_var.get())
                self.settings.overlay_mode = overlay_var.get()
                self.settings.save()
                dlg.destroy()
            except ValueError:
                pass

        save_btn = tk.Label(btn_row, text="  Save  ", font=("Segoe UI", 10),
                            fg="white", bg="#2860A0", padx=12, pady=4, cursor="hand2")
        save_btn.pack(side=tk.RIGHT, padx=4)
        save_btn.bind("<Button-1>", lambda e: save())

        cancel_btn = tk.Label(btn_row, text="  Cancel  ", font=("Segoe UI", 10),
                              fg=BUTTON_FG, bg=BUTTON_BG, padx=12, pady=4, cursor="hand2")
        cancel_btn.pack(side=tk.RIGHT, padx=4)
        cancel_btn.bind("<Button-1>", lambda e: dlg.destroy())

    def _reset_exclusions(self, dlg):
        self.settings.excluded_entries.clear()
        self.settings.removed_entries.clear()
        self.settings.save()
        dlg.destroy()
        self._open_settings()

    def _unblock(self, key: str, dlg):
        self.manager.unblock_entry_by_key(key)
        dlg.destroy()
        self._open_settings()

    # -- Status updates --

    def _on_entry_status_changed(self, entry: StartupEntry):
        self.root.after(0, self._update_entry_ui, entry)

    def _update_entry_ui(self, entry: StartupEntry):
        try:
            idx = self.manager.entries.index(entry)
        except ValueError:
            return

        color = STATUS_COLORS[entry.status]
        dot = self.dots[idx]
        dot.delete("dot")
        dot.create_oval(2, 2, 10, 10, fill=color, outline="", tags="dot")

        if entry.status == LaunchStatus.LAUNCHING:
            bg = LAUNCHING_BG
        elif entry.status == LaunchStatus.FAILED:
            bg = FAILED_BG
        else:
            bg = BG_COLOR

        self._set_frame_bg(idx, bg)

        if entry.status == LaunchStatus.FAILED and entry.error_message:
            self.error_labels[idx].config(text=entry.error_message, bg=bg)
            self.error_labels[idx].pack(fill=tk.X)
            self.source_labels[idx].pack_forget()
        elif entry.status == LaunchStatus.SKIPPED:
            self.source_labels[idx].config(
                text=entry.error_message or "Skipped"
            )

        done = sum(
            1 for e in self.manager.entries
            if e.status in (LaunchStatus.LAUNCHED, LaunchStatus.FAILED, LaunchStatus.SKIPPED)
        )
        launching = sum(1 for e in self.manager.entries if e.status == LaunchStatus.LAUNCHING)
        total = len(self.manager.entries)

        if launching > 0:
            self.status_label.config(text=f"Launching {done + 1} of {total}...")
        elif done == total:
            self.status_label.config(text="All done.")

    def _set_frame_bg(self, idx: int, bg: str):
        frame = self.item_frames[idx]
        frame.configure(bg=bg)
        for child in frame.winfo_children():
            child.configure(bg=bg)
            if hasattr(child, "winfo_children"):
                for gc in child.winfo_children():
                    gc.configure(bg=bg)

    # -- Tooltips --

    def _show_tooltip(self, event, idx: int):
        if idx >= len(self.manager.entries):
            return
        entry = self.manager.entries[idx]
        if not entry.error_message:
            return
        self._hide_tooltip()
        self._create_tooltip(event, entry.error_message, "#FF6B6B", FAILED_BG)

    def _show_simple_tooltip(self, event, text: str):
        self._hide_tooltip()
        self._create_tooltip(event, text, ITEM_COLOR, "#2A2A35")

    def _create_tooltip(self, event, text, fg, bg):
        tw = tk.Toplevel(self.root)
        tw.wm_overrideredirect(True)
        tw.wm_attributes("-topmost", True)
        x = event.x_root + 12
        y = event.y_root - 10
        tw.wm_geometry(f"+{x}+{y}")
        frame = tk.Frame(tw, bg=bg, bd=1, relief="solid")
        frame.pack()
        tk.Label(frame, text=text, font=("Segoe UI", 9), fg=fg, bg=bg,
                 padx=10, pady=6, wraplength=300, justify="left").pack()
        self._tooltip_window = tw

    def _hide_tooltip(self):
        if self._tooltip_window:
            self._tooltip_window.destroy()
            self._tooltip_window = None

    # -- Launching --

    def _manual_launch(self):
        if self._launch_started:
            return
        self._launch_btn.pack_forget()
        self.start_launching()

    def start_launching(self):
        self._launch_started = True
        thread = threading.Thread(target=self._launch_thread, daemon=True)
        thread.start()

    def _launch_thread(self):
        import time
        for i in range(len(self.manager.entries)):
            self.manager.launch_next(i)
            if self.settings.launch_delay > 0:
                time.sleep(self.settings.launch_delay)

        if self.settings.auto_close:
            delay_ms = int(self.settings.auto_close_delay * 1000)
            self.root.after(delay_ms, self._fade_out)

    def _fade_out(self, alpha=0.92):
        alpha -= 0.05
        if alpha <= 0:
            self.root.destroy()
            return
        self.root.attributes("-alpha", alpha)
        self.root.after(30, self._fade_out, alpha)

    def run(self):
        if self.auto_launch:
            self.root.after(500, self.start_launching)
            self.status_label.config(text="Preparing...")
        else:
            self.status_label.config(
                text="Ready \u2014 press \u25B6 to launch. Drag to reorder. Right-click for options."
            )
        self.root.mainloop()
