<img width="1024" height="1024" alt="Gemini_Generated_Image_hpwt4bhpwt4bhpwt" src="https://github.com/user-attachments/assets/9000479d-f5d6-4508-b46f-985b50cd0a2f" />


🎨 Meet Pip, the Chief Curator
Pip is the official mascot of FROGPAPER. While he might look like he’s about to paint a masterpiece with his trusty brush and beret, his real job is making sure your phone and computer screen looks amazing without selling your data. Pip believes in open-source, privacy, and the perfect pixel. Say hi to him in the issues tab! 🐸

# FrogPaper

> *A cozy AI wallpaper studio for your desktop and your phone.*

**FrogPaper** is a two-app wallpaper studio.

- **FrogPaper Desktop — v1.7.6** (Windows 10/11). Built with Python and Tkinter. Connects to 6 AI image generation providers (Pollinations.ai, Cloudflare Workers AI, Hugging Face, Prodia, Replicate, Fal.ai) and gives you a complete creative workflow — structured prompt building with negative prompt presets, a visual gallery with tagging and style filters, slideshow automation, text overlays, and native Windows wallpaper integration.
- **FrogPaper Mobile — v1.12.0** (Android 7.0+). Built with Expo / React Native. Generates phone wallpapers from a prompt or the Build screen, keeps them on the phone, and rotates them as your wallpaper.

No browser. No account. Just the apps and your imagination.

| App | Current version | Platform | Stack |
|---|---|---|---|
| **FrogPaper Desktop** | 1.7.6 | Windows 10 / 11 | Python 3.11+, Tkinter |
| **FrogPaper Mobile** | 1.12.0 | Android 7.0+ | Expo / React Native |

---

## Quick Start — Desktop

**1. Install & Launch**
```bash
pip install -r requirements.txt
python app.py
```

**2. Configure a Provider**
Open **Settings** (top of sidebar) and pick a provider under **Generation**:
- **Pollinations.ai** — Free, no API key needed. Just select and go.
- **Cloudflare Workers AI** — Free tier. Requires Account ID + API Token.
- **Prodia** — Pro account required. API key from app.prodia.com.
- **Replicate** — Pay-per-image (~$0.003/img for FLUX.schnell). API token from replicate.com.
- **Fal.ai** — Pay-per-use, fast inference. API key from fal.ai.
- **Hugging Face Inference** — Requires a token from huggingface.co.

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

**Customize defaults?** See **[CONFIG_GUIDE.md](CONFIG_GUIDE.md)** — what every `config.json` key does, the safe ways to hand-edit, and how to change first-run defaults for a build.

---

## Quick Start — Android

1. Download `FrogPaper-release-signed.apk` from the [latest FrogPaper Mobile release](https://github.com/sunnyskyess420/frogpaper-mobile/releases/latest).
2. Android 7.0 or newer. Allow installs from your browser or file manager when Android asks ("Install unknown apps").
3. Install over an existing FrogPaper install — it uses the same release key (`CN=FrogPaper`), so there is no need to uninstall first.
4. Type a prompt (two words is enough) and tap **Generate**. Optional: open **Build** to assemble a prompt from dropdowns, or add your own Gemini / Hugging Face / Replicate key in **Settings**.

> Generating needs a reachable FrogPaper backend; the app ships pointing at the public one. Your own API keys stay on the phone.

---

## What FrogPaper Does — Desktop

FrogPaper is a complete wallpaper creation and management studio in a single window:

1. **Build Prompts** — Use the sidebar dropdowns and negative prompt builder to craft prompts
2. **Generate Images** — Send prompts to any of the 6 configured providers
3. **Curate Collection** — Browse gallery, favorite images, apply 25 artistic filters, add text overlays, tag and organize
4. **Set & Rotate** — Apply wallpapers instantly or let the slideshow rotate automatically with fullscreen-pause detection

---

## Key Features — Desktop

| Feature | Description |
|---|---|
| **Three-Column Layout** | Sidebar controls, center preview, right gallery panel — everything visible at once |
| **Sidebar Controls** | 6 structured dropdowns + negative prompt builder, all action buttons at the top |
| **Pinned Favorites (★)** | Every dropdown item has a star button — pinned choices rise to a "★ FAVORITES" section at the top of each list; manage them all under Settings > Advanced > Favorite Dropdown Items |
| **Negative Prompt Builder** | Preset checkboxes with term counts, custom terms, live preview, smart negatives |
| **6 AI Providers** | Pollinations.ai (free), Cloudflare Workers AI (free tier), Hugging Face Inference, Prodia, Replicate, Fal.ai |
| **26 Model Presets** | FLUX.1-schnell, FLUX.1-dev, FLUX.dev, FLUX.pro, SDXL 1.0, SDXL Lightning, Animagine XL 3.1, DreamShaper 8, Playground v2.5, plus custom model IDs |
| **Gallery** | 7 views (Gallery, Favorites, Styled, Manual, 16:9, Portrait, Square) with sorting and filtering |
| **Portrait Export** | Bulk export portrait (9:16) images to any destination including SD cards and USB drives |
| **Style Transfer** | 25 local artistic filters: Oil Painting, Cyberpunk Neon, Gouache, Vaporwave, and more |
| **Text Overlay** | Add text to any image with font selection, sizing, color, outline, shadow, 5 quick-position presets and click/drag placement |
| **Tag System** | Tag images, filter gallery by tag, manage tags across all views |
| **Slideshow** | Auto-rotate wallpapers on timer (1–60 min) with fullscreen auto-pause and duplicate skipping |
| **Favorites** | Bookmark wallpapers with dedicated slideshow source |
| **Sessions** | Save and restore complete working states with auto-naming |
| **Recipe Library** | Save, load, import, export reusable prompt configurations |
| **19 App Themes** | Full theme system with dark, light, and specialty color schemes |
| **Windows Integration** | Native wallpaper setting, system tray with full controls, minimize-to-tray, startup tasks |
| **Keyboard Shortcuts** | Ctrl+G (Gallery), Ctrl+S (Settings), Ctrl+N (Generate), Ctrl+Alt+N (next wallpaper) |

---

## Android App (v1.12.0)

FrogPaper Mobile is a separate Android app, not a port of the desktop UI.

- **Bottom tabs** — Home, Generate, Gallery and Settings are one tap apart. Build, Detail, Slideshow and Prompt history open on top, and Back returns to the tab you came from.
- **Generate** — type a prompt, pick one of 7 size presets, set a seed, or roll **Surprise me** (20 curated ideas). A cancel button shows the elapsed time.
- **Build** — assemble a prompt from 10 modes, 16 subjects, 23 styles, 19 lighting options, 19 moods and 10 atmospheres, a free-text setting, recipes with rollable slots and quick negative presets.
- **Engines** — Pollinations (free, no key), Google Gemini, Hugging Face and Replicate. The last three use your own keys, stored on the phone. A locked engine opens the key sheet instead of failing silently.
- **Gallery** — runs from the phone by default. Search by name or prompt, sort, filter favourites, star images, multi-select, and open a full-screen viewer with swipe, pinch-zoom and double-tap. Long-press for set / star / save / share / delete, with a 5-second undo on delete.
- **Detail** — a "Made with" row names the engine that produced the image, read from the filename.
- **Rotation** — `Off` / `Every time I open` / `Once a day`, with `Surprise me`, `My favourites` or `Random from my gallery` as the source. A failed run backs off for 2 hours and names the real retry time.
- **Update prompt** — Home shows a one-time notice when a newer release exists, with "Get update" and "Later".

Android requirements: Android 7.0+ (API 24), roughly 80 MB of storage.

---

## Desktop App Layout

### Left Panel — Sidebar

All action buttons sit at the **top** for instant access, followed by a separator, then configuration controls below:

**Action Buttons (top):**
- **Generate Prompt** / **Generate Image** — primary green buttons, side by side
- **Random** / **Cancel** — utility buttons, side by side
- **Settings** — full-width, opens the Settings dialog

**Configuration Dropdowns:**

Every dropdown item carries a ☆ star button on its row. Click the star to **pin** that choice: pinned items move into a "★ FAVORITES" section at the top of the list and are shown with a ★ prefix when selected, so your go-to subjects and styles are always one click away. Click the star again to unpin. The full favorites manager lives in **Settings > Advanced > Favorite Dropdown Items**.

- **Subject** — What to generate (frog, dragon, owl, cat, 100+ options)
- **Mode** — Artistic style: Stylized, Realistic, Cinematic, Anime, Dark Fantasy, Painterly, Pixel Art, Minimalist, Product Photo, Surreal
- **Lighting** — Light source (neon, volumetric, monitor glow, blacklight, bloom, etc.)
- **Color Palette** — Two side-by-side dropdowns: Color Family (63 colors) + Color Variation (47 modifiers)
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

- **Apply Style** menubutton — 25 filters applied to the current preview image
- **Image Preview** — large display area; double-click for fullscreen view
- **Image details** — filename, resolution, file size below the preview
- **Slideshow countdown** — progress bar showing time until next wallpaper
- **Prompt Preview** — scrollable text widget showing the generated prompt with a Mode badge and Copy button

### Right Panel — My Collection (Gallery)

- **Header** — "My Collection" title with Open Folder and Refresh Gallery buttons
- **Action buttons** — Set as Wallpaper, Save to Favorites, Apply Style, Add Text, Delete, Export Portraits
- **View selector** — 7 radio-button views: Gallery, Favorites, Styled, Manual, 16:9, Portrait, Square
- **Sort dropdown** — Date Newest/Oldest, Name A-Z/Z-A, Size Largest/Smallest, Resolution Largest/Smallest
- **Tag filter** — dropdown to filter all views by tag
- **Thumbnail grid** — lazy-rendered cards with fade-in animation; double-click to set as wallpaper

### Settings Window

Opened via the Settings button, **Ctrl+S**, or tray menu. Opens in a resizable window with a **sidebar navigation** on the left and card-based sections on the right. Changes are staged with a sticky **Save Settings** bar at the bottom (an "Unsaved changes" indicator appears as you edit), and the whole window re-colors live if you switch themes while it is open:

| Category | Cards & Controls |
|---|---|
| **General** | App theme (19 themes), wallpaper resolution preset (16:9 / Portrait / Square) |
| **Generation** | AI provider (Pollinations/Cloudflare/HuggingFace), API tokens, Cloudflare Account ID, model selection + custom model |
| **Appearance** | Wallpaper output format (PNG/JPEG/WebP), JPEG quality |
| **Startup** | Run on Windows startup, auto-generate on launch + startup subject, system tray behavior |
| **Slideshow** | Slideshow enable + interval slider (1–60 min), fullscreen auto-pause, source & order, skip duplicates |
| **Cloud & Backup** | Google Drive / OneDrive / Dropbox connection cards — each with credential fields and a built-in "How to get your credentials" guide that is **expanded by default** with **clickable website links** (opens in your browser); auto-backup schedule; **Restore from Cloud / Restore from Folder** with a dry-run preview, conflict policies and tag import |
| **Advanced** | Generation behavior (Smart Negatives, Keep subject exact), keyword expansion mappings, **Favorite Dropdown Items** manager, morning auto-wallpaper scheduler |
| **Help** | Built-in tutorials (Quick Start, Feature Tour, Interactive Practice, Model Setup) and help resources |

---

## AI Providers & Models (Desktop)

All six providers are selectable under **Settings > Generation**, each with its own key field and setup guide.

### Pollinations.ai (Free — No Key)

| Model | Notes |
|---|---|
| FLUX (Default) | High quality, no account needed |
| FLUX Realism | Photorealistic output |
| FLUX Anime | Anime-optimized |
| FLUX 3D | 3D-render style |
| FLUX CablyAI | Enhanced quality |
| Turbo (Fast) | Fast generation |

### Cloudflare Workers AI (Free Tier)

| Model | Notes |
|---|---|
| FLUX.1-schnell (Fast - Free) | Fast generation, free tier |

Requires Account ID and API Token from the Cloudflare dashboard.

### Hugging Face Inference

| Model | Notes |
|---|---|
| FLUX.1-schnell (Fast - Free) | Fast, free-credit model |
| FLUX.1-dev (Higher Quality - Free Credits) | High quality |
| Custom... | Any Hugging Face model ID |

Requires a token from huggingface.co. Some models require accepting terms on the model page before API access.

### Prodia (Pro Account)

| Model | Notes |
|---|---|
| FLUX.schnell (Fast - Free) | Fast generation |
| FLUX.dev (Higher Quality) | Higher quality |
| FLUX.1-fill (Inpainting) | Inpainting |
| SDXL 1.0 | Stable Diffusion XL |
| SDXL Lightning (Fast) | Fast SDXL |
| Animagine XL 3.1 (Anime) | Anime-optimized |
| DreamShaper 8 | Stylized SD |

Pro account required; API key from app.prodia.com.

### Replicate (Pay-Per-Image)

| Model | Notes |
|---|---|
| FLUX.schnell (Fast - $0.003/img) | Fast and cheap |
| FLUX.dev (Quality - $0.025/img) | Higher quality |
| FLUX.pro (Best - $0.04/img) | Best quality |
| SDXL 1.0 | Stable Diffusion XL |
| SDXL Lightning (Fast) | Fast SDXL |

API token from replicate.com.

### Fal.ai (Fast Inference)

| Model | Notes |
|---|---|
| FLUX.schnell (Fast) | Fastest inference |
| FLUX.dev (Quality) | Higher quality |
| FLUX.pro (Best) | Best quality |
| SDXL 1.0 | Stable Diffusion XL |
| Playground v2.5 | Playground model |

API key from fal.ai.

---

## Prompt Modes (Desktop)

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

## System Tray (Desktop)

Right-clicking the tray icon gives full app control without opening the window:

| Menu Item | Action |
|---|---|
| **Open FrogPaper** | Restore main window (double-click default) |
| **Open Folder** | Open the wallpapers folder in Explorer |
| **Settings** | Open Settings dialog |
| **Tutorials** | Open the built-in tutorials |
| **Next Wallpaper** | Advance to next wallpaper in history |
| **Previous Wallpaper** | Go back in wallpaper history |
| **Random Wallpaper** | Set a random image from your gallery instantly |
| **Start / Pause / Resume Slideshow** | Dynamic label — changes with slideshow state |
| **Stop Slideshow** | Visible only when slideshow is running |
| **About FrogPaper** | Version and info dialog |
| **Quit FrogPaper** | Fully exit the application |

---

## Keyboard Shortcuts (Desktop)

| Shortcut | Action |
|---|---|
| `Ctrl+G` | Switch focus to Gallery |
| `Ctrl+S` | Open Settings |
| `Ctrl+N` | Generate image |
| `Ctrl+Alt+N` | Advance slideshow (global hotkey, requires `keyboard` package) |
| `Escape` | Close Settings; otherwise show the shortcut hint toast |

---

## Project Structure

```text
FrogPaper/
├── app.py                      # Main window, layout, events (~2,700 lines)
├── main.py                     # Entry point
├── app_paths.py                # Filesystem layout constants (BASE_DIR, logs, wallpaper dirs)
├── app_prompt_data.py          # Dropdown option banks, modes, provider/model tables
├── app_themes.py               # 19 theme palettes
├── app_theme_engine.py         # apply_theme() and themed-widget generation
├── app_generation_mixin.py     # Generate / regenerate pipeline
├── app_cloud_mixin.py          # Cloud sync, backup and startup-registry methods
├── app_system_mixin.py         # Tray, wallpaper and system integration
├── app_delegates_mixin.py      # Delegate helpers for tabs and dialogs
├── app_runtime.py              # Runtime bootstrap helpers
│
├── prompt_tab.py               # Prompt Builder, Quick Build, Recipe Library, Templates
├── gallery_tab.py              # Gallery views, style transfer, text overlay, tags
├── settings_tab.py             # Settings window shell with sidebar navigation
├── settings_categories.py      # Builders for the 8 settings categories
├── settings_components.py      # Reusable settings UI primitives
├── settings_providers.py       # Provider selection and API-key fields
├── settings_persistence.py     # Save / load settings
├── settings_slideshow.py       # Slideshow settings card
├── settings_ux_data.py         # Provider and cloud setup guides
│
├── tray_manager.py             # System tray icon and menu
├── slideshow.py                # Auto-rotation timer and logic
├── session_manager.py          # Session save/load (SQLite + JSON fallback)
├── database.py                 # SQLAlchemy ORM for sessions, favorites, tags
├── history_manager.py          # Prompt and wallpaper history
│
├── wallpaper_generator.py      # 6 AI provider backends
├── prompt_builder.py           # Prompt assembly from components
├── prompt_refiner.py           # Prompt optimization
├── prompt_validator.py         # Prompt audit and variable validation
├── prompt_library.py           # Saved prompt library
├── keyword_expander.py         # Keyword expansion (NLTK + sentence-transformers)
├── negative_manager.py         # Negative presets, smart negatives, style defaults
├── theme_mixer.py              # Theme/prompt generation engine
├── style_transfer.py           # 25 local artistic filters (OpenCV + Pillow)
│
├── gallery_manager.py          # Gallery metadata, tags, folder management
├── template_system.py          # Recipe/template data models
├── preset_manager.py           # Preset bundle management
│
├── cloud_providers.py          # Google Drive / OneDrive / Dropbox OAuth + API
├── cloud_catalog.py            # Read-only view of the cloud backup tree
├── cloud_restore.py            # Restore planner (de-duplication, conflicts)
├── restore_ui.py               # Restore preview / confirmation dialog
├── backup_manifest.py          # Portable backup metadata
├── sync_manager.py             # Delta sync engine
├── file_watcher.py             # watchdog file monitoring
├── update_checker.py           # GitHub release check + installer download
│
├── icons.py                    # Toolbar icon rendering
├── rounded_widgets.py          # Themed rounded-corner widget images
├── ui_effects.py               # Gradients, rounded corners, visual polish
├── sv_ttk_fix.py               # Recolors sv_ttk sprite images per theme
├── pinned_dropdowns.py         # Dropdown widget with pinned favourites
├── tutorial_manager.py         # Built-in tutorials
├── thread_manager.py           # Background thread/queue management
├── theme.py                    # Shared visual constants
├── utils.py                    # Shared utilities; get_app_dir() for EXE-safe paths
├── set_wallpaper.py            # Windows wallpaper API (Win32)
│
├── daily_runner.py             # Headless daily generation
├── setup_scheduler.py          # Task Scheduler integration
├── prebuild_check.py           # Secret scan run before PyInstaller
│
├── requirements.txt
├── config.template.json        # Clean first-run defaults
├── keywords.json               # Thematic keyword bank
├── negative_presets.json       # Negative prompt presets
├── presets.json                # Saved preset bundles
├── recipes.json                # Recipe library
├── templates.json              # Prompt template definitions
├── prompt_library.json         # Saved prompt library
├── custom_negatives.json       # User-added negative terms
├── user_thesaurus.json         # User keyword mappings
│
├── run_frogpaper.bat
├── build_frogpaper_exe.bat
├── build_installer.bat
├── FrogPaper.spec
├── rotate_wallpaper.bat
├── run_daily_runner.bat
│
├── .github/workflows/tests.yml # CI: full pytest suite on a Windows runner
├── tests/                      # 28 pytest modules (incl. test_prompt_builder.py,
│                               #   test_keyword_expander.py, cloud / restore / UI tests)
└── sounds/                     # App sound effects
```

### Data Location

User data lives **beside the app**, not in `AppData`. `utils.get_app_dir()` returns the folder containing `app.py` when running from source, or the folder containing `FrogPaper.exe` when frozen:

```text
FrogPaper/                    # or the folder holding FrogPaper.exe
├── wallpapers/
│   ├── generated/            # AI-generated wallpapers
│   ├── manual/               # Imported images
│   ├── styled/               # Style-filtered outputs
│   └── favorites/            # Bookmarked images
├── logs/
│   ├── prompts_history.json
│   ├── favorites.json
│   ├── presets.json
│   └── sessions.json         # JSON fallback for sessions
├── recipes/                  # Saved recipes
├── templates/                # Saved templates
├── negative_presets.json     # Negative prompt presets
├── config.json               # All user settings (auto-created) — see CONFIG_GUIDE.md
├── config.template.json      # Clean first-run defaults seeded to config.json
├── FrogPaper.db              # SQLite database (sessions, favorites, tags)
├── keywords.json             # Thematic keyword bank
├── presets.json              # Saved preset bundles
├── recipes.json              # Recipe library
├── templates.json            # Prompt template definitions
├── prompt_library.json       # Saved prompt library
└── custom_negatives.json     # User-added negative terms
```

---

## Android Releases

### v1.12.0 — Bottom tabs and honest rotation
- Home, Generate, Gallery and Settings are bottom tabs instead of a deep back stack. Build, Detail, Slideshow and Prompt history still open on top.
- A one-time update prompt on Home, with "Get update" and "Later".
- The detail screen shows a "Made with" row naming the engine that produced the image, read from the filename.
- A failed automatic wallpaper names the real retry time, and Settings > Wallpaper keeps a "Last automatic change" record that survives a restart.
- Locked engines open the key sheet instead of swallowing the tap.

### v1.11.2 — Engine-aware automatic wallpapers
- "Once a day" / "Every time I open" with "Surprise me" now generate through the engine saved on the Generate screen.
- No silent Pollinations downgrade: if the saved engine is unavailable the run is skipped and the normal 2-hour cooldown applies.

### v1.11.0 — Halloween Edition
- Halloween theme: pumpkin orange on a haunted purple night.
- Full file name on the image screen, palette check via `npm run check:theme`.

Earlier Android releases: see the [frogpaper-mobile releases](https://github.com/sunnyskyess420/frogpaper-mobile/releases).

---

## Desktop Changelog

### v1.7.6 - Security Release (Pillow 13, NLTK 3.10.4)

**Security fixes:**
- Upgraded Pillow 12.3.0 -> 13.0.0. This resolves the 2026-10 Dependabot advisory wave affecting FrogPaper's image-processing paths (gallery thumbnails, provider downloads, cloud-restored images, style transfer, tray icon), including CVE-2026-96639 (multi-frame loader stale native image storage), CVE-2026-112403 (JPEG decoder heap buffer overflow), CVE-2026-112406 (PDF rewrite infinite loop), and the bundled-libopenjp2 heap overflow reachable from `Image.open().load()`.
- Upgraded NLTK 3.10.3 -> 3.10.4 (the first NLTK release with no known security issues per the Snyk advisory database). NLTK is excluded from the packaged Windows EXE; this pin matters for source/dev installs and CI.
- Bumped declared Python minimum from 3.10 to 3.11. Pillow 13 dropped Python 3.10 support; FrogPaper's CI already tested only 3.11/3.12.

**Build process:**
- `build_frogpaper_exe.bat` now creates a clean `venv` from `requirements.txt` before invoking PyInstaller. This makes the build reproducible from the manifest instead of relying on whatever Python environment happens to be on the developer's machine.
- Consolidated duplicate entries in `requirements.txt` (Pillow, opencv-python, huggingface-hub, keyring, sqlalchemy, pystray, keyboard). OpenCV stays pinned at 4.8.1.78 deliberately; do not bump it without testing `style_transfer.py` filters and gallery previews on Windows.

---

### v1.7.5 - Style Filters and Text Overlay Restored

**Fixes:**
- Applying a style (Comic Book, Watercolor, and the rest) failed with "Could not apply style" because the bundled OpenCV was built for NumPy 1.x while the app shipped NumPy 2.x. The build now uses a NumPy 2-compatible OpenCV.
- Text overlay failed with "The image file may be corrupted" for the same root cause: the module imported OpenCV and PIL in one block, so OpenCV's failure also disabled PIL. The two are probed separately now, and text overlay works even if OpenCV is unavailable.
- Neither dialog blames your image file any more when the real problem is a missing library.

**Under the Hood:**
- `style_transfer.py`: separate `CV2_AVAILABLE` / `PIL_AVAILABLE` probes; `STYLE_TRANSFER_AVAILABLE` requires both for filters, while text overlay only needs PIL.
- Build environment: opencv-python 4.8.1.78 -> 4.14.0.94 (NumPy 2 compatible). Verified by applying `comic_book` and a text overlay to a test image before building.

---

### v1.7.4 - About Window Refresh

**Fixes:**
- The About window (tray right-click -> About FrogPaper) no longer advertises v1.7.0. It now lists the last three releases, and the version line underneath is always the build you are running.
- No functional changes; this is a wording release.

**Under the Hood:**
- `RELEASE_HIGHLIGHTS` in `app.py` replaces the hardcoded paragraph, so future releases update one tuple instead of a sentence buried in the dialog.

---

### v1.7.3 - No More Duplicate Restores

**Cloud Restore:**
- **Restoring no longer duplicates your gallery.** If a backup stored the same picture under both Generated and Manual, restore used to write a second local copy, so every image appeared twice.
- **The planner now checks content, not just filenames.** Before writing anything, it compares the backup against the images already in your gallery and skips a file whose bytes are already there under another folder.
- **Favorites and Styled still restore normally** - they are separate views, not duplicates.

**Under the Hood:**
- `cloud_restore.py` gained `_gallery_index()` and `_find_identical_image()`: a size-based pre-filter, then a hash check using the backup's own algorithm (SHA-256, MD5, SHA-1 or Dropbox content hash).
- Added tests covering cross-folder de-duplication and confirming Favorites copies are still restored.

---

### v1.7.2 - Backups you can actually restore

**Cloud Backup:**
- **Restoring from Google Drive now brings back every wallpaper.** A backup used to skip any image whose recorded cloud copy had been replaced - by a rename, a reinstall, or an upload from an older install - so a restore quietly returned only part of the library.
- **The app now checks its records against what is really in the folder**, re-uploads anything missing, and repoints entries at the copy that actually exists.
- **"Check backup..." downloads a sample** to prove the backup is readable before you rely on it.

**Under the Hood:**
- `sync_manager.py` `_reconcile_remote_ids()` runs before hash comparison: it drops ids with no file behind them, repoints ids at the real copy, and leaves ids alone when a provider cannot be listed.
- `_detect_changes()` counts a file as backed up only when it has a remote id for a provider connected in that run.
- Added `tests/test_sync_remote_ids.py` and `tests/test_drive_upload_dedupe.py`.

---

### v1.7.1 - New Circular Sidebar Logo

**Visual:**
- Replaced the rectangular sidebar logo with a new circular enamel-pin-style badge featuring the frog mascot, beret, and rainbow paintbrush. The "FrogPaper" wordmark is now arched around the top of the circle, with "AI WALLPAPER STUDIO" on a gold ribbon at the bottom.
- Sidebar sizing adjusted so the circle has comfortable breathing room on both sides instead of stretching edge-to-edge.
- The transparent background of the new logo means it automatically picks up each theme's panel color — no per-theme variants needed.

**Under the Hood:**
- `app.py` `build_ui()` logo resize logic simplified from proportional-rectangle to fixed-square.
- Bumped `APP_VERSION`, `build_installer.bat` `AppVersion` and `OutputBaseFilename` to 1.7.1.

---

### v1.7.0 - Halloween Edition
**New Features:**
- **🎃 Halloween theme** (Settings > General > App Theme): pumpkin orange on a haunted night - deep purple panels, bone-white text, pumpkin-glow button borders, candle focus indicators, rounded pumpkin buttons, and a ghost-fog overlay in dialogs.
- **Theme-only popup sound**: while the Halloween theme is active, popups play a ghost-attack sound (`sounds/halloween-ghost-attack.mp3`) instead of the frog ribbit. Every other theme keeps the ribbit, and a missing sound file falls back to it automatically.
- **Halloween startup subject**: this edition pre-fills the startup subject with "Halloween", so auto-generate greets the season on every launch. Change or clear it any time in Settings > Startup - a deliberate edition default, and v1.8 returns to the blank default.
- **One-click updates**: the "Update Available" popup now offers **Install Update** — FrogPaper downloads the installer straight from the GitHub release and launches it for you. No more opening GitHub, hunting for the file, and running it by hand.
- **Live download progress**: a themed, cancellable progress window shows the download percentage and size while the installer is fetched from GitHub.
- **Graceful fallback**: if the release has no direct installer asset, or the download fails, FrogPaper warns you and opens the download page in your browser instead.

**Under the Hood:**
- `THEME_POPUP_SOUNDS` in `app_themes.py` maps themes to their popup sound files; `ThemedDialog._popup_sound_path()` resolves the audio per popup, so switching themes takes effect immediately.
- `update_checker.py` gained `download_installer()` (streaming download with progress/cancel), `UpdateProgressWindow`, and `spawn_installer_after_exit()` — a detached helper waits for FrogPaper to exit before starting the installer, so it can replace the running EXE without a "file in use" prompt.
- `ThemedDialog._show()` accepts an optional `primary` button label (styled as the primary action and bound to Enter); default behaviour is unchanged.
- Added `tests/test_theme_popup_sounds.py` (theme registration, full token set, sound mapping and fallbacks) and `tests/test_update_checker.py` (version/URL parsing, release asset selection, streaming download, launch handoff and notification orchestration).

---

### v1.6.1 - Multi-Select Tagging Fixes
**Multi-Select Tagging:**
- **Multi-select tagging in every view** - Ctrl+click to pick several images at once (Gallery, Favorites, Manual and Styled views), then tag them all in one go.
- **Fixed tagging the wrong image** - after switching views, tagging now targets what you actually selected (before it could silently re-tag an old gallery selection).
- **Clearer button** - it now says "Tag 3 Images" (or however many you picked), so you always know what a click will do.
- **Fresh selection per view** - switching views starts a clean selection; a plain click resets the multi-selection.

**Under the Hood:**
- 307 automated tests (added gallery multi-select regression tests; the test suite no longer touches your real config.json)

---

### v1.6.0 - Visual Refresh
**Look & Feel:**
- **Visual Refresh across all 18 themes**: new palette tokens (elevated surfaces, muted text, stronger borders) extended to every dark and light theme, harmonized control surfaces, refined buttons/tabs/cards, and spacing & type polish throughout
- **No more startup theme flash**: the window is now built and fully themed while hidden, then appears - instead of visibly switching from raw system colours to your chosen theme mid-load

**Fixes:**
- **Mouse-wheel scrolling fixed everywhere**: the gallery, sidebar and prompt preview worked, and now the Settings window, tutorial windows and other dialogs scroll too - wheel events are routed to the page under the pointer, and pinned dropdowns keep their own scrolling
- **Popups stay keyboard-friendly**: dropdown popups no longer dismiss while navigating their rows with the keyboard

**Frog Sneak & Transparency:**
- **Hard-coded frog bias removed**: earlier builds could add a frog cameo to blank-subject images through a hard-coded bias in the theme engine. That code has been removed - nothing in the app forces frogs anymore.
- **Frogs are now fully user-controlled**: a dropdown in Settings > Generation ("Frog sneak") sets how often a frog may sneak into blank-subject random runs - `off`, `rare` (~5%), `classic` (~12%, default) or `party` (~50%). Choose `off` for never; daily runs vary within your setting.

**Under the Hood:**
- 304 automated tests (added gallery-scroll and dialog-scroll regression tests; the test suite no longer touches your real config.json)
- Dependency security bumps (nltk 3.10.3 clears most Dependabot alerts; pillow, opencv-python, sentence-transformers, huggingface-hub updated)
- `FrogPaper.spec` and `build_installer.bat` file lists now match the post-cleanup file set

---

### v1.5.0 - Quality Release (Performance, Accessibility, Resilience)
**Speed:**
- **Gallery views open instantly**: Favorites, Styled, and Manual views no longer decode a thumbnail for every item on the UI thread — cards appear with placeholders and thumbnails decode in one background worker (cache hits render immediately)
- **Instant resolution sorts**: image dimensions are memoized per path, so sorting by size pays the header read once and is instant afterwards
- **Debounced resizing**: Favorites/Styled/Manual re-grid on an 80 ms debounce instead of on every Configure event

**Reliability:**
- **Tags N+1 eliminated**: tag lookups are cached per image and automatically invalidated before every tag write (save, add, remove, rename, delete, cleanup), so views no longer open a database session per image
- **Friendly file-error dialogs**: gallery delete/move failures and unreadable data files now explain what happened instead of crashing (gallery/history I/O wrapped with safe fallbacks)
- **Prompt engine correctness**: `expand_text` preserves your capitalization on words it doesn't expand, and thesaurus mapping edits now invalidate the expansion cache immediately (no restart needed)

**Accessibility:**
- **Full keyboard navigation**: custom buttons and dropdown popups are reachable via Tab and activated with Enter/Space, with visible focus rings that adapt to the theme
- **Tab-trap fixed**: Tab no longer gets permanently stuck inside the negative-prompt Preview or any other text box (trade-off: literal tab characters can no longer be typed into text fields)
- **High-DPI popups**: dropdown popup width auto-fits the longest item instead of clipping at large font sizes

**Technical:**
- 296 automated tests (unit + UI integration) — up from 84 at v1.4.1
- GitHub Actions workflow (`.github/workflows/tests.yml`) runs the full suite on a Windows runner on every push
- New `CONFIG_GUIDE.md` documenting every config.json key; README points to it
- `build_installer.bat` / `APP_VERSION` aligned at 1.5.0

---

### v1.4.1 - Gallery Scroll Fix
**Fixes:**
- **Gallery scroll clamped after switching views**: Switching from a ratio view (16:9, 9:16, 1:1) or any other gallery tab back to the main Gallery view caused the scrollbar to stop working past ~6 images. The ratio view's empty-state code locked the canvas inner-frame height to the viewport size, and `load_gallery()` only reset the width — not the height — when rebuilding. Fixed by resetting `height=0` (Tk uses the widget's natural height) and clearing stale placeholder references from `_gallery_placeholders` when a ratio view takes over the shared canvas.

---

### v1.4.0 - Multi-Provider Generation, Dynamic Setup UI, Resolution Freedom
**New Features:**
- **3 New AI Providers**: Added Replicate, Prodia, and Fal.ai backends alongside existing Pollinations, Cloudflare, and HuggingFace — 6 providers total
- **Dynamic Provider Setup UI**: Switching providers in Settings now dynamically shows only that provider's API key field and step-by-step setup guide
- **Universal Resolution Auto-Resize**: Providers that only output 1024x1024 (like Cloudflare FLUX and Replicate FLUX) are automatically resized to your chosen resolution via Pillow LANCZOS

**Improvements:**
- **Faster Replicate Generation**: Replaced slow `Prefer: wait` long-poll with aggressive 1-second polling — generation time dropped from ~65 seconds to ~7–12 seconds
- **Dimension Presets Now Persist**: Changing the resolution preset (1920x1080, 1080x1920, 1024x1024) now correctly saves to config.json
- **Provider Setup Guides**: Each provider shows clickable setup instructions directly in Settings (where to find your Account ID, API token, etc.)

**Technical:**
- `AI_PROVIDER_UX` dictionary in `settings_tab.py` drives dynamic provider setup UI
- `_rebuild_provider_setup()` creates/destroys provider-specific fields on switch
- Universal post-generation resize safety net in `generate_image()` dispatcher checks actual image dimensions and resizes if needed
- Replicate uses model-based endpoint `/v1/models/{owner}/{name}/predictions` (no version hash required)
- Removed dead `save_scheduler_settings_to_config` import that produced spurious warnings

**Fixes:**
- Images now respect the chosen resolution preset instead of always coming out square
- Replicate generation no longer takes 60+ seconds due to `Prefer: wait` overhead
- Dimension preset changes no longer silently fail to save to config
- Fixed spurious "Failed to save scheduler settings" warning on every settings save

---

### v1.3.2 - Safer Builds, Smarter Updates, Pinned Favorites
**New Features:**
- **Pinned Favorites in Dropdowns**: Star your favorite subjects, styles, lighting, moods, and color families for quick access from the prompt builder
- **"Skip This Version" Button**: When an update notification appears, users can skip a specific release and won't be nagged again until an even newer version ships

**Improvements:**
- **Redesigned Settings Page**: The entire settings experience has been rebuilt with a sidebar-navigation layout and card-based sections. Each setting group (Generation, Cloud Storage, Slideshow, Scheduler, etc.) now lives in its own collapsible card with status badges, consistent label/control rows, and inline help resources. The result is a cleaner, more premium-feeling settings page that scales better as new options are added
- **Update Checker Fixed**: The "Update Available" popup no longer appears on every launch when the app is already up-to-date. The previous release reported the wrong internal version, causing a false-positive update prompt on every start — this is now resolved
- **Safer Credential Handling**: API tokens and OAuth secrets are no longer bundled into the EXE at build time. A clean `config.template.json` is bundled instead and seeded to `config.json` beside the EXE on first launch. Existing users' configs are never overwritten
- **Pre-build Secret Check**: The build pipeline now runs `prebuild_check.py` before PyInstaller packs the EXE. If any non-empty secret is detected in `config.json` or `config.template.json`, the build aborts with exit code 2 — no EXE is produced

**Technical:**
- New `settings_components.py` module providing reusable UI primitives: `StatusBadge`, `SettingRow`, `SettingCard`, `ExpandableSection`, `HelpResourceCard`, `SidebarNav`, `CloudProviderCard`
- `settings_tab.py` rewritten around the new component system with sidebar navigation
- Removed `config.json` from `FrogPaper.spec` `datas=[...]`; replaced with `config.template.json`
- `utils.seed_bundled_files()` now seeds `config.json` from the bundled template on first launch
- `build_installer.bat` ships `config.template.json` renamed to `config.json` with `onlyifdoesntexist` flag
- Added `prebuild_check.py` as a pre-build gate (scans for `hf_…`, `GOCSPX-…`, `AIza…`, `ya29.`, Dropbox `sl.`, and other suspicious patterns)
- Bumped `APP_VERSION` to `1.4.1` to align with installer and GitHub release tag
- Added `SECURITY_NOTES.md` documenting the secure build flow and key-rotation procedure
- `update_checker.py` persists `skipped_update_version` in `config.json` so the skip choice survives across launches

**Fixes:**
- **Theme rendering repaired**: A sprite-naming bug left 9 themed controls (scrollbars, arrows, empty states) permanently baked grey in every theme; all 93 sprites now render with the active theme's colors, and classic widgets no longer flip back to grey after a theme switch
- **Button text contrast engine**: Button label colors are now validated against their real painted background (WCAG) at theme-apply time — fixes invisible white-on-light text on the Neon Cyber Light theme and prevents the same class of bug in any future theme; dark themes are byte-identical to before
- **Pinned-favorites popup crash**: Opening a pinned dropdown popup under certain themes could raise `unknown color name` — fixed
- **Settings usability**: The Settings window is larger (980×700); cloud setup guides now word-wrap to the full card width, auto-size to show every step without inner scrolling, start expanded, and render all website references (including bare domains like `dash.cloudflare.com`) as clickable links that open in the default browser — the same clickable-link treatment applies to website mentions inside the Tutorials window

### v1.2.0 - Cloud Sync Integration
**New Features:**
- **Cloud Storage Integration**: Full OAuth support for Google Drive, OneDrive, and Dropbox
- **Automatic Sync**: Real-time file monitoring triggers automatic cloud sync when images are added, modified, or deleted
- **Sync Manager**: Delta sync engine with conflict resolution and favorites protection
- **OAuth Credential Management**: Secure cloud provider authentication via system credential manager
- **Cloud Provider UI**: Dedicated setup cards with step-by-step OAuth configuration guides

**Improvements:**
- Enhanced update checker with better markdown formatting and smarter release note truncation
- Improved tag system with style suffix handling for better tag fallback on styled images
- Better thread management for gallery operations with stale thread cancellation
- Added proper logging configuration with INFO level
- Removed NLTK dependency (no longer needed)

**Technical:**
- Added `cloud_providers.py` for OAuth and API integration
- Added `sync_manager.py` for cloud sync engine with delta sync
- Added `file_watcher.py` for real-time file system monitoring
- Enhanced `update_checker.py` with comprehensive markdown cleaning
- Updated `settings_tab.py` with cloud provider connection cards
- Added cloud provider dependencies: google-api-python-client, google-auth-oauthlib, msal, dropbox, watchdog

### v1.1.1 - Update Checker
**New Features:**
- Background update check on app startup
- Themed popup notification when a newer version is found
- One-click download link to the latest release
- Completely silent when app is up-to-date

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

### Desktop (v1.7.6)

| Requirement | Minimum | Recommended |
|---|---|---|
| OS | Windows 10 | Windows 11 |
| Python | 3.11 | 3.12+ |
| RAM | 4 GB | 8 GB |
| Storage | 500 MB | 2 GB+ |
| Internet | Required for generation | Stable connection |
| AI provider account | Pollinations (none), or a key for Cloudflare / Hugging Face / Prodia / Replicate / Fal.ai | — |

### Android (v1.12.0)

| Requirement | Minimum |
|---|---|
| OS | Android 7.0 (API 24) |
| Storage | ~80 MB |
| Internet | Required for generation |
| Account | None; optional own Gemini / Hugging Face / Replicate key |

---

## Installation — Desktop

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

> **Note:** Python 3.11 or newer is required (the code uses `X | None` type unions, and Pillow 13 dropped Python 3.10 support). Make sure to check **"Add Python to PATH"** during installation.

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

Produces `dist\FrogPaper.exe`. The `wallpapers/` folder must sit **beside** the EXE, not inside it. The EXE resolves all paths relative to its own location.

---

## Workflow Guide — Desktop

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
2. Choose from 25 filters (Oil Painting, Cyberpunk Neon, Gouache, etc.)
3. Styled image saves to `wallpapers/styled/` and appears in the Styled view

**Text Overlay:**
1. Select an image and click **Add Text**
2. Enter text, pick a font, adjust size, color, outline, and position
3. Live preview before saving to the Styled view

### Slideshow Setup

1. Go to **Settings > Slideshow**
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
| **Generation fails** | Check your provider settings. Pollinations.ai needs no key; Cloudflare needs Account ID + Token; Hugging Face, Prodia, Replicate and Fal.ai each need their own key. |
| **403 error (HuggingFace)** | Visit the model page on huggingface.co and accept terms. Some models require Pro. |
| **First prompt feels slow** | Wait for *"Ready — prompt engine warm."* in the status bar. |
| **Slideshow not rotating** | Ensure the source folder has images. For Favorites, add at least one image first. |
| **Wallpaper not changing** | Check the image exists in `wallpapers/generated/`. Verify Windows wallpaper permissions. |
| **EXE shows empty gallery** | Ensure `wallpapers/` and subfolders are beside `FrogPaper.exe`. |
| **System tray icon missing** | Install pystray: `pip install pystray` |
| **Global hotkey not working** | Install keyboard package: `pip install keyboard` |
| **App won't start** | Check Python 3.11+, all dependencies installed (`pip install -r requirements.txt`), and a valid provider configured. |
| **Android: "Backend offline"** | The FrogPaper backend is unreachable. Check Wi-Fi; locally start `python app.py` in `backend/`. |
| **Android: an engine is greyed out** | Tap it — the app opens the key sheet and links to the right Settings card. Add your own Gemini / Hugging Face / Replicate key. |
| **Android: gallery looks empty** | Check Settings > Wallpaper > Gallery source; the default is this phone. Pull older saves in with "Import from my SD folder". |

---

## Privacy

**Desktop:** all images are stored locally beside the app. Only text prompts are sent to the configured AI provider API. No images, filenames, or personal data are transmitted.

**Android:** wallpapers are stored on the phone. Prompts are sent to the FrogPaper backend, which forwards them to the selected engine. API keys you add stay on the device. No account, ads or tracking.

---

## Development Notes

- **Entry point:** `app.py` contains the main UI, layout, and event logic (~2,700 lines)
- **Tab modules:** `prompt_tab.py` (Quick Build, Recipes, Templates) and `gallery_tab.py` (Gallery, style transfer, text overlay, tags)
- **Settings:** `settings_tab.py` — resizable window with 8 sidebar categories (General, Generation, Appearance, Startup, Slideshow, Cloud & Backup, Advanced, Help)
- **Theme generation:** `theme_mixer.py` handles prompt construction; keyword caches pre-warm at startup
- **Image generation:** `wallpaper_generator.py` supports 6 providers (Pollinations, Cloudflare, Hugging Face, Prodia, Replicate, Fal.ai)
- **Prompt engine:** `prompt_builder.py` assembles final prompts with per-mode negatives and subject-aware anatomy constraints
- **Negative system:** `negative_manager.py` manages presets, smart negatives, and style-default negatives
- **Style filters:** `style_transfer.py` uses OpenCV for the filters and Pillow for text overlay (local processing, no API)
- **Slideshow:** `slideshow.py` manages auto-rotation with fullscreen detection, duplicate skipping, and countdown reset
- **Sessions:** `session_manager.py` with SQLite storage via `database.py` and JSON fallback
- **EXE path resolution:** `utils.get_app_dir()` returns `Path(sys.executable).parent` when frozen, `Path(__file__).parent` otherwise — all modules use this so user data always resolves correctly
- **Icon rendering:** `icons.py` generates themed toolbar icons programmatically
- **Tray:** `tray_manager.py` provides full app control from the system tray with a custom-drawn frog icon
- **Mobile:** `frogpaper-mobile/` is a separate Expo / React Native app with a Flask backend; bottom tabs are Home, Generate, Gallery and Settings

---

*Lily pads optional. Wallpapers mandatory.*
