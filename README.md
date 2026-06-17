# 🐸 FrogPaper

> *A cozy AI wallpaper studio that lives on your desktop.*

**FrogPaper** is a Windows desktop application for generating, curating, and rotating AI-powered wallpapers. Built with Python and Tkinter, it connects to Hugging Face's image generation API and gives you a complete creative workflow — from structured prompt building to a visual gallery, favorites, style transfer, slideshow automation, and direct Windows wallpaper integration.

No browser. No server. Just a desktop app and your imagination.

---

## ⚡ Quick Start

**1. Install & Launch**
```bash
pip install Pillow huggingface_hub nltk sentence-transformers opencv-python pystray
python app.py
```

**2. Set API Token**
Paste your Hugging Face token in **Settings → Generation**, or set via environment variable:
```bash
setx HUGGINGFACE_TOKEN hf_your_token_here
```

**3. Generate Your First Wallpaper**
1. Open **Prompt Builder** tab
2. Fill in Quick Build fields (Subject, Setting, Style, Lighting, Mood, Color, Atmosphere, Mode)
3. Click **🎲 Generate Prompt**
4. Click **🖼️ Generate Image**
5. Click **🚀 Set as Wallpaper**

> **Note:** The prompt engine warms up in the background after launch. The status bar will show *"Warming up prompt engine..."* and then *"Ready — prompt engine warm."* — first prompt generation is instant once that message appears.

---

## ✨ What FrogPaper Does

FrogPaper is a complete wallpaper creation and management studio in a single window:

1. **Build Prompts** — Use Quick Build dropdowns (Subject, Setting, Style, Lighting, Mood, Color, Atmosphere, Mode) or load from the Prompt Library
2. **Generate Images** — Send prompts to Hugging Face AI models and create wallpapers
3. **Curate Collection** — Browse gallery, favorite images, apply artistic filters, tag and organize
4. **Set & Rotate** — Apply wallpapers instantly or let the slideshow rotate automatically

---

## 🍃 Key Features

| Feature | Description |
|---|---|
| **Quick Build** | 8 structured dropdowns for fast prompt assembly: Subject, Setting, Style, Lighting, Mood, Color, Atmosphere, Mode |
| **Prompt Library** | Save, load, import, export reusable prompt configurations |
| **Quick Prompts** | Named snapshots of Quick Build field values for instant recall |
| **Sessions** | Save and restore complete working states; auto-named with subject and date/time |
| **AI Generation** | FLUX.1-schnell, FLUX.1-dev, Stable Diffusion XL, SD 3.5 Large, or custom models |
| **Gallery** | Thumbnail grid with sorting (date, name, size), filtering by tags, multi-select |
| **Favorites** | Bookmark wallpapers with dedicated slideshow source |
| **Style Transfer** | 19 local artistic filters: Oil Painting, Cyberpunk Neon, Gouache, Vaporwave, etc. |
| **Tagging** | Add custom tags to any image; filter gallery by tag |
| **Slideshow** | Auto-rotate wallpapers on timer; interval resets whenever you manually change the wallpaper |
| **App Themes** | 12 UI color themes |
| **Windows Integration** | Native wallpaper setting, system tray with full controls, minimize-to-tray |
| **Daily Runner** | Optional scheduled task for automatic daily wallpaper generation |

---

## 🪟 App Layout

### Left Panel — Preview
Shows the currently selected or generated image at full size. Double-click to set as wallpaper instantly. Displays filename, resolution, and file size below.

### Tab: Prompt Builder
Your creative workspace, all in one tab.

**Quick Build Prompts**
- 8 structured dropdown fields in paired rows: Style | Mode, Lighting | Mood, Color | Modifier
- Subject and Setting fields at the top
- Negative prompt field for exclusions
- "Keep typed subject literal" checkbox to prevent subject randomization
- Action buttons: 🎲 Generate Prompt, 🎰 Random Prompt, ⚡ Save as Quick Prompt, 📂 Load Quick Prompt, 🗑️ Delete Prompt

**Session Controls**
- 💾 Save — Snapshot current Quick Build state (auto-named: *Subject YYYY-MM-DD HH:MM*)
- 📂 Load — Restore a saved session

**Prompt Preview**
- Shows the generated prompt text
- Mode badge and Subject Lock indicator
- Action buttons: 🖼️ Generate Image, 🚀 Set as Wallpaper, ❌ Cancel

**Prompt Library** (collapsible)
- 📚 Prompt Library dropdown with built-in and custom prompts
- Import/Export/Edit/Delete controls

### Tab: Gallery
Visual image library with four views:
- **Gallery** — All generated and manual wallpapers
- **Favorites** — Bookmarked images
- **Styled** — Style-transferred outputs
- **Manual** — Imported images

**Controls:**
- Set as Wallpaper, Save to Favorites, Apply Themes, Tag Selected, Delete
- View selector, Tag filter, Sort dropdown (Date Newest/Oldest, Name A-Z/Z-A, Size Largest)
- Multi-select with Ctrl+click for batch tagging

### Tab: Settings

| Section | Controls |
|---|---|
| **Appearance** | UI theme selection (12 themes) |
| **Generation** | Hugging Face token, AI model, resolution presets, inference steps |
| **Gallery & Slideshow** | Slideshow interval/source/order, skip duplicates, wallpaper output format/quality |
| **Window Behavior** | Minimize to tray toggle |
| **Advanced** | Keyword expansion, negative prompt presets |

---

## 🤖 AI Models

| Model | Hugging Face ID | Notes |
|---|---|---|
| FLUX.1-schnell | `black-forest-labs/FLUX.1-schnell` | Fastest; free tier |
| FLUX.1-dev | `black-forest-labs/FLUX.1-dev` | High quality; requires Pro |
| Stable Diffusion XL | `stabilityai/stable-diffusion-xl-base-1.0` | Standard quality |
| SD 3.5 Large | `stabilityai/stable-diffusion-3.5-large` | Requires Pro |
| Custom | *any HF model ID* | Experimental |

> Some models require accepting terms on huggingface.co before API access.

---

## 🛠 Prompt Modes

| Mode | Aesthetic |
|---|---|
| **Stylized** | Digital illustration — bold shapes, vivid colors |
| **Realistic** | Photorealistic — cinematic lighting, real-world textures |
| **Product Photo** | Studio shot — sharp detail, clean neutral background (auto-remapped to Realistic for living subjects) |
| **Surreal** | Dreamlike — impossible scale and atmosphere |

---

## 🖥️ System Tray

Right-clicking the tray icon gives full app control without opening the window:

| Menu Item | Action |
|---|---|
| **Open FrogPaper** | Restore main window (double-click default) |
| **Open Gallery** | Restore and jump to Gallery tab |
| **Open Prompt Builder** | Restore and jump to Prompt Builder tab |
| **Random Wallpaper** | Set a random image from your gallery instantly |
| **Previous Wallpaper** | Go back in wallpaper history |
| **Next Wallpaper** | Advance to next wallpaper |
| **Start / Pause / Resume Slideshow** | Single dynamic item — label changes with slideshow state |
| **Stop Slideshow** | Visible only when slideshow is running |
| **About FrogPaper** | Version and info dialog |
| **Quit FrogPaper** | Fully exit the application |

---

## 📁 Project Structure

```
frogpaper/
├── app.py                  ← Main application (UI, logic, events)
├── main.py                 ← Alternate entry point
│
├── wallpaper_generator.py  ← Hugging Face API integration
├── theme_mixer.py          ← Theme/prompt generation engine
├── prompt_builder.py       ← Prompt assembly from components
├── prompt_refiner.py       ← Prompt optimization
├── prompt_validator.py     ← Prompt audit and variable validation
├── keyword_expander.py     ← Keyword expansion and thesaurus system
├── style_transfer.py       ← 19 local artistic filters (OpenCV)
├── template_system.py      ← Prompt Library data models
├── slideshow.py            ← Auto-rotation timer and logic
├── set_wallpaper.py        ← Windows wallpaper API
├── gallery_manager.py      ← Gallery metadata and tags
│
├── utils.py                ← Shared utilities; get_app_dir() for EXE-safe paths
│
├── config.json             ← User settings (auto-created)
├── keywords.json           ← Thematic keyword bank
├── gallery_tags.json       ← Image tag database
├── negative_presets.json   ← Negative prompt presets
├── presets.json            ← Saved preset bundles
├── recipes.json            ← Per-file prompt storage
├── templates.json          ← Prompt template definitions
├── prompt_library.json     ← Saved prompt library
│
├── wallpapers/             ← Lives beside the EXE (not bundled inside it)
│   ├── generated/          ← AI-generated wallpapers
│   ├── manual/             ← Imported images
│   ├── styled/             ← Style-filtered outputs
│   └── favorites/          ← Bookmarked images
│
├── logs/                   ← Session history, favorites, prompts
├── sessions/               ← Saved session snapshots
├── recipes/                ← Per-recipe prompt files
├── templates/              ← Per-template files
│
├── run_frogpaper.bat       ← Windows launcher
├── build_frogpaper_exe.bat ← PyInstaller EXE build script
├── FrogPaper.spec          ← PyInstaller spec file
├── setup_scheduler.py      ← Task Scheduler integration
├── rotate_wallpaper.bat    ← Random rotation script
└── daily_runner.py         ← Headless daily generation
```

---

## 💻 System Requirements

| Requirement | Minimum | Recommended |
|---|---|---|
| OS | Windows 10 | Windows 11 |
| Python | 3.9 | 3.11+ |
| RAM | 4 GB | 8 GB |
| Storage | 500 MB | 2 GB+ |
| Internet | Required for generation | Stable connection |
| Hugging Face token | Required | — |

---

## 🌱 Installation

### Recommended — Windows Launcher *(easiest)*

If you have Python installed, just double-click the launcher:

```
run_frogpaper.bat
```

The batch file handles dependency checks and launches the app automatically. No terminal needed.

---

### Manual — Command Prompt or PowerShell

If you prefer to run it yourself, open a terminal in the FrogPaper folder and run:

**Step 1 — Install dependencies**
```
pip install Pillow huggingface_hub nltk sentence-transformers opencv-python pystray
```

**Step 2 — Launch the app**
```
python app.py
```

> **Note:** Python 3.9 or newer is required. Download it from [python.org](https://www.python.org/downloads/) if needed. Make sure to check **"Add Python to PATH"** during installation.

---

### Optional — Daily Wallpaper Automation

To generate a fresh AI wallpaper automatically every time you log in, register a Windows Task Scheduler task:

```
python setup_scheduler.py
```

> **Run as Administrator** — right-click Command Prompt → *Run as administrator*, then run the command above. Only needs to be done once.

---

### EXE Build — Standalone Windows Executable

To package FrogPaper into a single `FrogPaper.exe` (no Python install required on the target machine):

```
build_frogpaper_exe.bat
```

The script installs PyInstaller, cleans old build artifacts, and produces `dist\FrogPaper.exe`.

**After building — required folder layout next to the EXE:**
```
dist\
├── FrogPaper.exe
├── config.json             ← copy from project root if you want saved settings
├── wallpapers\
│   ├── generated\          ← auto-created on first run
│   ├── manual\             ← place images here to use them
│   ├── styled\             ← auto-created
│   └── favorites\          ← auto-created
└── logs\                   ← auto-created
```

> **Important:** The `wallpapers/` folder and your images must sit **beside** `FrogPaper.exe`, not inside it. The EXE automatically resolves all paths relative to its own location — not the temporary extraction directory that PyInstaller uses internally.

---

## 🎬 Workflow Guide

### Building Prompts

**Quick Build Method:**
1. Fill Subject (what), Setting (where), then Style, Lighting, Mood, Color, Atmosphere, Mode
2. Click **🎲 Generate Prompt** to build the prompt
3. Review in Prompt Preview section
4. Click **🖼️ Generate Image** to create the wallpaper

**Random Prompt Method:**
Click **🎰 Random Prompt** to auto-fill all dropdowns with random values, then generate.

**Using Saved Prompts:**
1. Expand **📚 Prompt Library**
2. Select a saved prompt from dropdown
3. Fields auto-load into Quick Build
4. Adjust values as needed and generate

**Saving Quick Prompts:**
Click **⚡ Save as Quick Prompt** to save current field values as a named snapshot for later recall.

### Managing Images

**Gallery Navigation:**
- Click thumbnails to preview on left panel
- Double-click any thumbnail to set as wallpaper instantly
- Ctrl+click to multi-select for batch tagging

**Favorites:**
- Select image → Click **Save to Favorites**
- Switch to Favorites view via dropdown
- Favorites have a dedicated slideshow source

**Style Transfer:**
1. Select image in Gallery
2. Click **Apply Themes**
3. Choose from 19 filters (Oil Painting, Cyberpunk Neon, etc.)
4. Styled image saves as new file in `wallpapers/styled/`

**Tagging:**
1. Select one or more images (Ctrl+click for multi)
2. Click **Tag Selected**
3. Enter comma-separated tags
4. Use Tag filter dropdown to filter gallery

### Slideshow Setup

1. Go to **Settings → Gallery & Slideshow**
2. Check **Enable in-app slideshow**
3. Set interval (minutes)
4. Choose source: Generated, Manual, All Images, or Favorites
5. Use **⏭ Next Wallpaper** in the bottom bar to skip ahead

> The slideshow interval timer resets automatically whenever you manually change the wallpaper — from gallery clicks, tray controls, or any other source.

### Sessions

Save your complete working state (all Quick Build values, selected prompt, negative prompt, etc.):
- Click **💾 Save** in the Session Controls section
- Session is auto-named with your current subject and the date/time (e.g. *Dragon 2026-05-18 21:00*)
- Restore later with **📂 Load**

---

## 🤖 Automated Wallpaper Options

### Option A: Daily AI Generation (setup_scheduler.py)

Registers a Windows Task Scheduler task that generates a fresh AI wallpaper on every login.

**Setup (run once as Administrator):**
```bash
python setup_scheduler.py
```

**Test:**
```bash
schtasks /run /tn FrogPaperDailyWallpaper
```

**Remove:**
```bash
schtasks /delete /tn FrogPaperDailyWallpaper /f
```

> Uses your HF token and `keywords.json`. Does not use saved Quick Prompts.

### Option B: Random Rotation (rotate_wallpaper.bat)

Picks a random existing image from `wallpapers/` folders and sets it as wallpaper. No API call, works offline.

**Manual run:**
```bash
rotate_wallpaper.bat
```

**Auto-run:** Add to Task Scheduler with a trigger (logon, time interval, etc.)

### Option C: In-App Slideshow

Runs while the app is open (or minimized to tray). Configure in **Settings → Gallery & Slideshow**, or control it from the system tray without opening the window.

---

## 🔧 Troubleshooting

| Issue | Solution |
|---|---|
| **403 error on generation** | Visit model page on huggingface.co and accept terms. Some models (FLUX.1-dev, SD 3.5) require Pro. |
| **First prompt feels slow** | The prompt engine warms up in the background after launch. Wait for *"Ready — prompt engine warm."* in the status bar. |
| **Slideshow not rotating** | Ensure source folder has images. For Favorites, add at least one image first. |
| **Wallpaper not changing** | Check image exists in `wallpapers/generated/`. Verify Windows wallpaper permissions. |
| **No gallery images shown** | Gallery scans `wallpapers/` subfolders. Generate or import images to populate. |
| **EXE shows empty gallery** | Make sure `wallpapers/` and its subfolders are placed **beside** `FrogPaper.exe`, not inside the `dist/` build folder by itself. The EXE resolves all paths relative to its own location. |
| **System tray icon missing** | Install pystray: `pip install pystray` |
| **App won't start** | Check Python 3.9+, all dependencies installed, HF token set |

---

## 🔒 Privacy

All images stored locally. Only text prompts sent to Hugging Face API. No images, filenames, or personal data transmitted.

---

## 📝 Development Notes

- **Entry point:** `app.py` contains all UI and event logic
- **Theme generation:** `theme_mixer.py` handles prompt construction; keyword caches pre-warm at startup
- **Image generation:** `wallpaper_generator.py` interfaces with Hugging Face
- **Prompt engine:** `prompt_builder.py` assembles final prompts with per-mode negatives and subject-aware anatomy constraints
- **Style filters:** `style_transfer.py` uses OpenCV (local processing, no API)
- **Slideshow:** `slideshow.py` manages the auto-rotation timer, including `reset_timer()` on any manual wallpaper change
- **Settings:** `config.json` auto-created on first run
- **EXE path resolution:** `utils.get_app_dir()` returns `Path(sys.executable).parent` when frozen by PyInstaller and `Path(__file__).parent` when running as plain Python — all modules use this instead of `Path(__file__).parent` directly so user data folders always resolve beside the EXE

---

*Lily pads optional. Wallpapers mandatory.* 🐸