A light Christmas theme, the new badge everywhere, and frogs that stay away unless you ask.

**Theme**
- New **Christmas — Blush Light**: the festive palette in daylight — blush snow panels, cranberry buttons, holly-green selections. Pink and red lead; green is the accent, not the base.
- The festive theme is **opt-in**: both Christmas themes sit in the picker, and launching this build never switches your theme for you (the old one-time "edition default" that repainted existing installs is gone).
- Every foreground clears WCAG AA on the surface it is painted on (worst pair 4.67:1).
- Theme variants now inherit their family's logo, so the light Christmas theme shows the Christmas badge without a second asset.

**Branding**
- The circular enamel-pin badge replaces the old frog-on-a-monitor logo: sidebar, tray, taskbar/window, exe icon, shortcuts, installer and uninstall entry, installer artwork, splash screen, website favicon and header mark.
- Taskbar sizes (16–48px) use the frog's face inside a circle — the arched lettering turns to mush that small.
- New `tools/generate_brand_assets.py` regenerates every asset from `sidebar_logo.png`.

**Dropdowns**
- Type-to-filter box in every list; Enter takes the top match, Escape closes.
- A 🕘 recently used row holds your last five picks per dropdown, across restarts.
- The dice now uses a shuffled bag: every option once before any repeat (89 clicks used to hit 61 distinct subjects — now 89 of 89), continuing where it left off after a restart.
- Lists repaired: shipped typo gone, duplicates and misfiled terms removed, genre words out of Mood, casing normalised (old spellings still resolve).
- Colour: nonsense combinations are blocked (`deep white`, `neon brown`) while every retired word still parses, so older presets keep their palette.

**Fixes**
- Frogs no longer appear with the Frog Dial off. Three leaks: a composition entry hardcoded "frog", the blank-subject pool excluded frogs but not toads, and the dice ignored the dial.
- Mood no longer breaks the subject phrase — prompts opened with "Grand, frog" instead of "Epic frog" for every mood.
- **Hugging Face works again, and only where it still exists.** It called `api-inference.huggingface.co`, a host that no longer resolves, so every request died before the token was read. It now uses the router, offers the only image model Hugging Face still serves (SD3 Medium), generates square, rounds sizes to a multiple of 16, retries a dropped connection, and explains permission problems instead of blaming the plan. `tools/verify_hf_token.py` checks a token without launching the app.
- Progress bars follow the theme — sv_ttk was repainting them Windows blue; they now use a FrogPaper style and pick up the theme accent.
- No more `name.png.png`: filenames keep one extension, and the 37 files already doubled were renamed with every stored path updated.
- Deleting an image keeps its evidence; every generated image is logged with its source.

**Under the hood**
- New `image_events` table, `tools/option_report.py` (uses / favourites / deletes / wallpapers per option) and `tools/option_audit.py` (list hygiene gate).
- Keyword expansion results are cached to `cache/expansions.json`: a word you have used before expands instantly and never loads the language model again (measured: 14s cold, 0.02s warm).
- Hugging Face goes through the router the service actually uses now, with its credit-backed endpoint for FLUX; the old host no longer exists.
- 755 tests, including golden prompt snapshots and a regression test for each bug above.

**Heads-up**
- Windows caches taskbar icons per executable path: rebuild the exe/installer to see the new icon, and unpin/repin if it lingers.
- The installer is unsigned, so SmartScreen may warn. Choose More info → Run anyway.
- Your wallpapers, tags, favourites and API keys in `%LOCALAPPDATA%\FrogPaper` are untouched.

**Install:** `FrogPaper-Setup-1.9.0.exe`
