import sys
import os

from theme import COLOR_DIM_GRAY, COLOR_NEAR_BLACK, COLOR_WHITE  # shared color constants (migrated inline hex)

# App version - single source of truth for version string
# Must match the AppVersion in build_installer.bat and the GitHub release tag.
APP_VERSION = "1.5.0"

# Ensure local modules are found regardless of working directory
# In frozen PyInstaller exe, _MEIPASS already handles this — don't override it
if getattr(sys, 'frozen', False):
    # Running as PyInstaller bundle — use the extraction temp dir
    os.environ['FROGPAPER_ROOT'] = sys._MEIPASS
else:
    # Running as normal python script — add script's directory to path
    _script_dir = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, _script_dir)
    os.environ['FROGPAPER_ROOT'] = _script_dir

import tkinter as tk

import shutil

import tkinter.font as tkfont
import logging
from logging.handlers import RotatingFileHandler

from utils import get_app_dir

# Configure logging: INFO messages in the terminal PLUS a rotating file in
# logs/frogpaper.log — so errors are diagnosable even in the packaged EXE,
# which has no visible console. 2 MB per file, 3 backups = ~8 MB maximum.
_logging_handlers = [logging.StreamHandler()]
try:
    _logs_dir = get_app_dir() / "logs"
    _logs_dir.mkdir(exist_ok=True)
    _logging_handlers.append(RotatingFileHandler(
        _logs_dir / "frogpaper.log",
        maxBytes=2 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    ))
except Exception:
    pass  # file logging is optional — never block startup on it

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=_logging_handlers
)

import ctypes
import ctypes.wintypes

logger = logging.getLogger(__name__)

import threading

import concurrent.futures


import time

import random

from tkinter import ttk, simpledialog

# Runtime/platform probing moved to app_runtime.py (roadmap #7 Phase B step 2).
# Re-imported so app.<NAME>, bare names and monkeypatching keep working.
from app_runtime import (
    KEYBOARD_AVAILABLE,
    PINNED_DROPDOWNS_AVAILABLE,
    PYSTRAY_AVAILABLE,
    RoundedButton,
    SV_TTK_AVAILABLE,
    UI_EFFECTS_AVAILABLE,
    WINDOWS,
    apply_glass_to_dialog,
    collect_wallpapers,
    make_text_tab_friendly,
    run_background,
    schedule_ui_update,
)
if KEYBOARD_AVAILABLE:
    from app_runtime import keyboard
if PINNED_DROPDOWNS_AVAILABLE:
    from app_runtime import PinnedCombobox, init_pinned_manager
if SV_TTK_AVAILABLE:
    from app_runtime import sv_ttk

# stdlib imports that used to sit between the optional-dependency blocks
from pathlib import Path




from theme_mixer import generate_themes
from slideshow import SlideshowManager
from keyword_expander import warmup_keyword_expander







from preset_manager import (
    load_presets,
    save_bundle_preset,
    get_preset_by_id,
    import_preset,
)

from utils import (
    save_json_list,
    load_config,
    save_config,
    get_app_dir,
    seed_bundled_files,
)

seed_bundled_files()

from session_manager import SessionManager
from tray_manager import TrayManager
from tutorial_manager import TutorialManager
from settings_tab import SettingsTab
from prompt_tab import PromptTab
from gallery_tab import GalleryTab


# ──── Data modules (roadmap #7 Phase B) ──────────────────────────────────
# Theme palettes, UI spacing constants and the prompt/provider option
# tables moved to app_themes.py / app_prompt_data.py.  They are
# re-imported here so that app.<NAME> access from other modules,
# bare-name references inside class methods, and test monkeypatching of
# app.<NAME> all keep working exactly as before.
from app_themes import (  # noqa: F401
    THEMES,
    UI,
    THEME_DISPLAY_NAMES,
    THEME_INTERNAL_NAMES,
    _rel_luminance,   # noqa: F401 (re-export; used by ThemedDialog too)
    _contrast_ratio,  # noqa: F401
    _readable_fg,
)
from app_prompt_data import (  # noqa: F401
    DEFAULT_NEGATIVE_PROMPT,
    PROMPT_MODE_OPTIONS,
    PROMPT_MODE_LABELS,
    PROMPT_MODE_LABEL_TO_VALUE,
    PROMPT_MODE_VALUE_TO_LABEL,
    DEFAULT_PROMPT_MODE_VALUE,
    DEFAULT_PROMPT_MODE_LABEL,
    STYLE_MODES,
    COLOR_FAMILIES,
    COLOR_VARIATIONS,
    SLIDESHOW_SOURCES,
    SLIDESHOW_SOURCE_LABELS,
    SLIDESHOW_SOURCE_DISPLAY,
    SLIDESHOW_LABEL_TO_VALUE,
    PROVIDER_OPTIONS,
    PROVIDER_MODELS,
    MODEL_OPTIONS,
    MODEL_DISPLAY_TO_ID,
    MODEL_ID_TO_DISPLAY,
    IMAGE_EXTS,
    _GALLERY_CARD_H,
    DIMENSION_PRESETS,
    _BASE_SETTING_OPTIONS,   # noqa: F401
    LEGACY_SETTING_OPTIONS,  # noqa: F401
    _BASE_SUBJECT_OPTIONS,   # noqa: F401
    LEGACY_SUBJECT_OPTIONS,  # noqa: F401
    _BASE_STYLE_OPTIONS,     # noqa: F401
    LEGACY_STYLE_OPTIONS,    # noqa: F401
    _BASE_LIGHTING_OPTIONS,  # noqa: F401
    LEGACY_LIGHTING_OPTIONS, # noqa: F401
    _BASE_MOOD_OPTIONS,      # noqa: F401
    LEGACY_MOOD_OPTIONS,     # noqa: F401
    _BASE_ATMOSPHERE_OPTIONS,  # noqa: F401
    LEGACY_ATMOSPHERE_OPTIONS, # noqa: F401
    _merge_options,          # noqa: F401
    THEME_VARIABLE_OPTIONS,
)






# Filesystem layout constants moved to app_paths.py (roadmap #7 Phase B step 2).
# Re-imported at the same point of start-up (mkdir side effects preserved).
from app_paths import (
    BASE_DIR,
    LOGS_DIR,
    PROMPTS_LOG,
    FAVORITES_LOG,
    FAVORITES_DIR,
    STYLED_DIR,
    MANUAL_DIR,
    PRESETS_FILE,
    SESSIONS_FILE,
)

# Migrate old top-level favorites/ folder — runs ONCE then renames source so it never repeats
old_favorites_dir = BASE_DIR / "favorites"
if old_favorites_dir.exists() and old_favorites_dir.is_dir():
    import shutil
    try:
        for file in old_favorites_dir.iterdir():
            if file.is_file() and file.suffix.lower() in {'.png', '.jpg', '.jpeg', '.webp', '.bmp'}:
                dest = FAVORITES_DIR / file.name
                if not dest.exists():  # never overwrite — skip if already present
                    shutil.copy2(file, dest)
        # Rename so this block never runs again
        old_favorites_dir.rename(BASE_DIR / "favorites_migrated")
    except Exception:
        pass  # Ignore migration errors






# ──── Fullscreen detection (Windows API) ──────────────────────────────────

_user32 = ctypes.windll.user32


class _RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]


def _is_foreground_window_fullscreen():
    """Return True if the foreground window covers the entire primary monitor."""
    try:
        hwnd = _user32.GetForegroundWindow()
        if not hwnd:
            return False
        rect = _RECT()
        _user32.GetWindowRect(hwnd, ctypes.byref(rect))
        screen_w = _user32.GetSystemMetrics(0)
        screen_h = _user32.GetSystemMetrics(1)
        win_w = rect.right - rect.left
        win_h = rect.bottom - rect.top
        return (win_w >= screen_w - 4 and win_h >= screen_h - 4)
    except Exception:
        return False







# ── Negative Prompt Builder helpers ──────────────────────────────────

class _TextVarBridge:
    """Shim so that code calling .get()/.delete(0,END)/.insert(0,val) on
    ``negative_prompt_entry`` works with the new Text widget + StringVar.
    """
    def __init__(self, text_widget: tk.Text, string_var: tk.StringVar):
        self._text = text_widget
        self._var = string_var

    def get(self):
        return self._var.get()

    def delete(self, start, end):
        self._text.delete("1.0", tk.END)

    def insert(self, index, value):
        self._text.delete("1.0", tk.END)
        self._text.insert("1.0", value)
        self._var.set(value)


class _FakePresetListbox:
    """Drop-in replacement for the old tk.Listbox so that
    ``apply_negative_prompt_to_prompts`` in prompt_tab.py can still call
    ``.curselection()`` and ``.get(idx)`` without changes.
    """
    def __init__(self, preset_vars: dict, preset_info: list):
        self._vars = preset_vars        # key -> BooleanVar
        self._info = preset_info        # [(key, dname, desc, negs, term_count), ...]

    def curselection(self):
        """Return tuple of indices for checked presets."""
        return tuple(
            i for i, (key, *_) in enumerate(self._info)
            if self._vars[key].get()
        )

    def get(self, idx):
        """Return display name at *idx*."""
        return self._info[idx][1]


class ThemedDialog:
    """Themed replacements for tkinter.messagebox dialogs.

    Usage (inside FrogPaperApp):
        self._dialog.info("Title", "Message")
        self._dialog.warning("Title", "Message")
        self._dialog.error("Title", "Message")
        result = self._dialog.ask("Title", "Question")  # returns True/False
    """

    _ICONS = {
        "info":    "info",
        "warning": "warning",
        "error":   "error",
        "ask":     "ask",
    }

    def __init__(self, app):
        self._app = app
        # Resolve popup sound path once
        self._sound_path = Path(__file__).parent / "sounds" / "frog-croak.mp3"

    def _play_popup_sound(self):
        """Play ribbit sound non-blocking on every popup. Each call gets a unique alias so overlapping popups don't cut each other short."""
        import uuid
        alias = f"popup_snd_{uuid.uuid4().hex[:8]}"
        def _play():
            try:
                import sys
                sp = str(self._sound_path)
                if not self._sound_path.exists():
                    return
                if sys.platform == "win32":
                    import ctypes
                    winmm = ctypes.windll.winmm
                    winmm.mciSendStringW(f'open "{sp}" alias {alias}', None, 0, None)
                    winmm.mciSendStringW(f'play {alias} wait', None, 0, None)
                    winmm.mciSendStringW(f'close {alias}', None, 0, None)
                else:
                    import subprocess
                    player = ("afplay" if sys.platform == "darwin"
                              else "mpv")
                    subprocess.run(
                        [player, "--no-video", sp],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass
        try:
            run_background(_play)
        except Exception:
            pass

    def _pal(self):
        theme = getattr(self._app, "current_theme_name", "darkforest")
        return THEMES.get(theme, THEMES["darkforest"])

    def _show(self, kind: str, title: str, message: str, buttons=("OK",)) -> str:
        self._play_popup_sound()
        pal = self._pal()
        accent = pal.get("accent", pal["progress"])

        dlg = tk.Toplevel(self._app.root)
        dlg.title(title)
        dlg.configure(bg=pal["bg"])
        dlg.resizable(True, True)
        dlg.grab_set()

        # Calculate width based on message length, with min/max bounds
        # (must be computed BEFORE apply_glass_to_dialog which uses w, h)
        msg_lines = message.split("\n")
        max_line_length = max(len(line) for line in msg_lines) if msg_lines else 0
        w = min(max(380, max_line_length * 8 + 100), 800)  # Scale with content, cap at 800
        h = 160 + len(msg_lines) * 16

        # ── Glassmorphism overlay for ThemedDialog ──
        if UI_EFFECTS_AVAILABLE and apply_glass_to_dialog:
            try:
                apply_glass_to_dialog(dlg, width=w, height=h,
                                      corner_radius=16, bg_color=pal["bg"])
            except Exception:
                pass

        # Mist/fog overlay effect for FrogSwamp themes
        mist_color = pal.get("mist_color")
        mist_alpha = pal.get("mist_alpha", 0)
        if mist_color and mist_alpha > 0:
            # Create a semi-transparent overlay frame (simulated with lighter color)
            mist_frame = tk.Frame(dlg, bg=mist_color)
            mist_frame.place(relx=0, rely=0, relwidth=1, relheight=1)
            mist_frame.lower()  # Put behind content

        # Center over parent
        dlg.update_idletasks()
        pw = self._app.root.winfo_width()
        ph = self._app.root.winfo_height()
        px = self._app.root.winfo_rootx()
        py = self._app.root.winfo_rooty()
        
        x = px + (pw - w) // 2
        y = py + (ph - h) // 2
        dlg.geometry(f"{w}x{h}+{x}+{y}")

        result = tk.StringVar(value=buttons[-1])

        # Icon + message
        top = tk.Frame(dlg, bg=pal["bg"], padx=18, pady=14)
        top.pack(fill="both", expand=True)
        try:
            from icons import get_dialog_icon
            _icon_img = get_dialog_icon(kind, size=28, color=accent)
            icon_lbl = tk.Label(top, image=_icon_img, bg=pal["bg"])
        except Exception:
            icon_lbl = tk.Label(top, text=self._ICONS.get(kind, "info"),
                                font=("Segoe UI", 18, "bold"),
                                bg=pal["bg"], fg=accent)
        icon_lbl.pack(side="left", padx=(0, 12))
        msg_lbl = tk.Label(top, text=message, wraplength=w - 90,
                           justify="left", bg=pal["bg"], fg=pal["text"],
                           font=("Segoe UI", 10))
        msg_lbl.pack(side="left", fill="both", expand=True)

        # Separator
        sep = tk.Frame(dlg, bg=pal.get("border_color", pal["panel2"]), height=1)
        sep.pack(fill="x")

        # Buttons
        btn_row = tk.Frame(dlg, bg=pal["bg"], padx=14, pady=10)
        btn_row.pack(fill="x")

        def make_cmd(val):
            def _cmd():
                result.set(val)
                dlg.grab_release()
                dlg.destroy()
            return _cmd

        for i, label in enumerate(reversed(buttons)):
            is_primary = (i == 0)
            bg = accent if is_primary else pal["panel2"]
            # Secondary buttons sit on the panel2 surface — a white
            # button_fg (neoncyber_light) would be invisible there.
            if is_primary:
                fg = _readable_fg(pal["button_fg"], COLOR_NEAR_BLACK,
                                  COLOR_WHITE, accent)
            else:
                fg = _readable_fg(pal["text"], COLOR_NEAR_BLACK,
                                  COLOR_WHITE, pal["panel2"])
            if UI_EFFECTS_AVAILABLE and is_primary:
                btn = RoundedButton(
                    btn_row, text=label, width=80, height=30,
                    fill_color=accent, text_color=fg,
                    radius=8, font=("Segoe UI", 9, "bold"),
                    command=make_cmd(label), use_gradient=True,
                )
                btn.pack(side="right", padx=(6, 0))
            else:
                btn = tk.Button(
                    btn_row, text=label, bg=bg, fg=fg,
                    activebackground=pal["button_hover"], activeforeground=fg,
                    relief="flat", padx=16, pady=5, cursor="hand2",
                    font=("Segoe UI", 9, "bold" if is_primary else "normal"),
                    command=make_cmd(label),
                )
                btn.pack(side="right", padx=(6, 0))

        dlg.bind("<Return>", lambda e: make_cmd(buttons[0])())
        dlg.bind("<Escape>", lambda e: make_cmd(buttons[-1])())
        dlg.protocol("WM_DELETE_WINDOW", make_cmd(buttons[-1]))

        self._app.root.wait_window(dlg)
        return result.get()

    def info(self, title: str, message: str):
        self._show("info", title, message, buttons=("OK",))

    def warning(self, title: str, message: str):
        self._show("warning", title, message, buttons=("OK",))

    def error(self, title: str, message: str):
        self._show("error", title, message, buttons=("OK",))

    def ask(self, title: str, message: str) -> bool:
        return self._show("ask", title, message, buttons=("Yes", "No")) == "Yes"




# Theme engine lives in its own module (roadmap #7 Phase B step 2):
# apply_theme + all retheme/cursor helpers mix into FrogPaperApp below.
from app_theme_engine import FrogPaperAppThemeMixin


from app_generation_mixin import FrogPaperAppGenerationMixin
from app_system_mixin import FrogPaperAppSystemMixin
from app_cloud_mixin import FrogPaperAppCloudMixin
from app_delegates_mixin import FrogPaperAppDelegatesMixin

class FrogPaperApp(FrogPaperAppThemeMixin, FrogPaperAppGenerationMixin,
        FrogPaperAppSystemMixin, FrogPaperAppCloudMixin,
        FrogPaperAppDelegatesMixin):
    def __init__(self, root):
        """Initialize the FrogPaper application."""
        self.root = root
        self.root.title("FrogPaper - AI Wallpaper Generator")
        # Open centered in the visible work area (screen minus taskbar) and
        # never larger than it — the fixed 1600x900 window used to hang off
        # the bottom of the screen behind the taskbar.
        from utils import place_on_work_area
        _fit_w, _fit_h = place_on_work_area(self.root, 1600, 900)
        
        # Initialize thread-safe UI queue system
        from thread_manager import initialize_thread_manager
        initialize_thread_manager(root)
        
        # Initialize sync manager for automatic backups
        self.sync_manager = None
        self.backup_scheduler_job = None
        self._backup_stop_event = threading.Event()
        
        # Initialize SQLite database (migrates existing JSON on first run)
        try:
            import database
            database.init_db()
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning("Database init failed, will use fallback: %s", e)

        self.root.title("FrogPaper")

        # Start centered (not maximized) so the whole window is always
        # visible; the minimum size adapts to small work areas instead of
        # forcing the window past the taskbar.
        self.root.minsize(min(1100, _fit_w), min(700, _fit_h))

        # Fonts must exist before build_ui() because multiple tabs use them
        # during widget construction, including the Templates tab.
        default_font = tkfont.nametofont("TkDefaultFont")
        text_font = tkfont.nametofont("TkTextFont")
        fixed_font = tkfont.nametofont("TkFixedFont")

        self.basefont = default_font.copy()
        self.basefont.configure(size=10)

        self.smallfont = default_font.copy()
        self.smallfont.configure(size=9)

        self.tinyfont = default_font.copy()
        self.tinyfont.configure(size=8)

        self.boldfont = default_font.copy()
        self.boldfont.configure(size=10, weight="bold")

        self.uiheadingfont = default_font.copy()
        self.uiheadingfont.configure(size=11, weight="bold")

        self.small_font = self.smallfont  # alias for gallery_tab compatibility

        self.titlefont = default_font.copy()
        self.titlefont.configure(size=14, weight="bold")

        self.monospacefont = fixed_font.copy()
        self.monospacefont.configure(size=9)

        self.textfont = text_font.copy()
        self.textfont.configure(size=10)

        self.themes = []
        self.prompts = []
        self.current_prompt_data = None  # Single active preview prompt
        self.favorites = []
        self.presets = []
        self.last_image_path = None
        self.last_image_tk = None
        self.preview_source_label = None
        self.is_generating = False
        self.slideshow_interval_var = tk.StringVar(value='60')
        self.slideshow_source_var = tk.StringVar(value='All Images')
        self.slideshow_order_var = tk.StringVar(value='random')
        self.slideshow_enabled_var = tk.BooleanVar(value=False)
        self.slideshow_skip_duplicates_var = tk.BooleanVar(value=True)
        self.slideshow_pause_on_fullscreen_var = tk.BooleanVar(value=False)
        self._fullscreen_was_detected = False
        self._fullscreen_check_job = None
        self.gallery_images = []
        self.gallery_paths = []
        self.selected_gallery_path = None  # Primary selection for preview/wallpaper
        self.selected_gallery_paths = set()  # Multi-selection for batch operations
        self.favorite_thumb_refs = []
        self.prompt_source = "theme_builder"  # Track whether prompt came from theme_builder or recipe
        self.prompt_builder_quick_refs = None
        self.favorite_selected_item = None

        # Style transfer (OpenCV) is loaded on first use — avoids slow startup import.
        self.style_transfer = None
        self.style_transfer_available = False
        self._style_transfer_lazy_failed = False

        # Performance Fixes: Threading & Cancellation
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)
        self.cancel_event = threading.Event()
        self.thumb_cache = {}  # Cache for PhotoImage objects
        self.gen_future = None

        self.current_theme_name = "darkforest"
        self._tray_icon = None
        self._tray_thread = None
        self.gallery_cards = {}
        self.favorite_cards = {}
        self.remember_settings_var = tk.BooleanVar(value=False)
        self.custom_width_var = tk.StringVar(value="1024")
        self.custom_height_var = tk.StringVar(value="576")
        config = load_config()
        self.auto_generate_on_startup_var = tk.BooleanVar(
            value=config.get("auto_generate_on_startup", False))
        self.startup_subject_var = tk.StringVar(
            value=config.get("startup_subject", "frog"))

        # Initialize status variables early for slideshow
        self.statusvar = tk.StringVar(value="Starting up...")
        self.status_var = self.statusvar

        # Slideshow tracking
        self.slideshow = SlideshowManager(self.root, self.status_var)

        # Tutorial manager
        self.tutorial_manager = TutorialManager(self)

        # Gallery State (Initialize before build_ui)
        self.gallery_sort_mode = "date"  # "date" or "name"
        self.gallery_sort_desc = True
        self.gallery_organize_mode = tk.BooleanVar(value=False)
        self._gallery_custom_order = None  # List[Path] — persists manual order across reloads
        self._fav_custom_order = None       # List[str] image-paths — persists favorites manual order
        self._fav_drag_source = None        # int card-position index being dragged
        self._fav_display_items = []        # the exact list last rendered by _populate_visual_grid
        self._gallery_resize_job = None       # pending after() id for debounced resize handler
        self._gallery_layout_job = None      # pending after_idle id for deferred column layout
        self._gallery_scroll_job = None      # pending after() id for debounced scroll render
        self._gallery_cols = 3               # current column count, updated by layout passes
        self._gallery_placeholders = {}      # idx -> placeholder Frame for off-screen slots
        self.is_fullscreen = False

        # Themed dialog helper (replaces messagebox)
        self._dialog = ThemedDialog(self)

        # Toast notification system
        self._toast_frame = None
        self._toast_queue = []
        self._toast_timer = None

        # Minimize to tray setting
        self.minimize_to_tray_enabled = load_config().get("minimize_to_tray", True)

        # Run on startup setting (read actual registry state as source of truth)
        self.run_on_startup_enabled = self._get_startup_registry()

        _t0 = time.perf_counter()

        # Expose module-level constants as instance attributes for extracted modules
        self.THEMES = THEMES
        self.UI = UI
        self.THEME_DISPLAY_NAMES = THEME_DISPLAY_NAMES
        self.THEME_INTERNAL_NAMES = THEME_INTERNAL_NAMES
        self.COLOR_FAMILIES = COLOR_FAMILIES
        self.COLOR_VARIATIONS = COLOR_VARIATIONS
        self.THEME_VARIABLE_OPTIONS = THEME_VARIABLE_OPTIONS
        self.STYLE_MODES = STYLE_MODES
        self.MODEL_OPTIONS = MODEL_OPTIONS
        self.MODEL_ID_TO_DISPLAY = MODEL_ID_TO_DISPLAY
        self.MODEL_DISPLAY_TO_ID = MODEL_DISPLAY_TO_ID
        self.PROVIDER_OPTIONS = PROVIDER_OPTIONS
        self.PROVIDER_MODELS = PROVIDER_MODELS
        self.DIMENSION_PRESETS = DIMENSION_PRESETS
        self.SLIDESHOW_LABEL_TO_VALUE = SLIDESHOW_LABEL_TO_VALUE
        self.SLIDESHOW_SOURCE_DISPLAY = SLIDESHOW_SOURCE_DISPLAY
        self.SLIDESHOW_SOURCE_LABELS = SLIDESHOW_SOURCE_LABELS
        self.DEFAULT_NEGATIVE_PROMPT = DEFAULT_NEGATIVE_PROMPT
        self.DEFAULT_PROMPT_MODE_LABEL = DEFAULT_PROMPT_MODE_LABEL
        self.DEFAULT_PROMPT_MODE_VALUE = DEFAULT_PROMPT_MODE_VALUE
        self.PROMPT_MODE_LABELS = PROMPT_MODE_LABELS
        self.IMAGE_EXTS = IMAGE_EXTS
        self._GALLERY_CARD_H = _GALLERY_CARD_H
        self.BASE_DIR = BASE_DIR
        self.LOGS_DIR = LOGS_DIR
        self.PROMPTS_LOG = PROMPTS_LOG
        self.FAVORITES_LOG = FAVORITES_LOG
        self.FAVORITES_DIR = FAVORITES_DIR
        self.STYLED_DIR = STYLED_DIR
        self.MANUAL_DIR = MANUAL_DIR
        self.PRESETS_FILE = PRESETS_FILE
        self.SESSIONS_FILE = SESSIONS_FILE
        self.WINDOWS = WINDOWS
        self.PYSTRAY_AVAILABLE = PYSTRAY_AVAILABLE
        self.SV_TTK_AVAILABLE = SV_TTK_AVAILABLE
        self.KEYBOARD_AVAILABLE = KEYBOARD_AVAILABLE

        # Initialize extracted module managers
        self._session_mgr = SessionManager(self)
        self._settings_tab = SettingsTab(self)
        self._prompt_tab = PromptTab(self)
        self._gallery_tab = GalleryTab(self)
        self._tray_mgr = TrayManager(self)
        self._tutorial_mgr = TutorialManager(self)

        # Initialize pinned dropdowns system (v1.3.2 → v1.5.0+)
        if PINNED_DROPDOWNS_AVAILABLE:
            try:
                import utils as _pin_utils
                init_pinned_manager(_pin_utils.load_config, _pin_utils.save_config)
                self._pinned_dropdowns_enabled = True
                logger.info("Pinned dropdowns system initialized")
            except Exception as _pin_err:
                logger.warning("Pinned dropdowns not available: %s", _pin_err)
                self._pinned_dropdowns_enabled = False

        # Set window / taskbar icon using the shared icon loader
        # (must come AFTER _tray_mgr is created)
        try:
            from PIL import ImageTk
            self.icon_img = ImageTk.PhotoImage(self._get_app_icon_image())
            self.root.iconphoto(True, self.icon_img)
        except Exception:
            pass

        self.build_ui()
        logger.info(f"build_ui: {time.perf_counter()-_t0:.2f}s")

        _t1 = time.perf_counter()
        self.load_favorites()
        logger.info(f"load_favorites: {time.perf_counter()-_t1:.2f}s")

        _t2 = time.perf_counter()
        self.load_presets()
        self.load_slideshow_settings()
        # Load remembered settings after UI is built
        self.load_remembered_settings()
        logger.info(f"config/presets/settings: {time.perf_counter()-_t2:.2f}s")

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.bind("<Unmap>", self._on_minimize)
        self.root.bind("<F11>", self.toggle_fullscreen)

        # Keyboard shortcuts for common actions
        self.root.bind("<Control-g>", lambda e: self._switch_to_tab("gallery"))
        self.root.bind("<Control-s>", lambda e: self._open_settings_window())
        # Ctrl+P removed — Prompt Builder tab no longer accessible via shortcut
        self.root.bind("<Control-n>", lambda e: self.generate_image())
        self.root.bind("<Escape>", lambda e: self._handle_escape())

        # Global Hotkey (Ctrl+Alt+N for next wallpaper)
        if KEYBOARD_AVAILABLE:
            try:
                keyboard.add_hotkey('ctrl+alt+n', self.advance_slideshow)
            except Exception:
                pass

        _t3 = time.perf_counter()
        self.apply_theme(load_config().get("app_theme", "darkforest"))
        logger.info(f"apply_theme: {time.perf_counter()-_t3:.2f}s")
        
        # Check if first-run tutorial should be shown
        if self._tutorial_mgr.should_show_first_run_tutorial():
            self.root.after(1000, self._show_first_run_prompt)
        
        logger.info(f"total sync init: {time.perf_counter()-_t0:.2f}s")

        self.status_var.set("Loading gallery and warming up prompt engine…")
        self.root.after(1, self._deferred_startup_load)

        # Start tray icon on initialization so it's available when window closes
        if PYSTRAY_AVAILABLE:
            self._start_tray()

        # Show window normally on startup
        self.root.deiconify()
        self.root.state("normal")



    def _ensure_style_transfer(self):

        """Load OpenCV/style_transfer only when needed (first Apply Style open)."""

        if self.style_transfer is not None:

            return True

        if self._style_transfer_lazy_failed:

            return False

        try:

            from style_transfer import get_style_transfer



            self.style_transfer = get_style_transfer()

            self.style_transfer_available = True

            return True

        except Exception:

            self._style_transfer_lazy_failed = True

            self.style_transfer_available = False

            self.style_transfer = None

            return False





    def _deferred_startup_load(self):
        """Run all heavy disk I/O on a background thread; deliver results to main thread."""

        def _bg_work():
            _t = time.perf_counter()
            # 0. Warm up keyword expander and theme generation in background
            try:
                warmup_keyword_expander()
                logger.info(f"keyword warmup completed: {time.perf_counter()-_t:.2f}s")
            except Exception as e:
                logger.warning(f"keyword warmup failed: {e}")

            # 1. migrate saved image paths (rglob scan — was blocking main thread)
            try:
                updated_h, updated_f = self.migrate_saved_image_paths()
            except Exception:
                updated_h = updated_f = 0
            logger.info(f"migrate_saved_image_paths: {time.perf_counter()-_t:.2f}s")

            # 2. collect + sort gallery file list (rglob over 4 folders)
            _t2 = time.perf_counter()
            try:
                raw_images = collect_wallpapers() or []
                current_sort = getattr(self, '_startup_sort', 'Date Newest')
                if current_sort in ("Date Newest", "Date Oldest"):
                    images_with_stats = [(img, img.stat().st_mtime) for img in raw_images]
                    images_with_stats.sort(key=lambda x: x[1], reverse=(current_sort == "Date Newest"))
                    raw_images = [x[0] for x in images_with_stats]
                elif current_sort == "Name A-Z":
                    raw_images.sort(key=lambda x: x.name.lower())
                elif current_sort == "Name Z-A":
                    raw_images.sort(key=lambda x: x.name.lower(), reverse=True)
                elif current_sort == "Size Largest":
                    try:
                        images_with_size = [(img, os.path.getsize(img)) for img in raw_images]
                        images_with_size.sort(key=lambda x: x[1], reverse=True)
                        raw_images = [x[0] for x in images_with_size]
                    except OSError:
                        raw_images.sort(key=lambda x: x.name.lower())
            except Exception:
                raw_images = []
            logger.info(f"collect+sort wallpapers ({len(raw_images)} files): {time.perf_counter()-_t2:.2f}s")

            # Deliver results back on the main thread
            schedule_ui_update(_main_thread_finish, raw_images, updated_f)

        def _main_thread_finish(raw_images, updated_f):
            _t = time.perf_counter()
            if updated_f:
                self.load_favorites()
            # Apply custom order if set
            if self._gallery_custom_order is not None:
                order_strs = [str(p) for p in self._gallery_custom_order]
                ordered = {str(p): p for p in raw_images}
                raw_images2 = [ordered[s] for s in order_strs if s in ordered]
                raw_images2 += [p for p in ordered.values() if str(p) not in order_strs]
                raw_images[:] = raw_images2
            self.gallery_images = raw_images
            self.slideshow.load_gallery(self.gallery_images)
            # Trigger the UI-only part of load_gallery (clear old cards + build placeholders)
            self.load_gallery()
            logger.info(f"gallery UI populate: {time.perf_counter()-_t:.2f}s")
            # Start theme generation warmup to ensure fast prompt generation
            self.status_var.set("Warming up prompt engine...")
            self._warmup_theme_generation()

        # Cache the current sort choice before leaving the main thread
        self._startup_sort = getattr(self, 'sort_combo_var', None)
        self._startup_sort = self._startup_sort.get() if self._startup_sort else 'Date Newest'

        run_background(_bg_work)

    def _warmup_theme_generation(self):
        """Pre-warm theme generation on background thread (cold-start perf fix)."""
        def warmup_thread():
            try:
                warmup_start = time.perf_counter()
                # Warm up keyword expander (NLTK data loading)
                from keyword_expander import warmup_keyword_expander
                warmup_keyword_expander()
                
                # Warm up theme generation by generating a sample theme
                keywords = ["frog"]
                start = time.perf_counter()
                themes = generate_themes(count=1, user_keywords=keywords)
                elapsed = time.perf_counter() - start
                warmup_total = time.perf_counter() - warmup_start
                logger.debug(f"Theme generation warmup complete: {warmup_total:.2f}s (theme gen: {elapsed:.2f}s)")
                
                # Warm up prompt builder by building a sample prompt
                if themes:
                    from prompt_builder import build_prompt
                    prompt_start = time.perf_counter()
                    build_prompt(themes[0], style_mode="stylized")
                    prompt_elapsed = time.perf_counter() - prompt_start
                    logger.debug(f"Prompt builder warmup complete: {prompt_elapsed:.2f}s")
                
                schedule_ui_update(self.status_var.set, "Ready — prompt engine warm.")
            except Exception as e:
                logger.debug(f"Warmup error: {e}")
                schedule_ui_update(self.status_var.set, "Ready.")
        run_background(warmup_thread)






    def activate_generator_tab(self, event=None):
        """Select the Prompt Builder tab (Generator merged into it)."""
        try:
            self.notebook.select(self.prompt_builder_tab)
        except Exception:
            pass

    def activate_prompt_builder_tab(self, event=None):

        try:

            self.notebook.select(self.prompt_builder_tab)

        except Exception:

            pass



    def build_ui(self):

        style = ttk.Style(self.root)

        if SV_TTK_AVAILABLE:
            try:
                sv_ttk.set_theme("dark")
            except Exception:
                pass
        else:
            try:
                style.theme_use("clam")
            except Exception:
                pass

        self.base_font = tkfont.nametofont("TkDefaultFont")
        self.base_font.configure(family="Segoe UI", size=9)
        self.bold_font = tkfont.Font(family="Segoe UI", size=9, weight="bold")
        self.small_font = tkfont.Font(family="Segoe UI", size=8)
        self.title_font = tkfont.Font(family="Segoe UI", size=18, weight="bold")
        self.sidebar_title_font = tkfont.Font(family="Segoe UI", size=14, weight="bold")
        self.mono_font = tkfont.Font(family="Consolas", size=9)
        self.emoji_font = tkfont.Font(family="Segoe UI Emoji", size=11)

        self.main = ttk.Frame(self.root, padding=0)
        self.main.pack(fill="both", expand=True)
        # Store reference for gradient effects
        self._main_frame = self.main

        # ── Three-column layout with subtle spacing ────────────────────────
        self.main.columnconfigure(0, weight=0, minsize=300)  # left sidebar
        self.main.columnconfigure(1, weight=3)                # center preview
        self.main.columnconfigure(2, weight=2, minsize=280)  # right gallery
        self.main.rowconfigure(0, weight=1)
        self.main.configure(padding=4)

        # ═══════════════════════ LEFT SIDEBAR ═══════════════════════════════
        sidebar_outer = tk.Frame(self.main, bd=0, highlightthickness=0)
        sidebar_outer.grid(row=0, column=0, sticky="nsew", padx=(0, 4), pady=(4, 4))
        sidebar_outer.rowconfigure(0, weight=1)
        sidebar_outer.columnconfigure(0, weight=1)
        self._sidebar_outer = sidebar_outer

        sidebar_canvas = tk.Canvas(sidebar_outer, highlightthickness=0, width=300)
        sidebar_scroll = ttk.Scrollbar(sidebar_outer, orient="vertical", command=sidebar_canvas.yview)
        sidebar_canvas.configure(yscrollcommand=sidebar_scroll.set)
        sidebar_canvas.grid(row=0, column=0, sticky="nsew")
        sidebar_scroll.grid(row=0, column=1, sticky="ns")
        self._sidebar_canvas = sidebar_canvas

        left = tk.Frame(sidebar_canvas, padx=14, pady=14)
        _sb_win = sidebar_canvas.create_window((0, 0), window=left, anchor="nw")
        left.bind("<Configure>", lambda e: sidebar_canvas.configure(scrollregion=sidebar_canvas.bbox("all")))
        sidebar_canvas.bind("<Configure>", lambda e: sidebar_canvas.itemconfigure(_sb_win, width=e.width))
        left.columnconfigure(0, weight=1)
        self._sidebar = left

        # Sidebar mousewheel scrolling
        def _sidebar_wheel(event):
            sidebar_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            return "break"
        sidebar_canvas.bind("<MouseWheel>", _sidebar_wheel)
        left.bind("<MouseWheel>", _sidebar_wheel)
        self._sidebar_wheel = _sidebar_wheel  # store for binding children later

        def _bind_sidebar_wheel_recursive(widget):
            """Bind mousewheel to all children of the sidebar so scrolling works everywhere."""
            try:
                widget.bind("<MouseWheel>", _sidebar_wheel)
                for child in widget.winfo_children():
                    _bind_sidebar_wheel_recursive(child)
            except Exception:
                pass
        self._bind_sidebar_wheel_recursive = _bind_sidebar_wheel_recursive

        # ── Sidebar logo ──
        self._sidebar_logo_ref = None  # prevent GC
        try:
            from PIL import Image as _PILImg, ImageTk as _PILTk
            from utils import get_bundle_dir
            _logo_path = get_bundle_dir() / 'sidebar_logo.png'
            if _logo_path.exists():
                _logo_img = _PILImg.open(_logo_path).convert('RGBA')
                _sidebar_w = 260
                _ratio = _sidebar_w / _logo_img.width
                _logo_h = int(_logo_img.height * _ratio)
                _logo_img = _logo_img.resize((_sidebar_w, _logo_h), _PILImg.LANCZOS)
                self._sidebar_logo_ref = _PILTk.PhotoImage(_logo_img)
                _logo_label = tk.Label(left, image=self._sidebar_logo_ref,
                                       anchor='center')
                _logo_label.pack(pady=(0, 8))
                self._sidebar_logo_label = _logo_label
        except Exception:
            self._sidebar_logo_label = None

        # ── Primary actions: Generate Prompt + Generate Image ──
        gen_row = ttk.Frame(left)
        gen_row.pack(fill="x", pady=(0, 4))
        gen_row.columnconfigure(0, weight=1)
        gen_row.columnconfigure(1, weight=1)

        # Use RoundedButton with gradient if ui_effects is available
        if UI_EFFECTS_AVAILABLE:
            accent_preview = THEMES.get(
                load_config().get("app_theme", "darkforest"),
                THEMES["darkforest"]
            ).get("accent", "#4a9eff")

            self._rounded_prompt_btn = RoundedButton(
                gen_row, text="Generate Prompt", width=140, height=38,
                fill_color=accent_preview, text_color=COLOR_WHITE,
                radius=10, font=("Segoe UI", 10, "bold"),
                command=self.generate_prompt_only, use_gradient=True,
            )
            self._rounded_prompt_btn.grid(row=0, column=0, sticky="ew", padx=(0, 3), pady=(0, 0))
            # Keep a reference to an invisible tk.Button for compatibility
            gen_prompt_btn = tk.Button(gen_row, text="", width=0, height=0, bd=0)
            gen_prompt_btn.configure(font=tkfont.Font(family="Segoe UI", size=10, weight="bold"))
            gen_prompt_btn.grid_forget()

            self._rounded_gen_btn = RoundedButton(
                gen_row, text="Generate Image", width=140, height=38,
                fill_color=accent_preview, text_color=COLOR_WHITE,
                radius=10, font=("Segoe UI", 10, "bold"),
                command=self.generate, use_gradient=True,
            )
            self._rounded_gen_btn.grid(row=0, column=1, sticky="ew", padx=(3, 0), pady=(0, 0))
            gen_img_btn = tk.Button(gen_row, text="", width=0, height=0, bd=0)
            gen_img_btn.configure(font=tkfont.Font(family="Segoe UI", size=10, weight="bold"))
            gen_img_btn.grid_forget()
        else:
            gen_prompt_btn = tk.Button(gen_row, text="Generate Prompt", cursor="hand2",
                                       relief="flat", bd=0, padx=10, pady=8,
                                       command=self.generate_prompt_only)
            gen_prompt_btn.configure(font=tkfont.Font(family="Segoe UI", size=10, weight="bold"))
            gen_prompt_btn.grid(row=0, column=0, sticky="ew", padx=(0, 3), ipady=3)
            self._rounded_prompt_btn = None

            gen_img_btn = tk.Button(gen_row, text="Generate Image", cursor="hand2",
                                    relief="flat", bd=0, padx=10, pady=8,
                                    command=self.generate)
            gen_img_btn.configure(font=tkfont.Font(family="Segoe UI", size=10, weight="bold"))
            gen_img_btn.grid(row=0, column=1, sticky="ew", padx=(3, 0), ipady=3)
            self._rounded_gen_btn = None

        self._generate_prompt_btn = gen_prompt_btn
        self._generate_btn = gen_img_btn

        # ── Utility bar: Random · Cancel / Settings ──
        util_bar = ttk.Frame(left)
        util_bar.pack(fill="x", pady=(4, 6))
        util_bar.columnconfigure(0, weight=1)
        util_bar.columnconfigure(1, weight=1)
        self._btn_random = ttk.Button(util_bar, text=" Random",
                   command=self.random_theme)
        self._btn_random.grid(row=0, column=0, sticky="ew", padx=(0, 3))
        self._btn_cancel = ttk.Button(util_bar, text=" Cancel",
                   command=self.cancel_generation)
        self._btn_cancel.grid(row=0, column=1, sticky="ew")
        self._btn_settings = ttk.Button(util_bar, text=" Settings",
                   command=self._open_settings_window)
        self._btn_settings.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(3, 0))

        ttk.Separator(left, orient="horizontal").pack(fill="x", pady=(2, 10))

        # Mood (placed above Subject so mood directly modifies subject in the prompt)
        mood_lbl = tk.Label(left, text="Mood", anchor="w")
        mood_lbl.configure(font=self.bold_font)
        mood_lbl.pack(fill="x", pady=(0, 2))
        self._sidebar_mood_lbl = mood_lbl
        mood_options = THEME_VARIABLE_OPTIONS.get("mood", [""])
        self.mood_var = tk.StringVar(value="")
        
        # Use PinnedCombobox if available (has stars inside!)
        if PINNED_DROPDOWNS_AVAILABLE and getattr(self, '_pinned_dropdowns_enabled', False):
            try:
                self.mood_entry = PinnedCombobox(left, category="mood", values=mood_options,
                                                  textvariable=self.mood_var, state="readonly")
                self.mood_entry.pack(fill="x", pady=(0, 10))
                self.mood_entry.bind("<MouseWheel>", lambda e: "break")
            except Exception as _mood_err:
                logger.debug("Pinned mood fallback: %s", _mood_err)
                self.mood_entry = ttk.Combobox(left, textvariable=self.mood_var,
                                               values=mood_options, state="readonly")
                self.mood_entry.pack(fill="x", pady=(0, 10))
                self.mood_entry.bind("<MouseWheel>", lambda e: "break")
        else:
            self.mood_entry = ttk.Combobox(left, textvariable=self.mood_var,
                                           values=mood_options, state="readonly")
            self.mood_entry.pack(fill="x", pady=(0, 10))
            self.mood_entry.bind("<MouseWheel>", lambda e: "break")

        # Subject
        subj_lbl = tk.Label(left, text="Subject", anchor="w")
        subj_lbl.configure(font=self.bold_font)
        subj_lbl.pack(fill="x", pady=(0, 2))
        self._sidebar_subj_lbl = subj_lbl
        # Subject - Use PinnedCombobox if available
        if PINNED_DROPDOWNS_AVAILABLE and getattr(self, '_pinned_dropdowns_enabled', False):
            try:
                self.subject_entry = PinnedCombobox(left, category="subject", 
                                                     values=THEME_VARIABLE_OPTIONS["subject"])
                self.subject_entry.pack(fill="x", pady=(0, 10))
                self.subject_entry.insert(0, "frog")
                self.subject_entry.bind("<MouseWheel>", lambda e: "break")
            except Exception as _subj_err:
                logger.debug("Pinned subject fallback: %s", _subj_err)
                self.subject_entry = ttk.Combobox(left, values=THEME_VARIABLE_OPTIONS["subject"])
                self.subject_entry.pack(fill="x", pady=(0, 10))
                self.subject_entry.insert(0, "frog")
                self.subject_entry.bind("<MouseWheel>", lambda e: "break")
        else:
            self.subject_entry = ttk.Combobox(left, values=THEME_VARIABLE_OPTIONS["subject"])
            self.subject_entry.pack(fill="x", pady=(0, 10))
            self.subject_entry.insert(0, "frog")
            self.subject_entry.bind("<MouseWheel>", lambda e: "break")

        # Mode dropdown
        mode_lbl = tk.Label(left, text="Mode", anchor="w")
        mode_lbl.configure(font=self.bold_font)
        mode_lbl.pack(fill="x", pady=(0, 2))
        self._sidebar_mode_lbl = mode_lbl

        self.mode_var = tk.StringVar(value=DEFAULT_PROMPT_MODE_LABEL)
        mode_combo = ttk.Combobox(left, textvariable=self.mode_var,
                                  values=PROMPT_MODE_LABELS, state="readonly")
        mode_combo.pack(fill="x", pady=(0, 10))
        mode_combo.bind("<<ComboboxSelected>>", lambda e: self.update_mode_badge())
        mode_combo.bind("<MouseWheel>", lambda e: "break")
        self.mode_combo = mode_combo

        # Lighting dropdown
        lighting_lbl = tk.Label(left, text="Lighting", anchor="w")
        lighting_lbl.configure(font=self.bold_font)
        lighting_lbl.pack(fill="x", pady=(0, 2))
        self._sidebar_lighting_lbl = lighting_lbl

        # Lighting - Use PinnedCombobox if available
        if PINNED_DROPDOWNS_AVAILABLE and getattr(self, '_pinned_dropdowns_enabled', False):
            try:
                self.lighting_entry = PinnedCombobox(left, category="lighting",
                                                      values=THEME_VARIABLE_OPTIONS["lighting"])
                self.lighting_entry.pack(fill="x", pady=(0, 10))
                self.lighting_entry.insert(0, "neon")
                self.lighting_entry.bind("<MouseWheel>", lambda e: "break")
            except Exception as _lit_err:
                logger.debug("Pinned lighting fallback: %s", _lit_err)
                self.lighting_entry = ttk.Combobox(left, values=THEME_VARIABLE_OPTIONS["lighting"])
                self.lighting_entry.pack(fill="x", pady=(0, 10))
                self.lighting_entry.insert(0, "neon")
                self.lighting_entry.bind("<MouseWheel>", lambda e: "break")
        else:
            self.lighting_entry = ttk.Combobox(left, values=THEME_VARIABLE_OPTIONS["lighting"])
            self.lighting_entry.pack(fill="x", pady=(0, 10))
            self.lighting_entry.insert(0, "neon")
            self.lighting_entry.bind("<MouseWheel>", lambda e: "break")

        # Color palette row
        color_lbl = tk.Label(left, text="Color Palette", anchor="w")
        color_lbl.configure(font=self.bold_font)
        color_lbl.pack(fill="x", pady=(0, 4))
        self._sidebar_color_lbl = color_lbl

        # Color palette row
        color_frame = ttk.Frame(left)
        color_frame.pack(fill="x", pady=(0, 14))
        
        # Use random defaults for color to avoid empty on startup
        color_families = [f for f in COLOR_FAMILIES if f]
        color_variations = COLOR_VARIATIONS
        default_family = random.choice(color_families) if color_families else ""
        default_variation = random.choice(color_variations) if color_variations else ""
        self.color_family_var = tk.StringVar(value=default_family)
        
        # Color Family - Use PinnedCombobox if available
        if PINNED_DROPDOWNS_AVAILABLE and getattr(self, '_pinned_dropdowns_enabled', False):
            try:
                self.color_family_combo = PinnedCombobox(color_frame, category="color_family",
                                                          values=COLOR_FAMILIES, state="readonly",
                                                          textvariable=self.color_family_var, width=14)
                self.color_family_combo.pack(side="left", padx=(0, 6))
                self.color_family_combo.bind("<MouseWheel>", lambda e: "break")
            except Exception as _cf_err:
                logger.debug("Pinned color family fallback: %s", _cf_err)
                self.color_family_combo = ttk.Combobox(color_frame, textvariable=self.color_family_var,
                                                       values=COLOR_FAMILIES, state="readonly", width=14)
                self.color_family_combo.pack(side="left", padx=(0, 6))
                self.color_family_combo.bind("<MouseWheel>", lambda e: "break")
        else:
            self.color_family_combo = ttk.Combobox(color_frame, textvariable=self.color_family_var,
                                                   values=COLOR_FAMILIES, state="readonly", width=14)
            self.color_family_combo.pack(side="left", padx=(0, 6))
            self.color_family_combo.bind("<MouseWheel>", lambda e: "break")
        
        self.color_variation_var = tk.StringVar(value=default_variation)
        
        # Color Variation - Use PinnedCombobox if available  
        if PINNED_DROPDOWNS_AVAILABLE and getattr(self, '_pinned_dropdowns_enabled', False):
            try:
                self.color_variation_combo = PinnedCombobox(color_frame, category="color_variation",
                                                             values=COLOR_VARIATIONS, state="readonly",
                                                             textvariable=self.color_variation_var, width=14)
                self.color_variation_combo.pack(side="left")
                self.color_variation_combo.bind("<MouseWheel>", lambda e: "break")
            except Exception as _cv_err:
                logger.debug("Pinned color variation fallback: %s", _cv_err)
                self.color_variation_combo = ttk.Combobox(color_frame, textvariable=self.color_variation_var,
                                                          values=COLOR_VARIATIONS, state="readonly", width=14)
                self.color_variation_combo.pack(side="left")
                self.color_variation_combo.bind("<MouseWheel>", lambda e: "break")
        else:
            self.color_variation_combo = ttk.Combobox(color_frame, textvariable=self.color_variation_var,
                                                      values=COLOR_VARIATIONS, state="readonly", width=14)
            self.color_variation_combo.pack(side="left")
            self.color_variation_combo.bind("<MouseWheel>", lambda e: "break")

        # Setting (location/environment)
        setting_lbl = tk.Label(left, text="Setting", anchor="w")
        setting_lbl.configure(font=self.bold_font)
        setting_lbl.pack(fill="x", pady=(0, 2))
        self._sidebar_setting_lbl = setting_lbl
        # Setting - Use PinnedCombobox if available
        if PINNED_DROPDOWNS_AVAILABLE and getattr(self, '_pinned_dropdowns_enabled', False):
            try:
                self.setting_entry = PinnedCombobox(left, category="setting",
                                                     values=THEME_VARIABLE_OPTIONS["setting"])
                self.setting_entry.pack(fill="x", pady=(0, 10))
                first_setting = [opt for opt in THEME_VARIABLE_OPTIONS["setting"] if opt]
                if first_setting:
                    self.setting_entry.insert(0, first_setting[0])
                self.setting_entry.bind("<MouseWheel>", lambda e: "break")
            except Exception as _set_err:
                logger.debug("Pinned setting fallback: %s", _set_err)
                self.setting_entry = ttk.Combobox(left, values=THEME_VARIABLE_OPTIONS["setting"])
                self.setting_entry.pack(fill="x", pady=(0, 10))
                first_setting = [opt for opt in THEME_VARIABLE_OPTIONS["setting"] if opt]
                if first_setting:
                    self.setting_entry.insert(0, first_setting[0])
                self.setting_entry.bind("<MouseWheel>", lambda e: "break")
        else:
            self.setting_entry = ttk.Combobox(left, values=THEME_VARIABLE_OPTIONS["setting"])
            self.setting_entry.pack(fill="x", pady=(0, 10))
            first_setting = [opt for opt in THEME_VARIABLE_OPTIONS["setting"] if opt]
            if first_setting:
                self.setting_entry.insert(0, first_setting[0])
            self.setting_entry.bind("<MouseWheel>", lambda e: "break")

        # Atmosphere
        atm_lbl = tk.Label(left, text="Atmosphere", anchor="w")
        atm_lbl.configure(font=self.bold_font)
        atm_lbl.pack(fill="x", pady=(0, 2))
        self._sidebar_atm_lbl = atm_lbl
        # Atmosphere - Use PinnedCombobox if available
        first_atmosphere = [opt for opt in THEME_VARIABLE_OPTIONS.get("atmosphere", []) if opt]
        # Use a random default instead of first alphabetically to avoid always showing "arcane haze"
        default_atm = random.choice(first_atmosphere) if first_atmosphere else ""
        self.atmosphere_var = tk.StringVar(value=default_atm)
        
        if PINNED_DROPDOWNS_AVAILABLE and getattr(self, '_pinned_dropdowns_enabled', False):
            try:
                self.atmosphere_combo = PinnedCombobox(left, category="atmosphere",
                                                       values=THEME_VARIABLE_OPTIONS.get("atmosphere", [""]),
                                                       state="readonly",
                                                       textvariable=self.atmosphere_var)
                self.atmosphere_combo.pack(fill="x", pady=(0, 10))
                self.atmosphere_combo.bind("<MouseWheel>", lambda e: "break")
            except Exception as _atm_err:
                logger.debug("Pinned atmosphere fallback: %s", _atm_err)
                self.atmosphere_combo = ttk.Combobox(left, textvariable=self.atmosphere_var,
                                                     values=THEME_VARIABLE_OPTIONS.get("atmosphere", [""]),
                                                     state="readonly")
                self.atmosphere_combo.pack(fill="x", pady=(0, 10))
                self.atmosphere_combo.bind("<MouseWheel>", lambda e: "break")
        else:
            self.atmosphere_combo = ttk.Combobox(left, textvariable=self.atmosphere_var,
                                                 values=THEME_VARIABLE_OPTIONS.get("atmosphere", [""]),
                                                 state="readonly")
            self.atmosphere_combo.pack(fill="x", pady=(0, 10))
            self.atmosphere_combo.bind("<MouseWheel>", lambda e: "break")

        # ── Negative Prompt Builder (unified) ──
        from negative_manager import load_negative_presets
        neg_builder_lbl = tk.Label(left, text="Negative Prompt", anchor="w")
        neg_builder_lbl.configure(font=self.bold_font)
        neg_builder_lbl.pack(fill="x", pady=(0, 4))
        self._sidebar_neg_preset_lbl = neg_builder_lbl
        self._sidebar_neg_lbl = neg_builder_lbl

        _presets_data = load_negative_presets().get("presets", {})
        # Store ordered list of (key, name, description, negatives_text, term_count)
        self._neg_preset_info = []
        self._neg_preset_vars = {}  # key -> BooleanVar
        for key, val in _presets_data.items():
            if key == "none":
                continue
            dname = val.get("name", key)
            desc = val.get("description", "")
            negs = val.get("negatives", "")
            term_count = len([t for t in negs.split(",") if t.strip()])
            self._neg_preset_info.append((key, dname, desc, negs, term_count))
            # Initialize with False, will be restored by load_remembered_settings
            self._neg_preset_vars[key] = tk.BooleanVar(value=False)
        # Keep _neg_preset_key_map for backward compat (display_name -> key)
        self._neg_preset_key_map = {info[1]: info[0] for info in self._neg_preset_info}

        # Preset checkbuttons — compact rows with term counts
        preset_frame = ttk.Frame(left)
        preset_frame.pack(fill="x", pady=(0, 4))
        self._neg_preset_frame = preset_frame
        for idx, (key, dname, desc, negs, term_count) in enumerate(self._neg_preset_info):
            row_frame = ttk.Frame(preset_frame)
            row_frame.pack(fill="x", pady=(0, 1))
            cb = ttk.Checkbutton(row_frame, text=dname, variable=self._neg_preset_vars[key],
                                  command=self._rebuild_neg_combined)
            cb.pack(side="left")
            count_lbl = tk.Label(row_frame, text=f"({term_count})", fg="gray", anchor="e")
            count_lbl.configure(font=self.small_font)
            count_lbl.pack(side="right", padx=(0, 2))

        # Preset description (updates on checkbox hover)
        self._neg_preset_desc_var = tk.StringVar(value="")
        self._neg_preset_desc_lbl = tk.Label(left, textvariable=self._neg_preset_desc_var,
                                              anchor="w", wraplength=240, fg="gray")
        self._neg_preset_desc_lbl.pack(fill="x", pady=(0, 2))
        # Bind hover on each checkbutton to show description
        for key, dname, desc, negs, term_count in self._neg_preset_info:
            for child in self._neg_preset_frame.winfo_children():
                for sub in child.winfo_children():
                    if isinstance(sub, ttk.Checkbutton) and sub.cget("text") == dname:
                        sub.bind("<Enter>", lambda e, d=desc: self._neg_preset_desc_var.set(d))
                        sub.bind("<Leave>", lambda e: self._neg_preset_desc_var.set(""))
                        break

        # ── Custom Negatives (user-curated, persistent) ──

        cn_header = ttk.Frame(left)
        cn_header.pack(fill="x", pady=(6, 0))
        cn_lbl = tk.Label(cn_header, text="Custom Negatives", anchor="w")
        cn_lbl.configure(font=self.small_font)
        cn_lbl.pack(side="left")
        self._sidebar_cn_lbl = cn_lbl
        cn_add_btn = ttk.Button(cn_header, text="+", width=3,
                                 command=self._add_custom_negative)
        cn_add_btn.pack(side="right")

        # Scrollable frame for custom negative checkboxes
        self._cn_frame = ttk.Frame(left)
        self._cn_frame.pack(fill="x", pady=(0, 2))
        self._cn_vars = {}  # term_str -> BooleanVar
        self._cn_widgets = []  # list of (row_frame, term_str) for rebuild
        self._rebuild_custom_neg_ui()

        # Custom terms — single-line entry with label
        custom_lbl = tk.Label(left, text="Custom terms (comma-separated):", anchor="w")
        custom_lbl.configure(font=self.small_font)
        custom_lbl.pack(fill="x", pady=(0, 1))
        self._neg_custom_var = tk.StringVar(value="")
        self._neg_custom_entry = ttk.Entry(left, textvariable=self._neg_custom_var)
        self._neg_custom_entry.pack(fill="x", pady=(0, 4))
        self._neg_custom_entry.bind("<KeyRelease>", lambda e: self._rebuild_neg_combined())

        # Preview — live-merged presets + custom (edits mark it as manual)
        preview_lbl = tk.Label(left, text="Preview", anchor="w")
        preview_lbl.configure(font=self.small_font)
        preview_lbl.pack(fill="x", pady=(0, 1))
        self._neg_final_frame = ttk.Frame(left)
        self._neg_final_frame.pack(fill="x", pady=(0, 1))
        _neg_scroll = tk.Scrollbar(self._neg_final_frame, orient="vertical", width=12)
        self._neg_final_text = tk.Text(self._neg_final_frame, height=8, wrap="word",
                                        font=self.mono_font, bd=1, relief="solid",
                                        yscrollcommand=_neg_scroll.set)
        self._neg_final_text.pack(side="left", fill="both", expand=True)
        _neg_scroll.config(command=self._neg_final_text.yview)
        _neg_scroll.pack(side="right", fill="y")
        self._neg_final_text.bind("<KeyRelease>", self._on_neg_final_edited)
        # Tab must escape this box (editable Text eats Tab by default)
        if UI_EFFECTS_AVAILABLE:
            make_text_tab_friendly(self._neg_final_text)

        # Small note about what this preview shows
        preview_note = tk.Label(left, anchor="w", wraplength=240, fg="gray",
                              text="Additional negatives may be added at generation time. "
                              "Edit the preview directly or use Reset to reapply custom terms.")
        preview_note.configure(font=self.small_font)
        preview_note.pack(fill="x", pady=(0, 1))

        # Term count + reset row
        self._neg_term_count_var = tk.StringVar(value="0 terms")
        count_row = ttk.Frame(left)
        count_row.pack(fill="x", pady=(0, 6))
        tk.Label(count_row, textvariable=self._neg_term_count_var, anchor="w",
                 fg="gray").pack(side="left")
        self._neg_reset_btn = ttk.Button(count_row, text="Reset", width=6,
                                          command=self._reset_neg_combined)
        self._neg_reset_btn.pack(side="right")

        # negative_prompt_var still exists for backward compat — reflects the final combined text
        self.negative_prompt_var = tk.StringVar(value=DEFAULT_NEGATIVE_PROMPT)
        # negative_prompt_entry kept as alias for _neg_final_text (for _set_active_entry compat)
        self.negative_prompt_entry = _TextVarBridge(self._neg_final_text, self.negative_prompt_var)

        # Track whether user has manually edited the final text
        self._neg_manual_edit = False
        # Backward compat: keep _neg_preset_listbox interface (returns selected keys)
        self._neg_preset_listbox = _FakePresetListbox(self._neg_preset_vars, self._neg_preset_info)

        # Seed the initial combined prompt
        self._rebuild_neg_combined()

        # ── Secondary toggles (stored here; UI lives in Settings > Advanced) ──
        self.smart_neg_var = tk.BooleanVar(value=True)
        self.subject_lock_var = tk.BooleanVar(value=True)

        # Bind mousewheel to all sidebar children
        self._bind_sidebar_wheel_recursive(left)

        # ═══════════════════════ CENTER PANEL ═══════════════════════════════
        center = ttk.Frame(self.main, padding=(8, 8), style="Card.TFrame")
        center.grid(row=0, column=1, sticky="nsew", padx=4, pady=(4, 4))
        center.rowconfigure(1, weight=1)
        center.columnconfigure(0, weight=1)
        self._center_panel = center

        # Quick actions on center tab bar
        center_tabs = ttk.Frame(center)
        center_tabs.grid(row=0, column=0, sticky="ew", pady=(0, 6))

        # Image preview area
        preview_card = ttk.Frame(center, style="Card.TFrame")
        preview_card.grid(row=1, column=0, sticky="nsew", padx=2, pady=2)
        preview_card.rowconfigure(0, weight=1)
        preview_card.columnconfigure(0, weight=1)

        self.preview_source_label = ttk.Label(preview_card, text="")
        self.image_label = tk.Label(preview_card, text="Selected or generated image\nwill appear here",
                                    anchor="center", justify="center", width=80, height=30)
        self.image_label.grid(row=0, column=0, sticky="nsew")
        self.image_label.bind("<Double-Button-1>", self.previewdoubleclick)
        self.image_label.bind("<Configure>", self._on_preview_resize)
        self.last_preview_path = None

        details = ttk.Frame(preview_card, style="Inner.TFrame")
        details.grid(row=1, column=0, sticky="ew", pady=(6, 0))
        self.preview_details_frame = details
        self.preview_name_label = ttk.Label(details, text="", wraplength=600)
        self.preview_name_label.configure(font=self.bold_font)
        self.preview_name_label.pack(anchor="w")
        self.preview_dims_label = ttk.Label(details, text="")
        self.preview_dims_label.pack(anchor="w")
        self.preview_size_label = ttk.Label(details, text="")
        self.preview_size_label.pack(anchor="w")

        # Slideshow countdown progress bar (above prompt preview)
        progress_frame = ttk.Frame(center, height=24)
        progress_frame.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        progress_frame.grid_propagate(False)
        progress_frame.columnconfigure(0, weight=1)
        progress_frame.rowconfigure(0, weight=1)
        self.progress = ttk.Progressbar(progress_frame, mode="determinate", maximum=100)
        self.progress.grid(row=0, column=0, sticky="nsew")
        self.progress_overlay_label = tk.Label(progress_frame, text="", font=self.bold_font, anchor="center")
        self.progress_overlay_label.place(relx=0.5, rely=0.5, anchor="center")
        # Progress bar is always visible, shows countdown when slideshow is running

        # Image generation status label (below slideshow progress bar)
        # Simple visual indicator when image is being generated
        self.image_generation_status_label = ttk.Label(center, text="", font=self.bold_font, anchor="center", foreground="#00ff00")
        self.image_generation_status_label.grid(row=3, column=0, sticky="ew", pady=(4, 0))

        # Generation progress bar overlay (over image preview)
        self.generation_progress = ttk.Progressbar(preview_card, mode="indeterminate", maximum=100)
        self.generation_progress.place(relx=0.5, rely=0.5, anchor="center", relwidth=0.5, relheight=0.1)
        self.generation_progress.place_forget()  # Hide initially

        # Prompt preview (below progress bars) — styled as a card
        preview_frame = ttk.LabelFrame(center, text=" Prompt Preview ", padding=(8, 4))
        preview_frame.grid(row=4, column=0, sticky="ew", pady=(6, 0), padx=2)
        preview_frame.columnconfigure(0, weight=1)

        badge_frame = ttk.Frame(preview_frame)
        badge_frame.grid(row=0, column=0, sticky="ew", pady=(0, 2))
        badge_frame.columnconfigure(0, weight=1)

        self.mode_badge = ttk.Label(badge_frame,
                                    text=f"Subject lock: ON")
        self.mode_badge.grid(row=0, column=0, sticky="w")

        ttk.Button(badge_frame, text=" Copy Prompt", width=18,
                   command=self._copy_prompt_to_clipboard).grid(row=0, column=1, sticky="e", padx=(4, 0))

        _pt_scroll = ttk.Scrollbar(preview_frame, orient="vertical")
        self.prompt_text = tk.Text(
            preview_frame, wrap="word", font=self.mono_font, height=12,
            yscrollcommand=_pt_scroll.set,
        )
        _pt_scroll.config(command=self.prompt_text.yview)
        self.prompt_text.grid(row=1, column=0, sticky="nsew")
        _pt_scroll.grid(row=1, column=1, sticky="ns")
        self.prompt_text.config(state="disabled")
        self.prompt_text.bind("<MouseWheel>", lambda e: self._on_prompt_text_scroll(e))
        # read-only preview: keep it OUT of the Tab ring (it would trap Tab)
        if UI_EFFECTS_AVAILABLE:
            make_text_tab_friendly(self.prompt_text)

        # ═══════════════════════ RIGHT PANEL (GALLERY) ══════════════════════
        right = ttk.Frame(self.main, padding=(8, 8))
        right.grid(row=0, column=2, sticky="nsew")
        right.rowconfigure(1, weight=1)
        right.columnconfigure(0, weight=1)
        self._right_panel = right

        # Header: "My Collection" + view icons
        gallery_header = ttk.Frame(right)
        gallery_header.grid(row=0, column=0, sticky="ew", pady=(0, 6))

        ttk.Label(gallery_header, text="My Collection",
                  font=self.sidebar_title_font).pack(side="left")

        button_frame = ttk.Frame(gallery_header)
        button_frame.pack(side="right")

        # Header buttons — packed dynamically so order can change per view
        self._btn_export_portraits = ttk.Button(button_frame, text="Export Portraits",
                   command=self._gallery_export_portraits)
        self._btn_open_folder = ttk.Button(button_frame, text="📂 Open Folder",
                   command=self._open_wallpapers_folder)
        self._btn_tutorials = ttk.Button(button_frame, text="Tutorials",
                   command=self._show_tutorial_menu)
        # Initial pack (non-portrait order: Open Folder | Tutorials)
        self._repack_header_buttons(is_portrait=False)

        # Gallery content — delegate to existing builder
        gallery_content = ttk.Frame(right, padding=(0, 0))
        gallery_content.grid(row=1, column=0, sticky="nsew")
        self._build_gallery_tab(gallery_content)

        # ═══════════════════════ BOTTOM STATUS BAR ══════════════════════════
        bottom = ttk.Frame(self.main, style="Surface.TFrame")
        bottom.grid(row=1, column=0, columnspan=3, sticky="ew", padx=8, pady=(4, 4))
        self.bottom_bar = bottom

        # Cloud sync quick button (left side of status bar)
        self._statusbar_sync_btn = ttk.Button(bottom, text="☁ Sync",
                                                  command=self._manual_sync, width=9)
        self._statusbar_sync_btn.pack(side="left", padx=(0, 8))
        self._statusbar_sync_lbl = ttk.Label(bottom, text="", font=self.small_font)
        self._statusbar_sync_lbl.pack(side="left")
        self._sync_status_lbl = self._statusbar_sync_lbl

        ttk.Label(bottom, textvariable=self.statusvar).pack(side="right")

        # ── Notebook stub (kept so existing code doesn't crash) ─────────────
        # Hidden notebook — never displayed, but self.notebook.select() calls
        # are wrapped in try/except throughout, so this is safe.
        self._notebook_stub = ttk.Frame(self.main)
        self.notebook = ttk.Notebook(self._notebook_stub)
        gallery_tab = ttk.Frame(self.notebook)
        self.gallery_tab = gallery_tab
        prompt_builder_tab = ttk.Frame(self.notebook)
        self.prompt_builder_tab = prompt_builder_tab
        self.generator_tab = prompt_builder_tab
        settings_tab = ttk.Frame(self._notebook_stub, padding=(20, 10))
        self.settings_tab = settings_tab
        self.notebook.add(prompt_builder_tab, text="Prompt Builder")
        self.notebook.add(gallery_tab, text="Gallery")

        # Build prompt builder into hidden tab so Quick Build refs exist
        self.build_prompt_builder_tab(prompt_builder_tab)

        # Build settings into hidden tab (opened via modal)
        self._build_settings_tab(settings_tab)

        # Sync slideshow state now that widgets exist
        self.sync_slideshow_state()

        self.root.bind_all("<MouseWheel>", self._on_mousewheel)

    def _repack_header_buttons(self, is_portrait=False):
        """Repack the header buttons (Export Portraits / Open Folder / Tutorials).

        Portrait order:  Export Portraits | Open Folder | Tutorials
        Other view order: Open Folder | Tutorials  (Export Portraits hidden)
        """
        for btn in (self._btn_export_portraits, self._btn_open_folder, self._btn_tutorials):
            btn.pack_forget()

        if is_portrait:
            self._btn_export_portraits.pack(side="left", padx=(0, 8))
            self._btn_open_folder.pack(side="left", padx=(0, 8))
            self._btn_tutorials.pack(side="left")
        else:
            self._btn_open_folder.pack(side="left", padx=(0, 8))
            self._btn_tutorials.pack(side="left")

    def _on_minimize_to_tray_changed(self):
        """Handle minimize-to-tray setting change."""
        new_value = self.minimize_to_tray_var.get()

        self.minimize_to_tray_enabled = new_value
        config = load_config()
        config["minimize_to_tray"] = new_value
        save_config(config)

        if hasattr(self, "_tray_icon") and self._tray_icon:
            try:
                self._tray_icon.update_menu()
            except Exception as e:
                logger.error(f"Error updating tray menu: {e}")

    def on_close(self):
        """Minimize to taskbar (and tray) when X is pressed; only quit on explicit Quit."""
        if hasattr(self, "save_current_settings_for_memory"):
            self.save_current_settings_for_memory()

        if self.minimize_to_tray_enabled:
            self.root.withdraw()   # hide window completely, show only tray icon
            self._start_tray()
        else:
            self._stop_fullscreen_watcher()
            self.slideshow.stop()
            self._stop_tray()
            self._shutdown_db()
            try:
                self.root.destroy()
            except Exception:
                pass
            import os
            os._exit(0)

    def _shutdown_db(self):
        """Close database connections before app exits."""
        try:
            import database
            database.shutdown_db()
        except Exception:
            pass

    def migrate_saved_image_paths(self):

        updated_favorites = 0

        # One disk scan for all guesses.

        known_images = self._all_known_images()

        for item in self.favorites:

            if not item.get("image_path"):

                guessed = self._guess_image_for_item(item, known_images=known_images)

                if guessed:

                    item["image_path"] = str(guessed)

                    updated_favorites += 1

        if updated_favorites:

            save_json_list(FAVORITES_LOG, self.favorites)

        # Also run the GalleryTab's original_image_path backfill, which
        # repairs favorites (created by older versions or migrated from the
        # legacy top-level favorites/ folder) whose JSON entry is missing
        # original_image_path. Without this, the heart icon on the Gallery/
        # Styled/Manual views shows as outline even though the image is in
        # favorites — see load_favorites() for the runtime fallback.
        try:
            if hasattr(self, '_gallery_tab'):
                backfilled = self._gallery_tab._backfill_original_image_paths()
                updated_favorites += backfilled or 0
        except Exception as e:
            try:
                logger.warning(f"migrate_saved_image_paths: backfill failed: {e}")
            except Exception:
                pass

        return 0, updated_favorites



    def load_presets(self):
        self.presets = load_presets()
        # Presets UI removed - just load the data for potential future use



    def _preset_payload(self):

        return {

            "subject": self.get_active_subject(),

            "style": self.get_active_style(),

            "lighting": self.get_active_lighting(),

            "mood": self.get_active_mood(),

            "color": self.get_active_color(),

            "mode": self.get_active_mode(),

            "subject_lock": self.get_active_subject_lock(),

            "negative_prompt": self.get_active_negative_prompt(),

        }



    def save_current_preset(self):

        name = simpledialog.askstring("Save Preset Bundle", "Preset name:", parent=self.root)

        if not name or not name.strip():

            return

        name = name.strip()

        

        # Save as a full bundle including themes and prompts

        payload = self._preset_payload()

        save_bundle_preset(

            name=name,

            subject=payload["subject"],

            style=payload["style"],

            lighting=payload["lighting"],

            mood=payload["mood"],

            style_mode=payload["mode"],

            themes=self.themes if self.themes else [],

            prompts=self.prompts if self.prompts else [],

            favorite_prompts=[],  # Could be populated later

        )

        self.load_presets()
        self.status_var.set(f"✓ Bundle preset saved: {name}")


    def load_selected_preset(self):
        # Presets UI removed - this method is no longer used
        pass


    def delete_current_preset(self):
        # Presets UI removed - this method is no longer used
        pass


    def export_preset_bundle(self):
        """Export current preset to a shareable JSON file."""
        # Presets UI removed - this method is no longer used
        pass



    def import_preset_bundle(self):

        """Import a preset from a JSON file."""

        from tkinter import filedialog

        path = filedialog.askopenfilename(

            filetypes=[("JSON files", "*.json")],

            title="Import Preset Bundle",

        )

        if not path:

            return

        preset_id = import_preset(path)

        if preset_id:

            self.load_presets()

            preset = get_preset_by_id(preset_id)

            if preset:
                # Presets UI removed - no need to set preset_var
                pass
            self.status_var.set(f"✓ Preset imported: {Path(path).name}")
            self._dialog.info("Import Successful", f"Preset imported and loaded.")

        else:
            self._dialog.error("Import Failed", "Could not import preset file.")





    def _all_known_images(self):

        paths = []

        try:

            paths.extend(collect_wallpapers())

        except Exception:

            pass

        wallpapers_root = BASE_DIR / "wallpapers"

        if wallpapers_root.exists():

            for p in wallpapers_root.rglob("*"):

                if p.is_file() and p.suffix.lower() in IMAGE_EXTS:

                    paths.append(p)

        unique = []

        seen = set()

        for p in paths:

            rp = str(Path(p).resolve())

            if rp not in seen:

                seen.add(rp)

                unique.append(Path(p))

        unique.sort(key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)

        return unique



    def _guess_image_for_item(self, item, strict=False, known_images=None):

        for key in ("image_path", "path", "last_image_path"):

            val = item.get(key)

            if val:

                p = Path(val)

                if p.exists():

                    return p

        if strict:

            return None

        known = known_images if known_images is not None else self._all_known_images()

        sentence = (item.get("theme_sentence") or "").strip().lower()

        prompt = (item.get("prompt") or "").strip().lower()

        for p in known:

            name = p.stem.lower()

            if sentence and any(word for word in sentence.split()[:3] if word and word in name):

                return p

            if prompt and any(word for word in prompt.split()[:3] if word and word in name):

                return p

        return known[0] if known else None



    def _on_preview_resize(self, event=None):
        if self.last_preview_path:
            self._render_preview(self.last_preview_path)

    def _render_preview(self, path):
        try:
            from PIL import Image, ImageTk
            path = Path(path)
            img = Image.open(path)
            w = max(self.image_label.winfo_width(), 100)
            h = max(self.image_label.winfo_height(), 100)
            preview = img.copy()
            preview.thumbnail((w, h), Image.Resampling.LANCZOS)
            self.last_image_tk = ImageTk.PhotoImage(preview)
            self.image_label.config(image=self.last_image_tk, text="")
        except Exception:
            pass

    def show_preview_in_left_panel(self, path, source_text="Preview"):

        try:

            from PIL import Image, ImageTk

            path = Path(path)

            img = Image.open(path)

            orig_w, orig_h = img.size

            self.last_preview_path = path
            w = max(self.image_label.winfo_width(), 100)
            h = max(self.image_label.winfo_height(), 100)
            preview = img.copy()
            preview.thumbnail((w, h), Image.Resampling.LANCZOS)

            self.last_image_tk = ImageTk.PhotoImage(preview)

            self.image_label.config(image=self.last_image_tk, text="")

            self.preview_source_label.config(text=source_text)

            size_bytes = path.stat().st_size

            size_str = f"{size_bytes / 1_048_576:.1f} MB" if size_bytes >= 1_048_576 else f"{size_bytes / 1024:.1f} KB"

            self.preview_name_label.config(text=path.name)

            self.preview_dims_label.config(text=f"Resolution: {orig_w} × {orig_h} px")

            self.preview_size_label.config(text=f"File size: {size_str}")

        except Exception as e:

            self.image_label.config(text=f"Preview failed: {e}", image="")

            self.preview_source_label.config(text=source_text)

            self.preview_name_label.config(text="")

            self.preview_dims_label.config(text="")

            self.preview_size_label.config(text="")

    def _on_mousewheel(self, event):
        """Handle mousewheel scrolling with context awareness."""
        try:
            # ── If mouse is over a Toplevel (e.g. Settings window), skip gallery ──
            # The gallery hit-test below uses root-relative coordinates, so when a
            # Toplevel overlaps the gallery the gallery would steal the scroll event.
            # Instead, fall through to the _hover_canvas fallback which the settings
            # canvas sets up via <Enter>/<Leave> bindings.
            pointer_x = self.root.winfo_pointerx()
            pointer_y = self.root.winfo_pointery()
            for child_win in self.root.winfo_children():
                if isinstance(child_win, tk.Toplevel) and child_win.winfo_exists() and child_win.winfo_viewable():
                    wx = child_win.winfo_rootx()
                    wy = child_win.winfo_rooty()
                    ww = child_win.winfo_width()
                    wh = child_win.winfo_height()
                    if wx <= pointer_x <= wx + ww and wy <= pointer_y <= wy + wh:
                        # Mouse is over a Toplevel — let _hover_canvas handle it
                        hover_c = getattr(self, '_hover_canvas', None)
                        if hover_c is not None:
                            try:
                                hover_c.yview_scroll(int(-1 * (event.delta / 120)), "units")
                            except Exception:
                                pass
                        return "break"

            # Get mouse position (used for all hit-testing below)
            mouse_x = pointer_x - self.root.winfo_rootx()
            mouse_y = pointer_y - self.root.winfo_rooty()

            # If focus is in an input widget, ONLY block scrolling when the
            # mouse is actually over that input widget.  Otherwise the scroll
            # event should still reach the canvas the mouse is hovering over.
            focus_widget = self.root.focus_get()
            if focus_widget:
                widget_class = focus_widget.winfo_class()
                if widget_class in ('TEntry', 'Entry', 'TCombobox', 'Combobox', 'Text'):
                    try:
                        fx = focus_widget.winfo_rootx() - self.root.winfo_rootx()
                        fy = focus_widget.winfo_rooty() - self.root.winfo_rooty()
                        fw = focus_widget.winfo_width()
                        fh = focus_widget.winfo_height()
                        if (fx <= mouse_x <= fx + fw and fy <= mouse_y <= fy + fh):
                            # Mouse IS over the focused input — let it scroll
                            # the input natively (e.g. combobox dropdown list).
                            return
                    except Exception:
                        pass
                    # Mouse is NOT over the focused input — fall through and
                    # scroll the canvas the mouse is actually hovering over.

            # Check if mouse is over Prompt Preview text widget
            if hasattr(self, 'prompt_text'):
                try:
                    widget_x = self.prompt_text.winfo_rootx() - self.root.winfo_rootx()
                    widget_y = self.prompt_text.winfo_rooty() - self.root.winfo_rooty()
                    widget_w = self.prompt_text.winfo_width()
                    widget_h = self.prompt_text.winfo_height()
                    if (widget_x <= mouse_x <= widget_x + widget_w and
                        widget_y <= mouse_y <= widget_y + widget_h):
                        # Mouse is over prompt text - scroll it locally
                        self.prompt_text.yview_scroll(int(-1 * (event.delta / 120)), "units")
                        return "break"
                except Exception:
                    pass

            # Gallery is always visible — scroll the active view canvas
            # First determine which canvas to scroll based on mouse position
            target_canvas = None
            view = getattr(self, "gallery_view_var", None)
            
            if view:
                current_view = view.get()
                # Check if mouse is over the active gallery canvas
                if current_view == "Favorites" and hasattr(self, 'gallery_fav_canvas'):
                    widget_x = self.gallery_fav_canvas.winfo_rootx() - self.root.winfo_rootx()
                    widget_y = self.gallery_fav_canvas.winfo_rooty() - self.root.winfo_rooty()
                    widget_w = self.gallery_fav_canvas.winfo_width()
                    widget_h = self.gallery_fav_canvas.winfo_height()
                    if (widget_x <= mouse_x <= widget_x + widget_w and
                        widget_y <= mouse_y <= widget_y + widget_h):
                        target_canvas = self.gallery_fav_canvas
                elif current_view == "Styled" and hasattr(self, 'gallery_styled_canvas'):
                    widget_x = self.gallery_styled_canvas.winfo_rootx() - self.root.winfo_rootx()
                    widget_y = self.gallery_styled_canvas.winfo_rooty() - self.root.winfo_rooty()
                    widget_w = self.gallery_styled_canvas.winfo_width()
                    widget_h = self.gallery_styled_canvas.winfo_height()
                    if (widget_x <= mouse_x <= widget_x + widget_w and
                        widget_y <= mouse_y <= widget_y + widget_h):
                        target_canvas = self.gallery_styled_canvas
                elif current_view == "Manual" and hasattr(self, 'gallery_manual_canvas'):
                    widget_x = self.gallery_manual_canvas.winfo_rootx() - self.root.winfo_rootx()
                    widget_y = self.gallery_manual_canvas.winfo_rooty() - self.root.winfo_rooty()
                    widget_w = self.gallery_manual_canvas.winfo_width()
                    widget_h = self.gallery_manual_canvas.winfo_height()
                    if (widget_x <= mouse_x <= widget_x + widget_w and
                        widget_y <= mouse_y <= widget_y + widget_h):
                        target_canvas = self.gallery_manual_canvas
                elif hasattr(self, 'gallery_canvas'):
                    # Default gallery view
                    widget_x = self.gallery_canvas.winfo_rootx() - self.root.winfo_rootx()
                    widget_y = self.gallery_canvas.winfo_rooty() - self.root.winfo_rooty()
                    widget_w = self.gallery_canvas.winfo_width()
                    widget_h = self.gallery_canvas.winfo_height()
                    if (widget_x <= mouse_x <= widget_x + widget_w and
                        widget_y <= mouse_y <= widget_y + widget_h):
                        target_canvas = self.gallery_canvas

            # Scroll the target canvas if found
            if target_canvas:
                target_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
                if target_canvas == self.gallery_canvas:
                    self._on_gallery_scroll()
                return "break"

            # Fallback: scroll whatever canvas the mouse is hovering over
            # (settings tab, tutorial popups, prompt template vars, etc.)
            hover_c = getattr(self, '_hover_canvas', None)
            if hover_c is not None:
                try:
                    hover_c.yview_scroll(int(-1 * (event.delta / 120)), "units")
                    return "break"
                except Exception:
                    pass

        except Exception:
            pass

    def _on_prompt_text_scroll(self, event):
        """Handle mousewheel scrolling specifically for Prompt Preview text widget."""
        try:
            self.prompt_text.yview_scroll(int(-1 * (event.delta / 120)), "units")
            return "break"  # Prevent event from bubbling up to parent
        except Exception:
            pass

    def _on_template_var_scroll(self, event):

        """Handle mousewheel scrolling on the template variables scrollable area."""

        try:

            self.template_var_scroll_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        except Exception:

            pass

    def set_prompt_text(self, text):

        self.prompt_text.config(state="normal")

        self.prompt_text.delete("1.0", tk.END)

        self.prompt_text.insert("1.0", text)

        self.prompt_text.config(state="disabled")

    def get_prompt_text(self):
        """Return the current generator prompt text."""
        try:
            return self.prompt_text.get("1.0", tk.END).strip()
        except Exception:
            return ""

    def clear_prompt(self):

            self.set_prompt_text("")

    def _show_about_dialog(self, icon=None, item=None):
        """Show About dialog from tray menu."""
        return self._tray_mgr._tray_show_about(icon, item)

    def _show_about_popup(self):
        """Display the About popup window with full theme support."""
        # Restore window if minimized to ensure popup appears
        if self.root.state() == "iconic":
            self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

        about_window = tk.Toplevel(self.root)
        about_window.title("About FrogPaper")
        about_window.geometry("400x300")
        about_window.minsize(360, 260)
        about_window.resizable(True, False)
        about_window.transient(self.root)
        about_window.grab_set()

        from utils import center_window
        center_window(self.root, about_window)

        # Apply full theme styling
        pal = THEMES.get(self.current_theme_name, THEMES["darkforest"])
        about_window.configure(bg=pal["panel"])

        # ── Glassmorphism backdrop for About dialog ──
        glass_overlay = None
        if UI_EFFECTS_AVAILABLE:
            try:
                glass_overlay = apply_glass_to_dialog(
                    about_window, width=400, height=300,
                    corner_radius=20, bg_color=pal["bg"]
                )
            except Exception:
                pass

        # Main container with fixed bottom button bar
        main_frame = tk.Frame(about_window, bg=pal["panel"])
        main_frame.pack(fill="both", expand=True)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=0)

        # Content area (scrollable/shrinkable)
        content_frame = tk.Frame(main_frame, bg=pal["panel"])
        content_frame.grid(row=0, column=0, sticky="nsew", padx=24, pady=(20, 8))
        content_frame.columnconfigure(0, weight=1)

        # Title with accent color
        title_label = tk.Label(
            content_frame,
            text="🐸 FrogPaper",
            font=("Segoe UI", 20, "bold"),
            bg=pal["panel"],
            fg=pal.get("accent", pal["text"])
        )
        title_label.pack(pady=(0, 8))

        # Subtitle
        tk.Label(
            content_frame,
            text="AI Wallpaper Generator",
            font=("Segoe UI", 12),
            bg=pal["panel"],
            fg=pal["text"]
        ).pack()

        # Description
        tk.Label(
            content_frame,
            text="Generate, style, and manage wallpapers from one app.",
            font=("Segoe UI", 10),
            bg=pal["panel"],
            fg=pal.get("muted", "#888"),
            wraplength=320
        ).pack(pady=(10, 2))

        # New features
        tk.Label(
            content_frame,
            text="✨ v1.5.0: Faster gallery views (lazy thumbnails + caching), keyboard navigation & Tab fixes, friendly file-error dialogs • v1.4.1: Fixed gallery scroll bug after switching views/ratios",
            font=("Segoe UI", 9),
            bg=pal["panel"],
            fg=pal.get("accent", pal["progress"]),
            wraplength=320
        ).pack(pady=(0, 10))

        # Version
        tk.Label(
            content_frame,
            text=f"Version {APP_VERSION}",
            font=("Segoe UI", 10, "italic"),
            bg=pal["panel"],
            fg=pal.get("muted", "#888")
        ).pack()

        # Fixed bottom button bar
        btn_bar = tk.Frame(main_frame, bg=pal["panel2"], height=54)
        btn_bar.grid(row=1, column=0, sticky="ew")
        btn_bar.grid_propagate(False)
        btn_bar.columnconfigure(0, weight=1)

        if UI_EFFECTS_AVAILABLE:
            ok_btn = RoundedButton(
                btn_bar, text="OK", width=100, height=32,
                fill_color=pal.get("accent", pal["progress"]),
                text_color=_readable_fg(pal.get("button_fg", COLOR_WHITE),
                                        COLOR_NEAR_BLACK, COLOR_WHITE,
                                        pal.get("accent", pal["progress"])),
                radius=8, font=("Segoe UI", 10),
                command=about_window.destroy, use_gradient=True,
            )
            ok_btn.place(relx=0.5, rely=0.5, anchor="center")
        else:
            ok_btn = tk.Button(
                btn_bar,
                text="OK",
                command=about_window.destroy,
                width=14,
                font=("Segoe UI", 10),
                bg=pal.get("accent", pal["progress"]),
                fg=pal["text"],
                activebackground=pal.get("surface", pal["panel"]),
                activeforeground=pal["text"],
                relief="flat",
                cursor="hand2"
            )
            ok_btn.place(relx=0.5, rely=0.5, anchor="center")



    # ── Fullscreen slideshow pause ─────────────────────────────────────────

    def _on_pause_fullscreen_toggle(self):
        if self.slideshow_pause_on_fullscreen_var.get():
            self._start_fullscreen_watcher()
        else:
            self._stop_fullscreen_watcher()
            if self._fullscreen_was_detected and self.slideshow.running and self.slideshow.paused:
                self.slideshow.resume()
                self._fullscreen_was_detected = False
                self.status_var.set('Fullscreen mode ended — slideshow resumed.')

    def _start_fullscreen_watcher(self):
        self._stop_fullscreen_watcher()
        self._fullscreen_check_loop()

    def _stop_fullscreen_watcher(self):
        if self._fullscreen_check_job is not None:
            try:
                self.root.after_cancel(self._fullscreen_check_job)
            except Exception:
                pass
            self._fullscreen_check_job = None
        self._fullscreen_was_detected = False

    def _fullscreen_check_loop(self):
        if not self.slideshow_pause_on_fullscreen_var.get():
            self._fullscreen_check_job = None
            return
        try:
            is_fs = _is_foreground_window_fullscreen()
            if is_fs and not self._fullscreen_was_detected:
                self._fullscreen_was_detected = True
                if self.slideshow.running and not self.slideshow.paused:
                    self.slideshow.pause()
                    self.status_var.set('Fullscreen app detected — slideshow paused.')
            elif not is_fs and self._fullscreen_was_detected:
                self._fullscreen_was_detected = False
                if self.slideshow.running and self.slideshow.paused:
                    self.slideshow.resume()
                    self.status_var.set('Fullscreen mode ended — slideshow resumed.')
        except Exception:
            pass
        self._fullscreen_check_job = self.root.after(3000, self._fullscreen_check_loop)

    def _add_fullscreen_setting(self, parent):
        """Find the 'Skip duplicates' checkbox and add 'Pause on fullscreen' below it.
        Called after settings_tab builds its UI."""
        try:
            # Walk all children to find the Gallery & Slideshow frame
            for widget in parent.winfo_children():
                for child in widget.winfo_children():
                    for grandchild in child.winfo_children():
                        for gc2 in grandchild.winfo_children():
                            try:
                                txt = gc2.cget('text') if hasattr(gc2, 'cget') else ''
                                if 'Skip duplicates' in str(txt):
                                    # Found it — shift all rows below this one down by 2 FIRST
                                    row_info = gc2.grid_info()
                                    r = row_info.get('row', 0)
                                    p = gc2.master
                                    # Shift existing widgets down before inserting new ones
                                    for w in p.winfo_children():
                                        info = w.grid_info()
                                        if not info:
                                            continue
                                        wr = info.get('row', 0)
                                        if wr > r:
                                            w.grid(row=wr + 2)
                                    # Now insert into the cleared rows
                                    ttk.Checkbutton(p, text='Pause when a full-screen app is active',
                                                    variable=self.slideshow_pause_on_fullscreen_var,
                                                    command=self._on_pause_fullscreen_toggle).grid(
                                        row=r+1, column=0, columnspan=2, sticky='w', pady=(0, 2))
                                    ttk.Label(p, text='Auto-pauses slideshow while games, videos, or presentations are full-screen',
                                              font=self.small_font, foreground=COLOR_DIM_GRAY, wraplength=620).grid(
                                        row=r+2, column=0, columnspan=2, sticky='w', pady=(0, 6))
                                    return
                            except Exception:
                                pass
        except Exception:
            pass

    def _on_minimize(self, event=None):

        """Handle window minimize event — keep taskbar button; start tray if enabled."""

        # Only trigger if window is actually being minimized (state is "iconic").
        # Do NOT withdraw — that removes the taskbar button.
        # Stay iconic so the taskbar entry remains; only add the tray icon.
        if self.minimize_to_tray_enabled and self.root.state() == "iconic":

            self._start_tray()



    def advance_slideshow(self):

        """Advance slideshow with single step and debounce."""

        # Debounce: only allow one advance per second

        current_time = time.time()

        if not hasattr(self, '_last_advance_time'):

            self._last_advance_time = 0

        

        if current_time - self._last_advance_time < 1.0:  # 1 second debounce

            return  # Ignore rapid clicks

        

        self._last_advance_time = current_time

        self.slideshow.advance_once()  # Use advance_once instead of next_now for single step




def _acquire_single_instance_mutex():
    """Create a named Windows mutex to enforce a single running instance.
    Returns the mutex handle on success, or None if another instance is already running."""
    import ctypes
    mutex = ctypes.windll.kernel32.CreateMutexW(None, True, "FrogPaper_SingleInstance_Mutex")
    if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        ctypes.windll.kernel32.CloseHandle(mutex)
        return None
    return mutex

def _release_mutex(mutex):
    """Release the mutex handle."""
    if mutex:
        import ctypes
        ctypes.windll.kernel32.CloseHandle(mutex)


def main():

        mutex = _acquire_single_instance_mutex()
        if mutex is None:
            import tkinter as _tk
            _r = _tk.Tk()
            _r.withdraw()
            from tkinter import messagebox as _mb
            _mb.showwarning(
                "FrogPaper Already Running",
                "FrogPaper is already open.\n\nCheck your taskbar or system tray."
            )
            _r.destroy()
            return

        try:
            root = tk.Tk()

            app = FrogPaperApp(root)

            app.update_mode_badge()

            app.refresh_token_status()

            # Check for updates in the background (non-blocking)
            try:
                from update_checker import check_on_startup
                check_on_startup(app, APP_VERSION, delay_seconds=5)
            except Exception:
                pass  # Update checker is optional — don't crash if it fails

            # Auto-generate a fresh wallpaper on startup if enabled
            if app.auto_generate_on_startup_var.get():
                def _startup_generate():
                    # Use the configured startup subject from settings (defaults to "frog")
                    subject = app.startup_subject_var.get().strip() or "frog"
                    app.set_active_subject(subject)
                    # Randomize everything except subject
                    import random as _rng
                    import time
                    _rng.seed(int(time.time() * 1000))  # Ensure different random values each time
                    settings = [o for o in THEME_VARIABLE_OPTIONS["setting"] if o]
                    styles = [o for o in THEME_VARIABLE_OPTIONS["style"] if o]
                    lightings = [o for o in THEME_VARIABLE_OPTIONS["lighting"] if o]
                    moods = [o for o in THEME_VARIABLE_OPTIONS["mood"] if o]
                    atmospheres = [o for o in THEME_VARIABLE_OPTIONS.get("atmosphere", []) if o]
                    color_families = [f for f in COLOR_FAMILIES if f]
                    family = _rng.choice(color_families)
                    variation = _rng.choice(COLOR_VARIATIONS)
                    color_value = f"{variation} {family}".strip() if variation else family
                    random_setting = _rng.choice(settings)
                    random_style = _rng.choice(styles)
                    random_lighting = _rng.choice(lightings)
                    random_mood = _rng.choice(moods)
                    random_atmosphere = _rng.choice(atmospheres)
                    random_mode = _rng.choice(STYLE_MODES)

                    # Apply random values to both sidebar and PB Quick Build widgets
                    app.set_active_setting(random_setting)
                    app.set_active_style(random_style)
                    app.set_active_lighting(random_lighting)
                    app.set_active_mood(random_mood)
                    app.set_active_color(color_value)
                    app.set_active_atmosphere(random_atmosphere)
                    app.set_active_mode(random_mode)

                    # Also update sidebar widgets directly to ensure they have the random values
                    if hasattr(app, 'setting_entry'):
                        app.setting_entry.delete(0, tk.END)
                        app.setting_entry.insert(0, random_setting)
                    if hasattr(app, 'style_entry'):
                        app.style_entry.delete(0, tk.END)
                        app.style_entry.insert(0, random_style)
                    if hasattr(app, 'lighting_entry'):
                        app.lighting_entry.delete(0, tk.END)
                        app.lighting_entry.insert(0, random_lighting)
                    if hasattr(app, 'mood_entry'):
                        if isinstance(app.mood_entry, ttk.Combobox):
                            app.mood_entry.set(random_mood)
                        else:
                            app.mood_entry.delete(0, tk.END)
                            app.mood_entry.insert(0, random_mood)
                    # Update color family and color variation sidebar widgets
                    if hasattr(app, 'color_family_var'):
                        app.color_family_var.set(family)
                    if hasattr(app, 'color_variation_var'):
                        app.color_variation_var.set(variation)
                    # Update atmosphere sidebar widget
                    if hasattr(app, 'atmosphere_var'):
                        app.atmosphere_var.set(random_atmosphere)
                    # Update mode sidebar widget directly
                    if hasattr(app, 'mode_var'):
                        app.mode_var.set(random_mode)

                    app.update_mode_badge()

                    # Force UI update before generation
                    app.root.update()

                    app.generate(show_progress=False)  # This generates themes/prompts AND the image
                root.after(2000, _startup_generate)

            root.mainloop()
        finally:
            _release_mutex(mutex)



if __name__ == "__main__":

        main()



