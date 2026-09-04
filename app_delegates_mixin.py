"""Delegate surface of FrogPaperApp (roadmap #7 Phase B step 2).

Extracted verbatim from app.py: the thin one/two-line adapter methods
that forward gallery, template, session, preset-UI, slideshow, mode,
token and negative-prompt requests to the modular tab classes
(GalleryTab, PromptTab, SettingsTab and friends).

Contains the first (shadowed) copies of on_fav_resize / _on_minimize /
advance_slideshow exactly as in the original class body - the winning
later definitions keep precedence (app.py body / class order).

All methods are mixed into FrogPaperApp (see app.py), so behaviour is
unchanged: state still lives on self / self.app and every caller keeps
working untouched.
"""

import logging
from pathlib import Path

import tkinter as tk
from tkinter import ttk, simpledialog

from app_prompt_data import (
    DEFAULT_NEGATIVE_PROMPT,
    DEFAULT_PROMPT_MODE_LABEL,
    DEFAULT_PROMPT_MODE_VALUE,
    PROMPT_MODE_OPTIONS,
    PROMPT_MODE_VALUE_TO_LABEL,
    STYLE_MODES,
)
from utils import load_config, save_config

logger = logging.getLogger(__name__)



class FrogPaperAppDelegatesMixin:
    """Mixed into FrogPaperApp (see app.py); methods are verbatim."""

    def _build_gallery_tab(self, parent):
        return self._gallery_tab._build_gallery_tab(parent)




    # toggle_gallery_sort removed - dropdown handles all sorting



    def sort_gallery(self, event=None):
        return self._gallery_tab.sort_gallery(event)


    def _do_sort_gallery_reload(self):
        return self._gallery_tab._do_sort_gallery_reload()




    def _on_tag_selected(self):
        return self._gallery_tab._on_tag_selected()


    def apply_gallery_filter(self):
        return self._gallery_tab.apply_gallery_filter()



    def on_gallery_resize(self, event):
        return self._gallery_tab.on_gallery_resize(event)




    def refresh_grid_layout(self, cols):
        return self._gallery_tab.refresh_grid_layout(cols)




    # ------------------------------------------------------------------
    # Lazy / virtual gallery rendering
    # ------------------------------------------------------------------
    #
    # Strategy: every image index always occupies a grid slot in gallery_inner,
    # either as a real thumbnail card or as a fixed-size placeholder Frame.
    # This keeps gallery_inner's height correct so the canvas scrollregion and
    # scrollbar always match reality.
    #
    # _render_visible_cards() "promotes" placeholders → real cards for the
    # visible viewport (+1 row buffer) and "demotes" real cards → placeholders
    # outside that range.  thumb_cache means re-promotion is instant.
    # ------------------------------------------------------------------

    def _gallery_visible_range(self):
        return self._gallery_tab._gallery_visible_range()


    def _make_gallery_placeholder(self, idx, row, col):
        return self._gallery_tab._make_gallery_placeholder(idx, row, col)


    def _render_visible_cards(self):
        return self._gallery_tab._render_visible_cards()


    def _on_gallery_scroll(self, *_):
        return self._gallery_tab._on_gallery_scroll(*_)


    def _gallery_view_mode(self):
        return self._gallery_tab._gallery_view_mode()


    def get_active_tag(self):
        return self._gallery_tab.get_active_tag()


    def _gallery_set_wallpaper(self):
        return self._gallery_tab._gallery_set_wallpaper()


    def _gallery_save_to_favorites(self):
        return self._gallery_tab._gallery_save_to_favorites()


    def _gallery_apply_theme(self, style_key):
        return self._gallery_tab._gallery_apply_theme(style_key)


    def _gallery_add_text(self):
        return self._gallery_tab._gallery_add_text()


    def _gallery_tag_selected(self):
        return self._gallery_tab._gallery_tag_selected()


    def _gallery_delete(self):
        return self._gallery_tab._gallery_delete()

    def _gallery_export_portraits(self):
        return self._gallery_tab._gallery_export_portraits()

    def _delete_styled_image(self):
        return self._gallery_tab._delete_styled_image()

    def _copy_prompt_to_clipboard(self):
        return self._gallery_tab._copy_prompt_to_clipboard()


    def _open_wallpapers_folder(self):
        return self._gallery_tab._open_wallpapers_folder()


    def _on_gallery_view_changed(self):
        return self._gallery_tab._on_gallery_view_changed()


    def load_gallery(self):
        return self._gallery_tab.load_gallery()




    def create_gallery_card(self, img_path, row, col, index):
        return self._gallery_tab.create_gallery_card(img_path, row, col, index)




    def on_card_click(self, event, path, index):
        return self._gallery_tab.on_card_click(event, path, index)


    def show_gallery_context_menu(self, event, path):
        return self._gallery_tab.show_gallery_context_menu(event, path)


    def load_prompt_from_history(self, image_path):
        return self._gallery_tab.load_prompt_from_history(image_path)


    def copy_to_clipboard(self, text):
        return self._gallery_tab.copy_to_clipboard(text)




    def on_card_drag(self, event, index):
        return self._gallery_tab.on_card_drag(event, index)


    def on_card_drop(self, event, source_index):
        return self._gallery_tab.on_card_drop(event, source_index)




    def _widget_to_card_index(self, widget):
        return self._gallery_tab._widget_to_card_index(widget)


    def _highlight_organize_source(self, picked_index, hover_index):
        return self._gallery_tab._highlight_organize_source(picked_index, hover_index=hover_index)




    def apply_style_transfer_filter(self, style_key):
        return self._gallery_tab.apply_style_transfer_filter(style_key)




    def apply_artistic_filter(self, style_name):
        return self._gallery_tab.apply_artistic_filter(style_name)




    def _rebuild_fav_grid(self, cols):
        return self._gallery_tab._rebuild_fav_grid(cols)




    def on_styled_resize(self, event):
        return self._gallery_tab.on_styled_resize(event)




    def _rebuild_styled_grid(self, cols):
        return self._gallery_tab._rebuild_styled_grid(cols)




    def on_manual_resize(self, event):
        return self._gallery_tab.on_manual_resize(event)

    def on_cloud_resize(self, event):
        return self._gallery_tab.on_cloud_resize(event)

    def on_fav_resize(self, event):
        return self._gallery_tab.on_fav_resize(event)

    def _rebuild_manual_grid(self, cols):
        return self._gallery_tab._rebuild_manual_grid(cols)





    def on_organize_toggle(self):
        return self._gallery_tab.on_organize_toggle()


    def _on_thumbnail_click(self, path, ctrl_pressed=False):
        return self._gallery_tab._on_thumbnail_click(path, ctrl_pressed)


    def _update_gallery_highlight(self, selected_path):
        return self._gallery_tab._update_gallery_highlight(selected_path)


    def _update_gallery_highlight_multi(self):
        return self._gallery_tab._update_gallery_highlight_multi()


    def set_gallery_image_as_wallpaper(self, path):
        return self._gallery_tab.set_gallery_image_as_wallpaper(path)




    def set_gallery_selection(self):
        return self._gallery_tab.set_gallery_selection()




    def save_gallery_to_favorites(self):
        return self._gallery_tab.save_gallery_to_favorites()




    def _resolve_related_paths(self, path):
        return self._gallery_tab._resolve_related_paths(path)


    def _propagate_tags_to_related(self, path, tags):
        return self._gallery_tab._propagate_tags_to_related(path, tags)


    def tag_gallery_image(self):
        return self._gallery_tab.tag_gallery_image()




    def organize_gallery_image(self):
        return self._gallery_tab.organize_gallery_image()




    def delete_selected(self):
        return self._gallery_tab.delete_selected()




    def _refresh_tag_ui(self, status_msg=None, keep_selection=True):
        return self._gallery_tab._refresh_tag_ui(status_msg, keep_selection)


    def _refresh_gallery_tag_filter(self):
        return self._gallery_tab._refresh_gallery_tag_filter()


        

    def clear_image(self):
        return self._gallery_tab.clear_image()


    def open_style_dialog(self):
        return self._gallery_tab.open_style_dialog()


    

    def apply_selected_style(self, dialog):
        return self._gallery_tab.apply_selected_style(dialog)


    

    def _apply_style_thread(self, style):
        return self._gallery_tab._apply_style_thread(style)


    

    def _style_applied_success(self, styled_path, style):
        return self._gallery_tab._style_applied_success(styled_path, style)




    def toggle_fullscreen(self, event=None):
        return self._gallery_tab.toggle_fullscreen(event)


    def _slideshow_prev(self):
        """Go to previous wallpaper in slideshow history."""
        self.slideshow.prev_wallpaper()

    def _slideshow_play(self):
        """Start the slideshow."""
        self.slideshow.start()

    def _slideshow_pause(self):
        """Pause the slideshow."""
        self.slideshow.pause()

    def _slideshow_next(self):
        """Advance to next wallpaper."""
        self.advance_slideshow()

    def _slideshow_stop(self):
        """Stop the slideshow."""
        self.slideshow.stop()


    def _style_applied_failed(self, style):
        return self._gallery_tab._style_applied_failed(style)


    def _style_applied_error(self, error):
        return self._gallery_tab._style_applied_error(error)

    def _build_demoted_theme_builder(self, parent):
        return self._prompt_tab._build_demoted_theme_builder(parent)


    def _build_theme_builder_panel(self, parent, assign_refs, title, refs):
        return self._prompt_tab._build_theme_builder_panel(parent, assign_refs=assign_refs, title=title, refs=refs)


    def build_prompt_builder_tab(self, parent):
        return self._prompt_tab.build_prompt_builder_tab(parent)


    def update_prompt_builder_mode(self):
        return self._prompt_tab.update_prompt_builder_mode()


    def _on_notebook_tab_changed(self, event=None):
        return self._prompt_tab._on_notebook_tab_changed(event)


    def _open_settings_window(self):
        return self._prompt_tab._open_settings_window()


    def _open_recipe_window(self):
        return self._prompt_tab._open_recipe_window()


    def _toggle_recipe_library(self):
        return self._prompt_tab._toggle_recipe_library()


    def _build_templates_tab(self, parent):
        return self._prompt_tab._build_templates_tab(parent)


    def ontemplateselected(self, event=None):
        return self._prompt_tab.ontemplateselected(event)


    def load_selected_recipe_into_quick_build(self):
        return self._prompt_tab.load_selected_recipe_into_quick_build()


    def load_selected_prompt_from_library(self):
        return self._prompt_tab.load_selected_prompt_from_library()


    def loadtemplate(self):
        return self._prompt_tab.loadtemplate()


    def _load_recipe(self, recipe):
        return self._prompt_tab._load_recipe(recipe)


    def _load_template_legacy(self, template):
        return self._prompt_tab._load_template_legacy(template)


    def generatefromtemplate(self):
        return self._prompt_tab.generatefromtemplate()


    def _generate_from_recipe(self, recipe):
        return self._prompt_tab._generate_from_recipe(recipe)


    def _generate_from_template_legacy(self, template):
        return self._prompt_tab._generate_from_template_legacy(template)


    def refreshtemplatelist(self):
        return self._prompt_tab.refreshtemplatelist()


    def _refresh_template_library(self):
        return self._prompt_tab._refresh_template_library()


    def _update_template_detail_label(self):
        return self._prompt_tab._update_template_detail_label()


    def resettemplatevariables(self):
        return self._prompt_tab.resettemplatevariables()


    def _generate_template_name_from_prompt(self, prompt):
        return self._prompt_tab._generate_template_name_from_prompt(prompt)


    def _generate_template_description(self):
        return self._prompt_tab._generate_template_description()


    def save_as_template(self):
        return self._prompt_tab.save_as_template()


    def _save_template_dialog(self, name, description, dialog):
        return self._prompt_tab._save_template_dialog(name, description, dialog)




    # ── Working Session save / load ──────────────────────────────────────────

    def _collect_session_state(self):
        return self._session_mgr._collect_session_state()


    def _restore_session_state(self, state):
        return self._session_mgr._restore_session_state(state)


    def save_session(self):
        return self._session_mgr.save_session()


    def load_session(self):
        return self._session_mgr.load_session()


    def _ensure_recipe_manager(self):
        return self._prompt_tab._ensure_recipe_manager()


    def save_as_quick_recipe(self):
        return self._prompt_tab.save_as_quick_recipe()


    def _save_quick_recipe_dialog(self, name, description, dialog, subject, style, lighting, mood, color, atmosphere, mode, subject_lock, negative_prompt):
        return self._prompt_tab._save_quick_recipe_dialog(name, description, dialog, subject, style, lighting, mood, color, atmosphere, mode, subject_lock, negative_prompt)


    def _generate_quick_recipe_name(self, subject, style, mood, atmosphere=None):
        return self._prompt_tab._generate_quick_recipe_name(subject, style, mood, atmosphere)


    def _generate_quick_recipe_description(self, subject, style, mood, lighting, atmosphere=None):
        return self._prompt_tab._generate_quick_recipe_description(subject, style, mood, lighting, atmosphere)


    def load_quick_recipe(self):
        return self._prompt_tab.load_quick_recipe()


    def _load_quick_recipe_to_theme_builder(self, recipe):
        return self._prompt_tab._load_quick_recipe_to_theme_builder(recipe)


    def delete_quick_recipe(self):
        return self._prompt_tab.delete_quick_recipe()


    def duplicate_template(self):
        return self._prompt_tab.duplicate_template()


    def import_templates(self):
        return self._prompt_tab.import_templates()

    
    def export_templates(self):
        return self._prompt_tab.export_templates()


    def edit_template(self):
        return self._prompt_tab.edit_template()


    def _open_template_edit_dialog(self, source, is_recipe):
        return self._prompt_tab._open_template_edit_dialog(source, is_recipe=is_recipe)


    def delete_template(self):
        return self._prompt_tab.delete_template()


    

    def export_template(self):
        return self._prompt_tab.export_template()


    def import_template(self):
        return self._prompt_tab.import_template()


    

    # _on_template_search and _clear_template_search removed —
    # template_search_var widget was never added to the UI.











    def previewdoubleclick(self, event=None):
        return self._prompt_tab.previewdoubleclick(event)





    def _build_settings_tab(self, parent):
        result = self._settings_tab._build_settings_tab(parent)
        # Inject fullscreen pause checkbox after settings UI is built
        self.root.after(500, lambda: self._add_fullscreen_setting(parent))
        return result




    def _on_model_choice_changed(self, event=None):
        return self._settings_tab._on_model_choice_changed(event)

    def _on_provider_changed(self, event=None):
        return self._settings_tab._on_provider_changed(event)

    def _update_provider_description(self):
        return self._settings_tab._update_provider_description()




    def setup_scheduler_from_gui(self):
        return self._settings_tab.setup_scheduler_from_gui()


    def _populate_visual_grid(self, ui, items, kind):
        return self._gallery_tab._populate_visual_grid(ui, items, kind)


    def _on_fav_card_click(self, event, path, data, ui, index):
        return self._gallery_tab._on_fav_card_click(event, path, data, ui, index)


    def _on_fav_card_drag(self, event, index):
        return self._gallery_tab._on_fav_card_drag(event, index)


    def _on_fav_card_drop(self, event, source_index):
        return self._gallery_tab._on_fav_card_drop(event, source_index)


    def _fav_widget_to_card_index(self, widget):
        return self._gallery_tab._fav_widget_to_card_index(widget)


    def _highlight_fav_organize(self, picked_index, hover_index):
        return self._gallery_tab._highlight_fav_organize(picked_index, hover_index=hover_index)


    def _update_fav_card_highlight(self, selected_item):
        return self._gallery_tab._update_fav_card_highlight(selected_item)


    def _refresh_fav_card_highlights(self):
        return self._gallery_tab._refresh_fav_card_highlights()


    def _select_visual_item(self, ui, path, data):
        return self._gallery_tab._select_visual_item(ui, path, data)


    def _double_click_visual_item(self, ui, path, data):
        return self._gallery_tab._double_click_visual_item(ui, path, data)


    def double_click_set_wallpaper(self, path):
        return self._gallery_tab.double_click_set_wallpaper(path)


    def random_theme(self):
        return self._gallery_tab.random_theme()




    def upscale_selected(self):
        return self._gallery_tab.upscale_selected()








    def delete_selected_favorite(self):
        return self._gallery_tab.delete_selected_favorite()


    def _canonical_mode_value(self, value=None):
        raw = (value or "").strip()
        if not raw:
            # Read mode_var from PB Quick Build refs (primary source).
            # Read directly to avoid circular calls with get_active_mode_label.
            refs = self._get_pb_quick_refs()
            if refs and "mode_var" in refs:
                try:
                    raw = refs["mode_var"].get().strip()
                except Exception:
                    raw = ""
        if not raw:
            return DEFAULT_PROMPT_MODE_VALUE
        lower = raw.lower()
        if lower in STYLE_MODES:
            return lower
        if raw in STYLE_MODES:
            return raw
        for label, canonical in PROMPT_MODE_OPTIONS:
            if lower == label.lower():
                return canonical
        hyphenated = lower.replace(" ", "-")
        if hyphenated in STYLE_MODES:
            return hyphenated
        return DEFAULT_PROMPT_MODE_VALUE

    def current_mode(self):

        return self.get_active_mode()



    def _mode_label(self, mode_value=None):
        canonical = self._canonical_mode_value(mode_value)
        return PROMPT_MODE_VALUE_TO_LABEL.get(canonical, DEFAULT_PROMPT_MODE_LABEL)

    def _set_mode_display(self, mode_value):
        # Retained for any call sites not yet migrated; delegates to set_active_mode.
        self.set_active_mode(mode_value)



    def format_token_preview(self):
        return self._settings_tab.format_token_preview()




    def refresh_token_status(self):
        return self._settings_tab.refresh_token_status()




    def resolved_model_id(self):
        return self._settings_tab.resolved_model_id()




    def save_settings(self):
        result = self._settings_tab.save_settings()
        # Save fullscreen pause setting
        config = load_config()
        config['slideshow_pause_on_fullscreen'] = bool(self.slideshow_pause_on_fullscreen_var.get())
        
        # Save cloud account settings
        if hasattr(self, 'auto_backup_var'):
            config['auto_backup_enabled'] = bool(self.auto_backup_var.get())
        # Parse and validate backup time
        if hasattr(self, 'auto_backup_hour_var'):
            try:
                parts = self.auto_backup_hour_var.get().strip().split(':')
                h = int(parts[0]) % 24
                m = int(parts[1]) % 60 if len(parts) > 1 else 0
                config['auto_backup_hour'] = h
                config['auto_backup_minute'] = m
            except (ValueError, IndexError):
                pass  # keep previous values
        if hasattr(self, 'sync_scope_var'):
            config['sync_scope'] = self.sync_scope_var.get()
        
        save_config(config)
        
        # Restart backup scheduler if setting changed
        self._setup_auto_backup()
        
        return result




    def load_slideshow_settings(self):
        result = self._settings_tab.load_slideshow_settings()
        # Load fullscreen pause setting and start watcher if enabled
        config = load_config()
        self.slideshow_pause_on_fullscreen_var.set(bool(config.get('slideshow_pause_on_fullscreen', False)))
        if self.slideshow_pause_on_fullscreen_var.get():
            self._start_fullscreen_watcher()
        return result




    def sync_slideshow_state(self):
        return self._settings_tab.sync_slideshow_state()



    def on_slideshow_toggle(self):
        return self._settings_tab.on_slideshow_toggle()




    def slideshow_start_click(self):
        return self._settings_tab.slideshow_start_click()




    def slideshow_stop_click(self):
        return self._settings_tab.slideshow_stop_click()




    def slideshow_next_now(self):
        return self._settings_tab.slideshow_next_now()




    def slideshow_prev_now(self):
        return self._settings_tab.slideshow_prev_now()




    def slideshow_pause_click(self):
        return self._settings_tab.slideshow_pause_click()




    def slideshow_preview_sources(self):
        return self._settings_tab.slideshow_preview_sources()




    def update_slideshow_status(self):
        return self._settings_tab.update_slideshow_status()




    def _on_dimension_preset_changed(self, event=None):
        return self._settings_tab._on_dimension_preset_changed(event)


    def _set_dimensions_from_string(self, dimensions_str):
        return self._settings_tab._set_dimensions_from_string(dimensions_str)




    def get_current_dimensions(self):
        return self._settings_tab.get_current_dimensions()




    def _on_remember_settings_changed(self, event=None):
        return self._settings_tab._on_remember_settings_changed(event)




    def load_remembered_settings(self):
        return self._settings_tab.load_remembered_settings()




    def add_user_mapping(self):
        return self._settings_tab.add_user_mapping()




    def remove_user_mapping(self):
        return self._settings_tab.remove_user_mapping()




    def save_current_settings_for_memory(self):
        return self._session_mgr.save_current_settings_for_memory()




    def _on_token_changed(self, event=None):
        return self._settings_tab._on_token_changed(event)


    def toggle_token_visibility(self):
        return self._settings_tab.toggle_token_visibility()




    def subject_lock_enabled(self):
        return self._prompt_tab.subject_lock_enabled()




    def _is_prompt_builder_tab_selected(self):
        return self._prompt_tab._is_prompt_builder_tab_selected()


    def _is_prompt_builder_quick_active(self):
        return self._prompt_tab._is_prompt_builder_quick_active()


    def _get_pb_quick_refs(self):
        return self._prompt_tab._get_pb_quick_refs()


    def _get_active_quick_refs(self):
        return self._prompt_tab._get_active_quick_refs()


    def _get_active_widget(self, name):
        return self._prompt_tab._get_active_widget(name)


    def _get_active_text(self, name, default=''):
        return self._prompt_tab._get_active_text(name, default)


    def get_active_subject(self):
        return self._prompt_tab.get_active_subject()


    def get_active_style(self):
        return self._prompt_tab.get_active_style()


    def get_active_lighting(self):
        return self._prompt_tab.get_active_lighting()


    def get_active_mood(self):
        return self._prompt_tab.get_active_mood()


    def get_active_color(self):
        return self._prompt_tab.get_active_color()


    def get_active_setting(self):
        return self._prompt_tab.get_active_setting()


    def set_active_setting(self, value):
        return self._prompt_tab.set_active_setting(value)


    def get_active_atmosphere(self):
        return self._prompt_tab.get_active_atmosphere()


    def get_active_mode_label(self):
        return self._prompt_tab.get_active_mode_label()


    def get_active_mode(self):
        return self._canonical_mode_value(self.get_active_mode_label())

    def get_active_subject_lock(self):
        return self._prompt_tab.get_active_subject_lock()


    def get_active_negative_prompt(self):
        # The var always mirrors the final Text widget content
        return self.negative_prompt_var.get().strip() or DEFAULT_NEGATIVE_PROMPT

    # ── Negative Prompt Builder methods ──────────────────────────────────

    def _rebuild_neg_combined(self, *_args):
        """Rebuild the final combined negative prompt from selected presets + custom negatives + custom terms."""
        if self._neg_manual_edit:
            return  # user is manually editing; don't overwrite
        parts = []
        # 1. Preset negatives (from checkboxes)
        for key, dname, desc, negs, term_count in self._neg_preset_info:
            if self._neg_preset_vars[key].get():
                parts.append(negs)
        # 2. Custom negatives (saved, toggleable)
        for term, var in self._cn_vars.items():
            if var.get():
                parts.append(term)
        # 3. One-off custom terms entry
        custom = self._neg_custom_var.get().strip()
        if custom:
            parts.append(custom)
        # Deduplicate
        seen = set()
        unique = []
        for raw in (", ".join(parts)).split(","):
            t = raw.strip()
            if t and t.lower() not in seen:
                unique.append(t)
                seen.add(t.lower())
        combined = ", ".join(unique)
        # Update Text widget and StringVar (suppress the <KeyRelease> handler)
        self._neg_final_text.config(state="normal")
        self._neg_final_text.delete("1.0", tk.END)
        self._neg_final_text.insert("1.0", combined)
        self.negative_prompt_var.set(combined)
        # Update term count
        count = len(unique)
        self._neg_term_count_var.set(f"{count} term{'s' if count != 1 else ''}")

    def _on_neg_final_edited(self, event=None):
        """User typed in the final Text widget — enter manual-edit mode."""
        self._neg_manual_edit = True
        text = self._neg_final_text.get("1.0", tk.END).strip()
        self.negative_prompt_var.set(text)
        count = len([t for t in text.split(",") if t.strip()])
        self._neg_term_count_var.set(f"{count} term{'s' if count != 1 else ''} (edited)")

    def _reset_neg_combined(self):
        """Exit manual-edit mode and rebuild from presets + custom."""
        self._neg_manual_edit = False
        self._rebuild_neg_combined()

    # ── Custom Negatives UI ─────────────────────────────────────────────────

    def _rebuild_custom_neg_ui(self):
        """Rebuild the custom negatives checkbox list from saved data."""
        from negative_manager import load_custom_negatives

        # Clear existing
        for widget in self._cn_frame.winfo_children():
            widget.destroy()
        self._cn_vars.clear()
        self._cn_widgets.clear()

        terms = load_custom_negatives()
        if not terms:
            # Show a subtle placeholder
            ph = tk.Label(self._cn_frame, text="No saved terms yet", fg="gray",
                          anchor="w")
            ph.configure(font=self.small_font)
            ph.pack(fill="x")
            self._cn_widgets.append((ph, ""))
            return

        for entry in terms:
            term = entry.get("term", "")
            enabled = entry.get("enabled", True)
            row = ttk.Frame(self._cn_frame)
            row.pack(fill="x", pady=(0, 1))

            var = tk.BooleanVar(value=enabled)
            self._cn_vars[term] = var

            cb = ttk.Checkbutton(row, text=term, variable=var,
                                  command=self._on_custom_neg_toggled)
            cb.pack(side="left")

            # Small × button to remove
            x_btn = tk.Label(row, text="×", fg="gray", cursor="hand2")
            x_btn.configure(font=self.small_font)
            x_btn.pack(side="right", padx=(2, 0))
            x_btn.bind("<Button-1>", lambda e, t=term: self._remove_custom_negative(t))
            x_btn.bind("<Enter>", lambda e, lbl=x_btn: lbl.configure(fg="#ff6666"))
            x_btn.bind("<Leave>", lambda e, lbl=x_btn: lbl.configure(fg="gray"))

            self._cn_widgets.append((row, term))

    def _add_custom_negative(self):
        """Prompt user to add a new custom negative term."""
        term = simpledialog.askstring("Add Custom Negative",
                                      "Enter a negative term to save:",
                                      parent=self.root)
        if not term or not term.strip():
            return
        from negative_manager import add_custom_negative
        add_custom_negative(term.strip())
        self._rebuild_custom_neg_ui()
        self._neg_manual_edit = False
        self._rebuild_neg_combined()

    def _remove_custom_negative(self, term):
        """Remove a custom negative term and refresh."""
        from negative_manager import remove_custom_negative
        remove_custom_negative(term)
        self._rebuild_custom_neg_ui()
        self._neg_manual_edit = False
        self._rebuild_neg_combined()

    def _on_custom_neg_toggled(self):
        """Handle checkbox toggle — persist the new state and rebuild preview."""
        from negative_manager import set_custom_negative_enabled
        for term, var in self._cn_vars.items():
            set_custom_negative_enabled(term, var.get())
        self._neg_manual_edit = False
        self._rebuild_neg_combined()

    # ── Active-source setters ────────────────────────────────────────────────

    def _set_active_entry(self, name, value):
        return self._prompt_tab._set_active_entry(name, value)


    def _set_active_var(self, name, value):
        return self._prompt_tab._set_active_var(name, value)


    def set_active_subject(self, value):
        return self._prompt_tab.set_active_subject(value)


    def set_active_style(self, value):
        return self._prompt_tab.set_active_style(value)


    def set_active_lighting(self, value):
        return self._prompt_tab.set_active_lighting(value)


    def set_active_mood(self, value):
        return self._prompt_tab.set_active_mood(value)


    def set_active_color(self, value):
        return self._prompt_tab.set_active_color(value)


    def set_active_atmosphere(self, value):
        return self._prompt_tab.set_active_atmosphere(value)


    def set_active_mode(self, mode_value):
        return self._prompt_tab.set_active_mode(mode_value)


    def set_active_subject_lock(self, value):
        return self._prompt_tab.set_active_subject_lock(value)


    def set_active_negative_prompt(self, value):
        return self._prompt_tab.set_active_negative_prompt(value)


    # ────────────────────────────────────────────────────────────────────────

    def update_mode_badge(self, mode=None):
        return self._prompt_tab.update_mode_badge(mode)




    def get_negative_prompt(self):
        return self._prompt_tab.get_negative_prompt()




    def apply_negative_prompt_to_prompts(self):
        return self._prompt_tab.apply_negative_prompt_to_prompts()


    def load_favorites(self, tag_filter=None):
        return self._gallery_tab.load_favorites(tag_filter=tag_filter)




    def load_styled(self, tag_filter=None):
        return self._gallery_tab.load_styled(tag_filter=tag_filter)




    def _create_styled_card(self, img_path, index, pal, border):
        return self._gallery_tab._create_styled_card(img_path, index, pal, border)




    def load_manual(self, tag_filter=None):
        return self._gallery_tab.load_manual(tag_filter=tag_filter)


    def load_gallery_by_ratio(self, ratio_mode, tag_filter=None):
        return self._gallery_tab.load_gallery_by_ratio(ratio_mode, tag_filter)


    def _build_ratio_gallery_ui(self, filtered_images, ratio_mode, tag_filter):
        return self._gallery_tab._build_ratio_gallery_ui(filtered_images, ratio_mode, tag_filter)




    def _create_manual_card(self, img_path, index, pal, border):
        return self._gallery_tab._create_manual_card(img_path, index, pal, border)




    def _select_manual_image(self, path):
        return self._gallery_tab._select_manual_image(path)


    def _update_manual_highlight(self, selected_path):
        return self._gallery_tab._update_manual_highlight(selected_path)




    def _select_styled_image(self, path):
        return self._gallery_tab._select_styled_image(path)


    def _update_styled_highlight(self, selected_path):
        return self._gallery_tab._update_styled_highlight(selected_path)




    def favorite_current_prompt(self):
        return self._gallery_tab.favorite_current_prompt()




    def set_selected_favorite_as_wallpaper(self):
        return self._gallery_tab.set_selected_favorite_as_wallpaper()


    def load_image_preview(self, image_path):

            self.show_preview_in_left_panel(image_path, f"Generated image: {Path(image_path).name}")
