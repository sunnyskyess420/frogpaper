Styles that finally look like their names, a smarter Ctrl+N, and the Halloween costume retired.

**Styles — rebuilt**
- Oil Painting, Watercolour, Gouache, Impressionist and 3D Render now use a Kuwahara renderer (flat painted regions with preserved edges) instead of a blur.
- Line Art no longer floods the page with black. Comic Book, Manga and Pop Art use real colour quantisation with clean black keylines.
- Fixed the filters that were outright broken: Art Deco (drew stripes), Edge Enhance (rendered near-black), Noir B&W (flat grey), 3D Render (blue speckle), Pop Art (pale noise).
- Sketch Pencil is its own graphite pass. Posterize uses 6-colour k-means. Cyberpunk Neon is a real magenta/cyan edge glow.

**Generation**
- Ctrl+N chooses: a random prompt when nothing changed, your built prompt right after an edit.
- Cancel now stops the transfer and never leaves a partial PNG behind.
- Pollinations 401/402/403/404 explain themselves — 402 means the model is out of credits.

**Interface**
- 26 text-overlay fonts (was 14), alphabetical, with a scrollbar.
- Mouse wheel fixed for touchpads and high-resolution wheels.
- Footer links renamed: Downloads & Updates, plus a Facebook Page link.
- Rounder corners, and the tray menu shows the running version.
- Settings > Help now has one Version History list instead of three overlapping ones.

**Fixes**
- A config.json that cannot be read is never overwritten — locked, corrupt, or saved with a UTF-8 BOM used to wipe every API key.
- Changing Sync Scope no longer deletes the cloud copies of images outside the new scope.
- Gallery thumbnails no longer blank out past 200 images.
- Ctrl+N and the tray's Generate item now call a method that exists.

**Heads-up**
- Halloween Edition branding is retired: About shows a plain version and fresh installs start with a blank startup subject. The theme and its popup sound are still available.
- The installer is unsigned, so SmartScreen may warn. Choose More info → Run anyway.
- Your wallpapers, tags, favourites and API keys live in `%LOCALAPPDATA%\FrogPaper` and are untouched.

**Install:** `FrogPaper-Setup-1.8.0.exe` (69.3 MB)
**SHA-256:** `E646264636CCA739CB7FA6B22271C5392927F29F7EEDC7180DDB99CDADF569AA`
