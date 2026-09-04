"""FrogPaper theme data and WCAG contrast helpers (roadmap #7 Phase B).

Extracted from app.py: the THEMES palette dictionary (single source of
truth for every colour in the app), layout/spacing constants (UI), the
display<->internal theme name maps, and the WCAG relative-luminance /
contrast-ratio helpers used by apply_theme to keep button text readable
on light themes.

app.py re-imports all of these, so app.THEMES / app.UI / bare-name
references keep working unchanged.
"""

# ── WCAG contrast helpers ─────────────────────────────────────────────────
# Some light themes ship button_fg colours designed for their saturated
# accent buttons (neoncyber_light uses pure white).  Plain buttons are
# painted on the light panel2 sprite, where such text is invisible.
# These helpers let apply_theme validate each foreground against the
# surface it is actually painted on and fall back to a readable colour.

def _rel_luminance(hex_color):
    """WCAG relative luminance of a hex colour (0.0 – 1.0)."""
    try:
        h = str(hex_color).strip().lstrip("#")
        if len(h) == 3:
            h = "".join(ch * 2 for ch in h)
        if len(h) != 6:
            return 0.0
        def _chan(v):
            v = v / 255.0
            return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
        r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
        return 0.2126 * _chan(r) + 0.7152 * _chan(g) + 0.0722 * _chan(b)
    except Exception:
        return 0.0


def _contrast_ratio(c1, c2):
    """WCAG contrast ratio between two colours (1.0 – 21.0)."""
    l1, l2 = _rel_luminance(c1), _rel_luminance(c2)
    if l1 < l2:
        l1, l2 = l2, l1
    return (l1 + 0.05) / (l2 + 0.05) if l2 > 0 else 21.0


def _readable_fg(preferred, fallback_dark, fallback_light, surface,
                 min_ratio=3.0):
    """Return a foreground that is actually readable on *surface*.

    Keeps *preferred* whenever it reaches *min_ratio* contrast on the
    surface (preserving every theme whose palette already works).
    Otherwise returns whichever fallback — dark or light — reads better.
    """
    try:
        if _contrast_ratio(preferred, surface) >= min_ratio:
            return preferred
    except Exception:
        pass
    try:
        return (fallback_dark
                if _contrast_ratio(fallback_dark, surface)
                >= _contrast_ratio(fallback_light, surface)
                else fallback_light)
    except Exception:
        return preferred


THEMES = {

    # ── Dark Moss / Lily Pad (default) ────────────────────────────────
    "darkforest": {
        "bg":          "#161d14",
        "panel":       "#1e2a1b",
        "panel2":      "#263322",
        "surface":     "#2c3d28",
        "text":        "#d6eacf",
        "muted":       "#7a9b72",
        "entrybg":     "#1a2418",
        "entryfg":     "#cde4c6",
        "tabbg":       "#222e1f",
        "tabsel":      "#3a5c34",
        "accent":      "#5aad78",
        "progress":    "#4a8c62",
        "actions":     ["#2a6644","#358055","#429966","#52b077","#65c48a","#7dd49e"],
        "button_fg":   "#e6f5e0",
        "button_hover":"#4a8c62",
        "scrollbar_bg":"#1e2a1b",
        "scrollbar_fg":"#4a8c62",
        "selected_bg": "#3a5c34",
        "selected_fg": "#f0fff0",
        "border_color":"#334d2f",
        "separator":   "#263322",
        "success_color":"#65c48a",
        "error_color": "#c0392b",
        "warning_color":"#e6a020",
        "tag_fg":      "#7dd49e",
        "heading_font_size": 11, "label_font_weight": "bold",
        # Default special effects (disabled)
        "glow_color":   "",
        "glow_intensity": 0,
        "hover_transition": "",
        "focus_color":  "",
        "focus_shape":  "",
        "button_radius": 0,
        "mist_color":   "",
        "mist_alpha":   0,
    },

    # ── Light Mist / Lily ─────────────────────────────────────────────
    "lightforest": {
        "bg":          "#f0f7ec",
        "panel":       "#e0edda",
        "panel2":      "#cfe2c8",
        "surface":     "#f8fcf6",
        "text":        "#1a3318",
        "muted":       "#4d7a47",
        "entrybg":     "#f8fef5",
        "entryfg":     "#1a3318",
        "tabbg":       "#cfe2c8",
        "tabsel":      "#84bb7e",
        "accent":      "#3d8c50",
        "progress":    "#4a9960",
        "actions":     ["#2e7d32","#388e3c","#43a047","#4caf50","#66bb6a","#81c784"],
        "button_fg":   "#0e2210",
        "button_hover":"#2e7d32",
        "button_hover_fg": "#ffffff",
        "scrollbar_bg":"#e0edda",
        "scrollbar_fg":"#4a9960",
        "selected_bg": "#84bb7e",
        "selected_fg": "#0e2210",
        "border_color":"#b0d0a8",
        "separator":   "#cfe2c8",
        "success_color":"#388e3c",
        "error_color": "#c62828",
        "warning_color":"#ef6c00",
        "tag_fg":      "#2e7d32",
        "heading_font_size": 11, "label_font_weight": "bold",
        # Default special effects (disabled)
        "glow_color":   "",
        "glow_intensity": 0,
        "hover_transition": "",
        "focus_color":  "",
        "focus_shape":  "",
        "button_radius": 0,
        "mist_color":   "",
        "mist_alpha":   0,
    },


    # ── Clear Sky ─────────────────────────────────────────────────────
    "lightocean": {
        "bg":          "#eaf4fc",
        "panel":       "#d4eaf8",
        "panel2":      "#bcdcf0",
        "surface":     "#f4faff",
        "text":        "#0c2840",
        "muted":       "#366889",
        "entrybg":     "#f0f9ff",
        "entryfg":     "#0c2840",
        "tabbg":       "#bcdcf0",
        "tabsel":      "#62aacc",
        "accent":      "#1a7eb8",
        "progress":    "#1e88c8",
        "actions":     ["#01579b","#0277bd","#0288d1","#039be5","#29b6f6","#4fc3f7"],
        "button_fg":   "#0c2840",
        "button_hover":"#0277bd",
        "button_hover_fg": "#ffffff",
        "scrollbar_bg":"#d4eaf8",
        "scrollbar_fg":"#1e88c8",
        "selected_bg": "#62aacc",
        "selected_fg": "#ffffff",
        "border_color":"#8cc8e8",
        "separator":   "#bcdcf0",
        "success_color":"#0288d1",
        "error_color": "#c62828",
        "warning_color":"#ef6c00",
        "tag_fg":      "#0277bd",
        "heading_font_size": 11, "label_font_weight": "bold",
        # Default special effects (disabled)
        "glow_color":   "",
        "glow_intensity": 0,
        "hover_transition": "",
        "focus_color":  "",
        "focus_shape":  "",
        "button_radius": 0,
        "mist_color":   "",
        "mist_alpha":   0,
    },

    # ── Ember Dark ────────────────────────────────────────────────────
    "darksunset": {
        "bg":          "#1c1108",
        "panel":       "#281808",
        "panel2":      "#362010",
        "surface":     "#3e2814",
        "text":        "#eedcc4",
        "muted":       "#9c6e48",
        "entrybg":     "#201208",
        "entryfg":     "#e4c8a0",
        "tabbg":       "#301a0c",
        "tabsel":      "#6a3610",
        "accent":      "#e07840",
        "progress":    "#c05e28",
        "actions":     ["#bf360c","#d84315","#e64a19","#f4511e","#ff7043","#ff8a65"],
        "button_fg":   "#fff0e0",
        "button_hover":"#c05e28",
        "scrollbar_bg":"#281808",
        "scrollbar_fg":"#c05e28",
        "selected_bg": "#6a3610",
        "selected_fg": "#ffffff",
        "border_color":"#522c0c",
        "separator":   "#362010",
        "success_color":"#ff8a65",
        "error_color": "#b71c1c",
        "warning_color":"#ffd54f",
        "tag_fg":      "#ff8a65",
        "heading_font_size": 11, "label_font_weight": "bold",
        # Default special effects (disabled)
        "glow_color":   "",
        "glow_intensity": 0,
        "hover_transition": "",
        "focus_color":  "",
        "focus_shape":  "",
        "button_radius": 0,
        "mist_color":   "",
        "mist_alpha":   0,
    },

    # ── Warm Linen ────────────────────────────────────────────────────
    "lightsunset": {
        "bg":          "#fef8f0",
        "panel":       "#faecd8",
        "panel2":      "#f4dcbc",
        "surface":     "#fffcf8",
        "text":        "#38180a",
        "muted":       "#845830",
        "entrybg":     "#fffaf4",
        "entryfg":     "#38180a",
        "tabbg":       "#f4dcbc",
        "tabsel":      "#f0a060",
        "accent":      "#d86820",
        "progress":    "#d86820",
        "actions":     ["#e65100","#ef6c00","#f57c00","#fb8c00","#ffa726","#ffb74d"],
        "button_fg":   "#38180a",
        "button_hover":"#c05a18",
        "button_hover_fg": "#ffffff",
        "scrollbar_bg":"#faecd8",
        "scrollbar_fg":"#d86820",
        "selected_bg": "#f0a060",
        "selected_fg": "#38180a",
        "border_color":"#f0cca0",
        "separator":   "#f4dcbc",
        "success_color":"#f57c00",
        "error_color": "#c62828",
        "warning_color":"#fdd835",
        "tag_fg":      "#e65100",
        "heading_font_size": 11, "label_font_weight": "bold",
        # Default special effects (disabled)
        "glow_color":   "",
        "glow_intensity": 0,
        "hover_transition": "",
        "focus_color":  "",
        "focus_shape":  "",
        "button_radius": 0,
        "mist_color":   "",
        "mist_alpha":   0,
    },

    # ── Pitch Dark ────────────────────────────────────────────────────
    "darkcontrast": {
        "bg":          "#080808",
        "panel":       "#111111",
        "panel2":      "#1c1c1c",
        "surface":     "#242424",
        "text":        "#f0f0f0",
        "muted":       "#aaaaaa",
        "entrybg":     "#0c0c0c",
        "entryfg":     "#f0f0f0",
        "tabbg":       "#1a1a1a",
        "tabsel":      "#404040",
        "accent":      "#90d090",
        "progress":    "#888888",
        "actions":     ["#333333","#444444","#555555","#666666","#777777","#888888"],
        "button_fg":   "#ffffff",
        "button_hover":"#505050",
        "scrollbar_bg":"#111111",
        "scrollbar_fg":"#888888",
        "selected_bg": "#404040",
        "selected_fg": "#ffffff",
        "border_color":"#303030",
        "separator":   "#1c1c1c",
        "success_color":"#aaaaaa",
        "error_color": "#ff4444",
        "warning_color":"#ffcc00",
        "tag_fg":      "#cccccc",
        "heading_font_size": 11, "label_font_weight": "bold",
        # Default special effects (disabled)
        "glow_color":   "",
        "glow_intensity": 0,
        "hover_transition": "",
        "focus_color":  "",
        "focus_shape":  "",
        "button_radius": 0,
        "mist_color":   "",
        "mist_alpha":   0,
    },

    # ── Clean White ───────────────────────────────────────────────────
    "lightcontrast": {
        "bg":          "#f8f8f8",
        "panel":       "#eeeeee",
        "panel2":      "#e0e0e0",
        "surface":     "#ffffff",
        "text":        "#111111",
        "muted":       "#555555",
        "entrybg":     "#fdfdfd",
        "entryfg":     "#111111",
        "tabbg":       "#e0e0e0",
        "tabsel":      "#999999",
        "accent":      "#3a8a50",
        "progress":    "#555555",
        "actions":     ["#222222","#333333","#444444","#555555","#666666","#777777"],
        "button_fg":   "#111111",
        "button_hover":"#444444",
        "button_hover_fg": "#ffffff",
        "scrollbar_bg":"#eeeeee",
        "scrollbar_fg":"#555555",
        "selected_bg": "#999999",
        "selected_fg": "#ffffff",
        "border_color":"#cccccc",
        "separator":   "#e0e0e0",
        "success_color":"#333333",
        "error_color": "#cc0000",
        "warning_color":"#cc7700",
        "tag_fg":      "#333333",
        "heading_font_size": 11, "label_font_weight": "bold",
        # Default special effects (disabled)
        "glow_color":   "",
        "glow_intensity": 0,
        "hover_transition": "",
        "focus_color":  "",
        "focus_shape":  "",
        "button_radius": 0,
        "mist_color":   "",
        "mist_alpha":   0,
    },

    # ── Neon Cyber ────────────────────────────────────────────────────
    "neoncyber": {
        "bg":          "#12081e",
        "panel":       "#1a1030",
        "panel2":      "#241840",
        "surface":     "#2e2050",
        "text":        "#f0eaff",
        "muted":       "#b080d0",
        "entrybg":     "#160c24",
        "entryfg":     "#e8daff",
        "tabbg":       "#1e1438",
        "tabsel":      "#3a1870",
        "accent":      "#c864ff",
        "progress":    "#a040e0",
        "actions":     ["#5020a0","#6030b8","#7040d0","#8850e0","#a060f0","#b878ff"],
        "button_fg":   "#f8ecff",
        "button_hover":"#7a30c0",
        "scrollbar_bg":"#1a1030",
        "scrollbar_fg":"#7a40c0",
        "selected_bg": "#4a2090",
        "selected_fg": "#ffffff",
        "border_color":"#442878",
        "separator":   "#2a1848",
        "success_color":"#40e0b0",
        "error_color": "#ff4070",
        "warning_color":"#ffd040",
        "tag_fg":      "#d090ff",
        "heading_font_size": 12, "label_font_weight": "bold",
        # Default special effects (disabled)
        "glow_color":   "",
        "glow_intensity": 0,
        "hover_transition": "",
        "focus_color":  "",
        "focus_shape":  "",
        "button_radius": 0,
        "mist_color":   "",
        "mist_alpha":   0,
    },

    # ── Warm Paper ────────────────────────────────────────────────────
    "warmpaper": {
        "bg":          "#f4ede0",
        "panel":       "#ece0cc",
        "panel2":      "#ddd0b8",
        "surface":     "#faf6ee",
        "text":        "#2c1e0e",
        "muted":       "#7a6040",
        "entrybg":     "#faf6ee",
        "entryfg":     "#2c1e0e",
        "tabbg":       "#ddd0b8",
        "tabsel":      "#c0a878",
        "accent":      "#a07040",
        "progress":    "#9c7040",
        "actions":     ["#6d4c41","#795548","#8d6e63","#a1887f","#bcaaa4","#d7ccc8"],
        "button_fg":   "#2c1e0e",
        "button_hover":"#6d4c41",
        "button_hover_fg": "#ffffff",
        "scrollbar_bg":"#ece0cc",
        "scrollbar_fg":"#9c7040",
        "selected_bg": "#c0a878",
        "selected_fg": "#2c1e0e",
        "border_color":"#ccc0a0",
        "separator":   "#ddd0b8",
        "success_color":"#558b2f",
        "error_color": "#b71c1c",
        "warning_color":"#e65100",
        "tag_fg":      "#6d4c41",
        "heading_font_size": 11, "label_font_weight": "normal",
        # Default special effects (disabled)
        "glow_color":   "",
        "glow_intensity": 0,
        "hover_transition": "",
        "focus_color":  "",
        "focus_shape":  "",
        "button_radius": 0,
        "mist_color":   "",
        "mist_alpha":   0,
    },

    # ── Studio Neutral ────────────────────────────────────────────────
    "studioneutral": {
        "bg":          "#222222",
        "panel":       "#2c2c2c",
        "panel2":      "#363636",
        "surface":     "#3c3c3c",
        "text":        "#eaeaea",
        "muted":       "#848484",
        "entrybg":     "#282828",
        "entryfg":     "#e0e0e0",
        "tabbg":       "#333333",
        "tabsel":      "#4e4e4e",
        "accent":      "#7abea0",
        "progress":    "#686868",
        "actions":     ["#404040","#4a4a4a","#555555","#606060","#6a6a6a","#757575"],
        "button_fg":   "#f0f0f0",
        "button_hover":"#5a5a5a",
        "scrollbar_bg":"#2c2c2c",
        "scrollbar_fg":"#686868",
        "selected_bg": "#4e4e4e",
        "selected_fg": "#ffffff",
        "border_color":"#444444",
        "separator":   "#363636",
        "success_color":"#80cbc4",
        "error_color": "#ef9a9a",
        "warning_color":"#ffe082",
        "tag_fg":      "#aaaaaa",
        "heading_font_size": 11, "label_font_weight": "normal",
        # Default special effects (disabled)
        "glow_color":   "",
        "glow_intensity": 0,
        "hover_transition": "",
        "focus_color":  "",
        "focus_shape":  "",
        "button_radius": 0,
        "mist_color":   "",
        "mist_alpha":   0,
    },

    # ── Dark Glass ────────────────────────────────────────────────────
    "darkglass": {
        "bg":          "#0e1620",
        "panel":       "#162030",
        "panel2":      "#1e2c3e",
        "surface":     "#243446",
        "text":        "#d8eaf8",
        "muted":       "#6080a0",
        "entrybg":     "#121a26",
        "entryfg":     "#c4dcf0",
        "tabbg":       "#1a2636",
        "tabsel":      "#284060",
        "accent":      "#4899cc",
        "progress":    "#386898",
        "actions":     ["#1e3a5f","#24496e","#2c5880","#346898","#4080b0","#5898c8"],
        "button_fg":   "#e4f2ff",
        "button_hover":"#386898",
        "scrollbar_bg":"#162030",
        "scrollbar_fg":"#386898",
        "selected_bg": "#284060",
        "selected_fg": "#ffffff",
        "border_color":"#223344",
        "separator":   "#1e2c3e",
        "success_color":"#5898c8",
        "error_color": "#e05060",
        "warning_color":"#f0b030",
        "tag_fg":      "#80b8e0",
        "heading_font_size": 11, "label_font_weight": "normal",
        # Default special effects (disabled)
        "glow_color":   "",
        "glow_intensity": 0,
        "hover_transition": "",
        "focus_color":  "",
        "focus_shape":  "",
        "button_radius": 0,
        "mist_color":   "",
        "mist_alpha":   0,
    },

    # ── Deep Ocean — rich navy blue ─────────────────────────────────────
    "oceanbluenew": {
        "bg":          "#0a1628",
        "panel":       "#101e34",
        "panel2":      "#162844",
        "surface":     "#1c3254",
        "text":        "#c8e0ff",
        "muted":       "#5090c0",
        "entrybg":     "#0c1a2e",
        "entryfg":     "#b0d0f0",
        "tabbg":       "#142640",
        "tabsel":      "#1e4a78",
        "accent":      "#38a8e8",
        "progress":    "#2878b0",
        "actions":     ["#0e3a6a","#144880","#1a5898","#2068b0","#2878c8","#3888d8"],
        "button_fg":   "#d8f0ff",
        "button_hover":"#2878b0",
        "scrollbar_bg":"#101e34",
        "scrollbar_fg":"#2878b0",
        "selected_bg": "#1e4a78",
        "selected_fg": "#ffffff",
        "border_color":"#1a3a60",
        "separator":   "#162844",
        "success_color":"#38a8e8",
        "error_color": "#e85060",
        "warning_color":"#f0b830",
        "tag_fg":      "#58b0e8",
        "heading_font_size": 11, "label_font_weight": "normal",
        # Default special effects (disabled)
        "glow_color":   "",
        "glow_intensity": 0,
        "hover_transition": "",
        "focus_color":  "",
        "focus_shape":  "",
        "button_radius": 0,
        "mist_color":   "",
        "mist_alpha":   0,
    },

    # ── Frog Swamp — maximum frog energy ──────────────────────────────────
    "frogswamp": {
        "bg":           "#0a1a08",   # deep swamp black-green
        "panel":        "#0f2610",   # dark lily-pad green
        "panel2":       "#163319",   # slightly lighter swamp
        "surface":      "#1c4020",   # muddy pond surface
        "text":         "#c8f59a",   # poison dart frog chartreuse
        "muted":        "#6abf4b",   # mid frog green
        "entrybg":      "#0c1e0d",   # near-black swamp water
        "entryfg":      "#b8e87a",   # bright leaf green
        "tabbg":        "#122915",   # tab bar swamp
        "tabsel":       "#2d7a1f",   # selected tab — vivid frog belly
        "accent":       "#5dda2a",   # poison dart lime
        "progress":     "#4ab822",   # frog-tongue green
        "actions":      ["#1a5c10","#237a16","#2e9920","#3db82a","#52d035","#6ae845"],
        "button_fg":    "#e8ffd0",   # pale lily pad
        "button_hover": "#3db82a",
        "scrollbar_bg": "#0f2610",
        "scrollbar_fg": "#4ab822",
        "selected_bg":  "#2d7a1f",
        "selected_fg":  "#e8ffd0",
        "border_color": "#1e4d18",   # swamp reed border
        "separator":    "#163319",
        "success_color":"#6ae845",
        "error_color":  "#d94f1e",   # red-eyed treefrog red
        "warning_color":"#f0d020",   # golden poison frog yellow
        "tag_fg":       "#a8f060",   # bright frog-spot green
        "heading_font_size": 11, "label_font_weight": "bold",
        # Special effects for FrogSwamp
        "glow_color":   "#5dda2a",   # bioluminescent glow color
        "glow_intensity": 15,        # glow shadow blur radius
        "hover_transition": "#7ae845", # water ripple hover color
        "focus_color":  "#5dda2a",   # frog-eye focus indicator
        "focus_shape":  "oval",      # frog-eye oval shape
        "button_radius": 8,          # lily pad moderate rounding
        "mist_color":   "#0a1a08",   # mist overlay color
        "mist_alpha":   0.3,         # mist transparency
    },

    # ── Frog Swamp Light — misty morning swamp ─────────────────────────────
    "frogswamp_light": {
        "bg":          "#e8f5e0",   # misty morning swamp
        "panel":       "#d4ebd0",   # light lily pad
        "panel2":      "#c0e0b8",   # lighter swamp green
        "surface":     "#f0f8ec",   # pond surface reflection
        "text":        "#1a3d10",   # deep forest green
        "muted":       "#4a7a35",   # mid swamp green
        "entrybg":     "#f4fcf0",   # near-white water
        "entryfg":     "#1a3d10",   # dark frog green
        "tabbg":       "#c8e0c0",   # tab bar light
        "tabsel":      "#7ab860",   # selected tab — bright frog
        "accent":      "#3d8c20",   # vibrant lime
        "progress":    "#2e7a18",   # frog tongue green
        "actions":     ["#2e7a18","#3d8c20","#4a9c30","#5aac40","#6abc50","#7acc60"],
        "button_fg":   "#1a3d10",
        "button_hover": "#2e7a18",
        "button_hover_fg": "#ffffff",
        "scrollbar_bg":"#d4ebd0",
        "scrollbar_fg":"#3d8c20",
        "selected_bg": "#7ab860",
        "selected_fg": "#ffffff",
        "border_color":"#8ab870",
        "separator":   "#c0e0b8",
        "success_color":"#3d8c20",
        "error_color": "#c0392b",
        "warning_color":"#e6a020",
        "tag_fg":      "#2e7a18",
        "heading_font_size": 11, "label_font_weight": "bold",
        # Special effects for FrogSwamp Light
        "glow_color":   "#3d8c20",   # bioluminescent glow color
        "glow_intensity": 12,        # glow shadow blur radius
        "hover_transition": "#5aac40", # water ripple hover color
        "focus_color":  "#3d8c20",   # frog-eye focus indicator
        "focus_shape":  "oval",      # frog-eye oval shape
        "button_radius": 8,          # lily pad moderate rounding
        "mist_color":   "#e8f5e0",   # mist overlay color
        "mist_alpha":   0.4,         # mist transparency
    },

    # ── Neon Cyber Light — daytime cyberpunk ───────────────────────────────
    "neoncyber_light": {
        "bg":          "#f8f0ff",   # very light lavender background
        "panel":       "#eee0f8",   # light purple panel
        "panel2":      "#e0ccf0",   # medium lavender
        "surface":     "#fcf8ff",   # near-white surface
        "text":        "#1e0838",   # very deep purple text
        "muted":       "#7a48a8",   # readable mid purple
        "entrybg":     "#fefcff",   # near-white entry
        "entryfg":     "#1e0838",   # deep purple text
        "tabbg":       "#e4d4f2",   # tab bar light
        "tabsel":      "#c888e8",   # selected tab — softer purple
        "accent":      "#8828e0",   # vivid purple accent
        "progress":    "#7020c0",   # deep purple progress
        "actions":     ["#6018a0","#7020b8","#8028d0","#9038e0","#a048f0","#b060f8"],
        "button_fg":   "#ffffff",
        "button_hover": "#7020b8",
        "button_hover_fg": "#ffffff",
        "scrollbar_bg":"#eee0f8",
        "scrollbar_fg":"#9038e0",
        "selected_bg": "#d0a0f0",
        "selected_fg": "#1e0838",
        "border_color":"#c8a0d8",
        "separator":   "#e0ccf0",
        "success_color":"#008868",
        "error_color": "#cc2244",
        "warning_color":"#b87800",
        "tag_fg":      "#7020b8",
        "heading_font_size": 12, "label_font_weight": "bold",
        # Default special effects (disabled)
        "glow_color":   "",
        "glow_intensity": 0,
        "hover_transition": "",
        "focus_color":  "",
        "focus_shape":  "",
        "button_radius": 0,
        "mist_color":   "",
        "mist_alpha":   0,
    },

    # ── Warm Paper Dark — candlelight reading ───────────────────────────────
    "warmpaper_dark": {
        "bg":          "#1a1410",   # dark brown background
        "panel":       "#241c14",   # dark brown panel
        "panel2":      "#302420",   # lighter brown
        "surface":     "#3c3028",   # brown surface
        "text":        "#e8d8c0",   # warm beige text
        "muted":       "#a08060",   # mid brown
        "entrybg":     "#201810",   # dark entry
        "entryfg":     "#e0d0b8",   # light beige text
        "tabbg":       "#2c2018",   # tab bar dark
        "tabsel":      "#504030",   # selected tab — brown
        "accent":      "#c08040",   # amber accent
        "progress":    "#a06030",   # brown progress
        "actions":     ["#403020","#504030","#605040","#706050","#807060","#908070"],
        "button_fg":   "#f0e8d8",
        "button_hover": "#a06030",
        "scrollbar_bg":"#241c14",
        "scrollbar_fg":"#a06030",
        "selected_bg": "#504030",
        "selected_fg": "#ffffff",
        "border_color":"#403020",
        "separator":   "#302420",
        "success_color":"#80a040",
        "error_color": "#c04040",
        "warning_color":"#c09030",
        "tag_fg":      "#c08040",
        "heading_font_size": 11, "label_font_weight": "normal",
        # Default special effects (disabled)
        "glow_color":   "",
        "glow_intensity": 0,
        "hover_transition": "",
        "focus_color":  "",
        "focus_shape":  "",
        "button_radius": 0,
        "mist_color":   "",
        "mist_alpha":   0,
    },

    # ── Studio Neutral Light — professional clean ───────────────────────────
    "studioneutral_light": {
        "bg":          "#f0f0f0",   # light gray background
        "panel":       "#e0e0e0",   # light gray panel
        "panel2":      "#d0d0d0",   # lighter gray
        "surface":     "#f8f8f8",   # near-white surface
        "text":        "#202020",   # dark gray text
        "muted":       "#606060",   # mid gray
        "entrybg":     "#fcfcfc",   # near-white entry
        "entryfg":     "#202020",   # dark gray text
        "tabbg":       "#d8d8d8",   # tab bar light
        "tabsel":      "#a0a0a0",   # selected tab — gray
        "accent":      "#508060",   # muted green accent
        "progress":    "#406050",   # green progress
        "actions":     ["#303030","#404040","#505050","#606060","#707070","#808080"],
        "button_fg":   "#202020",
        "button_hover": "#406050",
        "button_hover_fg": "#ffffff",
        "scrollbar_bg":"#e0e0e0",
        "scrollbar_fg":"#406050",
        "selected_bg": "#a0a0a0",
        "selected_fg": "#ffffff",
        "border_color":"#b0b0b0",
        "separator":   "#d0d0d0",
        "success_color":"#406050",
        "error_color": "#c04040",
        "warning_color":"#c08030",
        "tag_fg":      "#406050",
        "heading_font_size": 11, "label_font_weight": "normal",
        # Default special effects (disabled)
        "glow_color":   "",
        "glow_intensity": 0,
        "hover_transition": "",
        "focus_color":  "",
        "focus_shape":  "",
        "button_radius": 0,
        "mist_color":   "",
        "mist_alpha":   0,
    },

    # ── Dark Glass Light — frosted glass daylight ───────────────────────────
    "darkglass_light": {
        "bg":          "#e8f0f8",   # light blue-gray background
        "panel":       "#d0e0f0",   # light blue panel
        "panel2":      "#b8d0e8",   # lighter blue
        "surface":     "#f0f8fc",   # near-white surface
        "text":        "#102030",   # dark blue text
        "muted":       "#406080",   # mid blue
        "entrybg":     "#f4f8fc",   # near-white entry
        "entryfg":     "#102030",   # dark blue text
        "tabbg":       "#c8dce8",   # tab bar light
        "tabsel":      "#80b0d0",   # selected tab — blue
        "accent":      "#2060a0",   # blue accent
        "progress":    "#185090",   # blue progress
        "actions":     ["#104070","#185090","#2060a0","#2870b0","#3080c0","#3890d0"],
        "button_fg":   "#102030",
        "button_hover": "#185090",
        "button_hover_fg": "#ffffff",
        "scrollbar_bg":"#d0e0f0",
        "scrollbar_fg":"#185090",
        "selected_bg": "#80b0d0",
        "selected_fg": "#ffffff",
        "border_color":"#a0c0d8",
        "separator":   "#b8d0e8",
        "success_color":"#185090",
        "error_color": "#c04050",
        "warning_color":"#c08030",
        "tag_fg":      "#2060a0",
        "heading_font_size": 11, "label_font_weight": "normal",
        # Default special effects (disabled)
        "glow_color":   "",
        "glow_intensity": 0,
        "hover_transition": "",
        "focus_color":  "",
        "focus_shape":  "",
        "button_radius": 0,
        "mist_color":   "",
        "mist_alpha":   0,
    },

}



# ── Layout / spacing constants ─────────────────────────────────────────

UI = {

    "small_pad":       5,   # tight inline spacing (icon-to-label, radio buttons)

    "med_pad":        10,   # standard row/column padding

    "large_pad":      16,   # between control groups

    "section_spacing": 20,  # between LabelFrame sections inside a tab

    "card_pad":         6,  # gallery/favorites card outer margin

    "card_inner":       4,  # gallery/favorites card inner padding

    "button_padx":      4,  # horizontal spacing between action buttons

    "tab_padding":    (16, 9),  # ttk.Notebook tab padding (same as style)

    "heading_font":  ("Segoe UI", 11, "bold"),

    "body_font":     ("Segoe UI", 10),

    "small_font":    ("Segoe UI", 9),

    "mono_font":     ("Consolas", 10),

}



THEME_DISPLAY_NAMES = {

    # Forest Greens
    "darkforest":       "🌲 Forest Green — Dark",
    "lightforest":      "🌿 Forest Green — Light",
    "frogswamp":        "🐸 Frog Swamp — Dark",
    "frogswamp_light":  "🐸 Frog Swamp — Light",

    # Ocean Blues
    "oceanbluenew":     "🌊 Ocean Blue — Dark",
    "lightocean":       "💧 Ocean Blue — Light",
    "darkglass":        "🔮 Dark Glass — Dark",
    "darkglass_light":  "🔮 Dark Glass — Light",


    # Warm Tones
    "darksunset":       "🌅 Sunset Ember — Dark",
    "lightsunset":      "🌅 Sunset Ember — Light",
    "warmpaper":        "📜 Warm Paper — Light",
    "warmpaper_dark":   "📜 Warm Paper — Dark",

    # Neon / Cyber
    "neoncyber":        "⚡ Neon Cyber — Dark",
    "neoncyber_light":  "⚡ Neon Cyber — Light",

    # Neutral
    "darkcontrast":     "◼ High Contrast — Dark",
    "lightcontrast":    "◻ High Contrast — Light",
    "studioneutral":    "🎨 Studio Neutral — Dark",
    "studioneutral_light": "🎨 Studio Neutral — Light",

}



THEME_INTERNAL_NAMES = {v: k for k, v in THEME_DISPLAY_NAMES.items()}
