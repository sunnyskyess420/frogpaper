"""Generation pipeline methods for FrogPaperApp (roadmap #7 Phase B step 2).

Extracted verbatim from app.py: generate / generate_prompt_only, the
prompt + theme + image worker threads, progress UI, cancellation and
completion callbacks.

All methods are mixed into FrogPaperApp (see app.py), so behaviour is
unchanged: state still lives on self / self.app and every caller keeps
working untouched.
"""

import logging
import time
from datetime import datetime
from pathlib import Path

from app_paths import PROMPTS_LOG
from app_prompt_data import PROMPT_MODE_LABEL_TO_VALUE
from app_runtime import (
    PINNED_DROPDOWNS_AVAILABLE,
    WINDOWS,
    set_wallpaper,
    run_background,
    schedule_ui_update,
)
from gallery_manager import save_prompt_parameters
from prompt_builder import build_all_prompts
from theme_mixer import generate_themes
from utils import has_huggingface_token, load_json_list, save_json_list

if PINNED_DROPDOWNS_AVAILABLE:
    from app_runtime import get_manager

logger = logging.getLogger(__name__)



class FrogPaperAppGenerationMixin:
    """Mixed into FrogPaperApp (see app.py); methods are verbatim."""

    def generate(self, show_progress=True):

        if self.is_generating:

            self._dialog.info("Please wait", "Generation is already in progress.")

            return

        # Read from sidebar widgets (same as generate_prompt_only)
        logger.debug(f"generate: Reading from sidebar widgets")
        
        # Subject - check if it's a Combobox or Entry
        if hasattr(self, 'subject_entry'):
            if hasattr(self.subject_entry, 'get'):
                val = self.subject_entry.get()
                logger.debug(f"generate: subject_entry.get() = '{val}'")
                # Strip ★ pin marker if present
                if PINNED_DROPDOWNS_AVAILABLE:
                    _pmgr = get_manager()
                    if _pmgr:
                        val = _pmgr.strip_pin_marker(val)
                self.prompt_builder_values["subject"] = val
            elif hasattr(self.subject_entry, 'current'):
                idx = self.subject_entry.current()
                if idx >= 0:
                    val = self.subject_entry.get()
                    logger.debug(f"generate: subject_entry (combobox).get() = '{val}'")
                    self.prompt_builder_values["subject"] = val
        
        # Style - sidebar doesn't have style dropdown, read from Mode dropdown
        # The Mode dropdown is below the Style label and contains style values like "Painterly"
        if hasattr(self, 'mode_var') and hasattr(self.mode_var, 'get'):
            val = self.mode_var.get()
            logger.debug(f"generate: mode_var.get() = '{val}'")
            # Convert mode label to value if needed
            if val in PROMPT_MODE_LABEL_TO_VALUE:
                style_value = PROMPT_MODE_LABEL_TO_VALUE[val]
                logger.debug(f"generate: style from mode: '{style_value}'")
                self.prompt_builder_values["style"] = style_value
            else:
                self.prompt_builder_values["style"] = val
        # Fallback to Prompt Builder if sidebar mode is not available
        refs = self._get_pb_quick_refs()
        if refs and not self.prompt_builder_values.get("style"):
            style_entry = refs.get("style_entry")
            if style_entry and hasattr(style_entry, 'get'):
                val = style_entry.get()
                logger.debug(f"generate: style_entry (from PB).get() = '{val}'")
                self.prompt_builder_values["style"] = val
        
        # Lighting
        if hasattr(self, 'lighting_entry'):
            if hasattr(self.lighting_entry, 'get'):
                val = self.lighting_entry.get()
                logger.debug(f"generate: lighting_entry.get() = '{val}'")
                # Strip ★ pin marker if present
                if PINNED_DROPDOWNS_AVAILABLE:
                    _pmgr = get_manager()
                    if _pmgr:
                        val = _pmgr.strip_pin_marker(val)
                self.prompt_builder_values["lighting"] = val
            elif hasattr(self.lighting_entry, 'current'):
                idx = self.lighting_entry.current()
                if idx >= 0:
                    val = self.lighting_entry.get()
                    logger.debug(f"generate: lighting_entry (combobox).get() = '{val}'")
                    self.prompt_builder_values["lighting"] = val
        
        # Setting
        if hasattr(self, 'setting_entry'):
            if hasattr(self.setting_entry, 'get'):
                val = self.setting_entry.get()
                logger.debug(f"generate: setting_entry.get() = '{val}'")
                # Strip ★ pin marker if present
                if PINNED_DROPDOWNS_AVAILABLE:
                    _pmgr = get_manager()
                    if _pmgr:
                        val = _pmgr.strip_pin_marker(val)
                self.prompt_builder_values["setting"] = val
            elif hasattr(self.setting_entry, 'current'):
                idx = self.setting_entry.current()
                if idx >= 0:
                    val = self.setting_entry.get()
                    logger.debug(f"generate: setting_entry (combobox).get() = '{val}'")
                    self.prompt_builder_values["setting"] = val
        
        # Atmosphere
        if hasattr(self, 'atmosphere_combo'):
            if hasattr(self.atmosphere_combo, 'get'):
                val = self.atmosphere_combo.get()
                logger.debug(f"generate: atmosphere_combo.get() = '{val}'")
                # Strip ★ pin marker if present
                if PINNED_DROPDOWNS_AVAILABLE:
                    _pmgr = get_manager()
                    if _pmgr:
                        val = _pmgr.strip_pin_marker(val)
                self.prompt_builder_values["atmosphere"] = val
            elif hasattr(self.atmosphere_combo, 'current'):
                idx = self.atmosphere_combo.current()
                if idx >= 0:
                    val = self.atmosphere_combo.get()
                    logger.debug(f"generate: atmosphere_combo (combobox).get() = '{val}'")
                    self.prompt_builder_values["atmosphere"] = val
        
        # Mood
        if hasattr(self, 'mood_entry'):
            if hasattr(self.mood_entry, 'get'):
                val = self.mood_entry.get()
                logger.debug(f"generate: mood_entry.get() = '{val}'")
                # Strip ★ pin marker if present
                if PINNED_DROPDOWNS_AVAILABLE:
                    _pmgr = get_manager()
                    if _pmgr:
                        val = _pmgr.strip_pin_marker(val)
                self.prompt_builder_values["mood"] = val
            elif hasattr(self.mood_entry, 'current'):
                idx = self.mood_entry.current()
                if idx >= 0:
                    val = self.mood_entry.get()
                    logger.debug(f"generate: mood_entry (combobox).get() = '{val}'")
                    self.prompt_builder_values["mood"] = val
        
        # Color - combine family and variation
        if hasattr(self, 'color_family_var') and hasattr(self.color_family_var, 'get'):
            family = self.color_family_var.get()
            variation = ""
            if hasattr(self, 'color_variation_var') and hasattr(self.color_variation_var, 'get'):
                variation = self.color_variation_var.get()
            if family and variation:
                val = f"{variation} {family}"
            else:
                val = family or variation
            logger.debug(f"generate: color: family='{family}', variation='{variation}', combined='{val}'")
            self.prompt_builder_values["color"] = val

        subject = self.get_active_subject()

        setting = self.get_active_setting()

        style = self.get_active_style()

        lighting = self.get_active_lighting()

        mood = self.get_active_mood()

        color = self.get_active_color()

        atmosphere = self.get_active_atmosphere()

        mode = self.get_active_mode()

        subject_lock = self.get_active_subject_lock()

        logger.debug(f"generate: After getter functions:")
        logger.info(f"  subject='{subject}'")
        logger.info(f"  style='{style}'")
        logger.info(f"  lighting='{lighting}'")
        logger.info(f"  setting='{setting}'")
        logger.info(f"  atmosphere='{atmosphere}'")
        logger.info(f"  mood='{mood}'")
        logger.info(f"  color='{color}'")
        logger.info(f"  mode='{mode}'")
        logger.info(f"  subject_lock={subject_lock}")

        # Check if audit mode is enabled
        run_audit = False
        if hasattr(self, 'prompt_audit_var'):
            run_audit = self.prompt_audit_var.get()

        # Clear template selection when generating from Quick Build
        self.prompt_source = "theme_builder"
        self._should_generate_image = True  # Flag to trigger image generation
        if hasattr(self, 'template_var'):
            self.template_var.set("")

        self.is_generating = True
        self._show_generation_progress()

        self.cancel_event.clear()

        self.update_mode_badge(mode)

        self.status_var.set("Generating themes...")

        # Use ThreadPoolExecutor for non-blocking UI

        self.gen_future = self.executor.submit(

            self._generate_themes_thread,

            subject, setting, style, lighting, mood, color, atmosphere, mode, subject_lock, run_audit

        )

    def generate_prompt_only(self):
        """Generate prompt text from sidebar choices without generating the image.
        
        Non-blocking implementation with threading to prevent UI freeze.
        Shows busy feedback, prevents overlapping requests, and safely updates UI from background thread.
        """
        logger.debug("generate_prompt_only called")
        
        # Prevent overlapping requests
        if hasattr(self, '_is_generating_prompt') and self._is_generating_prompt:
            self._dialog.info("Please wait", "Prompt generation is already in progress.")
            return
        
        if self.is_generating:
            self._dialog.info("Please wait", "Image generation is already in progress.")
            return

        # Read from sidebar widgets (what the user is actually using)
        logger.debug(f"Reading from sidebar widgets")
        
        # Subject - check if it's a Combobox or Entry
        if hasattr(self, 'subject_entry'):
            if hasattr(self.subject_entry, 'get'):
                val = self.subject_entry.get()
                logger.debug(f"subject_entry.get() = '{val}'")
                self.prompt_builder_values["subject"] = val
            elif hasattr(self.subject_entry, 'current'):
                # It's a Combobox - get current selection
                idx = self.subject_entry.current()
                if idx >= 0:
                    val = self.subject_entry.get()
                    logger.debug(f"subject_entry (combobox).get() = '{val}'")
                    self.prompt_builder_values["subject"] = val
        
        # Style - sidebar doesn't have style dropdown, read from Mode dropdown
        # The Mode dropdown is below the Style label and contains style values like "Painterly"
        if hasattr(self, 'mode_var') and hasattr(self.mode_var, 'get'):
            val = self.mode_var.get()
            logger.debug(f"mode_var.get() = '{val}'")
            # Convert mode label to value if needed
            if val in PROMPT_MODE_LABEL_TO_VALUE:
                style_value = PROMPT_MODE_LABEL_TO_VALUE[val]
                logger.debug(f"style from mode: '{style_value}'")
                self.prompt_builder_values["style"] = style_value
            else:
                self.prompt_builder_values["style"] = val
        # Fallback to Prompt Builder if sidebar mode is not available
        refs = self._get_pb_quick_refs()
        if refs and not self.prompt_builder_values.get("style"):
            style_entry = refs.get("style_entry")
            if style_entry and hasattr(style_entry, 'get'):
                val = style_entry.get()
                logger.debug(f"style_entry (from PB).get() = '{val}'")
                self.prompt_builder_values["style"] = val
        
        # Lighting
        if hasattr(self, 'lighting_entry'):
            if hasattr(self.lighting_entry, 'get'):
                val = self.lighting_entry.get()
                logger.debug(f"lighting_entry.get() = '{val}'")
                self.prompt_builder_values["lighting"] = val
            elif hasattr(self.lighting_entry, 'current'):
                idx = self.lighting_entry.current()
                if idx >= 0:
                    val = self.lighting_entry.get()
                    logger.debug(f"lighting_entry (combobox).get() = '{val}'")
                    self.prompt_builder_values["lighting"] = val
        
        # Setting
        if hasattr(self, 'setting_entry'):
            if hasattr(self.setting_entry, 'get'):
                val = self.setting_entry.get()
                logger.debug(f"setting_entry.get() = '{val}'")
                self.prompt_builder_values["setting"] = val
            elif hasattr(self.setting_entry, 'current'):
                idx = self.setting_entry.current()
                if idx >= 0:
                    val = self.setting_entry.get()
                    logger.debug(f"setting_entry (combobox).get() = '{val}'")
                    self.prompt_builder_values["setting"] = val
        
        # Atmosphere
        if hasattr(self, 'atmosphere_combo'):
            if hasattr(self.atmosphere_combo, 'get'):
                val = self.atmosphere_combo.get()
                logger.debug(f"atmosphere_combo.get() = '{val}'")
                self.prompt_builder_values["atmosphere"] = val
            elif hasattr(self.atmosphere_combo, 'current'):
                idx = self.atmosphere_combo.current()
                if idx >= 0:
                    val = self.atmosphere_combo.get()
                    logger.debug(f"atmosphere_combo (combobox).get() = '{val}'")
                    self.prompt_builder_values["atmosphere"] = val

        # Mood
        if hasattr(self, 'mood_entry'):
            val = self.mood_entry.get()
            logger.debug(f"mood_entry.get() = '{val}'")
            self.prompt_builder_values["mood"] = val
        
        # Color - combine family and variation
        if hasattr(self, 'color_family_var') and hasattr(self.color_family_var, 'get'):
            family = self.color_family_var.get()
            variation = ""
            if hasattr(self, 'color_variation_var') and hasattr(self.color_variation_var, 'get'):
                variation = self.color_variation_var.get()
            if family and variation:
                val = f"{variation} {family}"
            else:
                val = family or variation
            logger.debug(f"color: family='{family}', variation='{variation}', combined='{val}'")
            self.prompt_builder_values["color"] = val
        
        logger.debug(f"prompt_builder_values = {self.prompt_builder_values}")
        subject = self.get_active_subject()
        setting = self.get_active_setting()
        style = self.get_active_style()
        lighting = self.get_active_lighting()
        mood = self.get_active_mood()
        color = self.get_active_color()
        atmosphere = self.get_active_atmosphere()
        mode = self.get_active_mode()
        subject_lock = self.get_active_subject_lock()

        # Check if audit mode is enabled
        run_audit = False
        if hasattr(self, 'prompt_audit_var'):
            run_audit = self.prompt_audit_var.get()

        # Clear template selection when generating from Quick Build
        self.prompt_source = "theme_builder"
        self._should_generate_image = False  # Flag to NOT trigger image generation
        if hasattr(self, 'template_var'):
            self.template_var.set("")

        # Set flag to prevent overlapping requests
        self._is_generating_prompt = True
        
        # Show busy feedback
        original_status = self.status_var.get()
        self.status_var.set("Generating prompt...")
        
        # Disable the generate button temporarily
        if hasattr(self, '_btn_qb_generate') and self._btn_qb_generate is not None:
            self._btn_qb_generate.config(state="disabled")
        
        # Run prompt generation in background thread using ThreadManager
        run_background(
            self._generate_prompt_thread,
            subject, setting, style, lighting, mood, color, atmosphere, mode, subject_lock, run_audit, original_status
        )

    def _generate_prompt_thread(self, subject, setting, style, lighting, mood, color, atmosphere, mode, subject_lock, run_audit, original_status):
        """Background thread for prompt generation to prevent UI freeze."""
        try:
            # Generate prompt only
            keywords = [w for w in f"{subject} {setting} {style} {lighting} {mood} {color} {atmosphere}".split() if w]

            ui_values = {
                "subject": subject,
                "style": style,
                "lighting": lighting,
                "mood": mood,
                "color": color,
                "mode": mode,
                "atmosphere": atmosphere,
                "setting": setting
            }

            themes = generate_themes(
                count=1,
                user_keywords=keywords,
                subject_lock=subject_lock,
                custom_subject=subject,
                explicit_subject=subject,
                explicit_setting=setting,
                explicit_style=style,
                explicit_lighting=lighting,
                explicit_mood=mood,
                explicit_color=color,
                explicit_atmosphere=atmosphere,
            )

            if themes:
                prompts = build_all_prompts(themes, style_mode=mode, ui_values=ui_values, run_audit=run_audit)
                if prompts:
                    prompt_data = prompts[0]
                    text = f"{prompt_data['theme_sentence']}\n\nPROMPT:\n\n{prompt_data['prompt']}\n\nNegative prompt: {prompt_data.get('negative', '(none)')}"
                    # Safely update UI from main thread using ThreadManager
                    schedule_ui_update(self._on_prompt_generated_success, text)
                else:
                    schedule_ui_update(self._on_prompt_generated_error, "Failed to generate prompt.")
            else:
                schedule_ui_update(self._on_prompt_generated_error, "Failed to generate themes.")
        except Exception as e:
            logger.error(f"Error in prompt generation thread: {e}")
            schedule_ui_update(self._on_prompt_generated_error, f"Error generating prompt: {e}")
        finally:
            # Reset flag
            self._is_generating_prompt = False

    def _on_prompt_generated_success(self, text):
        """Callback for successful prompt generation - runs on main thread."""
        try:
            self.set_prompt_text(text)
            self.status_var.set("Prompt generated successfully.")
        except Exception as e:
            logger.error(f"Error updating UI with generated prompt: {e}")
            self.status_var.set("Error displaying generated prompt.")
        finally:
            # Re-enable the generate button
            if hasattr(self, '_btn_qb_generate') and self._btn_qb_generate is not None:
                self._btn_qb_generate.config(state="normal")

    def _on_prompt_generated_error(self, error_message):
        """Callback for prompt generation error - runs on main thread."""
        try:
            self.status_var.set(error_message)
            self._dialog.error("Prompt Error", error_message)
        except Exception as e:
            logger.error(f"Error showing prompt generation error: {e}")
        finally:
            # Re-enable the generate button
            if hasattr(self, '_btn_qb_generate') and self._btn_qb_generate is not None:
                self._btn_qb_generate.config(state="normal")



    def _generate_themes_thread(self, subject, setting, style, lighting, mood, color, atmosphere, mode, subject_lock, run_audit=False):

        try:
            logger.debug(f"_generate_themes_thread called with:")
            logger.info(f"  subject='{subject}'")
            logger.info(f"  setting='{setting}'")
            logger.info(f"  style='{style}'")
            logger.info(f"  lighting='{lighting}'")
            logger.info(f"  mood='{mood}'")
            logger.info(f"  color='{color}'")
            logger.info(f"  atmosphere='{atmosphere}'")
            logger.info(f"  mode='{mode}'")
            logger.info(f"  subject_lock={subject_lock}")
            logger.info(f"  run_audit={run_audit}")

            if self.cancel_event.is_set(): return

            # Values are already passed as parameters from sidebar widget reading
            # Don't overwrite them by reading from Prompt Builder Entry widgets

            keywords = [w for w in f"{subject} {setting} {style} {lighting} {mood} {color} {atmosphere}".split() if w]
            logger.debug(f"keywords = {keywords}")

            # Build UI values dict for audit
            ui_values = {
                "subject": subject,
                "style": style,
                "lighting": lighting,
                "mood": mood,
                "color": color,
                "mode": mode,
                "atmosphere": atmosphere,
                "setting": setting
            }

            # Time theme generation for perf tracking
            gen_start = time.perf_counter()
            themes = generate_themes(

                count=1,

                user_keywords=keywords,

                subject_lock=subject_lock,

                custom_subject=subject,

                explicit_subject=subject,

                explicit_setting=setting,

                explicit_style=style,

                explicit_lighting=lighting,

                explicit_mood=mood,

                explicit_color=color,

                explicit_atmosphere=atmosphere,

            )
            gen_elapsed = time.perf_counter() - gen_start
            
            if self.cancel_event.is_set(): return

            prompts = build_all_prompts(themes, style_mode=mode, ui_values=ui_values, run_audit=run_audit) if themes else []

            # Log timing for diagnostics
            logger.debug(f"Theme generation completed: {gen_elapsed:.2f}s")

            schedule_ui_update(self._finish_generate_themes, themes, prompts, mode, None, ui_values)

        except Exception as e:
            import traceback
            error_details = f"{str(e)}\n\nTraceback:\n{traceback.format_exc()}"
            logger.error(f"[ERROR] Theme generation failed: {error_details}")
            schedule_ui_update(self._finish_generate_themes, None, None, mode, error_details, None)



    def _show_generation_progress(self):
        """Show the generation progress bar overlay."""
        if hasattr(self, 'generation_progress'):
            logger.debug("Showing generation progress bar")
            self.generation_progress.place(relx=0.5, rely=0.5, anchor="center", relwidth=0.5, relheight=0.1)
            self.generation_progress.lift()  # Bring to front
            self.generation_progress.start(10)  # Start indeterminate animation
            self.root.update_idletasks()  # Force UI update

    def _hide_generation_progress(self):
        """Hide the generation progress bar overlay (not the sidebar image_progress)."""
        if hasattr(self, 'generation_progress'):
            logger.debug("Hiding generation progress bar")
            self.generation_progress.stop()
            self.generation_progress.place_forget()
            self.root.update_idletasks()  # Force UI update
        # Do NOT hide the sidebar image_progress here - it's controlled separately

    def _finish_generate_themes(self, themes, prompts, mode, error_msg, ui_values=None):

        # Check if image generation will be triggered
        # If prompts exist and we're in generate mode (not prompt-only), image generation will follow
        # In that case, keep progress bar visible. Otherwise, hide it now.
        will_generate_image = (prompts and prompts[0] and
                                hasattr(self, 'prompt_source') and
                                self.prompt_source == "theme_builder" and
                                getattr(self, '_should_generate_image', False))

        if not will_generate_image:
            self.is_generating = False
            self._hide_generation_progress()
            # Only reset image generation progress UI when NOT generating image
            if self.image_progress.winfo_ismapped():
                self.image_progress.grid_remove()
                self.image_progress["value"] = 0
            if self.image_progress_overlay_label.winfo_ismapped():
                self.image_progress_overlay_label.config(text="")
        else:
            # Will generate image - ensure sidebar progress bar is visible
            if hasattr(self, 'image_progress'):
                self.image_progress.grid()
                self.image_progress["value"] = 0
                self.root.update_idletasks()

        if error_msg:

            self._dialog.error("Preview Failed", f"Could not generate a preview.\n\n{error_msg}")

            self.status_var.set("Preview generation failed.")

            return



        self.themes = themes
        self.prompts = prompts
        self._last_ui_values = ui_values  # cache for audit display in show_prompt

        # Ensure theme_sentence reflects the source (quick_build vs template)
        for prompt in self.prompts:
            if self.prompt_source == "theme_builder":
                theme = next((t for t in themes if t['theme_id'] == prompt['theme_id']), None)
                if theme:
                    prompt['theme_sentence'] = theme['sentence']

        self.apply_negative_prompt_to_prompts()

        if self.prompts:
            self.current_prompt_data = self.prompts[0]
            self.show_prompt()

            # Display audit results if audit mode was enabled
            if ui_values and self.prompts and "audit_results" in self.prompts[0]:
                self._display_audit_results(self.prompts[0]["audit_results"], ui_values)

            self.status_var.set(f"Generated preview in {mode} mode.")

            # Trigger image generation after themes/prompts are generated
            # Only trigger if _should_generate_image flag is True (set by generate(), not generate_prompt_only)
            if self.prompts and self.prompts[0] and getattr(self, '_should_generate_image', False):
                prompt = self.prompts[0]['prompt']
                import datetime
                filename = ui_values.get('subject', 'frog') + '_' + datetime.datetime.now().strftime('%Y%m%d_%H%M%S') + '.png'
                logger.debug(f"Triggering image generation with prompt: {prompt[:100]}...")
                self.gen_future = self.executor.submit(
                    self._generate_image_thread,
                    prompt,
                    filename,
                    False,  # auto_set_wallpaper
                    ui_values.get('subject', 'frog'),
                    ui_values.get('style', ''),
                    ui_values  # Pass full ui_values to save prompt parameters
                )
        else:
            self.current_prompt_data = None
            self.clear_prompt()
            self.clear_image()
            self.status_var.set("No preview generated.")



    def show_prompt(self, event=None):
        data = self.current_prompt_data
        if not data:
            return
        mode = data.get("style_mode", self.current_mode())
        self.update_mode_badge(mode)
        neg = data.get("negative_prompt", "")

        # Include audit results in the prompt display if available
        audit_section = ""
        if "audit_results" in data and data["audit_results"]:
            try:
                from prompt_validator import format_audit_summary
                _ui_vals = getattr(self, '_last_ui_values', None)
                _comps = (self.themes[0].get("components", {}) if getattr(self, 'themes', None) else None)
                audit_section = "\n\n" + format_audit_summary(
                    data["audit_results"],
                    ui_values=_ui_vals,
                    components=_comps,
                    final_prompt=data.get("prompt"),
                )
            except ImportError:
                pass

        text = f"{data['theme_sentence']}\n\nPROMPT:\n\n{data['prompt']}\n\nNegative prompt: {neg or '(none)'}{audit_section}"
        self.set_prompt_text(text)


    def _display_audit_results(self, audit_results, ui_values):
        """Display audit results in a message box and log warnings."""
        try:
            from prompt_validator import get_audit_warnings, format_audit_summary
            warnings = get_audit_warnings(audit_results)

            # Log to console
            logger.info("\n" + "=" * 80)
            logger.info("PROMPT VARIABLE AUDIT RESULTS")
            logger.info("=" * 80)
            _comps = (self.themes[0].get("components", {}) if getattr(self, 'themes', None) else None)
            logger.info(format_audit_summary(audit_results, ui_values=ui_values, components=_comps, final_prompt=(self.current_prompt_data or {}).get('prompt')))
            logger.info("=" * 80 + "\n")

            # Show warnings in message box if any
            if warnings:
                warning_text = "Prompt Variable Audit Warnings:\n\n" + "\n".join(warnings)
                self._dialog.warning("Prompt Variable Audit", warning_text)
            else:
                # Show success message in status
                self.status_var.set("Generated preview. Audit: All variables present in prompt.")

        except ImportError:
            pass



    def save_prompts(self):

            if not self.prompts:

                self._dialog.info("Nothing to save", "Generate a preview first.")

                return

            existing = load_json_list(PROMPTS_LOG)

            image_path = str(self.last_image_path) if self.last_image_path else ""

            enriched = []

            for item in self.prompts:

                clone = dict(item)
                clone.pop("audit_results", None)

                if image_path and not clone.get("image_path"):

                    clone["image_path"] = image_path

                clone.setdefault("saved_at", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

                enriched.append(clone)

            save_json_list(PROMPTS_LOG, existing + enriched)

            self.status_var.set(f"✓ Saved {len(enriched)} prompt(s) to log.")



    def selected_prompt(self):
        return self.current_prompt_data



    def generate_selected_image(self):

            if not has_huggingface_token():

                self._dialog.error("No API Key", "No HuggingFace token found. Go to Settings and enter your token, or switch to Pollinations.ai (free, no key needed).")

                return

            data = self.selected_prompt()

            if not data:

                self._dialog.info("No preview", "Generate a preview first.")

                return

            self.run_image_generation(

                data.get("prompt", ""), 

                data.get("theme_sentence", "prompt"), 

                data.get("style_mode", self.current_mode()),

                subject=data.get("subject"),

                art_style=data.get("art_style"),
                ui_values=self.current_prompt_data

            )



    def generate_and_set(self):
            """Set the current image as wallpaper without regenerating."""
            path = self.last_image_path or self.selected_gallery_path
            if not path:
                self._dialog.info("No image", "No image is currently loaded. Generate or select an image first.")
                return
            self.double_click_set_wallpaper(path)


    def cancel_generation(self):

        """Cancel any running generation tasks."""

        if not self.is_generating:

            return

            

        self.cancel_event.set()

        if self.gen_future:

            self.gen_future.cancel()

            

        self.is_generating = False
        self._hide_generation_progress()

        # Clear the status label
        self.image_generation_status_label.config(text="")
        self.status_var.set("Generation cancelled.")

        self.image_label.config(text="Generation cancelled", image="")

        self.preview_source_label.config(text="Cancelled")

        self.root.update_idletasks()



    def _update_progress_ui(self, value, text=None):

        """Update both the progress bar and the percentage label."""

        # Percentage calculation: Clamp value to 0-100

        val = max(0, min(100, int(value)))

        # Set progress bar value

        self.image_progress["value"] = val

        # Update label text for "how much is left" feeling

        display_text = text if text else "Generating Image..."
        self.image_progress_overlay_label.config(text=display_text)



    def _update_generation_timer(self):

            if not getattr(self, "is_generating", False) or getattr(self, "generation_cancelled", False):

                return


    def _update_image_generation_timer(self):
        """Timer function no longer needed - using simple label instead."""
        pass

    def run_image_generation(self, prompt, theme_sentence, style_mode="stylized", auto_set_wallpaper=False, subject=None, art_style=None, ui_values=None):

            if self.is_generating:

                self._dialog.info("Please wait", "An image is already being generated.")

                return

            self.generation_cancelled = False

            from wallpaper_generator import slugify_filename

            filename = slugify_filename(f"{theme_sentence}-{style_mode}")

            self.base_status_msg = f"Generating image in {style_mode} mode..."

            self.status_var.set(self.base_status_msg)

            self.update_mode_badge(style_mode)

            self.is_generating = True
            self._show_generation_progress()

            # Show image progress bar in sidebar
            if hasattr(self, 'image_progress'):
                logger.debug("Showing image_progress in sidebar")
                self.image_progress.grid()
                self.image_progress["value"] = 0
                self.root.update_idletasks()
            else:
                logger.debug("image_progress not found")

            self.cancel_event.clear()

            # Show the status label
            self.image_generation_status_label.config(text="🔄 Generating image...")

            self.image_label.config(text="Creating your wallpaper...", image="")

            self.preview_source_label.config(text=f"Generating image: {filename}")

            

            self.gen_future = self.executor.submit(

                self._generate_image_thread, 

                prompt, filename, auto_set_wallpaper, subject, art_style, ui_values

            )



    def _generate_image_thread(self, prompt, filename, auto_set_wallpaper, subject, art_style, ui_values=None):

            def status_cb(msg):

                def update():

                    self.base_status_msg = msg

                schedule_ui_update(update)

            # Progress bar is already shown in _finish_generate_themes, no need to show here

            try:

                if self.cancel_event.is_set(): return

                from wallpaper_generator import generate_image

                # Get live dimensions from the UI dropdown, not stale config
                live_dims = self.get_current_dimensions() if hasattr(self, 'get_current_dimensions') else None

                image_path = generate_image(prompt, subject=subject, style=art_style, filename=filename, status_callback=status_cb, dimensions=live_dims)

                if self.cancel_event.is_set():

                    schedule_ui_update(self._on_generation_cancelled)

                    return

                # Save prompt parameters with the generated image
                if image_path and ui_values:
                    try:
                        save_prompt_parameters(image_path, ui_values)
                    except Exception as e:
                        logger.error(f"[ERROR] Failed to save prompt parameters: {e}")

                # Auto-tag from filename: SUBJECT_STYLE_YYYYMMDD_N.png
                if image_path and subject:
                    try:
                        from gallery_manager import add_tags_to_image
                        auto_tags = [subject]
                        if art_style and art_style.lower() != subject.lower():
                            auto_tags.append(art_style)
                        # Also extract mode from UI values if present
                        mode = (ui_values or {}).get("mode", "")
                        if mode and mode.lower() not in [t.lower() for t in auto_tags]:
                            auto_tags.append(mode)
                        add_tags_to_image(image_path, auto_tags)
                    except Exception as e:
                        logger.error(f"[ERROR] Failed to auto-tag image: {e}")

                schedule_ui_update(self._on_generation_complete, image_path, auto_set_wallpaper, None)

            except Exception as e:

                if self.cancel_event.is_set():

                    schedule_ui_update(self._on_generation_cancelled)

                    return

                schedule_ui_update(self._on_generation_complete, None, False, str(e))



    def _on_generation_cancelled(self):

            self.is_generating = False
            self._hide_generation_progress()

            # Hide image progress bar in sidebar
            if hasattr(self, 'image_progress'):
                self.image_progress.grid_remove()
                self.image_progress["value"] = 0
            if hasattr(self, 'image_progress_overlay_label'):
                self.image_progress_overlay_label.config(text="")

            self.generation_cancelled = False

            # Clear the status label
            self.image_generation_status_label.config(text="")
            self.status_var.set("Image generation cancelled.")

            self.image_label.config(text="Generation cancelled", image="")

            self.preview_source_label.config(text="Cancelled")



    def _on_generation_complete(self, image_path, auto_set_wallpaper, error_msg):

            self.is_generating = False
            self._hide_generation_progress()

            # Hide image progress bar in sidebar
            if hasattr(self, 'image_progress'):
                self.image_progress.grid_remove()
                self.image_progress["value"] = 0
            if hasattr(self, 'image_progress_overlay_label'):
                self.image_progress_overlay_label.config(text="")

            # Clear the status label
            self.image_generation_status_label.config(text="")
            if error_msg:

                self._dialog.error("Image Generation Failed", f"{error_msg}")

                self.status_var.set("Image generation failed.")

                self.image_label.config(text="Generation failed", image="")

                return

            if not image_path:

                self._dialog.error("Generation Failed", "Could not generate an image. Check your API key in Settings, or try switching to a different provider.")

                self.status_var.set("Image generation failed.")

                self.image_label.config(text="Generation failed", image="")

                return

            self.last_image_path = Path(image_path)

            for item in self.prompts:

                item["image_path"] = str(self.last_image_path)

            self.load_image_preview(image_path)

            self.status_var.set(f"Generated: {self.last_image_path.name}")

            self._gallery_tab._refresh_current_view()

            if auto_set_wallpaper:

                self.set_last_image_as_wallpaper()



    def set_last_image_as_wallpaper(self):

            if not WINDOWS:

                self._dialog.info("Windows only", "Automatic wallpaper setting only works on Windows.")

                return

            if not self.last_image_path:

                self._dialog.info("No image yet", "Generate an image first.")

                return

            self.status_var.set("Setting wallpaper...")

            self.root.update_idletasks()

            try:

                success = set_wallpaper(self.last_image_path)

            except Exception as e:

                self._dialog.error("Wallpaper Error", "Could not set wallpaper. Windows may have blocked the change — try setting it manually from your Gallery.")

                self.status_var.set("Wallpaper set failed.")

                return

            if success:

                self.status_var.set(f"Wallpaper set: {self.last_image_path.name}")
                self.slideshow.reset_timer()

                self._dialog.info("Done!", "Wallpaper set successfully!")

            else:

                self.status_var.set("Wallpaper could not be set.")

                self._dialog.warning("Warning", "Image generated, but Windows did not set it as wallpaper.")
