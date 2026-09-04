import tkinter as tk
import logging
import os
import threading
import random
from pathlib import Path
from datetime import datetime

from theme import COLOR_BLACK, COLOR_MID_GRAY, COLOR_WHITE  # shared color constants (migrated inline hex)

# Import thread-safe UI update functions
try:
    from thread_manager import run_background, schedule_ui_update
    THREAD_MANAGER_AVAILABLE = True
except ImportError:
    THREAD_MANAGER_AVAILABLE = False
    # Fallback to direct threading if thread_manager not available
    def schedule_ui_update(callback, *args, **kwargs):
        """Fallback for thread-safe UI updates."""
        if hasattr(callback, '__self__') and hasattr(callback.__self__, 'root'):
            callback.__self__.root.after(0, lambda: callback(*args, **kwargs))
        else:
            # Direct call as fallback (not thread-safe, but prevents crashes)
            callback(*args, **kwargs)
    
    def run_background(target, *args, daemon=True, **kwargs):
        """Fallback for background thread execution."""
        thread = threading.Thread(target=target, args=args, kwargs=kwargs, daemon=daemon)
        thread.start()
        return thread

from tkinter import ttk, simpledialog
from PIL import ImageTk, ImageEnhance, ImageColor

try:
    from set_wallpaper import set_wallpaper, collect_wallpapers
except (ImportError, AttributeError):
    def collect_wallpapers():
        return []
    def set_wallpaper(_path):
        return False

from gallery_manager import (
    add_tags_to_image,
    add_tags_to_paths,
    get_tags_for_image,
    get_all_tags,
    organize_image_into_folder,
    delete_image_and_tags,
    cleanup_orphaned_tags,
    get_prompt_parameters,
    get_portrait_images,
)


from utils import load_json_list, save_json_list, get_app_dir

logger = logging.getLogger(__name__)


class GalleryTab:
    """Gallery tab: wallpaper grid, favorites, styled images, manual images, style transfer."""

    # Icon mapping: widget attribute or local var name -> icon name
    _ACTION_ICONS = {
        "wallpaper": "wallpaper",
        "style": "palette",
        "text": "text_edit",
        "delete": "delete",
        "export": "export",
    }

    def __init__(self, app):
        self.app = app
        self._fade_jobs = {}  # label widget -> list of after() ids
        self._ratio_load_gen = 0  # generation counter to cancel stale ratio-load threads

    # ── Tag helpers ──────────────────────────────────────────────────
    _STYLE_SUFFIXES = None  # lazily built from StyleTransfer.available_styles

    def _get_tags_with_fallback(self, img_path, fav_item=None):
        """Get tags for an image, falling back to related/original paths.

        Styled images and favorites copies live in different directories than
        the originals whose tags were actually stored.  This helper tries:
          1. Direct lookup on *img_path*
          2. For styled images: strip _{style} suffix and check generated/manual dirs
          3. For favorites: use the ``original_image_path`` from the fav entry
          4. Broader _resolve_related_paths search
        """
        app = self.app

        # 1. Direct lookup
        tags = get_tags_for_image(img_path) or []
        if tags:
            return tags

        # 2. Styled image → try the original source
        if hasattr(app, 'STYLED_DIR') and img_path.is_absolute() and app.STYLED_DIR in img_path.parents:
            if self._STYLE_SUFFIXES is None:
                # Build lazy once: ["_oil_painting", "_watercolor", ...] (skip "original")
                try:
                    from style_transfer import StyleTransfer
                    st = StyleTransfer()
                    self._STYLE_SUFFIXES = sorted(
                        [f"_{s}" for s in st.available_styles if s != "original"],
                        key=len, reverse=True,  # longest first so we strip correctly
                    )
                except Exception:
                    self._STYLE_SUFFIXES = []
            stem = img_path.stem
            ext = img_path.suffix
            for suffix in self._STYLE_SUFFIXES:
                if stem.endswith(suffix):
                    original_stem = stem[:-len(suffix)]
                    for search_dir in (getattr(app, 'GENERATED_DIR', None),
                                       getattr(app, 'MANUAL_DIR', None)):
                        if search_dir and search_dir.exists():
                            candidate = search_dir / f"{original_stem}{ext}"
                            if candidate.exists():
                                tags = get_tags_for_image(candidate) or []
                                if tags:
                                    return tags
                    break  # only one style suffix can match

        # 3. Favorites → try original_image_path from entry metadata
        if fav_item:
            orig = fav_item.get("original_image_path")
            if orig:
                try:
                    orig_path = Path(orig)
                    if orig_path.exists() and orig_path != img_path:
                        tags = get_tags_for_image(orig_path) or []
                        if tags:
                            return tags
                except Exception:
                    pass

        # 4. Broader related-paths search (original ↔ favorite copy)
        try:
            for related in self._resolve_related_paths(img_path):
                if str(related) != str(img_path):
                    tags = get_tags_for_image(related) or []
                    if tags:
                        return tags
        except Exception:
            pass

        return []

    # ── Icon helpers ────────────────────────────────────────────────
    def _refresh_current_view(self):
        """Refresh the currently active gallery view."""
        app = self.app
        current_view = app.gallery_view_var.get()
        
        if current_view == "Gallery":
            app.load_gallery()
        elif current_view == "Favorites":
            tag_filter = app.get_active_tag()
            app.load_favorites(tag_filter=tag_filter)
        elif current_view == "Styled":
            tag_filter = app.get_active_tag()
            app.load_styled(tag_filter=tag_filter)
        elif current_view == "Manual":
            tag_filter = app.get_active_tag()
            app.load_manual(tag_filter=tag_filter)
        elif current_view in ["Ratio 16:9", "Ratio 9:16", "Ratio 1:1"]:
            tag_filter = app.get_active_tag()
            # Show loading indicator
            app.status_var.set(f'Refreshing {current_view} images...')
            app.root.update_idletasks()
            # Load in background thread to prevent UI freeze
            run_background(app.load_gallery_by_ratio, current_view, tag_filter)
        else:
            # Default to gallery if unknown view
            app.load_gallery()

    def _apply_toolbar_icons(self):
        """Set icon images on gallery action buttons after theme load."""
        app = self.app
        if not hasattr(app, '_gallery_action_row_order'):
            return
        pal = app.THEMES.get(app.current_theme_name, app.THEMES["darkforest"])
        accent = pal.get("accent", pal["progress"])
        try:
            from icons import get_icon
            icon_names = ["wallpaper", "palette", "text_edit", "delete", "refresh", "export"]
            for btn, icon_name in zip(app._gallery_action_row_order, icon_names):
                if hasattr(btn, 'configure') and icon_name:
                    try:
                        _img = get_icon(icon_name, size=14, color=accent)
                        btn.configure(image=_img, compound="left")
                        btn._icon_ref = _img  # prevent GC
                    except Exception:
                        pass  # Skip if icon not available
        except Exception as e:
            logger.error(f"Error applying toolbar icons: {e}")
            pass  # Graceful fallback — buttons still work with text-only

    def _fade_in_thumb(self, label_widget, photo_image, steps=4, interval=35,
                       base_pil=None):
        """Smoothly fade-in a thumbnail using brightness stepping.

        Starts at 30% brightness and ramps to 100% over *steps* frames.
        Pass ``base_pil`` (the PIL image the PhotoImage was made from) to
        skip the PhotoImage->PIL round-trip this would otherwise do.
        """
        # Cancel any previous fade on this label
        if label_widget in self._fade_jobs:
            for job_id in self._fade_jobs[label_widget]:
                try:
                    label_widget.after_cancel(job_id)
                except Exception:
                    pass
        self._fade_jobs[label_widget] = []

        base_img = base_pil if base_pil is not None else ImageTk.getimage(photo_image)

        def _step(step_num):
            if step_num >= steps:
                label_widget.configure(image=photo_image)
                self._fade_jobs.pop(label_widget, None)
                return
            brightness = 0.3 + 0.7 * ((step_num + 1) / steps)
            faded = ImageEnhance.Brightness(base_img).enhance(brightness)
            faded_photo = ImageTk.PhotoImage(faded)
            label_widget.configure(image=faded_photo)
            label_widget._faded_ref = faded_photo  # prevent GC
            job_id = label_widget.after(interval, _step, step_num + 1)
            self._fade_jobs.setdefault(label_widget, []).append(job_id)

        _step(0)

    def _apply_style_thread(self, style):

        """Apply style in a separate thread."""

        app = self.app
        try:

            # Update status for image loading (thread-safe)
            schedule_ui_update(app.status_var.set, f"Loading image for {style} style...")

            from style_transfer import apply_style_to_image

            # Update status for processing (thread-safe)
            schedule_ui_update(app.status_var.set, f"Processing {style} style...")

            styled_path = apply_style_to_image(app.selected_gallery_path, style)

            if styled_path:

                # Update status for success (thread-safe)
                schedule_ui_update(app.status_var.set, f"✅ {style} style applied successfully!")

                # Update UI from main thread (thread-safe)
                schedule_ui_update(app._style_applied_success, styled_path, style)

            else:

                # Update status for failure (thread-safe)
                schedule_ui_update(app.status_var.set, f"❌ {style} style failed - no image created")

                schedule_ui_update(app._style_applied_failed, style)

        except Exception as e:

            # Update status for error - avoid threading issues
            try:
                schedule_ui_update(app.status_var.set, f"❌ Style transfer error: {str(e)}")
                schedule_ui_update(app._style_applied_error, str(e))
            except Exception:

                # Fallback if root is no longer valid
                logger.error(f"Style transfer error (app.UI update failed): {str(e)}")


    def _build_gallery_tab(self, parent):

        # Gallery Controls — contains view selector, filters, sort, and action buttons
        app = self.app
        filter_frame = ttk.LabelFrame(parent, text="Gallery Controls", padding=10)

        filter_frame.pack(fill='x', pady=(0, 8))

        # Row 1: View Selection - what to view
        view_row = ttk.Frame(filter_frame)
        view_row.pack(fill='x', pady=(0, 8))

        ttk.Label(view_row, text="View:", font=app.small_font).pack(side='left', padx=(0, 4))
        app.gallery_view_var = tk.StringVar(value="Gallery")
        ttk.Radiobutton(view_row, text="Gallery", variable=app.gallery_view_var,
                        value="Gallery", command=app._on_gallery_view_changed).pack(side='left', padx=(0, 4))
        ttk.Radiobutton(view_row, text="Favs", variable=app.gallery_view_var,
                        value="Favorites", command=app._on_gallery_view_changed).pack(side='left', padx=(0, 4))
        ttk.Radiobutton(view_row, text="Styled", variable=app.gallery_view_var,
                        value="Styled", command=app._on_gallery_view_changed).pack(side='left', padx=(0, 4))
        ttk.Radiobutton(view_row, text="Manual", variable=app.gallery_view_var,
                        value="Manual", command=app._on_gallery_view_changed).pack(side='left', padx=(0, 4))

        ttk.Separator(view_row, orient="vertical").pack(side="left", padx=(4, 4), fill="y")

        # Even distribution spacer between View and Ratio groups
        ttk.Frame(view_row).pack(side="left", fill="x", expand=True)

        ttk.Label(view_row, text="Ratio:", font=app.small_font).pack(side='left', padx=(0, 4))
        ttk.Radiobutton(view_row, text="16:9", variable=app.gallery_view_var,
                        value="Ratio 16:9", command=app._on_gallery_view_changed).pack(side='left', padx=(0, 4))
        ttk.Radiobutton(view_row, text="Portrait", variable=app.gallery_view_var,
                        value="Ratio 9:16", command=app._on_gallery_view_changed).pack(side='left', padx=(0, 4))
        ttk.Radiobutton(view_row, text="Square", variable=app.gallery_view_var,
                        value="Ratio 1:1", command=app._on_gallery_view_changed).pack(side='left', padx=(0, 4))

        # Row 2: Image Actions - what to do with selected image
        action_row = ttk.Frame(filter_frame)
        action_row.pack(fill='x', pady=(0, 8))
        app._gallery_action_row = action_row  # saved for view-switch repack

        def _pack_spaced(parent, *widgets):
            """Pack widgets left with expanding spacers between them for even distribution."""
            for i, w in enumerate(widgets):
                w.pack(side='left')
                if i < len(widgets) - 1:
                    ttk.Frame(parent).pack(side='left', fill='x', expand=True)

        _btn_wallpaper = ttk.Button(action_row, text="Set Wallpaper",
                   command=app._gallery_set_wallpaper)

        app.style_menu_btn = ttk.Menubutton(action_row, text="Apply Style")
        app.style_menu = tk.Menu(app.style_menu_btn, tearoff=0)
        for display_name, style_key in [
            ("Oil Painting", "oil_painting"), ("Watercolor", "watercolor"),
            ("Sketch", "sketch"), ("Line Art", "line_art"),
            ("Comic Book", "comic_book"), ("Manga", "manga"),
            ("Sepia", "sepia"), ("B&W", "bw"),
            ("Vintage", "vintage"), ("Posterize", "posterize"),
            ("Emboss", "emboss"), ("Edge Enhance", "edge_enhance"),
            ("Cyberpunk Neon", "cyberpunk_neon"), ("Vaporwave", "vaporwave"),
            ("Pixel Art", "pixel_art"), ("Sketch Pencil", "sketch_pencil"),
            ("Gouache", "gouache"), ("Art Deco", "art_deco"),
            ("Surreal Dali", "surreal_dali"), ("3D Render", "3d_render"),
            ("Anime Key", "anime_key"), ("Noir B&W", "noir_bw"),
            ("Vintage Sepia", "vintage_sepia"), ("Pop Art", "pop_art"),
            ("Impressionist", "impressionist"),
        ]:
            app.style_menu.add_command(label=display_name,
                command=lambda sk=style_key: app._gallery_apply_theme(sk))
        app.style_menu_btn.config(menu=app.style_menu)

        _btn_text = ttk.Button(action_row, text="Add Text",
                   command=app._gallery_add_text)

        _btn_delete = ttk.Button(action_row, text="Delete",
                   command=app._gallery_delete)

        _btn_refresh = ttk.Button(action_row, text="Refresh Gallery", command=self._refresh_current_view)

        _pack_spaced(action_row, _btn_wallpaper, app.style_menu_btn, _btn_text, _btn_delete, _btn_refresh)

        # Full ordered list — mirrors the view radio order: Gallery|Favorites|Styled|Manual
        # Gallery=Wallpaper, Styled=Apply Style, Manual=Delete
        app._gallery_action_row_order = [
            _btn_wallpaper, app.style_menu_btn,
            _btn_text, _btn_delete, _btn_refresh,
        ]

        # Row 3: Organization - sort, tag, refresh
        org_row = ttk.Frame(filter_frame)
        org_row.pack(fill='x')

        ttk.Label(org_row, text="Sort:", font=app.small_font).pack(side='left', padx=(0, 8))

        app.sort_combo_var = tk.StringVar(value="Date Newest")

        app.sort_combo = ttk.Combobox(org_row, textvariable=app.sort_combo_var,
                                        values=["Date Newest", "Date Oldest", "Name A-Z", "Name Z-A", "Size Largest", "Size Smallest", "Resolution Largest", "Resolution Smallest"],
                                        state="readonly", width=14)
        app.sort_combo.pack(side='left', padx=(0, 10))
        app.sort_combo.bind('<<ComboboxSelected>>', app.sort_gallery)
        
        # Enhanced scroll prevention for dropdown
        def prevent_gallery_scroll(event):
            """Prevent scroll events from propagating to gallery when dropdown is active."""
            return "break"
        
        app.sort_combo.bind("<MouseWheel>", prevent_gallery_scroll)
        app.sort_combo.bind("<Button-4>", prevent_gallery_scroll)
        app.sort_combo.bind("<Button-5>", prevent_gallery_scroll)

        ttk.Label(org_row, text="Tag:", font=app.small_font).pack(side='left', padx=(10, 8))
        app.gallery_tag_var = tk.StringVar(value='All tags')
        app.gallery_tag_combo = ttk.Combobox(org_row, textvariable=app.gallery_tag_var,
                                              values=['All tags'] + get_all_tags(),
                                              state="readonly", width=12)
        app.gallery_tag_combo.pack(side='left', padx=(0, 8))
        app.gallery_tag_combo.bind('<<ComboboxSelected>>', lambda e: app._on_tag_selected())
        
        # Enhanced scroll prevention for dropdown
        def prevent_gallery_scroll_tag(event):
            """Prevent scroll events from propagating to gallery when dropdown is active."""
            return "break"
        
        app.gallery_tag_combo.bind("<MouseWheel>", prevent_gallery_scroll_tag)
        app.gallery_tag_combo.bind("<Button-4>", prevent_gallery_scroll_tag)
        app.gallery_tag_combo.bind("<Button-5>", prevent_gallery_scroll_tag)

        _btn_tag = ttk.Button(org_row, text="Tag Image", command=app._gallery_tag_selected)
        _btn_tag.pack(side='left', padx=(0, 8))
        _btn_autotag = ttk.Button(org_row, text="Auto-Tag All", command=self._bulk_auto_tag)

        # Even distribution spacer between tag controls
        ttk.Frame(org_row).pack(side="left", fill="x", expand=True)
        _btn_autotag.pack(side='left')

        # Export Portraits button is created in app.py beside Tutorials / Open Folder



        # Thumbnails

        thumb_frame = ttk.Frame(parent)

        thumb_frame.pack(fill='both', expand=True)

        # --- Gallery canvas (shown in Gallery view) ---
        _init_pal = app.THEMES.get(app.current_theme_name, app.THEMES["darkforest"])
        app.gallery_canvas = tk.Canvas(thumb_frame, bg=_init_pal["bg"], highlightthickness=0)
        def _gallery_scrollbar_cmd(*args):
            app.gallery_canvas.yview(*args)
            app._on_gallery_scroll()
        app._gallery_scroll = ttk.Scrollbar(thumb_frame, orient='vertical', command=_gallery_scrollbar_cmd)
        app.gallery_inner = ttk.Frame(app.gallery_canvas, style="Inner.TFrame")
        app.gallery_canvas.bind('<Configure>', app.on_gallery_resize)
        app.gallery_canvas.create_window(0, 0, window=app.gallery_inner, anchor='nw', tags="inner_frame")
        app.gallery_canvas.configure(yscrollcommand=app._gallery_scroll.set)
        app.gallery_canvas.pack(side='left', fill='both', expand=True)
        app._gallery_scroll.pack(side='right', fill='y')

        # --- Favorites canvas (shown in Favorites view) ---
        app.gallery_fav_canvas = tk.Canvas(thumb_frame, bg=_init_pal["bg"], highlightthickness=0)
        gallery_fav_scroll = ttk.Scrollbar(thumb_frame, orient='vertical', command=app.gallery_fav_canvas.yview)
        app.gallery_fav_inner = ttk.Frame(app.gallery_fav_canvas, style="Inner.TFrame")
        app.gallery_fav_inner.bind("<Configure>", lambda e: app.gallery_fav_canvas.configure(
            scrollregion=app.gallery_fav_canvas.bbox("all")))
        app.gallery_fav_canvas.create_window((0, 0), window=app.gallery_fav_inner, anchor='nw', tags="fav_inner_frame")
        app.gallery_fav_canvas.configure(yscrollcommand=gallery_fav_scroll.set)
        app.gallery_fav_canvas.bind('<Configure>', app.on_fav_resize)
        # Hidden by default; revealed by _on_gallery_view_changed
        app._gallery_fav_scroll = gallery_fav_scroll
        app.gallery_favorites_ui = {"canvas": app.gallery_fav_canvas, "inner": app.gallery_fav_inner, "mode": "favorites"}

        # --- Styled canvas (shown in Styled view) ---
        app.gallery_styled_canvas = tk.Canvas(thumb_frame, bg=_init_pal["bg"], highlightthickness=0)
        gallery_styled_scroll = ttk.Scrollbar(thumb_frame, orient='vertical', command=app.gallery_styled_canvas.yview)
        app.gallery_styled_inner = ttk.Frame(app.gallery_styled_canvas, style="Inner.TFrame")
        app.gallery_styled_inner.bind("<Configure>", lambda e: app.gallery_styled_canvas.configure(
            scrollregion=app.gallery_styled_canvas.bbox("all")))
        app.gallery_styled_canvas.create_window((0, 0), window=app.gallery_styled_inner, anchor='nw', tags="styled_inner_frame")
        app.gallery_styled_canvas.configure(yscrollcommand=gallery_styled_scroll.set)
        app.gallery_styled_canvas.bind('<Configure>', app.on_styled_resize)
        # Hidden by default; revealed by _on_gallery_view_changed
        app._gallery_styled_scroll = gallery_styled_scroll
        app.gallery_styled_images = []  # List of styled image paths
        app.gallery_styled_cards = {}   # path -> card frame

        # --- Manual canvas (shown in Manual view) ---
        app.gallery_manual_canvas = tk.Canvas(thumb_frame, bg=_init_pal["bg"], highlightthickness=0)
        gallery_manual_scroll = ttk.Scrollbar(thumb_frame, orient='vertical', command=app.gallery_manual_canvas.yview)
        app.gallery_manual_inner = ttk.Frame(app.gallery_manual_canvas, style="Inner.TFrame")
        app.gallery_manual_inner.bind("<Configure>", lambda e: app.gallery_manual_canvas.configure(
            scrollregion=app.gallery_manual_canvas.bbox("all")))
        app.gallery_manual_canvas.create_window((0, 0), window=app.gallery_manual_inner, anchor='nw', tags="manual_inner_frame")
        app.gallery_manual_canvas.configure(yscrollcommand=gallery_manual_scroll.set)
        app.gallery_manual_canvas.bind('<Configure>', app.on_manual_resize)
        # Hidden by default; revealed by _on_gallery_view_changed
        app._gallery_manual_scroll = gallery_manual_scroll
        app.gallery_manual_images = []  # List of manual image paths
        app.gallery_manual_cards = {}   # path -> card frame

        # Selection tracking

        app.selected_gallery_path = None

        app.gallery_cards = {}  # path -> card frame

        app.drag_source_index = None

        # ── Mouse-wheel scrolling for all gallery canvases ─────────────
        # We track which canvas the mouse is hovering over and route wheel
        # events to that canvas so scrolling works without clicking first.
        app._hover_canvas = None

        def _bind_wheel(canvas):
            """Make *canvas* scrollable via mouse-wheel on hover."""
            def _on_enter(event):
                app._hover_canvas = canvas
            def _on_leave(event):
                if app._hover_canvas is canvas:
                    app._hover_canvas = None
            canvas.bind('<Enter>', _on_enter)
            canvas.bind('<Leave>', _on_leave)

        _bind_wheel(app.gallery_canvas)
        _bind_wheel(app.gallery_fav_canvas)
        _bind_wheel(app.gallery_styled_canvas)
        _bind_wheel(app.gallery_manual_canvas)

        def _on_mousewheel(event):
            # Prevent gallery scrolling if mouse is over dropdown widgets
            try:
                widget = event.widget
                widget_class = widget.winfo_class()
                # Check if the widget or any parent is a combobox or listbox
                current = widget
                while current:
                    class_name = current.winfo_class()
                    if "TCombobox" in class_name or "Listbox" in class_name:
                        return "break"
                    current = current.master
            except Exception:
                pass
            c = app._hover_canvas
            if c is not None:
                c.yview_scroll(int(-1 * (event.delta / 120)), "units")

        def _on_mousewheel_linux(event):
            # Prevent gallery scrolling if mouse is over dropdown widgets
            try:
                widget = event.widget
                widget_class = widget.winfo_class()
                # Check if the widget or any parent is a combobox or listbox
                current = widget
                while current:
                    class_name = current.winfo_class()
                    if "TCombobox" in class_name or "Listbox" in class_name:
                        return "break"
                    current = current.master
            except Exception:
                pass
            c = app._hover_canvas
            if c is not None:
                c.yview_scroll(int(-1 * event.delta), "units")

        app.root.bind_all("<MouseWheel>", _on_mousewheel)
        app.root.bind_all("<Button-4>", _on_mousewheel_linux)
        app.root.bind_all("<Button-5>", _on_mousewheel_linux)

        

        app.load_gallery()  # Initial load


    def _build_ratio_gallery_ui(self, filtered_images, ratio_mode, tag_filter):
        """Build the app.UI for ratio gallery (must run on main thread)."""
        app = self.app
        try:
            logger.info(f"Building ratio gallery UI for {ratio_mode} with {len(filtered_images)} images")
            app.gallery_images = filtered_images

            # Clear existing gallery cards and stale placeholders
            for widget in app.gallery_inner.winfo_children():
                widget.destroy()
            app.gallery_cards.clear()
            app._gallery_placeholders.clear()

            # Reset height so scrollregion isn't clamped by a stale value
            # from a previous empty-state or ratio view (Tk: height<=0 uses
            # the widget's natural height instead of a fixed pixel value).
            try:
                app.gallery_canvas.itemconfig("inner_frame", height=0)
            except Exception:
                pass

            # Empty-state message
            if not app.gallery_images:
                pal = app.THEMES.get(app.current_theme_name, app.THEMES["darkforest"])
                ratio_labels = {
                    "Ratio 16:9": "16:9 widescreen",
                    "Ratio 9:16": "Portrait",
                    "Ratio 1:1": "Square",
                }
                view_label = ratio_labels.get(ratio_mode, ratio_mode)
                if tag_filter:
                    message = f"No {view_label} images tagged '{tag_filter}'."
                else:
                    message = f"No {view_label} images found. Generate wallpapers in this size to see them here."
                app.gallery_inner.columnconfigure(0, weight=1)
                app.gallery_inner.rowconfigure(0, weight=1)
                tk.Label(
                    app.gallery_inner,
                    text=message,
                    bg=pal["bg"], fg=pal["text"], font=app.small_font,
                    pady=10,
                ).grid(row=0, column=0, sticky="nsew")
                # Make the inner frame fill the entire canvas so the empty
                # background blends with the theme instead of showing a box
                try:
                    cw = app.gallery_canvas.winfo_width()
                    ch = app.gallery_canvas.winfo_height()
                    if cw > 1 and ch > 1:
                        app.gallery_canvas.itemconfig("inner_frame", width=cw, height=ch)
                except Exception:
                    pass
                app.gallery_canvas.configure(
                    scrollregion=app.gallery_canvas.bbox("all") or (0, 0, 1, 1)
                )
                app.status_var.set(f'{ratio_mode}: 0 images')
                logger.info(f"Ratio gallery UI built: 0 images")
                return

            # Create placeholder cards first for immediate UI response
            pal = app.THEMES.get(app.current_theme_name, app.THEMES["darkforest"])
            border = pal.get("border_color", pal["panel2"])

            for idx, img_path in enumerate(app.gallery_images):
                cols = min(3, max(1, app.gallery_canvas.winfo_width() // 260))
                row, col = idx // cols, idx % cols
                self._create_placeholder_card(img_path, row, col, idx, pal, border)

            app.gallery_canvas.configure(
                scrollregion=app.gallery_canvas.bbox("all") or (0, 0, 1, 1)
            )
            app.status_var.set(f'{ratio_mode}: {len(app.gallery_images)} images (loading thumbnails...)')

            # Load thumbnails in background to prevent UI freeze
            # Bump generation counter so any previous ratio-load thread aborts
            self._ratio_load_gen += 1
            gen = self._ratio_load_gen
            run_background(self._load_thumbnails_lazy, ratio_mode, gen)
            logger.info(f"Ratio gallery UI built: {len(app.gallery_images)} images, thumbnails loading started (gen={gen})")

        except Exception as e:
            app.status_var.set(f'Error building ratio gallery: {e}')


    def _create_heart_button(self, parent, img_path, pal):
        """Create a heart button for favoriting images."""
        app = self.app
        try:
            from icons import get_icon
            accent = pal.get("accent", pal["progress"])
            
            # Check if image is already favorited
            is_favorited = self._is_image_favorited(img_path)
            heart_name = "heart_filled" if is_favorited else "heart_outline"
            heart_icon = get_icon(heart_name, size=36, color=accent)  # Doubled from 18 to 36
            
            # Create button with heart icon — match parent bg so no square
            # outline is visible around the star shape.
            parent_bg = pal.get("panel", "#1e1e2e")
            try:
                parent_bg = parent.cget("bg")
            except Exception:
                pass
            heart_btn = tk.Button(parent, image=heart_icon,
                                 bg=parent_bg,
                                 activebackground=pal.get("panel2", parent_bg),
                                 bd=0, highlightthickness=0,
                                 cursor="hand2", relief="flat")
            heart_btn.image = heart_icon  # prevent GC
            heart_btn._icon_ref = heart_icon
            heart_btn._img_path = img_path  # store path for toggle
            
            # Bind click event to toggle favorite
            heart_btn.bind('<Button-1>', lambda e, p=img_path: self._on_heart_click(e, p, heart_btn))
            
            return heart_btn
        except Exception as e:
            logger.error(f"Error creating heart button: {e}")
            return None

    def _on_heart_click(self, event, img_path, heart_btn):
        """Handle heart button click to toggle favorite status."""
        app = self.app

        # Check current state before toggling
        was_favorited = self._is_image_favorited(img_path)

        # Toggle favorite status
        self._toggle_image_favorite(img_path)

        # Update heart icon based on the new state (opposite of old state)
        try:
            from icons import get_icon
            pal = app.THEMES.get(app.current_theme_name, app.THEMES["darkforest"])
            accent = pal.get("accent", pal["progress"])
            # If it was favorited, now it's not (outline). If it wasn't, now it is (filled)
            heart_name = "heart_outline" if was_favorited else "heart_filled"
            heart_icon = get_icon(heart_name, size=36, color=accent)  # Doubled from 18 to 36
            heart_btn.configure(image=heart_icon)
            heart_btn.image = heart_icon
            heart_btn._icon_ref = heart_icon
        except Exception as e:
            logger.error(f"Error updating heart icon: {e}")

        # Refresh the Favorites view so the grid stays in sync (item added or
        # removed). Other views (Gallery/Styled/Manual/Ratio) don't need a
        # full rebuild here — the heart icon was already updated locally
        # above, and _is_image_favorited now also checks the favorites folder
        # by basename, so the heart state will be correct when the user
        # switches away and back.
        try:
            if app._gallery_view_mode() == "Favorites":
                app.load_favorites()
        except Exception as e:
            logger.warning(f"Heart-click favorites refresh failed: {e}")

    def _on_fav_heart_click(self, event, img_path, item, heart_btn):
        """Handle heart button click on favorites card to remove from favorites."""
        app = self.app
        # Remove from favorites
        try:
            existing = load_json_list(app.FAVORITES_LOG)
            original_resolved = Path(img_path).resolve()
            
            # Find and remove the item
            favorited_index = None
            for i, fav_item in enumerate(existing):
                if fav_item.get('copied_image_path') and Path(fav_item.get('copied_image_path')).resolve() == original_resolved:
                    favorited_index = i
                    break
            
            if favorited_index is not None:
                entry = existing.pop(favorited_index)
                save_json_list(app.FAVORITES_LOG, existing)
                
                # Optionally delete the copied file
                try:
                    copied_path = entry.get('copied_image_path')
                    if copied_path and Path(copied_path).exists():
                        if app.FAVORITES_DIR in Path(copied_path).parents:
                            Path(copied_path).unlink()
                except Exception:
                    pass
                
                app.status_var.set(f'💔 Removed from favorites: {Path(img_path).name}')
            else:
                app.status_var.set('Item not found in favorites')
                
        except Exception as e:
            app.status_var.set(f'Error removing from favorites: {e}')
            logger.error(f"Error removing from favorites: {e}")
        
        # Always refresh favorites view after removal
        app.load_favorites()

    def _create_placeholder_card(self, img_path, row, col, index, pal, border):
        """Create a placeholder card without loading the thumbnail (for lazy loading)."""
        app = self.app
        card = tk.Frame(app.gallery_inner, bg=pal["panel"],
                        highlightthickness=1, highlightbackground=border, bd=0)
        card.grid(row=row, column=col, padx=6, pady=6, sticky='nsew')
        card.columnconfigure(0, weight=1)

        # Placeholder label
        placeholder = tk.Label(card, text="Loading...", bg=pal["panel"], fg=pal["muted"],
                             font=app.small_font, width=30, height=8)
        placeholder.grid(row=0, column=0, pady=(4, 4), padx=4)

        # Name label
        name_label = tk.Label(card, text=img_path.name,
                             wraplength=220, height=2, font=app.small_font,
                             bg=pal["panel"], fg=pal["text"],
                             anchor="w", justify="left", padx=6, pady=2)
        name_label.grid(row=1, column=0, sticky='ew')

        # File size + resolution info (dimensions via shared cache)
        try:
            size_bytes = img_path.stat().st_size
            size_str = f"{size_bytes / 1_048_576:.1f} MB" if size_bytes >= 1_048_576 else f"{size_bytes / 1024:.0f} KB"
            w_px, h_px = self._img_dims(img_path)
            info_text = f"{w_px}\u00d7{h_px}  \u2022  {size_str}" if w_px and h_px else size_str
        except Exception:
            info_text = ""
        info_label = tk.Label(card, text=info_text, fg=pal["muted"], font=app.tinyfont,
                              bg=pal["panel"], anchor="w", justify="left", padx=6, pady=0)
        info_label.grid(row=2, column=0, sticky='ew')

        # Tags label
        tags = get_tags_for_image(img_path) or []
        tags_label = tk.Label(card, text=', '.join(tags[:3]),
                              fg=pal.get("tag_fg", pal["muted"]), font=app.small_font,
                              bg=pal["panel"], anchor="w", justify="left", padx=6, pady=4)
        tags_label.grid(row=3, column=0, sticky='ew')

        # Heart button (positioned in bottom-right corner)
        heart_btn = self._create_heart_button(card, img_path, pal)
        if heart_btn:
            heart_btn.place(relx=1.0, rely=1.0, x=-12, y=-12, anchor="se")  # Adjusted for larger icon

        # Store placeholder reference for later replacement
        app.gallery_cards[str(img_path)] = (card, placeholder, name_label, row, col, index, heart_btn)

        # Bind click events to card
        card.bind('<Button-1>', lambda e, p=img_path, idx=index: app.on_card_click(e, p, idx))
        card.bind('<Button-3>', lambda e, p=img_path: app.show_gallery_context_menu(e, p))
        placeholder.bind('<Button-1>', lambda e, p=img_path, idx=index: app.on_card_click(e, p, idx))
        placeholder.bind('<Button-3>', lambda e, p=img_path: app.show_gallery_context_menu(e, p))
        name_label.bind('<Button-1>', lambda e, p=img_path, idx=index: app.on_card_click(e, p, idx))
        for sub in (info_label, tags_label):
            sub.bind('<Button-1>', lambda e, p=img_path, idx=index: app.on_card_click(e, p, idx))

    def _load_thumbnails_lazy(self, ratio_mode, generation):
        """Load thumbnails in background thread and update UI on main thread.

        *generation* is the load-generation counter captured at dispatch time.
        If a newer load has started, this thread aborts early.
        """
        app = self.app
        try:
            from PIL import Image, ImageTk

            for idx, img_path in enumerate(app.gallery_images):
                # Abort if a newer load cycle has started or view changed entirely
                if generation != self._ratio_load_gen:
                    return
                current_view = app.gallery_view_var.get()
                if current_view != ratio_mode:
                    return

                path_str = str(img_path)
                card_data = app.gallery_cards.get(path_str)

                if not card_data:
                    continue

                # Handle both 6-element (old) and 7-element (new with heart button) card data
                if len(card_data) == 7:
                    card, placeholder, name_label, row, col, index, heart_btn = card_data
                else:
                    card, placeholder, name_label, row, col, index = card_data
                    heart_btn = None

                # Capture current theme palette for closures (read from thread-safe config)
                pal = app.THEMES.get(app.current_theme_name, app.THEMES["darkforest"])

                # Check if thumbnail is already cached (on main thread later)
                cached = path_str in app.thumb_cache

                if cached:
                    thumb = app.thumb_cache[path_str]
                    def update_card(_card=card, _placeholder=placeholder, _thumb=thumb,
                                   _img_path=img_path, _index=index, _pal=pal,
                                   _gen=generation):
                        if _gen != self._ratio_load_gen:
                            return
                        try:
                            _placeholder.destroy()
                            label = tk.Label(_card, image=_thumb, bg=_pal["panel"])
                            label.grid(row=0, column=0, pady=(4, 4), padx=4)
                            label.bind('<Button-1>', lambda e, p=_img_path, idx=_index: app.on_card_click(e, p, idx))
                            label.bind('<Button-3>', lambda e, p=_img_path: app.show_gallery_context_menu(e, p))
                        except Exception as e:
                            logger.error(f"Error updating card UI: {e}")
                    schedule_ui_update(update_card)
                else:
                    # Prepare PIL thumbnail in this thread; defer ImageTk to main thread
                    try:
                        img = Image.open(img_path)
                        img.thumbnail((240, 135), Image.Resampling.LANCZOS)
                    except Exception as e:
                        logger.error(f"Thumbnail loading error for {img_path}: {e}")
                        continue

                    def update_card(_card=card, _placeholder=placeholder, _pil_img=img,
                                   _img_path=img_path, _index=index, _pal=pal,
                                   _gen=generation, _path_str=path_str):
                        if _gen != self._ratio_load_gen:
                            return
                        try:
                            thumb = ImageTk.PhotoImage(_pil_img)
                            if len(app.thumb_cache) > 200:
                                app.thumb_cache.clear()
                            app.thumb_cache[_path_str] = thumb
                            _placeholder.destroy()
                            label = tk.Label(_card, image=thumb, bg=_pal["panel"])
                            label.grid(row=0, column=0, pady=(4, 4), padx=4)
                            label.bind('<Button-1>', lambda e, p=_img_path, idx=_index: app.on_card_click(e, p, idx))
                            label.bind('<Button-3>', lambda e, p=_img_path: app.show_gallery_context_menu(e, p))
                        except Exception as e:
                            logger.error(f"Error updating card UI: {e}")
                    schedule_ui_update(update_card)

            # Update status when done
            if generation == self._ratio_load_gen:
                def update_status():
                    app.status_var.set(f'{ratio_mode}: {len(app.gallery_images)} images')
                schedule_ui_update(update_status)

        except Exception as e:
            error_msg = f'Error loading thumbnails: {e}'
            schedule_ui_update(app.status_var.set, error_msg)

    def _copy_prompt_to_clipboard(self):
        """Copy the current prompt text to the system clipboard."""
        app = self.app
        prompt = app.prompt_text.get("1.0", "end-1c").strip()
        if prompt:
            app.root.clipboard_clear()
            app.root.clipboard_append(prompt)
            app.status_var.set("Prompt copied to clipboard!")
        else:
            app.status_var.set("No prompt to copy.")

    def _bulk_auto_tag(self):
        """Scan all generated/styled/manual images and auto-tag from filenames,
        then clean up any tags referencing deleted images.

        Filename formats:
          - Generated/Manual: SUBJECT_STYLE_YYYYMMDD_N.ext
          - Styled: SUBJECT_STYLE_YYYYMMDD_N_stylefilter.ext
        Extracts subject and style as tags for any untagged image.
        """
        import re as _re
        app = self.app
        try:
            from set_wallpaper import MANUAL_DIR, GENERATED_DIR
        except ImportError:
            app.status_var.set('Auto-tag: could not find wallpaper directories.')
            return

        # Build list of directories to scan
        search_dirs = [GENERATED_DIR, MANUAL_DIR]
        if hasattr(app, 'STYLED_DIR') and app.STYLED_DIR.exists():
            search_dirs.append(app.STYLED_DIR)

        app.status_var.set('Auto-tagging images from filenames...')
        app.root.update_idletasks()

        # Pattern: SUBJECT_STYLE_YYYYMMDD_N.ext  (generated/manual)
        filename_re = _re.compile(r'^([a-z0-9_]+)_([a-z0-9]+)_\d{8}_\d+\.', _re.IGNORECASE)
        # Pattern: SUBJECT_STYLE_YYYYMMDD_N_STYLEFILTER.ext  (styled)
        styled_filename_re = _re.compile(r'^([a-z0-9_]+)_([a-z0-9]+)_\d{8}_\d+_([a-z0-9_]+)\.', _re.IGNORECASE)

        tagged_count = 0
        skipped_count = 0
        error_count = 0

        for search_dir in search_dirs:
            if not search_dir.exists():
                continue
            for img_file in search_dir.iterdir():
                if not img_file.is_file() or img_file.suffix.lower() not in {'.png', '.jpg', '.jpeg', '.webp'}:
                    continue

                # Try styled pattern first (has extra _stylefilter segment)
                m = styled_filename_re.match(img_file.name)
                if m:
                    raw_subject = m.group(1).replace('_', ' ')
                    raw_style = m.group(2).replace('_', ' ')
                    style_filter = m.group(3).replace('_', ' ')
                else:
                    # Fall back to standard generated/manual pattern
                    m = filename_re.match(img_file.name)
                    if not m:
                        skipped_count += 1
                        continue
                    raw_subject = m.group(1).replace('_', ' ')
                    raw_style = m.group(2).replace('_', ' ')
                    style_filter = None

                # Skip generic filenames
                if raw_subject.lower() in ('wallpaper', 'unknown', 'image'):
                    skipped_count += 1
                    continue
                tags = [raw_subject]
                if raw_style.lower() != raw_subject.lower():
                    tags.append(raw_style)
                if style_filter and style_filter.lower() not in (raw_subject.lower(), raw_style.lower()):
                    tags.append(style_filter)
                try:
                    add_tags_to_image(img_file, tags)
                    tagged_count += 1
                except Exception:
                    error_count += 1

        # Clean up tags for images that no longer exist on disk
        try:
            cleaned = cleanup_orphaned_tags()
        except Exception:
            cleaned = 0

        app._refresh_gallery_tag_filter()
        cleanup_note = f', {cleaned} stale tags removed' if cleaned else ''
        app.status_var.set(f'Auto-tag complete: {tagged_count} tagged, {skipped_count} skipped, {error_count} errors{cleanup_note}')


    def _create_manual_card(self, img_path, index, pal, border):
        """Create a card for a manual image."""
        app = self.app
        cols = min(3, max(1, app.gallery_manual_canvas.winfo_width() // 260))
        row, col = index // cols, index % cols

        card = tk.Frame(app.gallery_manual_inner, bg=pal["panel"],
                       highlightthickness=1, highlightbackground=border, bd=0)
        card.grid(row=row, column=col, padx=6, pady=6, sticky='nsew')
        card.columnconfigure(0, weight=1)

        # Thumbnail — decoded off the UI thread when not cached (perf)
        try:
            label = self._attach_card_thumb(
                card, pal, img_path,
                pack_kwargs={"pady": (4, 4), "padx": 4},
                on_click=lambda e, p=img_path: app._select_manual_image(p),
                on_double=lambda e, p=img_path: app.set_gallery_image_as_wallpaper(p),
                on_context=lambda e, p=img_path: app.show_gallery_context_menu(e, p),
            )

            card.bind('<Button-1>', lambda e, p=img_path: app._select_manual_image(p))
            card.bind('<Button-3>', lambda e, p=img_path: app.show_gallery_context_menu(e, p))

        except Exception as e:
            logger.error(f"Manual thumbnail error for {img_path}: {e}")
            tk.Label(card, text=f'❌ {img_path.name}', bg='red', fg='white').pack()

        # Name label
        name_label = tk.Label(card, text=img_path.name,
                             wraplength=220, height=2, font=app.small_font,
                             bg=pal["panel"], fg=pal["text"],
                             anchor="w", justify="left", padx=6, pady=2)
        name_label.pack(fill="x")
        name_label.bind('<Button-1>', lambda e, p=img_path: app._select_manual_image(p))

        # File size + resolution info (dimensions via shared cache)
        try:
            size_bytes = img_path.stat().st_size
            size_str = f"{size_bytes / 1_048_576:.1f} MB" if size_bytes >= 1_048_576 else f"{size_bytes / 1024:.0f} KB"
            w_px, h_px = self._img_dims(img_path)
            info_text = f"{w_px}\u00d7{h_px}  \u2022  {size_str}" if w_px and h_px else size_str
        except Exception:
            info_text = ""
        info_label = tk.Label(card, text=info_text, fg=pal["muted"], font=app.tinyfont,
                              bg=pal["panel"], anchor="w", justify="left", padx=6, pady=0)
        info_label.pack(fill="x")
        info_label.bind('<Button-1>', lambda e, p=img_path: app._select_manual_image(p))

        # Tags label
        tags = get_tags_for_image(img_path) or []
        tags_label = tk.Label(card, text=', '.join(tags[:3]),
                              fg=pal.get("tag_fg", pal["muted"]), font=app.small_font,
                              bg=pal["panel"], anchor="w", justify="left", padx=6, pady=4)
        tags_label.pack(fill="x")
        tags_label.bind('<Button-1>', lambda e, p=img_path: app._select_manual_image(p))

        # Heart button (positioned in bottom-right corner)
        heart_btn = self._create_heart_button(card, img_path, pal)
        if heart_btn:
            heart_btn.place(relx=1.0, rely=1.0, x=-12, y=-12, anchor="se")  # Adjusted for larger icon

        app.gallery_manual_cards[str(img_path)] = (card, name_label, heart_btn)


    def _create_styled_card(self, img_path, index, pal, border):
        """Create a card for a styled image."""
        app = self.app
        cols = min(3, max(1, app.gallery_styled_canvas.winfo_width() // 260))
        row, col = index // cols, index % cols

        card = tk.Frame(app.gallery_styled_inner, bg=pal["panel"],
                       highlightthickness=1, highlightbackground=border, bd=0)
        card.grid(row=row, column=col, padx=6, pady=6, sticky='nsew')
        card.columnconfigure(0, weight=1)

        # Thumbnail — decoded off the UI thread when not cached (perf)
        try:
            label = self._attach_card_thumb(
                card, pal, img_path,
                pack_kwargs={"pady": (4, 4), "padx": 4},
                on_click=lambda e, p=img_path: app._select_styled_image(p),
                on_double=lambda e, p=img_path: app.set_gallery_image_as_wallpaper(p),
                on_context=lambda e, p=img_path: app.show_gallery_context_menu(e, p),
            )

            card.bind('<Button-1>', lambda e, p=img_path: app._select_styled_image(p))
            card.bind('<Button-3>', lambda e, p=img_path: app.show_gallery_context_menu(e, p))

        except Exception as e:
            logger.error(f"Styled thumbnail error for {img_path}: {e}")
            tk.Label(card, text=f'❌ {img_path.name}', bg='red', fg='white').pack()

        # Name label
        name_label = tk.Label(card, text=img_path.name,
                             wraplength=220, height=2, font=app.small_font,
                             bg=pal["panel"], fg=pal["text"],
                             anchor="w", justify="left", padx=6, pady=2)
        name_label.pack(fill="x")
        name_label.bind('<Button-1>', lambda e, p=img_path: app._select_styled_image(p))

        # File size + resolution info (dimensions via shared cache)
        try:
            size_bytes = img_path.stat().st_size
            size_str = f"{size_bytes / 1_048_576:.1f} MB" if size_bytes >= 1_048_576 else f"{size_bytes / 1024:.0f} KB"
            w_px, h_px = self._img_dims(img_path)
            info_text = f"{w_px}\u00d7{h_px}  \u2022  {size_str}" if w_px and h_px else size_str
        except Exception:
            info_text = ""
        info_label = tk.Label(card, text=info_text, fg=pal["muted"], font=app.tinyfont,
                              bg=pal["panel"], anchor="w", justify="left", padx=6, pady=0)
        info_label.pack(fill="x")
        info_label.bind('<Button-1>', lambda e, p=img_path: app._select_styled_image(p))

        # Tags label (fall back to original image's tags for styled copies)
        tags = self._get_tags_with_fallback(img_path)
        tags_label = tk.Label(card, text=', '.join(tags[:3]),
                              fg=pal.get("tag_fg", pal["muted"]), font=app.small_font,
                              bg=pal["panel"], anchor="w", justify="left", padx=6, pady=4)
        tags_label.pack(fill="x")
        tags_label.bind('<Button-1>', lambda e, p=img_path: app._select_styled_image(p))

        # Heart button (positioned in bottom-right corner)
        heart_btn = self._create_heart_button(card, img_path, pal)
        if heart_btn:
            heart_btn.place(relx=1.0, rely=1.0, x=-12, y=-12, anchor="se")

        app.gallery_styled_cards[str(img_path)] = (card, name_label, heart_btn)


    def _delete_styled_image(self):
        """Delete selected styled image from the styled folder."""
        app = self.app
        if not app.selected_gallery_path:
            app._dialog.warning("No Selection", "Select a styled image first.")
            return

        if not app.selected_gallery_path.exists():
            app._dialog.warning("File Not Found", "The selected image no longer exists.")
            return

        confirm = app._dialog.ask(
            "Confirm Delete",
            f"Delete styled image:\n{app.selected_gallery_path.name}\n\nThis cannot be undone."
        )
        if not confirm:
            return

        try:
            app.selected_gallery_path.unlink()
            app.status_var.set(f'🗑️ Deleted styled image: {app.selected_gallery_path.name}')
            app.selected_gallery_path = None
            app.load_styled()  # Refresh styled view
        except Exception as e:
            app._dialog.error("Delete Failed", "Could not delete the file. It may be in use by another program — close any apps using it and try again.")


    def _do_sort_gallery_reload(self):
        """Perform the actual gallery reload after combobox closes."""
        app = self.app
        current_sort = app.sort_combo_var.get()

        if current_sort in ["Date Newest", "Date Oldest"]:
            app.gallery_sort_mode = "date"
        elif current_sort in ["Name A-Z", "Name Z-A"]:
            app.gallery_sort_mode = "name"
        elif current_sort in ["Size Largest", "Size Smallest"]:
            app.gallery_sort_mode = "size"
        elif current_sort in ["Resolution Largest", "Resolution Smallest"]:
            app.gallery_sort_mode = "resolution"
        else:
            app.gallery_sort_mode = "date"  # Default fallback

        tag_filter = app.get_active_tag()
        view_mode = app._gallery_view_mode()
        if view_mode == "Favorites":
            app.load_favorites(tag_filter=tag_filter)
        elif view_mode == "Styled":
            app.load_styled(tag_filter=tag_filter)
        elif view_mode == "Manual":
            app.load_manual(tag_filter=tag_filter)
        elif view_mode in ["Ratio 16:9", "Ratio 9:16", "Ratio 1:1"]:
            # Show loading indicator
            app.status_var.set(f'Loading {view_mode} images...')
            app.root.update_idletasks()
            # Load in background thread to prevent UI freeze
            run_background(app.load_gallery_by_ratio, view_mode, tag_filter)
        else:  # Gallery
            app.load_gallery()


    def _double_click_visual_item(self, ui, path, data):
        app = self.app
        app._select_visual_item(ui, path, data)
        if path:
            app.double_click_set_wallpaper(path)


    def _fav_widget_to_card_index(self, widget):
        app = self.app
        return None  # Organize Mode removed


    def _gallery_add_text(self):
        """Add Text Overlay — click-to-position, font selection, live preview, bold/italic fix."""
        app = self.app
        if app._gallery_view_mode() == "Favorites":
            if not app.favorite_selected_item:
                app._dialog.warning("No Selection", "Select a Favorite thumbnail first.")
                return
            path_str = app.favorite_selected_item.get("image_path") or \
                       app.favorite_selected_item.get("copied_image_path")
            if not path_str or not Path(path_str).exists():
                app._dialog.warning("No Image", "Selected favorite has no valid image file.")
                return
            app.selected_gallery_path = Path(path_str)
        
        if not app.selected_gallery_path or not app.selected_gallery_path.exists():
            app._dialog.warning("No Selection", "Select an image thumbnail first.")
            return

        img_path = app.selected_gallery_path
        pal = app.THEMES.get(app.current_theme_name, app.THEMES["darkforest"])

        # ── Curated font list with per-font preview ──
        import sys
        discovered_fonts = {}  # display_name -> file_path

        # Hand-picked fonts commonly available on the OS
        # (display_name, filename_on_windows, [linux_font_names])
        curated = [
            ("Arial",                   "arial.ttf",         ["Arial"]),
            ("Arial Black",             "ariblk.ttf",        ["Arial Black"]),
            ("Calibri",                 "calibri.ttf",       ["Calibri"]),
            ("Cambria",                 "cambria.ttc",       ["Cambria"]),
            ("Comic Sans MS",           "comic.ttf",         ["Comic Sans MS"]),
            ("Consolas",                "consola.ttf",       ["Consolas"]),
            ("Courier New",             "cour.ttf",          ["Courier New"]),
            ("Georgia",                 "georgia.ttf",       ["Georgia"]),
            ("Impact",                  "impact.ttf",        ["Impact"]),
            ("Segoe UI",                "segoeui.ttf",       ["Segoe UI"]),
            ("Tahoma",                  "tahoma.ttf",        ["Tahoma"]),
            ("Times New Roman",         "times.ttf",         ["Times New Roman"]),
            ("Trebuchet MS",            "trebuc.ttf",        ["Trebuchet MS"]),
            ("Verdana",                 "verdana.ttf",       ["Verdana"]),
        ]

        def _discover(display_name, win_file, linux_names):
            # Try full path discovery
            if sys.platform == "win32":
                font_dir = Path(os.environ.get("WINDIR", r"C:\\Windows")) / "Fonts"
                candidate = font_dir / win_file
                if candidate.exists():
                    discovered_fonts[display_name] = str(candidate)
                    return True
            # Try Linux / macOS via matplotlib / PIL
            for ln in linux_names:
                try:
                    import matplotlib.font_manager as _fm
                    for f in _fm.findSystemFonts():
                        if ln.lower() in Path(f).stem.lower():
                            discovered_fonts[display_name] = f
                            return True
                except Exception:
                    pass
            # Try PIL font manager (Pillow >= 10.1)
            try:
                from PIL import FontManager
                fm = FontManager()
                for ln in linux_names:
                    p = fm.findfont(ln, fallback_to_default=False)
                    if p and Path(p).exists():
                        discovered_fonts[display_name] = p
                        return True
            except Exception:
                pass
            return False

        for name, wfile, lnames in curated:
            _discover(name, wfile, lnames)

        font_names = [name for name, _, _ in curated if name in discovered_fonts]
        if not font_names:
            font_names = ["Default"]

        # ── Create dialog ──
        dialog = tk.Toplevel(app.root)
        dialog.title("Add Text Overlay")
        dialog.geometry("920x860")
        dialog.minsize(840, 760)
        dialog.transient(app.root)
        dialog.grab_set()
        dialog.configure(bg=pal["bg"])

        from utils import center_window
        center_window(app.root, dialog)

        # ── Main layout: left controls (fixed width), right preview (expanding) ──
        main_frame = ttk.Frame(dialog)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Left: scrollable control panel
        ctrl_outer = ttk.Frame(main_frame, width=310)
        ctrl_outer.pack(side="left", fill="y", padx=(0, 10))
        ctrl_outer.pack_propagate(False)

        ctrl_canvas = tk.Canvas(ctrl_outer, highlightthickness=0, bg=pal["bg"])
        ctrl_scrollbar = ttk.Scrollbar(ctrl_outer, orient="vertical", command=ctrl_canvas.yview)
        ctrl_frame = ttk.Frame(ctrl_canvas)

        _ctrl_win_id = ctrl_canvas.create_window((0, 0), window=ctrl_frame, anchor="nw")
        ctrl_canvas.configure(yscrollcommand=ctrl_scrollbar.set)

        # When canvas resizes, stretch inner frame to match width
        def _on_ctrl_canvas_configure(event):
            ctrl_canvas.itemconfig(_ctrl_win_id, width=event.width)
        ctrl_canvas.bind("<Configure>", _on_ctrl_canvas_configure)

        # When inner frame content changes, update scroll region
        def _on_ctrl_frame_configure(event):
            ctrl_canvas.configure(scrollregion=ctrl_canvas.bbox("all"))
        ctrl_frame.bind("<Configure>", _on_ctrl_frame_configure)

        ctrl_canvas.pack(side="left", fill="both", expand=True)
        ctrl_scrollbar.pack(side="right", fill="y")

        # Mouse wheel scrolling — only when pointer is over the left panel
        def _on_ctrl_mousewheel(event):
            ctrl_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            return "break"
        ctrl_canvas.bind("<MouseWheel>", _on_ctrl_mousewheel)
        ctrl_frame.bind("<MouseWheel>", _on_ctrl_mousewheel)
        # Also bind to all children recursively when they're mapped
        def _bind_mousewheel_to_children(widget):
            widget.bind("<MouseWheel>", _on_ctrl_mousewheel)
            for child in widget.winfo_children():
                _bind_mousewheel_to_children(child)
        ctrl_frame.bind("<Map>", lambda e: _bind_mousewheel_to_children(ctrl_frame), add="+")

        # Right: preview area (expanding)
        right_frame = ttk.Frame(main_frame)
        right_frame.pack(side="left", fill="both", expand=True)

        # ── Variables ──
        text_var = tk.StringVar()
        custom_pos = [None, None]  # [frac_x, frac_y] or [None, None] for preset
        position_var = tk.StringVar(value="bottom-right")
        font_size_var = tk.IntVar(value=36)
        color_var = tk.StringVar(value="white")
        outline_color_var = tk.StringVar(value="black")
        outline_width_var = tk.IntVar(value=2)
        bold_var = tk.BooleanVar(value=False)
        italic_var = tk.BooleanVar(value=False)
        underline_var = tk.BooleanVar(value=False)
        opacity_var = tk.IntVar(value=100)
        shadow_var = tk.BooleanVar(value=False)
        font_name_var = tk.StringVar(value=font_names[0] if font_names else "Default")

        # ── Text input ──
        ttk.Label(ctrl_frame, text="Text:").pack(anchor="w", pady=(0, 2))
        text_entry = ttk.Entry(ctrl_frame, textvariable=text_var, width=30)
        text_entry.pack(fill="x", pady=(0, 8))
        text_entry.focus()

        # ── Font list with per-font preview ──
        ttk.Label(ctrl_frame, text="Font:").pack(anchor="w", pady=(0, 2))
        font_listbox = tk.Listbox(ctrl_frame, height=6, exportselection=False,
                                   bg=pal["panel2"], fg=pal["text"],
                                   selectbackground=pal["accent"],
                                   selectforeground=pal["bg"],
                                   highlightthickness=1,
                                   highlightbackground=pal.get("border_color", pal["panel2"]),
                                   font=("TkDefaultFont", 11),
                                   relief="flat", bd=2)
        font_listbox.pack(fill="x", pady=(0, 8))

        # Populate listbox — render each font name in its own font
        for i, fname in enumerate(font_names):
            font_listbox.insert(tk.END, fname)
            fpath = discovered_fonts.get(fname)
            if fpath:
                try:
                    preview_font = (fpath, 13)
                    font_listbox.itemconfig(i, font=preview_font)
                except Exception:
                    pass

        if font_names:
            font_listbox.select_set(0)
            font_name_var.set(font_names[0])

        def _on_font_select(event):
            sel = font_listbox.curselection()
            if sel:
                font_name_var.set(font_names[sel[0]])

        font_listbox.bind("<<ListboxSelect>>", _on_font_select)

        # ── Font size ──
        size_row = ttk.Frame(ctrl_frame)
        size_row.pack(fill="x", pady=(0, 8))
        ttk.Label(size_row, text="Size:").pack(side="left")
        ttk.Spinbox(size_row, from_=12, to=200, textvariable=font_size_var, width=6).pack(side="right")

        # ── Bold / Italic / Underline row ──
        style_row = ttk.Frame(ctrl_frame)
        style_row.pack(fill="x", pady=(0, 8))
        ttk.Checkbutton(style_row, text="Bold", variable=bold_var).pack(side="left")
        ttk.Checkbutton(style_row, text="Italic", variable=italic_var).pack(side="left", padx=(12, 0))
        ttk.Checkbutton(style_row, text="Underline", variable=underline_var).pack(side="left", padx=(12, 0))

        # ── Color picker helper ──
        def _pick_color(target_var):
            from tkinter import colorchooser
            try:
                initial = target_var.get()
                if initial.lower() == "none":
                    initial = COLOR_BLACK
                result = colorchooser.askcolor(initialcolor=initial, title="Choose Color",
                                                parent=dialog)
                if result and result[1]:
                    target_var.set(result[1])
            except Exception:
                pass

        # ── Text color ──
        ttk.Label(ctrl_frame, text="Text Color:").pack(anchor="w", pady=(0, 2))
        text_color_row = ttk.Frame(ctrl_frame)
        text_color_row.pack(fill="x", pady=(0, 8))
        color_combo = ttk.Combobox(text_color_row, textvariable=color_var,
                                     values=["white", "black", "red", "blue", "green",
                                             "yellow", "cyan", "magenta", "orange", "pink",
                                             "lime", "turquoise", "navy", "maroon", "olive",
                                             "teal", "aqua", "fuchsia", "coral", "salmon",
                                             "gold", "khaki", "violet", "indigo",
                                             "#FF6B6B", "4ECDC4", "FFE66D", "95E1D3",
                                             "#C0392B", "#8E44AD", "#2980B9", "#27AE60",
                                             "#F39C12", "#1ABC9C", "#E74C3C", "#3498DB"],
                                     state="readonly", width=24)
        color_combo.pack(side="left", fill="x", expand=True)
        ttk.Button(text_color_row, text=chr(0x270F), width=3,
                   command=lambda: _pick_color(color_var)).pack(side="right", padx=(4, 0))
        text_swatch = tk.Canvas(text_color_row, width=24, height=20,
                                bg=color_var.get(), highlightthickness=1,
                                highlightbackground=pal.get("border_color", pal["panel2"]))
        text_swatch.pack(side="right", padx=(4, 0))
        def _update_text_swatch(*args):
            try:
                text_swatch.configure(bg=color_var.get())
            except Exception:
                pass
        color_var.trace_add("write", _update_text_swatch)

        # ── Outline color ──
        ttk.Label(ctrl_frame, text="Outline Color:").pack(anchor="w", pady=(0, 2))
        outline_color_row = ttk.Frame(ctrl_frame)
        outline_color_row.pack(fill="x", pady=(0, 8))
        outline_combo = ttk.Combobox(outline_color_row, textvariable=outline_color_var,
                                      values=["black", "white", "darkgray", "gray", "lightgray",
                                              "red", "blue", "green", "yellow", "none",
                                              "#333333", COLOR_BLACK, COLOR_WHITE, "#FF0000",
                                              "#00FF00", "#0000FF", "#FFFF00", "#FF00FF"],
                                      state="readonly", width=24)
        outline_combo.pack(side="left", fill="x", expand=True)
        ttk.Button(outline_color_row, text=chr(0x270F), width=3,
                   command=lambda: _pick_color(outline_color_var)).pack(side="right", padx=(4, 0))
        outline_swatch = tk.Canvas(outline_color_row, width=24, height=20,
                                   bg=outline_color_var.get(), highlightthickness=1,
                                   highlightbackground=pal.get("border_color", pal["panel2"]))
        outline_swatch.pack(side="right", padx=(4, 0))
        def _update_outline_swatch(*args):
            try:
                c = outline_color_var.get()
                if c.lower() == "none":
                    outline_swatch.configure(bg=pal["panel2"])
                else:
                    outline_swatch.configure(bg=c)
            except Exception:
                pass
        outline_color_var.trace_add("write", _update_outline_swatch)

        # ── Outline width ──
        ow_row = ttk.Frame(ctrl_frame)
        ow_row.pack(fill="x", pady=(0, 8))
        ttk.Label(ow_row, text="Outline Width:").pack(side="left")
        ttk.Spinbox(ow_row, from_=0, to=8, textvariable=outline_width_var, width=6).pack(side="right")

        # ── Opacity slider ──
        ttk.Label(ctrl_frame, text="Opacity:").pack(anchor="w", pady=(0, 2))
        opacity_label = ttk.Label(ctrl_frame, text="100%")
        opacity_label.pack(anchor="e")
        opacity_scale = ttk.Scale(ctrl_frame, from_=5, to=100, variable=opacity_var,
                                   orient="horizontal", length=260,
                                   command=lambda v: opacity_label.configure(text=f"{int(float(v))}%"))
        opacity_scale.set(100)
        opacity_scale.pack(fill="x", pady=(0, 8))

        # ── Shadow checkbox ──
        ttk.Checkbutton(ctrl_frame, text="Drop Shadow", variable=shadow_var).pack(anchor="w", pady=(0, 8))

        # ── Preview area (right side) ──
        preview_header = ttk.Frame(right_frame)
        preview_header.pack(fill="x")
        ttk.Label(preview_header, text="Preview", font=app.bold_font).pack(side="left")
        pos_info_label = ttk.Label(preview_header, text="", font=app.small_font)
        pos_info_label.pack(side="right")

        preview_canvas = tk.Canvas(right_frame, bg=pal["panel2"], highlightthickness=1,
                                    highlightbackground=pal.get("border_color", pal["panel2"]),
                                    cursor="crosshair")
        preview_canvas.pack(fill="both", expand=True, pady=(4, 4))

        # Hint label below preview
        hint_label = ttk.Label(right_frame, text="⬇ Click or drag on preview to position text",
                                font=app.small_font)
        hint_label.pack(anchor="w", pady=(0, 4))

        # ── Quick-position presets row ──
        preset_row = ttk.Frame(right_frame)
        preset_row.pack(fill="x", pady=(0, 4))
        ttk.Label(preset_row, text="Quick:", font=app.small_font).pack(side="left")
        presets = ["Top-Left", "Top-Right", "Center", "Bot-Left", "Bot-Right"]
        preset_keys = ["top-left", "top-right", "center", "bottom-left", "bottom-right"]
        for lbl, key in zip(presets, preset_keys):
            def _set_preset(k=key):
                custom_pos[0] = None
                custom_pos[1] = None
                position_var.set(k)
                pos_info_label.configure(text="")
                update_preview()
            ttk.Button(preset_row, text=lbl, command=_set_preset, width=8).pack(side="left", padx=2)

        # ── Load the source image and track preview geometry ──
        preview_state = {"img_w": 0, "img_h": 0, "offset_x": 0, "offset_y": 0, "scale": 1.0}

        def _load_base_image():
            try:
                from PIL import Image as _PILImg
                preview_img = _PILImg.open(img_path)
                preview_state["img_w"] = preview_img.width
                preview_state["img_h"] = preview_img.height
                preview_state["base_img"] = preview_img
            except Exception:
                preview_state["img_w"] = 0
                preview_state["img_h"] = 0

        _load_base_image()

        # ── Click / drag-to-position on preview canvas ──
        def _canvas_to_frac(event):
            cx, cy = event.x, event.y
            iw, ih = preview_state["img_w"], preview_state["img_h"]
            if iw == 0 or ih == 0:
                return None, None
            cw = preview_canvas.winfo_width()
            ch = preview_canvas.winfo_height()
            if cw <= 0 or ch <= 0:
                return None, None
            ratio = min(cw / iw, ch / ih)
            dw, dh = int(iw * ratio), int(ih * ratio)
            ox = (cw - dw) // 2
            oy = (ch - dh) // 2
            frac_x = (cx - ox) / dw if dw > 0 else 0.5
            frac_y = (cy - oy) / dh if dh > 0 else 0.5
            return max(0.0, min(1.0, frac_x)), max(0.0, min(1.0, frac_y))

        def _on_canvas_click(event):
            fx, fy = _canvas_to_frac(event)
            if fx is None:
                return
            custom_pos[0] = fx
            custom_pos[1] = fy
            pos_info_label.configure(text=f"Position: {fx:.0%}, {fy:.0%}")
            update_preview()

        preview_canvas.bind("<Button-1>", _on_canvas_click)
        preview_canvas.bind("<B1-Motion>", _on_canvas_click)

        # ── Helper: resolve font with bold/italic for preview ──
        def _get_preview_font(target_size):
            from PIL import ImageFont as _Font
            from style_transfer import StyleTransfer
            st = StyleTransfer.__new__(StyleTransfer)  # borrow FONT_VARIANTS

            sel_font = font_name_var.get()
            fpath = discovered_fonts.get(sel_font)
            want_bold = bold_var.get()
            want_italic = italic_var.get()

            if fpath:
                font, syn_bold, syn_italic = st._resolve_font_variant(fpath, target_size, want_bold, want_italic)
                if font is not None:
                    return font, syn_bold, syn_italic

            # Fallback system fonts
            if want_bold and want_italic:
                fallbacks = ["DejaVuSans-BoldOblique.ttf", "LiberationSans-BoldItalic.ttf",
                             "FreeSansBoldOblique.ttf"]
            elif want_bold:
                fallbacks = ["DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf", "FreeSansBold.ttf"]
            elif want_italic:
                fallbacks = ["DejaVuSans-Oblique.ttf", "LiberationSans-Italic.ttf", "FreeSansOblique.ttf"]
            else:
                fallbacks = ["DejaVuSans.ttf", "LiberationSans.ttf", "FreeSans.ttf"]
            for fn in fallbacks:
                try:
                    return _Font.truetype(fn, target_size), want_bold, want_italic
                except Exception:
                    continue
            return _Font.load_default(), want_bold, want_italic

        # ── Live preview update ──
        def update_preview(*args):
            txt = text_var.get().strip()
            if not txt:
                try:
                    preview_canvas.delete("all")
                    if "base_img" in preview_state:
                        from PIL import Image as _PILImg, ImageTk as _PILTk
                        bi = preview_state["base_img"].copy()
                        cw = preview_canvas.winfo_width() or 400
                        ch = preview_canvas.winfo_height() or 300
                        bi.thumbnail((cw, ch), _PILImg.Resampling.LANCZOS)
                        photo = _PILTk.PhotoImage(bi)
                        preview_canvas.create_image(cw // 2, ch // 2, image=photo, anchor="center")
                        preview_canvas._base_photo = photo
                except Exception:
                    pass
                pos_info_label.configure(text="")
                return

            try:
                from PIL import Image as _Img, ImageDraw as _Draw, ImageTk as _Tk
                import math as _math

                cw = preview_canvas.winfo_width() or 400
                ch = preview_canvas.winfo_height() or 300
                iw, ih = preview_state["img_w"], preview_state["img_h"]
                if iw == 0 or ih == 0:
                    return

                # Scale to fit canvas
                ratio = min(cw / iw, ch / ih)
                pw, ph = int(iw * ratio), int(ih * ratio)
                ox = (cw - pw) // 2
                oy = (ch - ph) // 2

                # Build preview image
                with _Img.open(img_path) as src:
                    prev = src.resize((pw, ph), _Img.Resampling.LANCZOS)

                if prev.mode != 'RGBA':
                    prev = prev.convert('RGBA')

                draw = _Draw.Draw(prev)
                scaled_size = max(8, int(font_size_var.get() * ratio))
                font, syn_bold, syn_italic = _get_preview_font(scaled_size)

                # Calculate text position in preview coords
                bbox = draw.textbbox((0, 0), txt, font=font)
                tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
                pad = int(12 * ratio)

                if custom_pos[0] is not None and custom_pos[1] is not None:
                    tx = int(custom_pos[0] * pw - tw / 2)
                    ty = int(custom_pos[1] * ph - th / 2)
                    tx = max(0, min(tx, pw - tw))
                    ty = max(0, min(ty, ph - th))
                else:
                    pos = position_var.get()
                    if pos == "top-left":
                        tx, ty = pad, pad
                    elif pos == "top-right":
                        tx, ty = pw - tw - pad, pad
                    elif pos == "middle-top":
                        tx, ty = (pw - tw) // 2, pad
                    elif pos == "middle-bottom":
                        tx, ty = (pw - tw) // 2, ph - th - pad
                    elif pos == "bottom-left":
                        tx, ty = pad, ph - th - pad
                    elif pos == "bottom-right":
                        tx, ty = pw - tw - pad, ph - th - pad
                    elif pos == "center":
                        tx, ty = (pw - tw) // 2, (ph - th) // 2
                    else:
                        tx, ty = pw - tw - pad, ph - th - pad

                ow = outline_width_var.get()
                ol_color = outline_color_var.get()

                # Helper: draw text with optional synthetic bold
                def _pdraw(d, pos, fill):
                    if syn_bold:
                        for dx in (-0.6, 0, 0.6):
                            for dy in (-0.6, 0, 0.6):
                                d.text((pos[0]+dx, pos[1]+dy), txt, font=font, fill=fill)
                    else:
                        d.text(pos, txt, font=font, fill=fill)

                # If synthetic italic, draw onto a separate layer and shear it
                if syn_italic:
                    text_layer = _Img.new('RGBA', prev.size, (0, 0, 0, 0))
                    tl_draw = _Draw.Draw(text_layer)
                    if shadow_var.get():
                        so = max(1, scaled_size // 12)
                        for ax in range(-ow, ow + 1):
                            for ay in range(-ow, ow + 1):
                                tl_draw.text((tx+ax+so, ty+ay+so), txt, font=font, fill=(0,0,0,255))
                    if ow > 0 and ol_color != "none":
                        for ax in range(-ow, ow + 1):
                            for ay in range(-ow, ow + 1):
                                if ax != 0 or ay != 0:
                                    tl_draw.text((tx+ax, ty+ay), txt, font=font, fill=ol_color)
                    _pdraw(tl_draw, (tx, ty), color_var.get())
                    if underline_var.get():
                        ul_offset = max(2, int(scaled_size * 0.08))
                        ul_thickness = max(1, int(scaled_size * 0.05))
                        try:
                            _m = font.getmetrics()
                            ul_y = ty + _m[0] + ul_offset
                        except Exception:
                            ul_y = ty + th + ul_offset
                        tl_draw.line([(tx, ul_y), (tx+tw, ul_y)], fill=color_var.get(), width=ul_thickness)
                    shear = -12
                    text_layer = text_layer.transform(
                        prev.size, _Img.AFFINE,
                        (1, _math.tan(_math.radians(shear)), 0, 0, 1, 0),
                        resample=_Img.BICUBIC)
                    # Apply opacity
                    opa = opacity_var.get()
                    if opa < 100:
                        alpha = int(255 * opa / 100)
                        r, g, b, a = text_layer.split()
                        a = a.point(lambda px: int(px * alpha / 255))
                        text_layer = _Img.merge('RGBA', (r, g, b, a))
                    prev = _Img.alpha_composite(prev, text_layer)
                else:
                    # Direct draw path
                    opa = opacity_var.get()
                    if opa < 100:
                        # Use alpha compositing for opacity
                        alpha = int(255 * opa / 100)
                        text_layer = _Img.new('RGBA', prev.size, (0, 0, 0, 0))
                        td = _Draw.Draw(text_layer)
                        if shadow_var.get():
                            so = max(1, scaled_size // 12)
                            _pdraw(td, (tx+so, ty+so), (0,0,0,alpha))
                        if ow > 0 and ol_color != "none":
                            try:
                                ol_rgb = ImageColor.getrgb(ol_color) if not isinstance(ol_color, tuple) else ol_color[:3]
                            except Exception:
                                ol_rgb = (0, 0, 0)
                            for ax in range(-ow, ow + 1):
                                for ay in range(-ow, ow + 1):
                                    if ax != 0 or ay != 0:
                                        td.text((tx+ax, ty+ay), txt, font=font, fill=(*ol_rgb, alpha))
                        try:
                            tc_rgb = ImageColor.getrgb(color_var.get())
                        except Exception:
                            tc_rgb = (255, 255, 255)
                        _pdraw(td, (tx, ty), (*tc_rgb, alpha))
                        if underline_var.get():
                            ul_offset = max(2, int(scaled_size * 0.08))
                            ul_thickness = max(1, int(scaled_size * 0.05))
                            try:
                                _m = font.getmetrics()
                                ul_y = ty + _m[0] + ul_offset
                            except Exception:
                                ul_y = ty + th + ul_offset
                            td.line([(tx, ul_y), (tx+tw, ul_y)], fill=(*tc_rgb, alpha), width=ul_thickness)
                        prev = _Img.alpha_composite(prev, text_layer)
                    else:
                        # Full opacity, no synthetic italic
                        if shadow_var.get():
                            so = max(1, scaled_size // 12)
                            _pdraw(draw, (tx+so, ty+so), "black")
                        if ow > 0 and ol_color != "none":
                            for ax in range(-ow, ow + 1):
                                for ay in range(-ow, ow + 1):
                                    if ax != 0 or ay != 0:
                                        draw.text((tx+ax, ty+ay), txt, font=font, fill=ol_color)
                        _pdraw(draw, (tx, ty), color_var.get())
                        if underline_var.get():
                            ul_offset = max(2, int(scaled_size * 0.08))
                            ul_thickness = max(1, int(scaled_size * 0.05))
                            try:
                                _m = font.getmetrics()
                                ul_y = ty + _m[0] + ul_offset
                            except Exception:
                                ul_y = ty + th + ul_offset
                            draw.line([(tx, ul_y), (tx+tw, ul_y)], fill=color_var.get(), width=ul_thickness)

                if prev.mode == 'RGBA':
                    prev = prev.convert('RGB')

                photo = _Tk.PhotoImage(prev)
                preview_canvas.delete("all")
                preview_canvas.create_image(cw // 2, ch // 2, image=photo, anchor="center")
                preview_canvas._preview_photo = photo

            except Exception:
                pass  # Silent fail for preview — non-critical

        # Bind all controls to trigger live preview update
        for var in (text_var, font_name_var, color_var, outline_color_var,
                    position_var, bold_var, italic_var, underline_var, shadow_var,
                    opacity_var, font_size_var, outline_width_var):
            var.trace_add("write", update_preview)

        # ── Buttons (at bottom of right panel) ──
        button_frame = ttk.Frame(right_frame)
        button_frame.pack(fill="x", pady=(8, 0))

        def apply_text():
            text = text_var.get().strip()
            if not text:
                app._dialog.warning("No Text", "Please enter some text to add.")
                return
            
            try:
                from style_transfer import get_style_transfer
                transfer = get_style_transfer()

                # Resolve font path
                sel_font = font_name_var.get()
                fpath = discovered_fonts.get(sel_font)
                
                result_path = transfer.add_text_overlay(
                    img_path,
                    text,
                    position=position_var.get() if custom_pos[0] is None else "custom",
                    font_size=font_size_var.get(),
                    text_color=color_var.get(),
                    outline_color=outline_color_var.get() if outline_color_var.get() != "none" else None,
                    outline_width=outline_width_var.get() if outline_color_var.get() != "none" else 0,
                    font_path=fpath,
                    bold=bold_var.get(),
                    italic=italic_var.get(),
                    underline=underline_var.get(),
                    opacity=opacity_var.get(),
                    shadow=shadow_var.get(),
                    custom_x=custom_pos[0],
                    custom_y=custom_pos[1],
                )
                
                if result_path and result_path.exists():
                    app.status_var.set(f"Text overlay saved to Styled view: {result_path.name}")
                    app._dialog.info("Saved to Styled View", f"Text overlay applied successfully!\n\nImage saved as:\n{result_path.name}\n\nSwitching to the Styled tab.")
                    app.gallery_view_var.set("Styled")
                    app._on_gallery_view_changed()
                    dialog.destroy()
                else:
                    app._dialog.error("Text Overlay Failed", "Could not apply text to the image. The image file may be corrupted.")
            except Exception as e:
                import traceback
                error_msg = f"Failed to add text: {str(e)}\n\nTraceback:\n{traceback.format_exc()}"
                app._dialog.error("Text Overlay Failed", "Could not apply text overlay. Try a different image.")

        ttk.Button(button_frame, text="Apply", command=apply_text).pack(side="left", padx=(0, 10))
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side="left")

        # Bind Enter key to apply
        text_entry.bind("<Return>", lambda e: apply_text())

        # Cleanup on close
        def _on_close():
            dialog.destroy()
        dialog.protocol("WM_DELETE_WINDOW", _on_close)

        # Initial preview trigger after dialog is visible
        dialog.after(200, update_preview)

    def _gallery_apply_theme(self, style_key):
        """Apply Themes — uses resolved image path in Favorites view."""
        app = self.app
        if app._gallery_view_mode() == "Favorites":
            if not app.favorite_selected_item:
                app._dialog.warning("No Selection", "Select a Favorite thumbnail first.")
                return
            path_str = app.favorite_selected_item.get("image_path") or \
                       app.favorite_selected_item.get("copied_image_path")
            if not path_str or not Path(path_str).exists():
                app._dialog.warning("No Image", "Selected favorite has no valid image file.")
                return
            app.selected_gallery_path = Path(path_str)
        app.apply_style_transfer_filter(style_key)


    def _gallery_delete(self):
        """Delete — removes gallery image, favorite, or styled image depending on view."""
        app = self.app
        mode = app._gallery_view_mode()
        if mode == "Favorites":
            app.delete_selected_favorite()
        elif mode == "Styled":
            app._delete_styled_image()
        elif mode == "Manual":
            app.delete_selected()
            app.load_manual()  # Refresh manual view after deletion
        else:
            app.delete_selected()
            app.load_gallery()  # Refresh gallery view after deletion


    def _gallery_save_to_favorites(self):
        """Save to Favorites — no-op with message if already a favorite."""
        app = self.app
        if app._gallery_view_mode() == "Favorites":
            app.status_var.set("Already in Favorites.")
        else:
            app.save_gallery_to_favorites()


    def _gallery_set_wallpaper(self):
        """Set as Wallpaper — routes to gallery, favorites, or styled selection."""
        app = self.app
        if app._gallery_view_mode() == "Favorites":
            app.set_selected_favorite_as_wallpaper()
        else:
            # Gallery or Styled view — both use selected_gallery_path
            app.set_gallery_selection()


    def _gallery_tag_selected(self):
        """Tag Selected — uses resolved image path in Favorites view."""
        app = self.app
        if app._gallery_view_mode() == "Favorites":
            if not app.favorite_selected_item:
                app._dialog.warning("No Selection", "Select a Favorite thumbnail first.")
                return
            path_str = app.favorite_selected_item.get("image_path") or \
                       app.favorite_selected_item.get("copied_image_path")
            if not path_str or not Path(path_str).exists():
                app._dialog.warning("No Image", "Selected favorite has no valid image file.")
                return
            app.selected_gallery_path = Path(path_str)
        app.tag_gallery_image()

    def _gallery_export_portraits(self):
        """Export all portrait images to a user-selected folder for phone transfer."""
        from tkinter import filedialog
        from pathlib import Path
        
        app = self.app
        
        # Show folder browser dialog to select destination
        app.status_var.set("Select export destination...")
        
        # Suggest Documents folder as initial directory
        initial_dir = str(Path.home() / "Documents")
        
        destination_folder = filedialog.askdirectory(
            title="Select Destination Folder for Portrait Images",
            initialdir=initial_dir,
            mustexist=False
        )
        
        # Handle user cancellation
        if not destination_folder:
            app.status_var.set("Export cancelled")
            return
        
        destination_path = Path(destination_folder)
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        export_subfolder = destination_path / f"FrogPaper_Portraits_{timestamp}"
        export_subfolder.mkdir(parents=True, exist_ok=True)
        
        # Show initial status
        app.status_var.set("Finding portrait images...")
        
        # Run in background thread to avoid UI freeze
        def _export_thread():
            try:
                from utils import copy_images_to_folder, open_folder_in_explorer
                
                # Collect portrait images
                portrait_images = get_portrait_images()
                
                if not portrait_images:
                    schedule_ui_update(app._dialog.info,
                        "No Portrait Images", 
                        "No portrait (9:16) images found in your gallery.\n\n"
                        "Generate some portrait wallpapers first, then try again."
                    )
                    schedule_ui_update(app.status_var.set, "No portrait images found")
                    try:
                        export_subfolder.rmdir()
                    except Exception:
                        pass
                    return
                
                # Update status with count
                schedule_ui_update(app.status_var.set, f"Found {len(portrait_images)} portrait images")
                schedule_ui_update(app.status_var.set, f"Copying {len(portrait_images)} images to {export_subfolder.name}...")
                
                # Copy images to the auto-created subfolder
                success_count, failure_count = copy_images_to_folder(portrait_images, export_subfolder)
                
                # Show completion status
                if failure_count > 0:
                    schedule_ui_update(app.status_var.set,
                        f"Exported {success_count} images ({failure_count} failed)"
                    )
                else:
                    schedule_ui_update(app.status_var.set,
                        f"Successfully exported {success_count} portrait images"
                    )
                
                # Open the export subfolder in Explorer
                open_folder_in_explorer(export_subfolder)
                
                # Show success dialog with instructions
                schedule_ui_update(app._dialog.info,
                    "Portrait Images Exported",
                    f"Successfully exported {success_count} portrait images to:\n\n"
                    f"{export_subfolder}\n\n"
                    f"The entire folder is ready to drag to your phone!\n\n"
                    f"Note: If your phone doesn't appear in the export dialog (MTP devices),\n"
                    f"you can copy the folder manually:\n"
                    f"1. Open Windows Explorer (your phone is visible there)\n"
                    f"2. Drag the folder above onto your phone\n\n"
                    f"Alternative transfer methods:\n"
                    f"• Use Windows Nearby Sharing from the exported folder\n"
                    f"• Upload to cloud storage (Google Drive, OneDrive, etc.)\n"
                    f"• Email the images to yourself\n\n"
                    f"({failure_count} images failed to copy)" if failure_count > 0 else
                    f"The entire folder is ready to drag to your phone!\n\n"
                    f"Note: If your phone doesn't appear in the export dialog (MTP devices),\n"
                    f"you can copy the folder manually:\n"
                    f"1. Open Windows Explorer (your phone is visible there)\n"
                    f"2. Drag the folder above onto your phone\n\n"
                    f"Alternative transfer methods:\n"
                    f"• Use Windows Nearby Sharing from the exported folder\n"
                    f"• Upload to cloud storage (Google Drive, OneDrive, etc.)\n"
                    f"• Email the images to yourself"
                )
                
            except Exception as e:
                logger.error(f"Error exporting portrait images: {e}")
                schedule_ui_update(app._dialog.error, "Export Failed", "Could not export portrait images. Check that the destination folder is accessible.")
                schedule_ui_update(app.status_var.set, "Export failed")
        
        # Start background thread
        run_background(_export_thread)


    def _gallery_view_mode(self):
        """Return 'Favorites' or 'Gallery' based on current radio selection."""
        app = self.app
        return app.gallery_view_var.get()


    def _gallery_visible_range(self):
        """Return (first_idx, last_idx) inclusive for the visible viewport + buffer.

        Reads the canvas yview fraction and maps it to image indices using the
        known placeholder/card height constant.
        """
        app = self.app
        n = len(app.gallery_images)
        if n == 0:
            return 0, -1

        cols = max(1, app._gallery_cols)
        n_rows = (n + cols - 1) // cols
        total_h = n_rows * app._GALLERY_CARD_H

        if total_h == 0:
            return 0, n - 1

        y0_frac, y1_frac = app.gallery_canvas.yview()

        buf = app._GALLERY_CARD_H  # one-row look-ahead buffer
        top_px = max(0.0, y0_frac * total_h - buf)
        bot_px = min(float(total_h), y1_frac * total_h + buf)

        first_row = int(top_px // app._GALLERY_CARD_H)
        last_row  = min(n_rows - 1, int(bot_px // app._GALLERY_CARD_H))

        first_idx = first_row * cols
        last_idx  = min(n - 1, (last_row + 1) * cols - 1)

        return first_idx, last_idx


    def _highlight_fav_organize(self, picked_index, *, hover_index):
        app = self.app
        pass  # Organize Mode removed


    def _highlight_organize_source(self, picked_index, *, hover_index):
        app = self.app
        pass  # Organize Mode removed


    def _make_gallery_placeholder(self, idx, row, col):
        """Create and grid a fixed-size placeholder Frame for one image slot."""
        app = self.app
        pal = app.THEMES.get(app.current_theme_name, app.THEMES["darkforest"])
        ph = tk.Frame(
            app.gallery_inner,
            width=252, height=app._GALLERY_CARD_H,
            bg=pal["panel2"],
        )
        ph.grid(row=row, column=col, padx=6, pady=6, sticky='nsew')
        ph.grid_propagate(False)  # hold fixed size even when empty
        app._gallery_placeholders[idx] = ph


    def _on_fav_card_click(self, event, path, data, ui, index):
        app = self.app
        app._select_visual_item(ui, path, data)


    def _on_fav_card_drag(self, event, index):
        app = self.app
        pass  # Organize Mode removed


    def _on_fav_card_drop(self, event, source_index):
        app = self.app
        pass  # Organize Mode removed


    def _on_gallery_scroll(self, *_):
        """Debounced scroll handler — defers _render_visible_cards by 60 ms."""
        app = self.app
        if app._gallery_scroll_job is not None:
            try:
                app.gallery_canvas.after_cancel(app._gallery_scroll_job)
            except Exception:
                pass
        app._gallery_scroll_job = app.gallery_canvas.after(
            60, app._render_visible_cards
        )


    def _on_gallery_view_changed(self):
        """Switch between Gallery, Favorites, Styled, Manual, and Ratio views inside the Gallery tab."""
        app = self.app
        mode = app.gallery_view_var.get()

        # Ensure all canvases use the current theme background
        pal = app.THEMES.get(app.current_theme_name, app.THEMES["darkforest"])
        canvas_bg = pal["bg"]
        for c in (app.gallery_canvas, app.gallery_fav_canvas,
                  app.gallery_styled_canvas, app.gallery_manual_canvas):
            try:
                c.configure(bg=canvas_bg, highlightthickness=0)
            except Exception:
                pass

        # Hide all view canvases first
        app.gallery_canvas.pack_forget()
        app._gallery_scroll.pack_forget()
        app.gallery_fav_canvas.pack_forget()
        app._gallery_fav_scroll.pack_forget()
        app.gallery_styled_canvas.pack_forget()
        app._gallery_styled_scroll.pack_forget()
        app.gallery_manual_canvas.pack_forget()
        app._gallery_manual_scroll.pack_forget()

        # Invalidate any in-flight ratio thumbnail loading so stale callbacks become no-ops
        if mode not in ("Ratio 16:9", "Ratio 9:16", "Ratio 1:1"):
            self._ratio_load_gen += 1

        # Helper: repack action row showing only the given subset in order
        # Uses expanding spacers between widgets for even distribution
        def _repack(visible):
            # Forget ALL children of the row (buttons + old spacers)
            for w in app._gallery_action_row.winfo_children():
                w.pack_forget()
            for i, w in enumerate(visible):
                w.pack(side='left')
                if i < len(visible) - 1:
                    ttk.Frame(app._gallery_action_row).pack(side='left', fill='x', expand=True)

        _btn_wallpaper_ref = app._gallery_action_row_order[0]
        _btn_style_ref = app._gallery_action_row_order[1]
        _btn_text_ref = app._gallery_action_row_order[2]
        _btn_delete_ref = app._gallery_action_row_order[3]
        _btn_refresh_ref = app._gallery_action_row_order[4]

        if mode == "Favorites":
            app.gallery_fav_canvas.pack(side='left', fill='both', expand=True)
            app._gallery_fav_scroll.pack(side='right', fill='y')
            # Favorites: Wallpaper | Apply Style | Add Text | Delete | Refresh
            _repack([_btn_wallpaper_ref, _btn_style_ref, _btn_text_ref, _btn_delete_ref, _btn_refresh_ref])
            app._repack_header_buttons(is_portrait=False)
            tag_filter = app.get_active_tag()
            app.load_favorites(tag_filter=tag_filter)
        elif mode == "Styled":
            app.gallery_styled_canvas.pack(side='left', fill='both', expand=True)
            app._gallery_styled_scroll.pack(side='right', fill='y')
            # Styled: Wallpaper | Apply Style | Add Text | Delete | Refresh
            _repack([_btn_wallpaper_ref, _btn_style_ref, _btn_text_ref, _btn_delete_ref, _btn_refresh_ref])
            app._repack_header_buttons(is_portrait=False)
            tag_filter = app.get_active_tag()
            app.load_styled(tag_filter=tag_filter)
        elif mode == "Manual":
            app.gallery_manual_canvas.pack(side='left', fill='both', expand=True)
            app._gallery_manual_scroll.pack(side='right', fill='y')
            # Manual: Wallpaper | Apply Style | Add Text | Delete | Refresh
            _repack([_btn_wallpaper_ref, _btn_style_ref, _btn_text_ref, _btn_delete_ref, _btn_refresh_ref])
            app._repack_header_buttons(is_portrait=False)
            tag_filter = app.get_active_tag()
            app.load_manual(tag_filter=tag_filter)
        elif mode == "Ratio 9:16":
            app.gallery_canvas.pack(side='left', fill='both', expand=True)
            app._gallery_scroll.pack(side='right', fill='y')
            # Portrait view: Wallpaper | Apply Style | Add Text | Delete | Refresh
            _repack([_btn_wallpaper_ref, _btn_style_ref, _btn_text_ref, _btn_delete_ref, _btn_refresh_ref])
            # Show Export Portraits button (portrait order: Export | Open Folder | Tutorials)
            app._repack_header_buttons(is_portrait=True)
            tag_filter = app.get_active_tag()
            # Show loading indicator
            app.status_var.set(f'Loading {mode} images...')
            app.root.update_idletasks()
            # Load in background thread to prevent UI freeze
            run_background(app.load_gallery_by_ratio, mode, tag_filter)
        elif mode in ["Ratio 16:9", "Ratio 1:1"]:
            app.gallery_canvas.pack(side='left', fill='both', expand=True)
            app._gallery_scroll.pack(side='right', fill='y')
            # Other ratio views: Wallpaper | Apply Style | Add Text | Delete | Refresh
            _repack([_btn_wallpaper_ref, _btn_style_ref, _btn_text_ref, _btn_delete_ref, _btn_refresh_ref])
            app._repack_header_buttons(is_portrait=False)
            tag_filter = app.get_active_tag()
            # Show loading indicator
            app.status_var.set(f'Loading {mode} images...')
            app.root.update_idletasks()
            # Load in background thread to prevent UI freeze
            logger.info(f"Starting ratio load for {mode} with tag filter: {tag_filter}")
            run_background(app.load_gallery_by_ratio, mode, tag_filter)
        else:  # Gallery
            app.gallery_canvas.pack(side='left', fill='both', expand=True)
            app._gallery_scroll.pack(side='right', fill='y')
            # Gallery: Wallpaper | Apply Style | Add Text | Delete | Refresh
            _repack([_btn_wallpaper_ref, _btn_style_ref, _btn_text_ref, _btn_delete_ref, _btn_refresh_ref])
            app._repack_header_buttons(is_portrait=False)
            # Force multiple UI updates to ensure canvas is properly visible and sized
            app.gallery_canvas.update()
            app.gallery_canvas.update_idletasks()
            app.root.update_idletasks()
            app.load_gallery()
            # Force another update after loading to ensure rendering
            app.gallery_canvas.update_idletasks()


    def _on_tag_selected(self):
        """Handle tag selection change - applies tag filter to current view."""
        app = self.app
        current_tag = app.gallery_tag_var.get()
        tag_filter = current_tag if current_tag != 'All tags' else None

        view_mode = app._gallery_view_mode()
        if view_mode == "Gallery":
            app.load_gallery()
            filter_desc = f" with tag '{current_tag}'" if tag_filter else ""
            app.status_var.set(f'Gallery reloaded{filter_desc}.')
        elif view_mode == "Favorites":
            app.load_favorites(tag_filter=tag_filter)
            filter_desc = f" with tag '{current_tag}'" if tag_filter else ""
            app.status_var.set(f'Favorites reloaded{filter_desc}.')
        elif view_mode == "Styled":
            app.load_styled(tag_filter=tag_filter)
            filter_desc = f" with tag '{current_tag}'" if tag_filter else ""
            app.status_var.set(f'Styled reloaded{filter_desc}.')
        elif view_mode == "Manual":
            app.load_manual(tag_filter=tag_filter)
            filter_desc = f" with tag '{current_tag}'" if tag_filter else ""
            app.status_var.set(f'Manual reloaded{filter_desc}.')
        elif view_mode in ["Ratio 16:9", "Ratio 9:16", "Ratio 1:1"]:
            app.status_var.set(f'Loading {view_mode} images...')
            app.root.update_idletasks()
            run_background(app.load_gallery_by_ratio, view_mode, tag_filter)

        # Return focus to the active canvas so mousewheel scrolling works
        # immediately after tag selection without needing an extra click.
        try:
            canvas_map = {
                "Gallery": app.gallery_canvas,
                "Favorites": app.gallery_fav_canvas,
                "Styled": app.gallery_styled_canvas,
                "Manual": app.gallery_manual_canvas,
                "Ratio 16:9": app.gallery_canvas,
                "Ratio 9:16": app.gallery_canvas,
                "Ratio 1:1": app.gallery_canvas,
            }
            target = canvas_map.get(view_mode, app.gallery_canvas)
            target.focus_set()
        except Exception:
            pass


    def _on_thumbnail_click(self, path, ctrl_pressed=False):
        """Handle thumbnail click with multi-select support (Ctrl-click)."""
        app = self.app
        path_obj = Path(path)
        path_str = str(path_obj)
        
        if ctrl_pressed:
            # Ctrl-click: toggle selection in multi-select set
            if path_str in app.selected_gallery_paths:
                app.selected_gallery_paths.discard(path_str)
            else:
                app.selected_gallery_paths.add(path_str)
            # Primary selection stays as last clicked
            app.selected_gallery_path = path_obj
        else:
            # Normal click: clear multi-select, set single selection
            app.selected_gallery_paths.clear()
            app.selected_gallery_paths.add(path_str)
            app.selected_gallery_path = path_obj
            app.show_preview_in_left_panel(path, f'Gallery: {path.name}')
            
            # Reload sidebar variables from saved prompt parameters
            prompt_params = get_prompt_parameters(path)
            if prompt_params:
                app.set_active_subject(prompt_params.get("subject", ""))
                app.set_active_style(prompt_params.get("style", ""))
                app.set_active_lighting(prompt_params.get("lighting", ""))
                app.set_active_mood(prompt_params.get("mood", ""))
                app.set_active_color(prompt_params.get("color", ""))
                app.set_active_atmosphere(prompt_params.get("atmosphere", ""))
                app.set_active_setting(prompt_params.get("setting", ""))
                mode = prompt_params.get("mode", "")
                if mode:
                    app.set_active_mode(mode)
                app.set_active_subject_lock(prompt_params.get("subject_lock", True))
                neg = prompt_params.get("negative_prompt", "")
                if neg:
                    app.set_active_negative_prompt(neg)
        
        selection_count = len(app.selected_gallery_paths)
        if selection_count > 1:
            app.status_var.set(f'Selected {selection_count} images')
        else:
            app.status_var.set(f'Selected: {path.name}')
        
        app._update_gallery_highlight_multi()


    def _open_wallpapers_folder(self):
        """Open the wallpapers directory in the system file explorer."""
        app = self.app
        try:
            folder_path = get_app_dir() / "wallpapers"
            if not folder_path.exists():
                folder_path.mkdir(parents=True, exist_ok=True)
            os.startfile(folder_path)
        except Exception as e:
            app.status_var.set(f"Could not open folder: {e}")


    # ── Shared image-dimension cache (perf) ──────────────────────────────

    def _img_dims(self, path):
        """Cached (width, height) for an image path — (0, 0) if unreadable.

        Resolution sorts and card info lines used to open every image on
        EVERY view load. With this memo the first load pays for the header
        read once and every later load/sort is instant. Bounded like
        thumb_cache; safe across threads (dict ops are atomic, worst case
        is a duplicate header read).
        """
        app = self.app
        cache = getattr(app, "_img_dims_cache", None)
        if cache is None:
            cache = app._img_dims_cache = {}
        key = str(path)
        dims = cache.get(key)
        if dims is not None:
            return dims
        try:
            from PIL import Image as PILImg
            with PILImg.open(path) as img:
                dims = (img.width, img.height)
        except Exception:
            dims = (0, 0)
        if len(cache) > 500:
            cache.clear()
        cache[key] = dims
        return dims

    def _info_line_for(self, path):
        """'1920×1080  •  2.1 MB' string used by manual/styled/fav cards."""
        try:
            size_bytes = Path(path).stat().st_size
            size_str = f"{size_bytes / 1_048_576:.1f} MB" if size_bytes >= 1_048_576 else f"{size_bytes / 1024:.0f} KB"
            w_px, h_px = self._img_dims(path)
            return f"{w_px}\u00d7{h_px}  \u2022  {size_str}" if w_px and h_px else size_str
        except Exception:
            return ""

    # ── Deferred grid thumbnails (perf: no UI-thread PIL decode) ─────────

    def _bump_grid_load_seq(self):
        """Invalidate in-flight deferred thumbnail loads (new view load).

        Drops everything still queued and bumps the generation token the
        background worker stamps onto its results, so a stale worker's
        output is discarded on arrival instead of touching dead labels.
        """
        self._grid_load_seq = getattr(self, "_grid_load_seq", 0) + 1
        queue = getattr(self, "_grid_thumb_queue", None)
        if queue:
            self._grid_thumb_queue = []
        job = getattr(self, "_grid_thumb_job", None)
        if job is not None:
            try:
                self.app.root.after_cancel(job)
            except Exception:
                pass
            self._grid_thumb_job = None

    def _attach_card_thumb(self, parent, pal, path, pack_kwargs=None,
                           on_click=None, on_double=None, on_context=None):
        """Create a card thumbnail label that never decodes on the UI thread.

        Cache hit  -> label shows the thumbnail immediately, no fade (the
                      main Gallery shows cache hits the same way).
        Cache miss -> label starts as a themed text placeholder; the decode
                      is coalesced into ONE background worker and the same
                      label is reconfigured in place on arrival, so bindings
                      stay live and nothing is rebuilt.
        """
        app = self.app
        if pack_kwargs is None:
            pack_kwargs = {}
        cached = app.thumb_cache.get(str(path))
        if cached is not None:
            lbl = tk.Label(parent, image=cached, bg=pal["panel"], cursor="hand2")
            lbl.image = cached  # prevent GC
            lbl.pack(**pack_kwargs)
        else:
            lbl = tk.Label(parent, text="…", bg=pal["panel"],
                           fg=pal.get("muted", COLOR_MID_GRAY),
                           font=app.small_font, width=28, height=4,
                           cursor="hand2")
            lbl.pack(**pack_kwargs)
            self._queue_grid_thumb(lbl, path)
        for seq_name, handler in (("<Button-1>", on_click),
                                  ("<Double-Button-1>", on_double),
                                  ("<Button-3>", on_context)):
            if handler is not None:
                lbl.bind(seq_name, handler)
        return lbl

    def _queue_grid_thumb(self, label, path):
        """Queue a placeholder label for the shared background decode."""
        queue = getattr(self, "_grid_thumb_queue", None)
        if queue is None:
            queue = self._grid_thumb_queue = []
        key = str(path)
        label._grid_thumb_path = key
        queue.append((label, Path(path), key))
        # Coalesce everything queued during this UI tick into ONE worker
        if getattr(self, "_grid_thumb_job", None) is None:
            try:
                self._grid_thumb_job = self.app.root.after(
                    30, self._start_grid_thumb_worker)
            except Exception:
                self._grid_thumb_job = None
                self._start_grid_thumb_worker()

    def _start_grid_thumb_worker(self):
        """Flush the pending queue to a single background decode thread."""
        self._grid_thumb_job = None
        queue = getattr(self, "_grid_thumb_queue", None)
        if not queue:
            return
        jobs, self._grid_thumb_queue = queue, []
        run_background(self._grid_thumb_worker, jobs,
                       getattr(self, "_grid_load_seq", 0))

    def _grid_thumb_worker(self, jobs, seq):
        """Background thread: decode 240x135 LANCZOS thumbnails in chunks.

        Produces plain PIL images — PhotoImage objects are Tk-bound and
        must be created on the main thread (same split as the main
        gallery's _load_thumbnails_lazy).
        """
        from PIL import Image as _PILImage
        cache = getattr(self, "_grid_pil_cache", None)
        if cache is None:
            cache = self._grid_pil_cache = {}
        results = []
        for label, path, key in jobs:
            try:
                pil = cache.get(key)
                if pil is None:
                    img = _PILImage.open(path)
                    img.thumbnail((240, 135), _PILImage.Resampling.LANCZOS)
                    pil = img
                    if len(cache) > 300:
                        cache.clear()
                    cache[key] = pil
                results.append((label, pil))
            except Exception:
                results.append((label, None))
            if len(results) >= 6:  # chunked: thumbs appear progressively
                schedule_ui_update(self._apply_grid_thumbs, results, seq)
                results = []
        if results:
            schedule_ui_update(self._apply_grid_thumbs, results, seq)

    def _apply_grid_thumbs(self, results, seq):
        """Main thread: swap placeholder labels to their decoded thumbnails."""
        app = self.app
        if seq != getattr(self, "_grid_load_seq", 0):
            return  # superseded by a newer view load
        for label, pil in results:
            try:
                if not label.winfo_exists():
                    continue
                if pil is None:
                    label.configure(text="(image error)", width=0, height=0)
                    continue
                photo = ImageTk.PhotoImage(pil)
                label.configure(image=photo, text="", width=0, height=0)
                label.image = photo  # prevent GC
                refs = getattr(app, "favorite_thumb_refs", None)
                if isinstance(refs, list):
                    refs.append(photo)
                try:
                    self._fade_in_thumb(label, photo, steps=4, interval=35,
                                        base_pil=pil)
                except Exception:
                    pass
                if len(app.thumb_cache) > 200:
                    app.thumb_cache.clear()
                key = getattr(label, "_grid_thumb_path", None)
                if key:
                    app.thumb_cache[key] = photo
            except Exception:
                continue  # widget destroyed between check and configure

    def _populate_visual_grid(self, ui, items, kind):

        app = self.app
        for widget in ui["inner"].winfo_children():

            widget.destroy()



        app.favorite_cards.clear()

        app.favorite_thumb_refs.clear()

        # Any deferred thumbnail loads for the old grid are now stale
        self._bump_grid_load_seq()

        app.favorite_selected_item = None

        cards = app.favorite_cards

        refs = app.favorite_thumb_refs

        pal = app.THEMES.get(app.current_theme_name, app.THEMES["darkforest"])



        rows = []

        for i, item in enumerate(items):

            item = dict(item)

            # Resolve using only the stored path — no cross-folder repair so
            # gallery images can never leak into the favorites grid.
            guessed = app._guess_image_for_item(item, strict=True)

            path = Path(guessed) if guessed else None

            if path:
                item["resolved_image_path"] = str(path)

            # Always include item — path=None will render a placeholder text card
            rows.append((i, item, path))



        if not rows:

            msg = "No favorites yet. Use 'Save to Favorites' on any image to add it here."

            ui["inner"].columnconfigure(0, weight=1)
            ui["inner"].rowconfigure(0, weight=1)
            tk.Label(
                ui["inner"],
                text=msg,
                bg=pal["bg"], fg=pal["text"], font=app.small_font,
                pady=10,
            ).grid(row=0, column=0, sticky="nsew", padx=20, pady=10)
            # Fill canvas with themed background
            try:
                cw = ui["canvas"].winfo_width()
                ch = ui["canvas"].winfo_height()
                if cw > 1 and ch > 1:
                    ui["canvas"].itemconfig("fav_inner_frame", width=cw, height=ch)
            except Exception:
                pass

            return



        # Store the exact rendered list so organize-mode reorder operates on correct indices
        app._fav_display_items = [item for _, item, _ in rows]

        FAV_COLS = 3

        row = col = 0

        for card_idx, (i, item, path) in enumerate(rows):

            border = pal.get("border_color", pal["panel2"])
            card = tk.Frame(ui["inner"], bd=0, padx=0, pady=0, bg=pal["panel"],
                            highlightthickness=1, highlightbackground=border)

            card.grid(row=row, column=col, padx=6, pady=6, sticky='nsew')
            card.columnconfigure(0, weight=1)

            if path and path.exists():

                self._attach_card_thumb(
                    card, pal, path,
                    on_click=lambda e, p=path, d=item, u=ui, cidx=card_idx: app._on_fav_card_click(e, p, d, u, cidx),
                    on_double=lambda e, p=path, d=item, u=ui: app._double_click_visual_item(u, p, d),
                    on_context=lambda e, p=path: app.show_gallery_context_menu(e, p),
                )

            else:

                snippet = (item.get("theme_sentence") or item.get("prompt") or "")[:100]

                tl = tk.Label(
                    card,
                    text=snippet + ("…" if len(snippet) == 100 else ""),
                    wraplength=220,
                    justify="left",
                    cursor="hand2",
                    font=app.small_font,
                    bg=pal["panel"],
                    fg=pal["text"],
                )

                tl.pack()

                tl.bind("<Button-1>", lambda e, d=item, u=ui: app._select_visual_item(u, None, d))

            # Filename label — matches Gallery view style
            filename_text = path.name if path else ((item.get("theme_sentence") or item.get("prompt") or "")[:40])
            name_label = tk.Label(
                card,
                text=filename_text,
                wraplength=220,
                height=2,
                font=app.small_font,
                bg=pal["panel"],
                fg=pal["text"],
                anchor="w",
                justify="left",
                padx=6,
                pady=2,
            )
            name_label.pack(fill="x")
            if path:
                name_label.bind("<Button-1>", lambda e, p=path, d=item, u=ui, cidx=card_idx: app._on_fav_card_click(e, p, d, u, cidx))

            # File size + resolution info (dimensions via shared cache)
            if path and path.exists():
                try:
                    size_bytes = path.stat().st_size
                    size_str = f"{size_bytes / 1_048_576:.1f} MB" if size_bytes >= 1_048_576 else f"{size_bytes / 1024:.0f} KB"
                    w_px, h_px = self._img_dims(path)
                    info_text = f"{w_px}\u00d7{h_px}  \u2022  {size_str}" if w_px and h_px else size_str
                except Exception:
                    info_text = ""
                info_lbl = tk.Label(card, text=info_text, fg=pal["muted"], font=app.tinyfont,
                                    bg=pal["panel"], anchor="w", justify="left", padx=6, pady=0)
                info_lbl.pack(fill="x")
                info_lbl.bind("<Button-1>", lambda e, p=path, d=item, u=ui, cidx=card_idx: app._on_fav_card_click(e, p, d, u, cidx))

            # Tags label — matches Gallery view (fall back to original image's tags)
            if path:
                fav_tags = self._get_tags_with_fallback(path, fav_item=item)
                fav_tags_label = tk.Label(card, text=', '.join(fav_tags[:3]),
                                          fg=pal.get("tag_fg", pal["muted"]), font=app.small_font,
                                          bg=pal["panel"], anchor="w", justify="left", padx=6, pady=4)
                fav_tags_label.pack(fill="x")
                fav_tags_label.bind("<Button-1>", lambda e, p=path, d=item, u=ui, cidx=card_idx: app._on_fav_card_click(e, p, d, u, cidx))

            # Heart button for favorites (always filled, click to remove)
            if path:
                try:
                    from icons import get_icon
                    accent = pal.get("accent", pal["progress"])
                    heart_icon = get_icon("heart_filled", size=36, color=accent)  # Doubled from 18 to 36

                    _fav_btn_bg = pal.get("panel", "#1e1e2e")
                    try:
                        _fav_btn_bg = card.cget("bg")
                    except Exception:
                        pass
                    heart_btn = tk.Button(card, image=heart_icon,
                                         bg=_fav_btn_bg,
                                         activebackground=pal.get("panel2", _fav_btn_bg),
                                         bd=0, highlightthickness=0,
                                         cursor="hand2", relief="flat")
                    heart_btn.image = heart_icon
                    heart_btn._icon_ref = heart_icon
                    heart_btn._img_path = path  # store for theme-change re-rendering
                    heart_btn.place(relx=1.0, rely=1.0, x=-12, y=-12, anchor="se")  # Adjusted position for larger icon
                    
                    # For favorites, clicking heart removes from favorites
                    heart_btn.bind('<Button-1>', lambda e, p=path, d=item: self._on_fav_heart_click(e, p, d, heart_btn))
                except Exception as e:
                    logger.error(f"Error creating favorites heart button: {e}")

            # Register card so organize-mode highlight and index lookup work
            cards[card_idx] = (card, name_label, item)

            # Advance grid position
            col += 1
            if col >= FAV_COLS:
                col = 0
                row += 1


    def _propagate_tags_to_related(self, path, tags: list) -> list:
        """Apply tags to path and all its related sibling paths.

        Returns the full list of paths that were tagged.
        """
        app = self.app
        all_paths = app._resolve_related_paths(path)
        if all_paths and tags:
            add_tags_to_paths(all_paths, tags)
        return all_paths


    def _rebuild_fav_grid(self, cols):

        """Re-grid all favorites cards based on column count."""

        app = self.app
        for c in range(cols):
            app.gallery_fav_inner.columnconfigure(c, weight=1)

        for i, card_frame in enumerate(app.gallery_fav_inner.winfo_children()):

            card_frame.grid(row=i // cols, column=i % cols, padx=5, pady=6, sticky='nsew')


    def _rebuild_manual_grid(self, cols):

        """Re-grid all manual cards based on column count."""

        app = self.app
        for c in range(cols):
            app.gallery_manual_inner.columnconfigure(c, weight=1)

        for i, card_frame in enumerate(app.gallery_manual_inner.winfo_children()):
            card_frame.grid(row=i // cols, column=i % cols, padx=5, pady=6, sticky='nsew')


    def _rebuild_styled_grid(self, cols):

        """Re-grid all styled cards based on column count."""

        app = self.app
        for c in range(cols):
            app.gallery_styled_inner.columnconfigure(c, weight=1)

        for i, card_frame in enumerate(app.gallery_styled_inner.winfo_children()):
            card_frame.grid(row=i // cols, column=i % cols, padx=5, pady=6, sticky='nsew')


    def _refresh_fav_card_highlights(self):
        app = self.app
        pal = app.THEMES.get(app.current_theme_name, app.THEMES["darkforest"])
        accent = pal.get("accent", pal["progress"])
        border = pal.get("border_color", pal["panel2"])
        for card_id, (card, name_label, item) in app.favorite_cards.items():
            is_sel = item is app.favorite_selected_item
            bg = pal.get("surface", pal["panel2"]) if is_sel else pal["panel"]
            hi = accent if is_sel else border
            card.config(bg=bg, highlightbackground=hi, highlightthickness=2 if is_sel else 1)
            name_label.config(bg=bg, fg=pal["text"])


    def _refresh_gallery_tag_filter(self):
        """Refresh tag list and reload current view with tag filtering applied.
        Delegates to _refresh_tag_ui for consistency."""
        app = self.app
        app._refresh_tag_ui(status_msg=None, keep_selection=True)


    def _refresh_tag_ui(self, status_msg=None, keep_selection=True):
        """Centralized tag app.UI refresh - call after ANY tag change.

        Rebuilds dropdown and reloads current view with proper filtering.
        Preserves current selection by default, or falls back to 'All tags'.
        """
        app = self.app
        # Check if tag UI exists - if not, just reload current view without tag filtering
        if not hasattr(app, 'gallery_tag_var') or not hasattr(app, 'gallery_tag_combo'):
            self._refresh_current_view()
            if status_msg:
                app.status_var.set(status_msg)
            return

        # Get current selection before rebuilding
        current_tag = app.gallery_tag_var.get()

        # Rebuild tag dropdown from current storage
        tags = ['All tags', 'Untagged'] + get_all_tags()
        app.gallery_tag_combo['values'] = tags

        # Restore or reset selection — always call set() so the combobox
        # display refreshes even when the deleted tag was previously shown.
        new_selection = current_tag if (keep_selection and current_tag in tags) else 'All tags'
        app.gallery_tag_var.set(new_selection)
        # Force the readonly combobox to visually reflect the new value
        app.gallery_tag_combo.set(new_selection)

        # Reload current view (handles all modes including ratio views)
        self._refresh_current_view()

        # Show status message
        if status_msg:
            app.status_var.set(status_msg)
        else:
            effective_tag = app.gallery_tag_var.get()
            view_mode = app._gallery_view_mode()
            if effective_tag and effective_tag != 'All tags':
                app.status_var.set(f'{view_mode} filtered by tag: {effective_tag}')
            else:
                app.status_var.set(f'{view_mode} reloaded')


    def _render_visible_cards(self):
        """Promote placeholders → real cards for the visible range; demote the rest.

        Safe to call repeatedly; idempotent for slots already in the right state.
        In organize mode all slots are promoted so drag indices stay contiguous.
        """
        app = self.app
        n = len(app.gallery_images)
        if not n:
            return

        cols = max(1, app._gallery_cols)

        first_idx, last_idx = app._gallery_visible_range()

        visible_set = set(range(first_idx, last_idx + 1))

        # Build reverse lookup once for O(1) index resolution below
        path_to_idx = {str(p): i for i, p in enumerate(app.gallery_images)}

        # --- Demote real cards outside visible range back to placeholders ---
        to_demote = []
        for key in list(app.gallery_cards):
            idx = path_to_idx.get(key)
            if idx is None or idx not in visible_set:
                to_demote.append(key)

        for key in to_demote:
            entry = app.gallery_cards.pop(key, None)
            if entry:
                card = entry[0]
                idx = path_to_idx.get(key)
                card.destroy()
                if idx is not None:
                    row, col = idx // cols, idx % cols
                    app._make_gallery_placeholder(idx, row, col)

        # --- Promote placeholders in visible range to real cards ---
        for idx in range(first_idx, last_idx + 1):
            img_path = app.gallery_images[idx]
            key = str(img_path)
            if key in app.gallery_cards:
                continue  # already a real card

            # Destroy placeholder for this slot if one exists
            ph = app._gallery_placeholders.pop(idx, None)
            if ph is not None:
                ph.destroy()

            row, col = idx // cols, idx % cols
            app.create_gallery_card(img_path, row, col, idx)

        # scrollregion tracks gallery_inner's actual content (placeholders fill it)
        app.gallery_canvas.configure(
            scrollregion=app.gallery_canvas.bbox('all') or (0, 0, 1, 1)
        )


    def _resolve_related_paths(self, path) -> list[str]:
        """Return all known physical paths that represent the same image.

        For a generated image this includes its favorite copy (if any).
        For a favorite copy this includes the original generated file.
        Always returns at least the input path when it exists.
        Paths are de-duplicated by resolved absolute path.
        """
        app = self.app
        try:
            target = Path(path).resolve()
        except Exception:
            return [str(path)]

        seen = set()
        result = []

        def _add(p):
            try:
                rp = Path(p).resolve()
                key = str(rp)
                if key not in seen and rp.exists():
                    seen.add(key)
                    result.append(str(rp))
            except Exception:
                pass

        _add(target)

        target_str = str(target)
        target_name = target.name

        favorites = getattr(app, "favorites", []) or []
        if not favorites:
            try:
                favorites = load_json_list(app.FAVORITES_LOG)
            except Exception:
                favorites = []
        for item in favorites:
            orig = item.get("original_image_path") or ""
            img  = item.get("image_path") or ""
            cpy  = item.get("copied_image_path") or ""

            candidates = [c for c in (orig, img, cpy) if c]
            resolved_candidates = []
            for c in candidates:
                try:
                    resolved_candidates.append((c, str(Path(c).resolve())))
                except Exception:
                    pass

            # Check if any candidate matches the input path
            match = any(rc == target_str for _, rc in resolved_candidates)
            if not match:
                # Fallback: match by filename (handles renamed-copy edge case)
                match = any(Path(c).name == target_name for c, _ in resolved_candidates)

            if match:
                for _, rc in resolved_candidates:
                    _add(rc)

        return result


    def _select_manual_image(self, path):
        """Handle manual image selection with highlighting."""
        app = self.app
        app.selected_gallery_path = Path(path)
        app.selected_manual_path = Path(path)
        app.show_preview_in_left_panel(path, f'Manual: {path.name}')
        app.status_var.set(f'Selected manual: {path.name}')
        app._update_manual_highlight(app.selected_manual_path)


    def _select_styled_image(self, path):
        """Handle styled image selection with highlighting."""
        app = self.app
        app.selected_gallery_path = Path(path)
        app.selected_styled_path = Path(path)
        app.show_preview_in_left_panel(path, f'Styled: {path.name}')
        app.status_var.set(f'Selected styled: {path.name}')
        app._update_styled_highlight(app.selected_styled_path)


    def _select_visual_item(self, ui, path, data):
        app = self.app
        mode = ui["mode"]
        app.set_prompt_text(data.get("prompt", ""))
        if path:
            app.show_preview_in_left_panel(path, f"{mode.capitalize()} selection: {path.name}")
        app.favorite_selected_item = data
        app._update_fav_card_highlight(data)


    def _style_applied_error(self, error):
        """Handle style application error."""
        app = self.app
        app.status_var.set(f"❌ Style transfer error: {error}")
        app._dialog.error(
            "Style Transfer Error",
            f"An error occurred during style transfer:\n\n{error}\n\n"
            f"This could be due to:\n"
            f"• Missing OpenCV installation\n"
            f"• Corrupted image file\n"
            f"• Insufficient system resources\n\n"
            f"Please try installing OpenCV: pip install opencv-python"
        )


    def _style_applied_failed(self, style):
        """Handle failed style application."""
        app = self.app
        app.status_var.set(f"❌ Failed to apply style '{style}' - no image created")
        app._dialog.error(
            "Style Transfer Failed",
            f"Could not apply style '{style}'.\n\n"
            f"Possible causes:\n"
            f"• Image file is corrupted or unsupported\n"
            f"• OpenCV libraries missing\n"
            f"• Insufficient memory for processing\n\n"
            f"Please check the image file and try again."
        )


    def _style_applied_success(self, styled_path, style):
        """Update app.UI after successful style application."""
        app = self.app
        app.status_var.set(f"✅ {style} style applied!")
        app.load_gallery()

        # Show the styled image in preview
        app.show_preview_in_left_panel(styled_path, f"Styled image: {style}")

        # Switch to Styled view and notify
        app.gallery_view_var.set("Styled")
        app._on_gallery_view_changed()
        app._dialog.info("Style Applied", f"Style '{style}' applied successfully!\n\nImage saved to Styled view.\nSwitching to the Styled tab.")


    def _update_fav_card_highlight(self, selected_item):
        app = self.app
        pal = app.THEMES.get(app.current_theme_name, app.THEMES["darkforest"])
        accent = pal.get("accent", pal["progress"])
        border = pal.get("border_color", pal["panel2"])
        for card_id, (card, name_label, item) in app.favorite_cards.items():
            is_sel = item is selected_item
            bg = pal.get("surface", pal["panel2"]) if is_sel else pal["panel"]
            hi = accent if is_sel else border
            card.config(bg=bg, highlightbackground=hi, highlightthickness=2 if is_sel else 1)
            name_label.config(bg=bg, fg=pal["text"])
            for child in card.winfo_children():
                if isinstance(child, tk.Label) and child is not name_label:
                    child.config(bg=bg, fg=pal["text"])
                elif isinstance(child, tk.Button):
                    child.config(bg=bg, activebackground=pal["panel2"])


    def _update_gallery_highlight(self, selected_path):
        """Apply selection highlight to the selected gallery card (legacy single-select)."""
        app = self.app
        app._update_gallery_highlight_multi()


    def _update_gallery_highlight_multi(self):
        """Apply selection highlight to all selected gallery cards (multi-select support)."""
        app = self.app
        pal = app.THEMES.get(app.current_theme_name, app.THEMES["darkforest"])
        accent = pal.get("accent", pal["progress"])
        border = pal.get("border_color", pal["panel2"])
        surface = pal.get("surface", pal["panel2"])
        
        for path_str, card_data in app.gallery_cards.items():
            # Handle variable-length card data (some have 2, 3, 4, or 6 elements)
            card = card_data[0] if isinstance(card_data, (tuple, list)) else card_data
            name_label = card_data[1] if len(card_data) > 1 else None
            tags_label = card_data[2] if len(card_data) > 2 else None
            heart_btn = card_data[3] if len(card_data) > 3 else None
            
            is_multi_sel = path_str in app.selected_gallery_paths
            is_primary = app.selected_gallery_path and path_str == str(app.selected_gallery_path)
            
            if is_primary and len(app.selected_gallery_paths) > 1:
                # Primary selection in multi-select: accent border, surface bg
                bg = surface
                hi = accent
                thickness = 3
            elif is_multi_sel:
                # Multi-selected: surface bg, accent border
                bg = surface
                hi = accent
                thickness = 2
            else:
                # Not selected: panel bg, border color
                bg = pal["panel"]
                hi = border
                thickness = 1
            
            card.config(bg=bg, highlightbackground=hi, highlightthickness=thickness)
            for child in card.winfo_children():
                if isinstance(child, tk.Label):
                    child.config(bg=bg)
                elif isinstance(child, tk.Button):
                    child.config(bg=bg, activebackground=pal["panel2"])


    def _update_manual_highlight(self, selected_path):
        """Apply selection highlight to the selected manual card."""
        app = self.app
        pal = app.THEMES.get(app.current_theme_name, app.THEMES["darkforest"])
        sel_str = str(selected_path) if selected_path else None

        for path_str, card_data in app.gallery_manual_cards.items():
            # Handle variable-length card data (2 or 3 elements)
            card = card_data[0] if isinstance(card_data, (tuple, list)) else card_data
            name_label = card_data[1] if len(card_data) > 1 else None
            heart_btn = card_data[2] if len(card_data) > 2 else None
            
            is_sel = path_str == sel_str
            accent = pal.get("accent", pal["progress"])
            border = pal.get("border_color", pal["panel2"])
            bg = pal.get("surface", pal["panel2"]) if is_sel else pal["panel"]
            hi = accent if is_sel else border

            card.config(bg=bg, highlightbackground=hi, highlightthickness=1 if not is_sel else 2)
            name_label.config(bg=bg, fg=pal["text"])

            for child in card.winfo_children():
                if isinstance(child, tk.Label) and child is not name_label:
                    child.config(bg=bg)
                elif isinstance(child, tk.Button):
                    child.config(bg=bg, activebackground=pal["panel2"])


    def _update_styled_highlight(self, selected_path):
        """Apply selection highlight to the selected styled card."""
        app = self.app
        pal = app.THEMES.get(app.current_theme_name, app.THEMES["darkforest"])
        sel_str = str(selected_path) if selected_path else None

        for path_str, card_data in app.gallery_styled_cards.items():
            # Handle variable-length card data (2 or 3 elements)
            card = card_data[0] if isinstance(card_data, (tuple, list)) else card_data
            name_label = card_data[1] if len(card_data) > 1 else None
            heart_btn = card_data[2] if len(card_data) > 2 else None
            
            is_sel = path_str == sel_str
            accent = pal.get("accent", pal["progress"])
            border = pal.get("border_color", pal["panel2"])
            bg = pal.get("surface", pal["panel2"]) if is_sel else pal["panel"]
            hi = accent if is_sel else border

            card.config(bg=bg, highlightbackground=hi, highlightthickness=1 if not is_sel else 2)
            name_label.config(bg=bg, fg=pal["text"])

            for child in card.winfo_children():
                if isinstance(child, tk.Label) and child is not name_label:
                    child.config(bg=bg)
                elif isinstance(child, tk.Button):
                    child.config(bg=bg, activebackground=pal["panel2"])


    def _widget_to_card_index(self, widget):
        app = self.app
        return None  # Organize Mode removed


    def apply_artistic_filter(self, style_name):

        """Apply a selected artistic filter using PIL and save as a new file."""

        app = self.app
        if not app.selected_gallery_path:

            app._dialog.warning("No Selection", "Select an image from the gallery first.")

            return

        

        try:

            from PIL import Image, ImageEnhance, ImageOps

            img = Image.open(app.selected_gallery_path)

            

            suffix = ""

            if style_name == "Vivid":

                # Enhance brightness and contrast

                img = ImageEnhance.Brightness(img).enhance(1.2)

                img = ImageEnhance.Contrast(img).enhance(1.2)

                suffix = "_vivid"

            elif style_name == "Monochrome":

                # Convert to grayscale

                img = ImageOps.grayscale(img)

                suffix = "_bw"

            elif style_name == "Vintage":

                # Warm tint and slightly lower contrast

                img = ImageEnhance.Color(img).enhance(0.8)

                img = ImageEnhance.Contrast(img).enhance(0.9)

                # Simple vintage tint (increase red/yellow slightly if RGB)

                if img.mode == 'RGB':

                    r, g, b = img.split()

                    r = r.point(lambda i: i * 1.1)

                    b = b.point(lambda i: i * 0.9)

                    img = Image.merge('RGB', (r, g, b))

                suffix = "_vintage"

            elif style_name == "Pop":

                # High saturation

                img = ImageEnhance.Color(img).enhance(1.6)

                suffix = "_pop"

            

            # Save new file

            new_name = f"{app.selected_gallery_path.stem}{suffix}.png"

            new_path = app.selected_gallery_path.parent / new_name

            img.save(new_path)

            

            app.status_var.set(f"🎨 {style_name} style saved: {new_name}")

            app.load_gallery()

        except Exception as e:

            app._dialog.error("Filter Error", f"Could not apply '{style_name}' filter. The image may be corrupted or in an unsupported format.")


    def apply_gallery_filter(self):
        """Apply selected gallery filter - now delegates to view-aware handler."""
        app = self.app
        app._on_tag_selected()


    def apply_selected_style(self, dialog):

        """Apply the selected style to the image."""

        app = self.app
        style = app.selected_style_var.get()

        

        if style == "original":

            app._dialog.info("Style Transfer", "No style selected. Using original image.")

            dialog.destroy()

            return

        

        # Show progress

        app.status_var.set(f"Applying {style} style... (this may take 10-20 seconds)")

        dialog.destroy()

        

        # Apply style in a separate thread to avoid freezing UI
        run_background(app._apply_style_thread, style)


    def apply_style_transfer_filter(self, style_key):

        """Apply a selected artistic style using style_transfer.py and save as a new file."""

        app = self.app
        if not app.selected_gallery_path:

            app._dialog.warning("No Selection", "Select an image from the gallery first.")

            return

        

        # Validate style key exists

        from style_transfer import get_style_transfer

        transfer = get_style_transfer()

        if style_key not in transfer.get_style_list():

            app._dialog.error("Unsupported Style", 

                               f"The style '{style_key}' is not available.\n\n"

                               f"Available styles:\n"

                               f"• {', '.join(transfer.get_style_list())}\n\n"

                               f"Please contact support if you need this style added.")

            return

        

        if style_key == "original":

            app._dialog.info("Style Transfer", "No style selected. Using original image.")

            return

        

        # Validate image path exists

        if not app.selected_gallery_path.exists():

            app._dialog.error("File Not Found", 

                               f"The selected image file could not be found:\n\n"

                               f"{app.selected_gallery_path}\n\n"

                               f"Please select a different image and try again.")

            return

        

        # Show progress

        app.status_var.set(f"Applying {style_key} style... (this may take 10-20 seconds)")

        

        # Apply style in a separate thread to avoid freezing UI
        run_background(app._apply_style_thread, style_key)


    def clear_image(self):

        """Clear the preview image from the left panel."""

        app = self.app
        app.last_image_tk = None

        app.image_label.config(image='', text='Selected or generated image will appear here')

        app.preview_source_label.config(text="Nothing selected yet")

        app.preview_name_label.config(text="")

        app.preview_dims_label.config(text="")

        app.preview_size_label.config(text="")


    def copy_to_clipboard(self, text):
        """Copy text to clipboard."""
        app = self.app
        app.root.clipboard_clear()
        app.root.clipboard_append(text)
        app.status_var.set("Copied to clipboard")


    def create_gallery_card(self, img_path, row, col, index):

        """Create clickable thumbnail card with drag-drop support."""

        app = self.app
        pal = app.THEMES.get(app.current_theme_name, app.THEMES["darkforest"])
        border = pal.get("border_color", pal["panel2"])
        card = tk.Frame(app.gallery_inner, bg=pal["panel"],
                        highlightthickness=1, highlightbackground=border, bd=0)

        card.grid(row=row, column=col, padx=6, pady=6, sticky='nsew')

        card.columnconfigure(0, weight=1)

        

        # Thumbnail with Caching

        try:

            from PIL import Image, ImageTk

            path_str = str(img_path)

            if path_str in app.thumb_cache:

                thumb = app.thumb_cache[path_str]

            else:

                img = Image.open(img_path)

                img.thumbnail((240, 135), Image.Resampling.LANCZOS)

                thumb = ImageTk.PhotoImage(img)

                if len(app.thumb_cache) > 200:

                    app.thumb_cache.clear()

                app.thumb_cache[path_str] = thumb

            

            label = tk.Label(card, image=thumb, bg=pal["panel"])

            label.image = thumb  # Keep reference

            label.grid(row=0, column=0, pady=(4, 4), padx=4)

            try:
                self._fade_in_thumb(label, thumb, steps=4, interval=35)
            except Exception:
                pass

            # Selection & Drag Logic

            label.bind('<Button-1>', lambda e, p=img_path, idx=index: app.on_card_click(e, p, idx))

            label.bind('<Double-Button-1>', lambda e, p=img_path: app.set_gallery_image_as_wallpaper(p))

            label.bind('<Button-3>', lambda e, p=img_path: app.show_gallery_context_menu(e, p))

            card.bind('<Button-1>', lambda e, p=img_path, idx=index: app.on_card_click(e, p, idx))

            card.bind('<Button-3>', lambda e, p=img_path: app.show_gallery_context_menu(e, p))

        except Exception as e:

            logger.error(f"Gallery thumbnail error for {img_path}: {e}")

            tk.Label(card, text=f'❌ {img_path.name}', bg='red', fg='white').grid(row=0, column=0)

        

        # Name + actions

        name_label = tk.Label(card, text=img_path.name,
                               wraplength=220, height=2, font=app.small_font, bg=pal["panel"], fg=pal["text"], anchor="w", justify="left",
                               padx=6, pady=2)

        name_label.grid(row=1, column=0, sticky='ew')

        # File size + resolution info
        try:
            stat = img_path.stat()
            size_bytes = stat.st_size
            if size_bytes >= 1_048_576:
                size_str = f"{size_bytes / 1_048_576:.1f} MB"
            else:
                size_str = f"{size_bytes / 1024:.0f} KB"
            from PIL import Image as _PILImage
            with _PILImage.open(img_path) as _im:
                w_px, h_px = _im.size
            info_text = f"{w_px}×{h_px}  •  {size_str}"
        except Exception:
            info_text = ""

        info_label = tk.Label(card, text=info_text, fg=pal["muted"], font=app.tinyfont,
                              bg=pal["panel"], anchor="w", justify="left", padx=6, pady=0)
        info_label.grid(row=2, column=0, sticky='ew')

        tags = get_tags_for_image(img_path) or []

        tags_label = tk.Label(card, text=', '.join(tags[:3]), fg=pal.get("tag_fg", pal["muted"]), font=app.small_font,
                              bg=pal["panel"], anchor="w", justify="left", padx=6, pady=4)

        tags_label.grid(row=3, column=0, sticky='ew')

        for sub in (name_label, info_label, tags_label):
            sub.bind('<Button-1>', lambda e, p=img_path, idx=index: app.on_card_click(e, p, idx))

        # Heart button (positioned in bottom-right corner)
        heart_btn = self._create_heart_button(card, img_path, pal)
        if heart_btn:
            heart_btn.place(relx=1.0, rely=1.0, x=-12, y=-12, anchor="se")  # Adjusted for larger icon

        app.gallery_cards[str(img_path)] = (card, name_label, tags_label, heart_btn)


    def delete_selected(self):
        """Delete selected image + tags, with proper tag app.UI refresh."""
        app = self.app
        if not app.selected_gallery_path:
            app._dialog.warning('No Selection', 'Select an image first.')
            return

        if app._dialog.ask('Confirm', f'Delete {app.selected_gallery_path.name}?'):
            try:
                delete_image_and_tags(str(app.selected_gallery_path))
            except Exception as e:
                logger.error(f"Failed to delete image {app.selected_gallery_path}: {e}")
                app._dialog.error(
                    'Delete Failed',
                    'The image could not be deleted. It may be open in another '
                    'program (image viewer, editor, or wallpaper preview).\n\n'
                    'Close any program using the file and try again.')
                return
            app.selected_gallery_path = None
            app.clear_image()
            # Use centralized refresh to update dropdown and view
            app._refresh_tag_ui(status_msg='🗑️ Deleted.')


    def delete_selected_favorite(self):

        app = self.app
        if not app.favorite_selected_item:

            app._dialog.info("No selection", "Click a Favorite thumbnail first.")

            return

        target = app.favorite_selected_item

        if not app._dialog.ask("Delete Favorite", "Remove the selected item from Favorites?"):

            return

        # Delete the copied file from favorites/ folder if it exists.
        # Resolve the favorites-folder path from BOTH the in-memory target
        # (which may have had copied_image_path overwritten by load_favorites)
        # and the original disk JSON entry, to be robust.
        try:
            existing_on_disk = load_json_list(app.FAVORITES_LOG)
        except Exception:
            existing_on_disk = []
        target_key = target.get("saved_at")
        target_prompt = target.get("prompt")
        target_image_path = target.get("image_path") or target.get("copied_image_path")
        target_name = Path(target_image_path).name if target_image_path else None

        # Locate the matching on-disk entry so we preserve its original
        # original_image_path / copied_image_path when we save the trimmed list.
        disk_match = None
        for item in existing_on_disk:
            if target_key is not None and item.get("saved_at") == target_key \
                    and item.get("prompt") == target_prompt:
                disk_match = item
                break
        if disk_match is None and target_name:
            for item in existing_on_disk:
                for k in ("image_path", "copied_image_path"):
                    v = item.get(k)
                    if v and Path(v).name == target_name:
                        disk_match = item
                        break
                if disk_match is not None:
                    break

        # Pick the favorites-folder file path to delete
        file_to_delete = None
        if disk_match:
            for k in ("copied_image_path", "image_path"):
                v = disk_match.get(k) or target.get(k)
                if v and Path(v).exists() and app.FAVORITES_DIR in Path(v).parents:
                    file_to_delete = Path(v)
                    break
        if file_to_delete is None:
            v = target.get("copied_image_path") or target.get("image_path")
            if v:
                try:
                    p = Path(v)
                    if p.exists() and p.is_file() and app.FAVORITES_DIR in p.parents:
                        file_to_delete = p
                except Exception:
                    pass
        if file_to_delete is not None:
            try:
                file_to_delete.unlink()
            except Exception:
                pass  # Ignore file deletion errors

        # Save the trimmed list back to disk. We deliberately use the
        # existing_on_disk list (preserving each entry's original fields
        # like original_image_path) rather than app.favorites, because
        # load_favorites() overwrites image_path / copied_image_path in
        # memory with the favorites-folder path — writing that back would
        # silently clobber the link to the source image.
        if disk_match is not None:
            updated = [item for item in existing_on_disk if item is not disk_match]
        else:
            # Fallback: remove by saved_at+prompt, else leave the list alone
            updated = [item for item in existing_on_disk
                       if not (target_key is not None
                               and item.get("saved_at") == target_key
                               and item.get("prompt") == target_prompt)]
        save_json_list(app.FAVORITES_LOG, updated)

        # Keep app.favorites in sync so subsequent UI reads are consistent
        try:
            app.favorites = [item for item in app.favorites if item is not target]
        except Exception:
            pass

        app.favorite_selected_item = None

        app.load_favorites()  # Refresh favorites view

        app.status_var.set("Favorite deleted.")


    def double_click_set_wallpaper(self, path):
        app = self.app
        if not app.WINDOWS:
            app._dialog.info("Windows only", "Setting wallpaper is only supported on Windows.")
            return
        try:
            ok = set_wallpaper(Path(path))
            if ok:
                app.status_var.set(f"Wallpaper set: {Path(path).name}")
                app.slideshow.reset_timer()
            else:
                app.status_var.set(f"Could not set wallpaper: {Path(path).name}")
        except Exception as e:
            app.status_var.set(f"Wallpaper error: {e}")
            app._dialog.error("Wallpaper Error", "Could not set this image as wallpaper. Try right-clicking the image in the Gallery instead.")


    def favorite_current_prompt(self):

            app = self.app
            data = app.selected_prompt()

            if not data:

                app._dialog.info("No preview", "Generate a preview first.")

                return

            # Check if we have an image to copy to favorites
            image_to_copy = None
            if app.last_image_path and Path(app.last_image_path).exists():
                image_to_copy = app.last_image_path

            existing = load_json_list(app.FAVORITES_LOG)
            
            if image_to_copy:
                original_resolved = Path(image_to_copy).resolve()
                # Check if already favorited by comparing resolved paths.
                # Must check BOTH copied_image_path AND original_image_path
                # against the source image, otherwise the check never matches.
                if any(
                    (item.get('copied_image_path') and Path(item.get('copied_image_path')).resolve() == original_resolved)
                    or (item.get('original_image_path') and Path(item.get('original_image_path')).resolve() == original_resolved)
                    for item in existing
                ):
                    app.status_var.set("Image already in favorites.")
                    return
                # Basename fallback: catch favorites created by older app
                # versions that don't have original_image_path set.
                try:
                    target_name = Path(image_to_copy).name.lower()
                    if target_name and app.FAVORITES_DIR.exists():
                        for f in app.FAVORITES_DIR.iterdir():
                            if (f.is_file()
                                    and f.suffix.lower() in app.IMAGE_EXTS
                                    and f.name.lower() == target_name):
                                app.status_var.set("Image already in favorites.")
                                return
                except Exception:
                    pass

            # Determine the final image path for the favorite
            final_image_path = None
            needs_copy = True
            
            if image_to_copy:
                # Check if the selected image is already inside wallpapers/favorites/
                if app.FAVORITES_DIR in Path(image_to_copy).parents:
                    # Image is already in favorites folder, use it directly
                    final_image_path = Path(image_to_copy)
                    needs_copy = False
                else:
                    # Need to copy to favorites folder
                    dest_filename = Path(image_to_copy).name
                    dest_path = app.FAVORITES_DIR / dest_filename
                    
                    # Handle filename collisions with fav2, fav3, etc. suffix
                    counter = 2
                    while dest_path.exists():
                        # Check if it's the same file (same resolved path)
                        if dest_path.resolve() == original_resolved:
                            # Same file, reuse it
                            final_image_path = dest_path
                            needs_copy = False
                            break
                        
                        # Different file, create unique name
                        stem = Path(image_to_copy).stem
                        suffix = Path(image_to_copy).suffix
                        dest_filename = f"{stem}_fav{counter}{suffix}"
                        dest_path = app.FAVORITES_DIR / dest_filename
                        counter += 1
                    
                    if needs_copy:
                        final_image_path = dest_path
                        try:
                            import shutil
                            shutil.copy2(image_to_copy, dest_path)
                        except Exception:
                            # If copy fails, skip copying but still save metadata
                            needs_copy = False

            # Create metadata entry with both paths
            entry = {
                'saved_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'original_image_path': str(image_to_copy) if image_to_copy else None,
                'image_path': str(final_image_path) if final_image_path else None,
                'copied_image_path': str(final_image_path) if needs_copy and final_image_path else None,
                'prompt': data.get('prompt', ''),
                'theme_sentence': data.get('theme_sentence', 'Prompt favorite'),
                'style_mode': data.get('style_mode', 'stylized'),
                'subject': data.get('subject'),
                'art_style': data.get('art_style')
            }

            existing.append(entry)
            save_json_list(app.FAVORITES_LOG, existing)

            app.status_var.set("Current prompt added to favorites.")
            app.load_favorites()


    def get_active_tag(self):
        """Return the currently selected tag filter, or None if 'All tags' / unset."""
        app = self.app
        tag = getattr(app, 'gallery_tag_var', None)
        if tag is None:
            return None
        val = tag.get()
        return val if val and val != 'All tags' else None


    def load_favorites(self, tag_filter=None):
        """Load favorites."""
        app = self.app
        # Purge JSON entries for files that were deleted outside the app
        try:
            self._purge_stale_favorites_log()
        except Exception as e:
            logger.warning(f"load_favorites: purge failed: {e}")

        # One-shot repair: backfill missing original_image_path on entries
        # whose source file can be located in generated/manual/styled dirs.
        # This is what makes the heart icon on the Gallery/Styled/Manual
        # views correctly show as filled for favorites that were created by
        # older app versions or migrated from the legacy top-level favorites
        # folder (where original_image_path was never recorded).
        try:
            self._backfill_original_image_paths()
        except Exception as e:
            logger.warning(f"load_favorites: backfill failed: {e}")

        raw_favorites = load_json_list(app.FAVORITES_LOG)

        # --- Authoritative source: files present in FAVORITES_DIR ---
        # Build a lookup from filename -> best-matching JSON record so
        # generate-from-favorite still has prompt/metadata available.
        meta_by_name = {}
        for item in raw_favorites:
            p = item.get("image_path") or item.get("copied_image_path") or ""
            if p:
                meta_by_name[Path(p).name] = item

        fav_files = sorted(
            (f for f in app.FAVORITES_DIR.iterdir()
             if f.is_file() and f.suffix.lower() in app.IMAGE_EXTS),
            key=lambda f: f.stat().st_mtime,
            reverse=True,
        )

        app.favorites = []
        for fav_file in fav_files:
            meta = dict(meta_by_name.get(fav_file.name, {}))
            meta["image_path"] = str(fav_file)
            meta["copied_image_path"] = str(fav_file)
            app.favorites.append(meta)

        logger.info(f"[Favorites] folder={len(fav_files)} json_records={len(raw_favorites)}")

        # Apply custom order if one exists from Organize Mode
        if app._fav_custom_order is not None:
            def _fav_key(x):
                return x.get("image_path") or x.get("copied_image_path") or ""
            by_path = {_fav_key(x): x for x in app.favorites}
            ordered = [by_path[p] for p in app._fav_custom_order if p in by_path]
            ordered += [x for x in app.favorites if _fav_key(x) not in set(app._fav_custom_order)]
            display_items = ordered
        else:
            # Apply the same sort as Gallery
            current_sort = app.sort_combo_var.get() if hasattr(app, 'sort_combo_var') else "Date Newest"
            sorted_favs = list(app.favorites)
            def _fav_path(x):
                return x.get("image_path") or x.get("copied_image_path") or ""
            if current_sort in ("Date Newest", "Date Oldest"):
                def _fav_mtime(x):
                    p = _fav_path(x)
                    try:
                        return Path(p).stat().st_mtime if p else 0
                    except Exception:
                        return 0
                sorted_favs.sort(key=_fav_mtime, reverse=(current_sort == "Date Newest"))
            elif current_sort in ("Name A-Z", "Name Z-A"):
                sorted_favs.sort(key=lambda x: Path(_fav_path(x)).name.lower(), reverse=(current_sort == "Name Z-A"))
            elif current_sort == "Size Largest":
                def _fav_size(x):
                    p = _fav_path(x)
                    try:
                        return os.path.getsize(p) if p else 0
                    except Exception:
                        return 0
                sorted_favs.sort(key=_fav_size, reverse=True)
            elif current_sort == "Size Smallest":
                def _fav_size(x):
                    p = _fav_path(x)
                    try:
                        return os.path.getsize(p) if p else 0
                    except Exception:
                        return 0
                sorted_favs.sort(key=_fav_size, reverse=False)
            elif current_sort == "Resolution Largest":
                try:
                    def _fav_resolution(x):
                        p = _fav_path(x)
                        if not p:
                            return (0, 0)
                        return self._img_dims(p)
                    sorted_favs.sort(key=lambda x: (_fav_resolution(x)[0] * _fav_resolution(x)[1]), reverse=True)
                except Exception:
                    pass
            elif current_sort == "Resolution Smallest":
                try:
                    def _fav_resolution(x):
                        p = _fav_path(x)
                        if not p:
                            return (0, 0)
                        return self._img_dims(p)
                    sorted_favs.sort(key=lambda x: (_fav_resolution(x)[0] * _fav_resolution(x)[1]), reverse=False)
                except Exception:
                    sorted_favs.sort(key=lambda x: Path(_fav_path(x)).name.lower())
            display_items = sorted_favs

        # Apply tag filter
        if tag_filter:
            if tag_filter == 'Untagged':
                # Show images with no tags
                display_items = [item for item in display_items
                                if not get_tags_for_image(_fav_path(item))]
            else:
                # Show images with specific tag
                display_items = [item for item in display_items
                                if tag_filter in get_tags_for_image(_fav_path(item))]

        app._populate_visual_grid(app.gallery_favorites_ui, display_items, "favorites")


    def load_gallery(self):

        """Load and display gallery images (excluding favorites and styled) with custom sorting."""

        app = self.app
        try:

            # Only load from manual and generated folders, NOT favorites or styled
            from set_wallpaper import GENERATED_DIR
            raw_images = collect_wallpapers([app.MANUAL_DIR, GENERATED_DIR]) or []

            

            # Apply Sorting based on selected mode

            current_sort = app.sort_combo_var.get()

            

            if current_sort == "Date Newest":

                # Sort by date descending (newest first)

                images_with_stats = [(img, img.stat().st_mtime) for img in raw_images]

                images_with_stats.sort(key=lambda x: x[1], reverse=True)

                raw_images = [x[0] for x in images_with_stats]

            elif current_sort == "Date Oldest":

                # Sort by date ascending (oldest first)

                images_with_stats = [(img, img.stat().st_mtime) for img in raw_images]

                images_with_stats.sort(key=lambda x: x[1], reverse=False)

                raw_images = [x[0] for x in images_with_stats]

            elif current_sort == "Name A-Z":

                # Sort by name ascending

                raw_images.sort(key=lambda x: str(x.name).lower())

            elif current_sort == "Name Z-A":

                # Sort by name descending

                raw_images.sort(key=lambda x: str(x.name).lower(), reverse=True)

            elif current_sort == "Size Largest":

                # Sort by file size descending (largest first)

                try:

                    raw_images.sort(key=lambda x: x.stat().st_size, reverse=True)

                except OSError:

                    raw_images.sort(key=lambda x: str(x.name).lower())


            elif current_sort == "Size Smallest":

                # Sort by file size ascending (smallest first)

                try:

                    raw_images.sort(key=lambda x: x.stat().st_size, reverse=False)

                except OSError:

                    raw_images.sort(key=lambda x: str(x.name).lower())

            elif current_sort == "Resolution Largest":

                # Sort by image resolution (width * height) descending

                try:


                    def _img_res(path):

                        w, h = self._img_dims(path)

                        return w * h

                    raw_images.sort(key=_img_res, reverse=True)

                except Exception:

                    raw_images.sort(key=lambda x: str(x.name).lower())


            elif current_sort == "Resolution Smallest":

                # Sort by image resolution (width * height) ascending

                try:


                    def _img_res(path):

                        w, h = self._img_dims(path)

                        return w * h

                    raw_images.sort(key=_img_res, reverse=False)

                except Exception:

                    raw_images.sort(key=lambda x: str(x.name).lower())

            else:

                # Default to Date Newest

                images_with_stats = [(img, img.stat().st_mtime) for img in raw_images]

                images_with_stats.sort(key=lambda x: x[1], reverse=True)

                raw_images = [x[0] for x in images_with_stats]

            

            # If a custom order exists (from Organize Mode), apply it
            if app._gallery_custom_order is not None:
                order_strs = [str(p) for p in app._gallery_custom_order]
                ordered = {str(p): p for p in raw_images}
                raw_images = [ordered[s] for s in order_strs if s in ordered]
                # Append any new files not yet in the custom order
                raw_images += [p for p in ordered.values() if str(p) not in order_strs]

            app.gallery_images = raw_images

            # Apply tag filter
            tag_filter = app.get_active_tag()
            if tag_filter:
                if tag_filter == 'Untagged':
                    # Show images with no tags
                    app.gallery_images = [img for img in app.gallery_images if not get_tags_for_image(img)]
                else:
                    # Show images with specific tag
                    app.gallery_images = [img for img in app.gallery_images if tag_filter in get_tags_for_image(img)]

            app.slideshow.load_gallery(app.gallery_images)

        except Exception as e:

            app.status_var.set(f'Gallery load failed: {e}')

            app.gallery_images = []

        

        # Clear existing real cards
        for card_data in app.gallery_cards.values():
            card = card_data[0] if isinstance(card_data, (tuple, list)) else card_data
            card.destroy()
        app.gallery_cards.clear()

        # Clear existing placeholders
        for ph in app._gallery_placeholders.values():
            ph.destroy()
        app._gallery_placeholders.clear()

        # Cancel any stale layout or scroll jobs from a previous load
        for job_attr in ('_gallery_layout_job', '_gallery_scroll_job'):
            job = getattr(app, job_attr, None)
            if job is not None:
                try:
                    app.gallery_canvas.after_cancel(job)
                except Exception:
                    pass
                setattr(app, job_attr, None)

        # Compute column count from current canvas width (default 3 before first layout)
        w = app.gallery_canvas.winfo_width()
        cols = min(3, max(1, w // 250)) if w > 1 else 3
        app._gallery_cols = cols
        # Reset BOTH width and height — ratio views lock height=ch which
        # clamps scrollregion if not cleared (Tk: height<=0 uses natural size).
        app.gallery_canvas.itemconfig("inner_frame", width=max(w, 1), height=0)
        for c in range(cols):
            app.gallery_inner.columnconfigure(c, weight=1)

        # Create a lightweight placeholder Frame for every image slot.
        # Placeholders hold gallery_inner at the correct total height so the
        # scrollbar is accurate before any thumbnails are loaded.
        n = len(app.gallery_images)
        if n == 0:
            # Empty-state message for main Gallery view
            pal = app.THEMES.get(app.current_theme_name, app.THEMES["darkforest"])
            app.gallery_inner.columnconfigure(0, weight=1)
            app.gallery_inner.rowconfigure(0, weight=1)
            tk.Label(
                app.gallery_inner,
                text="No wallpapers yet. Generate or add images to get started.",
                bg=pal["bg"], fg=pal["text"], font=app.small_font,
                pady=10,
            ).grid(row=0, column=0, sticky="nsew")
            # Fill canvas with themed background
            try:
                cw = app.gallery_canvas.winfo_width()
                ch = app.gallery_canvas.winfo_height()
                if cw > 1 and ch > 1:
                    app.gallery_canvas.itemconfig("inner_frame", width=cw, height=ch)
            except Exception:
                pass
        else:
            for idx in range(n):
                app._make_gallery_placeholder(idx, idx // cols, idx % cols)

        # scrollregion is now driven by actual placeholder content
        app.gallery_canvas.update_idletasks()
        app.gallery_canvas.configure(
            scrollregion=app.gallery_canvas.bbox('all') or (0, 0, 1, 1)
        )

        # Promote the initial viewport to real cards
        app._render_visible_cards()

        app.status_var.set(f'Gallery loaded: {len(app.gallery_images)} images')


    def load_gallery_by_ratio(self, ratio_mode, tag_filter=None):
        """Load gallery images filtered by aspect ratio (runs in background thread)."""
        app = self.app
        try:
            from PIL import Image
            from set_wallpaper import GENERATED_DIR

            # Define target ratios with tolerance
            target_ratios = {
                "Ratio 16:9": (16/9, 0.1),
                "Ratio 9:16": (9/16, 0.1),
                "Ratio 1:1": (1.0, 0.05)
            }
            target_ratio, tolerance = target_ratios.get(ratio_mode, (16/9, 0.1))

            # Collect images from manual and generated directories
            raw_images = collect_wallpapers([app.MANUAL_DIR, GENERATED_DIR]) or []
            logger.info(f"Collected {len(raw_images)} raw images for ratio {ratio_mode}")

            # Cache for image dimensions to avoid repeated PIL opens (ratio-specific)
            if not hasattr(app, '_ratio_cache'):
                app._ratio_cache = {}
            # Clear cache for this specific ratio to ensure fresh results
            cache_key = f"{ratio_mode}_"
            keys_to_remove = [k for k in app._ratio_cache.keys() if k.startswith(cache_key)]
            for k in keys_to_remove:
                del app._ratio_cache[k]

            # Filter by aspect ratio with caching
            def matches_ratio(img_path):
                path_str = str(img_path)
                cache_entry = f"{cache_key}{path_str}"
                if cache_entry in app._ratio_cache:
                    return app._ratio_cache[cache_entry]
                try:
                    with Image.open(img_path) as img:
                        w, h = img.size
                        if h == 0:
                            app._ratio_cache[cache_entry] = False
                            return False
                        img_ratio = w / h
                        matches = abs(img_ratio - target_ratio) <= tolerance
                        app._ratio_cache[cache_entry] = matches
                        return matches
                except Exception:
                    app._ratio_cache[cache_entry] = False
                    return False

            filtered_images = [img for img in raw_images if matches_ratio(img)]
            logger.info(f"Filtered to {len(filtered_images)} images matching ratio {ratio_mode}")

            # Apply tag filter if specified
            if tag_filter:
                if tag_filter == 'Untagged':
                    # Show images with no tags
                    filtered_images = [img for img in filtered_images if not get_tags_for_image(img)]
                else:
                    # Show images with specific tag
                    filtered_images = [img for img in filtered_images if tag_filter in get_tags_for_image(img)]

            # Apply sorting
            current_sort = app.sort_combo_var.get() if hasattr(app, 'sort_combo_var') else "Date Newest"
            if current_sort == "Date Newest":
                filtered_images.sort(key=lambda f: f.stat().st_mtime, reverse=True)
            elif current_sort == "Date Oldest":
                filtered_images.sort(key=lambda f: f.stat().st_mtime)
            elif current_sort == "Name A-Z":
                filtered_images.sort(key=lambda f: f.name.lower())
            elif current_sort == "Name Z-A":
                filtered_images.sort(key=lambda f: f.name.lower(), reverse=True)
            elif current_sort == "Size Largest":
                try:
                    filtered_images.sort(key=lambda f: f.stat().st_size, reverse=True)
                except OSError:
                    filtered_images.sort(key=lambda f: f.name.lower())
            elif current_sort == "Size Smallest":
                try:
                    filtered_images.sort(key=lambda f: f.stat().st_size, reverse=False)
                except OSError:
                    filtered_images.sort(key=lambda f: f.name.lower())
            elif current_sort == "Resolution Largest":
                try:
                    def _ratio_img_res(path):
                        try:
                            with Image.open(path) as img:
                                w, h = img.size
                                return w * h
                        except Exception:
                            return 0
                    filtered_images.sort(key=_ratio_img_res, reverse=True)
                except Exception:
                    filtered_images.sort(key=lambda f: f.name.lower())

            # Schedule UI updates on main thread
            def update_ui():
                try:
                    logger.info(f"UI update callback triggered for {len(filtered_images)} images")
                    app._build_ratio_gallery_ui(filtered_images, ratio_mode, tag_filter)
                    logger.info("UI update completed successfully")
                    # Force canvas update to ensure images render
                    app.gallery_canvas.update_idletasks()
                    app.gallery_canvas.update()
                except Exception as e:
                    error_msg = f'Error building ratio UI: {e}'
                    app.status_var.set(error_msg)
                    logger.error(f'Error building ratio UI: {e}')
            
            logger.info("Scheduling UI update on main thread")
            schedule_ui_update(update_ui)

        except Exception as e:
            error_msg = f'Error loading ratio view: {e}'
            schedule_ui_update(app.status_var.set, error_msg)
            logger.error(f'Error loading ratio view: {e}')


    def load_manual(self, tag_filter=None):
        """Load manual images."""
        app = self.app
        try:
            # Collect manual images
            manual_files = [
                f for f in app.MANUAL_DIR.iterdir()
                if f.is_file() and f.suffix.lower() in app.IMAGE_EXTS
            ]

            # Apply sorting
            current_sort = app.sort_combo_var.get() if hasattr(app, 'sort_combo_var') else "Date Newest"
            if current_sort == "Date Newest":
                manual_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
            elif current_sort == "Date Oldest":
                manual_files.sort(key=lambda f: f.stat().st_mtime)
            elif current_sort == "Name A-Z":
                manual_files.sort(key=lambda f: f.name.lower())
            elif current_sort == "Name Z-A":
                manual_files.sort(key=lambda f: f.name.lower(), reverse=True)
            elif current_sort == "Size Largest":
                manual_files.sort(key=lambda f: f.stat().st_size, reverse=True)
            elif current_sort == "Size Smallest":
                manual_files.sort(key=lambda f: f.stat().st_size, reverse=False)
            elif current_sort == "Resolution Largest":
                try:
                    def _manual_res(path):
                        w, h = self._img_dims(path)
                        return w * h
                    manual_files.sort(key=_manual_res, reverse=True)
                except Exception:
                    manual_files.sort(key=lambda f: f.name.lower())
            elif current_sort == "Resolution Smallest":
                try:
                    def _manual_res(path):
                        w, h = self._img_dims(path)
                        return w * h
                    manual_files.sort(key=_manual_res, reverse=False)
                except Exception:
                    manual_files.sort(key=lambda f: f.name.lower())

            app.gallery_manual_images = manual_files

            # Apply tag filter
            if tag_filter:
                if tag_filter == 'Untagged':
                    # Show images with no tags
                    app.gallery_manual_images = [img for img in app.gallery_manual_images if not get_tags_for_image(img)]
                else:
                    # Show images with specific tag
                    app.gallery_manual_images = [img for img in app.gallery_manual_images if tag_filter in get_tags_for_image(img)]

            # Clear existing manual cards
            for widget in app.gallery_manual_inner.winfo_children():
                widget.destroy()
            app.gallery_manual_cards.clear()
            # Any deferred thumbnail loads for the old grid are now stale
            self._bump_grid_load_seq()

            # Build manual cards
            pal = app.THEMES.get(app.current_theme_name, app.THEMES["darkforest"])
            border = pal.get("border_color", pal["panel2"])

            for idx, img_path in enumerate(app.gallery_manual_images):
                app._create_manual_card(img_path, idx, pal, border)

            # Empty-state message
            if not app.gallery_manual_images:
                pal = app.THEMES.get(app.current_theme_name, app.THEMES["darkforest"])
                if tag_filter:
                    msg = f"No manual images tagged '{tag_filter}'."
                else:
                    msg = "No manual images yet. Add images to the Manual folder to see them here."
                app.gallery_manual_inner.columnconfigure(0, weight=1)
                app.gallery_manual_inner.rowconfigure(0, weight=1)
                tk.Label(
                    app.gallery_manual_inner,
                    text=msg,
                    bg=pal["bg"], fg=pal["text"], font=app.small_font,
                    pady=10,
                ).grid(row=0, column=0, sticky="nsew")
                # Fill canvas with themed background
                try:
                    cw = app.gallery_manual_canvas.winfo_width()
                    ch = app.gallery_manual_canvas.winfo_height()
                    if cw > 1 and ch > 1:
                        app.gallery_manual_canvas.itemconfig("manual_inner_frame", width=cw, height=ch)
                except Exception:
                    pass

            app.gallery_manual_canvas.configure(
                scrollregion=app.gallery_manual_canvas.bbox("all") or (0, 0, 1, 1)
            )
            app.status_var.set(f'Manual loaded: {len(app.gallery_manual_images)} images')

        except Exception as e:
            app.status_var.set(f'Manual load failed: {e}')
            app.gallery_manual_images = []


    def load_prompt_from_history(self, image_path):
        """Load prompt data from history for the given image path into sidebar fields."""
        app = self.app
        from history_manager import get_history_manager
        from pathlib import Path
        
        history_mgr = get_history_manager()
        image_path_str = str(Path(image_path).resolve())
        
        # Debug: show what we're looking for
        logger.debug(f"Looking for history for: {image_path_str}")
        
        # Search for matching history entry by image path
        matching_entries = []
        for entry in history_mgr.get_history():
            entry_path = entry.get('image_path', '')
            if entry_path:
                try:
                    entry_resolved = str(Path(entry_path).resolve())
                    # Try exact match first
                    if entry_resolved == image_path_str:
                        logger.debug(f"Found exact match: {entry_resolved}")
                        matching_entries.append(entry)
                        break
                    # Try case-insensitive match for Windows
                    elif entry_resolved.lower() == image_path_str.lower():
                        logger.debug(f"Found case-insensitive match: {entry_resolved}")
                        matching_entries.append(entry)
                        break
                    # Try filename match as fallback
                    elif Path(entry_path).name == Path(image_path).name:
                        logger.debug(f"Found filename match: {entry_path}")
                        matching_entries.append(entry)
                        break
                except Exception as e:
                    logger.debug(f"Error comparing path {entry_path}: {e}")
                    continue
        
        logger.debug(f"Total history entries: {len(history_mgr.get_history())}")
        logger.debug(f"Matching entries found: {len(matching_entries)}")
        
        if not matching_entries:
            app.status_var.set("No prompt history found for this image.")
            return
        
        entry = matching_entries[0]
        
        # Load the prompt data into sidebar fields
        refs = app._get_pb_quick_refs()
        if not refs:
            app.status_var.set("Could not access sidebar fields.")
            return
        
        # Extract components from the history entry
        subject = entry.get('subject', '')
        style = entry.get('style', '')
        lighting = entry.get('lighting', '')
        mood = entry.get('mood', '')
        color = entry.get('color', '')
        setting = entry.get('setting', '')
        atmosphere = entry.get('atmosphere', '')
        
        # Load into Quick Build fields
        if "subject_entry" in refs and subject:
            refs["subject_entry"].delete(0, tk.END)
            refs["subject_entry"].insert(0, subject)
        
        if "style_entry" in refs and style:
            refs["style_entry"].delete(0, tk.END)
            refs["style_entry"].insert(0, style)
        
        if "lighting_entry" in refs and lighting:
            refs["lighting_entry"].delete(0, tk.END)
            refs["lighting_entry"].insert(0, lighting)
        
        if "mood_entry" in refs and mood:
            refs["mood_entry"].delete(0, tk.END)
            refs["mood_entry"].insert(0, mood)
        
        if "color_family_var" in refs and color:
            refs["color_family_var"].set(color)
        
        # Load the full prompt into the prompt preview
        full_prompt = entry.get('prompt', '')
        if full_prompt and hasattr(app, 'prompt_text'):
            app.prompt_text.delete(1.0, tk.END)
            app.prompt_text.insert(1.0, full_prompt)
        
        app.status_var.set(f"Loaded prompt from history: {subject}")


    def load_styled(self, tag_filter=None):
        """Load styled images."""
        app = self.app
        try:
            # Collect styled images
            styled_files = [
                f for f in app.STYLED_DIR.iterdir()
                if f.is_file() and f.suffix.lower() in app.IMAGE_EXTS
            ]

            # Apply sorting
            current_sort = app.sort_combo_var.get() if hasattr(app, 'sort_combo_var') else "Date Newest"
            if current_sort == "Date Newest":
                styled_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
            elif current_sort == "Date Oldest":
                styled_files.sort(key=lambda f: f.stat().st_mtime)
            elif current_sort == "Name A-Z":
                styled_files.sort(key=lambda f: f.name.lower())
            elif current_sort == "Name Z-A":
                styled_files.sort(key=lambda f: f.name.lower(), reverse=True)
            elif current_sort == "Size Largest":
                styled_files.sort(key=lambda f: f.stat().st_size, reverse=True)
            elif current_sort == "Size Smallest":
                styled_files.sort(key=lambda f: f.stat().st_size, reverse=False)
            elif current_sort == "Resolution Largest":
                try:
                    def _styled_res(path):
                        w, h = self._img_dims(path)
                        return w * h
                    styled_files.sort(key=_styled_res, reverse=True)
                except Exception:
                    styled_files.sort(key=lambda f: f.name.lower())
            elif current_sort == "Resolution Smallest":
                try:
                    def _styled_res(path):
                        w, h = self._img_dims(path)
                        return w * h
                    styled_files.sort(key=_styled_res, reverse=False)
                except Exception:
                    styled_files.sort(key=lambda f: f.name.lower())

            app.gallery_styled_images = styled_files

            # Apply tag filter
            if tag_filter:
                if tag_filter == 'Untagged':
                    # Show images with no tags
                    app.gallery_styled_images = [img for img in app.gallery_styled_images if not get_tags_for_image(img)]
                else:
                    # Show images with specific tag
                    app.gallery_styled_images = [img for img in app.gallery_styled_images if tag_filter in get_tags_for_image(img)]

            # Clear existing styled cards
            for widget in app.gallery_styled_inner.winfo_children():
                widget.destroy()
            app.gallery_styled_cards.clear()
            # Any deferred thumbnail loads for the old grid are now stale
            self._bump_grid_load_seq()

            # Build styled cards
            pal = app.THEMES.get(app.current_theme_name, app.THEMES["darkforest"])
            border = pal.get("border_color", pal["panel2"])

            for idx, img_path in enumerate(app.gallery_styled_images):
                app._create_styled_card(img_path, idx, pal, border)

            # Empty-state message
            if not app.gallery_styled_images:
                pal = app.THEMES.get(app.current_theme_name, app.THEMES["darkforest"])
                if tag_filter:
                    msg = f"No styled images tagged '{tag_filter}'."
                else:
                    msg = "No styled images yet. Apply a style filter to any image to create one."
                app.gallery_styled_inner.columnconfigure(0, weight=1)
                app.gallery_styled_inner.rowconfigure(0, weight=1)
                tk.Label(
                    app.gallery_styled_inner,
                    text=msg,
                    bg=pal["bg"], fg=pal["text"], font=app.small_font,
                    pady=10,
                ).grid(row=0, column=0, sticky="nsew")
                # Fill canvas with themed background
                try:
                    cw = app.gallery_styled_canvas.winfo_width()
                    ch = app.gallery_styled_canvas.winfo_height()
                    if cw > 1 and ch > 1:
                        app.gallery_styled_canvas.itemconfig("styled_inner_frame", width=cw, height=ch)
                except Exception:
                    pass

            app.gallery_styled_canvas.configure(
                scrollregion=app.gallery_styled_canvas.bbox("all") or (0, 0, 1, 1)
            )
            app.status_var.set(f'Styled loaded: {len(app.gallery_styled_images)} images')

        except Exception as e:
            app.status_var.set(f'Styled load failed: {e}')
            app.gallery_styled_images = []


    def on_card_click(self, event, path, index):
        """Handle card click - delegate to _on_thumbnail_click with Ctrl check."""
        app = self.app
        # Check if the click was on a heart button
        if event.widget and isinstance(event.widget, tk.Button):
            # Let the heart button handler deal with it
            return
        ctrl_pressed = (event.state & 0x4) != 0  # Check if Ctrl key is pressed
        app._on_thumbnail_click(path, ctrl_pressed)


    def on_card_drag(self, event, index):
        app = self.app
        pass


    def on_card_drop(self, event, source_index):
        app = self.app
        pass


    def on_fav_resize(self, event):

        """Handle favorites canvas resize — match gallery 3-column behaviour.

        Debounced (80 ms) exactly like on_gallery_resize: the raw event
        fires for every pixel of a drag-resize, and each pass re-grids
        every card plus reconfigures the scrollregion.
        """

        app = self.app
        canvas_width = event.width

        if getattr(app, "_fav_resize_job", None) is not None:
            app.gallery_fav_canvas.after_cancel(app._fav_resize_job)

        def _do_resize():
            app._fav_resize_job = None
            cols = min(3, max(1, canvas_width // 260))
            app._rebuild_fav_grid(cols)
            app.gallery_fav_canvas.configure(scrollregion=app.gallery_fav_canvas.bbox('all') or (0, 0, 1, 1))
            app.gallery_fav_canvas.itemconfig("fav_inner_frame", width=canvas_width)

        app._fav_resize_job = app.gallery_fav_canvas.after(80, _do_resize)


    def on_gallery_resize(self, event):

        """Handle window resize to adjust column count — debounced."""

        app = self.app
        canvas_width = event.width

        if app._gallery_resize_job is not None:
            app.gallery_canvas.after_cancel(app._gallery_resize_job)

        def _do_resize():
            app._gallery_resize_job = None
            cols = min(3, max(1, canvas_width // 250))
            app._gallery_cols = cols
            app.refresh_grid_layout(cols)
            app.gallery_canvas.itemconfig("inner_frame", width=canvas_width)
            app._render_visible_cards()

        app._gallery_resize_job = app.gallery_canvas.after(80, _do_resize)


    def on_manual_resize(self, event):

        """Handle manual canvas resize — match gallery 3-column behaviour.

        Debounced (80 ms) exactly like on_gallery_resize.
        """

        app = self.app
        canvas_width = event.width

        if getattr(app, "_manual_resize_job", None) is not None:
            app.gallery_manual_canvas.after_cancel(app._manual_resize_job)

        def _do_resize():
            app._manual_resize_job = None
            cols = min(3, max(1, canvas_width // 260))
            app._rebuild_manual_grid(cols)
            app.gallery_manual_canvas.configure(scrollregion=app.gallery_manual_canvas.bbox('all') or (0, 0, 1, 1))
            app.gallery_manual_canvas.itemconfig("manual_inner_frame", width=canvas_width)

        app._manual_resize_job = app.gallery_manual_canvas.after(80, _do_resize)


    def on_organize_toggle(self):
        app = self.app
        pass  # Organize Mode removed


    def on_styled_resize(self, event):

        """Handle styled canvas resize — match gallery 3-column behaviour.

        Debounced (80 ms) exactly like on_gallery_resize.
        """

        app = self.app
        canvas_width = event.width

        if getattr(app, "_styled_resize_job", None) is not None:
            app.gallery_styled_canvas.after_cancel(app._styled_resize_job)

        def _do_resize():
            app._styled_resize_job = None
            cols = min(3, max(1, canvas_width // 260))
            app._rebuild_styled_grid(cols)
            app.gallery_styled_canvas.configure(scrollregion=app.gallery_styled_canvas.bbox('all') or (0, 0, 1, 1))
            app.gallery_styled_canvas.itemconfig("styled_inner_frame", width=canvas_width)

        app._styled_resize_job = app.gallery_styled_canvas.after(80, _do_resize)


    def open_style_dialog(self):

        """Open the style transfer dialog for the selected image."""

        app = self.app
        if not app.selected_gallery_path:

            app._dialog.warning("No Selection", "Please select an image from the gallery first.")

            return

        

        if not app._ensure_style_transfer():

            app._dialog.error("Style Transfer Not Available", "Style transfer requires OpenCV, which is not included in this build. This feature may be added in a future update.")

            return

        

        # Create style dialog

        style_dialog = tk.Toplevel(app.root)
        style_dialog.title("Apply Artistic Style")
        style_dialog.geometry("560x960")
        style_dialog.minsize(520, 820)
        style_dialog.transient(app.root)
        style_dialog.grab_set()

        from utils import center_window
        center_window(app.root, style_dialog)

        

        # Style selection (packed first → stays at top)

        style_frame = ttk.LabelFrame(style_dialog, text="Apply Artistic Style:", padding=10)

        style_frame.pack(fill="x", padx=10, pady=10)

        

        app.selected_style_var = tk.StringVar(value="original")

        

        # Create radio buttons for styles

        styles = [

            ("original", "Original (no filter)"),

            ("oil_painting", "Oil Painting (thick brushstrokes, blended colors)"),

            ("watercolor", "Watercolor (soft edges, color blooms)"),

            ("sketch", "Sketch (line art, pen-like strokes)"),

            ("line_art", "Line Art (high contrast, minimal color)"),

            ("comic_book", "Comic Book (bold lines, limited palette)"),

            ("manga", "Manga (clean lines, high contrast)"),

            ("sepia", "Sepia (warm brown tones, vintage)"),

            ("bw", "B&W (grayscale, no color)"),

            ("vintage", "Vintage (aged, faded look)"),

            ("posterize", "Posterize (reduced color palette)"),

            ("emboss", "Emboss (3D relief effect)"),

            ("edge_enhance", "Edge Enhance (sharpened edges)"),

            ("cyberpunk_neon", "Cyberpunk Neon (neon glow, dark shadows)"),

            ("vaporwave", "Vaporwave (retro synth, purple/pink palette)"),

            ("pixel_art", "Pixel Art (retro 8-bit style)"),

            ("sketch_pencil", "Sketch Pencil (charcoal-like texture)"),

            ("gouache", "Gouache (opaque watercolor, matte finish)"),

            ("art_deco", "Art Deco (geometric patterns, gold accents)"),

            ("surreal_dali", "Surreal Dali (dreamlike, melting forms)"),

            ("3d_render", "3D Render (digital 3D style, glossy)"),

            ("anime_key", "Anime Key (cel shading, vibrant colors)"),

            ("noir_bw", "Noir B&W (high contrast, dramatic shadows)"),

            ("vintage_sepia", "Vintage Sepia (aged photo, warm tones)"),

            ("pop_art", "Pop Art (bold colors, comic style)"),

            ("impressionist", "Impressionist (soft brushstrokes, light effects)"),

        ]

        

        for i, (style_value, style_name) in enumerate(styles):

            row = i // 2

            col = (i % 2) * 2

            ttk.Radiobutton(style_frame, text=style_name, variable=app.selected_style_var, value=style_value).grid(row=row, column=col, sticky="w", padx=5, pady=2)

        

        # Buttons at bottom (packed before preview so preview fills space between top and bottom)

        button_frame = ttk.Frame(style_dialog)

        button_frame.pack(side="bottom", fill="x", padx=10, pady=(4, 12))

        ttk.Button(button_frame, text="Apply Style", command=lambda: app.apply_selected_style(style_dialog)).pack(side="right", padx=5)

        ttk.Button(button_frame, text="Cancel", command=style_dialog.destroy).pack(side="right", padx=5)



        # Preview fills remaining height between style list and buttons

        preview_frame = ttk.LabelFrame(style_dialog, text="Preview:", padding=10)

        preview_frame.pack(fill="both", expand=True, padx=10, pady=10)

        

        try:

            from PIL import Image, ImageTk

            img = Image.open(app.selected_gallery_path)

            img.thumbnail((480, 220))

            photo = ImageTk.PhotoImage(img)

            app.preview_label = tk.Label(preview_frame, image=photo)

            app.preview_label.image = photo

            app.preview_label.pack()

            ttk.Label(preview_frame, text="Original image selected", font=app.small_font).pack(pady=5)

        except Exception as e:

            ttk.Label(preview_frame, text=f"Could not load preview: {e}").pack()


    def organize_gallery_image(self):

        """Move to subfolder."""

        app = self.app
        if not app.selected_gallery_path:

            return

        folder = simpledialog.askstring('Folder', 'Subfolder name (e.g. "cyberpunk"):', initialvalue='')

        if folder:

            try:
                new_path = organize_image_into_folder(str(app.selected_gallery_path), folder)
            except Exception as e:
                logger.error(f"Failed to organize image {app.selected_gallery_path}: {e}")
                app._dialog.error(
                    'Move Failed',
                    'The image could not be moved into the subfolder. The file '
                    'may be locked by another program, or the folder name may '
                    'be invalid.\n\n'
                    'Close any program using the file and try again.')
                return

            if new_path:

                app.selected_gallery_path = Path(new_path)

                app.load_gallery()  # Refresh gallery

                app.status_var.set(f'📁 Moved to /{folder}/')

            else:

                app.status_var.set('❌ Organize failed.')


    def random_theme(self):
        """Randomize all quick-build variables including setting and atmosphere."""
        app = self.app
        subjects = [option for option in app.THEME_VARIABLE_OPTIONS["subject"] if option]
        settings = [option for option in app.THEME_VARIABLE_OPTIONS["setting"] if option]
        styles = [option for option in app.THEME_VARIABLE_OPTIONS["style"] if option]
        lightings = [option for option in app.THEME_VARIABLE_OPTIONS["lighting"] if option]
        moods = [option for option in app.THEME_VARIABLE_OPTIONS["mood"] if option]
        atmospheres = [option for option in app.THEME_VARIABLE_OPTIONS["atmosphere"] if option]

        # Color options — sourced from module-level constants (exclude blank family so random always picks a color)
        color_families = [f for f in app.COLOR_FAMILIES if f]
        color_variations = app.COLOR_VARIATIONS
        # Build color string like "rich gold" or just "gold"
        family = random.choice(color_families)
        variation = random.choice(color_variations)
        color_value = f"{variation} {family}".strip() if variation else family

        app.set_active_subject(random.choice(subjects))
        app.set_active_setting(random.choice(settings))
        app.set_active_style(random.choice(styles))
        app.set_active_lighting(random.choice(lightings))
        app.set_active_mood(random.choice(moods))
        app.set_active_color(color_value)
        app.set_active_atmosphere(random.choice(atmospheres))
        random_mode = random.choice(app.STYLE_MODES)
        app.set_active_mode(random_mode)
        # Also update the sidebar mode combobox so generate() reads the correct value
        if hasattr(app, 'mode_var'):
            try:
                mode_label = app._mode_label(random_mode)
                app.mode_var.set(mode_label)
            except Exception:
                pass
        app.update_mode_badge()
        # Don't auto-generate - just set random values
        app.status_var.set("Random prompt set - click Generate Image to create image")


    def refresh_grid_layout(self, cols):

        """Re-grid all gallery cards and placeholders based on new column count."""

        app = self.app
        app._gallery_cols = cols

        # Make each column expand equally to fill the canvas width
        for c in range(cols):
            app.gallery_inner.columnconfigure(c, weight=1)

        # Re-grid real cards by their true index in gallery_images
        # Skip any widget that has been destroyed (TclError guard)
        path_to_idx = {str(p): i for i, p in enumerate(app.gallery_images)}
        dead_cards = []
        for key, card_data in app.gallery_cards.items():
            # Handle variable-length card data (some have 2, 3, or 6 elements)
            card = card_data[0] if isinstance(card_data, (tuple, list)) else card_data
            try:
                if not card.winfo_exists():
                    dead_cards.append(key)
                    continue
                idx = path_to_idx.get(key)
                if idx is not None:
                    card.grid(row=idx // cols, column=idx % cols, padx=6, pady=6, sticky='nsew')
            except tk.TclError:
                dead_cards.append(key)

        # Clean up dead card references
        for key in dead_cards:
            app.gallery_cards.pop(key, None)

        # Re-grid placeholders by their stored index
        dead_placeholders = []
        for idx, ph in app._gallery_placeholders.items():
            try:
                if not ph.winfo_exists():
                    dead_placeholders.append(idx)
                    continue
                ph.grid(row=idx // cols, column=idx % cols, padx=6, pady=6, sticky='nsew')
            except tk.TclError:
                dead_placeholders.append(idx)

        # Clean up dead placeholder references
        for idx in dead_placeholders:
            app._gallery_placeholders.pop(idx, None)


    def _is_image_favorited(self, img_path):
        """Check if an image is already in favorites.

        Matches against the favorites log by either:
          1. Exact resolved-path match on copied_image_path OR original_image_path, OR
          2. Basename match against any image file currently present in the
             favorites folder (handles entries missing original_image_path,
             e.g. favorites created by older app versions or migrated from the
             legacy top-level favorites/ folder).
        """
        app = self.app
        try:
            existing = load_json_list(app.FAVORITES_LOG)
            original_resolved = Path(img_path).resolve()
            # 1. Exact resolved-path match against JSON entries
            for item in existing:
                cp = item.get('copied_image_path')
                op = item.get('original_image_path')
                if cp and Path(cp).exists() and Path(cp).resolve() == original_resolved:
                    return True
                if op and Path(op).exists() and Path(op).resolve() == original_resolved:
                    return True
            # 2. Basename fallback: look for a file with the same name in the
            #    favorites folder. This catches favorites whose JSON entry is
            #    missing original_image_path (old/migrated favorites).
            try:
                target_name = Path(img_path).name.lower()
                if target_name and app.FAVORITES_DIR.exists():
                    for f in app.FAVORITES_DIR.iterdir():
                        if not f.is_file():
                            continue
                        if f.suffix.lower() not in app.IMAGE_EXTS:
                            continue
                        if f.name.lower() == target_name:
                            return True
            except Exception:
                pass
            return False
        except Exception:
            return False

    def _backfill_original_image_paths(self):
        """One-shot repair pass: for each favorites.json entry that is missing
        original_image_path, try to find a source image (in generated/manual/
        styled folders) with the same basename and backfill it.

        Idempotent — only writes when at least one entry is repaired. Safe to
        call at startup or whenever the favorites view is loaded.
        """
        app = self.app
        try:
            existing = load_json_list(app.FAVORITES_LOG)
            if not existing:
                return 0
            search_dirs = []
            from set_wallpaper import MANUAL_DIR, GENERATED_DIR
            search_dirs.append(MANUAL_DIR)
            search_dirs.append(GENERATED_DIR)
            if hasattr(app, 'STYLED_DIR'):
                search_dirs.append(app.STYLED_DIR)
            # Build a basename -> resolved path index for fast lookup
            index = {}
            for d in search_dirs:
                try:
                    if not d.exists():
                        continue
                    for f in d.iterdir():
                        if not f.is_file():
                            continue
                        if f.suffix.lower() not in app.IMAGE_EXTS:
                            continue
                        index.setdefault(f.name.lower(), f.resolve())
                except Exception:
                    continue
            changed = 0
            for item in existing:
                op = item.get('original_image_path')
                if op and Path(op).exists():
                    continue
                # Pick the basename from whichever path field is available
                guess_name = None
                for key in ('image_path', 'copied_image_path', 'original_image_path'):
                    v = item.get(key)
                    if v:
                        guess_name = Path(v).name
                        break
                if not guess_name:
                    continue
                match = index.get(guess_name.lower())
                if match:
                    item['original_image_path'] = str(match)
                    changed += 1
            if changed:
                save_json_list(app.FAVORITES_LOG, existing)
                logger.info(f"Backfilled original_image_path on {changed} favorites entries")
            return changed
        except Exception as e:
            logger.warning(f"_backfill_original_image_paths failed: {e}")
            return 0

    def _purge_stale_favorites_log(self):
        """Remove FAVORITES_LOG entries whose copied_image_path no longer exists on disk.

        This keeps the JSON in sync when the user manually deletes image files
        from the favorites folder outside the app.
        """
        app = self.app
        try:
            existing = load_json_list(app.FAVORITES_LOG)
            if not existing:
                return
            before = len(existing)
            cleaned = []
            for item in existing:
                cp = item.get('copied_image_path') or item.get('image_path')
                if cp and Path(cp).exists():
                    cleaned.append(item)
            if len(cleaned) < before:
                save_json_list(app.FAVORITES_LOG, cleaned)
                logger.info(f"Purged {before - len(cleaned)} stale entries from favorites.json")
        except Exception as e:
            logger.warning(f"_purge_stale_favorites_log failed: {e}")

    def _toggle_image_favorite(self, img_path):
        """Toggle an image's favorite status (add or remove)."""
        app = self.app
        try:
            existing = load_json_list(app.FAVORITES_LOG)
            original_resolved = Path(img_path).resolve()
            
            # Check if already favorited (check both copied and original paths)
            # Skip entries where the file no longer exists on disk
            favorited_index = None
            for i, item in enumerate(existing):
                cp = item.get('copied_image_path')
                op = item.get('original_image_path')
                if cp and Path(cp).exists() and Path(cp).resolve() == original_resolved:
                    favorited_index = i
                    break
                if op and Path(op).exists() and Path(op).resolve() == original_resolved:
                    favorited_index = i
                    break
            
            if favorited_index is not None:
                # Remove from favorites
                entry = existing.pop(favorited_index)
                save_json_list(app.FAVORITES_LOG, existing)
                
                # Optionally delete the copied file
                try:
                    copied_path = entry.get('copied_image_path')
                    if copied_path and Path(copied_path).exists():
                        # Only delete if it's in the favorites folder
                        if app.FAVORITES_DIR in Path(copied_path).parents:
                            Path(copied_path).unlink()
                except Exception:
                    pass  # Ignore deletion errors
                
                app.load_favorites()
                app.status_var.set(f'💔 Removed from favorites: {Path(img_path).name}')
                return False
            else:
                # Add to favorites
                path_str = str(img_path)
                final_image_path = None
                needs_copy = True
                
                # Check if the selected image is already inside wallpapers/favorites/
                if app.FAVORITES_DIR in Path(img_path).parents:
                    final_image_path = Path(img_path)
                    needs_copy = False
                else:
                    # Need to copy to favorites folder
                    dest_filename = Path(img_path).name
                    dest_path = app.FAVORITES_DIR / dest_filename
                    
                    # Handle filename collisions
                    counter = 2
                    while dest_path.exists():
                        if dest_path.resolve() == original_resolved:
                            final_image_path = dest_path
                            needs_copy = False
                            break
                        
                        stem = Path(img_path).stem
                        suffix = Path(img_path).suffix
                        dest_filename = f"{stem}_fav{counter}{suffix}"
                        dest_path = app.FAVORITES_DIR / dest_filename
                        counter += 1
                    
                    if needs_copy:
                        final_image_path = dest_path
                        try:
                            import shutil
                            shutil.copy2(img_path, dest_path)
                        except Exception as e:
                            app._dialog.error('Favorites Error', 'Could not copy image to favorites. Check that the folder exists and is accessible.')
                            return False
                
                # Create metadata entry
                entry = {
                    'saved_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'original_image_path': path_str,
                    'image_path': str(final_image_path),
                    'copied_image_path': str(final_image_path) if needs_copy else None,
                    'theme_sentence': f'Gallery favorite: {Path(img_path).name}'
                }
                
                existing.append(entry)
                save_json_list(app.FAVORITES_LOG, existing)
                app.load_favorites()
                app.status_var.set(f'❤️ Added to favorites: {Path(img_path).name}')
                return True
                
        except Exception as e:
            app.status_var.set(f'Error toggling favorite: {e}')
            return False

    def save_gallery_to_favorites(self):

        """Add selected to favorites by copying to wallpapers/favorites/ folder."""

        app = self.app
        if not app.selected_gallery_path:

            app._dialog.warning('No Selection', 'Select an image first.')

            return

        existing = load_json_list(app.FAVORITES_LOG)

        path_str = str(app.selected_gallery_path)
        original_resolved = app.selected_gallery_path.resolve()
        
        # Check if already favorited by comparing resolved paths.
        # NOTE: must check BOTH copied_image_path (favorites-folder path) AND
        # original_image_path (source gallery path) against the gallery image,
        # otherwise the duplicate check never matches and the user can add
        # the same image over and over.
        if any(
            (item.get('copied_image_path') and Path(item.get('copied_image_path')).resolve() == original_resolved)
            or (item.get('original_image_path') and Path(item.get('original_image_path')).resolve() == original_resolved)
            for item in existing
        ):

            app.status_var.set(f'Image already in favorites.')

            return

        # Basename fallback: if a file with the same name already exists in
        # the favorites folder, treat it as already favorited. This catches
        # favorites created by older app versions or migrated from the
        # legacy top-level favorites/ folder that don't have a matching
        # original_image_path.
        try:
            target_name = app.selected_gallery_path.name.lower()
            if target_name and app.FAVORITES_DIR.exists():
                for f in app.FAVORITES_DIR.iterdir():
                    if (f.is_file()
                            and f.suffix.lower() in app.IMAGE_EXTS
                            and f.name.lower() == target_name):
                        app.status_var.set(f'Image already in favorites.')
                        return
        except Exception:
            pass

        # Determine the final image path for the favorite
        final_image_path = None
        needs_copy = True
        
        # Check if the selected image is already inside wallpapers/favorites/
        if app.FAVORITES_DIR in app.selected_gallery_path.parents:
            # Image is already in favorites folder, use it directly
            final_image_path = app.selected_gallery_path
            needs_copy = False
        else:
            # Need to copy to favorites folder
            dest_filename = app.selected_gallery_path.name
            dest_path = app.FAVORITES_DIR / dest_filename
            
            # Handle filename collisions with fav2, fav3, etc. suffix
            counter = 2
            while dest_path.exists():
                # Check if it's the same file (same resolved path)
                if dest_path.resolve() == original_resolved:
                    # Same file, reuse it
                    final_image_path = dest_path
                    needs_copy = False
                    break
                
                # Different file, create unique name
                stem = app.selected_gallery_path.stem
                suffix = app.selected_gallery_path.suffix
                dest_filename = f"{stem}_fav{counter}{suffix}"
                dest_path = app.FAVORITES_DIR / dest_filename
                counter += 1
            
            if needs_copy:
                final_image_path = dest_path
                try:
                    import shutil
                    shutil.copy2(app.selected_gallery_path, dest_path)
                except Exception as e:
                    app._dialog.error('Favorites Error', 'Could not copy image to favorites. Check that the folder exists and is accessible.')
                    return

        # Create metadata entry with both paths
        entry = {
            'saved_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'original_image_path': path_str,
            'image_path': str(final_image_path),  # Final favorite copy path
            'copied_image_path': str(final_image_path) if needs_copy else None,
            'theme_sentence': f'Gallery favorite: {app.selected_gallery_path.name}'
        }

        existing.append(entry)
        save_json_list(app.FAVORITES_LOG, existing)

        app.load_favorites()
        app.status_var.set(f'★ Saved to favorites: {app.selected_gallery_path.name}')


    def set_gallery_image_as_wallpaper(self, path):

        """Set gallery image as wallpaper on double-click."""

        app = self.app
        if not app.WINDOWS:

            app._dialog.info('Windows only', 'Wallpaper setting is Windows-only.')

            return

        try:

            ok = set_wallpaper(Path(path))

            if ok:

                app.status_var.set(f'✅ Wallpaper set: {Path(path).name}')
                app.slideshow.reset_timer()

            else:

                app.status_var.set(f'❌ Set failed: {Path(path).name}')

        except Exception as e:

            app.status_var.set(f'❌ Error: {e}')

            app._dialog.error("Wallpaper Error", "Could not set this image as wallpaper. Try selecting it from the Gallery and using the wallpaper button.")


    def set_gallery_selection(self):

        """Set selected as wallpaper."""

        app = self.app
        if not app.selected_gallery_path or not app.WINDOWS:

            app._dialog.info('Windows only', 'Wallpaper setting is Windows-only.')

            return

        try:

            ok = set_wallpaper(app.selected_gallery_path)

            app.status_var.set(f'✅ Wallpaper set: {app.selected_gallery_path.name}' if ok else '❌ Set failed.')
            if ok:
                app.slideshow.reset_timer()

        except Exception as e:

            app.status_var.set(f'❌ Error: {e}')


    def set_selected_favorite_as_wallpaper(self):
        """Set the selected favorite image as wallpaper directly."""
        app = self.app
        if not app.WINDOWS:
            app._dialog.info("Windows only", "Setting wallpaper is only supported on Windows.")
            return

        if not app.favorite_selected_item:
            app._dialog.info("No selection", "Click a Favorite thumbnail first.")
            return

        data = app.favorite_selected_item
        # Use copied_image_path as primary, fall back to image_path for legacy entries
        image_path = data.get("copied_image_path") or data.get("image_path")

        if not image_path:
            app._dialog.info("No image", "This favorite has no associated image path.")
            return

        try:
            ok = set_wallpaper(Path(image_path))
            if ok:
                app.status_var.set(f"✅ Wallpaper set: {Path(image_path).name}")
            else:
                app.status_var.set(f"❌ Set failed: {Path(image_path).name}")
        except Exception as e:
            app.status_var.set(f"❌ Error: {e}")
            app._dialog.error("Wallpaper Error", "Could not set wallpaper. Try right-clicking the image instead.")


    def show_gallery_context_menu(self, event, path):
        """Show right-click context menu for gallery images."""
        app = self.app
        context_menu = tk.Menu(app.root, tearoff=0)
        context_menu.add_command(label="Tag Image", command=lambda: (setattr(app, 'selected_gallery_path', Path(path)), app._gallery_tag_selected()))
        context_menu.add_command(label="Load Prompt to Sidebar", command=lambda: app.load_prompt_from_history(path))
        context_menu.add_command(label="Set as Wallpaper", command=lambda: app.set_gallery_image_as_wallpaper(path))
        context_menu.add_separator()
        context_menu.add_command(label="Copy Path", command=lambda: app.copy_to_clipboard(str(path)))
        
        # Show existing tags for this image
        existing = get_tags_for_image(path)
        if existing:
            context_menu.add_separator()
            tags_label = f"Tags: {', '.join(existing)}"
            context_menu.add_command(label=tags_label, state='disabled')
            # Add option to remove all tags
            context_menu.add_command(label="Remove All Tags", 
                                     command=lambda: self._remove_all_tags(path))

        try:
            context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            context_menu.grab_release()


    def _remove_all_tags(self, path):
        """Remove all tags from a specific image."""
        app = self.app
        try:
            from gallery_manager import get_tags_for_image, remove_tag_from_image
            existing_tags = get_tags_for_image(path)
            if not existing_tags:
                app._dialog.info("No Tags", "This image has no tags to remove.")
                return
            
            if not app._dialog.ask('Remove All Tags', f'Remove all tags from this image?\n\nTags: {", ".join(existing_tags)}'):
                return
            
            # Remove each tag
            for tag in existing_tags:
                remove_tag_from_image(path, tag)
            
            app._refresh_gallery_tag_filter()
            app.status_var.set(f'Removed all tags from image.')
        except Exception as e:
            app.status_var.set(f'Error removing tags: {e}')
            app._dialog.error("Tag Error", "Could not remove the tag. Try again or restart the app.")

    def sort_gallery(self, event=None):
        """Handle sort dropdown selection - deferred to avoid app.UI freeze."""
        app = self.app
        # Cancel any pending sort refresh job to avoid queuing multiple reloads
        if hasattr(app, '_sort_refresh_job') and app._sort_refresh_job:
            app.root.after_cancel(app._sort_refresh_job)
        # Schedule a new refresh after the combobox event cycle finishes
        app._sort_refresh_job = app.root.after(50, app._do_sort_gallery_reload)
        # Shift focus to gallery canvas so mouse wheel scrolling works immediately
        # without requiring an extra click after dropdown closes
        try:
            app.gallery_canvas.focus_set()
        except Exception:
            pass


    def _show_tag_dialog(self, title):
        """Show a custom tag dialog with existing tags as selectable options.
        
        Allows users to select from existing tags or manually enter new tags.
        Returns a list of selected/entered tags, or None if cancelled.
        """
        app = self.app
        from gallery_manager import get_all_tags
        
        # Create dialog window
        dialog = tk.Toplevel(app.root)
        dialog.title(title)
        dialog.geometry("500x400")
        dialog.transient(app.root)
        dialog.grab_set()

        from utils import center_window
        center_window(app.root, dialog)
        
        # Get existing tags
        existing_tags = get_all_tags()
        
        # Result storage
        result = []
        cancelled = True
        
        # Create UI
        main_frame = ttk.Frame(dialog, padding=15)
        main_frame.pack(fill="both", expand=True)
        
        # Instructions
        ttk.Label(main_frame, text="Select existing tags or type new tags (comma-separated):",
                 wraplength=450).pack(anchor="w", pady=(0, 10))
        
        # Existing tags listbox with scrollbar
        list_frame = ttk.Frame(main_frame)
        list_frame.pack(fill="both", expand=True, pady=(0, 10))
        
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side="right", fill="y")
        
        tag_listbox = tk.Listbox(list_frame, selectmode="multiple", 
                                 yscrollcommand=scrollbar.set,
                                 height=8, exportselection=False)
        tag_listbox.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=tag_listbox.yview)
        
        # Populate with existing tags
        for tag in existing_tags:
            tag_listbox.insert(tk.END, tag)
        
        # Manual entry field
        ttk.Label(main_frame, text="Or enter new tags:").pack(anchor="w")
        manual_entry = ttk.Entry(main_frame)
        manual_entry.pack(fill="x", pady=(5, 10))
        manual_entry.focus_set()
        
        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill="x")
        
        def on_ok():
            nonlocal result, cancelled
            cancelled = False
            
            # Get selected tags from listbox
            selected_indices = tag_listbox.curselection()
            for idx in selected_indices:
                result.append(tag_listbox.get(idx))
            
            # Get manually entered tags
            manual_text = manual_entry.get().strip()
            if manual_text:
                manual_tags = [t.strip() for t in manual_text.split(',') if t.strip()]
                result.extend(manual_tags)
            
            dialog.destroy()
        
        def on_cancel():
            dialog.destroy()
        
        ttk.Button(button_frame, text="OK", command=on_ok, width=15).pack(side="right", padx=(5, 0))
        ttk.Button(button_frame, text="Cancel", command=on_cancel, width=15).pack(side="right")
        
        # Handle Enter key in entry field
        manual_entry.bind("<Return>", lambda e: on_ok())
        
        # Wait for dialog to close
        app.root.wait_window(dialog)
        
        if cancelled:
            return None
        return result if result else None

    def tag_gallery_image(self):
        """Add tags to selected image(s) with batch tagging support.
        
        Shows existing tags as selectable options while allowing manual entry of new tags.
        Prevents duplicate tags on the same image and refreshes gallery tag filters after save.
        """
        app = self.app
        # Validate selection - use multi-select set if available, otherwise fall back to single
        target_paths = []
        if app.selected_gallery_paths:
            target_paths = [p for p in app.selected_gallery_paths if Path(p).exists()]
        elif app.selected_gallery_path and Path(app.selected_gallery_path).exists():
            target_paths = [str(app.selected_gallery_path)]
        
        if not target_paths:
            app._dialog.warning('No Selection', 'Select at least one image first.')
            return
        
        # Filter out non-existent paths
        existing_paths = [p for p in target_paths if Path(p).exists()]
        if not existing_paths:
            app._dialog.error('Image Not Found', 'The selected image(s) have been moved or deleted. Refresh the gallery to see current images.')
            app.selected_gallery_path = None
            app.selected_gallery_paths.clear()
            app._refresh_tag_ui(status_msg='Selection cleared - file(s) not found')
            return
        
        # Show custom tag dialog with existing tags as selectable options
        count_str = f'{len(existing_paths)} image(s)' if len(existing_paths) > 1 else 'image'
        tags = self._show_tag_dialog(f'Tag {count_str}')
        if not tags:
            return  # User cancelled or empty input
        
        # Deduplicate tags case-insensitively (preserve first occurrence's case)
        seen_lower = set()
        unique_tags = []
        for tag in tags:
            lower = tag.lower()
            if lower not in seen_lower:
                seen_lower.add(lower)
                unique_tags.append(tag)
        
        # Apply tags to all selected images
        total_new_tags = 0
        total_skipped = 0
        failed_paths = []
        
        for path_str in existing_paths:
            try:
                existing_tags = get_tags_for_image(path_str) or []
                existing_lower = {t.lower() for t in existing_tags}
                new_tags = [t for t in unique_tags if t.lower() not in existing_lower]

                if new_tags:
                    app._propagate_tags_to_related(path_str, new_tags)
                    total_new_tags += len(new_tags)
                total_skipped += len(unique_tags) - len(new_tags)
            except Exception as e:
                failed_paths.append((path_str, str(e)))
        
        # Build status message
        if len(existing_paths) == 1:
            if total_new_tags > 0:
                status_msg = f'🏷️ Tagged: {", ".join(unique_tags)}'
                if total_skipped > 0:
                    status_msg += f' ({total_skipped} duplicate skipped)'
            else:
                status_msg = 'All tags already exist on this image.'
        else:
            status_msg = f'🏷️ Tagged {len(existing_paths)} images with {total_new_tags} new tags'
            if total_skipped > 0:
                status_msg += f' ({total_skipped} duplicates skipped)'
            if failed_paths:
                status_msg += f' ({len(failed_paths)} failed)'
        
        app._refresh_tag_ui(status_msg=status_msg, keep_selection=True)
        
        # Refresh gallery tag filters to show new tags
        app._refresh_gallery_tag_filter()
        
        if failed_paths:
            app.status_var.set(f'Error tagging some images: {failed_paths[0][1]}')


    def toggle_fullscreen(self, event=None):
        """Toggle fullscreen mode and hide/show the bottom bar."""
        app = self.app
        app.is_fullscreen = not app.is_fullscreen
        app.root.attributes("-fullscreen", app.is_fullscreen)

        if app.is_fullscreen:
            app.bottom_bar.pack_forget()
        else:
            app.bottom_bar.pack(fill="x", pady=(10, 0))

        app.status_var.set(f"Fullscreen: {'ON' if app.is_fullscreen else 'OFF'}")


    def upscale_selected(self):

        app = self.app
        if not app.selected_gallery_path:

            app._dialog.info("No Selection", "Please click an image in the gallery first.")

            return

        path = app.selected_gallery_path

        if "_upscaled" in path.stem:

            app._dialog.info("Already Upscaled", "This image has already been upscaled.")

            return

        try:

            from PIL import Image

            img = Image.open(path)

            orig_w, orig_h = img.size

            new_w, new_h = orig_w * 2, orig_h * 2

            upscaled = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

            out_path = path.parent / f"{path.stem}_upscaled{path.suffix}"

            upscaled.save(str(out_path))

            app.status_var.set(f"Upscaled saved: {out_path.name}")

            app.load_gallery()

        except Exception as e:

            app._dialog.error("Upscale Failed", "Could not upscale the image. It may be too large or in an unsupported format.")
