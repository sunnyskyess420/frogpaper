import tkinter as tk
from tkinter import ttk
import logging
from typing import Dict, List

from settings_components import linkify_text_widget

logger = logging.getLogger(__name__)


class TutorialManager:
    """Manages the tutorial system including quick start, feature tour, and interactive practice.

    Provider setup guides live in Settings > Generation — not here.
    """

    def __init__(self, app):
        self.app = app
        self.current_tutorial = None
        self.current_step = 0
        self.tutorial_window = None
        self.highlight_frame = None
        self.is_active = False
        self._init_tutorials()

    def _pal(self):
        """Return the current theme's colour palette."""
        return self.app.THEMES.get(
            getattr(self.app, "current_theme_name", "darkforest"),
            self.app.THEMES["darkforest"],
        )

    def _init_tutorials(self):
        self.tutorials = {
            "quick_start": {
                "title": "Quick Start Guide",
                "description": "Learn the basics of FrogPaper in 5 minutes",
                "steps": self._get_quick_start_steps()
            },
            "feature_tour": {
                "title": "Feature Tour",
                "description": "Explore all major features of FrogPaper",
                "steps": self._get_feature_tour_steps()
            },
            "interactive_practice": {
                "title": "Interactive Practice",
                "description": "Generate your first wallpaper with guided assistance",
                "steps": self._get_practice_steps()
            },
        }
    
    def _get_quick_start_steps(self) -> List[Dict]:
        """Steps for the 5-minute quick start guide."""
        return [
            {
                "title": "Welcome to FrogPaper! 🐸",
                "content": "FrogPaper is your AI-powered wallpaper studio. It supports 6 AI providers, 25 style filters, cloud sync, and much more. Let's cover the basics in about 5 minutes.",
                "highlight": None,
                "action": None
            },
            {
                "title": "The Prompt Builder",
                "content": "The left panel is your Prompt Builder. It has 7 dropdown categories — Subject, Mode, Lighting, Color Family, Color Variation, Setting, and Atmosphere — plus keyword expansion to enrich your prompts automatically.",
                "highlight": "prompt_builder",
                "action": "show_prompt_builder"
            },
            {
                "title": "Choose Your Subject",
                "content": "Start by picking a subject from the Subject dropdown. You can type anything — 'frog', 'mountain', 'cityscape', 'dragon' — or choose from the list. Click the star next to any option to pin it to the top of the list for quick access later.",
                "highlight": "subject_dropdown",
                "action": "highlight_subject"
            },
            {
                "title": "Build Your Scene",
                "content": "Fill in the remaining dropdowns to shape your wallpaper. Try 'Digital Art' mode, 'Golden Hour' lighting, a 'Warm' color family, and 'Forest' setting. Each choice adds detail to your prompt behind the scenes.",
                "highlight": "style_dropdowns",
                "action": "highlight_styles"
            },
            {
                "title": "Generate Your Wallpaper",
                "content": "Click the Generate button to send your prompt to the selected AI provider. Pollinations.ai is the default and works for free with no setup. Other providers like Cloudflare, HuggingFace, Prodia, Replicate, and Fal.ai are available in Settings.",
                "highlight": "generate_button",
                "action": "highlight_generate"
            },
            {
                "title": "Preview, Style, and Apply",
                "content": "Your generated image appears in the center preview. From here you can apply one of 25 style filters (Oil Painting, Cyberpunk Neon, Pixel Art, and more), add text overlay, or click 'Set as Wallpaper' to apply it to your desktop immediately.",
                "highlight": "preview_area",
                "action": "highlight_preview"
            },
            {
                "title": "Explore the Gallery",
                "content": "The Gallery tab on the right organizes your collection with 7 views — Gallery (all images), Favorites, Styled (filter-applied), Manual (imported), and three ratio-based views (16:9, Portrait, Square). Use the tag system to filter by subject or style.",
                "highlight": "gallery",
                "action": "show_gallery"
            },
            {
                "title": "You're All Set! 🎉",
                "content": "You know the basics! Next steps to explore: try the slideshow mode for auto-rotating wallpapers, set up cloud sync in Settings to back up your collection, or switch AI providers to find the style that suits you best. Have fun!",
                "highlight": None,
                "action": None
            }
        ]
    
    def _get_feature_tour_steps(self) -> List[Dict]:
        """Steps for the comprehensive feature tour."""
        return [
            {
                "title": "Prompt Builder",
                "content": "The left panel contains the structured prompt builder with 7 dropdown categories: Subject, Mode, Lighting, Color Family, Color Variation, Setting, and Atmosphere. Each dropdown supports pinned favorites — click the star to keep your go-to options at the top of the list.",
                "highlight": "prompt_builder",
                "action": "show_prompt_builder"
            },
            {
                "title": "Keyword Expansion",
                "content": "When you generate, FrogPaper automatically expands your chosen subject into rich descriptive keywords. For example, 'frog' becomes 'a beautiful frog with intricate details, vibrant colors, professional photography'. You can add custom keywords and synonyms in the prompt builder.",
                "highlight": "prompt_builder",
                "action": "show_prompt_builder"
            },
            {
                "title": "6 AI Providers",
                "content": "FrogPaper supports 6 generation backends: Pollinations (free, no API key), Cloudflare Workers AI (free), HuggingFace, Prodia, Replicate, and Fal.ai. Switch providers anytime in Settings > Generation — the UI adapts to show only that provider's fields and a step-by-step setup guide.",
                "highlight": "settings",
                "action": "show_settings"
            },
            {
                "title": "Preview and Style Filters",
                "content": "The center panel shows your generated wallpaper with 25 one-click style filters: Oil Painting, Watercolor, Sketch, Line Art, Comic Book, Manga, Cyberpunk Neon, Vaporwave, Pixel Art, Anime Key, Pop Art, Impressionist, and more. You can also add text overlays for personalization.",
                "highlight": "preview_area",
                "action": "highlight_preview"
            },
            {
                "title": "Gallery Views",
                "content": "The Gallery tab has 7 views to organize your collection: Gallery (all images), Favorites (hearted), Styled (filter-applied copies), Manual (imported from disk), 16:9 (widescreen), Portrait (9:16), and Square (1:1). Use tag filters to find images by subject or style.",
                "highlight": "gallery",
                "action": "show_gallery"
            },
            {
                "title": "Cloud Sync",
                "content": "Connect Google Drive, OneDrive, or Dropbox to sync your wallpaper collection across devices. Set it up in Settings > Cloud Storage. Changes are detected automatically and synced in the background.",
                "highlight": "settings",
                "action": "show_settings"
            },
            {
                "title": "Slideshow and Tray",
                "content": "Enable slideshow mode to auto-rotate wallpapers at your chosen interval (1-60 minutes). Minimize FrogPaper to the system tray for background operation — right-click the tray icon for quick wallpaper controls.",
                "highlight": "slideshow",
                "action": "show_slideshow"
            },
            {
                "title": "Recipes and Templates",
                "content": "Save your favorite prompt combinations as recipes for one-click reuse. The recipe library lets you name, organize, and reload complete setups including all dropdown values and provider settings.",
                "highlight": "recipes",
                "action": "show_recipes"
            },
            {
                "title": "Themes and Appearance",
                "content": "FrogPaper includes multiple built-in themes (dark and light) that restyle the entire UI. Switch themes in Settings > Appearance. Your chosen theme persists across restarts.",
                "highlight": "settings",
                "action": "show_settings"
            }
        ]
    
    def _get_practice_steps(self) -> List[Dict]:
        """Steps for interactive guided practice."""
        return [
            {
                "title": "Let's Create Together! 🎨",
                "content": "I'll walk you through creating your first wallpaper step by step. Just follow along at your own pace — there's no rush.",
                "highlight": None,
                "action": None
            },
            {
                "title": "Step 1: Pick a Subject",
                "content": "Go to the Prompt Builder tab and find the Subject field. Type anything you like — 'frog', 'mountain lake', 'neon city', 'dragon in flight' — or pick from the dropdown list. This is the main focus of your wallpaper.",
                "highlight": "subject_dropdown",
                "action": "wait_for_subject_selection"
            },
            {
                "title": "Step 2: Choose a Mode",
                "content": "The Mode dropdown controls the artistic style of the generation. 'Digital Art' is a great all-rounder. 'Photography' gives realistic results. 'Oil Painting' and 'Watercolor' produce hand-crafted feels. Pick whatever appeals to you!",
                "highlight": "mode_dropdown",
                "action": "wait_for_mode_selection"
            },
            {
                "title": "Step 3: Set the Lighting",
                "content": "Lighting makes a huge difference. Try 'Golden Hour' for warm sunset vibes, 'Dramatic Lighting' for high contrast, or 'Neon' for a cyberpunk feel. This is where your wallpaper starts to take on a mood.",
                "highlight": "lighting_dropdown",
                "action": "wait_for_lighting_selection"
            },
            {
                "title": "Step 4: Color and Setting",
                "content": "Pick a Color Family (like 'Warm' or 'Cool') and a Setting (like 'Forest', 'Ocean', or 'Space'). These fill in the background and color palette of your scene. Don't overthink it — you can always regenerate!",
                "highlight": "color_dropdown",
                "action": "wait_for_color_selection"
            },
            {
                "title": "Step 5: Generate!",
                "content": "Click the Generate button. FrogPaper sends your prompt to the AI provider (Pollinations.ai by default — free, no setup required). Generation typically takes 10-30 seconds. Watch the status bar for progress.",
                "highlight": "generate_button",
                "action": "wait_for_generation"
            },
            {
                "title": "Step 6: Style It (Optional)",
                "content": "Once your image appears, try applying a style filter from the 'Apply Style' dropdown — Oil Painting, Cyberpunk Neon, or Pixel Art are popular choices. You can also add text overlay or click the heart icon to favorite it.",
                "highlight": "preview_area",
                "action": None
            },
            {
                "title": "Congratulations! 🎉",
                "content": "You've created your first wallpaper! Click 'Set as Wallpaper' to apply it, or head to the Gallery to see it saved. Try different subjects, modes, and providers to discover what you like. Check out the Feature Tour for more tips!",
                "highlight": "gallery",
                "action": None
            }
        ]
    
    def start_tutorial(self, tutorial_id: str):
        """Start a specific tutorial."""
        if tutorial_id not in self.tutorials:
            logger.error(f"Unknown tutorial: {tutorial_id}")
            return
        
        self.current_tutorial = self.tutorials[tutorial_id]
        self.current_step = 0
        self.is_active = True
        self._show_tutorial_window()
        self._show_current_step()
    
    def _show_tutorial_window(self):
        """Create and show the tutorial window."""
        if self.tutorial_window:
            self.tutorial_window.destroy()
        
        self.tutorial_window = tk.Toplevel(self.app.root)
        self.tutorial_window.title(self.current_tutorial["title"])
        self.tutorial_window.geometry("760x660")
        self.tutorial_window.resizable(True, True)
        self.tutorial_window.minsize(640, 550)

        from utils import center_window
        center_window(self.app.root, self.tutorial_window)
        
        # Keep tutorial on top of main window but allow interaction with it
        self.tutorial_window.transient(self.app.root)  # Makes tutorial stay above main window
        self.tutorial_window.lift()  # Bring to front
        
        # Style the window — use theme palette colours
        pal = self._pal()
        self.tutorial_window.configure(bg=pal["bg"])
        
        # Main container — use default TFrame (bg matches window)
        main_container = ttk.Frame(self.tutorial_window)
        main_container.pack(fill="both", expand=True, padx=20, pady=20)
        
        # ---- Fixed header (title + description) ----
        title_label = ttk.Label(
            main_container,
            text=self.current_tutorial["title"],
            font=("Segoe UI", 18, "bold"),
            foreground=pal["accent"]
        )
        title_label.pack(pady=(0, 5))
        
        desc_label = ttk.Label(
            main_container,
            text=self.current_tutorial["description"],
            font=("Segoe UI", 11),
            foreground=pal["muted"]
        )
        desc_label.pack(pady=(0, 10))

        # ---- Fixed footer (progress + nav buttons) — packed FIRST so it
        #      claims space from the bottom; the canvas will fill the rest.
        bottom_frame = ttk.Frame(main_container)
        bottom_frame.pack(side="bottom", fill="x", pady=(10, 0))

        # Progress indicator (in fixed footer)
        self.progress_label = ttk.Label(
            bottom_frame,
            text="",
            font=("Segoe UI", 11, "bold"),
            foreground=pal["accent"]
        )
        self.progress_label.pack(pady=(0, 5))

        # Navigation buttons (in fixed footer)
        button_frame = ttk.Frame(bottom_frame)
        button_frame.pack(fill="x")
        
        self.prev_button = ttk.Button(
            button_frame,
            text="← Previous",
            command=self._previous_step,
            state="disabled"
        )
        self.prev_button.pack(side="left", padx=5)
        
        self.next_button = ttk.Button(
            button_frame,
            text="Next →",
            command=self._next_step
        )
        self.next_button.pack(side="right", padx=5)
        
        self.close_button = ttk.Button(
            button_frame,
            text="Skip Tutorial",
            command=self._close_tutorial
        )
        self.close_button.pack(side="right", padx=5)

        # ---- Scrollable content area (fills remaining space) ----
        canvas = tk.Canvas(main_container, highlightthickness=0, bg=pal["bg"])
        scrollbar = ttk.Scrollbar(main_container, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="n")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Make the scrollable frame fill the canvas width
        def _resize_scrollable(event):
            canvas.itemconfig(canvas.find_withtag("all")[0], width=event.width)
        canvas.bind("<Configure>", _resize_scrollable)

        # Mouse-wheel scrolling — register with the app's hover-based router
        def _on_enter(event):
            self.app._hover_canvas = canvas
        def _on_leave(event):
            if self.app._hover_canvas is canvas:
                self.app._hover_canvas = None
        canvas.bind('<Enter>', _on_enter)
        canvas.bind('<Leave>', _on_leave)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Step content — use Text widget for selectable/copyable text.
        # No fixed width: fill="x" lets it adapt to the window width;
        # height is set dynamically in _show_current_step() via bbox.
        self.step_content = tk.Text(
            scrollable_frame,
            font=("Segoe UI", 12),
            wrap="word",
            bg=pal["bg"],
            fg=pal["text"],
            highlightthickness=0,
            padx=10,
            pady=10,
            relief="flat",
            borderwidth=0,
            selectbackground=pal["selected_bg"],
            selectforeground=pal["selected_fg"],
            inactiveselectbackground=pal["bg"],
        )
        self.step_content.pack(pady=10, padx=10, fill="x")
        self.step_content.config(state="disabled")  # Make read-only but selectable
        # read-only text: keep it OUT of the Tab ring (it would trap Tab)
        try:
            from ui_effects import make_text_tab_friendly
            make_text_tab_friendly(self.step_content)
        except ImportError:
            pass
    
    def _show_current_step(self):
        """Display the current tutorial step."""
        if not self.current_tutorial or self.current_step >= len(self.current_tutorial["steps"]):
            self._close_tutorial()
            return
        
        step = self.current_tutorial["steps"][self.current_step]
        
        # Update content in Text widget
        self.step_content.config(state="normal")
        self.step_content.delete(1.0, tk.END)
        self.step_content.insert(tk.END, step["content"])

        # --- Auto-resize height to fit ALL visible (wrapped) text ---
        # Force the geometry manager to calculate layout so bbox is valid.
        self.step_content.update_idletasks()

        # Measure the first line's height and the last character's position
        # to compute the total number of *display* lines (accounting for
        # word-wrap), not just paragraph/newline boundaries.
        first_bbox = self.step_content.bbox("1.0")
        last_bbox  = self.step_content.bbox("end-1c")

        if first_bbox and last_bbox:
            line_h = first_bbox[3]                       # pixel height of one line
            total_px = last_bbox[1] + last_bbox[3]       # bottom edge of last char
            display_lines = max(3, round(total_px / line_h))
        else:
            display_lines = 3                             # safe fallback
        self.step_content.config(height=display_lines)

        # Make website references clickable (same treatment as the cloud
        # "How to get your credentials" guides in Settings).  Bare domains
        # like dash.cloudflare.com open with an https:// prefix.
        self._step_links = linkify_text_widget(
            self.step_content,
            link_color=self._pal().get("accent", "#60a5fa"),
        )
        self.step_content.config(state="disabled")
        
        # Update progress
        progress_text = f"Step {self.current_step + 1} of {len(self.current_tutorial['steps'])}"
        self.progress_label.config(text=progress_text)
        
        # Update buttons
        self.prev_button.config(state="normal" if self.current_step > 0 else "disabled")
        
        if self.current_step == len(self.current_tutorial["steps"]) - 1:
            self.next_button.config(text="Finish")
        else:
            self.next_button.config(text="Next →")
        
        # Highlight UI element if specified
        if step.get("highlight"):
            self._highlight_element(step["highlight"])
        else:
            self._remove_highlight()
        
        # Execute action if specified
        if step.get("action"):
            self._execute_action(step["action"])
    
    def _highlight_element(self, element_id: str):
        """Highlight a specific UI element."""
        self._remove_highlight()
        
        # Map element IDs to actual widgets
        element_map = {
            "prompt_builder": self.app.prompt_tab if hasattr(self.app, 'prompt_tab') else None,
            "subject_dropdown": self.app.subject_var if hasattr(self.app, 'subject_var') else None,
            "preview_area": None,  # Would need actual widget reference
            "gallery": self.app.gallery_tab if hasattr(self.app, 'gallery_tab') else None,
            "settings": self.app.settings_tab if hasattr(self.app, 'settings_tab') else None,
        }
        
        # For now, we'll just log this - actual highlighting would need widget references
        logger.info(f"Highlighting element: {element_id}")
    
    def _remove_highlight(self):
        """Remove any UI highlighting."""
        if self.highlight_frame:
            self.highlight_frame.destroy()
            self.highlight_frame = None
    
    def _execute_action(self, action: str):
        """Execute a tutorial action."""
        # Map actions to actual methods
        action_map = {
            "show_prompt_builder": lambda: self.app._show_tab("prompt") if hasattr(self.app, '_show_tab') else None,
            "show_gallery": lambda: self.app._show_tab("gallery") if hasattr(self.app, '_show_tab') else None,
            "show_settings": lambda: self.app._show_tab("settings") if hasattr(self.app, '_show_tab') else None
        }
        
        if action in action_map:
            try:
                action_map[action]()
            except Exception as e:
                logger.error(f"Failed to execute action {action}: {e}")
        else:
            logger.info(f"Action {action} not yet implemented")
    
    def _next_step(self):
        """Move to the next tutorial step."""
        if self.current_step < len(self.current_tutorial["steps"]) - 1:
            self.current_step += 1
            self._show_current_step()
        else:
            self._close_tutorial()
    
    def _previous_step(self):
        """Move to the previous tutorial step."""
        if self.current_step > 0:
            self.current_step -= 1
            self._show_current_step()
    
    def _close_tutorial(self):
        """Close the tutorial window."""
        self.is_active = False
        self._remove_highlight()
        if self.tutorial_window:
            self.tutorial_window.destroy()
            self.tutorial_window = None
        
        # Mark tutorial as completed in config
        self._mark_tutorial_completed()
    
    def _mark_tutorial_completed(self):
        """Mark the current tutorial as completed."""
        if self.current_tutorial:
            from utils import load_config, save_config
            config = load_config()
            if "completed_tutorials" not in config:
                config["completed_tutorials"] = []
            
            tutorial_name = self.current_tutorial["title"]
            if tutorial_name not in config["completed_tutorials"]:
                config["completed_tutorials"].append(tutorial_name)
                save_config(config)
                logger.info(f"Marked tutorial as completed: {tutorial_name}")
    
    def is_tutorial_completed(self, tutorial_id: str) -> bool:
        """Check if a tutorial has been completed."""
        from utils import load_config
        config = load_config()
        completed = config.get("completed_tutorials", [])
        
        if tutorial_id in self.tutorials:
            return self.tutorials[tutorial_id]["title"] in completed
        return False
    
    def should_show_first_run_tutorial(self) -> bool:
        """Check if first-run tutorial should be shown."""
        from utils import load_config
        config = load_config()
        return not config.get("first_run_completed", False)
    
    def mark_first_run_completed(self):
        """Mark first-run tutorial as completed."""
        from utils import load_config, save_config
        config = load_config()
        config["first_run_completed"] = True
        save_config(config)
        logger.info("Marked first-run tutorial as completed")
    
    def _show_tutorial_menu(self):
        """Show a menu to select which tutorial to start."""
        if self.tutorial_window:
            self.tutorial_window.destroy()
        
        menu_window = tk.Toplevel(self.app.root)
        menu_window.title("Tutorials")
        menu_window.geometry("450x550")
        menu_window.resizable(True, True)
        menu_window.minsize(400, 450)
        menu_window.attributes('-topmost', True)

        from utils import center_window
        center_window(self.app.root, menu_window)
        
        # Style the window — use theme palette colours
        pal = self._pal()
        menu_window.configure(bg=pal["bg"])
        
        # Main container
        main_container = ttk.Frame(menu_window)
        main_container.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Title
        title_label = ttk.Label(
            main_container,
            text="🎓 FrogPaper Tutorials",
            font=("Segoe UI", 20, "bold"),
            foreground=pal["accent"]
        )
        title_label.pack(pady=(0, 15))
        
        # Scrollable area for tutorial options
        canvas = tk.Canvas(main_container, highlightthickness=0, bg=pal["bg"])
        scrollbar = ttk.Scrollbar(main_container, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="n")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Make the scrollable frame fill the canvas width
        def _resize_scrollable(event):
            canvas.itemconfig(canvas.find_withtag("all")[0], width=event.width)
        canvas.bind("<Configure>", _resize_scrollable)
        
        # Mouse-wheel scrolling — register with the app's hover-based router
        # (set up by gallery_tab) so it doesn't override gallery scrolling.
        def _on_enter(event):
            self.app._hover_canvas = canvas
        def _on_leave(event):
            if self.app._hover_canvas is canvas:
                self.app._hover_canvas = None
        canvas.bind('<Enter>', _on_enter)
        canvas.bind('<Leave>', _on_leave)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Tutorial options
        tutorials_info = [
            ("quick_start", "🚀 Quick Start Guide", "Learn the basics in 5 minutes"),
            ("feature_tour", "🗺️ Feature Tour", "Explore all major features"),
            ("interactive_practice", "🎨 Interactive Practice", "Guided wallpaper generation"),
        ]

        # Centering wrapper — constrains card width and centers content
        center_frame = ttk.Frame(scrollable_frame)
        center_frame.pack(fill="x", expand=True)

        for tutorial_id, title, description in tutorials_info:
            is_completed = self.is_tutorial_completed(tutorial_id)
            
            # Tutorial card
            card_frame = ttk.Frame(center_frame, padding=18)
            card_frame.pack(fill="x", pady=10)
            
            # Tutorial title
            title_label = ttk.Label(
                card_frame,
                text=title,
                font=("Segoe UI", 13, "bold"),
                foreground=pal["text"]
            )
            title_label.pack(anchor="w")
            
            # Description
            desc_label = ttk.Label(
                card_frame,
                text=description,
                font=("Segoe UI", 11),
                foreground=pal["muted"]
            )
            desc_label.pack(anchor="w", pady=(5, 12))
            
            # Button row
            button_row = ttk.Frame(card_frame)
            button_row.pack(fill="x")
            
            # Start button
            start_button = ttk.Button(
                button_row,
                text="Start Tutorial",
                command=lambda tid=tutorial_id: self._start_from_menu(menu_window, tid)
            )
            start_button.pack(side="left")
            
            # Completion status
            if is_completed:
                status_label = ttk.Label(
                    button_row,
                    text="✓ Completed",
                    foreground=pal["success_color"],
                    font=("Segoe UI", 11, "bold")
                )
                status_label.pack(side="right")
        
        # Close button
        close_button = ttk.Button(
            center_frame,
            text="Close",
            command=menu_window.destroy
        )
        close_button.pack(pady=(20, 0))
    
    def _start_from_menu(self, menu_window, tutorial_id):
        """Start tutorial from menu and close menu."""
        menu_window.destroy()
        self.start_tutorial(tutorial_id)