"""AI-provider configuration methods for the Settings tab (roadmap #7 Phase A).

Hosts the dynamic provider setup panel (``_rebuild_provider_setup``),
provider/model change handlers, token entry + visibility toggling and
dimension-preset helpers.  Mixed into ``SettingsTab``; widgets created
here are stored on ``self``/``self.app`` exactly as before, so the
delegating wrappers in app.py keep working untouched.
"""

import tkinter as tk
import webbrowser
from tkinter import ttk

from utils import load_config, save_config, get_huggingface_token

from settings_components import ExpandableSection
from settings_ux_data import AI_PROVIDER_UX

from theme import COLOR_ACCENT, COLOR_SUCCESS  # shared color constants (migrated inline hex)


class SettingsProvidersMixin:
    """Provider setup / token UI methods for SettingsTab."""

    # ================================================================
    # EVENT HANDLERS (delegated to existing app methods)
    # ================================================================

    def _on_dimension_preset_changed(self, event=None):
        app = self.app
        preset = app.dimension_preset_var.get()
        dimensions = app.DIMENSION_PRESETS.get(preset, "1920x1080")
        self._set_dimensions_from_string(dimensions)
        config = load_config()
        config['dimensions'] = dimensions
        save_config(config)

    def _on_model_choice_changed(self, event=None):
        app = self.app
        if app.model_choice_var.get() == "Custom...":
            if not app.custom_model_entry.winfo_ismapped():
                app.custom_model_entry.pack(fill="x", pady=8)
        elif app.custom_model_entry.winfo_ismapped():
            app.custom_model_entry.pack_forget()


    def _rebuild_provider_setup(self, provider, pal):
        """Dynamically rebuild the provider setup area for the selected provider."""
        app = self.app

        # Clear existing fields and guide
        for widget in app.provider_fields_frame.winfo_children():
            widget.destroy()
        for widget in app.provider_guide_frame.winfo_children():
            widget.destroy()

        # Determine which provider UX to use
        ux_key = None
        for key in AI_PROVIDER_UX:
            if key.lower() in provider.lower():
                ux_key = key
                break
        if not ux_key:
            # Fallback: no setup needed
            no_key_label = tk.Label(
                app.provider_fields_frame,
                text="No configuration needed for this provider.",
                font=("Segoe UI", 10),
                fg=pal["muted"],
                bg=pal["card_bg"]
            )
            no_key_label.pack(fill="x", pady=8)
            return

        ux = AI_PROVIDER_UX[ux_key]
        from settings_components import SetupGuideText

        if not ux.get("needs_key", False):
            # No key needed (e.g. Pollinations)
            free_label = tk.Label(
                app.provider_fields_frame,
                text=f"{ux['display_name']} requires no API key. You're all set!",
                font=("Segoe UI", 10),
                fg=COLOR_SUCCESS,
                bg=pal["card_bg"]
            )
            free_label.pack(fill="x", pady=8)
        else:
            # Build key entry field(s)
            key_frame = tk.Frame(app.provider_fields_frame, bg=pal["card_bg"])
            key_frame.pack(fill="x", pady=8)

            key_config_field = ux["key_config_field"]
            key_label_text = ux.get("key_label", "API Key")
            saved_key = load_config().get(key_config_field, "")

            # For HuggingFace, also check env var
            if key_config_field == "huggingface_token":
                saved_key = get_huggingface_token()

            key_var = tk.StringVar(value=saved_key)
            setattr(app, f"{ux_key.lower()}_key_var", key_var)

            tk.Label(key_frame, text=f"{key_label_text}:", font=("Segoe UI", 10),
                    fg=pal["text"], bg=pal["card_bg"]).pack(side="left", padx=(8, 4))
            key_entry = ttk.Entry(key_frame, textvariable=key_var, width=40, show="*")
            key_entry.pack(side="left", fill="x", expand=True)
            app.configure_entry_cursor(key_entry)

            # Auto-save on focus out
            # Map the generic var name to the actual config field for saving
            def make_config_save_handler(config_field, var_attr):
                def handler(event=None):
                    config = load_config()
                    var_obj = getattr(app, var_attr, None)
                    if var_obj:
                        val = var_obj.get().strip()
                        if val:
                            config[config_field] = val
                        else:
                            config.pop(config_field, None)
                        save_config(config)
                return handler

            key_entry.bind("<FocusOut>", make_config_save_handler(key_config_field, f"{ux_key.lower()}_key_var"))

            # Get Key button
            get_url = ux.get("get_key_url", "")
            if get_url:
                ttk.Button(key_frame, text="Get Key",
                           command=lambda u=get_url: webbrowser.open(u)).pack(side="right", padx=8)

            # Account ID field for Cloudflare
            if ux.get("needs_account_id", False):
                id_frame = tk.Frame(app.provider_fields_frame, bg=pal["card_bg"])
                id_frame.pack(fill="x", pady=(0, 8))

                id_config_field = ux["account_id_config_field"]
                saved_id = load_config().get(id_config_field, "")
                app.cloudflare_account_id_var = tk.StringVar(value=saved_id)

                tk.Label(id_frame, text="Account ID:", font=("Segoe UI", 10),
                        fg=pal["text"], bg=pal["card_bg"]).pack(side="left", padx=(8, 4))
                id_entry = ttk.Entry(id_frame, textvariable=app.cloudflare_account_id_var, width=40)
                id_entry.pack(side="left", fill="x", expand=True)
                app.configure_entry_cursor(id_entry)
                id_entry.bind("<FocusOut>", make_config_save_handler(id_config_field, "cloudflare_account_id_var"))

        # Build setup guide (expandable, starts expanded)
        guide_section = ExpandableSection(
            app.provider_guide_frame,
            f"How to set up {ux['display_name']}",
            expanded=True,
            palette=pal,
            accent_color=pal.get("accent", COLOR_ACCENT)
        )

        guide_content = guide_section.get_content()
        guide_text = SetupGuideText(
            guide_content,
            ux["setup_steps"],
            bg=pal["card_bg"],
            fg=pal["muted"],
            link=pal.get("accent", COLOR_ACCENT),
            font=("Segoe UI", 9),
        )
        guide_text.pack(fill="x", pady=4)

    def _on_provider_changed(self, event=None):
        """Handle provider dropdown change."""
        app = self.app
        provider = app.provider_var.get().strip()
        provider_info = app.PROVIDER_MODELS.get(provider, {})
        new_models = provider_info.get("options", [])
        app.model_choice_combo["values"] = new_models
        if new_models:
            app.model_choice_var.set(new_models[0])
        else:
            app.model_choice_var.set("")
        app.custom_model_entry.pack_forget()
        self._update_provider_description()
        # Rebuild the provider setup card for the new provider
        pal = self._palette
        self._rebuild_provider_setup(provider, pal)

    # _update_provider_visibility removed — now handled by _rebuild_provider_setup

    def _update_provider_description(self):
        """Update the description label for the selected provider."""
        app = self.app
        provider = app.provider_var.get().strip()
        descriptions = {
            "Pollinations.ai (Free - No Key)": "100% free, no account or API key needed. Multiple FLUX models available.",
            "Prodia (Pro Account)": "Pro account required for API access. Fast generation with 50+ models via inference.prodia.com.",
            "Cloudflare Workers AI (Free Tier)": "Free: 10,000 neurons/day. Needs a Cloudflare account (free to create).",
            "Replicate (Pay-Per-Image)": "Pay per image (~$0.003 for FLUX schnell). Most reliable, huge model library.",
            "Fal.ai (Fast Inference)": "Fastest inference (~1-2 sec). Prepaid credits from $1. Great FLUX models.",
            "Hugging Face Inference": "Uses your HF token. Free credits reset monthly ($0.10 for free users).",
        }
        app.provider_desc_var.set(descriptions.get(provider, ""))

    def _on_token_changed(self, event=None):
        """Auto-save token when the entry field loses focus. (Legacy — now handled dynamically.)"""
        pass

    # Individual provider key handlers removed — handled dynamically by _rebuild_provider_setup

    def _set_dimensions_from_string(self, dimensions_str):
        app = self.app
        if "x" in dimensions_str:
            width, height = dimensions_str.split("x", 1)
            app.custom_width_var.set(width.strip())
            app.custom_height_var.set(height.strip())
            for preset_name, preset_dims in app.DIMENSION_PRESETS.items():
                if preset_dims == dimensions_str:
                    app.dimension_preset_var.set(preset_name)
                    break

    # ================================================================
    # DELEGATED METHODS (called from app.py via self._settings_tab)
    # ================================================================

    def format_token_preview(self):
        """Format token for preview display."""
        token = get_huggingface_token()
        if not token:
            return "Environment token not found."
        if len(token) <= 8:
            return "Environment token loaded: " + ("*" * len(token))
        return f"Environment token loaded: {token[:4]}...{token[-4:]}"

    def refresh_token_status(self):
        """Refresh token from environment and update UI if HuggingFace provider is active."""
        app = self.app
        token = get_huggingface_token()
        # Update the dynamic HF key field if it exists (only when HF is selected)
        if hasattr(app, 'hugging_key_var'):
            app.hugging_key_var.set(token)
        if hasattr(app, 'status_var'):
            app.status_var.set("Environment token loaded." if token else "No environment token found.")

    def toggle_token_visibility(self):
        """Toggle token entry between hidden and visible (no-op with dynamic fields)."""
        pass

    def resolved_model_id(self):
        """Resolve the selected model display name to an actual model ID."""
        app = self.app
        choice = app.model_choice_var.get().strip()
        if choice == "Custom...":
            return app.custom_model_var.get().strip()
        provider = app.provider_var.get().strip()
        provider_info = app.PROVIDER_MODELS.get(provider, {})
        display_to_id = provider_info.get("display_to_id", {})
        return display_to_id.get(choice, "flux")

