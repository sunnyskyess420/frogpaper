import tkinter as tk
import logging
import os
import threading
import random
from pathlib import Path
from datetime import datetime

from tkinter import ttk, messagebox, simpledialog
from PIL import Image, ImageTk, ImageFilter, ImageEnhance, ImageDraw, ImageFont

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
    remove_tag_from_image,
    get_all_tags,
    get_images_by_tag,
    organize_image_into_folder,
    rename_image,
    get_folder_structure,
    delete_image_and_tags,
    save_prompt_parameters,
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
        "favorite": "star",
        "style": "palette",
        "text": "text_edit",
        "delete": "delete",
        "export": "export",
    }

    def __init__(self, app):
        self.app = app
        self._fade_jobs = {}  # label widget -> list of after() ids

    # ── Icon helpers ────────────────────────────────────────────────
    def _apply_toolbar_icons(self):
        """Set icon images on gallery action buttons after theme load."""
        app = self.app
        if not hasattr(app, '_gallery_action_row_order'):
            return
        pal = app.THEMES.get(app.current_theme_name, app.THEMES["darkforest"])
        accent = pal.get("accent", pal["progress"])
        try:
            from icons import get_icon
            icon_names = ["wallpaper", "star", "palette", "text_edit", "delete", "export"]
            for btn, icon_name in zip(app._gallery_action_row_order, icon_names):
                if hasattr(btn, 'configure') and icon_name:
                    _img = get_icon(icon_name, size=14, color=accent)
                    btn.configure(image=_img, compound="left")
                    btn._icon_ref = _img  # prevent GC
        except Exception:
            pass  # Graceful fallback — buttons still work with text-only

    def _fade_in_thumb(self, label_widget, photo_image, steps=4, interval=35):
        """Smoothly fade-in a thumbnail using brightness stepping.

        Starts at 30% brightness and ramps to 100% over *steps* frames.
        """
        # Cancel any previous fade on this label
        if label_widget in self._fade_jobs:
            for job_id in self._fade_jobs[label_widget]:
                try:
                    label_widget.after_cancel(job_id)
                except Exception:
                    pass
        self._fade_jobs[label_widget] = []

        from PIL import ImageEnhance
        base_img = ImageTk.getimage(photo_image)

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

            # Update status for image loading

            app.root.after(0, lambda: app.status_var.set(f"Loading image for {style} style..."))

            

            from style_transfer import apply_style_to_image

            

            # Update status for processing

            app.root.after(0, lambda: app.status_var.set(f"Processing {style} style..."))

            

            styled_path = apply_style_to_image(app.selected_gallery_path, style)

            

            if styled_path:

                # Update status for success

                app.root.after(0, lambda: app.status_var.set(f"✅ {style} style applied successfully!"))

                # Update UI from main thread

                app.root.after(0, app._style_applied_success, styled_path, style)

            else:

                # Update status for failure

                app.root.after(0, lambda: app.status_var.set(f"❌ {style} style failed - no image created"))

                app.root.after(0, app._style_applied_failed, style)

                

        except Exception as e:

            # Update status for error - avoid threading issues

            try:

                app.root.after(0, lambda: app.status_var.set(f"❌ Style transfer error: {str(e)}"))

                app.root.after(0, app._style_applied_error, str(e))

            except:

                # Fallback if root is no longer valid

                logger.error(f"Style transfer error (app.UI update failed): {str(e)}")


    def _build_gallery_tab(self, parent):

        # Gallery Controls — contains view selector, filters, sort, and action buttons
        app = self.app
        filter_frame = ttk.LabelFrame(parent, text="Gallery Controls", padding=5)

        filter_frame.pack(fill='x', pady=(0, 8))

        # Row 0: Action buttons
        action_row = ttk.Frame(filter_frame)
        action_row.pack(fill='x', pady=(0, 4))
        app._gallery_action_row = action_row  # saved for view-switch repack

        _btn_wallpaper = ttk.Button(action_row, text=" Set as Wallpaper",
                   command=app._gallery_set_wallpaper)
        _btn_wallpaper.pack(side="left", padx=(0, 6))

        app._btn_save_to_fav = ttk.Button(action_row, text=" Save to Favorites",
                   command=app._gallery_save_to_favorites)
        app._btn_save_to_fav.pack(side="left", padx=(0, 6))

        app.style_menu_btn = ttk.Menubutton(action_row, text=" Apply Style")
        app.style_menu = tk.Menu(app.style_menu_btn, tearoff=0)
        for display_name, style_key in [
            ("Vivid Enhance", "edge_enhance"), ("Monochrome BW", "bw"),
            ("Vintage Warm", "vintage"), ("Color Pop", "posterize"),
            ("Oil Painting", "oil_painting"), ("Watercolor", "watercolor"),
            ("Cyberpunk Neon", "cyberpunk_neon"), ("Vaporwave", "vaporwave"),
            ("Pixel Art", "pixel_art"), ("Sketch Pencil", "sketch_pencil"),
            ("Gouache", "gouache"), ("Art Deco", "art_deco"),
            ("Surreal Dali", "surreal_dali"), ("3D Render", "3d_render"),
            ("Anime Key", "anime_key"), ("Noir BW", "noir_bw"),
            ("Vintage Sepia", "vintage_sepia"), ("Pop Art", "pop_art"),
            ("Impressionist", "impressionist"),
        ]:
            app.style_menu.add_command(label=display_name,
                command=lambda sk=style_key: app._gallery_apply_theme(sk))
        app.style_menu_btn.config(menu=app.style_menu)
        # Not packed — Apply Style moved to center panel

        _btn_text = ttk.Button(action_row, text=" Add Text",
                   command=app._gallery_add_text)
        _btn_text.pack(side="left", padx=(0, 6))

        _btn_delete = ttk.Button(action_row, text=" Delete",
                   command=app._gallery_delete)
        _btn_delete.pack(side="left", padx=(0, 6))

        app._btn_export_portraits = ttk.Button(action_row, text=" Export Portraits",
                   command=app._gallery_export_portraits)
        app._btn_export_portraits.pack(side="left", padx=(0, 6))

        # Full ordered list — mirrors the view radio order: Gallery|Favorites|Styled|Manual
        # Gallery=Wallpaper, Favorites=Save to Fav, Styled=Apply Style, Manual=Delete
        app._gallery_action_row_order = [
            _btn_wallpaper, app._btn_save_to_fav, app.style_menu_btn,
            _btn_text, _btn_delete, app._btn_export_portraits,
        ]

        # Row 1: View selector
        view_row = ttk.Frame(filter_frame)
        view_row.pack(fill='x', pady=(0, 4))
        ttk.Label(view_row, text="View:").pack(side='left', padx=(0, 6))
        app.gallery_view_var = tk.StringVar(value="Gallery")
        ttk.Radiobutton(view_row, text="Gallery", variable=app.gallery_view_var,
                        value="Gallery", command=app._on_gallery_view_changed).pack(side='left', padx=(0, 6))
        ttk.Radiobutton(view_row, text="Favorites", variable=app.gallery_view_var,
                        value="Favorites", command=app._on_gallery_view_changed).pack(side='left', padx=(0, 6))
        ttk.Radiobutton(view_row, text="Styled", variable=app.gallery_view_var,
                        value="Styled", command=app._on_gallery_view_changed).pack(side='left', padx=(0, 6))
        ttk.Radiobutton(view_row, text="Manual", variable=app.gallery_view_var,
                        value="Manual", command=app._on_gallery_view_changed).pack(side='left', padx=(0, 6))
        ttk.Radiobutton(view_row, text="16:9", variable=app.gallery_view_var,
                        value="Ratio 16:9", command=app._on_gallery_view_changed).pack(side='left', padx=(0, 6))
        ttk.Radiobutton(view_row, text="Portrait", variable=app.gallery_view_var,
                        value="Ratio 9:16", command=app._on_gallery_view_changed).pack(side='left', padx=(0, 6))
        ttk.Radiobutton(view_row, text="Square", variable=app.gallery_view_var,
                        value="Ratio 1:1", command=app._on_gallery_view_changed).pack(side='left')

        # Row 1: Sort & Organize

        ctrl_row = ttk.Frame(filter_frame)

        ctrl_row.pack(fill='x', pady=2)

        ttk.Label(ctrl_row, text="Sort:").pack(side='left', padx=(0, 4))

        app.sort_combo_var = tk.StringVar(value="Date Newest")

        app.sort_combo = ttk.Combobox(ctrl_row, textvariable=app.sort_combo_var,
                                        values=["Date Newest", "Date Oldest", "Name A-Z", "Name Z-A", "Size Largest", "Size Smallest", "Resolution Largest", "Resolution Smallest"],
                                        state="readonly", width=18)
        app.sort_combo.pack(side='left', padx=(0, 8))
        app.sort_combo.bind('<<ComboboxSelected>>', app.sort_gallery)
        app.sort_combo.bind("<MouseWheel>", lambda e: "break")
        app.sort_combo.bind("<Button-4>", lambda e: "break")
        app.sort_combo.bind("<Button-5>", lambda e: "break")

        # --- Tag filter ---
        ttk.Label(ctrl_row, text="Tag:").pack(side='left', padx=(8, 4))
        app.gallery_tag_var = tk.StringVar(value='All tags')
        app.gallery_tag_combo = ttk.Combobox(ctrl_row, textvariable=app.gallery_tag_var,
                                              values=['All tags'] + get_all_tags(),
                                              state="readonly", width=16)
        app.gallery_tag_combo.pack(side='left', padx=(0, 4))
        app.gallery_tag_combo.bind('<<ComboboxSelected>>', lambda e: app._on_tag_selected())
        app.gallery_tag_combo.bind("<MouseWheel>", lambda e: "break")
        app.gallery_tag_combo.bind("<Button-4>", lambda e: "break")
        app.gallery_tag_combo.bind("<Button-5>", lambda e: "break")
        app.gallery_tag_var.trace_add('write', lambda *a: app._on_tag_var_changed())

        _btn_tag = ttk.Button(ctrl_row, text=" Tag Image", command=app._gallery_tag_selected)
        _btn_tag.pack(side='left', padx=(0, 4))

        # Auto-Tag All is in the gallery header beside Open Folder / Refresh Gallery
        # (see app.py _build_ui)

        app.delete_tag_btn = ttk.Button(ctrl_row, text=" Delete Tag", command=self._confirm_delete_tag)
        # Hidden by default — shown only when a specific tag is selected
        # (see _on_tag_var_changed)



        # Thumbnails

        thumb_frame = ttk.Frame(parent)

        thumb_frame.pack(fill='both', expand=True)

        # --- Gallery canvas (shown in Gallery view) ---
        app.gallery_canvas = tk.Canvas(thumb_frame, highlightthickness=0)
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
        app.gallery_fav_canvas = tk.Canvas(thumb_frame, highlightthickness=0)
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
        app.gallery_styled_canvas = tk.Canvas(thumb_frame, highlightthickness=0)
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
        app.gallery_manual_canvas = tk.Canvas(thumb_frame, highlightthickness=0)
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

        

        app.load_gallery()  # Initial load


    def _build_ratio_gallery_ui(self, filtered_images, ratio_mode, tag_filter):
        """Build the app.UI for ratio gallery (must run on main thread)."""
        app = self.app
        try:
            app.gallery_images = filtered_images

            # Clear existing gallery cards
            for widget in app.gallery_inner.winfo_children():
                widget.destroy()
            app.gallery_cards.clear()

            # Empty-state message
            if not app.gallery_images:
                pal = app.THEMES.get(app.current_theme_name, app.THEMES["darkforest"])
                ratio_labels = {
                    "Ratio 16:9": "16:9 widescreen",
                    "Ratio 9:16": "Portrait (9:16)",
                    "Ratio 1:1": "Square (1:1)",
                }
                view_label = ratio_labels.get(ratio_mode, ratio_mode)
                if tag_filter:
                    message = f"No {view_label} images tagged '{tag_filter}'."
                else:
                    message = f"No {view_label} images found. Generate wallpapers in this size to see them here."
                tk.Label(
                    app.gallery_inner,
                    text=message,
                    bg=pal["panel"], fg=pal["text"], font=app.small_font,
                    pady=30,
                ).grid(row=0, column=0, sticky="ew")
                app.gallery_canvas.configure(
                    scrollregion=app.gallery_canvas.bbox("all") or (0, 0, 1, 1)
                )
                app.status_var.set(f'{ratio_mode}: 0 images')
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
            threading.Thread(target=self._load_thumbnails_lazy, args=(ratio_mode,), daemon=True).start()

        except Exception as e:
            app.status_var.set(f'Error building ratio gallery: {e}')


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

        # Store placeholder reference for later replacement
        app.gallery_cards[str(img_path)] = (card, placeholder, name_label, row, col, index)

        # Bind click events to card
        card.bind('<Button-1>', lambda e, p=img_path, idx=index: app.on_card_click(e, p, idx))
        card.bind('<Button-3>', lambda e, p=img_path: app.show_gallery_context_menu(e, p))
        placeholder.bind('<Button-1>', lambda e, p=img_path, idx=index: app.on_card_click(e, p, idx))
        placeholder.bind('<Button-3>', lambda e, p=img_path: app.show_gallery_context_menu(e, p))
        name_label.bind('<Button-1>', lambda e, p=img_path, idx=index: app.on_card_click(e, p, idx))

    def _load_thumbnails_lazy(self, ratio_mode):
        """Load thumbnails in background thread and update UI on main thread."""
        app = self.app
        try:
            from PIL import Image, ImageTk

            for idx, img_path in enumerate(app.gallery_images):
                # Check if view changed during loading
                if app.gallery_view_var.get() not in ["Ratio 16:9", "Ratio 9:16", "Ratio 1:1"]:
                    return

                path_str = str(img_path)
                card_data = app.gallery_cards.get(path_str)

                if not card_data:
                    continue

                card, placeholder, name_label, row, col, index = card_data

                # Check if thumbnail is already cached
                if path_str in app.thumb_cache:
                    thumb = app.thumb_cache[path_str]
                else:
                    try:
                        img = Image.open(img_path)
                        img.thumbnail((240, 135), Image.Resampling.LANCZOS)
                        thumb = ImageTk.PhotoImage(img)
                        if len(app.thumb_cache) > 200:
                            app.thumb_cache.clear()
                        app.thumb_cache[path_str] = thumb
                    except Exception as e:
                        logger.error(f"Thumbnail loading error for {img_path}: {e}")
                        continue

                # Update UI on main thread
                def update_card():
                    try:
                        # Replace placeholder with actual thumbnail
                        placeholder.destroy()
                        label = tk.Label(card, image=thumb, bg=pal["panel"])
                        label.image = thumb
                        label.grid(row=0, column=0, pady=(4, 4), padx=4)

                        try:
                            self._fade_in_thumb(label, thumb, steps=4, interval=35)
                        except Exception:
                            pass

                        # Rebind events
                        label.bind('<Button-1>', lambda e, p=img_path, idx=index: app.on_card_click(e, p, idx))
                        label.bind('<Double-Button-1>', lambda e, p=img_path: app.set_gallery_image_as_wallpaper(p))
                        label.bind('<Button-3>', lambda e, p=img_path: app.show_gallery_context_menu(e, p))

                        # Add file size + resolution info
                        try:
                            size_bytes = img_path.stat().st_size
                            size_str = f"{size_bytes / 1_048_576:.1f} MB" if size_bytes >= 1_048_576 else f"{size_bytes / 1024:.0f} KB"
                            with Image.open(img_path) as _im:
                                w_px, h_px = _im.size
                            info_text = f"{w_px}×{h_px}  •  {size_str}"
                        except Exception:
                            info_text = ""

                        info_label = tk.Label(card, text=info_text, fg=pal["muted"], font=app.tinyfont,
                                            bg=pal["panel"], anchor="w", justify="left", padx=6, pady=0)
                        info_label.grid(row=2, column=0, sticky='ew')
                        info_label.bind('<Button-1>', lambda e, p=img_path, idx=index: app.on_card_click(e, p, idx))

                        # Update card data
                        app.gallery_cards[path_str] = (card, name_label)

                    except Exception as e:
                        logger.error(f"UI update error for {img_path}: {e}")

                pal = app.THEMES.get(app.current_theme_name, app.THEMES["darkforest"])
                app.root.after(0, update_card)

            # Update status when done
            app.root.after(0, lambda: app.status_var.set(f'{ratio_mode}: {len(app.gallery_images)} images'))

        except Exception as e:
            app.root.after(0, lambda: app.status_var.set(f'Error loading thumbnails: {e}'))

    def _confirm_delete_tag(self):
        """Delete the selected tag after user confirmation."""
        app = self.app
        current_tag = app.gallery_tag_var.get()
        if not current_tag or current_tag == 'All tags':
            return

        # First confirmation dialog
        if not app._dialog.ask('Delete Tag', f'Delete tag "{current_tag}" from all images?\n\nThis cannot be undone.'):
            return

        # Second confirmation for "All tags" safety check
        if current_tag == 'All tags':
            if not app._dialog.ask('Confirm Delete', f'Are you absolutely sure you want to delete the "All tags" tag?\n\nThis will remove it from all images in the gallery.'):
                return

        # Delete the tag from all images
        try:
            from gallery_manager import get_images_by_tag, remove_tag_from_image

            # Get all images with this tag
            tagged_images = get_images_by_tag(current_tag)

            # Remove the tag from each image
            for image_path in tagged_images:
                remove_tag_from_image(image_path, current_tag)

            # Refresh the tag dropdown
            app._refresh_gallery_tag_filter()

            app.status_var.set(f'Tag "{current_tag}" deleted from {len(tagged_images)} images.')
        except Exception as e:
            app.status_var.set(f'Error deleting tag: {e}')
            app._dialog.error('Error', f'Failed to delete tag: {e}')


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
        """Scan all generated images and auto-tag from filenames.

        Filename format: SUBJECT_STYLE_YYYYMMDD_N.png
        Extracts subject and style as tags for any untagged image.
        """
        import re as _re
        app = self.app
        try:
            from set_wallpaper import MANUAL_DIR, GENERATED_DIR
        except ImportError:
            app.status_var.set('Auto-tag: could not find wallpaper directories.')
            return

        app.status_var.set('Auto-tagging images from filenames...')
        app.root.update_idletasks()

        # Pattern: SUBJECT_STYLE_YYYYMMDD_N.ext
        filename_re = _re.compile(r'^([a-z0-9_]+)_([a-z0-9]+)_\d{8}_\d+\.', _re.IGNORECASE)

        tagged_count = 0
        skipped_count = 0
        error_count = 0

        for search_dir in [GENERATED_DIR, MANUAL_DIR]:
            if not search_dir.exists():
                continue
            for img_file in search_dir.iterdir():
                if not img_file.is_file() or img_file.suffix.lower() not in {'.png', '.jpg', '.jpeg', '.webp'}:
                    continue
                m = filename_re.match(img_file.name)
                if not m:
                    skipped_count += 1
                    continue
                raw_subject = m.group(1).replace('_', ' ')
                raw_style = m.group(2).replace('_', ' ')
                # Skip generic filenames
                if raw_subject.lower() in ('wallpaper', 'unknown', 'image'):
                    skipped_count += 1
                    continue
                tags = [raw_subject]
                if raw_style.lower() != raw_subject.lower():
                    tags.append(raw_style)
                try:
                    add_tags_to_image(img_file, tags)
                    tagged_count += 1
                except Exception:
                    error_count += 1

        app._refresh_gallery_tag_filter()
        app.status_var.set(f'Auto-tag complete: {tagged_count} tagged, {skipped_count} skipped, {error_count} errors')


    def _create_manual_card(self, img_path, index, pal, border):
        """Create a card for a manual image."""
        app = self.app
        cols = min(3, max(1, app.gallery_manual_canvas.winfo_width() // 260))
        row, col = index // cols, index % cols

        card = tk.Frame(app.gallery_manual_inner, bg=pal["panel"],
                       highlightthickness=1, highlightbackground=border, bd=0)
        card.grid(row=row, column=col, padx=6, pady=6, sticky='nsew')
        card.columnconfigure(0, weight=1)

        # Thumbnail
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
            label.image = thumb
            label.pack(pady=(4, 4), padx=4)

            try:
                self._fade_in_thumb(label, thumb, steps=4, interval=35)
            except Exception:
                pass

            # Click to select, double-click to set wallpaper
            label.bind('<Button-1>', lambda e, p=img_path: app._select_manual_image(p))
            label.bind('<Double-Button-1>', lambda e, p=img_path: app.set_gallery_image_as_wallpaper(p))
            label.bind('<Button-3>', lambda e, p=img_path: app.show_gallery_context_menu(e, p))
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

        # File size + resolution info
        try:
            size_bytes = img_path.stat().st_size
            size_str = f"{size_bytes / 1_048_576:.1f} MB" if size_bytes >= 1_048_576 else f"{size_bytes / 1024:.0f} KB"
            from PIL import Image as _PILImg
            with _PILImg.open(img_path) as _im:
                w_px, h_px = _im.size
            info_text = f"{w_px}\u00d7{h_px}  \u2022  {size_str}"
        except Exception:
            info_text = ""
        info_label = tk.Label(card, text=info_text, fg=pal["muted"], font=app.tinyfont,
                              bg=pal["panel"], anchor="w", justify="left", padx=6, pady=0)
        info_label.pack(fill="x")
        info_label.bind('<Button-1>', lambda e, p=img_path: app._select_manual_image(p))

        app.gallery_manual_cards[str(img_path)] = (card, name_label)


    def _create_styled_card(self, img_path, index, pal, border):
        """Create a card for a styled image."""
        app = self.app
        cols = min(3, max(1, app.gallery_styled_canvas.winfo_width() // 260))
        row, col = index // cols, index % cols

        card = tk.Frame(app.gallery_styled_inner, bg=pal["panel"],
                       highlightthickness=1, highlightbackground=border, bd=0)
        card.grid(row=row, column=col, padx=6, pady=6, sticky='nsew')
        card.columnconfigure(0, weight=1)

        # Thumbnail
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
            label.image = thumb
            label.pack(pady=(4, 4), padx=4)

            try:
                self._fade_in_thumb(label, thumb, steps=4, interval=35)
            except Exception:
                pass

            # Click to select, double-click to set wallpaper
            label.bind('<Button-1>', lambda e, p=img_path: app._select_styled_image(p))
            label.bind('<Double-Button-1>', lambda e, p=img_path: app.set_gallery_image_as_wallpaper(p))
            label.bind('<Button-3>', lambda e, p=img_path: app.show_gallery_context_menu(e, p))
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

        # File size + resolution info
        try:
            size_bytes = img_path.stat().st_size
            size_str = f"{size_bytes / 1_048_576:.1f} MB" if size_bytes >= 1_048_576 else f"{size_bytes / 1024:.0f} KB"
            from PIL import Image as _PILImg
            with _PILImg.open(img_path) as _im:
                w_px, h_px = _im.size
            info_text = f"{w_px}\u00d7{h_px}  \u2022  {size_str}"
        except Exception:
            info_text = ""
        info_label = tk.Label(card, text=info_text, fg=pal["muted"], font=app.tinyfont,
                              bg=pal["panel"], anchor="w", justify="left", padx=6, pady=0)
        info_label.pack(fill="x")
        info_label.bind('<Button-1>', lambda e, p=img_path: app._select_styled_image(p))

        app.gallery_styled_cards[str(img_path)] = (card, name_label)


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
            app._dialog.error("Delete Failed", f"Failed to delete:\n{e}")


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
            import threading
            threading.Thread(target=app.load_gallery_by_ratio, args=(view_mode, tag_filter), daemon=True).start()
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
        """Add Text Overlay — improved dialog with font selection, live preview, and extra options."""
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
            ("Palatino Linotype",       "pala.ttf",          ["Palatino Linotype", "Palatino"]),
            ("Segoe UI",                "segoeui.ttf",       ["Segoe UI"]),
            ("Trebuchet MS",            "trebuc.ttf",        ["Trebuchet MS"]),
            ("Verdana",                 "verdana.ttf",       ["Verdana"]),
            ("Franklin Gothic Medium",  "framd.ttf",         ["Franklin Gothic Medium"]),
            ("Lucida Console",          "lucon.ttf",         ["Lucida Console"]),
        ]

        if sys.platform == "win32":
            win_fonts_dir = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
            for display, filename, _ in curated:
                fpath = win_fonts_dir / filename
                if fpath.exists():
                    discovered_fonts[display] = str(fpath)
        else:
            # Linux / macOS: try to locate each curated font via fc-list
            import subprocess
            try:
                result = subprocess.run(
                    ["fc-list", "--format", "%{file}|%{family}\n"],
                    capture_output=True, text=True, timeout=5
                )
                fc_map = {}  # family_lower -> file_path
                for line in result.stdout.strip().splitlines():
                    parts = line.split("|", 1)
                    if len(parts) == 2:
                        fc_map[parts[1].strip().lower()] = parts[0].strip()
                for display, _, linux_names in curated:
                    for ln in linux_names:
                        fpath = fc_map.get(ln.lower())
                        if fpath:
                            discovered_fonts[display] = fpath
                            break
            except Exception:
                pass

        font_names = [name for name, _, _ in curated if name in discovered_fonts]
        if not font_names:
            font_names = ["Default"]

        # ── Create dialog ──
        dialog = tk.Toplevel(app.root)
        dialog.title("Add Text Overlay")
        dialog.geometry("580x760")
        dialog.transient(app.root)
        dialog.grab_set()
        dialog.configure(bg=pal["bg"])
        
        # Center the dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
        y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{x}+{y}")

        # ── Main layout: left controls, right preview ──
        main_frame = ttk.Frame(dialog)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        ctrl_frame = ttk.Frame(main_frame)
        ctrl_frame.pack(side="left", fill="y", padx=(0, 10))
        preview_frame = ttk.Frame(main_frame)
        preview_frame.pack(side="left", fill="both", expand=True)

        # ── Variables ──
        text_var = tk.StringVar()
        position_var = tk.StringVar(value="bottom-right")
        font_size_var = tk.IntVar(value=36)
        color_var = tk.StringVar(value="white")
        outline_color_var = tk.StringVar(value="black")
        outline_width_var = tk.IntVar(value=2)
        bold_var = tk.BooleanVar(value=False)
        opacity_var = tk.IntVar(value=100)
        shadow_var = tk.BooleanVar(value=False)
        font_name_var = tk.StringVar(value=font_names[0] if font_names else "Default")

        # ── Text input ──
        ttk.Label(ctrl_frame, text="Text:").pack(anchor="w", pady=(0, 2))
        text_entry = ttk.Entry(ctrl_frame, textvariable=text_var, width=28)
        text_entry.pack(fill="x", pady=(0, 8))
        text_entry.focus()

        # ── Font list with per-font preview ──
        ttk.Label(ctrl_frame, text="Font:").pack(anchor="w", pady=(0, 2))
        font_listbox = tk.Listbox(ctrl_frame, height=7, exportselection=False,
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

        # Select first item and sync with font_name_var
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

        # ── Bold checkbox ──
        ttk.Checkbutton(ctrl_frame, text="Bold", variable=bold_var).pack(anchor="w", pady=(0, 8))

        # ── Text color ──
        ttk.Label(ctrl_frame, text="Text Color:").pack(anchor="w", pady=(0, 2))
        color_combo = ttk.Combobox(ctrl_frame, textvariable=color_var,
                                     values=["white", "black", "red", "blue", "green",
                                             "yellow", "cyan", "magenta", "orange", "pink",
                                             "#FF6B6B", "#4ECDC4", "#FFE66D", "#95E1D3"],
                                     state="readonly", width=26)
        color_combo.pack(fill="x", pady=(0, 8))

        # ── Outline color ──
        ttk.Label(ctrl_frame, text="Outline Color:").pack(anchor="w", pady=(0, 2))
        outline_combo = ttk.Combobox(ctrl_frame, textvariable=outline_color_var,
                                      values=["black", "white", "darkgray", "none",
                                              "#333333", "#000000"],
                                      state="readonly", width=26)
        outline_combo.pack(fill="x", pady=(0, 8))

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
                                   orient="horizontal", length=220,
                                   command=lambda v: opacity_label.configure(text=f"{int(float(v))}%"))
        opacity_scale.set(100)
        opacity_scale.pack(fill="x", pady=(0, 8))

        # ── Shadow checkbox ──
        ttk.Checkbutton(ctrl_frame, text="Drop Shadow", variable=shadow_var).pack(anchor="w", pady=(0, 8))

        # ── Position ──
        ttk.Label(ctrl_frame, text="Position:").pack(anchor="w", pady=(0, 2))
        position_frame = ttk.Frame(ctrl_frame)
        position_frame.pack(fill="x", pady=(0, 8))
        positions = ["top-left", "top-right", "middle-top", "middle-bottom",
                     "bottom-left", "bottom-right", "center"]
        pos_labels = ["Top-Left", "Top-Right", "Mid-Top", "Mid-Bottom",
                      "Bot-Left", "Bot-Right", "Center"]
        for i, (pos, lbl) in enumerate(zip(positions, pos_labels)):
            ttk.Radiobutton(position_frame, text=lbl, variable=position_var,
                           value=pos).grid(row=i // 2, column=i % 2, sticky="w", padx=(0, 8))

        # ── Preview area ──
        ttk.Label(preview_frame, text="Preview", font=app.bold_font).pack(anchor="w", pady=(0, 4))
        preview_canvas = tk.Canvas(preview_frame, width=320, height=180,
                                    bg=pal["panel2"], highlightthickness=1,
                                    highlightbackground=pal.get("border_color", pal["panel2"]))
        preview_canvas.pack(fill="both", expand=True, pady=(0, 8))

        # Load the source image for preview
        try:
            from PIL import Image as _PILImg, ImageTk as _PILTk
            preview_img = _PILImg.open(img_path)
            # Scale to fit preview area
            max_w, max_h = 320, 180
            preview_img.thumbnail((max_w, max_h), _PILImg.Resampling.LANCZOS)
            _preview_photo = _PILTk.PhotoImage(preview_img)
            preview_canvas._base_photo = _preview_photo  # keep reference
            preview_canvas.create_image(160, 90, image=_preview_photo, anchor="center")
        except Exception:
            preview_canvas.create_text(160, 90, text="Image unavailable", fill=pal["muted"],
                                         font=app.small_font)

        # ── Live preview update ──
        def update_preview(*args):
            txt = text_var.get().strip()
            if not txt:
                # Clear any previous text overlay and show base image
                try:
                    preview_canvas.delete("overlay")
                    if hasattr(preview_canvas, '_base_photo'):
                        preview_canvas.create_image(160, 90, image=preview_canvas._base_photo,
                                                    anchor="center", tags="overlay_base")
                except Exception:
                    pass
                return

            try:
                from PIL import Image as _Img, ImageDraw as _Draw, ImageFont as _Font, ImageTk as _Tk
                from style_transfer import get_style_transfer
                import io

                # Build preview at small scale
                with _Img.open(img_path) as src:
                    # Scale to preview size
                    max_pw, max_ph = 320, 180
                    ratio = min(max_pw / src.width, max_ph / src.height)
                    pw, ph = int(src.width * ratio), int(src.height * ratio)
                    prev = src.resize((pw, ph), _Img.Resampling.LANCZOS)

                if prev.mode != 'RGBA':
                    prev = prev.convert('RGBA')

                draw = _Draw.Draw(prev)

                # Scale font size to preview
                scaled_size = max(8, int(font_size_var.get() * ratio))

                # Load font
                font = None
                sel_font = font_name_var.get()
                fpath = discovered_fonts.get(sel_font)
                if fpath:
                    try:
                        font = _Font.truetype(fpath, scaled_size)
                    except Exception:
                        font = None
                if font is None:
                    for fn in ["DejaVuSans-Bold.ttf" if bold_var.get() else "DejaVuSans.ttf",
                               "LiberationSans-Bold.ttf" if bold_var.get() else "LiberationSans.ttf",
                               "FreeSans.ttf"]:
                        try:
                            font = _Font.truetype(fn, scaled_size)
                            break
                        except Exception:
                            continue
                if font is None:
                    font = _Font.load_default()

                # Calculate text position in preview coords
                bbox = draw.textbbox((0, 0), txt, font=font)
                tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
                pad = int(12 * ratio)
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

                # Shadow
                if shadow_var.get():
                    so = max(1, scaled_size // 12)
                    for ax in range(-ow, ow + 1):
                        for ay in range(-ow, ow + 1):
                            draw.text((tx + ax + so, ty + ay + so), txt, font=font, fill="black")

                # Outline
                if ow > 0 and ol_color != "none":
                    for ax in range(-ow, ow + 1):
                        for ay in range(-ow, ow + 1):
                            if ax != 0 or ay != 0:
                                draw.text((tx + ax, ty + ay), txt, font=font, fill=ol_color)

                # Text
                t_color = color_var.get()
                draw.text((tx, ty), txt, font=font, fill=t_color)

                # Opacity
                opa = opacity_var.get()
                if opa < 100:
                    alpha = int(255 * opa / 100)
                    # Build an overlay approach — blend with background
                    base = _Img.open(img_path).convert('RGBA')
                    base.thumbnail((max_pw, max_ph), _Img.Resampling.LANCZOS)
                    text_only = _Img.new('RGBA', prev.size, (0, 0, 0, 0))
                    td = _Draw.Draw(text_only)
                    if shadow_var.get():
                        so = max(1, scaled_size // 12)
                        for ax in range(-ow, ow + 1):
                            for ay in range(-ow, ow + 1):
                                td.text((tx + ax + so, ty + ay + so), txt, font=font, fill=(0, 0, 0, alpha))
                    if ow > 0 and ol_color != "none":
                        from PIL import ImageColor as _IC
                        try:
                            ol_rgb = _IC.getrgb(ol_color)
                        except Exception:
                            ol_rgb = (0, 0, 0)
                        for ax in range(-ow, ow + 1):
                            for ay in range(-ow, ow + 1):
                                if ax != 0 or ay != 0:
                                    td.text((tx + ax, ty + ay), txt, font=font, fill=(*ol_rgb, alpha))
                    from PIL import ImageColor as _IC2
                    try:
                        tc_rgb = _IC2.getrgb(t_color)
                    except Exception:
                        tc_rgb = (255, 255, 255)
                    td.text((tx, ty), txt, font=font, fill=(*tc_rgb, alpha))
                    prev = _Img.alpha_composite(base, text_only)

                if prev.mode == 'RGBA':
                    prev = prev.convert('RGB')

                photo = _Tk.PhotoImage(prev)
                preview_canvas.delete("all")
                preview_canvas.create_image(pw // 2, ph // 2, image=photo, anchor="center")
                preview_canvas._preview_photo = photo  # keep reference

            except Exception:
                pass  # Silent fail for preview — non-critical

        # Bind all controls to trigger live preview update
        for var in (text_var, font_name_var, color_var, outline_color_var,
                    position_var, bold_var, shadow_var, opacity_var, font_size_var,
                    outline_width_var):
            if isinstance(var, (tk.StringVar, tk.IntVar)):
                var.trace_add("write", update_preview)
            elif isinstance(var, tk.BooleanVar):
                var.trace_add("write", update_preview)

        # ── Buttons ──
        button_frame = ttk.Frame(dialog)
        button_frame.pack(fill="x", pady=(8, 12))

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
                    position=position_var.get(),
                    font_size=font_size_var.get(),
                    text_color=color_var.get(),
                    outline_color=outline_color_var.get() if outline_color_var.get() != "none" else None,
                    outline_width=outline_width_var.get() if outline_color_var.get() != "none" else 0,
                    font_path=fpath,
                    bold=bold_var.get(),
                    opacity=opacity_var.get(),
                    shadow=shadow_var.get()
                )
                
                if result_path and result_path.exists():
                    app.status_var.set(f"Text overlay saved to Styled view: {result_path.name}")
                    app._dialog.info("Saved to Styled View", f"Text overlay applied successfully!\n\nImage saved as:\n{result_path.name}\n\nSwitching to the Styled tab.")
                    app.gallery_view_var.set("Styled")
                    app._on_gallery_view_changed()
                    dialog.destroy()
                else:
                    app._dialog.error("Error", "Failed to add text overlay.")
            except Exception as e:
                import traceback
                error_msg = f"Failed to add text: {str(e)}\n\nTraceback:\n{traceback.format_exc()}"
                app._dialog.error("Error", error_msg)

        ttk.Button(button_frame, text="Apply", command=apply_text).pack(side="left", padx=(0, 10))
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side="left")

        # Bind Enter key to apply
        text_entry.bind("<Return>", lambda e: apply_text())

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
        
        # Show initial status
        app.status_var.set("Finding portrait images...")
        
        # Run in background thread to avoid UI freeze
        def _export_thread():
            try:
                from utils import copy_images_to_folder, open_folder_in_explorer
                
                # Collect portrait images
                portrait_images = get_portrait_images()
                
                if not portrait_images:
                    app.root.after(0, lambda: app._dialog.info(
                        "No Portrait Images", 
                        "No portrait (9:16) images found in your gallery.\n\n"
                        "Generate some portrait wallpapers first, then try again."
                    ))
                    app.root.after(0, lambda: app.status_var.set("No portrait images found"))
                    return
                
                # Update status with count
                app.root.after(0, lambda: app.status_var.set(f"Found {len(portrait_images)} portrait images"))
                app.root.after(0, lambda: app.status_var.set(f"Copying {len(portrait_images)} images to {destination_path.name}..."))
                
                # Copy images to selected destination
                success_count, failure_count = copy_images_to_folder(portrait_images, destination_path)
                
                # Show completion status
                if failure_count > 0:
                    app.root.after(0, lambda: app.status_var.set(
                        f"Exported {success_count} images ({failure_count} failed)"
                    ))
                else:
                    app.root.after(0, lambda: app.status_var.set(
                        f"Successfully exported {success_count} portrait images"
                    ))
                
                # Open destination folder in Explorer
                open_folder_in_explorer(destination_path)
                
                # Show success dialog with instructions
                app.root.after(0, lambda: app._dialog.info(
                    "Portrait Images Exported",
                    f"Successfully exported {success_count} portrait images to:\n\n"
                    f"{destination_path}\n\n"
                    f"Your images are ready! \n\n"
                    f"Note: If your phone doesn't appear in the export dialog (MTP devices),\n"
                    f"you can copy the images manually:\n"
                    f"1. Open Windows Explorer (your phone is visible there)\n"
                    f"2. Navigate to the exported folder above\n"
                    f"3. Drag and drop images to your phone\n\n"
                    f"Alternative transfer methods:\n"
                    f"• Use Windows Nearby Sharing from the exported folder\n"
                    f"• Upload to cloud storage (Google Drive, OneDrive, etc.)\n"
                    f"• Email the images to yourself\n\n"
                    f"({failure_count} images failed to copy)" if failure_count > 0 else
                    f"Your images are ready! \n\n"
                    f"Note: If your phone doesn't appear in the export dialog (MTP devices),\n"
                    f"you can copy the images manually:\n"
                    f"1. Open Windows Explorer (your phone is visible there)\n"
                    f"2. Navigate to the exported folder above\n"
                    f"3. Drag and drop images to your phone\n\n"
                    f"Alternative transfer methods:\n"
                    f"• Use Windows Nearby Sharing from the exported folder\n"
                    f"• Upload to cloud storage (Google Drive, OneDrive, etc.)\n"
                    f"• Email the images to yourself"
                ))
                
            except Exception as e:
                logger.error(f"Error exporting portrait images: {e}")
                app.root.after(0, lambda: app._dialog.error(
                    "Export Failed",
                    f"Failed to export portrait images:\n\n{str(e)}"
                ))
                app.root.after(0, lambda: app.status_var.set("Export failed"))
        
        # Start background thread
        threading.Thread(target=_export_thread, daemon=True).start()


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

        # Hide all view canvases first
        app.gallery_canvas.pack_forget()
        app._gallery_scroll.pack_forget()
        app.gallery_fav_canvas.pack_forget()
        app._gallery_fav_scroll.pack_forget()
        app.gallery_styled_canvas.pack_forget()
        app._gallery_styled_scroll.pack_forget()
        app.gallery_manual_canvas.pack_forget()
        app._gallery_manual_scroll.pack_forget()

        # Helper: repack action row showing only the given subset in order
        def _repack(visible):
            for w in app._gallery_action_row_order:
                w.pack_forget()
            for w in visible:
                w.pack(side="left", padx=(0, 6))

        _btn_wallpaper_ref = app._gallery_action_row_order[0]
        _btn_text_ref      = app._gallery_action_row_order[3]
        _btn_delete_ref    = app._gallery_action_row_order[4]
        _btn_export_ref    = app._gallery_action_row_order[5]

        if mode == "Favorites":
            app.gallery_fav_canvas.pack(side='left', fill='both', expand=True)
            app._gallery_fav_scroll.pack(side='right', fill='y')
            # Favorites: Wallpaper | Add Text | Delete | Export Portraits
            _repack([_btn_wallpaper_ref, _btn_text_ref, _btn_delete_ref, _btn_export_ref])
            tag_filter = app.get_active_tag()
            app.load_favorites(tag_filter=tag_filter)
        elif mode == "Styled":
            app.gallery_styled_canvas.pack(side='left', fill='both', expand=True)
            app._gallery_styled_scroll.pack(side='right', fill='y')
            # Styled: Wallpaper | Save to Fav | Delete | Export Portraits  (Apply Style hidden — already styled)
            _repack([_btn_wallpaper_ref, app._btn_save_to_fav, _btn_delete_ref, _btn_export_ref])
            tag_filter = app.get_active_tag()
            app.load_styled(tag_filter=tag_filter)
        elif mode == "Manual":
            app.gallery_manual_canvas.pack(side='left', fill='both', expand=True)
            app._gallery_manual_scroll.pack(side='right', fill='y')
            # Manual: Wallpaper | Save to Fav | Add Text | Delete | Export Portraits
            _repack([_btn_wallpaper_ref, app._btn_save_to_fav, _btn_text_ref, _btn_delete_ref, _btn_export_ref])
            tag_filter = app.get_active_tag()
            app.load_manual(tag_filter=tag_filter)
        elif mode in ["Ratio 16:9", "Ratio 9:16", "Ratio 1:1"]:
            app.gallery_canvas.pack(side='left', fill='both', expand=True)
            app._gallery_scroll.pack(side='right', fill='y')
            # Ratio views: Wallpaper | Save to Fav | Add Text | Delete | Export Portraits
            _repack([_btn_wallpaper_ref, app._btn_save_to_fav, _btn_text_ref, _btn_delete_ref, _btn_export_ref])
            tag_filter = app.get_active_tag()
            # Show loading indicator
            app.status_var.set(f'Loading {mode} images...')
            app.root.update_idletasks()
            # Load in background thread to prevent UI freeze
            import threading
            threading.Thread(target=app.load_gallery_by_ratio, args=(mode, tag_filter), daemon=True).start()
        else:  # Gallery
            app.gallery_canvas.pack(side='left', fill='both', expand=True)
            app._gallery_scroll.pack(side='right', fill='y')
            # Gallery: Wallpaper | Save to Fav | Add Text | Delete | Export Portraits
            _repack([_btn_wallpaper_ref, app._btn_save_to_fav, _btn_text_ref, _btn_delete_ref, _btn_export_ref])
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
            threading.Thread(target=app.load_gallery_by_ratio, args=(view_mode, tag_filter), daemon=True).start()

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


    def _on_tag_var_changed(self, *args):
        """Show/hide delete tag button based on tag selection."""
        app = self.app
        current_tag = app.gallery_tag_var.get()
        if current_tag and current_tag != 'All tags':
            app.delete_tag_btn.pack(side='left', padx=(0, 4))
        else:
            app.delete_tag_btn.pack_forget()


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


    def _populate_visual_grid(self, ui, items, kind):

        app = self.app
        for widget in ui["inner"].winfo_children():

            widget.destroy()



        app.favorite_cards.clear()

        app.favorite_thumb_refs.clear()

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

            tk.Label(
                ui["inner"],
                text=msg,
                bg=pal["panel"], fg=pal["text"], font=app.small_font,
                pady=30,
            ).pack(fill='x', padx=20, pady=30)

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

            ts = item.get("timestamp") or item.get("saved_at", "")

            subtitle = (ts[:19].replace("T", " ") if ts else "")

            meta = subtitle or (path.name[:18] if path else "")



            if path and path.exists():

                try:
                    from PIL import Image, ImageTk
                    img = Image.open(path)
                    img.thumbnail((240, 135), Image.Resampling.LANCZOS)
                    photo = ImageTk.PhotoImage(img)
                    refs.append(photo)
                    thumb = tk.Label(card, image=photo, cursor="hand2", bg=pal["panel"])
                    thumb.image = photo
                    thumb.pack()
                    try:
                        self._fade_in_thumb(thumb, photo, steps=4, interval=35)
                    except Exception:
                        pass
                    thumb.bind("<Button-1>", lambda e, p=path, d=item, u=ui, cidx=card_idx: app._on_fav_card_click(e, p, d, u, cidx))
                    thumb.bind("<Double-Button-1>", lambda e, p=path, d=item, u=ui: app._double_click_visual_item(u, p, d))
                    thumb.bind("<Button-3>", lambda e, p=path: app.show_gallery_context_menu(e, p))
                    pass  # no organize drag binds
                except Exception:
                    tk.Label(card, text="(image error)", cursor="hand2", bg=pal["panel"], fg=pal["text"]).pack()

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

            # Meta label shown below thumbnail or text — used by highlight/organize logic
            name_label = tk.Label(
                card,
                text=meta,
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

            # File size + resolution info
            if path and path.exists():
                try:
                    size_bytes = path.stat().st_size
                    size_str = f"{size_bytes / 1_048_576:.1f} MB" if size_bytes >= 1_048_576 else f"{size_bytes / 1024:.0f} KB"
                    from PIL import Image as _PILImg
                    with _PILImg.open(path) as _im2:
                        w_px, h_px = _im2.size
                    info_text = f"{w_px}×{h_px}  •  {size_str}"
                except Exception:
                    info_text = ""
                info_lbl = tk.Label(card, text=info_text, fg=pal["muted"], font=app.tinyfont,
                                    bg=pal["panel"], anchor="w", justify="left", padx=6, pady=0)
                info_lbl.pack(fill="x")
                info_lbl.bind("<Button-1>", lambda e, p=path, d=item, u=ui, cidx=card_idx: app._on_fav_card_click(e, p, d, u, cidx))

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
            view_mode = app._gallery_view_mode()
            if view_mode == "Gallery":
                app.load_gallery()
            elif view_mode == "Favorites":
                app.load_favorites()
            elif view_mode == "Styled":
                app.load_styled()
            elif view_mode == "Manual":
                app.load_manual()
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

        # Determine effective filter after potential selection change
        effective_tag = app.gallery_tag_var.get()
        tag_filter = effective_tag if effective_tag != 'All tags' else None
        # Special handling for 'Untagged' - pass it as-is to indicate untagged filter
        if effective_tag == 'Untagged':
            tag_filter = 'Untagged'

        # Reload current view
        view_mode = app._gallery_view_mode()
        if view_mode == "Gallery":
            app.load_gallery()
        elif view_mode == "Favorites":
            app.load_favorites()
        elif view_mode == "Styled":
            app.load_styled()
        elif view_mode == "Manual":
            app.load_manual()

        # Show status message
        if status_msg:
            app.status_var.set(status_msg)
        elif tag_filter:
            app.status_var.set(f'{view_mode} filtered by tag: {effective_tag}')
        else:
            app.status_var.set(f'{view_mode} reloaded (no tag filter)')


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
            # Handle variable-length card data (some have 2, 3, or 6 elements)
            card = card_data[0] if isinstance(card_data, (tuple, list)) else card_data
            name_label = card_data[1] if len(card_data) > 1 else None
            tags_label = card_data[2] if len(card_data) > 2 else None
            
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


    def _update_manual_highlight(self, selected_path):
        """Apply selection highlight to the selected manual card."""
        app = self.app
        pal = app.THEMES.get(app.current_theme_name, app.THEMES["darkforest"])
        sel_str = str(selected_path) if selected_path else None

        for path_str, (card, name_label) in app.gallery_manual_cards.items():
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


    def _update_styled_highlight(self, selected_path):
        """Apply selection highlight to the selected styled card."""
        app = self.app
        pal = app.THEMES.get(app.current_theme_name, app.THEMES["darkforest"])
        sel_str = str(selected_path) if selected_path else None

        for path_str, (card, name_label) in app.gallery_styled_cards.items():
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

            app._dialog.error("Filter Error", f"Failed to apply {style_name}: {e}")


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

        import threading

        thread = threading.Thread(target=app._apply_style_thread, args=(style,))

        thread.daemon = True

        thread.start()


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

        import threading

        thread = threading.Thread(target=app._apply_style_thread, args=(style_key,))

        thread.daemon = True

        thread.start()


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

        

        app.gallery_cards[str(img_path)] = (card, name_label, tags_label)


    def delete_selected(self):
        """Delete selected image + tags, with proper tag app.UI refresh."""
        app = self.app
        if not app.selected_gallery_path:
            app._dialog.warning('No Selection', 'Select an image first.')
            return

        if app._dialog.ask('Confirm', f'Delete {app.selected_gallery_path.name}?'):
            delete_image_and_tags(str(app.selected_gallery_path))
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

        # Delete the copied file from favorites/ folder if it exists
        copied_path = target.get("copied_image_path")
        if copied_path:
            try:
                copied_file = Path(copied_path)
                if copied_file.exists() and copied_file.is_file():
                    copied_file.unlink()
            except Exception:
                pass  # Ignore file deletion errors

        updated = [item for item in app.favorites if item is not target]

        if len(updated) == len(app.favorites):

            for i, item in enumerate(app.favorites):

                if item.get("saved_at") == target.get("saved_at") and item.get("prompt") == target.get("prompt"):

                    del app.favorites[i]

                    updated = app.favorites

                    break

        save_json_list(app.FAVORITES_LOG, updated)

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
            app._dialog.error("Wallpaper Error", f"Failed to set wallpaper:\n{e}")


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
                # Check if already favorited by comparing resolved paths
                if any(item.get('copied_image_path') and Path(item.get('copied_image_path')).resolve() == original_resolved for item in existing):
                    app.status_var.set("Image already in favorites.")
                    return

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
                    from PIL import Image as PILImg
                    def _fav_resolution(x):
                        p = _fav_path(x)
                        try:
                            img = PILImg.open(p)
                            res = img.width * img.height
                            img.close()
                            return res
                        except Exception:
                            return 0
                    sorted_favs.sort(key=_fav_resolution, reverse=True)
                except Exception:
                    pass
            elif current_sort == "Resolution Smallest":
                try:
                    from PIL import Image as PILImg
                    def _fav_resolution(x):
                        p = _fav_path(x)
                        if not p:
                            return 0
                        try:
                            with PILImg.open(p) as img:
                                w, h = img.size
                                return w * h
                        except Exception:
                            return 0
                    sorted_favs.sort(key=_fav_resolution, reverse=False)
                except Exception:
                    sorted_favs.sort(key=lambda x: Path(_fav_path(x)).name.lower())
            display_items = sorted_favs

        # Apply tag filter
        if tag_filter:
            def _fav_path(x):
                return x.get("image_path") or x.get("copied_image_path") or ""
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
            from set_wallpaper import MANUAL_DIR, GENERATED_DIR
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

                    from PIL import Image as PILImg

                    def _img_res(path):

                        try:

                            img = PILImg.open(path)

                            res = img.width * img.height

                            img.close()

                            return res

                        except Exception:

                            return 0

                    raw_images.sort(key=_img_res, reverse=True)

                except Exception:

                    raw_images.sort(key=lambda x: str(x.name).lower())


            elif current_sort == "Resolution Smallest":

                # Sort by image resolution (width * height) ascending

                try:

                    from PIL import Image as PILImg

                    def _img_res(path):

                        try:

                            img = PILImg.open(path)

                            res = img.width * img.height

                            img.close()

                            return res

                        except Exception:

                            return 0

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
        app.gallery_canvas.itemconfig("inner_frame", width=max(w, 1))
        for c in range(cols):
            app.gallery_inner.columnconfigure(c, weight=1)

        # Create a lightweight placeholder Frame for every image slot.
        # Placeholders hold gallery_inner at the correct total height so the
        # scrollbar is accurate before any thumbnails are loaded.
        n = len(app.gallery_images)
        if n == 0:
            # Empty-state message for main Gallery view
            pal = app.THEMES.get(app.current_theme_name, app.THEMES["darkforest"])
            tk.Label(
                app.gallery_inner,
                text="No wallpapers yet. Generate or add images to get started.",
                bg=pal["panel"], fg=pal["text"], font=app.small_font,
                pady=30,
            ).grid(row=0, column=0, sticky="ew")
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
            from set_wallpaper import MANUAL_DIR, GENERATED_DIR

            # Define target ratios with tolerance
            target_ratios = {
                "Ratio 16:9": (16/9, 0.1),
                "Ratio 9:16": (9/16, 0.1),
                "Ratio 1:1": (1.0, 0.05)
            }
            target_ratio, tolerance = target_ratios.get(ratio_mode, (16/9, 0.1))

            # Collect images from manual and generated directories
            raw_images = collect_wallpapers([app.MANUAL_DIR, GENERATED_DIR]) or []

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
                except:
                    app._ratio_cache[cache_entry] = False
                    return False

            filtered_images = [img for img in raw_images if matches_ratio(img)]

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
            app.root.after(0, lambda: app._build_ratio_gallery_ui(filtered_images, ratio_mode, tag_filter))

        except Exception as e:
            app.root.after(0, lambda: app.status_var.set(f'Error loading ratio view: {e}'))


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
                    from PIL import Image as PILImg
                    def _manual_res(path):
                        try:
                            with PILImg.open(path) as img:
                                return img.size[0] * img.size[1]
                        except Exception:
                            return 0
                    manual_files.sort(key=_manual_res, reverse=True)
                except Exception:
                    manual_files.sort(key=lambda f: f.name.lower())
            elif current_sort == "Resolution Smallest":
                try:
                    from PIL import Image as PILImg
                    def _manual_res(path):
                        try:
                            with PILImg.open(path) as img:
                                return img.size[0] * img.size[1]
                        except Exception:
                            return 0
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
                tk.Label(
                    app.gallery_manual_inner,
                    text=msg,
                    bg=pal["panel"], fg=pal["text"], font=app.small_font,
                    pady=30,
                ).grid(row=0, column=0, sticky="ew")

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
                    from PIL import Image as PILImg
                    def _styled_res(path):
                        try:
                            with PILImg.open(path) as img:
                                return img.size[0] * img.size[1]
                        except Exception:
                            return 0
                    styled_files.sort(key=_styled_res, reverse=True)
                except Exception:
                    styled_files.sort(key=lambda f: f.name.lower())
            elif current_sort == "Resolution Smallest":
                try:
                    from PIL import Image as PILImg
                    def _styled_res(path):
                        try:
                            with PILImg.open(path) as img:
                                return img.size[0] * img.size[1]
                        except Exception:
                            return 0
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
                tk.Label(
                    app.gallery_styled_inner,
                    text=msg,
                    bg=pal["panel"], fg=pal["text"], font=app.small_font,
                    pady=30,
                ).grid(row=0, column=0, sticky="ew")

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
        ctrl_pressed = (event.state & 0x4) != 0  # Check if Ctrl key is pressed
        app._on_thumbnail_click(path, ctrl_pressed)


    def on_card_drag(self, event, index):
        app = self.app
        pass


    def on_card_drop(self, event, source_index):
        app = self.app
        pass


    def on_fav_resize(self, event):

        """Handle favorites canvas resize — match gallery 3-column behaviour."""

        app = self.app
        canvas_width = event.width

        cols = min(3, max(1, canvas_width // 260))

        app._rebuild_fav_grid(cols)

        app.gallery_fav_canvas.configure(scrollregion=app.gallery_fav_canvas.bbox('all'))

        app.gallery_fav_canvas.itemconfig("fav_inner_frame", width=canvas_width)


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

        """Handle manual canvas resize — match gallery 3-column behaviour."""

        app = self.app
        canvas_width = event.width

        cols = min(3, max(1, canvas_width // 260))

        app._rebuild_manual_grid(cols)

        app.gallery_manual_canvas.configure(scrollregion=app.gallery_manual_canvas.bbox('all'))

        app.gallery_manual_canvas.itemconfig("manual_inner_frame", width=canvas_width)


    def on_organize_toggle(self):
        app = self.app
        pass  # Organize Mode removed


    def on_styled_resize(self, event):

        """Handle styled canvas resize — match gallery 3-column behaviour."""

        app = self.app
        canvas_width = event.width

        cols = min(3, max(1, canvas_width // 260))

        app._rebuild_styled_grid(cols)

        app.gallery_styled_canvas.configure(scrollregion=app.gallery_styled_canvas.bbox('all'))

        app.gallery_styled_canvas.itemconfig("styled_inner_frame", width=canvas_width)


    def open_style_dialog(self):

        """Open the style transfer dialog for the selected image."""

        app = self.app
        if not app.selected_gallery_path:

            app._dialog.warning("No Selection", "Please select an image from the gallery first.")

            return

        

        if not app._ensure_style_transfer():

            app._dialog.error("Style Transfer Not Available", "Style transfer requires OpenCV. Please install it with: pip install opencv-python")

            return

        

        # Create style dialog

        style_dialog = tk.Toplevel(app.root)

        style_dialog.title("Apply Artistic Style")

        style_dialog.geometry("560x780")

        style_dialog.minsize(520, 640)

        style_dialog.transient(app.root)

        style_dialog.grab_set()

        

        # Style selection (packed first → stays at top)

        style_frame = ttk.LabelFrame(style_dialog, text="Apply Artistic Style:", padding=10)

        style_frame.pack(fill="x", padx=10, pady=10)

        

        app.selected_style_var = tk.StringVar(value="original")

        

        # Create radio buttons for styles

        styles = [

            ("original", "Original (no filter)"),

            ("oil_painting", "Oil Painting (thick brushstrokes)"),

            ("watercolor", "Watercolor (soft edges)"),

            ("sketch", "Sketch (line art)"),

            ("line_art", "Line Art (high contrast)"),

            ("comic_book", "Comic Book (bold lines)"),

            ("manga", "Manga (clean lines)"),

            ("sepia", "Sepia (warm brown tones)"),

            ("bw", "B&W (grayscale)"),

            ("vintage", "Vintage (aged look)"),

            ("posterize", "Posterize (reduced colors)"),

            ("emboss", "Emboss (3D relief)"),

            ("edge_enhance", "Edge Enhance (sharpened)"),

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

            new_path = organize_image_into_folder(str(app.selected_gallery_path), folder)

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


    def save_gallery_to_favorites(self):

        """Add selected to favorites by copying to wallpapers/favorites/ folder."""

        app = self.app
        if not app.selected_gallery_path:

            app._dialog.warning('No Selection', 'Select an image first.')

            return

        existing = load_json_list(app.FAVORITES_LOG)

        path_str = str(app.selected_gallery_path)
        original_resolved = app.selected_gallery_path.resolve()
        
        # Check if already favorited by comparing resolved paths
        if any(item.get('copied_image_path') and Path(item.get('copied_image_path')).resolve() == original_resolved for item in existing):

            app.status_var.set(f'Image already in favorites.')

            return

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
                    app._dialog.error('Error', f'Failed to copy image to favorites folder:\n{e}')
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
        app.status_var.set(f'⭐ Saved to favorites: {app.selected_gallery_path.name}')


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

            app._dialog.error("Wallpaper Error", f"Failed to set wallpaper: {e}")


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
            app._dialog.error("Error", f"Failed to set wallpaper:\n{e}")


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
            app._dialog.error("Error", f"Failed to remove tags:\n\n{e}")

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
        
        # Center the dialog
        dialog.update_idletasks()
        x = app.root.winfo_x() + (app.root.winfo_width() // 2) - (dialog.winfo_width() // 2)
        y = app.root.winfo_y() + (app.root.winfo_height() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{x}+{y}")
        
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
            app._dialog.error('Error', 'Selected image(s) no longer exist.')
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

            app._dialog.error("Upscale Failed", f"Could not upscale image.\n{e}")
