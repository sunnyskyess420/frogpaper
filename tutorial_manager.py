import tkinter as tk
from tkinter import ttk
import logging
from typing import Callable, Optional, Dict, List

from settings_components import linkify_text_widget

logger = logging.getLogger(__name__)


class TutorialManager:
    """Manages the tutorial system including quick start, feature tour, and interactive practice."""

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
            "model_setup": {
                "title": "Model Setup Guide",
                "description": "Configure AI providers and set up models",
                "steps": self._get_model_setup_steps()
            }
        }
    
    def _get_quick_start_steps(self) -> List[Dict]:
        """Steps for the 5-minute quick start guide."""
        return [
            {
                "title": "Welcome to FrogPaper! 🐸",
                "content": "FrogPaper is your AI-powered wallpaper studio. Let's get you started with the basics in just 5 minutes.",
                "highlight": None,
                "action": None
            },
            {
                "title": "The Prompt Builder",
                "content": "On the left side, you'll find the Prompt Builder. This is where you create your wallpaper descriptions using dropdown menus for different artistic elements.",
                "highlight": "prompt_builder",
                "action": "show_prompt_builder"
            },
            {
                "title": "Choose Your Subject",
                "content": "Start by selecting a subject from the dropdown. This could be anything from 'frog' to 'mountain' to 'cityscape'.",
                "highlight": "subject_dropdown",
                "action": "highlight_subject"
            },
            {
                "title": "Add Artistic Style",
                "content": "Select artistic modes, lighting, colors, and settings to define your wallpaper's style. Try 'Digital Art' mode with 'Dramatic Lighting'!",
                "highlight": "style_dropdowns",
                "action": "highlight_styles"
            },
            {
                "title": "Generate Your Wallpaper",
                "content": "Click the 'Generate' button to create your wallpaper using AI. It usually takes 10-30 seconds depending on your provider.",
                "highlight": "generate_button",
                "action": "highlight_generate"
            },
            {
                "title": "Preview and Apply",
                "content": "Your generated wallpaper appears in the center preview. Click 'Set as Wallpaper' to apply it to your desktop!",
                "highlight": "preview_area",
                "action": "highlight_preview"
            },
            {
                "title": "Save Your Favorites",
                "content": "Use the gallery on the right to save, organize, and manage your wallpaper collection. You can create multiple galleries!",
                "highlight": "gallery",
                "action": "show_gallery"
            },
            {
                "title": "You're All Set! 🎉",
                "content": "You now know the basics! Try exploring the settings, style filters, and slideshow features. Enjoy creating beautiful wallpapers!",
                "highlight": None,
                "action": None
            }
        ]
    
    def _get_feature_tour_steps(self) -> List[Dict]:
        """Steps for the comprehensive feature tour."""
        return [
            {
                "title": "Prompt Builder",
                "content": "The left panel contains the structured prompt builder with 6 dropdown categories: Subject, Mode, Lighting, Color, Setting, and Atmosphere.",
                "highlight": "prompt_builder",
                "action": "show_prompt_builder"
            },
            {
                "title": "Preview Area",
                "content": "The center area shows your generated wallpaper with live preview and style filter controls.",
                "highlight": "preview_area",
                "action": "highlight_preview"
            },
            {
                "title": "Gallery System",
                "content": "The right panel contains 7 different gallery views including Favorites, Recent, and custom collections for organizing your wallpapers.",
                "highlight": "gallery",
                "action": "show_gallery"
            },
            {
                "title": "Style Filters",
                "content": "Apply 19 different artistic filters like Oil Painting, Cyberpunk Neon, or Vaporwave to transform your wallpapers.",
                "highlight": "style_filters",
                "action": "show_style_filters"
            },
            {
                "title": "Settings Panel",
                "content": "Configure AI providers, API tokens, slideshow timing, startup options, and app appearance.",
                "highlight": "settings",
                "action": "show_settings"
            },
            {
                "title": "System Tray",
                "content": "Minimize to tray for background operation. Right-click the tray icon for quick access to wallpaper controls.",
                "highlight": "tray",
                "action": "show_tray_info"
            },
            {
                "title": "Slideshow Mode",
                "content": "Set up automatic wallpaper rotation with customizable timing from 1-60 minutes.",
                "highlight": "slideshow",
                "action": "show_slideshow"
            },
            {
                "title": "Recipe Library",
                "content": "Save and reuse your favorite prompt combinations as recipes for quick access.",
                "highlight": "recipes",
                "action": "show_recipes"
            }
        ]
    
    def _get_practice_steps(self) -> List[Dict]:
        """Steps for interactive guided practice."""
        return [
            {
                "title": "Let's Create Together! 🎨",
                "content": "I'll guide you through creating your first wallpaper. Follow each step and I'll help you along the way.",
                "highlight": None,
                "action": None
            },
            {
                "title": "Step 1: Choose a Subject",
                "content": "Select a subject from the Subject dropdown. Try something like 'peaceful forest' or 'sunset beach'.",
                "highlight": "subject_dropdown",
                "action": "wait_for_subject_selection"
            },
            {
                "title": "Step 2: Pick an Art Mode",
                "content": "Choose an artistic mode. 'Digital Art' or 'Oil Painting' work great for beginners!",
                "highlight": "mode_dropdown",
                "action": "wait_for_mode_selection"
            },
            {
                "title": "Step 3: Add Lighting",
                "content": "Select lighting to set the mood. 'Golden Hour' or 'Dramatic Lighting' create beautiful effects.",
                "highlight": "lighting_dropdown",
                "action": "wait_for_lighting_selection"
            },
            {
                "title": "Step 4: Choose Colors",
                "content": "Pick a color palette. Try 'Vibrant' for eye-catching results or 'Monochrome' for artistic effects.",
                "highlight": "color_dropdown",
                "action": "wait_for_color_selection"
            },
            {
                "title": "Step 5: Generate!",
                "content": "Now click the Generate button and watch your creation come to life!",
                "highlight": "generate_button",
                "action": "wait_for_generation"
            },
            {
                "title": "Congratulations! 🎉",
                "content": "You've created your first wallpaper! You can now apply it, save it, or try generating more with different settings.",
                "highlight": "preview_area",
                "action": None
            }
        ]
    
    def _get_model_setup_steps(self) -> List[Dict]:
        """Steps for the model setup tutorial."""
        return [
            {
                "title": "AI Provider Setup Guide 🤖",
                "content": "FrogPaper supports multiple AI providers. Let's configure them for the best experience.",
                "highlight": None,
                "action": None
            },
            {
                "title": "Option 1: Pollinations.ai (Free - No Key)",
                "content": "The easiest option! Pollinations.ai is completely free and requires no setup. Just select it from the provider dropdown and you're ready to generate.",
                "highlight": "provider_dropdown",
                "action": "show_settings"
            },
            {
                "title": "Option 2: Cloudflare Workers AI",
                "content": "For Cloudflare, you'll need two things: 1) An API token from dash.cloudflare.com → Workers AI → Use REST API → Create Token. 2) Your Account ID from the URL or right sidebar.",
                "highlight": "cloudflare_settings",
                "action": "show_cloudflare_setup"
            },
            {
                "title": "Setting Up Cloudflare Token",
                "content": "In Settings → Generation, select 'Cloudflare Workers AI' from the provider dropdown. Then enter your token in the Cloudflare Token field and your Account ID in the Account ID field.",
                "highlight": "token_fields",
                "action": "highlight_tokens"
            },
            {
                "title": "Option 3: HuggingFace",
                "content": "HuggingFace offers access to many models. You'll need an API token from huggingface.co → Settings → Access Tokens. Different models work better for different styles.",
                "highlight": "huggingface_settings",
                "action": "show_huggingface_setup"
            },
            {
                "title": "Setting Up HuggingFace Token",
                "content": "In Settings → Generation, select 'HuggingFace' from the provider dropdown. Enter your token in the API Token field. You can also add it via your OS credential manager for security.",
                "highlight": "token_entry",
                "action": "highlight_hf_token"
            },
            {
                "title": "Choosing the Right Model",
                "content": "Different AI models excel at different styles. FLUX models are great for realistic images, SDXL models work well for artistic styles. Experiment to find your favorites!",
                "highlight": "model_selection",
                "action": "show_model_info"
            },
            {
                "title": "Testing Your Setup",
                "content": "After configuring your provider and token, try generating a simple wallpaper. If it works, you're all set! If you see errors, double-check your token and try the free Pollinations.ai option.",
                "highlight": "test_generation",
                "action": "suggest_test"
            },
            {
                "title": "You're Configured! 🎉",
                "content": "Your AI provider is now set up! You can change providers anytime in Settings. Each has different strengths - feel free to experiment with all of them.",
                "highlight": None,
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
        self.tutorial_window.geometry("700x600")
        self.tutorial_window.resizable(True, True)
        self.tutorial_window.minsize(600, 500)

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
        
        # Title label
        title_label = ttk.Label(
            main_container,
            text=self.current_tutorial["title"],
            font=("Segoe UI", 18, "bold"),
            foreground=pal["accent"]
        )
        title_label.pack(pady=(0, 5))
        
        # Description label
        desc_label = ttk.Label(
            main_container,
            text=self.current_tutorial["description"],
            font=("Segoe UI", 11),
            foreground=pal["muted"]
        )
        desc_label.pack(pady=(0, 10))
        
        # Scrollable content area
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
        
        # Step content with better padding - use Text widget for selectable/copyable content
        # Use a smaller height and auto-resize based on content
        self.step_content = tk.Text(
            scrollable_frame,
            font=("Segoe UI", 12),
            wrap="word",
            width=60,
            height=1,
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
        self.step_content.pack(pady=15, padx=10)
        self.step_content.config(state="disabled")  # Make read-only but selectable
        
        # Progress indicator
        self.progress_label = ttk.Label(
            scrollable_frame,
            text="",
            font=("Segoe UI", 11, "bold"),
            foreground=pal["accent"]
        )
        self.progress_label.pack(pady=(15, 15))
        
        # Navigation buttons
        button_frame = ttk.Frame(scrollable_frame)
        button_frame.pack(pady=(10, 0), fill="x")
        
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
        # Auto-resize: count lines and set height to fit content
        line_count = int(self.step_content.index('end-1c').split('.')[0])
        self.step_content.config(height=max(line_count + 1, 3))
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
            ("model_setup", "🤖 Model Setup Guide", "Configure AI providers and models")
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