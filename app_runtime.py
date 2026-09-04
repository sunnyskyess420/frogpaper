"""Runtime environment probing for FrogPaper (roadmap #7 Phase B step 2).

Extracted verbatim from app.py: the optional-dependency try/except
blocks (thread_manager, pystray, sv_ttk, keyboard, ui_effects,
pinned_dropdowns) and the wallpaper-engine / platform detection.
app.py re-imports every name defined here, so ``app.<NAME>`` access
from other modules and bare-name references keep working unchanged.
"""

import threading


# Import thread-safe UI update functions
try:
    from thread_manager import run_background, schedule_ui_update
    THREAD_MANAGER_AVAILABLE = True
except ImportError:
    THREAD_MANAGER_AVAILABLE = False
    # Fallback to direct threading if thread_manager not available
    def schedule_ui_update(callback, *args, **kwargs):
        """Fallback for thread-safe UI updates."""
        if hasattr(callback, '__self__') and hasattr(callback.__self__, 'root'):
            callback.__self__.root.after(0, lambda: callback(*args, **kwargs))
        else:
            # Direct call as fallback (not thread-safe, but prevents crashes)
            callback(*args, **kwargs)
    
    def run_background(target, *args, daemon=True, **kwargs):
        """Fallback for background thread execution."""
        thread = threading.Thread(target=target, args=args, kwargs=kwargs, daemon=daemon)
        thread.start()
        return thread











try:

    import pystray  # noqa: F401  (availability probe)

    PYSTRAY_AVAILABLE = True

except ImportError:

    PYSTRAY_AVAILABLE = False

try:
    import sv_ttk  # noqa: F401  (availability probe)
    SV_TTK_AVAILABLE = True
except ImportError:
    SV_TTK_AVAILABLE = False

try:
    import keyboard  # noqa: F401  (availability probe)
    KEYBOARD_AVAILABLE = True
except ImportError:
    KEYBOARD_AVAILABLE = False

try:
    from ui_effects import (
        RoundedButton, create_shadow_image, ThemeTransition,
        apply_glass_to_dialog, lerp_color, make_text_tab_friendly,
    )
    UI_EFFECTS_AVAILABLE = True
except ImportError:
    UI_EFFECTS_AVAILABLE = False
    RoundedButton = None
    create_shadow_image = None
    ThemeTransition = None
    apply_glass_to_dialog = None
    lerp_color = None
    make_text_tab_friendly = None


# ── Pinned Dropdown Options (v1.3.2 → v1.5.0+) ─────────────────────────────
try:
    from pinned_dropdowns import (
        init_pinned_manager,  # noqa: F401  (availability probe)
        get_manager,  # noqa: F401  (availability probe)
        PinnedCombobox,  # noqa: F401  (availability probe)
        create_pinned_combobox,  # noqa: F401  (availability probe)
        build_pinned_settings_ui,  # noqa: F401  (availability probe)
    )
    PINNED_DROPDOWNS_AVAILABLE = True
except ImportError:
    PINNED_DROPDOWNS_AVAILABLE = False


try:

    from set_wallpaper import set_wallpaper, collect_wallpapers

    WINDOWS = True
    
    
    
    
    

except (ImportError, AttributeError):

    WINDOWS = False

    def collect_wallpapers():

        return []

    def set_wallpaper(_path):

        return False
