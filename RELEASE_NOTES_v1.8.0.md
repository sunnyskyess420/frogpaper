## FrogPaper v1.8.0

Styles that finally look like their names, a Ctrl+N that reads the room, and the Halloween costume put away.

### Styles — rebuilt

Every filter was reviewed on a real wallpaper, and the ones that did nothing (or the wrong thing) were rewritten.

- **Oil Painting, Watercolour, Gouache, Impressionist and 3D Render** now run through a Kuwahara renderer — the technique that produces flat painted regions with preserved edges — instead of a blur. They read as painted, not filtered.
- **Line Art** no longer floods the page with black; it traces sparse ink outlines and drops texture speckle.
- **Comic Book, Manga and Pop Art** use real colour quantisation with clean black keylines.
- **Art Deco** is a gold-on-ink duotone with a frame, not horizontal stripes.
- **Noir B&W** gains CLAHE contrast and a vignette; **Edge Enhance** is an unsharp mask instead of a near-black frame.
- **Posterize** quantises to six colours with k-means (the old per-channel bit-mask produced yellow casts).
- **Sketch Pencil** is its own graphite dodge rather than a copy of Sketch.
- **Cyberpunk Neon** is a darkened plate with magenta/cyan edge glow.
- **Surreal Dali** gets a real melt warp with colour fringing.

### Generation

- **Ctrl+N now chooses.** Nothing on screen yet → a random prompt. You edited the sidebar since the last image → your built prompt. Untouched → roll a random prompt. The log states which branch ran.
- **Cancel actually cancels.** Response bodies are read in 64 KiB chunks, back-off sleeps are interruptible, and a cancelled run never leaves a partial PNG behind.
- **Pollinations errors explain themselves.** 401/403 (token needed), 402 (out of credits), 404 (unknown model) each say what happened and what to do.

### Interface

- **Text overlay: 26 fonts**, up from 14, alphabetically sorted, with a scrollbar — the old list was six rows tall with no scrollbar, so it looked like six fonts.
- **Mouse wheel fixed.** High-resolution and touchpad deltas are no longer truncated to zero; text scrolls three lines per notch, canvases one unit.
- **Footer links say what they open:** "Downloads & Updates" and a new "Facebook Page" link.
- **Rounder corners:** Windows 11 gets rounded window corners, and buttons/panels have larger radii.
- **Version visible everywhere:** the tray menu shows `FrogPaper v1.8.0`, and Settings > Help has a single Version History list (the old page had three overlapping lists, one of them stale).
- **The welcome prompt no longer returns** on every launch.

### Reliability

- **A config.json that cannot be read is never overwritten.** Locked, corrupt, or saved with a UTF-8 BOM (Notepad, PowerShell 5.1) used to wipe every API key on the next save.
- **Changing Sync Scope no longer deletes cloud copies** of images outside the new scope.
- **Gallery thumbnails no longer blank out** past 200 images.
- **Ctrl+N and the tray's Generate item call a method that exists** — both used to fail silently.
- **Packaging:** the installer no longer ships every root `.py` file (including a debug script that deletes `config.json`), and the build script no longer deletes the onedir output folder.

### Halloween retired

The Halloween Edition branding is gone: About shows a plain version, and fresh installs start with a blank startup subject instead of "Halloween". The Halloween **theme** and its popup sound remain available in Settings > General > App Theme.

### Under the hood

- 551 tests passing, 25 style sub-tests, ruff clean.
- New regression test: every style keeps its image size and never renders blank or black.
- Release list (`RELEASE_HISTORY`) is now the single source for About, Settings > Help, and the website changelog.

### Upgrading

Run the installer over your existing copy. Your wallpapers, gallery tags, pinned favourites, presets, settings and cloud connections live in `%LOCALAPPDATA%\FrogPaper` and are untouched.

The installer is unsigned, so Windows SmartScreen may warn — choose **More info → Run anyway**.

### Checksums

```
FrogPaper-Setup-1.8.0.exe
SHA-256: E646264636CCA739CB7FA6B22271C5392927F29F7EEDC7180DDB99CDADF569AA
```

Verify with `certutil -hashfile FrogPaper-Setup-1.8.0.exe SHA256`.
