"""
Pinned Dropdown Options - Custom Widget (v1.3.0)
=================================================
Creates custom dropdowns where each item has a ★ pin button INSIDE the list.

When you open a dropdown, you see:
  ★ frog      ⭐     ← Click ⭐ to pin/unpin!
  ★ cat       ⭐
    dragon          
    forest          

Pinned items float to top. Stars are clickable!

Usage:
    from pinned_dropdowns import PinnedCombobox, init_pinned_manager
    
    # In __init__:
    init_pinned_manager(load_config, save_config)
    
    # Create dropdown:
    combo = PinnedCombobox(parent, category="mood", values=mood_list)
"""

import tkinter as tk
from tkinter import ttk
import logging

logger = logging.getLogger(__name__)

# Categories that support pinning
PINNED_CATEGORIES = [
    "subject", "setting", "lighting", "mood", 
    "atmosphere", "color_family", "color_variation"
]


class PinnedDropdownManager:
    """Manages pinned state for all categories."""
    
    def __init__(self, config_loader, config_saver):
        self._load = config_loader
        self._save = config_saver
        self._pins = {}  # {category: [pinned_items]}
        self._callbacks = []  # Widgets to notify on change
        self._load_pins()
    
    def _load_pins(self):
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
    
    def _save_pins(self):
        """Save to config.json."""
        try:
            cfg = self._load()
            cfg["pinned_options"] = self._pins
            self._save(cfg)
            # Notify all registered widgets to refresh
            for cb in self._callbacks:
                try:
                    cb()
                except:
                    pass
        except Exception as e:
            logger.error(f"Failed to save pins: {e}")
    
    def is_pinned(self, category, value):
        """Check if value is pinned."""
        return bool(value) and value in self._pins.get(category, [])
    
    def toggle_pin(self, category, value):
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
    
    def get_pinned(self, category):
        """Get pinned items for category."""
        return list(self._pins.get(category, []))
    
    def strip_pin_marker(self, value):
        """Strip pin marker (★, ☆, ⭐, 📌, etc.) and leading/trailing whitespace from value string."""
        if not value or not isinstance(value, str):
            return value if value is not None else ""
        val = value.strip()
        for prefix in ["★", "☆", "⭐", "📌", "*"]:
            if val.startswith(prefix):
                val = val[len(prefix):].strip()
        return val
    
    def register_callback(self, callback):
        """Register widget to be notified when pins change."""
        self._callbacks.append(callback)


# Global manager
_mgr = None

def init_pinned_manager(config_loader, config_saver):
    """Initialize global manager."""
    global _mgr
    _mgr = PinnedDropdownManager(config_loader, config_saver)
    return _mgr

def get_manager():
    """Get global manager."""
    return _mgr

def strip_pin_marker(value):
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
    
    def __init__(self, parent, category="", values=None, **kwargs):
        """
        Create a PinnedCombobox.
        
        Args:
            parent: Parent widget
            category: Category key ('subject', 'mood', etc.)
            values: List of string values
            **kwargs: Additional args for Combobox (including state='readonly' etc.)
        """
        self._category = category
        self._base_values = list(values) if values else []
        self._popup_window = None
        
        # CRITICAL: Preserve original state (readonly/normal/disabled)
        # Don't force normal - respect what the caller wants!
        super().__init__(parent, values=self._build_display_values(), **kwargs)
        
        # Remember if this is an editable combobox
        self._is_editable = (self.cget('state') != 'readonly')
        
        # Bind our custom dropdown trigger
        # Use ButtonPress-1 to intercept BEFORE ttk processes it
        self.bind("<ButtonPress-1>", self._on_click)
        
        # For editable comboboxes, also bind to key events
        if self._is_editable:
            # Show popup when pressing down arrow in editable mode
            self.bind("<Down>", self._on_arrow_key)
        
        # Register for pin change notifications
        if _mgr:
            _mgr.register_callback(self._refresh_from_pins)
        
        logger.info(f"PinnedCombobox created: category={category}, state={self.cget('state')}, values={len(self._base_values)} items")
    
    def _build_display_values(self):
        """Build values list with pinned at top (with markers)."""
        if not _mgr:
            return self._base_values
        
        pinned = _mgr.get_pinned(self._category)
        display = []
        
        # Add pinned first with ★ prefix
        for val in self._base_values:
            if val in pinned and val:
                display.append(f"★ {val}")
        
        # Separator if there are pinned items
        if display:
            display.append("─────────")
        
        # Add unpinned
        for val in self._base_values:
            if val not in pinned and val:
                display.append(f"  {val}")
        
        return display
    
    def _on_click(self, event=None):
        """Handle click - show custom dropdown with stars."""
        # Don't interfere with normal operation if no manager
        if not _mgr:
            return
        
        # For EDITABLE comboboxes (Subject/Lighting/Setting):
        # - Click on right side (dropdown button area) → show star popup
        # - Click on text area → allow typing/editing
        if self._is_editable and event:
            # Get the width of the combobox
            combo_width = self.winfo_width()
            # Dropdown button is typically on the right ~25-30 pixels
            button_area = 30
            
            if event.x < (combo_width - button_area):
                # Click was in text area - allow editing, don't show popup
                logger.debug(f"Editable {self._category}: click in text area, allowing edit")
                return None  # Let ttk handle it normally
        
        logger.info(f"Click detected on {self._category} dropdown - showing star popup")
        
        # Show our custom popup immediately
        self._show_popup()
        
        # Prevent default ttk dropdown from showing
        return "break"
    
    def _on_arrow_key(self, event=None):
        """Handle Down arrow key - show popup for editable comboboxes."""
        if not _mgr:
            return
        
        logger.info(f"Arrow key on {self._category} - showing star popup")
        self._show_popup()
        return "break"
    
    def _get_theme_colors(self):
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
            except:
                bg = None
                
            try:
                fg = style.lookup('TLabel', 'foreground')
                if not fg or fg == '':
                    fg = None
            except:
                fg = None
            
            try:
                sel_bg = style.lookup('TCombobox', 'selectbackground')
                if not sel_bg or sel_bg == '':
                    sel_bg = None
            except:
                sel_bg = None
                
            try:
                sel_fg = style.lookup('TCombobox', 'selectforeground')
                if not sel_fg or sel_fg == '':
                    sel_fg = None
            except:
                sel_fg = None
            
            # If we got valid colors, use them
            if bg and fg:
                # If no explicit selected colors, derive them from accent
                if not sel_bg:
                    sel_bg = self._adjust_color(bg, 30)
                if not sel_fg:
                    sel_fg = '#ffffff'
                
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
                    'star_on': '#FFD700',
                }
        except Exception as e:
            logger.debug(f"Could not detect theme colors: {e}")
        
        # Fallback: Dark theme defaults (sv_ttk dark compatible)
        return {
            'bg': '#1e1e1e',
            'fg': '#ffffff',
            'hover': '#2d2d2d',
            'selected_bg': '#3a3a5c',
            'selected_fg': '#ffffff',
            'header_fg': '#888888',
            'separator': '#333333',
            'star_off': '#666666',
            'star_on': '#FFD700',
        }
    
    def _adjust_color(self, hex_color, amount):
        """Lighten or darken a hex color by given amount."""
        try:
            hex_color = hex_color.lstrip('#')
            r = max(0, min(255, int(hex_color[0:2], 16) + amount))
            g = max(0, min(255, int(hex_color[2:4], 16) + amount))
            b = max(0, min(255, int(hex_color[4:6], 16) + amount))
            return f'#{r:02x}{g:02x}{b:02x}'
        except:
            return hex_color
    
    @staticmethod
    def _ensure_contrast(bg_hex, fg_hex, fallback_fg):
        """Ensure foreground has at least 3:1 contrast ratio against background.
        
        If contrast is too low, use fallback_fg or force white/dark.
        """
        try:
            bg_hex = bg_hex.lstrip('#')
            fg_hex = fg_hex.lstrip('#')
            
            def relative_luminance(hex_str):
                r, g, b = int(hex_str[0:2], 16)/255, int(hex_str[2:4], 16)/255, int(hex_str[4:6], 16)/255
                r = r/12.92 if r <= 0.04045 else ((r+0.055)/1.055)**2.4
                g = g/12.92 if g <= 0.04045 else ((g+0.055)/1.055)**2.4
                b = b/12.92 if b <= 0.04045 else ((b+0.055)/1.055)**2.4
                return 0.2126*r + 0.7152*g + 0.0722*b
            
            l_bg = relative_luminance(bg_hex)
            l_fg = relative_luminance(fg_hex)
            
            # WCAG contrast ratio
            lighter = max(l_bg, l_fg)
            darker = min(l_bg, l_fg)
            ratio = (lighter + 0.05) / (darker + 0.05)
            
            if ratio >= 3.0:
                # NOTE: fg_hex was lstrip('#')ed above for the luminance
                # math — it MUST be re-prefixed, otherwise callers pass
                # the bare hex (e.g. "f0fff0") to widget options and Tk
                # raises "unknown color name" when the popup opens.
                return f"#{fg_hex}"
            
            # Use fallback if it has better contrast
            if fallback_fg and fallback_fg != fg_hex:
                l_fb = relative_luminance(fallback_fg.lstrip('#'))
                fb_lighter = max(l_bg, l_fb)
                fb_darker = min(l_bg, l_fb)
                fb_ratio = (fb_lighter + 0.05) / (fb_darker + 0.05)
                if fb_ratio >= 3.0:
                    return fallback_fg if fallback_fg.startswith("#") \
                        else f"#{fallback_fg}"
            
            # Force white or black based on background luminance
            return '#ffffff' if l_bg < 0.4 else '#1a1a1a'
        except:
            return fallback_fg or '#ffffff'
    
    def _on_mousewheel(self, event, canvas):
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
    
    def _show_popup(self):
        """Show the custom pinnable dropdown popup with clickable stars."""
        # Close any existing popup first
        self._close_popup()
        
        logger.info(f"Showing starred popup for category: {self._category}")
        
        # Get theme-matching colors!
        colors = self._get_theme_colors()
        bg_color = colors['bg']
        fg_color = colors['fg']
        hover_bg = colors['hover']
        selected_bg = colors.get('selected_bg', hover_bg)
        selected_fg = colors.get('selected_fg', '#ffffff')
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
        
        # Position below the combobox
        x = self.winfo_rootx()
        y = self.winfo_rooty() + self.winfo_height()
        self._popup_window.wm_geometry(f"+{x}+{y}")
        
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
            
            canvas = tk.Canvas(canvas_container, bg=bg_color, highlightthickness=0, width=260)
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
            if not self._popup_window:
                return
            x = self._popup_window.winfo_rootx()
            y = self._popup_window.winfo_rooty()
            w = self._popup_window.winfo_width()
            h = self._popup_window.winfo_height()
            
            ex = event.x_root
            ey = event.y_root
            
            if not (x <= ex <= x+w and y <= ey <= y+h):
                self._close_popup()
        
        self.bind_all("<Button-1>", on_popup_click)
        self._popup_window.bind("<Escape>", lambda e: self._close_popup())
    
    def _create_popup_row(self, scrollable_parent, value, is_pinned, 
                          bg_color, fg_color, hover_bg, star_on, star_off,
                          selected_bg=None, selected_fg=None, is_current=False):
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
        star_text = "★" if is_pinned else "☆"
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
            
            return "break"
        
        # Item select handler
        def on_item_click(event=None, val=value):
            self.set(val)
            self._close_popup()
            self.event_generate("<<ComboboxSelected>>")
        
        # For currently selected item, hover stays on the selected color
        if is_current and selected_bg:
            hover_for_row = selected_bg
        else:
            hover_for_row = hover_bg
        
        # Bind events
        star_btn.bind("<Button-1>", on_star_click)
        star_btn.bind("<Enter>", lambda e, b=star_btn, p=is_pinned: 
                      b.config(fg="#FFFFFF" if p else "#AAAAAA"))
        star_btn.bind("<Leave>", lambda e, b=star_btn, p=is_pinned, sf=star_fg: 
                      b.config(fg=sf))
        
        item_label.bind("<Button-1>", on_item_click)
        item_label.bind("<Enter>", lambda e, r=row: r.config(bg=hover_for_row))
        item_label.bind("<Leave>", lambda e, r=row, rb=row_bg: r.config(bg=rb))
    
    def _rebuild_popup(self):
        """Rebuild popup content (after pinning)."""
        if self._popup_window and self._popup_window.winfo_exists():
            self._close_popup()
            self._show_popup()
    
    def _close_popup(self):
        """Close the popup."""
        if self._popup_window:
            try:
                self._popup_window.destroy()
            except:
                pass
            self._popup_window = None
        
        # Unbind global click handler
        try:
            self.unbind_all("<Button-1>")
        except:
            pass
    
    def _refresh_from_pins(self):
        """Called when pins change externally."""
        # Update displayed values
        new_vals = self._build_display_values()
        self['values'] = new_vals
        
        # Restore current selection if possible
        current = self.get()
        if current and current.startswith("★ "):
            # Already marked, keep it
            pass
        elif current and current.startswith("  "):
            # Has indent, check if should be starred now
            clean = current.strip()
            if _mgr and _mgr.is_pinned(self._category, clean):
                self.set(f"★ {clean}")
    
    def get_clean_value(self):
        """Get value without markers."""
        val = self.get()
        return strip_pin_marker(val)
    
    def set_clean_value(self, value):
        """Set value with proper marker."""
        if not _mgr:
            self.set(value)
            return
        clean = strip_pin_marker(value)
        if _mgr.is_pinned(self._category, clean):
            self.set(f"★ {clean}")
        else:
            self.set(f"  {clean}")


def create_pinned_combobox(parent, category, values, **kwargs):
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


def build_pinned_settings_ui(parent, app):
    """
    Build settings UI section showing pinned items per category.
    """
    if not _mgr:
        return None
    
    frame = ttk.LabelFrame(parent, text=" 📌 Favorite Dropdown Items ", padding=(12, 10))
    frame.pack(fill="x", pady=8)
    
    # Description
    desc = ttk.Label(
        frame,
        text="Open any dropdown and click ⭐ next to items to mark them as favorites.\nPinned items appear at the top of each dropdown list.",
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
        else:
            ttk.Label(row, text="(no favorites)", foreground="gray").pack(side="left", padx=(8, 0))
    
    # Clear all
    btn_row = ttk.Frame(frame)
    btn_row.pack(fill="x", pady=10)
    
    ttk.Button(btn_row, text="Clear All Favorites", command=_clear_all).pack(side="left")
    
    return frame


def _clear_cat(cat):
    """Clear pins for one category."""
    if _mgr:
        _mgr._pins[cat] = []
        _mgr._save_pins()

def _clear_all():
    """Clear all pins."""
    from tkinter import messagebox
    if messagebox.askyesno("Clear All Favorites", "Remove all favorite items from all dropdowns?"):
        if _mgr:
            for cat in PINNED_CATEGORIES:
                _mgr._pins[cat] = []
            _mgr._save_pins()
