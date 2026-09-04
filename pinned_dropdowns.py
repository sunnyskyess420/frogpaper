"""
Pinned Dropdown Options - Custom Widget (since v1.4.1)
=================================================
Creates custom dropdowns where each item has a ★ pin button INSIDE the list.

When you open a dropdown, you see:
  ★ frog      ★     ← Click the star to add/remove favorites!
  ★ cat       ★
    dragon     ☆
    forest     ☆

Pinned items float to top. Stars are clickable!

Usage:
    from pinned_dropdowns import PinnedCombobox, init_pinned_manager
    
    # In __init__:
    init_pinned_manager(load_config, save_config)
    
    # Create dropdown:
    combo = PinnedCombobox(parent, category="mood", values=mood_list)
"""

import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk
import logging
from typing import Callable

from ui_effects import enable_keyboard_activation

from theme import (
    adjust_color as _theme_adjust_color,
    ensure_contrast as _theme_ensure_contrast,
    FALLBACK_POPUP_COLORS,
    COLOR_STAR_ON,
    PIN_MARKER_ON,
    PIN_MARKER_OFF,
    Tooltip,
)

from theme import COLOR_WHITE  # shared color constants (migrated inline hex)

logger = logging.getLogger(__name__)


def compute_popup_width(measure, items, min_width: int = 260,
                        max_width: int = 420, chrome: int = 78) -> int:
    """Pixel width for the dropdown popup canvas.

    Fits the longest item so text never clips (high-DPI / large fonts),
    clamped between min_width and max_width. ``measure`` is a callable
    mapping a string to its pixel width (e.g. ``tkfont.Font.measure``);
    kept as a parameter so this logic is testable without a display.
    ``chrome`` covers the star column, paddings and the scrollbar.
    """
    longest = 0
    for item in items or ():
        try:
            longest = max(longest, measure(str(item).lower()))
        except Exception:
            continue
    return max(min_width, min(max_width, longest + chrome))

# Categories that support pinning
PINNED_CATEGORIES: list[str] = [
    "subject", "setting", "lighting", "mood", 
    "atmosphere", "color_family", "color_variation"
]


class PinnedDropdownManager:
    """Manages pinned state for all categories."""
    
    def __init__(self, config_loader: Callable[[], dict], config_saver: Callable[[dict], None]) -> None:
        self._load: Callable[[], dict] = config_loader
        self._save: Callable[[dict], None] = config_saver
        self._pins: dict[str, list[str]] = {}  # {category: [pinned_items]}
        self._callbacks: list[Callable[[], None]] = []  # Widgets to notify on change
        self._load_pins()
    
    def _load_pins(self) -> None:
        """Load from config.json."""
        try:
            cfg = self._load()
            self._pins = cfg.get("pinned_options", {})
            for cat in PINNED_CATEGORIES:
                if cat not in self._pins:
                    self._pins[cat] = []
        except Exception as e:
            logger.warning(f"Failed to load pins: {e}")
            self._pins = {cat: [] for cat in PINNED_CATEGORIES}
    
    def _save_pins(self) -> None:
        """Save to config.json."""
        try:
            cfg = self._load()
            cfg["pinned_options"] = self._pins
            self._save(cfg)
            # Notify all registered widgets to refresh
            for cb in self._callbacks:
                try:
                    cb()
                except Exception:
                    pass
        except Exception as e:
            logger.error(f"Failed to save pins: {e}")
    
    def is_pinned(self, category: str, value: str | None) -> bool:
        """Check if value is pinned."""
        return bool(value) and value in self._pins.get(category, [])
    
    def toggle_pin(self, category: str, value: str | None) -> bool:
        """Toggle pin state. Returns True if now pinned."""
        if not value or not value.strip():
            return False
        
        value = value.strip()
        
        if category not in self._pins:
            self._pins[category] = []
        
        if value in self._pins[category]:
            self._pins[category].remove(value)
            self._save_pins()
            return False
        else:
            self._pins[category].append(value)
            self._save_pins()
            return True
    
    def get_pinned(self, category: str) -> list[str]:
        """Get pinned items for category."""
        return list(self._pins.get(category, []))
    
    def strip_pin_marker(self, value: object) -> object:
        """Strip pin marker (★, ☆, ⭐, 📌, etc.) and leading/trailing whitespace from value string."""
        if not value or not isinstance(value, str):
            return value if value is not None else ""
        val = value.strip()
        for prefix in ["★", "☆", "⭐", "📌", "*"]:
            if val.startswith(prefix):
                val = val[len(prefix):].strip()
        return val
    
    def register_callback(self, callback: Callable[[], None]) -> None:
        """Register widget to be notified when pins change."""
        self._callbacks.append(callback)


# Global manager
_mgr = None

def init_pinned_manager(config_loader: Callable[[], dict], config_saver: Callable[[dict], None]) -> PinnedDropdownManager:
    """Initialize global manager."""
    global _mgr
    _mgr = PinnedDropdownManager(config_loader, config_saver)
    return _mgr

def get_manager() -> PinnedDropdownManager | None:
    """Get global manager."""
    return _mgr

def strip_pin_marker(value: object) -> object:
    """Strip pin marker from value string."""
    if _mgr:
        return _mgr.strip_pin_marker(value)
    if not value or not isinstance(value, str):
        return value if value is not None else ""
    val = value.strip()
    for prefix in ["★", "☆", "⭐", "📌", "*"]:
        if val.startswith(prefix):
            val = val[len(prefix):].strip()
    return val


class PinnedCombobox(ttk.Combobox):
    """
    Custom Combobox with pinnable items inside the dropdown.
    
    Shows a custom popup listbox where each item has a clickable star.
    Pinned items appear at top and show with ★ marker.
    """
    
    def __init__(self, parent, category: str = "", values: list[str] | None = None, **kwargs) -> None:
        """
        Create a PinnedCombobox.
        
        Args:
            parent: Parent widget
            category: Category key ('subject', 'mood', etc.)
            values: List of string values
            **kwargs: Additional args for Combobox (including state='readonly' etc.)
        """
        self._category: str = category
        self._base_values: list[str] = list(values) if values else []
        self._popup_window: tk.Toplevel | None = None
        self._popup_active = False  # Flag to track popup state
        self._selection_in_progress = False  # Flag to prevent click-outside during selection
        
        # CRITICAL: Preserve original state (readonly/normal/disabled)
        # Don't force normal - respect what the caller wants!
        super().__init__(parent, values=self._build_display_values(), **kwargs)
        
        # Remember if this is an editable combobox
        self._is_editable = (self.cget('state') != 'readonly')
        
        # Bind our custom dropdown trigger
        # Use ButtonPress-1 to intercept BEFORE ttk processes it
        self.bind("<ButtonPress-1>", self._on_click)
        # Tk 9 note: some platforms post the native list on the RELEASE
        # half of the click — suppress that too so only the starred popup
        # ever appears.
        self.bind("<ButtonRelease-1>", lambda e: "break")
        
        # For editable comboboxes, also bind to key events
        if self._is_editable:
            # Show popup when pressing down arrow in editable mode
            self.bind("<Down>", self._on_arrow_key)
        
        # Register for pin change notifications
        if _mgr:
            _mgr.register_callback(self._refresh_from_pins)
        
        logger.info(f"PinnedCombobox created: category={category}, state={self.cget('state')}, values={len(self._base_values)} items")
    
    def _build_display_values(self) -> list[str]:
        """Build values list with pinned at top (with markers)."""
        if not _mgr:
            return self._base_values
        
        pinned = _mgr.get_pinned(self._category)
        display = []
        
        # Add pinned first with ★ prefix
        for val in self._base_values:
            if val in pinned and val:
                display.append(f"{PIN_MARKER_ON} {val}")
        
        # Separator if there are pinned items
        if display:
            display.append("─────────")
        
        # Add unpinned
        for val in self._base_values:
            if val not in pinned and val:
                display.append(f"  {val}")
        
        return display
    
    def _on_click(self, event: tk.Event | None = None) -> str | None:
        """Handle click - ALWAYS show the custom starred dropdown.

        One dropdown per category: the starred popup replaces the native
        ttk list everywhere, whether the click lands on the arrow or on
        the text area. (The native list has no favorites and used to open
        separately when clicking the words of editable comboboxes.)
        Typing still works — focus returns to the field when the popup
        closes (see _close_popup).
        """
        if not _mgr:
            return

        logger.info(f"Click detected on {self._category} dropdown - showing star popup")

        # Show our custom popup immediately
        self._show_popup()

        # Prevent the native ttk dropdown from showing
        return "break"
    
    def _on_arrow_key(self, event: tk.Event | None = None) -> str:
        """Handle Down arrow key - show popup for editable comboboxes."""
        if not _mgr:
            return
        
        logger.info(f"Arrow key on {self._category} - showing star popup")
        self._show_popup()
        return "break"
    
    def _get_theme_colors(self) -> dict:
        """
        Detect and return theme-matching colors.
        Tries to use ttk style colors, falls back to dark defaults.
        Now includes selected item highlighting for better readability.
        """
        try:
            style = ttk.Style()
            # Try to get actual theme colors
            try:
                bg = style.lookup('TFrame', 'background')
                if not bg or bg == '':
                    bg = None
            except Exception:
                bg = None
                
            try:
                fg = style.lookup('TLabel', 'foreground')
                if not fg or fg == '':
                    fg = None
            except Exception:
                fg = None
            
            try:
                sel_bg = style.lookup('TCombobox', 'selectbackground')
                if not sel_bg or sel_bg == '':
                    sel_bg = None
            except Exception:
                sel_bg = None
                
            try:
                sel_fg = style.lookup('TCombobox', 'selectforeground')
                if not sel_fg or sel_fg == '':
                    sel_fg = None
            except Exception:
                sel_fg = None
            
            # If we got valid colors, use them
            if bg and fg:
                # If no explicit selected colors, derive them from accent
                if not sel_bg:
                    sel_bg = self._adjust_color(bg, 30)
                if not sel_fg:
                    sel_fg = COLOR_WHITE
                
                # Ensure selected_fg has enough contrast against selected_bg
                sel_fg = self._ensure_contrast(sel_bg, sel_fg, fg)
                
                return {
                    'bg': bg,
                    'fg': fg,
                    'hover': self._adjust_color(bg, 18),
                    'selected_bg': sel_bg,
                    'selected_fg': sel_fg,
                    'header_fg': self._adjust_color(fg, -30),  # Dimmer for header
                    'separator': self._adjust_color(bg, 28),
                    'star_off': self._adjust_color(fg, -40),
                    'star_on': COLOR_STAR_ON,
                }
        except Exception as e:
            logger.debug(f"Could not detect theme colors: {e}")
        
        # Fallback: Dark theme defaults (sv_ttk dark compatible)
        return dict(FALLBACK_POPUP_COLORS)
    
    def _adjust_color(self, hex_color: str, amount: int) -> str:
        """Lighten or darken a hex color by given amount."""
        # Single implementation lives in theme.py
        return _theme_adjust_color(hex_color, amount)
    
    @staticmethod
    def _ensure_contrast(bg_hex: str, fg_hex: str, fallback_fg: str) -> str:
        """Ensure foreground has at least 3:1 contrast ratio against background.

        If contrast is too low, use fallback_fg or force white/dark.
        Single implementation lives in theme.py (keeps the historical fix
        of always re-prefixing the leading '#').
        """
        return _theme_ensure_contrast(bg_hex, fg_hex, fallback_fg)

    def _on_mousewheel(self, event: tk.Event, canvas: tk.Canvas) -> None:
        """Handle mouse wheel scrolling - works on Windows and Linux."""
        # Windows uses event.delta, Linux uses event.num
        try:
            if event.delta:
                # Windows/Mac - slower scrolling (was 30, now 8)
                delta = -int(event.delta / 120) * 8
            elif event.num == 4:
                # Linux scroll up - slower
                delta = -8
            elif event.num == 5:
                # Linux scroll down - slower
                delta = 8
            else:
                delta = 0
            
            canvas.yview_scroll(delta, "units")
        except Exception as e:
            logger.debug(f"Mousewheel error: {e}")
    
    def _show_popup(self) -> None:
        """Show the custom pinnable dropdown popup with clickable stars."""
        # Close any existing popup first
        self._close_popup()
        
        # Set popup active flag
        self._popup_active = True
        
        logger.info(f"Showing starred popup for category: {self._category}")
        
        # Get theme-matching colors!
        colors = self._get_theme_colors()
        bg_color = colors['bg']
        fg_color = colors['fg']
        hover_bg = colors['hover']
        selected_bg = colors.get('selected_bg', hover_bg)
        selected_fg = colors.get('selected_fg', COLOR_WHITE)
        header_fg = colors['header_fg']
        sep_color = colors['separator']
        star_off = colors['star_off']
        star_on = colors['star_on']
        
        # Store current value to highlight the selected item
        current_val = self.get()
        
        # Create popup window (toplevel)
        self._popup_window = tk.Toplevel(self)
        self._popup_window.wm_overrideredirect(True)
        
        # CRITICAL: Make sure popup stays on top and visible!
        self._popup_window.wm_attributes('-topmost', True)
        self._popup_window.lift()
        self._popup_window.focus_force()
        
        self._popup_window.configure(bg=bg_color)
        
        # Get pinned items
        pinned_list = _mgr.get_pinned(self._category) if _mgr else []
        
        # Separate into pinned and unpinned lists
        pinned_items = []
        unpinned_items = []
        
        for val in self._base_values:
            if val:
                if val in pinned_list:
                    pinned_items.append(val)
                else:
                    unpinned_items.append(val)
        
        # Sort both lists alphabetically
        pinned_items.sort()
        unpinned_items.sort()
        
        # Position below the combobox with screen boundary checking
        x = self.winfo_rootx()
        y = self.winfo_rooty() + self.winfo_height()
        
        # Get screen dimensions
        screen_width = self._popup_window.winfo_screenwidth()
        screen_height = self._popup_window.winfo_screenheight()
        
        # Calculate popup height (estimate based on content)
        popup_height = 100  # Base height
        if pinned_items:
            popup_height += len(pinned_items) * 28 + 40  # Favorites section
        if unpinned_items:
            popup_height += min(280, len(unpinned_items) * 28 + 20)  # Available section
        
        # Adjust y position if popup would extend beyond screen bottom
        if y + popup_height > screen_height:
            # Position above the combobox instead
            y = self.winfo_rooty() - popup_height - 5
            # Ensure it doesn't go off top of screen
            if y < 0:
                y = 5
        
        # Adjust x position if popup would extend beyond screen right edge
        popup_width = 300  # Estimated width
        if x + popup_width > screen_width:
            x = screen_width - popup_width - 10
            # Ensure it doesn't go off left edge
            if x < 0:
                x = 10
        
        self._popup_window.wm_geometry(f"+{x}+{y}")
        
        # Create main frame
        frame = tk.Frame(self._popup_window, bg=bg_color)
        frame.pack(fill="both", expand=True)
        
        # === FAVORITES SECTION (if any pinned) ===
        if pinned_items:
            fav_header = tk.Label(
                frame, text=f"★ FAVORITES ({len(pinned_items)})",
                font=("Segoe UI", 9, "bold"), fg=star_on, bg=bg_color,
                anchor="w", padx=10, pady=6
            )
            fav_header.pack(fill="x")
            
            fav_sep = tk.Frame(frame, height=1, bg=sep_color)
            fav_sep.pack(fill="x", padx=5)
            
            # Add pinned items
            for val in pinned_items:
                is_current = (val == current_val)
                self._create_popup_row(
                    scrollable_parent=frame, value=val, is_pinned=True,
                    bg_color=bg_color, fg_color=fg_color, hover_bg=hover_bg,
                    selected_bg=selected_bg, selected_fg=selected_fg,
                    is_current=is_current,
                    star_on=star_on, star_off=star_off
                )
            
            # Spacer between sections
            spacer = tk.Frame(frame, height=8, bg=bg_color)
            spacer.pack(fill="x")
        
        # === AVAILABLE ITEMS SECTION ===
        # Header for available items
        if pinned_items:
            avail_header = tk.Label(
                frame, text=f"Available Options ({len(unpinned_items)})",
                font=("Segoe UI", 9), fg=header_fg, bg=bg_color,
                anchor="w", padx=10, pady=4
            )
            avail_header.pack(fill="x")
        else:
            # No favorites yet - show instruction
            avail_header = tk.Label(
                frame, text="Click ☆ to add favorites",
                font=("Segoe UI", 8), fg=header_fg, bg=bg_color,
                anchor="w", padx=10, pady=4
            )
            avail_header.pack(fill="x")
        
        avail_sep = tk.Frame(frame, height=1, bg=sep_color)
        avail_sep.pack(fill="x", padx=5)
        
        # === SCROLLABLE AREA FOR UNPINNED ITEMS ===
        if unpinned_items:
            # Canvas with scrollbar for long lists
            canvas_container = tk.Frame(frame, bg=bg_color)
            canvas_container.pack(fill="both", expand=True)
            
            # Widen to fit the longest item (the old fixed 260px clipped
            # longer entries at high-DPI / large font settings).
            popup_width = compute_popup_width(
                tkfont.Font(family="Segoe UI", size=10).measure,
                unpinned_items)
            canvas = tk.Canvas(canvas_container, bg=bg_color, highlightthickness=0, width=popup_width)
            scrollbar = ttk.Scrollbar(canvas_container, orient="vertical", command=canvas.yview)
            scrollable_frame = tk.Frame(canvas, bg=bg_color)
            
            scrollable_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
            )
            
            canvas.create_window((0, 0), window=scrollable_frame, anchor="nw", width=260)
            canvas.configure(yscrollcommand=scrollbar.set)
            
            # Add unpinned items to scrollable area
            for val in unpinned_items:
                is_current = (val == current_val)
                self._create_popup_row(
                    scrollable_parent=scrollable_frame, value=val, is_pinned=False,
                    bg_color=bg_color, fg_color=fg_color, hover_bg=hover_bg,
                    selected_bg=selected_bg, selected_fg=selected_fg,
                    is_current=is_current,
                    star_on=star_on, star_off=star_off
                )
            
            # Pack scroll area
            canvas.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")
            
            # Set height based on item count (max 300px)
            item_height = 28
            max_height = min(280, len(unpinned_items) * item_height + 20)
            canvas.config(height=max_height)
            
            # === MOUSE WHEEL SCROLLING (Windows compatible) ===
            def _mousewheel_handler(event):
                self._on_mousewheel(event, canvas)
                return "break"
            
            # Bind to canvas
            canvas.bind("<MouseWheel>", _mousewheel_handler)  # Windows/Mac
            canvas.bind("<Button-4>", _mousewheel_handler)     # Linux scroll up  
            canvas.bind("<Button-5>", _mousewheel_handler)     # Linux scroll down
            
            # Bind to scrollable frame
            scrollable_frame.bind("<MouseWheel>", _mousewheel_handler)
            scrollable_frame.bind("<Button-4>", _mousewheel_handler)
            scrollable_frame.bind("<Button-5>", _mousewheel_handler)
            
            # CRITICAL: Bind to popup window itself for Windows
            self._popup_window.bind("<MouseWheel>", _mousewheel_handler)
            self._popup_window.bind("<Button-4>", _mousewheel_handler)
            self._popup_window.bind("<Button-5>", _mousewheel_handler)
            
            # Also bind to frame container
            frame.bind("<MouseWheel>", _mousewheel_handler)
            frame.bind("<Button-4>", _mousewheel_handler)
            frame.bind("<Button-5>", _mousewheel_handler)
            
            # Store reference for external access
            self._popup_canvas = canvas
        else:
            no_items = tk.Label(
                frame, text="All items are favorites! ★",
                font=("Segoe UI", 9, "italic"), fg=header_fg, bg=bg_color,
                padx=10, pady=10
            )
            no_items.pack()
            self._popup_canvas = None
        
        # Close popup when clicking outside
        def on_popup_click(event):
            # Only process if popup is still active and we're not selecting an item
            if not self._popup_active or not self._popup_window or self._selection_in_progress:
                return
            
            # Check if click is within the popup window
            try:
                x = self._popup_window.winfo_rootx()
                y = self._popup_window.winfo_rooty()
                w = self._popup_window.winfo_width()
                h = self._popup_window.winfo_height()
                
                ex = event.x_root
                ey = event.y_root
                
                # If click is outside popup bounds, close it
                if not (x <= ex <= x+w and y <= ey <= y+h):
                    self._close_popup()
            except Exception:
                # If popup window no longer exists, close it
                self._close_popup()
        
        # Store reference to the handler
        self._popup_click_handler = on_popup_click
        
        # Bind to the root window for click-outside detection
        root = self.winfo_toplevel()
        root.bind("<Button-1>", on_popup_click, add="+")
        
        self._popup_window.bind("<Escape>", lambda e: self._close_popup())
        # Keyboard: start focus inside the popup so Tab can reach the
        # star buttons and item rows immediately after it opens.
        try:
            self._popup_window.focus_set()
        except Exception:
            pass
    
    def _create_popup_row(self, scrollable_parent: tk.Frame | ttk.Frame, value: str, is_pinned: bool, 
                          bg_color: str, fg_color: str, hover_bg: str, star_on: str, star_off: str,
                          selected_bg: str | None = None, selected_fg: str | None = None, is_current: bool = False) -> None:
        """
        Create a single row in the popup with star + item label.
        If is_current, the row is highlighted with selected_bg/selected_fg.
        """
        # Use selected colors for the currently active item
        row_bg = selected_bg if is_current and selected_bg else bg_color
        row_fg = selected_fg if is_current and selected_fg else fg_color
        
        row = tk.Frame(scrollable_parent, bg=row_bg)
        row.pack(fill="x")
        
        # Star button (clickable!)
        star_text = PIN_MARKER_ON if is_pinned else PIN_MARKER_OFF
        star_fg = star_on if is_pinned else star_off
        # If row is highlighted, make star visible against selected_bg
        if is_current:
            star_fg = selected_fg if selected_fg else star_fg
        
        star_btn = tk.Label(
            row, text=star_text,
            font=("Segoe UI Emoji", 12),
            fg=star_fg, bg=row_bg,
            cursor="hand2",
            width=2
        )
        star_btn.pack(side="left", padx=(8, 4), pady=2)
        
        # Item label (selectable) - always display in lowercase
        item_label = tk.Label(
            row, text=value.lower(),
            font=("Segoe UI", 10),
            fg=row_fg, bg=row_bg,
            anchor="w",
            cursor="hand2"
        )
        item_label.pack(side="left", fill="x", expand=True, pady=2)
        
        # Star click handler - pin/unpin
        def on_star_click(event=None, val=value, btn=star_btn, lbl=item_label):
            self._selection_in_progress = True  # Flag that we're interacting with the popup
            if _mgr:
                now_pinned = _mgr.toggle_pin(self._category, val)
                
                if now_pinned:
                    # Just got pinned - update visual immediately
                    btn.config(text="★", fg=star_on)
                    # Rebuild after delay to move to favorites section
                    self.after(200, self._rebuild_popup)
                else:
                    # Just got unpinned - update visual
                    btn.config(text="☆", fg=star_off)
                    # Rebuild to move back to available section
                    self.after(200, self._rebuild_popup)
            
            # Reset flag after a short delay
            self.after(100, lambda: setattr(self, '_selection_in_progress', False))
            return "break"  # Prevent event propagation
        
        # Item select handler
        def on_item_click(event=None, val=value):
            self._selection_in_progress = True  # Flag that we're selecting an item
            self.set(val)
            self._close_popup()
            self.event_generate("<<ComboboxSelected>>")
            # Reset flag after a short delay to ensure click event completes
            self.after(100, lambda: setattr(self, '_selection_in_progress', False))
            return "break"  # Prevent event propagation to avoid conflicts
        
        # For currently selected item, hover stays on the selected color
        if is_current and selected_bg:
            hover_for_row = selected_bg
        else:
            hover_for_row = hover_bg
        
        # Bind events
        star_btn.bind("<Button-1>", on_star_click)
        star_btn.bind("<Enter>", lambda e, b=star_btn, p=is_pinned: 
                      b.config(fg=COLOR_WHITE if p else "#AAAAAA"))
        star_btn.bind("<Leave>", lambda e, b=star_btn, p=is_pinned, sf=star_fg: 
                      b.config(fg=sf))
        
        item_label.bind("<Button-1>", on_item_click)
        item_label.bind("<Enter>", lambda e, r=row: r.config(bg=hover_for_row))
        item_label.bind("<Leave>", lambda e, r=row, rb=row_bg: r.config(bg=rb))

        # Discoverability: explain what the star does
        Tooltip(star_btn, "Remove from favorites" if is_pinned else "Add to favorites")

        # Keyboard operable: Tab reaches the star and the item; Enter or
        # Space toggles the pin / selects the item (same handlers as the
        # mouse clicks). Each gets a visible focus ring.
        enable_keyboard_activation(star_btn, lambda: on_star_click(), row_bg)
        enable_keyboard_activation(item_label, lambda: on_item_click(), row_bg)
    
    def _rebuild_popup(self) -> None:
        """Rebuild popup content (after pinning)."""
        if self._popup_window and self._popup_window.winfo_exists():
            self._close_popup()
            self._show_popup()
    
    def _close_popup(self) -> None:
        """Close the popup."""
        # Set popup inactive flag first to prevent multiple close attempts
        self._popup_active = False
        
        if self._popup_window:
            try:
                self._popup_window.destroy()
            except Exception:
                pass
            self._popup_window = None
        
        # The popup_active flag will prevent the click handler from doing anything
        # No need to unbind - the flag handles it

        # Give focus back to the field so typing continues seamlessly
        try:
            if self._is_editable:
                self.focus_set()
        except Exception:
            pass
    
    def _refresh_from_pins(self) -> None:
        """Called when pins change externally."""
        # Update displayed values
        new_vals = self._build_display_values()
        self['values'] = new_vals
        
        # Restore current selection if possible
        current = self.get()
        if current and current.startswith(f"{PIN_MARKER_ON} "):
            # Already marked, keep it
            pass
        elif current and current.startswith("  "):
            # Has indent, check if should be starred now
            clean = current.strip()
            if _mgr and _mgr.is_pinned(self._category, clean):
                self.set(f"{PIN_MARKER_ON} {clean}")
    
    def get_clean_value(self) -> str:
        """Get value without markers."""
        val = self.get()
        return strip_pin_marker(val)
    
    def set_clean_value(self, value: str) -> None:
        """Set value with proper marker."""
        if not _mgr:
            self.set(value)
            return
        clean = strip_pin_marker(value)
        if _mgr.is_pinned(self._category, clean):
            self.set(f"{PIN_MARKER_ON} {clean}")
        else:
            self.set(f"  {clean}")


def create_pinned_combobox(parent, category: str, values: list[str], **kwargs) -> PinnedCombobox:
    """
    Factory function to create a PinnedCombobox.
    
    Args:
        parent: Parent widget
        category: Category string
        values: List of values
        **kwargs: Additional Combobox options
    
    Returns:
        PinnedCombobox instance
    """
    return PinnedCombobox(parent, category=category, values=values, **kwargs)


def build_pinned_settings_ui(parent, app) -> ttk.LabelFrame | None:
    """
    Build settings UI section showing pinned items per category.
    """
    if not _mgr:
        return None
    
    frame = ttk.LabelFrame(parent, text=f" {PIN_MARKER_ON} Favorite Dropdown Items ", padding=(12, 10))
    frame.pack(fill="x", pady=8)
    
    # Description
    desc = ttk.Label(
        frame,
        text=f"Open any dropdown and click {PIN_MARKER_OFF} next to items to mark them as favorites.\nPinned items appear at the top of each dropdown list.",
        font=app.small_font,
        wraplength=600
    )
    desc.pack(anchor="w", pady=(0, 12))
    
    # Show each category's pinned items
    for cat in PINNED_CATEGORIES:
        row = ttk.Frame(frame)
        row.pack(fill="x", pady=2)
        
        # Category name
        cat_label = cat.replace("_", " ").title()
        ttk.Label(row, text=f"{cat_label}:", width=14).pack(side="left")
        
        # Pinned count/items
        pinned = _mgr.get_pinned(cat)
        if pinned:
            # Show up to 5 items
            text = ", ".join(f"★{p}" for p in pinned[:5])
            if len(pinned) > 5:
                text += f" (+{len(pinned)-5} more)"
            lbl = ttk.Label(row, text=text, foreground="#FFD700")
            lbl.pack(side="left", padx=(8, 0))
            
            # Clear button
            clear_btn = ttk.Button(
                row, text="✕", width=2,
                command=lambda c=cat: _clear_cat(c)
            )
            clear_btn.pack(side="right", padx=(4, 0))
            Tooltip(clear_btn, "Clear favorites for this category")
        else:
            ttk.Label(row, text="(no favorites)", foreground="gray").pack(side="left", padx=(8, 0))
    
    # Clear all
    btn_row = ttk.Frame(frame)
    btn_row.pack(fill="x", pady=10)
    
    clear_all_btn = ttk.Button(btn_row, text="Clear All Favorites", command=_clear_all)
    clear_all_btn.pack(side="left")
    Tooltip(clear_all_btn, "Remove favorites from every dropdown")
    
    return frame


def _clear_cat(cat: str) -> None:
    """Clear pins for one category."""
    if _mgr:
        _mgr._pins[cat] = []
        _mgr._save_pins()

def _clear_all() -> None:
    """Clear all pins."""
    from tkinter import messagebox
    if messagebox.askyesno("Clear All Favorites", "Remove all favorite items from all dropdowns?"):
        if _mgr:
            for cat in PINNED_CATEGORIES:
                _mgr._pins[cat] = []
            _mgr._save_pins()
