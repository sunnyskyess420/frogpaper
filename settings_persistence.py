"""Settings persistence methods for the Settings tab (roadmap #7 Phase A).

Hosts ``save_settings`` (config write-back + side effects), remembered
settings loading, user mapping management and the scheduler setup
bridge.  Mixed into ``SettingsTab``.
"""

from utils import load_config, save_config, get_huggingface_token


class SettingsPersistenceMixin:
    """Config save/load and mapping methods for SettingsTab."""

    def save_settings(self):
        """Save all settings to config file."""
        app = self.app
        config = load_config()

        # Theme
        display_name = app.theme_var.get()
        config["app_theme"] = app.THEME_INTERNAL_NAMES.get(display_name, "darkforest")

        # Dimensions & model
        config["dimensions"] = self.get_current_dimensions()
        config["model_id"] = self.resolved_model_id() or "flux"
        config["provider"] = app.provider_var.get().strip()

        # Cloudflare (dynamically created when Cloudflare provider is selected)
        if hasattr(app, 'cloudflare_key_var'):
            cf_token = app.cloudflare_key_var.get().strip()
            if cf_token:
                config["cloudflare_token"] = cf_token
            else:
                config.pop("cloudflare_token", None)
        if hasattr(app, 'cloudflare_account_id_var'):
            cf_account_id = app.cloudflare_account_id_var.get().strip()
            if cf_account_id:
                config["cloudflare_account_id"] = cf_account_id
            else:
                config.pop("cloudflare_account_id", None)

        # Slideshow
        config['slideshow_enabled'] = bool(app.slideshow_enabled_var.get())
        config['slideshow_interval'] = int(app.slideshow_interval_var.get() or 60)
        source_value = app.slideshow_source_var.get().strip()
        if source_value == 'both':
            source_value = 'all'
        config['slideshow_source'] = app.SLIDESHOW_LABEL_TO_VALUE.get(source_value, source_value.lower()) or 'all'
        config['slideshow_order'] = app.slideshow_order_var.get()
        config['slideshow_skip_duplicates'] = bool(app.slideshow_skip_duplicates_var.get())

        # Startup & tray
        config["remember_settings"] = bool(app.remember_settings_var.get())
        config["auto_generate_on_startup"] = bool(app.auto_generate_on_startup_var.get())
        config["startup_subject"] = app.startup_subject_var.get().strip() or "frog"
        config['minimize_to_tray'] = bool(app.minimize_to_tray_enabled)

        # HuggingFace token (dynamically created when HF provider is selected)
        if hasattr(app, 'hugging_key_var'):
            token = app.hugging_key_var.get().strip()
            if token:
                config["huggingface_token"] = token
            else:
                config.pop("huggingface_token", None)
        elif get_huggingface_token():
            # Token exists from env var but HF provider not currently selected
            pass  # already stored from env, don't overwrite

        # Remembered settings
        if app.remember_settings_var.get():
            config["last_style_mode"] = app.get_active_mode()
            config["last_subject"] = app.get_active_subject()
            config["last_setting"] = app.get_active_setting()
            config["last_style"] = app.get_active_style()
            config["last_lighting"] = app.get_active_lighting()
            config["last_mood"] = app.get_active_mood()
            config["last_color"] = app.get_active_color()
            config["last_atmosphere"] = app.get_active_atmosphere()
            config["last_subject_lock"] = app.get_active_subject_lock()

        # Negative prompt selections
        neg_preset_selections = {}
        if hasattr(app, '_neg_preset_vars'):
            for key, var in app._neg_preset_vars.items():
                if hasattr(var, 'get'):
                    try:
                        neg_preset_selections[key] = var.get()
                    except Exception:
                        neg_preset_selections[key] = False
        neg_custom_terms = ""
        if hasattr(app, '_neg_custom_var'):
            if hasattr(app._neg_custom_var, 'get'):
                try:
                    neg_custom_terms = app._neg_custom_var.get()
                except Exception:
                    neg_custom_terms = ""
        config["last_neg_preset_selections"] = neg_preset_selections
        config["last_neg_custom_terms"] = neg_custom_terms

        # Wallpaper format
        config['wallpaper_format'] = app.wallpaper_format_var.get()
        config['wallpaper_quality'] = app.wallpaper_quality_var.get()

        # Scheduler settings — task creation is handled by setup_scheduler_from_gui()
        # via setup_scheduler.create_task(); no separate config keys to save here.

        save_config(config)
        app.status_var.set("Settings saved.")
        self.sync_slideshow_state()
        try:
            app._dialog.info("Settings", "Settings saved successfully.")
        except Exception:
            pass

    def setup_scheduler_from_gui(self):
        """Create a scheduled task for auto-wallpaper."""
        app = self.app
        try:
            from setup_scheduler import create_task
            ok = create_task()
            if ok:
                app._dialog.info("Task Scheduler", "Morning auto-wallpaper task created successfully.")
                app.status_var.set("Task Scheduler setup complete.")
            else:
                app._dialog.warning("Task Scheduler", "Task setup did not complete successfully.")
                app.status_var.set("Task Scheduler setup may have failed.")
        except Exception as e:
            app._dialog.error("Scheduler Error", "Could not create the scheduled task. Make sure FrogPaper is running as Administrator, or set up the task manually in Windows Task Scheduler.")
            app.status_var.set("Task Scheduler setup failed.")


    def _on_remember_settings_changed(self, event=None):
        """Handle remember-settings checkbox toggle."""
        pass

    def load_remembered_settings(self):
        """Load previously remembered settings from config."""
        app = self.app
        config = load_config()
        if hasattr(app, 'wallpaper_format_var'):
            app.wallpaper_format_var.set(config.get('wallpaper_format', 'PNG'))
        if hasattr(app, 'wallpaper_quality_var'):
            app.wallpaper_quality_var.set(config.get('wallpaper_quality', 'High'))
        neg_preset_selections = config.get("last_neg_preset_selections", {})
        neg_custom_terms = config.get("last_neg_custom_terms", "")
        if neg_preset_selections and hasattr(app, '_neg_preset_vars'):
            for key, selected in neg_preset_selections.items():
                if key in app._neg_preset_vars:
                    if hasattr(app._neg_preset_vars[key], 'set'):
                        try:
                            app._neg_preset_vars[key].set(selected)
                        except Exception:
                            pass
        if neg_custom_terms and hasattr(app, '_neg_custom_var'):
            if hasattr(app._neg_custom_var, 'set'):
                try:
                    app._neg_custom_var.set(neg_custom_terms)
                except Exception:
                    pass
        if hasattr(app, '_rebuild_neg_combined'):
            try:
                app._rebuild_neg_combined()
            except Exception:
                pass
        if config.get("remember_settings", False) and not config.get("auto_generate_on_startup", False):
            app.set_active_mode(config.get("last_style_mode", app.DEFAULT_PROMPT_MODE_VALUE))
            app.set_active_subject(config.get("last_subject", "frog"))
            app.set_active_setting(config.get("last_setting", ""))
            app.set_active_style(config.get("last_style", "oil painting"))
            app.set_active_lighting(config.get("last_lighting", "neon"))
            app.set_active_mood(config.get("last_mood", "epic"))
            app.set_active_color(config.get("last_color", ""))
            app.set_active_atmosphere(config.get("last_atmosphere", ""))
            app.set_active_subject_lock(config.get("last_subject_lock", True))
            app.status_var.set("Settings restored from last session")
        else:
            # "Remember settings" is OFF: wipe the SAVED values from config
            # so nothing from the last session persists, but leave the UI on
            # its built-in starter defaults (frog / neon / oil painting and
            # the random color/setting/atmosphere chosen at build time).
            # Previously this blanked the dropdowns themselves, which made
            # every category dropdown render empty on a fresh start.
            config["last_style"] = ""
            config["last_setting"] = ""
            config["last_lighting"] = ""
            config["last_mood"] = ""
            config["last_color"] = ""
            config["last_atmosphere"] = ""
            config["last_subject"] = ""
            save_config(config)
            # Re-seed prompt_builder_values from the live sidebar widgets so
            # the prompt engine and the UI agree on the starter defaults.
            try:
                for key, widget_name in (("subject", "subject_entry"),
                                         ("lighting", "lighting_entry"),
                                         ("setting", "setting_entry"),
                                         ("atmosphere", "atmosphere_combo"),
                                         ("mood", "mood_entry")):
                    widget = getattr(app, widget_name, None)
                    if widget is not None and hasattr(widget, "get"):
                        app.prompt_builder_values[key] = widget.get()
                family = (app.color_family_var.get() or "").strip()
                variation = (app.color_variation_var.get() or "").strip()
                app.prompt_builder_values["color"] = f"{variation} {family}".strip()
            except Exception:
                pass

    def add_user_mapping(self):
        """Add a custom user thesaurus mapping."""
        app = self.app
        from_word = app.from_word_var.get().strip()
        to_word = app.to_word_var.get().strip()
        if not from_word or not to_word:
            app._dialog.warning("Invalid Input", "Please enter both 'when I type' and 'treat as' values.")
            return
        try:
            from keyword_expander import get_keyword_expander
            expander = get_keyword_expander()
            expander.add_user_mapping(from_word, to_word)
            app.from_word_var.set("")
            app.to_word_var.set("")
            app.status_var.set(f"Added mapping: '{from_word}' -> '{to_word}'")
            app.expansion_status_var.set(f"Keyword expansion: Added '{from_word}' -> '{to_word}'")
        except Exception as e:
            app._dialog.error("Settings Error", "Could not save the mapping. Try again.")

    def remove_user_mapping(self):
        """Remove a custom user thesaurus mapping."""
        app = self.app
        from_word = app.from_word_var.get().strip()
        if not from_word:
            app._dialog.warning("Invalid Input", "Please enter the word to remove.")
            return
        try:
            from keyword_expander import get_keyword_expander
            expander = get_keyword_expander()
            expander.remove_user_mapping(from_word)
            app.from_word_var.set("")
            app.status_var.set(f"Removed mapping for: '{from_word}'")
            app.expansion_status_var.set(f"Keyword expansion: Removed '{from_word}'")
        except Exception as e:
            app._dialog.error("Settings Error", "Could not remove the mapping. Try again.")

    def get_current_dimensions(self):
        """Get current wallpaper dimensions string."""
        app = self.app
        return app.DIMENSION_PRESETS.get(app.dimension_preset_var.get(), "1920x1080")

