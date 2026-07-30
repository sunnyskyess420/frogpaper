import tkinter as tk
import logging

from tkinter import ttk

from datetime import datetime

from utils import (
    load_config,
    save_config,
    get_huggingface_token,
)


logger = logging.getLogger(__name__)


class SettingsTab:
    """Settings tab: appearance, model, slideshow, tokens, mappings."""

    def __init__(self, app):
        self.app = app
    def _build_settings_tab(self, parent):

        # ── Fixed header: Save Settings always visible ──────────────────────
        app = self.app
        header = ttk.Frame(parent, padding=(10, 6))
        header.pack(side="top", fill="x")
        app._btn_save_settings = ttk.Button(header, text=" Save Settings", command=app.save_settings)
        app._btn_save_settings.pack(side="left")
        ttk.Separator(parent, orient="horizontal").pack(side="top", fill="x")

        # ── Scrollable body ─────────────────────────────────────────────────
        canvas = tk.Canvas(parent, highlightthickness=0)
        scroll = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        inner = ttk.Frame(canvas, style="Inner.TFrame")
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        _st_win = canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(_st_win, width=e.width))
        canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        app.settings_canvas = canvas
        app.settings_inner = inner

        # Enable mousewheel scrolling for the entire settings panel
        def _settings_wheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            return "break"

        def _bind_wheel_recursive(widget):
            try:
                widget.bind("<MouseWheel>", _settings_wheel)
                for child in widget.winfo_children():
                    _bind_wheel_recursive(child)
            except Exception:
                pass

        # Bind after all widgets are built
        def _deferred_bind():
            _bind_wheel_recursive(canvas)
            _bind_wheel_recursive(inner)
        parent.after(200, _deferred_bind)

        PAD = {"pady": (0, 12)}   # uniform section gap
        LBL = {"font": app.UI["heading_font"]}  # section-label style

        # ── 1. APPEARANCE ────────────────────────────────────────────────────
        ap = ttk.LabelFrame(inner, text="Appearance", padding=10)
        ap.pack(fill="x", **PAD)
        ap.columnconfigure(1, weight=1)

        ttk.Label(ap, text="App Theme:", **LBL).grid(row=0, column=0, sticky="w", pady=(0, 4))
        app.theme_var = tk.StringVar(value=app.THEME_DISPLAY_NAMES.get(load_config().get("app_theme", "darkforest"), "Dark Forest Green"))
        app.theme_combo = ttk.Combobox(ap, textvariable=app.theme_var, values=list(app.THEME_DISPLAY_NAMES.values()), state="readonly", width=25)
        app.theme_combo.grid(row=0, column=1, sticky="w", pady=(0, 4))
        app.theme_combo.bind("<<ComboboxSelected>>", app.on_theme_changed)

        ttk.Label(ap, text="Resolution:", **LBL).grid(row=1, column=0, sticky="w", pady=(6, 4))
        if not hasattr(app, 'dimension_preset_var'):
            app.dimension_preset_var = tk.StringVar(value="16:9 (1080p)")
        app.dimension_preset_combo = ttk.Combobox(ap, textvariable=app.dimension_preset_var, values=list(app.DIMENSION_PRESETS.keys()), state="readonly", width=20)
        app.dimension_preset_combo.grid(row=1, column=1, sticky="w", pady=(6, 4))

        # Note: Custom WxH option removed - use built-in presets only

        # ── 2. GENERATION ────────────────────────────────────────────────────
        gn = ttk.LabelFrame(inner, text="Generation", padding=10)
        gn.pack(fill="x", **PAD)
        gn.columnconfigure(1, weight=1)

        # ── Provider selection ──
        ttk.Label(gn, text="Provider:", **LBL).grid(row=0, column=0, sticky="w", pady=(0, 4))
        saved_provider = load_config().get("provider", "Pollinations.ai (Free - No Key)")
        app.provider_var = tk.StringVar(value=saved_provider)
        app.provider_combo = ttk.Combobox(gn, textvariable=app.provider_var,
                                          values=app.PROVIDER_OPTIONS, state="readonly", width=40)
        app.provider_combo.grid(row=0, column=1, sticky="w", pady=(0, 4))
        app.provider_combo.bind("<<ComboboxSelected>>", app._on_provider_changed)

        # Provider description
        app.provider_desc_var = tk.StringVar(value="")
        ttk.Label(gn, textvariable=app.provider_desc_var, font=app.small_font,
                  foreground="#666666").grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 4))
        app._update_provider_description()

        # ── API Token: shown/hidden based on provider ──
        token_frame = ttk.Frame(gn)
        token_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(0, 4))
        token_frame.columnconfigure(1, weight=1)
        app.token_frame = token_frame

        ttk.Label(token_frame, text="API Token:", **LBL).grid(row=0, column=0, sticky="w", pady=(0, 4))
        app.token_var = tk.StringVar(value=get_huggingface_token())
        app.token_entry = ttk.Entry(token_frame, textvariable=app.token_var, width=40, show="*")
        app.token_entry.grid(row=0, column=1, sticky="ew", pady=(0, 4))
        app.configure_entry_cursor(app.token_entry)
        app.token_entry.bind("<FocusOut>", app._on_token_changed)

        app.token_preview_var = tk.StringVar(value=app.format_token_preview())
        ttk.Label(token_frame, textvariable=app.token_preview_var, font=app.small_font).grid(
            row=1, column=0, columnspan=2, sticky="w", pady=(2, 4))

        tok_btns = ttk.Frame(token_frame)
        tok_btns.grid(row=2, column=0, columnspan=2, sticky="w", pady=(0, 4))
        app.token_toggle_btn = ttk.Button(tok_btns, text="Show Token", command=app.toggle_token_visibility)
        app.token_toggle_btn.pack(side="left", padx=(0, 8))
        ttk.Button(tok_btns, text="Refresh Token Status", command=app.refresh_token_status).pack(side="left")

        # ── Cloudflare token + Account ID: shown only for Cloudflare provider ──
        cf_frame = ttk.Frame(gn)
        cf_frame.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(0, 4))
        cf_frame.columnconfigure(1, weight=1)
        app.cloudflare_token_frame = cf_frame
        # Hidden by default

        ttk.Label(cf_frame, text="Cloudflare Token:", **LBL).grid(row=0, column=0, sticky="w", pady=(0, 4))
        saved_cf_token = load_config().get("cloudflare_token", "")
        app.cloudflare_token_var = tk.StringVar(value=saved_cf_token)
        app.cloudflare_token_entry = ttk.Entry(cf_frame, textvariable=app.cloudflare_token_var, width=40, show="*")
        app.cloudflare_token_entry.grid(row=0, column=1, sticky="ew", pady=(0, 4))
        app.configure_entry_cursor(app.cloudflare_token_entry)

        ttk.Label(cf_frame, text="Account ID:", **LBL).grid(row=1, column=0, sticky="w", pady=(4, 4))
        saved_cf_account_id = load_config().get("cloudflare_account_id", "")
        app.cloudflare_account_id_var = tk.StringVar(value=saved_cf_account_id)
        app.cloudflare_account_id_entry = ttk.Entry(cf_frame, textvariable=app.cloudflare_account_id_var, width=40)
        app.cloudflare_account_id_entry.grid(row=1, column=1, sticky="ew", pady=(4, 4))
        app.configure_entry_cursor(app.cloudflare_account_id_entry)

        ttk.Label(cf_frame, text="Token: dash.cloudflare.com → Workers AI → Use REST API → Create Token",
                  font=app.small_font, foreground="#666666", wraplength=620).grid(
            row=2, column=0, columnspan=2, sticky="w", pady=(0, 0))
        ttk.Label(cf_frame, text="Account ID: dash.cloudflare.com → right sidebar (or URL: /accounts/XXXX)",
                  font=app.small_font, foreground="#666666", wraplength=620).grid(
            row=3, column=0, columnspan=2, sticky="w", pady=(0, 4))
        # Initially hide CF frame
        cf_frame.grid_remove()

        ttk.Separator(gn, orient="horizontal").grid(row=4, column=0, columnspan=2, sticky="ew", pady=(0, 8))

        # ── Model selection ──
        ttk.Label(gn, text="AI Model:", **LBL).grid(row=5, column=0, sticky="w", pady=(0, 4))
        saved_model_id = load_config().get("model_id", "flux")
        # Determine initial model list based on saved provider
        provider_info = app.PROVIDER_MODELS.get(saved_provider, app.PROVIDER_MODELS.get("Pollinations.ai (Free - No Key)", {}))
        provider_models = provider_info.get("options", [])
        provider_display_to_id = provider_info.get("display_to_id", {})
        provider_id_to_display = {v: k for k, v in provider_display_to_id.items()}
        initial_display = provider_id_to_display.get(saved_model_id, provider_models[0] if provider_models else "FLUX (Default)")

        app.model_choice_var = tk.StringVar(value=initial_display)
        app.model_choice_combo = ttk.Combobox(gn, textvariable=app.model_choice_var,
                                              values=provider_models, state="readonly", width=40)
        app.model_choice_combo.grid(row=5, column=1, sticky="w", pady=(0, 4))
        app.model_choice_combo.bind("<<ComboboxSelected>>", app._on_model_choice_changed)
        app.custom_model_var = tk.StringVar(value=saved_model_id if initial_display == "Custom..." else "")
        app.custom_model_entry = ttk.Entry(gn, textvariable=app.custom_model_var, width=58)
        app.configure_entry_cursor(app.custom_model_entry)
        if initial_display == "Custom...":
            app.custom_model_entry.grid(row=6, column=0, columnspan=2, sticky="w", pady=(0, 4))

        # Show/hide token fields based on initial provider
        app._update_provider_visibility()

        # ── 3. GALLERY & SLIDESHOW ───────────────────────────────────────────
        gs = ttk.LabelFrame(inner, text="Gallery & Slideshow", padding=10)
        gs.pack(fill="x", **PAD)
        gs.columnconfigure(1, weight=1)

        ttk.Label(gs, text="Wallpaper Slideshow:", **LBL).grid(row=0, column=0, sticky="w", pady=(0, 4))

        if not hasattr(app, 'slideshow_enabled_var'):
            app.slideshow_enabled_var = tk.BooleanVar(value=False)
        if not hasattr(app, 'slideshow_interval_var'):
            app.slideshow_interval_var = tk.StringVar(value='60')
        if not hasattr(app, 'slideshow_source_var'):
            app.slideshow_source_var = tk.StringVar(value='All Images')
        if not hasattr(app, 'slideshow_order_var'):
            app.slideshow_order_var = tk.StringVar(value='random')
        if not hasattr(app, 'slideshow_skip_duplicates_var'):
            app.slideshow_skip_duplicates_var = tk.BooleanVar(value=True)
        app.sync_slideshow_state()

        ttk.Checkbutton(gs, text="Enable in-app slideshow",
                        variable=app.slideshow_enabled_var,
                        command=app.on_slideshow_toggle).grid(row=1, column=1, sticky="w", pady=(0, 4))

        # Interval row with label and value display
        interval_label_frame = ttk.Frame(gs)
        interval_label_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(2, 0))
        interval_label_frame.columnconfigure(1, weight=1)
        
        ttk.Label(interval_label_frame, text="Interval (minutes)").grid(row=0, column=0, sticky="w")
        if not hasattr(app, 'interval_display_var'):
            app.interval_display_var = tk.StringVar(value='60')
        ttk.Label(interval_label_frame, textvariable=app.interval_display_var, font=("Segoe UI", 10, "bold"), foreground="#0078D4").grid(row=0, column=1, sticky="e")
        
        # Slider for interval selection (1-60 minutes)
        def on_interval_change(value):
            # Round to nearest integer for display and storage
            val = int(float(value))
            app.slideshow_interval_var.set(str(val))
            app.interval_display_var.set(str(val))
        
        app.interval_slider = ttk.Scale(gs, from_=1, to=60, orient='horizontal', command=on_interval_change)
        try:
            initial_val = int(float(app.slideshow_interval_var.get()))
            app.interval_slider.set(max(1, min(60, initial_val)))
        except:
            app.interval_slider.set(60)
        app.interval_slider.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(4, 0))
        
        # Helper text
        ttk.Label(gs, text="Adjust the slider to set how often wallpapers rotate (1–60 minutes)",
                  font=app.small_font, foreground="#666666", wraplength=620).grid(
            row=4, column=0, columnspan=2, sticky="w", pady=(2, 0))

        ttk.Label(gs, text="Source").grid(row=5, column=0, sticky="w", pady=(2, 0))
        ttk.Combobox(gs, textvariable=app.slideshow_source_var, values=app.SLIDESHOW_SOURCE_DISPLAY, state='readonly', width=18).grid(row=5, column=1, sticky="w", pady=(2, 0))

        ttk.Label(gs, text="Order").grid(row=6, column=0, sticky="w", pady=(2, 0))
        ttk.Combobox(gs, textvariable=app.slideshow_order_var, values=['random', 'newest', 'oldest'], state='readonly', width=10).grid(row=6, column=1, sticky="w", pady=(2, 0))

        ttk.Checkbutton(gs, text="Skip duplicates (no repeat until all shown)",
                        variable=app.slideshow_skip_duplicates_var).grid(
            row=7, column=0, columnspan=2, sticky="w", pady=(4, 6))

        # ── Wallpaper Optimization ────────────────────────────────────────────
        ttk.Separator(gs, orient="horizontal").grid(row=8, column=0, columnspan=2, sticky="ew", pady=(8, 8))

        ttk.Label(gs, text="Wallpaper Output:", **LBL).grid(row=9, column=0, sticky="w", pady=(0, 4))

        if not hasattr(app, 'wallpaper_format_var'):
            app.wallpaper_format_var = tk.StringVar(value='PNG')
        if not hasattr(app, 'wallpaper_quality_var'):
            app.wallpaper_quality_var = tk.StringVar(value='High')

        format_frame = ttk.Frame(gs)
        format_frame.grid(row=9, column=1, sticky="w", pady=(0, 4))
        ttk.Combobox(format_frame, textvariable=app.wallpaper_format_var,
                     values=['PNG', 'JPEG', 'WebP'], state='readonly', width=10).pack(side='left', padx=(0, 8))
        ttk.Combobox(format_frame, textvariable=app.wallpaper_quality_var,
                     values=['Maximum', 'High', 'Medium', 'Low'], state='readonly', width=10).pack(side='left')

        ttk.Label(gs, text="Lower quality = smaller file size, minimal visual difference at desktop size",
                  font=app.small_font, foreground="#666666", wraplength=620).grid(
            row=10, column=0, columnspan=2, sticky="w", pady=(2, 0))

        # ── 4. WINDOW BEHAVIOR ───────────────────────────────────────────────
        wb = ttk.LabelFrame(inner, text="Window Behavior", padding=10)
        wb.pack(fill="x", **PAD)

        app.minimize_to_tray_var = tk.BooleanVar(value=app.minimize_to_tray_enabled)
        ttk.Label(wb, text="Minimize to tray:", **LBL).grid(row=0, column=0, sticky="w", pady=(0, 2))
        ttk.Checkbutton(wb, text="Enabled",
                        variable=app.minimize_to_tray_var,
                        command=app._on_minimize_to_tray_changed).grid(row=0, column=1, sticky="w", pady=(0, 2))
        ttk.Label(wb, text="Closing or minimizing sends the app to the system tray",
                  font=app.small_font, foreground="#666666", wraplength=620).grid(
            row=1, column=0, columnspan=2, sticky="w", pady=(2, 0))

        app.run_on_startup_var = tk.BooleanVar(value=app.run_on_startup_enabled)
        ttk.Label(wb, text="Run on startup:", **LBL).grid(row=2, column=0, sticky="w", pady=(8, 2))
        ttk.Checkbutton(wb, text="Enabled",
                        variable=app.run_on_startup_var,
                        command=app._on_run_on_startup_changed).grid(row=2, column=1, sticky="w", pady=(8, 2))
        ttk.Label(wb, text="Automatically launch FrogPaper when Windows starts",
                  font=app.small_font, foreground="#666666", wraplength=620).grid(
            row=3, column=0, columnspan=2, sticky="w", pady=(0, 2))

        ttk.Label(wb, text="Auto-generate on startup:", **LBL).grid(row=4, column=0, sticky="w", pady=(8, 2))
        ttk.Checkbutton(wb, text="Generate a fresh random wallpaper each launch",
                        variable=app.auto_generate_on_startup_var).grid(
            row=4, column=1, sticky="w", pady=(8, 2))
        ttk.Label(wb, text="Startup subject:", **LBL).grid(row=5, column=0, sticky="w", pady=(4, 2))
        startup_subj_entry = ttk.Entry(wb, textvariable=app.startup_subject_var, width=20)
        startup_subj_entry.grid(row=5, column=1, sticky="w", pady=(4, 2))
        ttk.Label(wb, text="Leave as 'frog' for classic frogs, or change to any subject you like",
                  font=app.small_font, foreground="#666666", wraplength=620).grid(
            row=6, column=0, columnspan=2, sticky="w", pady=(0, 2))

        # ── 5. ADVANCED ──────────────────────────────────────────────────────
        adv = ttk.LabelFrame(inner, text="Advanced", padding=10)
        adv.pack(fill="x", pady=(0, 20))
        adv.columnconfigure(0, weight=1)

        # ── Generation Behavior section ──
        gen_beh_title = ttk.Label(adv, text="Generation Behavior", font=("Segoe UI", 10, "bold"))
        gen_beh_title.grid(row=0, column=0, sticky="w", pady=(0, 8))

        # Smart Negatives toggle
        smart_neg_frame = ttk.Frame(adv)
        smart_neg_frame.grid(row=1, column=0, sticky="ew", pady=(0, 2))
        smart_neg_frame.columnconfigure(1, weight=1)
        ttk.Checkbutton(smart_neg_frame, text="Smart Negatives",
                        variable=app.smart_neg_var).grid(row=0, column=0, sticky="w")
        ttk.Label(smart_neg_frame,
                  text="Scan the generated prompt for keywords (e.g. portrait, forest) and inject matching negative terms.",
                  font=app.small_font, foreground="#666666").grid(row=1, column=0, sticky="w", padx=(20, 0))

        # Subject Lock toggle
        subj_lock_frame = ttk.Frame(adv)
        subj_lock_frame.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        subj_lock_frame.columnconfigure(1, weight=1)
        ttk.Checkbutton(subj_lock_frame, text="Keep subject exact",
                        variable=app.subject_lock_var).grid(row=0, column=0, sticky="w")
        ttk.Label(subj_lock_frame,
                  text="Use your typed subject as-is. When off, mood adjectives (e.g. serene, vibrant) may be prefixed.",
                  font=app.small_font, foreground="#666666").grid(row=1, column=0, sticky="w", padx=(20, 0))

        ttk.Separator(adv, orient="horizontal").grid(row=3, column=0, sticky="ew", pady=(4, 10))

        # Keyword Expansion section title
        kw_title = ttk.Label(adv, text="Keyword Expansion", font=("Segoe UI", 10, "bold"))
        kw_title.grid(row=4, column=0, sticky="w", pady=(0, 8))

        # Centered container for mapping controls
        kw_center_frame = ttk.Frame(adv)
        kw_center_frame.grid(row=5, column=0, sticky="ew", pady=(0, 8))
        kw_center_frame.columnconfigure(0, weight=1)

        # Inner frame for the actual controls (centered)
        kw_row = ttk.Frame(kw_center_frame)
        kw_row.grid(row=0, column=0)

        ttk.Label(kw_row, text="When I type:").pack(side="left", padx=(0, 6))
        app.from_word_var = tk.StringVar()
        app.from_word_entry = ttk.Entry(kw_row, textvariable=app.from_word_var, width=14)
        app.from_word_entry.pack(side="left", padx=(0, 8))
        app.configure_entry_cursor(app.from_word_entry)
        ttk.Label(kw_row, text="→").pack(side="left", padx=(0, 6))
        app.to_word_var = tk.StringVar()
        app.to_word_entry = ttk.Entry(kw_row, textvariable=app.to_word_var, width=14)
        app.to_word_entry.pack(side="left", padx=(0, 8))
        app.configure_entry_cursor(app.to_word_entry)
        ttk.Button(kw_row, text="Add",    command=app.add_user_mapping).pack(side="left", padx=(0, 6))
        ttk.Button(kw_row, text="Remove", command=app.remove_user_mapping).pack(side="left")

        # Example and status labels
        ttk.Label(adv, text="e.g.  awesome → epic     gloomy → moody",
                  font=app.small_font, foreground="#666666").grid(
            row=6, column=0, sticky="w", pady=(4, 4))

        app.expansion_status_var = tk.StringVar(value="Keyword expansion: Ready")
        ttk.Label(adv, textvariable=app.expansion_status_var,
                  font=app.small_font).grid(row=7, column=0, sticky="w")

        # Initialize slideshow status variable
        app.slideshow_status_var = tk.StringVar(value="Slideshow idle")


    def _on_dimension_preset_changed(self, event=None):
        app = self.app
        preset = app.dimension_preset_var.get()
        dimensions = app.DIMENSION_PRESETS.get(preset, "1920x1080")
        app._set_dimensions_from_string(dimensions)
        # Save config to persist the dimension change
        app.save_config()


    def _on_model_choice_changed(self, event=None):

        app = self.app
        if app.model_choice_var.get() == "Custom...":

            if not app.custom_model_entry.winfo_ismapped():
                # Grid it below the model combo (row 6 in the Generation frame)
                app.custom_model_entry.grid(row=6, column=0, columnspan=2, sticky="w", pady=(0, 4))

        elif app.custom_model_entry.winfo_ismapped():

            app.custom_model_entry.grid_remove()

    def _on_provider_changed(self, event=None):
        """Handle provider dropdown change — update model list and token visibility."""
        app = self.app
        provider = app.provider_var.get().strip()

        # Update model dropdown with this provider's models
        provider_info = app.PROVIDER_MODELS.get(provider, {})
        new_models = provider_info.get("options", [])
        app.model_choice_combo["values"] = new_models
        # Select first model of new provider
        if new_models:
            app.model_choice_var.set(new_models[0])
        else:
            app.model_choice_var.set("")

        # Hide custom model entry if shown
        app.custom_model_entry.grid_remove()

        # Update visibility of token fields
        app._update_provider_visibility()

        # Update description
        app._update_provider_description()

    def _update_provider_visibility(self):
        """Show/hide token fields based on the selected provider."""
        app = self.app
        provider = app.provider_var.get().strip()

        if "Pollinations" in provider:
            # Pollinations needs no token at all — hide both
            app.token_frame.grid_remove()
            app.cloudflare_token_frame.grid_remove()
        elif "Cloudflare" in provider:
            # Show Cloudflare token, hide HF token
            app.token_frame.grid_remove()
            app.cloudflare_token_frame.grid()
        else:
            # Hugging Face — show HF token, hide CF token
            app.token_frame.grid()
            app.cloudflare_token_frame.grid_remove()

    def _update_provider_description(self):
        """Update the description label for the selected provider."""
        app = self.app
        provider = app.provider_var.get().strip()
        descriptions = {
            "Pollinations.ai (Free - No Key)": "100% free, no account needed. Multiple FLUX models available.",
            "Cloudflare Workers AI (Free Tier)": "Free: 10,000 neurons/day. Needs a free Cloudflare account token.",
            "Hugging Face Inference": "Uses your HF token. Free credits reset monthly ($0.10 for free users).",
        }
        app.provider_desc_var.set(descriptions.get(provider, ""))


    def _on_remember_settings_changed(self, event=None):

        app = self.app
        pass


    def _on_token_changed(self, event=None):
        """Auto-save token when the entry field loses focus."""
        app = self.app
        token = app.token_var.get().strip()
        config = load_config()
        if token:
            config["huggingface_token"] = token
        else:
            config.pop("huggingface_token", None)
        save_config(config)
        app.token_preview_var.set(app.format_token_preview())


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



            app.status_var.set(f"✓ Added mapping: '{from_word}' → '{to_word}'")

            app.expansion_status_var.set(f"Keyword expansion: Added '{from_word}' → '{to_word}'")



        except Exception as e:

            app._dialog.error("Error", f"Could not add mapping: {e}")


    def format_token_preview(self):

        app = self.app
        token = get_huggingface_token()

        if not token:

            return "Environment token not found."

        if len(token) <= 8:

            return "Environment token loaded: " + ("*" * len(token))

        return f"Environment token loaded: {token[:4]}...{token[-4:]}"


    def get_current_dimensions(self):
        app = self.app
        return app.DIMENSION_PRESETS.get(app.dimension_preset_var.get(), "1920x1080")


    def load_remembered_settings(self):

        app = self.app
        config = load_config()

        # Always restore wallpaper output format and quality (core settings)
        if hasattr(app, 'wallpaper_format_var'):
            app.wallpaper_format_var.set(config.get('wallpaper_format', 'PNG'))
        if hasattr(app, 'wallpaper_quality_var'):
            app.wallpaper_quality_var.set(config.get('wallpaper_quality', 'High'))

        # Always restore negative prompt selections (user preference)
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
        
        # Rebuild the combined negative prompt from restored selections
        if hasattr(app, '_rebuild_neg_combined'):
            try:
                app._rebuild_neg_combined()
            except Exception:
                pass

        # Only restore remembered settings if auto-generate on startup is disabled
        # When auto-generate is enabled, we want random variables each time
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
            # When auto-generate is enabled, clear any last settings to prevent them from being used
            # This ensures fresh randomization each startup
            config["last_style"] = ""
            config["last_setting"] = ""
            config["last_lighting"] = ""
            config["last_mood"] = ""
            config["last_color"] = ""
            config["last_atmosphere"] = ""
            save_config(config)
            # Also clear UI widget values to ensure they don't interfere with randomization
            app.set_active_style("")
            app.set_active_setting("")
            app.set_active_lighting("")
            app.set_active_mood("")
            app.set_active_color("")
            app.set_active_atmosphere("")


    def load_slideshow_settings(self):

        app = self.app
        config = load_config()

        app.slideshow_enabled_var.set(bool(config.get('slideshow_enabled', False)))

        interval_value = str(config.get('slideshow_interval', 60))
        app.slideshow_interval_var.set(interval_value)
        # Update interval display and slider
        try:
            interval_int = int(float(interval_value))
            # Clamp to 1-60 range for slider
            interval_int = max(1, min(60, interval_int))
            if hasattr(app, 'interval_display_var'):
                app.interval_display_var.set(str(interval_int))
            if hasattr(app, 'interval_slider'):
                app.interval_slider.set(interval_int)
        except (ValueError, AttributeError):
            if hasattr(app, 'interval_display_var'):
                app.interval_display_var.set('60')
            if hasattr(app, 'interval_slider'):
                app.interval_slider.set(60)

        # Backward compatibility: map old "both" to "all"
        source_value = config.get('slideshow_source', 'both')
        if source_value == 'both':
            source_value = 'all'
        app.slideshow_source_var.set(app.SLIDESHOW_SOURCE_LABELS.get(source_value, 'All Images'))

        app.slideshow_order_var.set(config.get('slideshow_order', 'random'))

        app.slideshow_skip_duplicates_var.set(bool(config.get('slideshow_skip_duplicates', True)))

        app.slideshow.load_gallery(app.gallery_images or [])  # Wire gallery

        app.sync_slideshow_state()

        app.on_slideshow_toggle()  # Sync running state

        app.root.after(200, app.update_slideshow_status)


    def on_slideshow_toggle(self):

        app = self.app
        app.slideshow.start() if app.slideshow_enabled_var.get() else app.slideshow.stop()

        app.update_slideshow_status()


    def refresh_token_status(self):

        app = self.app
        token = get_huggingface_token()

        app.token_var.set(token)

        app.token_entry.config(show="*")

        app.token_toggle_btn.config(text="Show Token")

        app.token_preview_var.set(app.format_token_preview())

        app.status_var.set("Environment token loaded." if token else "No environment token found.")


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



            app.status_var.set(f"✓ Removed mapping for: '{from_word}'")

            app.expansion_status_var.set(f"Keyword expansion: Removed '{from_word}'")



        except Exception as e:

            app._dialog.error("Error", f"Could not remove mapping: {e}")


    def resolved_model_id(self):

        app = self.app
        choice = app.model_choice_var.get().strip()

        if choice == "Custom...":

            return app.custom_model_var.get().strip()

        # Look up model ID from the current provider's mapping
        provider = app.provider_var.get().strip()
        provider_info = app.PROVIDER_MODELS.get(provider, {})
        display_to_id = provider_info.get("display_to_id", {})
        return display_to_id.get(choice, "flux")


    def save_settings(self):

        app = self.app
        config = load_config()

        

        # Convert display theme name to internal name

        display_name = app.theme_var.get()

        config["app_theme"] = app.THEME_INTERNAL_NAMES.get(display_name, "darkforest")

        config["dimensions"] = app.get_current_dimensions()

        config["model_id"] = app.resolved_model_id() or "flux"

        # Save provider
        config["provider"] = app.provider_var.get().strip()

        # Save Cloudflare token if set
        cf_token = app.cloudflare_token_var.get().strip()
        if cf_token:
            config["cloudflare_token"] = cf_token
        # Save Cloudflare account ID if set
        cf_account_id = app.cloudflare_account_id_var.get().strip()
        if cf_account_id:
            config["cloudflare_account_id"] = cf_account_id

        config['slideshow_enabled'] = bool(app.slideshow_enabled_var.get())

        config['slideshow_interval'] = int(app.slideshow_interval_var.get() or 60)

        source_value = app.slideshow_source_var.get().strip()
        # Backward compatibility: map old "both" to "all"
        if source_value == 'both':
            source_value = 'all'
        config['slideshow_source'] = app.SLIDESHOW_LABEL_TO_VALUE.get(source_value, source_value.lower()) or 'all'

        

        # Save minimize to tray setting

        config['minimize_to_tray'] = bool(app.minimize_to_tray_enabled)

        config['slideshow_order'] = app.slideshow_order_var.get()

        config['slideshow_skip_duplicates'] = bool(app.slideshow_skip_duplicates_var.get())

        config["remember_settings"] = bool(app.remember_settings_var.get())
        config["auto_generate_on_startup"] = bool(app.auto_generate_on_startup_var.get())
        config["startup_subject"] = app.startup_subject_var.get().strip() or "frog"

        # Save Hugging Face token if provided
        token = app.token_var.get().strip()
        if token:
            config["huggingface_token"] = token

        

        # Save current prompt/builder state if remember is enabled

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

        # Always save negative prompt selections (user preference)
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

        # Always persist wallpaper output format and quality
        config['wallpaper_format'] = app.wallpaper_format_var.get()
        config['wallpaper_quality'] = app.wallpaper_quality_var.get()

        # Always persist core settings regardless of remember_settings
        save_config(config)

        app.status_var.set("Settings saved.")

        app.sync_slideshow_state()

        app._dialog.info("Settings", "Settings saved successfully.")


    def setup_scheduler_from_gui(self):

        app = self.app
        try:

            ok = create_task()

            if ok:

                app._dialog.info("Task Scheduler", "Morning auto-wallpaper task created successfully.")

                app.status_var.set("Task Scheduler setup complete.")

            else:

                app._dialog.warning("Task Scheduler", "Task setup did not complete successfully.")

                app.status_var.set("Task Scheduler setup may have failed.")

        except Exception as e:

            app._dialog.error("Task Scheduler", f"Could not create scheduled task.\n\n{e}")

            app.status_var.set("Task Scheduler setup failed.")


    def slideshow_next_now(self):

        app = self.app
        app.slideshow.next_now()


    def slideshow_pause_click(self):

        app = self.app
        if app.slideshow.paused:
            app.slideshow.resume()
        else:
            app.slideshow.pause()
        app.update_slideshow_status()


    def slideshow_prev_now(self):

        app = self.app
        app.slideshow.prev_wallpaper()


    def slideshow_preview_sources(self):

        app = self.app
        source_value = app.SLIDESHOW_LABEL_TO_VALUE.get(app.slideshow_source_var.get().strip(), app.slideshow_source_var.get().strip().lower()) or 'all'
        candidates = app.slideshow.candidates(
            source=source_value,
            order=app.slideshow_order_var.get(),
            skip_duplicates=bool(app.slideshow_skip_duplicates_var.get())
        )

        lines = [f'Eligible images: {len(candidates)}']
        lines.append(f'Source: {app.slideshow_source_var.get()}')

        for i, p in enumerate(candidates[:30]):

            lines.append(f'{i+1}. {p.name}')

        if len(candidates) > 30:

            lines.append(f'... and {len(candidates) - 30} more')

        app._dialog.info('Slideshow Sources', '\n'.join(lines))


    def slideshow_start_click(self):

        app = self.app
        app.slideshow_enabled_var.set(True)

        app.slideshow.start()

        app.update_slideshow_status()

        app.status_var.set('Slideshow started.')


    def slideshow_stop_click(self):

        app = self.app
        app.slideshow_enabled_var.set(False)

        app.slideshow.stop()

        app.update_slideshow_status()

        app.status_var.set('Slideshow stopped.')


    def sync_slideshow_state(self):

        """Pass app.UI variables to the SlideshowManager instance."""

        app = self.app
        if not hasattr(app, 'slideshow_source_var'):

            return # Too early

        app.slideshow.slideshow_enabled_var = app.slideshow_enabled_var

        app.slideshow.slideshow_interval_var = app.slideshow_interval_var

        app.slideshow.slideshow_source_var = app.slideshow_source_var

        app.slideshow.slideshow_order_var = app.slideshow_order_var

        app.slideshow.slideshow_skip_duplicates_var = app.slideshow_skip_duplicates_var


    def toggle_token_visibility(self):

        app = self.app
        if app.token_entry.cget("show") == "*":

            app.token_entry.config(show="")

            app.token_toggle_btn.config(text="Hide Token")

        else:

            app.token_entry.config(show="*")

            app.token_toggle_btn.config(text="Show Token")


    def update_slideshow_status(self):

        app = self.app
        app.slideshow_status_var.set(app.slideshow.status_text())
        if hasattr(app, 'slideshow_pause_btn'):
            if app.slideshow.paused:
                app.slideshow_pause_btn.config(text=" Resume", style="Active.TButton")
            else:
                app.slideshow_pause_btn.config(text=" Pause", style="TButton")
        
        # Update visual countdown if running
        if app.slideshow.running and not app.slideshow.paused and app.slideshow.last_run:
            try:
                interval_mins = float(app.slideshow_interval_var.get())
                elapsed = (datetime.now() - app.slideshow.last_run).total_seconds()
                total = interval_mins * 60
                remaining = max(0, total - elapsed)
                
                # Format remaining time
                mins, secs = divmod(int(remaining), 60)
                time_str = f"{mins:02d}:{secs:02d}"

                progress_pct = min(100, (elapsed / total) * 100)
                app.progress.config(mode="determinate", value=progress_pct)
                app.progress.grid()

                # Show descriptive timer
                app.progress_overlay_label.config(text=f"Next Wallpaper in {time_str}")
                app.progress_overlay_label.place(relx=0.5, rely=0.5, anchor="center")
                
                # Theming the overlay label
                pal = app.THEMES.get(app.current_theme_name, app.THEMES["darkforest"])
                accent = pal.get("accent", pal["progress"])
                app.progress_overlay_label.config(bg=accent, fg=pal["button_fg"])
            except:
                pass
        else:
            app.progress["value"] = 0
            app.progress_overlay_label.config(text="")
            
        app.root.after(1000, app.update_slideshow_status)
