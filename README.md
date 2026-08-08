# FrogPaper

> *A cozy AI wallpaper studio that lives on your desktop.*

**FrogPaper** is a Windows desktop application for generating, curating, and rotating AI-powered wallpapers. Built with Python and Tkinter, it connects to multiple AI image generation providers (Pollinations.ai, Cloudflare Workers AI, HuggingFace) and gives you a complete creative workflow — from structured prompt building with negative prompt presets, to a visual gallery with tagging and style filters, slideshow automation, text overlays, and direct Windows wallpaper integration.

No browser. No server. Just a desktop app and your imagination.

---

## Quick Start

**1. Install & Launch**
```bash
pip install -r requirements.txt
python app.py
```

**2. Configure a Provider**
Open **Settings** (top of sidebar) and pick a provider under **Generation**:
- **Pollinations.ai** — Free, no API key needed. Just select and go.
- **Cloudflare Workers AI** — Free tier. Requires Account ID + API Token.
- **HuggingFace Inference** — Requires a token from huggingface.co.

```bash
# Optional: set HuggingFace token via environment variable
setx HUGGINGFACE_TOKEN hf_your_token_here
```

**3. Generate Your First Wallpaper**
1. Use the sidebar dropdowns to select: Subject, Mode, Lighting, Color Palette, Setting, Atmosphere
2. Click **Generate Image** at the top of the sidebar
3. Browse the result in the center preview
4. Click **Set as Wallpaper** in the gallery panel

> **Note:** The prompt engine warms up in the background after launch. The status bar will show *"Warming up prompt engine..."* and then *"Ready — prompt engine warm."* — first prompt generation is instant once that message appears.

---

## What FrogPaper Does

FrogPaper is a complete wallpaper creation and management studio in a single window:

1. **Build Prompts** — Use the sidebar dropdowns and negative prompt builder to craft prompts
2. **Generate Images** — Send prompts to AI models via Pollinations, Cloudflare, or HuggingFace
3. **Curate Collection** — Browse gallery, favorite images, apply 19 artistic filters, add text overlays, tag and organize
4. **Set & Rotate** — Apply wallpapers instantly or let the slideshow rotate automatically with fullscreen-pause detection

---

## Key Features

| Feature | Description |
|---|---|
| **Three-Column Layout** | Sidebar controls, center preview, right gallery panel — everything visible at once |
| **Sidebar Controls** | 6 structured dropdowns + negative prompt builder, all action buttons at the top |
| **Negative Prompt Builder** | Preset checkboxes with term counts, custom terms, live preview, smart negatives |
| **3 AI Providers** | Pollinations.ai (free), Cloudflare Workers AI (free tier), HuggingFace Inference |
| **Multiple Models** | FLUX.1-Krea-dev, FLUX Realism, FLUX Anime, FLUX 3D, Turbo, SDXL, SD 3.5 Large, custom |
| **Gallery** | 7 views (Gallery, Favorites, Styled, Manual, 16:9, Portrait, Square) with sorting and filtering |
| **Portrait Export** | Bulk export portrait (9:16) images to any destination including SD cards and USB drives |
| **Style Transfer** | 19 local artistic filters: Oil Painting, Cyberpunk Neon, Gouache, Vaporwave, and more |
| **Text Overlay** | Add text to any image with font selection, sizing, color, outline, shadow, and 7 positions |
| **Tag System** | Tag images, filter gallery by tag, manage tags across all views |
| **Slideshow** | Auto-rotate wallpapers on timer (1–60 min) with fullscreen auto-pause and duplicate skipping |
| **Favorites** | Bookmark wallpapers with dedicated slideshow source |
| **Sessions** | Save and restore complete working states with auto-naming |
| **Recipe Library** | Save, load, import, export reusable prompt configurations |
| **13 App Themes** | Full theme system with dark, light, and specialty color schemes |
| **Windows Integration** | Native wallpaper setting, system tray with full controls, minimize-to-tray, startup tasks |
| **Keyboard Shortcuts** | Ctrl+G (Gallery), Ctrl+S (Settings), Ctrl+N (Generate) |

---

## App Layout

### Left Panel — Sidebar

All action buttons sit at the **top** for instant access, followed by a separator, then configuration controls below:

**Action Buttons (top):**
- **Generate Prompt** / **Generate Image** — primary green buttons, side by side
- **Random** / **Cancel** — utility buttons, side by side
- **Settings** — full-width, opens the Settings dialog

**Configuration Dropdowns:**
- **Subject** — What to generate (frog, dragon, owl, cat, 100+ options)
- **Mode** — Artistic style: Stylized, Realistic, Cinematic, Anime, Dark Fantasy, Painterly, Pixel Art, Minimalist, Product Photo, Surreal
- **Lighting** — Light source (neon, volumetric, monitor glow, blacklight, bloom, etc.)
- **Color Palette** — Two side-by-side dropdowns: Color Family (70+ colors) + Color Variation (40+ modifiers)
- **Setting** — Environment/location (120+ options)
- **Atmosphere** — Mood (mist, fog, particles, etc.)

**Negative Prompt Builder:**
- Preset checkboxes with term counts in gray (e.g., "Minimal Clutter (6)")
- Hover a preset to see its description
- Custom terms entry (comma-separated, live-updates)
- Preview text box showing the combined result
- Term counter and Reset button
- Smart Negatives and Keep Subject Literal toggles live in **Settings > Advanced**

### Center Panel — Preview

- **Apply Style** menubutton — 19 filters applied to the current preview image
- **Image Preview** — large display area; double-click for fullscreen view
- **Image details** — filename, resolution, file size below the preview
- **Slideshow countdown** — progress bar showing time until next wallpaper
- **Prompt Preview** — scrollable text widget showing the generated prompt with a Mode badge and Copy button

### Right Panel — My Collection (Gallery)

- **Header** — "My Collection" title with Open Folder and Refresh Gallery buttons
- **Action buttons** — Set as Wallpaper, Save to Favorites, Apply Style, Add Text, Delete, Export Portraits
- **View selector** — 7 radio-button views: Gallery, Favorites, Styled, Manual, 16:9, Portrait, Square
- **Sort dropdown** — Date Newest/Oldest, Name A-Z/Z-A, Size Largest, Resolution Largest
- **Tag filter** — dropdown to filter all views by tag
- **Thumbnail grid** — lazy-rendered cards with fade-in animation; double-click to set as wallpaper

### Settings Window

Opened via the Settings button, **Ctrl+S**, or tray menu. Sections:

| Section | Controls |
|---|---|
| **Appearance** | UI theme (13 themes), dimension preset (16:9 / Portrait / Square) |
| **Generation** | AI provider (Pollinations/Cloudflare/HuggingFace), API tokens, model selection, custom model |
| **Gallery & Slideshow** | Slideshow controls, interval slider (1–60 min), source, order, skip duplicates, fullscreen pause, wallpaper output format (PNG/JPEG/WebP), quality |
| **Window Behavior** | Minimize to tray, run on Windows startup, auto-generate on startup, startup subject |
| **Advanced** | Keep Subject Literal, Smart Negatives, keyword expansion mappings, morning auto-wallpaper scheduler |

---

## AI Providers & Models

### Pollinations.ai (Free — No Key)

| Model | Notes |
|---|---|
| FLUX (Default) | High quality, no account needed |
| FLUX Realism | Photorealistic output |
| FLUX Anime | Anime-optimized |
| FLUX 3D | 3D-render style |
| FLUX CablyAI | Enhanced quality |
| Turbo | Fast generation |

### Cloudflare Workers AI (Free Tier)

| Model | Notes |
|---|---|
| FLUX.1-schnell | Fast generation, free tier |

Requires Account ID and API Token from Cloudflare dashboard.

### HuggingFace Inference

| Model | Hugging Face ID | Notes |
|---|---|---|
| FLUX.1-schnell | `black-forest-labs/FLUX.1-schnell` | Fast, free-credit model |
| FLUX.1-dev | `black-forest-labs/FLUX.1-dev` | High quality; requires Pro |
| FLUX.1-Krea-dev | `black-forest-labs/FLUX.1-Krea-dev` | High quality; recommended |
| SD 3.5 Large | `stabilityai/stable-diffusion-3.5-large` | Requires Pro |
| Custom | *any HF model ID* | Experimental |

> Some models require accepting terms on huggingface.co before API access.

---

## Prompt Modes

| Mode | Aesthetic |
|---|---|
| **Stylized** | Digital illustration — bold shapes, vivid colors |
| **Realistic** | Photorealistic — cinematic lighting, real-world textures |
| **Cinematic** | Cinematic composition — dramatic angles, film-like grading |
| **Anime** | Anime/manga style — cel-shaded, vibrant |
| **Dark Fantasy** | Dark, moody, atmospheric — gothic and ominous |
| **Painterly** | Oil painting aesthetic — visible brushwork, rich texture |
| **Pixel Art** | Retro pixel art — crisp edges, limited palette |
| **Minimalist** | Clean and simple — restrained composition, negative space |
| **Product Photo** | Studio shot — sharp detail, clean neutral background (auto-remapped for living subjects) |
| **Surreal** | Dreamlike — impossible scale and atmosphere |

---

## System Tray

Right-clicking the tray icon gives full app control without opening the window:

| Menu Item | Action |
|---|---|
| **Open FrogPaper** | Restore main window (double-click default) |
| **Open Gallery** | Restore and jump to Gallery tab |
| **Generate Image** | Restore window and generate a new image |
| **Settings** | Open Settings dialog |
| **Next Wallpaper** | Advance to next wallpaper in history |
| **Previous Wallpaper** | Go back in wallpaper history |
| **Random Wallpaper** | Set a random image from your gallery instantly |
| **Start / Pause / Resume Slideshow** | Dynamic label — changes with slideshow state |
| **Stop Slideshow** | Visible only when slideshow is running |
| **About FrogPaper** | Version and info dialog |
| **Quit FrogPaper** | Fully exit the application |

---

## Keyboard Shortcuts

| Shortcut | Action |
|---|---|
| `Ctrl+G` | Switch focus to Gallery |
| `Ctrl+S` | Open Settings |
| `Ctrl+N` | Generate image |
| `Ctrl+Alt+N` | Advance slideshow (global hotkey, requires `keyboard` package) |
| `Escape` | Close settings dialog |

---

## Project Structure

```text
FrogPaper/
├── app.py                  # Main application (UI, layout, events)
├── main.py                 # Entry point
├── settings_tab.py         # Settings window (modal dialog)
├── prompt_tab.py           # Prompt Builder, Quick Build, Recipe Library, Templates
├── gallery_tab.py          # Gallery panel, style transfer, text overlay, tags
├── tray_manager.py         # System tray icon and menu
├── slideshow.py            # Auto-rotation timer and logic
├── session_manager.py      # Session save/load (SQLite + JSON fallback)
├── wallpaper_generator.py  # AI provider integration (Pollinations, Cloudflare, HuggingFace)
├── theme_mixer.py          # Theme/prompt generation engine
├── prompt_builder.py       # Prompt assembly from components
├── prompt_refiner.py       # Prompt optimization
├── prompt_validator.py     # Prompt audit and variable validation
├── keyword_expander.py     # Keyword expansion (NLTK + sentence-transformers)
├── negative_manager.py     # Negative prompt presets, smart negatives, style defaults
├── style_transfer.py       # 19 local artistic filters (OpenCV)
├── template_system.py      # Recipe/template data models
├── gallery_manager.py      # Gallery metadata, tags, folder management
├── database.py             # SQLAlchemy ORM for sessions, favorites, tags
├── icons.py                # Toolbar icon rendering
├── preset_manager.py       # Preset bundle management
├── history_manager.py      # Prompt and wallpaper history tracking
├── utils.py                # Shared utilities; get_app_dir() for EXE-safe paths
├── set_wallpaper.py        # Windows wallpaper API (Win32)
├── convert_icon.py         # Icon conversion utilities
├── export_prompt_pack.py   # Prompt pack export
├── export_frogpaper_for_ai.py  # AI-friendly export
├── daily_runner.py         # Headless daily generation
├── setup_scheduler.py      # Task Scheduler integration
│
├── requirements.txt        # Python dependencies
├── keywords.json           # Thematic keyword bank
├── negative_presets.json   # Negative prompt presets
├── presets.json            # Saved preset bundles
├── recipes.json            # Recipe library
├── templates.json          # Prompt template definitions
├── prompt_library.json     # Saved prompt library
├── gallery_tags.json       # Gallery tag definitions
│
├── run_frogpaper.bat       # Windows launcher
├── build_frogpaper_exe.bat # PyInstaller EXE build script
├── FrogPaper.spec          # PyInstaller spec file
├── build_installer.bat     # Installer build script
├── rotate_wallpaper.bat    # Random rotation script
├── run_daily_runner.bat    # Daily generation launcher
├── ci.yml                  # CI configuration
├── conftest.py             # Pytest configuration
├── test_prompt_builder.py  # Prompt builder tests
├── test_keyword_expander.py # Keyword expander tests
├── test_wallpaper_generator.py # Generator tests
└── sounds/                 # App sound effects
```

### Data Location

User data is stored in `AppData/FrogPaper/` (resolved via `utils.get_app_dir()`):

```text
AppData/FrogPaper/
├── wallpapers/
│   ├── generated/          # AI-generated wallpapers
│   ├── manual/             # Imported images
│   ├── styled/             # Style-filtered outputs
│   └── favorites/          # Bookmarked images
├── logs/
│   ├── prompts_history.json
│   ├── favorites.json
│   ├── presets.json
│   └── sessions.json      # JSON fallback for sessions
├── negative_presets.json   # Negative prompt presets
├── config.json             # All user settings (auto-created)
├── FrogPaper.db            # SQLite database (sessions, favorites, tags)
├── keywords.json           # Thematic keyword bank
├── presets.json            # Saved preset bundles
├── recipes.json            # Recipe library
├── templates.json          # Prompt template definitions
├── prompt_library.json     # Saved prompt library
└── gallery_tags.json       # Gallery tag definitions
```

---

## Changelog

### v1.1.0 - Portrait Export Feature
**New Features:**
- **Portrait Export**: Bulk export all portrait (9:16) images from all folders (generated, manual, styled, favorites)
- **Folder Selection**: Choose export destination including SD cards, USB drives, and any folder location
- **Cross-View Export**: Export button available in all gallery views (Gallery, Favorites, Styled, Manual, 16:9, Portrait, Square)
- **Enhanced UX**: Progress feedback, error handling, and MTP device guidance

**Improvements:**
- Direct copy to selected destination (no intermediate folders)
- Automatic duplicate filename handling
- Enhanced success dialog with transfer instructions
- Fixed view switching to preserve export button visibility

**Technical:**
- Added `get_portrait_images()` to gallery_manager.py
- Added export utilities to utils.py (create_export_folder, copy_images_to_folder, open_folder_in_explorer)
- Updated gallery tab with folder browser dialog integration
- Fixed button repack logic for all gallery views

### v1.0.2 - Gallery & Style System
- Gallery system with 7 views and sorting
- Style transfer with 19 artistic filters
- Text overlay system
- Tag system and metadata management
- Slideshow automation
- Session management
- Recipe library

---

## System Requirements

| Requirement | Minimum | Recommended |
|---|---|---|
| OS | Windows 10 | Windows 11 |
| Python | 3.9 | 3.11+ |
| RAM | 4 GB | 8 GB |
| Storage | 500 MB | 2 GB+ |
| Internet | Required for generation | Stable connection |
| AI Provider account | Pollinations (none) or Cloudflare/HuggingFace token | — |

---

## Installation

### Recommended — Windows Launcher

If you have Python installed, just double-click:

```text
run_frogpaper.bat
```

The batch file handles dependency checks and launches the app automatically.

---

### Manual — Command Prompt or PowerShell

**Step 1 — Install dependencies**
```text
pip install -r requirements.txt
```

**Step 2 — Launch the app**
```text
python app.py
```

> **Note:** Python 3.9 or newer is required. Make sure to check **"Add Python to PATH"** during installation.

---

### Optional — Daily Wallpaper Automation

```text
python setup_scheduler.py
```

> **Run as Administrator** — right-click Command Prompt, then *Run as administrator*. Only needs to be done once.

---

### EXE Build — Standalone Windows Executable

```text
build_frogpaper_exe.bat
```

Produces `dist\\FrogPaper.exe`. The `wallpapers/` folder must sit **beside** the EXE, not inside it. The EXE resolves all paths relative to its own location.

---

## Workflow Guide

### Building Prompts

**Sidebar Method:**
1. Fill the dropdowns: Subject, Mode, Lighting, Color Palette, Setting, Atmosphere
2. Optionally configure negative prompt presets and custom terms
3. Click **Generate Image** at the top of the sidebar

### Managing Images

**Gallery Navigation:**
- Click thumbnails to preview in the center panel
- Double-click any thumbnail to set as wallpaper instantly
- Switch between 7 views: Gallery, Favorites, Styled, Manual, 16:9, Portrait, Square
- Sort by date, name, size, or resolution
- Filter by tag using the tag dropdown

**Favorites:**
- Select image and click **Save to Favorites**
- Favorites appear in the dedicated Favorites view and can be used as a slideshow source

**Style Transfer:**
1. Select an image in Gallery or use **Apply Style** on the center preview
2. Choose from 19 filters (Oil Painting, Cyberpunk Neon, Gouache, etc.)
3. Styled image saves to `wallpapers/styled/` and appears in the Styled view

**Text Overlay:**
1. Select an image and click **Add Text**
2. Enter text, pick a font, adjust size, color, outline, and position
3. Live preview before saving to the Styled view

### Slideshow Setup

1. Go to **Settings > Gallery & Slideshow**
2. Click **Start** to begin the slideshow
3. Set interval (1–60 minutes) with the slider
4. Choose source: Generated, Manual, All Images, Favorites, or Styled
5. Enable **Skip Duplicates** to avoid recent wallpapers
6. Enable **Pause when a full-screen app is active** to auto-pause during games or videos
7. Control from tray: Start/Pause/Resume/Stop, or advance manually with Next/Previous

> The slideshow timer resets automatically whenever you manually change the wallpaper.

---

## Troubleshooting

| Issue | Solution |
|---|---|
| **Generation fails** | Check your provider settings. Pollinations.ai needs no key; Cloudflare needs Account ID + Token; HuggingFace needs a valid token. |
| **403 error (HuggingFace)** | Visit the model page on huggingface.co and accept terms. Some models require Pro. |
| **First prompt feels slow** | Wait for *"Ready — prompt engine warm."* in the status bar. |
| **Slideshow not rotating** | Ensure the source folder has images. For Favorites, add at least one image first. |
| **Wallpaper not changing** | Check the image exists in `wallpapers/generated/`. Verify Windows wallpaper permissions. |
| **EXE shows empty gallery** | Ensure `wallpapers/` and subfolders are beside `FrogPaper.exe`. |
| **System tray icon missing** | Install pystray: `pip install pystray` |
| **Global hotkey not working** | Install keyboard package: `pip install keyboard` |
| **App won't start** | Check Python 3.9+, all dependencies installed (`pip install -r requirements.txt`), and a valid provider configured. |

---

## Privacy

All images are stored locally. Only text prompts are sent to the configured AI provider API. No images, filenames, or personal data are transmitted.

---

## Development Notes

- **Entry point:** `app.py` contains the main UI, layout, and event logic (~6400 lines)
- **Tab modules:** `prompt_tab.py` (Quick Build, Recipes, Templates) and `gallery_tab.py` (Gallery, style transfer, text overlay, tags)
- **Settings:** `settings_tab.py` — modal dialog with 5 sections
- **Theme generation:** `theme_mixer.py` handles prompt construction; keyword caches pre-warm at startup
- **Image generation:** `wallpaper_generator.py` supports 3 providers (Pollinations, Cloudflare, HuggingFace)
- **Prompt engine:** `prompt_builder.py` assembles final prompts with per-mode negatives and subject-aware anatomy constraints
- **Negative system:** `negative_manager.py` manages presets, smart negatives, and style-default negatives
- **Style filters:** `style_transfer.py` uses OpenCV (local processing, no API)
- **Slideshow:** `slideshow.py` manages auto-rotation with fullscreen detection, duplicate skipping, and countdown reset
- **Sessions:** `session_manager.py` with SQLite storage via `database.py` and JSON fallback
- **EXE path resolution:** `utils.get_app_dir()` returns `Path(sys.executable).parent` when frozen, `Path(__file__).parent` otherwise — all modules use this so user data always resolves correctly
- **Icon rendering:** `icons.py` generates themed toolbar icons programmatically
- **Tray:** `tray_manager.py` provides full app control from the system tray with a custom-drawn frog icon

---

*Lily pads optional. Wallpapers mandatory.*
