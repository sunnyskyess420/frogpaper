"""Category-builder methods for the Settings tab (roadmap #7 Phase A).

Hosts the eight sidebar section builders (General, Generation,
Appearance, Startup, Slideshow, Cloud, Advanced, Help) that were
previously defined inline in settings_tab.py.  They are mixed into the
single ``SettingsTab`` class (see settings_tab.py), so behaviour is
unchanged: each builder registers its frame in
``self._category_frames`` and wires widgets onto ``self.app``.
"""

import tkinter as tk
from tkinter import ttk

from utils import load_config

from settings_components import (
    CloudProviderCard,
    HelpResourceCard,
    SettingCard,
)
from settings_ux_data import CLOUD_PROVIDER_UX

from theme import COLOR_ACCENT, COLOR_GRAY_700  # shared color constants (migrated inline hex)

# Pinned Dropdown Options feature (since v1.4.1 - Favorite Items)
try:
    from pinned_dropdowns import build_pinned_settings_ui
    PINNED_AVAILABLE = True
except ImportError:
    PINNED_AVAILABLE = False


class SettingsCategoriesMixin:
    """Sidebar section builders for SettingsTab (mixed in, no state)."""

    # ================================================================
    # CATEGORY BUILDERS
    # ================================================================

    def _build_general_category(self, parent, pal):
        """Build General settings category."""
        app = self.app
        frame = tk.Frame(parent, bg=pal["bg"])
        self._category_frames["general"] = frame
        
        # Header
        header = tk.Label(frame, text="General", font=("Segoe UI", 18, "bold"),
                         fg=pal["text"], bg=pal["bg"], anchor="w")
        header.pack(fill="x", pady=20)
        
        # App Theme card
        theme_card = SettingCard(frame, "App Theme", 
                                "Choose your preferred color theme for FrogPaper.",
                                pal, pal.get("accent", COLOR_ACCENT))
        
        config = load_config()
        app.theme_var = tk.StringVar(
            value=app.THEME_DISPLAY_NAMES.get(config.get("app_theme", "darkforest"), "Forest Green — Dark")
        )
        theme_combo = ttk.Combobox(
            theme_card.get_content(),
            textvariable=app.theme_var,
            values=list(app.THEME_DISPLAY_NAMES.values()),
            state="readonly",
            width=30
        )
        theme_combo.pack(fill="x", pady=8)
        theme_combo.bind("<<ComboboxSelected>>", lambda e: [app.on_theme_changed(), self._mark_dirty()])
        theme_combo.bind("<MouseWheel>", lambda e: "break")
        
        # Resolution card
        res_card = SettingCard(frame, "Wallpaper Resolution",
                               "Set the default resolution for generated wallpapers.",
                               pal, pal.get("accent", COLOR_ACCENT))
        
        if not hasattr(app, 'dimension_preset_var'):
            app.dimension_preset_var = tk.StringVar(value="16:9 (1080p)")
        res_combo = ttk.Combobox(
            res_card.get_content(),
            textvariable=app.dimension_preset_var,
            values=list(app.DIMENSION_PRESETS.keys()),
            state="readonly",
            width=25
        )
        res_combo.pack(fill="x", pady=8)
        res_combo.bind("<<ComboboxSelected>>", lambda e: [self._on_dimension_preset_changed(), self._mark_dirty()])
        res_combo.bind("<MouseWheel>", lambda e: "break")

    def _build_generation_category(self, parent, pal):
        """Build Generation settings category."""
        app = self.app
        frame = tk.Frame(parent, bg=pal["bg"])
        self._category_frames["generation"] = frame
        
        header = tk.Label(frame, text="Generation", font=("Segoe UI", 18, "bold"),
                         fg=pal["text"], bg=pal["bg"], anchor="w")
        header.pack(fill="x", pady=20)
        
        # Provider card
        provider_card = SettingCard(frame, "AI Provider",
                                     "Select the AI service for generating wallpapers.",
                                     pal, pal.get("accent", COLOR_ACCENT))
        
        saved_provider = load_config().get("provider", "Pollinations.ai (Free - No Key)")
        app.provider_var = tk.StringVar(value=saved_provider)
        provider_combo = ttk.Combobox(
            provider_card.get_content(),
            textvariable=app.provider_var,
            values=app.PROVIDER_OPTIONS,
            state="readonly",
            width=40
        )
        provider_combo.pack(fill="x", pady=8)
        provider_combo.bind("<<ComboboxSelected>>", lambda e: [self._on_provider_changed(), self._mark_dirty()])
        provider_combo.bind("<MouseWheel>", lambda e: "break")
        
        app.provider_desc_var = tk.StringVar(value="")
        desc_label = tk.Label(
            provider_card.get_content(),
            textvariable=app.provider_desc_var,
            font=("Segoe UI", 9),
            fg=pal["muted"],
            bg=pal["card_bg"],
            wraplength=600,
            justify="left"
        )
        desc_label.pack(fill="x", pady=8)
        self._update_provider_description()
        
        # Provider Setup card (dynamic - shows relevant fields for selected provider)
        setup_card = SettingCard(frame, "Provider Setup",
                                 "Configure your selected AI provider.",
                                 pal, pal.get("accent", COLOR_ACCENT))
        app.provider_setup_card = setup_card
        setup_content = setup_card.get_content()

        # Container frame for dynamic key fields (cleared/rebuilt on provider change)
        app.provider_fields_frame = tk.Frame(setup_content, bg=pal["card_bg"])
        app.provider_fields_frame.pack(fill="x", pady=4)

        # Container frame for dynamic setup guide (cleared/rebuilt on provider change)
        app.provider_guide_frame = tk.Frame(setup_content, bg=pal["card_bg"])
        app.provider_guide_frame.pack(fill="x", pady=4)

        # Import here to avoid issues

        # Build initial provider fields
        self._rebuild_provider_setup(saved_provider, pal)

        # Model card
        model_card = SettingCard(frame, "AI Model",
                                  "Select the specific AI model to use.",
                                  pal, pal.get("accent", COLOR_ACCENT))
        
        saved_model_id = load_config().get("model_id", "flux")
        provider_info = app.PROVIDER_MODELS.get(saved_provider, app.PROVIDER_MODELS.get("Pollinations.ai (Free - No Key)", {}))
        provider_models = provider_info.get("options", [])
        provider_display_to_id = provider_info.get("display_to_id", {})
        provider_id_to_display = {v: k for k, v in provider_display_to_id.items()}
        initial_display = provider_id_to_display.get(saved_model_id, provider_models[0] if provider_models else "FLUX (Default)")
        
        app.model_choice_var = tk.StringVar(value=initial_display)
        model_combo = ttk.Combobox(
            model_card.get_content(),
            textvariable=app.model_choice_var,
            values=provider_models,
            state="readonly",
            width=40
        )
        model_combo.pack(fill="x", pady=8)
        app.model_choice_combo = model_combo
        model_combo.bind("<<ComboboxSelected>>", lambda e: [self._on_model_choice_changed(), self._mark_dirty()])
        model_combo.bind("<MouseWheel>", lambda e: "break")
        
        app.custom_model_var = tk.StringVar(value=saved_model_id if initial_display == "Custom..." else "")
        app.custom_model_entry = ttk.Entry(model_card.get_content(), textvariable=app.custom_model_var, width=58)
        app.configure_entry_cursor(app.custom_model_entry)
        if initial_display == "Custom...":
            app.custom_model_entry.pack(fill="x", pady=8)
        
        # Provider-specific model list is updated by _on_provider_changed -> _rebuild_provider_setup

    def _build_appearance_category(self, parent, pal):
        """Build Appearance settings category."""
        app = self.app
        frame = tk.Frame(parent, bg=pal["bg"])
        self._category_frames["appearance"] = frame
        
        header = tk.Label(frame, text="Appearance", font=("Segoe UI", 18, "bold"),
                         fg=pal["text"], bg=pal["bg"], anchor="w")
        header.pack(fill="x", pady=20)
        
        # Wallpaper Output card
        output_card = SettingCard(frame, "Wallpaper Output",
                                  "Configure the format and quality of saved wallpapers.",
                                  pal, pal.get("accent", COLOR_ACCENT))
        
        format_frame = tk.Frame(output_card.get_content(), bg=pal["card_bg"])
        format_frame.pack(fill="x", pady=8)
        
        if not hasattr(app, 'wallpaper_format_var'):
            app.wallpaper_format_var = tk.StringVar(value='PNG')
        if not hasattr(app, 'wallpaper_quality_var'):
            app.wallpaper_quality_var = tk.StringVar(value='High')
        
        tk.Label(format_frame, text="Format:", font=("Segoe UI", 10),
                fg=pal["text"], bg=pal["card_bg"]).pack(side="left")
        format_combo = ttk.Combobox(format_frame, textvariable=app.wallpaper_format_var,
                                    values=['PNG', 'JPEG', 'WebP'], state="readonly", width=12)
        format_combo.pack(side="left", padx=16)
        format_combo.bind("<<ComboboxSelected>>", lambda e: self._mark_dirty())
        format_combo.bind("<MouseWheel>", lambda e: "break")
        
        tk.Label(format_frame, text="Quality:", font=("Segoe UI", 10),
                fg=pal["text"], bg=pal["card_bg"]).pack(side="left")
        quality_combo = ttk.Combobox(format_frame, textvariable=app.wallpaper_quality_var,
                                     values=['Maximum', 'High', 'Medium', 'Low'], state="readonly", width=12)
        quality_combo.pack(side="left", padx=8)
        quality_combo.bind("<<ComboboxSelected>>", lambda e: self._mark_dirty())
        quality_combo.bind("<MouseWheel>", lambda e: "break")
        
        helper_label = tk.Label(
            output_card.get_content(),
            text="Lower quality = smaller file size, minimal visual difference at desktop size",
            font=("Segoe UI", 9),
            fg=pal["muted"],
            bg=pal["card_bg"],
            wraplength=600
        )
        helper_label.pack(fill="x", pady=8)

    def _build_startup_category(self, parent, pal):
        """Build Startup settings category."""
        app = self.app
        frame = tk.Frame(parent, bg=pal["bg"])
        self._category_frames["startup"] = frame
        
        header = tk.Label(frame, text="Startup", font=("Segoe UI", 18, "bold"),
                         fg=pal["text"], bg=pal["bg"], anchor="w")
        header.pack(fill="x", pady=20)
        
        # Run on Startup card
        startup_card = SettingCard(frame, "Run on Startup",
                                   "Configure how FrogPaper behaves when Windows starts.",
                                   pal, pal.get("accent", COLOR_ACCENT))
        
        app.run_on_startup_var = tk.BooleanVar(value=app.run_on_startup_enabled)
        startup_check = tk.Checkbutton(
            startup_card.get_content(),
            text="Launch FrogPaper when Windows starts",
            variable=app.run_on_startup_var,
            font=("Segoe UI", 10),
            fg=pal["text"],
            bg=pal["card_bg"],
            selectcolor=pal.get("entrybg", pal["card_bg"]),
            activebackground=pal["card_bg"],
            activeforeground=pal["text"],
            command=lambda: [app._on_run_on_startup_changed(), self._mark_dirty()]
        )
        startup_check.pack(fill="x", pady=8, anchor="w")
        
        # Auto-generate card
        gen_card = SettingCard(frame, "Auto-Generate on Launch",
                               "Automatically generate a wallpaper when FrogPaper starts.",
                               pal, pal.get("accent", COLOR_ACCENT))
        
        gen_check = tk.Checkbutton(
            gen_card.get_content(),
            text="Generate a fresh random wallpaper each launch",
            variable=app.auto_generate_on_startup_var,
            font=("Segoe UI", 10),
            fg=pal["text"],
            bg=pal["card_bg"],
            selectcolor=pal.get("entrybg", pal["card_bg"]),
            activebackground=pal["card_bg"],
            activeforeground=pal["text"],
            command=self._mark_dirty
        )
        gen_check.pack(fill="x", pady=8, anchor="w")
        
        # Startup subject
        subject_frame = tk.Frame(gen_card.get_content(), bg=pal["card_bg"])
        subject_frame.pack(fill="x", pady=8)
        
        tk.Label(subject_frame, text="Startup subject:", font=("Segoe UI", 10),
                fg=pal["text"], bg=pal["card_bg"]).pack(side="left")
        startup_subj_entry = ttk.Entry(subject_frame, textvariable=app.startup_subject_var, width=25)
        startup_subj_entry.pack(side="left", padx=8)
        app.configure_entry_cursor(startup_subj_entry)
        
        helper_label = tk.Label(
            gen_card.get_content(),
            text="Leave as 'frog' for classic frogs, or change to any subject you like",
            font=("Segoe UI", 9),
            fg=pal["muted"],
            bg=pal["card_bg"],
            wraplength=600
        )
        helper_label.pack(fill="x", pady=8)
        
        # Minimize to Tray card
        tray_card = SettingCard(frame, "System Tray",
                                "Control how FrogPaper behaves when minimized.",
                                pal, pal.get("accent", COLOR_ACCENT))
        
        app.minimize_to_tray_var = tk.BooleanVar(value=app.minimize_to_tray_enabled)
        tray_check = tk.Checkbutton(
            tray_card.get_content(),
            text="Minimize to system tray instead of taskbar",
            variable=app.minimize_to_tray_var,
            font=("Segoe UI", 10),
            fg=pal["text"],
            bg=pal["card_bg"],
            selectcolor=pal.get("entrybg", pal["card_bg"]),
            activebackground=pal["card_bg"],
            activeforeground=pal["text"],
            command=lambda: [app._on_minimize_to_tray_changed(), self._mark_dirty()]
        )
        tray_check.pack(fill="x", pady=8, anchor="w")

    def _build_slideshow_category(self, parent, pal):
        """Build Slideshow settings category."""
        app = self.app
        frame = tk.Frame(parent, bg=pal["bg"])
        self._category_frames["slideshow"] = frame
        
        header = tk.Label(frame, text="Slideshow", font=("Segoe UI", 18, "bold"),
                         fg=pal["text"], bg=pal["bg"], anchor="w")
        header.pack(fill="x", pady=20)
        
        # Slideshow Control card
        control_card = SettingCard(frame, "Slideshow Control",
                                   "Enable and configure the in-app wallpaper slideshow.",
                                   pal, pal.get("accent", COLOR_ACCENT))
        
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
        self.sync_slideshow_state()
        
        enable_check = tk.Checkbutton(
            control_card.get_content(),
            text="Enable in-app slideshow",
            variable=app.slideshow_enabled_var,
            font=("Segoe UI", 10),
            fg=pal["text"],
            bg=pal["card_bg"],
            selectcolor=pal.get("entrybg", pal["card_bg"]),
            activebackground=pal["card_bg"],
            activeforeground=pal["text"],
            command=lambda: [self.on_slideshow_toggle(), self._mark_dirty()]
        )
        enable_check.pack(fill="x", pady=8, anchor="w")
        
        # Interval slider
        interval_frame = tk.Frame(control_card.get_content(), bg=pal["card_bg"])
        interval_frame.pack(fill="x", pady=12)
        
        tk.Label(interval_frame, text="Interval:", font=("Segoe UI", 10),
                fg=pal["text"], bg=pal["card_bg"]).pack(side="left")
        
        if not hasattr(app, 'interval_display_var'):
            app.interval_display_var = tk.StringVar(value='60')
        interval_display = tk.Label(interval_frame, textvariable=app.interval_display_var,
                                   font=("Segoe UI", 10, "bold"), fg=pal.get("accent", COLOR_ACCENT),
                                   bg=pal["card_bg"])
        interval_display.pack(side="right")
        
        def on_interval_change(value):
            val = int(float(value))
            app.slideshow_interval_var.set(str(val))
            app.interval_display_var.set(str(val))
            self._mark_dirty()
        
        app.interval_slider = ttk.Scale(control_card.get_content(), from_=1, to=60, 
                                       orient='horizontal', command=on_interval_change)
        try:
            initial_val = int(float(app.slideshow_interval_var.get()))
            app.interval_slider.set(max(1, min(60, initial_val)))
        except Exception:
            app.interval_slider.set(60)
        app.interval_slider.pack(fill="x", pady=8)
        
        helper_label = tk.Label(
            control_card.get_content(),
            text="Adjust the slider to set how often wallpapers rotate (1-60 minutes)",
            font=("Segoe UI", 9),
            fg=pal["muted"],
            bg=pal["card_bg"]
        )
        helper_label.pack(fill="x", pady=4)
        
        # Source & Order card
        source_card = SettingCard(frame, "Source & Order",
                                  "Choose which wallpapers to show and in what order.",
                                  pal, pal.get("accent", COLOR_ACCENT))
        
        source_frame = tk.Frame(source_card.get_content(), bg=pal["card_bg"])
        source_frame.pack(fill="x", pady=8)
        source_frame.columnconfigure(1, weight=1)
        
        tk.Label(source_frame, text="Source:", font=("Segoe UI", 10),
                fg=pal["text"], bg=pal["card_bg"]).grid(row=0, column=0, sticky="w", padx=8)
        source_combo = ttk.Combobox(source_frame, textvariable=app.slideshow_source_var,
                                    values=app.SLIDESHOW_SOURCE_DISPLAY, state='readonly', width=20)
        source_combo.grid(row=0, column=1, sticky="w")
        source_combo.bind("<<ComboboxSelected>>", self._mark_dirty)
        source_combo.bind("<MouseWheel>", lambda e: "break")
        
        tk.Label(source_frame, text="Order:", font=("Segoe UI", 10),
                fg=pal["text"], bg=pal["card_bg"]).grid(row=1, column=0, sticky="w", padx=8, pady=8)
        order_combo = ttk.Combobox(source_frame, textvariable=app.slideshow_order_var,
                                    values=['random', 'newest', 'oldest'], state='readonly', width=20)
        order_combo.grid(row=1, column=1, sticky="w", pady=8)
        order_combo.bind("<<ComboboxSelected>>", self._mark_dirty)
        order_combo.bind("<MouseWheel>", lambda e: "break")
        
        skip_check = tk.Checkbutton(
            source_card.get_content(),
            text="Skip duplicates (no repeat until all shown)",
            variable=app.slideshow_skip_duplicates_var,
            font=("Segoe UI", 10),
            fg=pal["text"],
            bg=pal["card_bg"],
            selectcolor=pal.get("entrybg", pal["card_bg"]),
            activebackground=pal["card_bg"],
            activeforeground=pal["text"],
            command=self._mark_dirty
        )
        skip_check.pack(fill="x", pady=12, anchor="w")

    def _build_cloud_category(self, parent, pal):
        """Build Cloud & Backup settings category."""
        app = self.app
        frame = tk.Frame(parent, bg=pal["bg"])
        self._category_frames["cloud"] = frame
        
        header = tk.Label(frame, text="Cloud & Backup", font=("Segoe UI", 18, "bold"),
                         fg=pal["text"], bg=pal["bg"], anchor="w")
        header.pack(fill="x", pady=20)
        
        # Cloud Providers section
        providers_header = tk.Label(frame, text="Cloud Providers", font=("Segoe UI", 14, "bold"),
                                   fg=pal["text"], bg=pal["bg"], anchor="w")
        providers_header.pack(fill="x", pady=12)
        
        providers_desc = tk.Label(frame, text="Connect cloud storage for backup and sync.",
                                 font=("Segoe UI", 10), fg=pal["muted"], bg=pal["bg"], anchor="w")
        providers_desc.pack(fill="x", pady=12)
        
        # Build cloud provider cards
        self._cloud_provider_cards = {}
        for prov_key, ux_info in CLOUD_PROVIDER_UX.items():
            card = CloudProviderCard(frame, prov_key, ux_info, pal, app)
            self._cloud_provider_cards[prov_key] = card
        
        # Sync Settings card
        sync_card = SettingCard(frame, "Sync Settings",
                               "Configure automatic backup and sync behavior.",
                               pal, pal.get("accent", COLOR_ACCENT))
        
        app.auto_backup_var = tk.BooleanVar(value=load_config().get("auto_backup_enabled", False))
        
        backup_check = tk.Checkbutton(
            sync_card.get_content(),
            text="Enable automatic daily backups",
            variable=app.auto_backup_var,
            font=("Segoe UI", 10),
            fg=pal["text"],
            bg=pal["card_bg"],
            selectcolor=pal.get("entrybg", pal["card_bg"]),
            activebackground=pal["card_bg"],
            activeforeground=pal["text"],
            command=self._mark_dirty
        )
        backup_check.pack(fill="x", pady=8, anchor="w")
        
        # Backup time
        time_frame = tk.Frame(sync_card.get_content(), bg=pal["card_bg"])
        time_frame.pack(fill="x", pady=8)
        
        _cfg = load_config()
        saved_hour = _cfg.get("auto_backup_hour", 2)
        saved_minute = _cfg.get("auto_backup_minute", 0)
        app.auto_backup_hour_var = tk.StringVar(value=f"{saved_hour:02d}:{saved_minute:02d}")
        
        tk.Label(time_frame, text="Backup time:", font=("Segoe UI", 10),
                fg=pal["text"], bg=pal["card_bg"]).pack(side="left")
        time_entry = tk.Entry(time_frame, textvariable=app.auto_backup_hour_var, width=8,
                             font=("Segoe UI", 10), fg=pal["text"], bg=pal.get("entrybg", pal["card_bg"]),
                             insertbackground=pal["text"], relief="solid", bd=1)
        time_entry.pack(side="left", padx=8)
        app.configure_entry_cursor(time_entry)
        
        tk.Label(time_frame, text="(HH:MM, 24h)", font=("Segoe UI", 9),
                fg=pal["muted"], bg=pal["card_bg"]).pack(side="left")
        
        # Last backup status
        app.last_backup_var = tk.StringVar(value="Last backup: Never")
        backup_status = tk.Label(sync_card.get_content(), textvariable=app.last_backup_var,
                                font=("Segoe UI", 9), fg=pal["muted"], bg=pal["card_bg"])
        backup_status.pack(fill="x", pady=8, anchor="w")
        
        # Sync button
        sync_btn_frame = tk.Frame(sync_card.get_content(), bg=pal["card_bg"])
        sync_btn_frame.pack(fill="x", pady=8)
        
        ttk.Button(sync_btn_frame, text="Sync Now", command=app._manual_sync).pack(side="left")
        app.sync_status_var = tk.StringVar(value="Ready")
        tk.Label(sync_btn_frame, textvariable=app.sync_status_var, font=("Segoe UI", 9),
                fg=pal["muted"], bg=pal["card_bg"]).pack(side="left", padx=8)
        
        # Sync scope
        tk.Frame(sync_card.get_content(), bg=pal.get("border_color", COLOR_GRAY_700), 
                height=1).pack(fill="x", pady=16)
        
        tk.Label(sync_card.get_content(), text="Sync Scope:", font=("Segoe UI", 10, "bold"),
                fg=pal["text"], bg=pal["card_bg"]).pack(anchor="w")
        
        sync_frame = tk.Frame(sync_card.get_content(), bg=pal["card_bg"])
        sync_frame.pack(fill="x", pady=8)
        
        config = load_config()
        sync_scope = config.get("sync_scope", "everything")
        app.sync_scope_var = tk.StringVar(value=sync_scope)
        
        for scope_label, scope_val in [("All Wallpapers", "everything"), ("Favorites Only", "favorites")]:
            tk.Radiobutton(sync_frame, text=scope_label, variable=app.sync_scope_var,
                           value=scope_val, font=("Segoe UI", 10),
                           fg=pal["text"], bg=pal["card_bg"], 
                           selectcolor=pal.get("entrybg", pal["card_bg"]),
                           activebackground=pal["card_bg"], activeforeground=pal["text"],
                           command=self._mark_dirty).pack(side="left", padx=16)
        
        helper_label = tk.Label(sync_card.get_content(),
                               text="Choose what to sync to cloud storage",
                               font=("Segoe UI", 9), fg=pal["muted"], bg=pal["card_bg"])
        helper_label.pack(fill="x", pady=8)

    def _build_advanced_category(self, parent, pal):
        """Build Advanced settings category."""
        app = self.app
        frame = tk.Frame(parent, bg=pal["bg"])
        self._category_frames["advanced"] = frame
        
        header = tk.Label(frame, text="Advanced", font=("Segoe UI", 18, "bold"),
                         fg=pal["text"], bg=pal["bg"], anchor="w")
        header.pack(fill="x", pady=20)
        
        # Generation Behavior card
        gen_card = SettingCard(frame, "Generation Behavior",
                               "Fine-tune how prompts are constructed.",
                               pal, pal.get("accent", COLOR_ACCENT))
        
        smart_neg_check = tk.Checkbutton(
            gen_card.get_content(),
            text="Smart Negatives",
            variable=app.smart_neg_var,
            font=("Segoe UI", 10),
            fg=pal["text"],
            bg=pal["card_bg"],
            selectcolor=pal.get("entrybg", pal["card_bg"]),
            activebackground=pal["card_bg"],
            activeforeground=pal["text"],
            command=self._mark_dirty
        )
        smart_neg_check.pack(fill="x", pady=8, anchor="w")
        
        neg_helper = tk.Label(gen_card.get_content(),
                             text="Scan the generated prompt for keywords (e.g. portrait, forest) and inject matching negative terms.",
                             font=("Segoe UI", 9), fg=pal["muted"], bg=pal["card_bg"], wraplength=600)
        neg_helper.pack(fill="x", pady=12, anchor="w")
        
        subj_lock_check = tk.Checkbutton(
            gen_card.get_content(),
            text="Keep subject exact",
            variable=app.subject_lock_var,
            font=("Segoe UI", 10),
            fg=pal["text"],
            bg=pal["card_bg"],
            selectcolor=pal.get("entrybg", pal["card_bg"]),
            activebackground=pal["card_bg"],
            activeforeground=pal["text"],
            command=self._mark_dirty
        )
        subj_lock_check.pack(fill="x", pady=4, anchor="w")
        
        subj_helper = tk.Label(gen_card.get_content(),
                               text="Use your typed subject as-is. When off, mood adjectives (e.g. serene, vibrant) may be prefixed.",
                               font=("Segoe UI", 9), fg=pal["muted"], bg=pal["card_bg"], wraplength=600)
        subj_helper.pack(fill="x", pady=4, anchor="w")
        
        # Keyword Expansion card
        kw_card = SettingCard(frame, "Keyword Expansion",
                             "Create custom word mappings for prompt enhancement.",
                             pal, pal.get("accent", COLOR_ACCENT))
        
        kw_frame = tk.Frame(kw_card.get_content(), bg=pal["card_bg"])
        kw_frame.pack(fill="x", pady=8)
        
        tk.Label(kw_frame, text="When I type:", font=("Segoe UI", 10),
                fg=pal["text"], bg=pal["card_bg"]).pack(side="left", padx=8)
        app.from_word_var = tk.StringVar()
        app.from_word_entry = ttk.Entry(kw_frame, textvariable=app.from_word_var, width=14)
        app.from_word_entry.pack(side="left", padx=8)
        app.configure_entry_cursor(app.from_word_entry)
        
        tk.Label(kw_frame, text="→", font=("Segoe UI", 10),
                fg=pal["text"], bg=pal["card_bg"]).pack(side="left", padx=8)
        
        app.to_word_var = tk.StringVar()
        app.to_word_entry = ttk.Entry(kw_frame, textvariable=app.to_word_var, width=14)
        app.to_word_entry.pack(side="left", padx=8)
        app.configure_entry_cursor(app.to_word_entry)
        
        btn_frame = tk.Frame(kw_frame, bg=pal["card_bg"])
        btn_frame.pack(side="left")
        
        ttk.Button(btn_frame, text="Add", command=lambda: [self.add_user_mapping(), self._mark_dirty()]).pack(side="left", padx=4)
        ttk.Button(btn_frame, text="Remove", command=lambda: [self.remove_user_mapping(), self._mark_dirty()]).pack(side="left")
        
        kw_helper = tk.Label(kw_card.get_content(),
                            text="e.g. awesome → epic, gloomy → moody",
                            font=("Segoe UI", 9), fg=pal["muted"], bg=pal["card_bg"])
        kw_helper.pack(fill="x", pady=8)
        
        app.expansion_status_var = tk.StringVar(value="Keyword expansion: Ready")
        status_label = tk.Label(kw_card.get_content(), textvariable=app.expansion_status_var,
                                font=("Segoe UI", 9), fg=pal["muted"], bg=pal["card_bg"])
        status_label.pack(fill="x", pady=8)

        # Pinned Dropdown Options card (since v1.4.1)
        if PINNED_AVAILABLE:
            pin_card = SettingCard(frame, "Favorite Dropdown Items",
                                   "Pin your favorite items to the top of dropdown lists.",
                                   pal, pal.get("accent", COLOR_ACCENT))
            try:
                build_pinned_settings_ui(pin_card.get_content(), app)
            except Exception:
                pass

    def _build_help_category(self, parent, pal):
        """Build Help settings category."""
        app = self.app
        frame = tk.Frame(parent, bg=pal["bg"])
        self._category_frames["help"] = frame
        
        header = tk.Label(frame, text="Help", font=("Segoe UI", 18, "bold"),
                         fg=pal["text"], bg=pal["bg"], anchor="w")
        header.pack(fill="x", pady=20)
        
        # Version info card
        try:
            from app import APP_VERSION as _VER
        except Exception:
            _VER = '?.?.?'
        version_frame = tk.Frame(frame, bg=pal.get("card_bg", pal["bg"]),
                                highlightthickness=1, highlightbackground=pal.get("border_color", COLOR_GRAY_700))
        version_frame.pack(fill="x", pady=(0, 12), ipady=8, ipadx=12)
        version_info = tk.Label(version_frame,
                               text=f"FrogPaper v{_VER}  |  Built for Windows 10+",
                               font=("Segoe UI", 10), fg=pal["muted"], bg=pal.get("card_bg", pal["bg"]))
        version_info.pack(anchor="w", padx=12, pady=4)

        # What's New in <current version> - header auto-follows APP_VERSION
        wn_header = tk.Label(frame, text=f"What's New in v{_VER}", font=("Segoe UI", 14, "bold"),
                             fg=pal["text"], bg=pal["bg"], anchor="w")
        wn_header.pack(fill="x", pady=(16, 8))

        changes = [
            ("Speed", "Gallery views open instantly - thumbnails decode in the background with caching, image sizes are remembered, resizing no longer rebuilds the grid on every pixel"),
            ("Reliability", "Tag database reads are cached and kept in sync automatically; file problems in the gallery now show friendly error dialogs instead of crashes"),
            ("Keyboard", "Every button and dropdown is reachable with Tab and activated with Enter or Space, with visible focus rings; Tab can no longer get stuck inside text boxes"),
            ("Prompt Engine", "Your capitalization is preserved on words that aren't expanded, and thesaurus mapping edits apply immediately without a restart"),
            ("Docs & Tests", "New CONFIG_GUIDE.md, 296 automated tests, and a GitHub Actions workflow that runs the full suite on Windows with every push"),
        ]
        for category, desc in changes:
            row = tk.Frame(frame, bg=pal["bg"])
            row.pack(fill="x", pady=2)
            tk.Label(row, text=category, font=("Segoe UI", 9, "bold"),
                    fg=pal.get("accent", COLOR_ACCENT), bg=pal["bg"], width=14, anchor="nw").pack(side="left")
            tk.Label(row, text=desc, font=("Segoe UI", 9),
                    fg=pal["muted"], bg=pal["bg"], anchor="w", wraplength=500, justify="left").pack(side="left")

        # Previous versions (release history)
        pv_header = tk.Label(frame, text="Previous versions", font=("Segoe UI", 11, "bold"),
                             fg=pal["muted"], bg=pal["bg"], anchor="w")
        pv_header.pack(fill="x", pady=(16, 4))
        history = [
            ("v1.4.1", "Gallery scroll fix after switching views; crash fixes across color parsing, dialogs, themes and wallpaper module; thread-safe thumbnails"),
            ("v1.4.0", "Six AI providers, dynamic provider setup UI, universal resolution auto-resize, faster Replicate polling"),
            ("v1.3.2", "Star pins inside dropdowns, redesigned settings page, safer credential handling, theme rendering repaired"),
        ]
        for version, desc in history:
            row = tk.Frame(frame, bg=pal["bg"])
            row.pack(fill="x", pady=1)
            tk.Label(row, text=version, font=("Segoe UI", 9, "bold"),
                    fg=pal["muted"], bg=pal["bg"], width=14, anchor="nw").pack(side="left")
            tk.Label(row, text=desc, font=("Segoe UI", 8),
                    fg=pal["muted"], bg=pal["bg"], anchor="w", wraplength=500, justify="left").pack(side="left")

        # Getting Started section
        gs_header = tk.Label(frame, text="Getting Started", font=("Segoe UI", 14, "bold"),
                             fg=pal["text"], bg=pal["bg"], anchor="w")
        gs_header.pack(fill="x", pady=12)
        
        # Help resource cards
        HelpResourceCard(
            frame,
            "📖",
            "Quick Start Guide",
            "Learn the basics of FrogPaper in 5 minutes",
            "Start",
            lambda: app.tutorial_manager.start_tutorial("quick_start"),
            pal
        )
        
        HelpResourceCard(
            frame,
            "🎯",
            "Feature Tour",
            "Explore all major features of FrogPaper",
            "Start",
            lambda: app.tutorial_manager.start_tutorial("feature_tour"),
            pal
        )
        
        HelpResourceCard(
            frame,
            "✏",
            "Interactive Practice",
            "Guided wallpaper generation",
            "Start",
            lambda: app.tutorial_manager.start_tutorial("interactive_practice"),
            pal
        )
        
        # Browse All Tutorials button — opens the same menu as the gallery header button
        tutorials_btn = ttk.Button(frame, text="🎓  Browse All Tutorials",
                                   command=app._show_tutorial_menu)
        tutorials_btn.pack(fill="x", pady=(16, 8))
        
        # Tips section
        tips_header = tk.Label(frame, text="Tips & Shortcuts", font=("Segoe UI", 14, "bold"),
                             fg=pal["text"], bg=pal["bg"], anchor="w")
        tips_header.pack(fill="x", pady=(20, 12))
        
        shortcuts = [
            ("Ctrl + N", "Generate a new wallpaper"),
            ("Ctrl + S", "Open Settings"),
            ("Ctrl + Alt + N", "Advance slideshow (requires keyboard module)"),
            ("Escape", "Close current dialog"),
            ("Right-click image", "Context menu with set-as-wallpaper, favorite, etc."),
        ]
        for key, desc in shortcuts:
            row = tk.Frame(frame, bg=pal["bg"])
            row.pack(fill="x", pady=2)
            tk.Label(row, text=key, font=("Segoe UI", 9, "bold"),
                    fg=pal.get("accent", COLOR_ACCENT), bg=pal["bg"], width=18, anchor="w").pack(side="left")
            tk.Label(row, text=desc, font=("Segoe UI", 9),
                    fg=pal["muted"], bg=pal["bg"], anchor="w").pack(side="left")

