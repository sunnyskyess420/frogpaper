import tkinter as tk
import logging
import random
from pathlib import Path

from tkinter import ttk, messagebox, simpledialog

from negative_manager import (
    load_negative_presets,
    get_preset_names,
    get_preset_negatives,
    get_preset_description,
    build_final_negative_prompt,
)

from utils import (
    load_json_list,
    save_json_list,
    load_config,
    save_config,
    get_huggingface_token,
    has_huggingface_token,
    get_app_dir,
)


logger = logging.getLogger(__name__)


class PromptTab:
    """Prompt Builder tab: theme builder, templates, recipes, active-value getters/setters."""

    def __init__(self, app):
        self.app = app
    def _build_demoted_theme_builder(self, parent):
        """Build compact left-panel navigation shell. Prompt Builder Quick Build is the real editor."""
        app = self.app
        card = ttk.Labelframe(parent, text="Prompt Builder", padding=(10, 8))
        card.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        card.columnconfigure(0, weight=1)

        hint = ttk.Label(
            card,
            text="Build and edit prompts in the Prompt Builder tab.",
            wraplength=300,
            justify="left",
        )
        hint.grid(row=0, column=0, sticky="w", pady=(0, 8))

        ttk.Button(
            card,
            text="Open Prompt Builder →",
            command=app.activate_prompt_builder_tab,
        ).grid(row=1, column=0, sticky="w")


    def _build_templates_tab(self, parent):
        app = self.app
        try:
            from template_system import get_template_manager, get_recipe_manager, Template, Recipe
            app.template_manager = get_template_manager()
            app.recipe_manager = get_recipe_manager()
            app.template_available = True
            app.TemplateClass = Template
            app.RecipeClass = Recipe
        except ImportError as e:
            app.template_available = False
            app.template_manager = None
            app.recipe_manager = None
            app.TemplateClass = None
            app.RecipeClass = None
            logger.error("Template import failed:", e)

        app.templatemanager = app.template_manager
        app.recipemanager = app.recipe_manager
        app.templateavailable = app.template_available

        selectorframe = ttk.LabelFrame(parent, text="Select & Manage", padding=10)
        selectorframe.pack(fill="x", pady=(0, 10))

        row1 = ttk.Frame(selectorframe)
        row1.pack(fill="x", pady=(0, 6))

        ttk.Label(row1, text="Prompt:").pack(side="left", padx=(0, 6))
        app.template_var = tk.StringVar(value="")
        app.templatevar = app.template_var

        app.template_combo = ttk.Combobox(
            row1,
            textvariable=app.template_var,
            width=34,
            state="readonly",
        )
        app.templatecombo = app.template_combo
        app.template_combo.pack(side="left", padx=(0, 8))
        app.template_combo.bind("<<ComboboxSelected>>", app.ontemplateselected)

        app._btn_tpl_refresh = ttk.Button(row1, text=" Refresh",
                   command=app.refreshtemplatelist).pack(side="left", padx=(0, 0))

        row2 = ttk.Frame(selectorframe)
        row2.pack(fill="x", pady=(6, 0))

        app._btn_tpl_import = ttk.Button(row2, text=" Import Prompts", command=app.import_templates)
        app._btn_tpl_import.pack(side="left", padx=(0, 6))
        app._btn_tpl_export = ttk.Button(row2, text=" Export Prompts", command=app.export_templates)
        app._btn_tpl_export.pack(side="left", padx=(0, 6))
        app._btn_tpl_delete = ttk.Button(row2, text=" Delete Selected", command=app.delete_template)
        app._btn_tpl_delete.pack(side="left", padx=(0, 6))

        app.template_detail_var = tk.StringVar(value="")
        ttk.Label(
            selectorframe,
            textvariable=app.template_detail_var,
            font=app.small_font,
            foreground="#555555",
        ).pack(anchor="w", pady=(6, 0))

        # Template variable UI removed - now auto-loads into Quick Build
        app.template_variable_widgets = {}

        app.refreshtemplatelist()


    def _build_theme_builder_panel(self, parent, *, assign_refs=True, title="Theme Builder", refs=None):
        """Build the Theme Builder controls on the provided parent."""
        app = self.app
        if title is None:
            controls_card = ttk.Frame(parent)
            controls_card.grid(row=0, column=0, sticky="ew", pady=(0, 4))
        else:
            controls_card = ttk.Labelframe(parent, text=title, padding=10)
            controls_card.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        controls_card.columnconfigure(1, weight=1)

        def _store(name, widget):
            if assign_refs:
                setattr(app, name, widget)
            if refs is not None:
                refs[name] = widget

        ttk.Label(controls_card, text="Subject:", width=10, anchor="w").grid(row=1, column=0, sticky="w", padx=(0, 2), pady=(0, 8))
        subject_var = tk.StringVar(value="frog")
        subject_entry = ttk.Entry(controls_card, textvariable=subject_var, width=26)
        subject_entry.grid(row=1, column=1, sticky="ew", pady=(0, 8))
        app.configure_entry_cursor(subject_entry)
        subject_entry.bind("<MouseWheel>", lambda e: "break")
        subject_entry.bind("<Button-4>", lambda e: "break")
        subject_entry.bind("<Button-5>", lambda e: "break")
        # Store selected value directly in dictionary
        def update_subject_value(event=None):
            value = subject_entry.get()
            app.prompt_builder_values["subject"] = value
        subject_entry.bind("<FocusOut>", update_subject_value)
        subject_entry.bind("<KeyRelease>", update_subject_value)
        # Initialize with default value
        app.prompt_builder_values["subject"] = "frog"
        _store("subject_var", subject_var)
        _store("subject_entry", subject_entry)

        # Row 2: Style | Mode  (render treatment — both affect output type)
        row2 = ttk.Frame(controls_card)
        row2.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        row2.columnconfigure(1, weight=1)
        row2.columnconfigure(3, weight=1)
        ttk.Label(row2, text="Style:", width=10, anchor="w").grid(row=0, column=0, sticky="w", padx=(0, 2))
        style_var = tk.StringVar(value="oil painting")
        style_entry = ttk.Entry(row2, textvariable=style_var, width=14)
        style_entry.grid(row=0, column=1, sticky="ew", padx=(0, 10))
        app.configure_entry_cursor(style_entry)
        style_entry.bind("<MouseWheel>", lambda e: "break")
        style_entry.bind("<Button-4>", lambda e: "break")
        style_entry.bind("<Button-5>", lambda e: "break")
        # Store selected value directly in dictionary
        def update_style_value(event=None):
            value = style_entry.get()
            app.prompt_builder_values["style"] = value
        style_entry.bind("<FocusOut>", update_style_value)
        style_entry.bind("<KeyRelease>", update_style_value)
        # Initialize with default value
        app.prompt_builder_values["style"] = "oil painting"
        _store("style_var", style_var)
        _store("style_entry", style_entry)
        ttk.Label(row2, text="Mode:", width=10, anchor="w").grid(row=0, column=2, sticky="w", padx=(0, 2))
        mode_var = tk.StringVar(value=app.DEFAULT_PROMPT_MODE_LABEL)
        mode_combo = ttk.Combobox(
            row2,
            textvariable=mode_var,
            values=app.PROMPT_MODE_LABELS,
            width=15,
        )
        mode_combo.grid(row=0, column=3, sticky="ew")
        mode_combo.bind("<<ComboboxSelected>>", lambda e: app.update_mode_badge())
        mode_combo.bind("<MouseWheel>", lambda e: "break")
        mode_combo.bind("<Button-4>", lambda e: "break")
        mode_combo.bind("<Button-5>", lambda e: "break")
        if assign_refs:
            app.mode_var = mode_var
            app.mode_combo = mode_combo
        if refs is not None:
            refs["mode_var"] = mode_var
            refs["mode_combo"] = mode_combo

        # Row 3: Lighting
        row3 = ttk.Frame(controls_card)
        row3.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        ttk.Label(row3, text="Lighting:", width=10, anchor="w").grid(row=0, column=0, sticky="w", padx=(0, 2))
        lighting_var = tk.StringVar(value="neon")
        lighting_entry = ttk.Entry(row3, textvariable=lighting_var, width=14)
        lighting_entry.grid(row=0, column=1, sticky="ew")
        app.configure_entry_cursor(lighting_entry)
        lighting_entry.bind("<MouseWheel>", lambda e: "break")
        lighting_entry.bind("<Button-4>", lambda e: "break")
        lighting_entry.bind("<Button-5>", lambda e: "break")
        # Store selected value directly in dictionary
        def update_lighting_value(event=None):
            value = lighting_entry.get()
            app.prompt_builder_values["lighting"] = value
        lighting_entry.bind("<FocusOut>", update_lighting_value)
        lighting_entry.bind("<KeyRelease>", update_lighting_value)
        # Initialize with default value
        app.prompt_builder_values["lighting"] = "neon"
        _store("lighting_var", lighting_var)
        _store("lighting_entry", lighting_entry)

        # Row 4: Color Palette (Color family + Modifier)
        row4 = ttk.Frame(controls_card)
        row4.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        row4.columnconfigure(1, weight=1)
        row4.columnconfigure(3, weight=1)

        # Color family / variation options — sourced from module-level constants
        color_families = app.COLOR_FAMILIES
        color_variations = app.COLOR_VARIATIONS

        ttk.Label(row4, text="Color:", width=10, anchor="w").grid(row=0, column=0, sticky="w", padx=(0, 2))
        # Use random defaults for color to avoid empty on startup
        default_family = random.choice([f for f in color_families if f]) if color_families else ""
        color_family_var = tk.StringVar(value=default_family)
        color_family_combo = ttk.Combobox(row4, textvariable=color_family_var, width=14, values=color_families)
        color_family_combo.grid(row=0, column=1, sticky="ew", padx=(0, 10))
        color_family_combo.bind("<MouseWheel>", lambda e: "break")
        color_family_combo.bind("<Button-4>", lambda e: "break")
        color_family_combo.bind("<Button-5>", lambda e: "break")

        ttk.Label(row4, text="Modifier:", width=10, anchor="w").grid(row=0, column=2, sticky="w", padx=(0, 2))
        # Use random defaults for color variation
        default_variation = random.choice(color_variations) if color_variations else ""
        color_variation_var = tk.StringVar(value=default_variation)
        color_variation_combo = ttk.Combobox(row4, textvariable=color_variation_var, width=14, values=color_variations)
        color_variation_combo.grid(row=0, column=3, sticky="ew")
        color_variation_combo.bind("<MouseWheel>", lambda e: "break")
        color_variation_combo.bind("<Button-4>", lambda e: "break")
        color_variation_combo.bind("<Button-5>", lambda e: "break")

        _store("color_family_var", color_family_var)
        _store("color_family_combo", color_family_combo)
        _store("color_variation_var", color_variation_var)
        _store("color_variation_combo", color_variation_combo)

        # Row 5: Setting field (location/structure) - default to first non-empty option
        ttk.Label(controls_card, text="Setting:", width=10, anchor="w").grid(row=5, column=0, sticky="w", padx=(0, 2), pady=(0, 8))
        # Default to first non-empty setting option (swamp)
        first_setting = [opt for opt in app.THEME_VARIABLE_OPTIONS["setting"] if opt]
        default_setting = first_setting[0] if first_setting else ""
        setting_var = tk.StringVar(value=default_setting)
        setting_entry = ttk.Entry(controls_card, textvariable=setting_var, width=26)
        setting_entry.grid(row=5, column=1, sticky="ew", pady=(0, 8))
        app.configure_entry_cursor(setting_entry)
        setting_entry.bind("<MouseWheel>", lambda e: "break")
        setting_entry.bind("<Button-4>", lambda e: "break")
        setting_entry.bind("<Button-5>", lambda e: "break")
        # Store selected value directly in dictionary
        def update_setting_value(event=None):
            value = setting_entry.get()
            app.prompt_builder_values["setting"] = value
        setting_entry.bind("<FocusOut>", update_setting_value)
        setting_entry.bind("<KeyRelease>", update_setting_value)
        # Initialize with default value
        first_setting = [opt for opt in app.THEME_VARIABLE_OPTIONS["setting"] if opt]
        default_setting = first_setting[0] if first_setting else ""
        app.prompt_builder_values["setting"] = default_setting
        _store("setting_var", setting_var)
        _store("setting_entry", setting_entry)

        # Row 6: Atmosphere — full-width, same grid as Subject/Setting/Negative
        ttk.Label(controls_card, text="Atmosphere:", width=10, anchor="w").grid(row=6, column=0, sticky="w", padx=(0, 2), pady=(0, 8))
        first_atmosphere = [opt for opt in app.THEME_VARIABLE_OPTIONS.get("atmosphere", []) if opt]
        # Use a random default instead of first alphabetically to avoid always showing "arcane haze"
        default_atm = random.choice(first_atmosphere) if first_atmosphere else ""
        atmosphere_var = tk.StringVar(value=default_atm)
        atmosphere_combo = ttk.Entry(controls_card, textvariable=atmosphere_var, width=26)
        atmosphere_combo.grid(row=6, column=1, sticky="ew", pady=(0, 8))
        atmosphere_combo.bind("<MouseWheel>", lambda e: "break")
        atmosphere_combo.bind("<Button-4>", lambda e: "break")
        atmosphere_combo.bind("<Button-5>", lambda e: "break")
        # Store selected value directly in dictionary
        def update_atmosphere_value(event=None):
            value = atmosphere_combo.get()
            app.prompt_builder_values["atmosphere"] = value
        atmosphere_combo.bind("<FocusOut>", update_atmosphere_value)
        atmosphere_combo.bind("<KeyRelease>", update_atmosphere_value)
        # Initialize with default value
        app.prompt_builder_values["atmosphere"] = default_atm
        _store("atmosphere_var", atmosphere_var)
        _store("atmosphere_combo", atmosphere_combo)

        # ── Row 7+: Negative Preset checkbuttons (unified with sidebar) ──
        neg_preset_frame = ttk.Frame(controls_card)
        neg_preset_frame.grid(row=7, column=0, columnspan=2, sticky="ew", pady=(0, 2))

        ttk.Label(neg_preset_frame, text="Neg. Presets:", width=10, anchor="w").pack(side="left", padx=(0, 2))

        _presets_data = load_negative_presets().get("presets", {})
        _pb_preset_info = []  # [(key, dname, desc, negs, term_count), ...]
        _pb_preset_vars = {}  # key -> BooleanVar
        _preset_key_map = {}
        for key, val in _presets_data.items():
            if key == "none":
                continue
            dname = val.get("name", key)
            desc = val.get("description", "")
            negs = val.get("negatives", "")
            term_count = len([t for t in negs.split(",") if t.strip()])
            _pb_preset_info.append((key, dname, desc, negs, term_count))
            _pb_preset_vars[key] = tk.BooleanVar(value=False)
            _preset_key_map[dname] = key

        # Two-column grid of checkbuttons
        cb_frame = ttk.Frame(neg_preset_frame)
        cb_frame.pack(side="left", fill="x", expand=True)
        for idx, (key, dname, desc, negs, term_count) in enumerate(_pb_preset_info):
            r, c = divmod(idx, 2)
            cb = ttk.Checkbutton(cb_frame, text=f"{dname} ({term_count})",
                                  variable=_pb_preset_vars[key])
            cb.grid(row=r, column=c, sticky="w", padx=(0, 12))

        # Placeholder vars for backward compat (single-combobox interface)
        neg_preset_var = tk.StringVar(value="None (Custom Only)")

        # Preset description label (updates on hover over checkbuttons)
        preset_desc_var = tk.StringVar(value="")
        preset_desc_label = ttk.Label(controls_card, textvariable=preset_desc_var,
                                      wraplength=500)
        preset_desc_label.grid(row=8, column=0, columnspan=2, sticky="w", padx=(10, 0), pady=(0, 2))

        for key, dname, desc, negs, term_count in _pb_preset_info:
            for child in cb_frame.winfo_children():
                if isinstance(child, ttk.Checkbutton) and dname in child.cget("text"):
                    child.bind("<Enter>", lambda e, d=desc: preset_desc_var.set(d))
                    child.bind("<Leave>", lambda e: preset_desc_var.set(""))
                    break

        # ── Row 9: Smart Negatives checkbox (reuses sidebar var if available) ──
        if not hasattr(app, 'smart_neg_var'):
            app.smart_neg_var = tk.BooleanVar(value=True)
        smart_neg_var = app.smart_neg_var
        ttk.Checkbutton(controls_card, text="Smart Negatives (auto-detect from prompt keywords)",
                         variable=smart_neg_var).grid(row=9, column=0, columnspan=2, sticky="w", pady=(0, 8), padx=(0, 0))

        # ── Row 10: Custom Negative prompt entry ──
        ttk.Label(controls_card, text="Negative:", width=10, anchor="w").grid(row=10, column=0, sticky="nw", padx=(0, 2))
        negative_prompt_var = tk.StringVar(value=app.DEFAULT_NEGATIVE_PROMPT)
        negative_prompt_entry = ttk.Entry(controls_card, textvariable=negative_prompt_var, width=72)
        negative_prompt_entry.grid(row=10, column=1, sticky="ew", pady=(0, 8))
        app.configure_entry_cursor(negative_prompt_entry)
        negative_prompt_entry.bind("<MouseWheel>", lambda e: "break")
        negative_prompt_entry.bind("<Button-4>", lambda e: "break")
        negative_prompt_entry.bind("<Button-5>", lambda e: "break")
        if assign_refs:
            app.negative_prompt_var = negative_prompt_var
            app.negative_prompt_entry = negative_prompt_entry
            app.neg_preset_var = neg_preset_var
            app.neg_preset_key_map = _preset_key_map
            # smart_neg_var already points to app.smart_neg_var; no overwrite
            # Store PB tab preset vars so apply_negative_prompt_to_prompts can use them
            app._pb_neg_preset_vars = _pb_preset_vars
            app._pb_neg_preset_info = _pb_preset_info
        if refs is not None:
            refs["negative_prompt_var"] = negative_prompt_var
            refs["negative_prompt_entry"] = negative_prompt_entry
            refs["neg_preset_var"] = neg_preset_var
            refs["smart_neg_var"] = smart_neg_var

        return controls_card


    def _ensure_recipe_manager(self):
        """Lazy-initialize recipe_manager if not already set (handles Prompt Builder tab usage before Templates tab)."""
        app = self.app
        if not hasattr(app, 'recipe_manager') or app.recipe_manager is None:
            try:
                from template_system import get_recipe_manager
                app.recipe_manager = get_recipe_manager()
            except Exception:
                app.recipe_manager = None
        return app.recipe_manager


    def _generate_from_recipe(self, recipe):
        """Generate themes from a Recipe object (new unified system) using Quick Build fields."""
        app = self.app
        # Use Quick Build fields instead of template variables
        variable_values = {
            "subject": app.get_active_subject(),
            "style": app.get_active_style(),
            "lighting": app.get_active_lighting(),
            "mood": app.get_active_mood(),
            "color": app.get_active_color(),
        }

        expanded_prompt = recipe.expand(variable_values)
        mode = recipe.style_mode if recipe.style_mode else app.current_mode()
        theme_id = len(app.prompts) + 1

        # Create a theme entry
        theme_entry = {
            "theme_id": theme_id,
            "style_mode": mode,
            "theme_sentence": f"Recipe: {recipe.name}",
            "prompt": expanded_prompt,
            "negative_prompt": recipe.negative_prompt if recipe.negative_prompt else app.get_active_negative_prompt(),
            "subject": recipe.quick_fields.get("subject", "") if recipe.quick_fields else app.get_active_subject(),
            "art_style": recipe.quick_fields.get("style", "") if recipe.quick_fields else app.get_active_style(),
        }

        # Add to themes and prompts
        app.themes.append(theme_entry)
        app.prompts.append(theme_entry)

        # Apply negative prompt if configured
        app.apply_negative_prompt_to_prompts()

        app.current_prompt_data = theme_entry
        app.show_prompt()
        app.activate_generator_tab()
        app.status_var.set(f"Generated theme from prompt: {recipe.name}")


    def _generate_from_template_legacy(self, template):
        """Generate themes from a Template object (legacy system) using Quick Build fields."""
        app = self.app
        # Use Quick Build fields instead of template variables
        variable_values = {
            "subject": app.get_active_subject(),
            "style": app.get_active_style(),
            "lighting": app.get_active_lighting(),
            "mood": app.get_active_mood(),
            "color": app.get_active_color(),
        }

        expanded_prompt = template.expand(variable_values)
        mode = app.current_mode()
        theme_id = len(app.prompts) + 1

        # Create a theme entry
        theme_entry = {
            "theme_id": theme_id,
            "style_mode": mode,
            "theme_sentence": f"Template: {template.name}",
            "prompt": expanded_prompt,
            "negative_prompt": app.get_active_negative_prompt(),
            "subject": app.get_active_subject(),
            "art_style": app.get_active_style(),
        }

        # Add to themes and prompts
        app.themes.append(theme_entry)
        app.prompts.append(theme_entry)

        # Apply negative prompt if configured
        app.apply_negative_prompt_to_prompts()

        app.current_prompt_data = theme_entry
        app.show_prompt()
        app.activate_generator_tab()
        app.status_var.set(f"Generated theme from template: {template.name}")


    def _generate_quick_recipe_description(self, subject, style, mood, lighting, atmosphere=None):
        """Generate a description from Quick Build fields."""
        app = self.app
        parts = []
        if mood:
            parts.append(mood)
        if subject:
            parts.append(subject)
        if style:
            parts.append(f"in {style} style")
        if lighting:
            parts.append(f"with {lighting} lighting")
        if atmosphere:
            parts.append(f"with {atmosphere} atmosphere")
        
        if parts:
            description = " ".join(parts)
            description = description[0].upper() + description[1:] if description else description
            if description and not description.endswith('.'):
                description += "."
            return description
        else:
            return "Quick prompt with structured fields."


    def _generate_quick_recipe_name(self, subject, style, mood, atmosphere=None):
        """Generate a recipe name from Quick Build fields."""
        app = self.app
        parts = []
        if subject:
            parts.append(subject)
        if style:
            parts.append(style)
        if mood:
            parts.append(mood)
        # Include atmosphere if present and space allows
        if atmosphere and len(parts) < 3:
            parts.append(atmosphere.replace(" ", "-"))
        
        if parts:
            return " ".join(parts[:3]).title()
        else:
            return "Quick Prompt"


    def _generate_template_description(self):
        """Generate a human-readable description from Quick Build fields."""
        app = self.app
        parts = []

        # Get field values
        subject = app.get_active_subject()
        style = app.get_active_style()
        lighting = app.get_active_lighting()
        mood = app.get_active_mood()
        color = app.get_active_color()
        mode = app.get_active_mode_label()

        # Build description parts
        if mood and subject:
            parts.append(f"{mood} {subject}")
        elif subject:
            parts.append(subject)
        elif mood:
            parts.append(mood)

        if style:
            if parts:
                parts.append(f"in {style} style")
            else:
                parts.append(f"{style} style")

        if lighting:
            parts.append(f"with {lighting} lighting")
        
        if color:
            parts.append(f"{color} colors")
        
        if mode:
            parts.append(f"({mode} mode)")
        
        # Build final description
        if parts:
            description = " ".join(parts)
            # Capitalize first letter
            description = description[0].upper() + description[1:] if description else description
            # Add period if missing
            if description and not description.endswith('.'):
                description += "."
            return description
        else:
            return "Reusable wallpaper prompt template."


    def _generate_template_name_from_prompt(self, prompt):
        """Auto-generate a template name from subject, variables, and style."""
        app = self.app
        import re
        
        # Filler words to exclude
        filler_words = {
            "theme", "mode", "negative", "prompt", "quality", "wallpaper", 
            "generate", "image", "a", "an", "the", "of", "in", "on", "at", 
            "to", "and", "or", "with", "by", "for", "is", "as", "into", 
            "from", "very", "ultra", "highly"
        }
        
        # Collect name parts
        parts = []
        
        # 1. Use subject field if present
        subject = app.get_active_subject()
        if subject and subject.lower() not in filler_words:
            parts.append(subject.title())
        
        # 2. Extract and include variables from prompt
        variables = re.findall(r"\{(\w+)\}", prompt)
        for var in variables:
            if var.lower() not in filler_words:
                parts.append(f"{{{var}}}")
        
        # 3. Optionally include style if it adds clarity and we have room
        if len(parts) < 3:
            style = app.get_active_style()
            if style and style.lower() not in filler_words:
                # Only add if different from subject and not already implied
                if not parts or style.lower() != parts[0].lower():
                    parts.append(style.title())
        
        # 4. Fall back to cleaned prompt parsing if no parts yet
        if not parts:
            clean = re.sub(r"\{[^}]*\}", "", prompt)
            clean = re.sub(r"[^\w\s]", " ", clean)
            words = [w for w in clean.split() if w.lower() not in filler_words and len(w) > 2]
            parts = [w.title() for w in words[:3]]
        
        # 5. Limit to 2-4 meaningful parts
        if len(parts) > 4:
            parts = parts[:4]
        
        return " ".join(parts) if parts else "Custom Template"


    def _get_active_quick_refs(self):
        """Return PB Quick Build refs when the Prompt Builder tab is the active view.
        Falls back to PB refs unconditionally when no legacy widgets exist."""
        app = self.app
        if app._is_prompt_builder_quick_active():
            return getattr(app, "prompt_builder_quick_refs", None)
        # No legacy widgets any more — always fall back to PB Quick Build refs.
        return app._get_pb_quick_refs()


    def _get_active_text(self, name, default=""):
        app = self.app
        widget = app._get_active_widget(name)
        if not widget or not hasattr(widget, "get"):
            return default
        try:
            value = widget.get()
            # If value is empty, try to get the current selection from the combo box
            if not value and hasattr(widget, 'current'):
                current_index = widget.current()
                if current_index >= 0:
                    values = widget.cget('values') if hasattr(widget, 'cget') else []
                    if current_index < len(values):
                        value = values[current_index]
        except Exception as e:
            return default
        return value.strip() if isinstance(value, str) else value


    def _get_active_widget(self, name):
        # Always try PB Quick Build refs first (they're the primary source now)
        app = self.app
        refs = app._get_pb_quick_refs()
        if refs and name in refs:
            widget = refs[name]
            # Verify the widget actually exists and has a get method
            if widget is not None and hasattr(widget, 'get'):
                return widget
        # Fallback to sidebar widgets (app.xxx) if present
        widget = getattr(app, name, None)
        if widget is not None and hasattr(widget, 'get'):
            return widget
        return None


    def _get_pb_quick_refs(self):
        """Return PB Quick Build refs whenever they are populated (tab-agnostic).
        Used by setters and as the unconditional primary quick-build source."""
        app = self.app
        refs = getattr(app, "prompt_builder_quick_refs", None)
        return refs if refs else None


    def _is_prompt_builder_quick_active(self):
        app = self.app
        if getattr(app, "prompt_builder_mode_var", None) is None:
            return False
        if app.prompt_builder_mode_var.get() != "Quick Build":
            return False
        if not getattr(app, "prompt_builder_quick_refs", None):
            return False
        return app._is_prompt_builder_tab_selected()


    def _is_prompt_builder_tab_selected(self):
        # Check if the Prompt Builder tab is actually selected
        app = self.app
        if hasattr(app, 'notebook'):
            current_tab = app.notebook.index(app.notebook.select())
            tab_text = app.notebook.tab(current_tab, "text")
            return "Prompt Builder" in tab_text
        return False


    def _load_quick_recipe_to_theme_builder(self, recipe):
        """Load a Quick Recipe's fields into the active quick-build controls."""
        app = self.app
        try:
            quick_fields = recipe.quick_fields or {}

            app.set_active_subject(quick_fields.get("subject", ""))
            app.set_active_style(quick_fields.get("style", ""))
            app.set_active_lighting(quick_fields.get("lighting", ""))
            app.set_active_mood(quick_fields.get("mood", ""))
            app.set_active_color(quick_fields.get("color", ""))
            app.set_active_atmosphere(quick_fields.get("atmosphere", ""))
            app.set_active_mode(recipe.style_mode or app.DEFAULT_PROMPT_MODE_VALUE)
            app.set_active_subject_lock(quick_fields.get("subject_lock", True))
            if recipe.negative_prompt:
                app.set_active_negative_prompt(recipe.negative_prompt)

            app.status_var.set(f"Loaded Quick Prompt: {recipe.name}")
            app.update_mode_badge()

        except Exception as e:
            app._dialog.error("Error", f"Could not load quick prompt: {e}")


    def _load_recipe(self, recipe):
        """Load a Recipe object (new unified system)."""
        app = self.app
        app.template_variable_widgets = {}
        # Recipe auto-loads into Quick Build instead of showing variable UI
        app._load_quick_recipe_to_theme_builder(recipe)
        app.status_var.set(f"Loaded prompt: {recipe.name}")


    def _load_template_legacy(self, template):
        """Load a Template object (legacy system) - auto-converts to Quick Build."""
        app = self.app
        app.template_variable_widgets = {}
        # Convert legacy template to Recipe and load into Quick Build
        from template_system import Recipe
        recipe = Recipe.from_template(template)
        app._load_quick_recipe_to_theme_builder(recipe)
        app.status_var.set(f"Loaded template: {template.name}")


    def _on_notebook_tab_changed(self, event=None):
        app = self.app
        app.update_prompt_builder_mode()


    def _open_recipe_window(self):
        """Open Recipe Library in a modal Toplevel window."""
        app = self.app
        if hasattr(app, "_recipe_win") and app._recipe_win and app._recipe_win.winfo_exists():
            app._recipe_win.lift()
            app._recipe_win.focus_force()
            return

        win = tk.Toplevel(app.root)
        win.title("FrogPaper — Recipe Library")
        win.geometry("750x550")
        win.transient(app.root)
        win.grab_set()
        app._recipe_win = win

        container = ttk.Frame(win, padding=10)
        container.pack(fill="both", expand=True)

        app._build_templates_tab(container)
        app.refreshtemplatelist()

        def _on_close():
            win.grab_release()
            win.destroy()
            app._recipe_win = None

        win.protocol("WM_DELETE_WINDOW", _on_close)


    def _open_settings_window(self):
        """Open Settings in a modal Toplevel window, building content fresh."""
        app = self.app
        if hasattr(app, "_settings_win") and app._settings_win and app._settings_win.winfo_exists():
            app._settings_win.lift()
            app._settings_win.focus_force()
            return

        win = tk.Toplevel(app.root)
        win.title("FrogPaper — Settings")
        win.geometry("700x600")
        win.transient(app.root)
        win.grab_set()
        app._settings_win = win

        # Build settings content directly inside this window
        container = ttk.Frame(win)
        container.pack(fill="both", expand=True)
        app._build_settings_tab(container)

        def _on_close():
            win.grab_release()
            win.destroy()
            app._settings_win = None

        win.protocol("WM_DELETE_WINDOW", _on_close)


    def _open_template_edit_dialog(self, source, *, is_recipe):
        """Open a modal edit dialog for a custom template or recipe."""
        app = self.app
        import re as _re

        dialog = tk.Toplevel(app.root)
        dialog.title(f"Edit: {source.name}")
        dialog.geometry("560x480")
        dialog.resizable(True, True)
        dialog.transient(app.root)
        dialog.grab_set()

        ttk.Label(dialog, text="Name:").pack(anchor="w", padx=14, pady=(12, 0))
        name_var = tk.StringVar(value=source.name)
        name_entry = ttk.Entry(dialog, textvariable=name_var, width=60)
        name_entry.pack(padx=14, pady=(2, 8), fill="x")
        app.configure_entry_cursor(name_entry)

        ttk.Label(dialog, text="Description:").pack(anchor="w", padx=14)
        desc_var = tk.StringVar(value=source.description)
        desc_entry = ttk.Entry(dialog, textvariable=desc_var, width=60)
        desc_entry.pack(padx=14, pady=(2, 8), fill="x")
        app.configure_entry_cursor(desc_entry)

        ttk.Label(dialog, text="Template Text:").pack(anchor="w", padx=14)
        text_frame = ttk.Frame(dialog)
        text_frame.pack(padx=14, pady=(2, 8), fill="both", expand=True)
        text_scroll = ttk.Scrollbar(text_frame, orient="vertical")
        text_box = tk.Text(
            text_frame,
            wrap="word",
            height=10,
            yscrollcommand=text_scroll.set,
            font=("TkDefaultFont",),
        )
        text_scroll.config(command=text_box.yview)
        text_box.pack(side="left", fill="both", expand=True)
        text_scroll.pack(side="right", fill="y")
        text_box.insert("1.0", source.template_text or "")

        hint = ttk.Label(
            dialog,
            text="Use {variable_name} placeholders in the template text.",
            font=app.small_font,
            foreground="#666666",
        )
        hint.pack(anchor="w", padx=14, pady=(0, 8))

        def do_save():
            new_name = name_var.get().strip()
            new_desc = desc_var.get().strip()
            new_text = text_box.get("1.0", tk.END).strip()

            if not new_name:
                app._dialog.warning("Name Required", "Please enter a name.")
                return
            if not new_text:
                app._dialog.warning("Text Required", "Template text cannot be empty.")
                return

            # Re-extract variables from updated text; preserve existing options/last_values
            detected_vars = list(dict.fromkeys(_re.findall(r"\{(\w+)\}", new_text)))
            old_vars = source.variables if source.variables else {}
            old_last = source.last_values if source.last_values else {}
            new_vars = {v: old_vars.get(v, []) for v in detected_vars}
            new_last = {v: old_last[v] for v in detected_vars if v in old_last}

            try:
                if is_recipe and app.recipe_manager:
                    if new_name != source.name:
                        if app.recipe_manager.get_recipe(new_name):
                            app._dialog.error(
                                "Name Taken",
                                f"A recipe named '{new_name}' already exists.",
                            )
                            return
                        app.recipe_manager.delete_recipe(source.name)

                    from template_system import Recipe
                    updated = Recipe(
                        name=new_name,
                        description=new_desc,
                        recipe_type=source.recipe_type if source.recipe_type else "template",
                        template_text=new_text,
                        variables=new_vars,
                        last_values=new_last,
                        is_builtin=False,
                        style_mode=source.style_mode,
                        negative_prompt=source.negative_prompt,
                        quick_fields=dict(source.quick_fields) if source.quick_fields else {},
                    )
                    # Same name → update in place; new name → add (old already deleted above)
                    if new_name == source.name:
                        app.recipe_manager.update_recipe(updated)
                    else:
                        app.recipe_manager.add_recipe(updated)

                elif app.template_manager:
                    from template_system import Template
                    updated = Template(
                        name=new_name,
                        description=new_desc,
                        template_text=new_text,
                        variables=new_vars,
                        is_builtin=False,
                        last_values=new_last,
                    )
                    if new_name == source.name:
                        app.template_manager.update_template(updated)
                    else:
                        app.template_manager.delete_template(source.name)
                        app.template_manager.add_template(updated)

                app.refreshtemplatelist()
                app.template_var.set(new_name)
                app.loadtemplate()
                app.status_var.set(f"Prompt '{new_name}' saved.")
                dialog.destroy()

            except Exception as e:
                app._dialog.error("Save Error", f"Could not save template:\n{e}")

        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(pady=(0, 12))
        ttk.Button(btn_frame, text="Save", command=do_save).pack(side="left", padx=6)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side="left", padx=6)

        name_entry.focus_set()


    def _refresh_template_library(self):
        """Refresh template library display while preserving selection."""
        app = self.app
        if not app.template_available:
            return

        current = app.template_var.get()
        
        # Only show quick-type recipes (Quick Build snapshots); skip legacy template-variable entries
        if app.recipe_manager:
            recipes = [r for r in app.recipe_manager.get_all_recipes() if getattr(r, "recipe_type", "quick") == "quick"]
            template_names = [r.name for r in recipes]
        else:
            template_names = []
        
        app.template_combo["values"] = template_names

        if current in template_names:
            app.template_var.set(current)
        else:
            app.template_var.set("")

        app._update_template_detail_label()


    def _save_quick_recipe_dialog(self, name, description, dialog, subject, style, lighting, mood, color, atmosphere, mode, subject_lock, negative_prompt):
        """Handle save quick recipe dialog submission."""
        app = self.app
        name = (name or "").strip() or app._generate_quick_recipe_name(subject, style, mood, atmosphere)
        description = (description or "").strip() or app._generate_quick_recipe_description(subject, style, mood, lighting, atmosphere)

        # Auto-number if the name is already taken: Name → Name 2 → Name 3 …
        base_name = name
        n = 2
        while app.recipe_manager.get_recipe(name) is not None:
            name = f"{base_name} {n}"
            n += 1

        try:
            recipe = app.RecipeClass(
                name=name,
                description=description,
                recipe_type="quick",  # Quick mode uses structured fields
                template_text="",  # No template text for quick mode
                variables={},  # No variables for quick mode
                is_builtin=False,
                last_values={},
                style_mode=mode,
                negative_prompt=negative_prompt,
                quick_fields={
                    "subject": subject,
                    "style": style,
                    "lighting": lighting,
                    "mood": mood,
                    "color": color,
                    "atmosphere": atmosphere,
                    "subject_lock": subject_lock
                }
            )

            app.recipe_manager.add_recipe(recipe)
            app.status_var.set(f"Quick Prompt '{name}' saved successfully!")
            dialog.destroy()
            app._dialog.info("Saved", f"Quick Prompt saved as:\n\n\"{name}\"")

        except Exception as e:
            app._dialog.error("Error", f"Could not save quick prompt: {e}")


    def _save_template_dialog(self, name, description, dialog):
        """Handle save template/recipe dialog submission."""
        app = self.app
        current_prompt = app.get_prompt_text()
        name = (name or "").strip() or app._generate_template_name_from_prompt(current_prompt)
        description = (description or "").strip()

        try:
            import re

            variables = {}
            # Collect current variable values from template variable widgets
            last_values = {}
            for var_name in re.findall(r"\{(\w+)\}", current_prompt):
                if var_name not in variables:
                    variables[var_name] = []
                # Get current value from widget if it exists
                if hasattr(app, 'template_variable_widgets') and var_name in app.template_variable_widgets:
                    widget = app.template_variable_widgets[var_name]
                    if hasattr(widget, 'get'):
                        value = widget.get()
                        if value:
                            last_values[var_name] = value
                            # Also add to options if not already present
                            if value not in variables[var_name]:
                                variables[var_name].append(value)

            # Try to save as Recipe first (new unified system)
            if app.recipe_manager:
                recipe = app.RecipeClass(
                    name=name,
                    description=description,
                    recipe_type="template",  # Save as template mode for text-based recipes
                    template_text=current_prompt,
                    variables=variables,
                    is_builtin=False,
                    last_values=last_values,
                    style_mode=app.current_mode(),
                    negative_prompt=app.get_active_negative_prompt(),
                    quick_fields={
                        "subject": app.get_active_subject(),
                        "style": app.get_active_style(),
                        "lighting": app.get_active_lighting(),
                        "mood": app.get_active_mood(),
                        "color": app.get_active_color(),
                        "subject_lock": app.get_active_subject_lock()
                    }
                )

                if app.recipe_manager.add_recipe(recipe):
                    app.status_var.set(f"Prompt '{name}' saved successfully!")
                    app.refreshtemplatelist()
                    dialog.destroy()
                    app._dialog.info("Saved", f"Prompt saved as:\n\n\"{name}\"")
                else:
                    # Fall back to TemplateManager if RecipeManager fails (e.g., name conflict)
                    if app.template_manager:
                        template = app.TemplateClass(
                            name=name,
                            description=description,
                            template_text=current_prompt,
                            variables=variables,
                            is_builtin=False,
                            last_values=last_values
                        )
                        if app.template_manager.add_template(template):
                            app.status_var.set(f"Template '{name}' saved successfully!")
                            app.refreshtemplatelist()
                            dialog.destroy()
                            app._dialog.info("Saved", f"Template saved as:\n\n\"{name}\"")
                        else:
                            app._dialog.error(
                                "Name Taken",
                                f"A template named '{name}' already exists.\nPlease choose a different name.",
                            )
                    else:
                        app._dialog.error(
                            "Name Taken",
                            f"A prompt named '{name}' already exists.\nPlease choose a different name.",
                        )
            else:
                # Fall back to old TemplateManager if RecipeManager is not available
                if app.template_manager:
                    template = app.TemplateClass(
                        name=name,
                        description=description,
                        template_text=current_prompt,
                        variables=variables,
                        is_builtin=False,
                        last_values=last_values
                    )
                    if app.template_manager.add_template(template):
                        app.status_var.set(f"Template '{name}' saved successfully!")
                        app.refreshtemplatelist()
                        dialog.destroy()
                        app._dialog.info("Saved", f"Template saved as:\n\n\"{name}\"")
                    else:
                        app._dialog.error(
                            "Name Taken",
                            f"A template named '{name}' already exists.\nPlease choose a different name.",
                        )

        except Exception as e:
            app._dialog.error("Error", f"Could not save template: {e}")


    def _set_active_entry(self, name, value):
        """Set a text entry/combobox widget on both sidebar and PB Quick Build source."""
        app = self.app
        # Update sidebar widget if it exists
        sidebar_widget = getattr(app, name, None)
        if sidebar_widget and hasattr(sidebar_widget, "delete") and hasattr(sidebar_widget, "insert"):
            try:
                sidebar_widget.delete(0, tk.END)
                sidebar_widget.insert(0, value)
            except Exception:
                pass
        # Update PB Quick Build widget if it exists
        refs = app._get_pb_quick_refs()
        if refs and name in refs:
            widget = refs[name]
            if hasattr(widget, "delete") and hasattr(widget, "insert"):
                try:
                    widget.delete(0, tk.END)
                    widget.insert(0, value)
                except Exception:
                    pass


    def _set_active_var(self, name, value):
        """Set a StringVar / BooleanVar on the PB Quick Build source."""
        app = self.app
        refs = app._get_pb_quick_refs()
        if refs and name in refs:
            var = refs[name]
            if hasattr(var, "set"):
                try:
                    var.set(value)
                except Exception:
                    pass


    def _toggle_recipe_library(self):
        """Toggle Recipe Library visibility."""
        app = self.app
        if not app.recipe_lib_expanded.get():
            app.recipe_lib_content.pack_forget()
            return

        # Build content if not already built
        if not app._recipe_lib_built:
            app._build_templates_tab(app.recipe_lib_content)
            app._recipe_lib_built = True

        app.recipe_lib_content.pack(fill="x", expand=True, pady=(4, 0))
        app.refreshtemplatelist()


    def _update_template_detail_label(self):
        """Update the detail info label below the Template Library selector."""
        app = self.app
        if not hasattr(app, "template_detail_var"):
            return

        name = app.template_var.get() if hasattr(app, "template_var") else ""
        if not name:
            app.template_detail_var.set("")
            return

        source = None
        if app.recipe_manager:
            source = app.recipe_manager.get_recipe(name)
        if source is None and app.template_manager:
            source = app.template_manager.get_template(name)

        if source is None:
            app.template_detail_var.set("")
            return

        # Build status badges
        builtin_badge = "Built-in" if source.is_builtin else "Custom"
        type_badge = getattr(source, "recipe_type", "template").title()
        badges = f"[{builtin_badge}]  {type_badge}"

        desc = (source.description or "").strip()
        if desc:
            # Truncate long descriptions
            if len(desc) > 80:
                desc = desc[:77] + "..."
            detail = f"{badges}  —  {desc}"
        else:
            detail = badges

        app.template_detail_var.set(detail)


    def apply_negative_prompt_to_prompts(self):

        app = self.app

        # Smart negatives toggle
        smart_var = getattr(app, 'smart_neg_var', None)
        use_smart = smart_var.get() if smart_var else False

        mode = app.current_mode()

        # The unified Negative Prompt Builder merges presets + custom into
        # negative_prompt_var directly.  Detect it by checking for the new
        # attribute; fall back to the old two-source logic for the PB tab.
        if hasattr(app, '_neg_preset_vars'):
            # ── Unified builder (sidebar) ──
            # negative_prompt_var already contains presets + custom deduplicated.
            combined_custom = app.get_active_negative_prompt()
        else:
            # ── Legacy two-source path (PB Quick Build tab) ──
            custom = app.get_negative_prompt()

            preset_keys = []
            if hasattr(app, '_pb_neg_preset_vars'):
                # PB tab: multi-select checkbuttons
                for key, var in app._pb_neg_preset_vars.items():
                    if var.get():
                        preset_keys.append(key)
            elif hasattr(app, 'neg_preset_var'):
                # Fallback: old single combobox
                key_map = getattr(app, 'neg_preset_key_map', None)
                if key_map and app.neg_preset_var:
                    pk = key_map.get(app.neg_preset_var.get(), "none")
                    if pk != "none":
                        preset_keys.append(pk)

            from negative_manager import get_preset_negatives
            preset_neg_parts = []
            for pk in preset_keys:
                neg_text = get_preset_negatives(pk)
                if neg_text:
                    preset_neg_parts.append(neg_text)
            combined_preset_neg = ", ".join(preset_neg_parts) if preset_neg_parts else ""
            combined_custom = combined_preset_neg + (", " + custom if combined_preset_neg and custom else custom)

        for item in app.prompts:

            baked = item.get("negative_prompt", "")

            # Build merged negative: presets+custom + style defaults + smart
            item_prompt_text = item.get("prompt", "")
            manager_neg = build_final_negative_prompt(
                preset_key="none",  # presets already included in combined_custom
                custom_negatives=combined_custom,
                style_mode=mode,
                append_style_defaults=True,
                prompt_text=item_prompt_text,
                append_smart_negatives=use_smart,
            )

            # Merge with any baked negatives from prompt_builder
            if baked and manager_neg:
                combined_parts = [p.strip() for p in (baked + ", " + manager_neg).split(",") if p.strip()]
                seen = set()
                deduped = []
                for part in combined_parts:
                    key = part.lower()
                    if key not in seen:
                        deduped.append(part)
                        seen.add(key)
                item["negative_prompt"] = ", ".join(deduped)
            elif manager_neg:
                item["negative_prompt"] = manager_neg
            elif not baked:
                item["negative_prompt"] = ""


    def build_prompt_builder_tab(self, parent):
        """Create the Prompt Builder tab."""
        app = self.app
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)

        # ── Scrollable canvas wrapper ─────────────────────────────────────────
        canvas = tk.Canvas(parent, highlightthickness=0)
        scroll = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        inner = ttk.Frame(canvas, style="Inner.TFrame")
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        _pb_win = canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(_pb_win, width=e.width))
        canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        inner.columnconfigure(0, weight=1)
        app.prompt_builder_canvas = canvas

        # ── Quick Build Prompts ──────────────────────────────────────────────────────
        qb_frame = ttk.LabelFrame(inner, text="Quick Build Prompts", padding=(10, 6))
        qb_frame.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        qb_frame.columnconfigure(0, weight=1)

        app.prompt_builder_quick_refs = {}
        app.prompt_builder_values = {}  # Store actual selected values
        app._build_theme_builder_panel(
            qb_frame,
            assign_refs=False,
            title=None,
            refs=app.prompt_builder_quick_refs,
        )

        ttk.Separator(qb_frame, orient="horizontal").grid(
            row=1, column=0, columnspan=2, sticky="ew", pady=(4, 6))
        qb_actions = ttk.Frame(qb_frame)
        qb_actions.grid(row=2, column=0, columnspan=2, sticky="w")
        app._btn_qb_generate = ttk.Button(qb_actions, text=" Generate Prompt",
                   command=app.generate_prompt_only).pack(side="left", padx=(0, 6))
        app._btn_qb_random = ttk.Button(qb_actions, text=" Random Prompt",
                   command=app.random_theme).pack(side="left", padx=(0, 6))
        ttk.Button(qb_actions, text="Save Quick Prompt",
                   command=app.save_as_quick_recipe).pack(side="left", padx=(0, 6))

        app.prompt_builder_quick_container = qb_frame
        app.prompt_builder_mode_var = tk.StringVar(value="Quick Build Prompts")

        # ── Checkboxes: Subject Lock + Prompt Audit on one row ───────────────
        checks_frame = ttk.Frame(inner)
        checks_frame.grid(row=3, column=0, sticky="w", pady=(4, 4))
        # Use existing vars from sidebar if already created
        if not hasattr(app, 'subject_lock_var'):
            app.subject_lock_var = tk.BooleanVar(value=True)
        subject_lock_check = ttk.Checkbutton(checks_frame, text="Keep Typed Subject Literal",
                                              variable=app.subject_lock_var)
        subject_lock_check.pack(side="left", padx=(0, 18))
        app.prompt_builder_quick_refs["subject_lock_var"] = app.subject_lock_var
        app.prompt_builder_quick_refs["subject_lock_check"] = subject_lock_check
        app.subject_lock_check = subject_lock_check

        if not hasattr(app, 'prompt_audit_var'):
            app.prompt_audit_var = tk.BooleanVar(value=False)
        prompt_audit_check = ttk.Checkbutton(checks_frame, text="Show Prompt Variable Audit",
                                              variable=app.prompt_audit_var)
        prompt_audit_check.pack(side="left")
        app.prompt_builder_quick_refs["prompt_audit_var"] = app.prompt_audit_var
        app.prompt_builder_quick_refs["prompt_audit_check"] = prompt_audit_check
        app.prompt_audit_check = prompt_audit_check

        ttk.Separator(inner, orient="horizontal").grid(row=4, column=0, sticky="ew", pady=(6, 8))

        # ── Progress Bar (skip if already created in center panel) ────────────
        if not hasattr(app, 'progress'):
            progress_frame = ttk.Frame(inner, height=20)
            progress_frame.grid(row=6, column=0, sticky="ew", pady=(0, 6))
            progress_frame.grid_propagate(False)
            progress_frame.columnconfigure(0, weight=1)
            progress_frame.rowconfigure(0, weight=1)
            app.progress = ttk.Progressbar(progress_frame, mode="determinate", maximum=100)
            app.progress.grid(row=0, column=0, sticky="nsew")
            app.progress_overlay_label = tk.Label(progress_frame, text="", font=app.small_font, anchor="center")
            app.progress_overlay_label.place(relx=0.5, rely=0.5, anchor="center")

        # ── Image Generation Progress Bar (skip if already created in center panel) ────────────
        if not hasattr(app, 'image_progress'):
            image_progress_frame = ttk.Frame(inner, height=20)
            image_progress_frame.grid(row=7, column=0, sticky="ew", pady=(0, 6))
            image_progress_frame.grid_propagate(False)
            image_progress_frame.columnconfigure(0, weight=1)
            image_progress_frame.rowconfigure(0, weight=1)
            app.image_progress = ttk.Progressbar(image_progress_frame, mode="determinate", maximum=100)
            app.image_progress.grid(row=0, column=0, sticky="nsew")
            app.image_progress.grid_remove()  # Hide initially
            app.image_progress_overlay_label = tk.Label(image_progress_frame, text="", font=app.small_font, anchor="center")
            app.image_progress_overlay_label.place(relx=0.5, rely=0.5, anchor="center")

        # ── Prompt Preview (skip if already created in center panel) ────────
        if not hasattr(app, 'prompt_text'):
            preview_frame = ttk.LabelFrame(inner, text="Prompt Preview", padding=(10, 6))
            preview_frame.grid(row=9, column=0, sticky="ew", pady=(0, 8))
            preview_frame.columnconfigure(0, weight=1)
            preview_frame.columnconfigure(1, weight=0)

            app.mode_badge = ttk.Label(preview_frame,
                                        text=f"Subject lock: ON")
            app.mode_badge.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 4))

            # Image/output actions — pinned at top for immediate visibility
            img_actions = ttk.Frame(preview_frame)
            img_actions.grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 6))

            app._btn_img_generate = ttk.Button(img_actions, text=" Generate Image",
                       command=app.generate_selected_image).pack(side="left", padx=(0, 6))
            app._btn_img_wallpaper = ttk.Button(img_actions, text=" Set as Wallpaper",
                       command=app.generate_and_set).pack(side="left", padx=(0, 6))
            app._btn_img_cancel = ttk.Button(img_actions, text=" Cancel",
                       command=app.cancel_generation).pack(side="left")

            ttk.Separator(preview_frame, orient="horizontal").grid(
                row=2, column=0, columnspan=2, sticky="ew", pady=(6, 6))

            _pt_scroll = ttk.Scrollbar(preview_frame, orient="vertical")
            app.prompt_text = tk.Text(
                preview_frame, wrap="word", font=app.mono_font, height=6,
                yscrollcommand=_pt_scroll.set,
            )
            _pt_scroll.config(command=app.prompt_text.yview)
            app.prompt_text.grid(row=3, column=0, sticky="nsew")
            _pt_scroll.grid(row=3, column=1, sticky="ns")
            app.prompt_text.config(state="disabled")
            app.prompt_text.bind("<MouseWheel>", lambda e: app._on_prompt_text_scroll(e))
            app.prompt_text.bind("<Button-4>", lambda e: app._on_prompt_text_scroll(e))
            app.prompt_text.bind("<Button-5>", lambda e: app._on_prompt_text_scroll(e))

        ttk.Separator(inner, orient="horizontal").grid(row=8, column=0, sticky="ew", pady=(6, 8))

        # ── Recipe Library (collapsible) ─────────────────────────────────────
        recipe_lib_container = ttk.Frame(inner)
        recipe_lib_container.grid(row=9, column=0, sticky="ew", pady=(0, 4))
        recipe_lib_container.columnconfigure(0, weight=1)

        # Recipe action buttons (Session removed)

        # Header with toggle
        recipe_header = ttk.Frame(recipe_lib_container)
        recipe_header.pack(fill="x", pady=(0, 4))
        app._lbl_recipe_header = ttk.Label(recipe_header, text="  Quick Prompt Library", font=app.bold_font)
        app._lbl_recipe_header.pack(side="left")
        app.recipe_lib_expanded = tk.BooleanVar(value=False)
        ttk.Checkbutton(recipe_header, text="Show", variable=app.recipe_lib_expanded,
                       command=app._toggle_recipe_library).pack(side="right")

        # Content frame (toggleable)
        app.recipe_lib_content = ttk.Frame(recipe_lib_container)
        # Initially hidden, built when expanded
        app._recipe_lib_built = False

        app.prompt_builder_template_container = recipe_lib_container


    def delete_quick_recipe(self):
        """Delete the selected quick recipe after confirmation. Built-in recipes are protected."""
        app = self.app
        if not app.recipe_manager:
            app._dialog.warning("Prompt System", "Prompt system is not available.")
            return

        # Get list of quick recipes
        quick_recipes = [r for r in app.recipe_manager.get_all_recipes() if r.recipe_type == "quick"]
        if not quick_recipes:
            app._dialog.info("No Quick Prompts", "No quick prompts to delete.")
            return

        # Create dialog to select a recipe to delete
        dialog = tk.Toplevel(app.root)
        dialog.title("Delete Prompt")
        dialog.geometry("400x300")
        dialog.resizable(False, False)
        dialog.transient(app.root)
        dialog.grab_set()

        ttk.Label(dialog, text="Select a prompt to delete:", font=("TkDefaultFont", 10, "bold")).pack(pady=(12, 8), padx=12, anchor="w")

        # Listbox for recipe selection
        list_frame = ttk.Frame(dialog)
        list_frame.pack(fill="both", expand=True, padx=12, pady=(0, 8))
        recipe_list = tk.Listbox(list_frame, selectmode="single", height=10)
        recipe_list.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(list_frame, command=recipe_list.yview)
        scrollbar.pack(side="right", fill="y")
        recipe_list.config(yscrollcommand=scrollbar.set)

        # Populate list
        recipe_map = {}
        for recipe in quick_recipes:
            recipe_list.insert("end", recipe.name)
            recipe_map[recipe.name] = recipe

        def do_delete():
            selection = recipe_list.curselection()
            if not selection:
                app._dialog.warning("No Selection", "Please select a prompt to delete.")
                return
            recipe_name = recipe_list.get(selection[0])
            recipe = recipe_map.get(recipe_name)
            if not recipe:
                return

            # Protect built-in recipes
            if getattr(recipe, 'built_in', False) or getattr(recipe, 'is_builtin', False):
                app._dialog.info("Protected Prompt", f"'{recipe_name}' is a built-in prompt and cannot be deleted.")
                return

            # Confirm deletion
            if not app._dialog.ask("Confirm Delete", f"Are you sure you want to delete '{recipe_name}'?"):
                return

            # Delete the recipe
            try:
                if app.recipe_manager.delete_recipe(recipe_name):
                    # Only refresh template library if the Templates tab has been initialized
                    if hasattr(app, 'template_available') and app.template_available:
                        app._refresh_template_library()
                    app.status_var.set(f"Deleted prompt: {recipe_name}")
                    dialog.destroy()
                else:
                    app._dialog.error("Error", f"Could not delete prompt: {recipe_name}")
            except Exception as e:
                app._dialog.error("Error", f"Failed to delete prompt: {e}")

        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(fill="x", padx=12, pady=(0, 12))
        ttk.Button(btn_frame, text="Delete", command=do_delete).pack(side="right", padx=(6, 0))
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side="right")

        recipe_list.focus_set()
        recipe_list.bind("<Double-Button-1>", lambda e: do_delete())


    def delete_template(self):
        """Delete the selected template/recipe."""
        app = self.app
        template_name = app.template_var.get()

        if not template_name or not app.template_available:
            app._dialog.warning("No Selection", "Please select a prompt first.")
            return

        # Try RecipeManager first (new unified system), fall back to TemplateManager
        if app.recipe_manager:
            recipe = app.recipe_manager.get_recipe(template_name)
            if recipe:
                if recipe.is_builtin:
                    app._dialog.warning("Built-in Prompt", "Cannot delete built-in prompts.")
                    return
                result = app._dialog.ask("Delete Prompt", f"Are you sure you want to delete '{template_name}'?")
                if result:
                    if app.recipe_manager.delete_recipe(template_name):
                        app.status_var.set(f"Prompt '{template_name}' deleted.")
                        app.refreshtemplatelist()
                    else:
                        app._dialog.error("Error", "Could not delete prompt.")
                return

        # Fall back to old TemplateManager for backward compatibility
        if app.template_manager:
            template = app.template_manager.get_template(template_name)
            if template:
                if template.is_builtin:
                    app._dialog.warning("Built-in Template", "Cannot delete built-in templates.")
                    return
                result = app._dialog.ask("Delete Template", f"Are you sure you want to delete '{template_name}'?")
                if result:
                    if app.template_manager.delete_template(template_name):
                        app.status_var.set(f"Template '{template_name}' deleted.")
                        app.refreshtemplatelist()
                    else:
                        app._dialog.error("Error", "Could not delete template.")
                return


    def duplicate_template(self):
        """Create a custom editable copy of the selected template or recipe."""
        app = self.app
        template_name = app.template_var.get()
        if not template_name or not app.template_available:
            app._dialog.warning("No Selection", "Please select a prompt to copy.")
            return

        if not app.recipe_manager:
            app._dialog.warning("Prompt System", "Prompt system is not available.")
            return

        # Resolve source: RecipeManager first, then TemplateManager legacy
        source = app.recipe_manager.get_recipe(template_name)
        if source is None and app.template_manager:
            legacy = app.template_manager.get_template(template_name)
            if legacy:
                from template_system import Recipe
                source = Recipe.from_template(legacy)

        if source is None:
            app._dialog.warning("Not Found", f"Could not find template: {template_name}")
            return

        # Build a unique copy name: "Name (Copy)", "Name (Copy 2)", ...
        base_copy_name = f"{source.name} (Copy)"
        copy_name = base_copy_name
        counter = 2
        while app.recipe_manager.get_recipe(copy_name) is not None:
            copy_name = f"{base_copy_name[:-1]} {counter})"
            counter += 1

        from template_system import Recipe
        copy = Recipe(
            name=copy_name,
            description=source.description,
            recipe_type=source.recipe_type if source.recipe_type else "template",
            template_text=source.template_text,
            variables=dict(source.variables) if source.variables else {},
            last_values=dict(source.last_values) if source.last_values else {},
            is_builtin=False,
            style_mode=source.style_mode if hasattr(source, "style_mode") else "stylized",
            negative_prompt=source.negative_prompt if hasattr(source, "negative_prompt") else "",
            quick_fields=dict(source.quick_fields) if hasattr(source, "quick_fields") and source.quick_fields else {},
        )

        ok = app.recipe_manager.add_recipe(copy)
        if not ok:
            app._dialog.error("Name Conflict", f"A custom prompt named '{copy_name}' already exists.")
            return

        app.refreshtemplatelist()

        # Auto-select the new copy
        names = list(app.template_combo["values"])
        if copy_name in names:
            app.template_var.set(copy_name)
            app.loadtemplate()

        app.status_var.set(f"Editable copy created: '{copy_name}'")


    def edit_template(self):
        """Edit selected recipe by loading it into the Quick Build form."""
        app = self.app
        template_name = app.template_var.get()
        if not template_name or not app.template_available:
            app._dialog.warning("No Selection", "Please select a prompt first.")
            return

        source = None
        if app.recipe_manager:
            source = app.recipe_manager.get_recipe(template_name)
        if source is None and app.template_manager:
            legacy = app.template_manager.get_template(template_name)
            if legacy:
                from template_system import Recipe
                source = Recipe.from_template(legacy)

        if source is None:
            return

        if source.is_builtin:
            app._dialog.info(
                "Built-in Prompt",
                "Built-in prompts cannot be edited directly.\n\n"
                "Save a new prompt with your changes using \"Save Quick Prompt\"."
            )
            return

        app._load_quick_recipe_to_theme_builder(source)
        app.activate_prompt_builder_tab()
        app.status_var.set(f"Loaded '{template_name}' into Quick Build for editing. Adjust values and save as a new prompt.")


    def export_template(self):
        """Export the selected template/recipe to a JSON file."""
        app = self.app
        template_name = app.template_var.get()

        if not template_name or not app.template_available:
            app._dialog.warning("No Selection", "Please select a prompt first.")
            return

        from tkinter import filedialog
        export_path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialfile=f"{template_name}.json"
        )

        if export_path:
            # Try RecipeManager first (new unified system), fall back to TemplateManager
            if app.recipe_manager:
                recipe = app.recipe_manager.get_recipe(template_name)
                if recipe:
                    if app.recipe_manager.export_recipe(template_name, Path(export_path)):
                        app.status_var.set(f"Prompt '{template_name}' exported successfully.")
                        app._dialog.info("Export Successful", f"Prompt exported to {export_path}")
                    else:
                        app._dialog.error("Export Failed", "Could not export prompt.")
                    return

            # Fall back to old TemplateManager for backward compatibility
            if app.template_manager:
                if app.template_manager.export_template(template_name, Path(export_path)):
                    app.status_var.set(f"Template '{template_name}' exported successfully.")
                    app._dialog.info("Export Successful", f"Template exported to {export_path}")
                else:
                    app._dialog.error("Export Failed", "Could not export template.")


    def export_templates(self):
        """Export all custom templates/recipes to a single JSON file (list format)."""
        app = self.app
        if not app.template_available:
            app._dialog.warning("Template System", "Template system is not available.")
            return
        
        from tkinter import filedialog
        import json, re
        
        from datetime import date
        default_name = f"frogpaper_recipes_{date.today().strftime('%Y%m%d')}"
        
        file_path = filedialog.asksaveasfilename(
            title="Export Prompts",
            initialfile=f"{default_name}.json",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if not file_path:
            return
        
        try:
            # Try RecipeManager first (new unified system), fall back to TemplateManager
            if app.recipe_manager:
                custom = [r for r in app.recipe_manager.get_all_recipes() if not r.is_builtin]
                if not custom:
                    app._dialog.info("Nothing to Export", "You have no custom prompts to export.\n(Built-in prompts are not exported.)")
                    return
                data = [r.to_dict() for r in custom]
            else:
                # Fall back to old TemplateManager for backward compatibility
                custom = [t for t in app.template_manager.get_all_templates() if not t.is_builtin]
                if not custom:
                    app._dialog.info("Nothing to Export", "You have no custom templates to export.\n(Built-in templates are not exported.)")
                    return
                data = [t.to_dict() for t in custom]
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            
            app.status_var.set(f"Exported {len(custom)} custom template(s) to file.")
            app._dialog.info("Export Complete", f"Exported {len(custom)} template(s) to:\n{file_path}")
        except Exception as e:
            app._dialog.error("Export Error", f"Could not export templates:\n{e}")


    def generatefromtemplate(self):
        """Generate themes from loaded template/recipe using current Quick Build fields."""
        app = self.app
        template_name = app.template_var.get()

        if not template_name:
            app.status_var.set("No prompt selected. Choose one from Quick Prompt Library first.")
            return

        if not app.template_available:
            app.status_var.set("Prompt system is not available.")
            return

        # Set prompt_source to template when explicitly generating from template
        app.prompt_source = "template"

        # Try RecipeManager first (new unified system), fall back to TemplateManager
        try:
            if app.recipe_manager:
                recipe = app.recipe_manager.get_recipe(template_name)
                if recipe:
                    app._generate_from_recipe(recipe)
                    return

            # Fall back to old TemplateManager for backward compatibility
            if app.template_manager:
                template = app.template_manager.get_template(template_name)
                if template:
                    app._generate_from_template_legacy(template)
                    return

            app.status_var.set(f"Prompt not found: {template_name}")
        except Exception as e:
            app.status_var.set(f"Error generating from prompt: {e}")
            logger.error(f"Error in generatefromtemplate: {e}")


    def get_active_atmosphere(self):
        app = self.app
        return app.prompt_builder_values.get("atmosphere", "")


    def get_active_color(self):
        """Get color by combining family and variation selections."""
        app = self.app
        # First check if color was set from sidebar widget reading
        color = app.prompt_builder_values.get("color", "")
        if color:
            logger.debug(f"get_active_color returning from prompt_builder_values: '{color}'")
            return color
        # Fallback to Prompt Builder refs
        refs = app._get_pb_quick_refs()
        if refs:
            family = refs.get("color_family_var", tk.StringVar()).get() or ""
            variation = refs.get("color_variation_var", tk.StringVar()).get() or ""
            if family and variation:
                return f"{variation} {family}"
            return family or variation
        return ""


    def get_active_lighting(self):
        app = self.app
        val = app.prompt_builder_values.get("lighting", "")
        logger.debug(f"get_active_lighting returning: '{val}'")
        return val


    def get_active_mode_label(self):
        app = self.app
        label = app._get_active_text("mode_var", app.DEFAULT_PROMPT_MODE_LABEL)
        return label or app.DEFAULT_PROMPT_MODE_LABEL


    def get_active_mood(self):
        # Prompt Builder uses "atmosphere" instead of "mood"
        app = self.app
        mood = app._get_active_text("mood_entry", "")
        logger.debug(f"get_active_mood returning: '{mood}'")
        return mood


    def get_active_setting(self):
        app = self.app
        val = app.prompt_builder_values.get("setting", "")
        logger.debug(f"get_active_setting returning: '{val}'")
        return val


    def get_active_style(self):
        app = self.app
        val = app.prompt_builder_values.get("style", "")
        logger.debug(f"get_active_style returning: '{val}'")
        return val


    def get_active_subject(self):
        app = self.app
        val = app.prompt_builder_values.get("subject", "")
        logger.debug(f"get_active_subject returning: '{val}'")
        return val


    def get_active_subject_lock(self):
        app = self.app
        widget = app._get_active_widget("subject_lock_var")
        if widget and hasattr(widget, "get"):
            try:
                return bool(widget.get())
            except Exception:
                pass
        return True


    def get_negative_prompt(self):

        app = self.app
        return app.get_active_negative_prompt().strip()


    def import_template(self):
        """Import a template/recipe from a JSON file."""
        app = self.app
        from tkinter import filedialog

        import_path = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )

        if import_path:
            # Try RecipeManager first (new unified system), fall back to TemplateManager
            if app.recipe_manager:
                if app.recipe_manager.import_recipe(Path(import_path)):
                    app.status_var.set("Prompt imported successfully.")
                    app.refreshtemplatelist()
                    app._dialog.info("Import Successful", "Prompt imported successfully.")
                else:
                    app._dialog.error("Import Failed", "Could not import prompt.")
                return

            # Fall back to old TemplateManager for backward compatibility
            if app.template_manager:
                if app.template_manager.import_template(Path(import_path)):
                    app.status_var.set("Template imported successfully.")
                    app.refreshtemplatelist()
                    app._dialog.info("Import Successful", "Template imported successfully.")
                else:
                    app._dialog.error("Import Failed", "Could not import template.")


    def import_templates(self):
        """Import one or more templates/recipes from a JSON file (single or list format)."""
        app = self.app
        if not app.template_available:
            app._dialog.warning("Template System", "Template system is not available.")
            return
        
        from tkinter import filedialog
        import json
        from pathlib import Path
        
        file_path = filedialog.askopenfilename(
            title="Import Templates",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if not file_path:
            return
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Accept both a single dict and a list of dicts
            entries = data if isinstance(data, list) else [data]
            
            from template_system import Template, Recipe
            imported, skipped = 0, 0
            
            # Try RecipeManager first (new unified system), fall back to TemplateManager
            if app.recipe_manager:
                for entry in entries:
                    try:
                        # Support both old template format and new recipe format
                        if "recipe_type" in entry:
                            recipe = Recipe.from_dict(entry)
                            recipe.is_builtin = False
                            if app.recipe_manager.add_recipe(recipe):
                                imported += 1
                            else:
                                skipped += 1
                        else:
                            # Migrate old template format
                            template = Template.from_dict(entry)
                            recipe = Recipe.from_template(template)
                            recipe.is_builtin = False
                            if app.recipe_manager.add_recipe(recipe):
                                imported += 1
                            else:
                                skipped += 1
                    except Exception:
                        skipped += 1
            else:
                # Fall back to old TemplateManager for backward compatibility
                for entry in entries:
                    try:
                        tmpl = Template.from_dict(entry)
                        tmpl.is_builtin = False
                        if app.template_manager.add_template(tmpl):
                            imported += 1
                        else:
                            skipped += 1
                    except Exception:
                        skipped += 1
            
            app.refreshtemplatelist()
            msg = f"Imported {imported} template(s)."
            if skipped:
                msg += f" {skipped} skipped (name conflict or invalid)."
            app.status_var.set(msg)
            app._dialog.info("Import Complete", msg)
        except Exception as e:
            app._dialog.error("Import Error", f"Could not read file:\n{e}")


    def load_quick_recipe(self):
        """Load a Quick Recipe into Prompt Builder Quick Build controls."""
        app = self.app
        app._ensure_recipe_manager()
        if not app.recipe_manager:
            app._dialog.warning("Prompt System", "Prompt system is not available.")
            return

        # Get all quick recipes
        quick_recipes = [r for r in app.recipe_manager.get_all_recipes() if r.recipe_type == "quick"]
        
        if not quick_recipes:
            app._dialog.info("No Quick Prompts", "No Quick Prompts found.\n\nUse \"Save Quick Prompt\" in the Prompt Builder tab to save one.")
            return

        # Create dialog to select a quick prompt
        dialog = tk.Toplevel(app.root)
        dialog.title("Load Quick Prompt")
        dialog.geometry("500x400")
        dialog.resizable(True, True)
        dialog.transient(app.root)
        dialog.grab_set()

        header = ttk.Label(
            dialog,
            text="Select a Quick Prompt to load into Prompt Builder Quick Build.",
            font=app.small_font,
            foreground="#666666",
        )
        header.pack(anchor="w", padx=14, pady=(12, 8))

        # Create listbox for prompts
        list_frame = ttk.Frame(dialog)
        list_frame.pack(fill="both", expand=True, padx=14, pady=(0, 10))

        recipe_listbox = tk.Listbox(list_frame, height=10)
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=recipe_listbox.yview)
        recipe_listbox.configure(yscrollcommand=scrollbar.set)
        
        recipe_listbox.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Populate listbox
        for recipe in quick_recipes:
            recipe_listbox.insert(tk.END, recipe.name)

        # Description label
        desc_label = ttk.Label(dialog, text="", wraplength=460, foreground="#666666")
        desc_label.pack(fill="x", padx=14, pady=(0, 10))

        def on_select(event):
            selection = recipe_listbox.curselection()
            if selection:
                index = selection[0]
                recipe = quick_recipes[index]
                desc_label.config(text=f"{recipe.description}\n\nMode: {recipe.style_mode}")

        recipe_listbox.bind("<<ListboxSelect>>", on_select)

        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=(0, 14))

        def do_load():
            selection = recipe_listbox.curselection()
            if selection:
                index = selection[0]
                recipe = quick_recipes[index]
                app._load_quick_recipe_to_theme_builder(recipe)
                dialog.destroy()
            else:
                app._dialog.warning("No Selection", "Please select a Quick Prompt to load.")

        ttk.Button(button_frame, text="Load", command=do_load).pack(side="left", padx=6)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side="left", padx=6)


    def load_selected_prompt_from_library(self):
        """Explicit Load button handler — validates selection then loads into Quick Build."""
        app = self.app
        if not hasattr(app, "template_var") or not app.template_var.get():
            app._dialog.warning("No Selection", "Select a prompt from the library first.")
            return
        app.load_selected_recipe_into_quick_build()


    def load_selected_recipe_into_quick_build(self):
        """Load the selected Recipe Library entry into the Quick Build form."""
        app = self.app
        template_name = app.template_var.get()
        if not template_name:
            return
        recipe = None
        if app.recipe_manager:
            recipe = app.recipe_manager.get_recipe(template_name)
        if recipe is None and app.template_manager:
            legacy = app.template_manager.get_template(template_name)
            if legacy:
                from template_system import Recipe
                recipe = Recipe.from_template(legacy)
        if recipe is None:
            app._dialog.warning("Not Found", f"Could not find prompt: {template_name}")
            return
        app._load_quick_recipe_to_theme_builder(recipe)


    def loadtemplate(self):
        """Load selected template/recipe and show variable dropdowns."""
        app = self.app
        template_name = app.template_var.get()

        if not template_name or not app.template_available:
            return

        # Try RecipeManager first (new unified system), fall back to TemplateManager
        if app.recipe_manager:
            recipe = app.recipe_manager.get_recipe(template_name)
            if recipe:
                app._load_recipe(recipe)
                return

        # Fall back to old TemplateManager for backward compatibility
        if app.template_manager:
            template = app.template_manager.get_template(template_name)
            if template:
                app._load_template_legacy(template)
                return


    def ontemplateselected(self, event=None):
        """Handle recipe selection — update detail label and auto-load into Quick Build."""
        app = self.app
        template_name = app.template_var.get()
        if not template_name:
            return
        app._update_template_detail_label()
        app.load_selected_recipe_into_quick_build()


    def previewdoubleclick(self, event=None):
        """Double-click the preview image to instantly set it as wallpaper."""
        app = self.app
        path = app.last_image_path or app.selected_gallery_path
        if not path:
            app.status_var.set("No image loaded to set as wallpaper.")
            return
        app.double_click_set_wallpaper(path)


    def refreshtemplatelist(self):
        """Refresh the template/recipe library display."""
        app = self.app
        if not app.template_available:
            return
        app._refresh_template_library()


    def resettemplatevariables(self):
        """Reset Quick Build fields to defaults."""
        app = self.app
        # Reset Quick Build fields
        refs = app._get_pb_quick_refs()
        if refs:
            if "subject_entry" in refs:
                refs["subject_entry"].delete(0, tk.END)
                refs["subject_entry"].insert(0, "frog")
            if "style_entry" in refs:
                refs["style_entry"].delete(0, tk.END)
                refs["style_entry"].insert(0, "oil painting")
            if "lighting_entry" in refs:
                refs["lighting_entry"].delete(0, tk.END)
                refs["lighting_entry"].insert(0, "neon")
            if "mood_entry" in refs:
                refs["mood_entry"].delete(0, tk.END)
                refs["mood_entry"].insert(0, "epic")
            if "color_family_var" in refs:
                refs["color_family_var"].set("")
            if "color_variation_var" in refs:
                refs["color_variation_var"].set("")
        app.status_var.set("Quick Build fields reset to defaults")


    def save_as_quick_recipe(self):
        """Save the current Prompt Builder Quick Build configuration as a Quick Recipe."""
        app = self.app
        app._ensure_recipe_manager()
        if not app.recipe_manager:
            app._dialog.warning("Prompt System", "Prompt system is not available.")
            return

        # If a built-in prompt is currently selected, inform the user their
        # changes will be saved as a new custom prompt (built-ins are protected).
        current_name = getattr(app, "template_var", None)
        current_name = current_name.get() if current_name else ""
        if current_name:
            existing = app.recipe_manager.get_recipe(current_name)
            if existing and getattr(existing, "is_builtin", False):
                app._dialog.info(
                    "Saving as New Prompt",
                    f"'{current_name}' is a built-in prompt and cannot be overwritten.\n\n"
                    "Your changes will be saved as a new custom prompt."
                )

        # Get current active quick-build values
        subject = app.get_active_subject()
        style = app.get_active_style()
        lighting = app.get_active_lighting()
        mood = app.get_active_mood()
        color = app.get_active_color()
        atmosphere = app.get_active_atmosphere()
        mode = app.get_active_mode()
        subject_lock = app.get_active_subject_lock()
        negative_prompt = app.get_active_negative_prompt()

        # Generate suggested name and description
        suggested_name = app._generate_quick_recipe_name(subject, style, mood, atmosphere)
        suggested_desc = app._generate_quick_recipe_description(subject, style, mood, lighting, atmosphere)

        # Create dialog for prompt name
        dialog = tk.Toplevel(app.root)
        dialog.title("Save Quick Prompt")
        dialog.geometry("480x280")
        dialog.resizable(False, False)
        dialog.transient(app.root)
        dialog.grab_set()

        header = ttk.Label(
            dialog,
            text="Save the current Prompt Builder Quick Build configuration as a Quick Prompt.",
            font=app.small_font,
            foreground="#666666",
        )
        header.pack(anchor="w", padx=14, pady=(12, 8))

        ttk.Label(dialog, text="Prompt Name:").pack(anchor="w", padx=14, pady=(0, 3))
        name_var = tk.StringVar(value=suggested_name)
        name_entry = ttk.Entry(dialog, textvariable=name_var, width=52)
        name_entry.pack(padx=14, pady=(0, 10), fill="x")
        app.configure_entry_cursor(name_entry)
        name_entry.icursor(tk.END)

        ttk.Label(dialog, text="Description:").pack(anchor="w", padx=14, pady=(0, 3))
        desc_var = tk.StringVar(value=suggested_desc)
        desc_entry = ttk.Entry(dialog, textvariable=desc_var, width=52)
        desc_entry.pack(padx=14, pady=(0, 10), fill="x")
        app.configure_entry_cursor(desc_entry)

        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=(0, 14))
        ttk.Button(
            button_frame,
            text="Save Prompt",
            command=lambda: app._save_quick_recipe_dialog(name_var.get(), desc_var.get(), dialog, subject, style, lighting, mood, color, atmosphere, mode, subject_lock, negative_prompt),
        ).pack(side="left", padx=6)
        ttk.Button(
            button_frame,
            text="Cancel",
            command=dialog.destroy,
        ).pack(side="left", padx=6)

        name_entry.focus_set()
        name_entry.selection_range(0, tk.END)


    def save_as_template(self):
        """Save current prompt as a new template."""
        app = self.app
        current_prompt = app.get_prompt_text()
        if not current_prompt:
            app._dialog.warning("No Prompt", "Please generate or enter a prompt first.")
            return

        suggested_name = app._generate_template_name_from_prompt(current_prompt)
        suggested_desc = app._generate_template_description()

        dialog = tk.Toplevel(app.root)
        dialog.title("Save as New Prompt")
        dialog.geometry("480x320")
        dialog.resizable(False, False)
        dialog.transient(app.root)
        dialog.grab_set()

        header = ttk.Label(
            dialog,
            text="Save current prompt as a reusable prompt.",
            font=app.small_font,
            foreground="#666666",
        )
        header.pack(anchor="w", padx=14, pady=(12, 8))

        ttk.Label(dialog, text="Template Name  (subject & style):").pack(anchor="w", padx=14, pady=(0, 3))
        name_var = tk.StringVar(value=suggested_name)
        name_entry = ttk.Entry(dialog, textvariable=name_var, width=52)
        name_entry.pack(padx=14, pady=(0, 10), fill="x")
        app.configure_entry_cursor(name_entry)
        name_entry.icursor(tk.END)

        ttk.Label(dialog, text="Description  (shown in tooltip / dropdown):").pack(anchor="w", padx=14, pady=(0, 3))
        desc_var = tk.StringVar(value=suggested_desc)
        desc_entry = ttk.Entry(dialog, textvariable=desc_var, width=52)
        desc_entry.pack(padx=14, pady=(0, 10), fill="x")
        app.configure_entry_cursor(desc_entry)

        hint = ttk.Label(
            dialog,
            text="Tip: use {variable_name} in your prompt to create fill-in slots.",
            font=app.small_font,
            foreground="#888888",
        )
        hint.pack(anchor="w", padx=14, pady=(0, 12))

        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=(0, 14))
        ttk.Button(
            button_frame,
            text="Save Prompt",
            command=lambda: app._save_template_dialog(name_var.get(), desc_var.get(), dialog),
        ).pack(side="left", padx=6)
        ttk.Button(
            button_frame,
            text="Cancel",
            command=dialog.destroy,
        ).pack(side="left", padx=6)

        name_entry.focus_set()
        name_entry.selection_range(0, tk.END)


    def set_active_atmosphere(self, value):
        """Set atmosphere in Quick Build controls and sidebar."""
        app = self.app
        app._set_active_var("atmosphere_var", value or "")
        # Also update sidebar atmosphere combo
        if hasattr(app, 'atmosphere_var'):
            try:
                app.atmosphere_var.set(value or "")
            except Exception:
                pass


    def set_active_color(self, value):
        """Set color by parsing value into family and variation."""
        app = self.app
        refs = app._get_pb_quick_refs()
        if not refs:
            return
        # Valid sets derived from module-level constants
        valid_families = set(app.COLOR_FAMILIES)
        valid_variations = set(app.COLOR_VARIATIONS)
        # Parse value like "rich gold" -> family="gold", variation="rich"
        value = (value or "").strip().lower()
        family = ""
        variation = ""
        if value:
            parts = value.split(maxsplit=1)
            if len(parts) == 2:
                var, fam = parts
                # Validate both parts
                if fam in valid_families and var in valid_variations:
                    family = fam
                    variation = var
                elif fam in valid_families:
                    family = fam
                    variation = ""
                elif var in valid_families:
                    family = var
                    variation = ""
            else:
                single = parts[0]
                # Single word: must be a valid family to be accepted
                if single in valid_families:
                    family = single
                    variation = ""
                # If single word is not a valid family, leave both empty (don't show partial tokens like "tones")

        try:
            refs["color_family_var"].set(family)
            refs["color_variation_var"].set(variation)
        except Exception:
            pass
        
        # Also update sidebar color combo boxes
        if hasattr(app, 'color_family_var') and hasattr(app, 'color_variation_var'):
            try:
                app.color_family_var.set(family)
                app.color_variation_var.set(variation)
            except Exception:
                pass


    def set_active_lighting(self, value):
        app = self.app
        app._set_active_entry("lighting_entry", value)


    def set_active_mode(self, mode_value):
        """Set mode display on the PB Quick Build source (canonical value or label)."""
        app = self.app
        label = app._mode_label(mode_value)
        refs = app._get_pb_quick_refs()
        if refs and "mode_var" in refs:
            try:
                refs["mode_var"].set(label)
            except Exception:
                pass


    def set_active_mood(self, value):
        app = self.app
        app._set_active_entry("mood_entry", value)


    def set_active_negative_prompt(self, value):
        app = self.app
        # When the unified builder exists, also sync its Text widget
        # and clear the custom-only entry so it doesn't double-merge.
        if hasattr(app, '_neg_final_text'):
            app._neg_final_text.delete("1.0", tk.END)
            app._neg_final_text.insert("1.0", value or "")
            app.negative_prompt_var.set(value or "")
            app._neg_manual_edit = True  # prevent _rebuild from overwriting
            app._neg_custom_var.set("")
            # Clear preset checkboxes so they don't re-add
            for var in app._neg_preset_vars.values():
                var.set(False)
            count = len([t for t in (value or "").split(",") if t.strip()])
            app._neg_term_count_var.set(f"{count} term{'s' if count != 1 else ''} (recipe)")
        # Also update PB Quick Build refs if they exist
        app._set_active_entry("negative_prompt_entry", value)
        app._set_active_var("negative_prompt_var", value)


    def set_active_setting(self, value):
        """Set setting in Quick Build controls."""
        app = self.app
        app.prompt_builder_values["setting"] = value or ""
        app._set_active_entry("setting_entry", value or "")


    def set_active_style(self, value):
        app = self.app
        app._set_active_entry("style_entry", value)


    def set_active_subject(self, value):
        app = self.app
        app._set_active_entry("subject_entry", value)


    def set_active_subject_lock(self, value):
        app = self.app
        app._set_active_var("subject_lock_var", bool(value))


    def subject_lock_enabled(self):

        app = self.app
        return app.get_active_subject_lock()


    def update_mode_badge(self, mode=None):

        app = self.app
        effective_mode = mode if mode is not None else app.get_active_mode()

        app.mode_badge.config(
            text=f"Subject lock: {'ON' if app.get_active_subject_lock() else 'OFF'}"
        )


    def update_prompt_builder_mode(self):
        """No-op: Quick Build and Recipe Library are always visible together."""
        app = self.app
        app.update_mode_badge()
