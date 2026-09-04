# FrogPaper — Improvement Status
**Date:** 2026-09-01 · **Test suite:** 81 tests, all passing · **Source state:** all fixes below are in this folder's source files

---

## PART 1 — What we implemented today

### 1. Threading migration (report §3 — High priority) ✅ COMPLETE
- All scattered `threading.Thread` spawns now go through the centralized
  `ThreadManager` (`run_background`).
- All cross-thread `app.root.after(0, ...)` UI pokes now use the thread-safe
  `schedule_ui_update` queue.
- Files migrated: `app.py`, `gallery_tab.py`, `tray_manager.py`,
  `update_checker.py`. `sync_manager.py` verified clean (its only
  `root.after(0)` was inside a comment).
- ThreadManager init (startup) and shutdown (app quit) hooks verified in
  `app.py`. GUI logging also confirms "ThreadManager initialized" on boot.

### 2. Test suite built from scratch (report §4) ✅ 81 tests
- `tests/` folder + one-double-click runner: `tests\run_tests.bat`
  (or `python -m unittest discover -s tests -v` from the project root).
- Coverage:
  - **35 pinned-dropdown tests** — pin toggling, persistence round-trips,
    corrupt-config resilience, marker stripping (★ ☆ ⭐ 📌 *), change callbacks.
  - **24 theme tests** — color math, WCAG contrast (incl. the '#' re-prefix
    regression), single-source guarantees (no duplicated constants).
  - **5 single-dropdown tests** — panel refs point at sidebar widgets by
    identity, values seeded from sidebar, no duplicate labels, and a
    regression test: clicking the WORDS of an editable dropdown opens the
    starred popup, never the native list.
  - **3 logging-rotation tests** — both entry points attach RotatingFileHandler
    with correct paths and limits (verified in fresh subprocesses).
  - **14 config-schema tests** — validation, corruption recovery, version
    stamping, key-rename migration.
- Note: these are logic tests; they never touch your real `config.json`.

### 3. Visual consistency — theme.py (report §2) ✅ core done
- New **`theme.py`**: single source for `STATUS_COLORS` (was duplicated),
  shared semantic palette, ★/☆ pin markers, `FONT_FAMILY`,
  `FALLBACK_POPUP_COLORS`, one color-math implementation (was 3 copies),
  WCAG `ensure_contrast`, and a reusable `Tooltip` class.
- `settings_tab.py` / `settings_components.py` now import the shared colors;
  `pinned_dropdowns.py` / `rounded_widgets.py` delegate their color math.
- Pin symbols unified to the ★/☆ standard in all user-facing text.
- Tooltips added: star buttons ("Add/Remove from favorites"), favorites ✕ and
  Clear All buttons.
- Bonus fix: malformed hex colors (e.g. `#12345`) are now passed through
  untouched instead of being mangled into garbage colors.

### 4. Single dropdown per category (your report) ✅ COMPLETE
- Root cause 1: the (hidden) Quick Build panel created duplicate category
  fields and was treated as the *primary* input source. Its duplicate fields
  are removed; every internal reference now points at the sidebar's starred
  dropdowns; `prompt_builder_values` syncs live from the sidebar.
- Root cause 2: clicking the **words** of Subject/Lighting/Setting (editable
  fields) opened Tk's native starless dropdown. Now *every* click opens the
  starred popup; the native list is suppressed on press and release; typing
  still works (focus returns to the field when the popup closes).
- Kept in the panel (no sidebar equivalent): Style, Negative presets, Smart
  Negatives, Negative prompt.

### 5. Startup empty-dropdown fix ✅
- With "remember settings" OFF, startup used to *blank* Mood / Lighting /
  Color / Setting / Atmosphere. The built-in starter defaults (frog, neon,
  random color/setting/atmosphere) now survive, and the prompt engine agrees
  with what the UI shows.

### 6. Log rotation (report §3) ✅
- `daily_runner.log`: unbounded `FileHandler` → `RotatingFileHandler`
  (2 MB per file, 3 backups ≈ 8 MB max forever).
- **NEW:** the GUI app now logs to `logs/frogpaper.log` with the same limits —
  previously it logged to console only, which is invisible in the packaged
  EXE. All errors/info are now captured with timestamps.
- Verified live: a full app build writes real content to the log.

### 7. Config schema + versioning (report §5) ✅ core done
- All 46 known config keys are type-checked on load against a schema mirroring
  `config.template.json`. Wrong-typed values are dropped with a logged warning
  (app falls back to defaults instead of crashing); integral floats coerce to
  int; `True` is rejected where an int is expected; unknown/future keys are
  always preserved.
- Corrupt `config.json` is backed up as `config.json.corrupt` before the app
  starts clean — nothing is silently lost.
- `config_version` is stamped on every save; older configs are stamped on
  load; a key-rename registry (`_CONFIG_KEY_RENAMES` in `utils.py`) is ready
  for future renames.
- `load_config()` remains read-only (no surprise disk writes).

### 8. Type hints & docstrings (report §1 — High) ✅ COMPLETE (core API)
- ✅ `thread_manager.py` — fully typed (13 signatures, `UITask` dataclass).
- ✅ `pinned_dropdowns.py` — fully typed (35 signatures, instance attributes,
  factory functions). Honest `object -> object` on `strip_pin_marker`.
- ✅ `settings_components.py` — fully typed (31 signatures across 7 classes:
  SetupGuideText, StatusBadge, SettingRow, SettingCard, ExpandableSection,
  HelpResourceCard, SidebarNav, CloudProviderCard); docstring gaps filled;
  remaining `_lighten` duplicates consolidated into `theme.py`; `app`
  back-reference typed via `TYPE_CHECKING` + quoted annotation
  (introspection-safe on Python 3.14's lazy annotations).
- ⬜ Optional extensions: `gallery_tab.py`, `settings_tab.py`, `app.py`.

### Also produced
- **2026-09-02:** Main window now opens CENTERED in the visible work area
  (screen minus taskbar) and sized to always fit — previously a fixed
  1600x900 window opened at the top-left with its bottom hiding behind the
  taskbar. `utils.place_on_work_area()` + startup wiring in `app.py`;
  unreliable maximize-on-start removed; minsize adapts to small screens.
  3 placement tests added (84 total).
- Fresh `dist\FrogPaper.exe` (built mid-session). NOTE: it contains the fixes
  up to ~16:49 only — it does **not** include the startup-defaults fix, the
  click unification, log rotation, config schema, type hints, or this
  centering fix. Rebuild before reinstalling (see Part 3).
- Backups of every pre-change file, in timestamped folders in the project
  root (`_backup_before_*`).

---

## PART 2 — What still needs to be done

Ranked by value-per-effort (the order we agreed to work in):

1. ~~Type hints & docstrings — core modules~~ ✅ DONE (thread_manager,
   pinned_dropdowns, settings_components — 2026-09-01). Optional: extend to
   gallery_tab / settings_tab / app.py later.

2. ~~**Config: user-editable defaults docs**~~ ✅ DONE (2026-09-03) —
   CONFIG_GUIDE.md added; README points to it.

3. ~~**Graceful degradation pass**~~ ✅ DONE (2026-09-03) — gallery/history
   I/O wrapped in try/except with user-friendly dialogs; DB reads fall back
   to JSON/safe defaults; test_graceful_io.py.

4. **UI leftovers from report §2** (mostly done 2026-09-03)
   - ~~Keyboard navigation + visible focus indicators~~ ✅ (RoundedButton
     keyboard activation, ttk focus styles, Text-widget Tab-trap fix).
   - ~~Responsive card widths for high-DPI windows~~ ✅ (dropdown popup
     width auto-fits the longest item).
   - ✅ Inline-color hotspot migration (2026-09-03, release-prep round):
     the old "~600 inline colors in app.py" estimate was stale — an
     AST scan found 256 quoted hex literals outside the palette modules
     (app.py itself had only 14). Migrated the 16 most-repeated values
     (Tailwind gray ramp, violet accent #8b5cf6, white/black, status
     colors) into 12 new named constants in theme.py (COLOR_ACCENT,
     COLOR_GRAY_200..900, COLOR_NEAR_BLACK, COLOR_MID_GRAY,
     COLOR_DIM_GRAY, COLOR_GREEN_BRIGHT) plus the existing
     COLOR_SUCCESS/WARNING/ERROR/MUTED — 154 literals replaced across
     14 modules, every value byte-identical (pure refactor, zero visual
     change). Remaining ~102 literals are unique one-off values left in
     place by design. 301-test baseline + real-app startup smoke
     re-verified after the migration.
   - ✅ Unused-import cleanup (2026-09-03, release-prep round): 132 dead
     imports deleted, 21 availability-probe imports (watchdog/nltk/
     sqlalchemy/sv_ttk/pystray/pinned/…) marked inline with
     `# noqa: F401  (availability probe)`, and the STATUS_COLORS facade
     re-export in settings_tab.py given its own noqa (it is consumed via
     `from settings_tab import STATUS_COLORS` — ruff can't see that).
     ruff.toml now enforces F401 alongside F821/F811; `ruff check .`
     passes clean. Note: file_watcher.py is an orphan module (zero
     importers) with a pre-existing import-time NameError when watchdog
     is missing — left untouched, flagged for deletion-or-wiring in a
     future round.
   - Screen-reader-friendly pin markers (partially improved by unification).
     (OPEN, low priority)

5. ~~**Testing expansion**~~ ✅ DONE (2026-09-03) — 296 tests total (unit +
   UI integration), green via `python -m unittest discover` and pytest.
   CI workflow delivered: `.github/workflows/tests.yml` (windows-latest,
   lean deps) — commit it to the repo to activate the Actions tab.

6. ~~**Performance (report §6)**~~ ✅ DONE (2026-09-03) — background
   thumbnail loading with cache (Favorites/Styled/Manual), image-dimension
   memo, tags N+1 cache + invalidation on tag writes, expansion-cache
   invalidation on mapping changes, resize debouncing. test_performance.py.

7. **File modularization** (in progress — phases A + B done 2026-09-04)
   - ✅ Phase A (2026-09-04): `settings_tab.py` (2,110 lines) split into
     5 focused modules behind a facade — `settings_ux_data.py` (provider
     UX dicts), `settings_categories.py` (8 sidebar section builders),
     `settings_providers.py` (provider/token UI), `settings_slideshow.py`
     (slideshow controls), `settings_persistence.py` (save/load/mappings).
     `settings_tab.py` stays as the shell + re-export facade (613 lines);
     `SettingsTab` is still one class via mixins, so app.py / prompt_tab /
     tests needed zero changes. All 44 methods verified identical
     (AST diff), 296 tests green after the split.
   - ⬜ Phase B: `app.py` (~8,890 lines) → generation_logic / sidebar /
     center panel / gallery wiring… (same facade pattern)
     - ✅ Step 1 (2026-09-04): pure-data blocks extracted — `app_themes.py`
       (THEMES palettes, UI spacing, WCAG contrast helpers) and
       `app_prompt_data.py` (prompt-mode/style/slideshow tables, provider/
       model config, base+legacy option lists, THEME_VARIABLE_OPTIONS).
       app.py 8,891 → 7,289 lines. All 43 moved names verified value- and
       type-identical; re-exports are the same objects; app.<NAME> access
       and test monkeypatching unaffected. 296-test baseline preserved.
     - ✅ Step 2a (2026-09-04): theme engine extracted —
       `app_theme_engine.py` hosts `FrogPaperAppThemeMixin`: apply_theme
       (583 ln), all `_retheme_*` helpers, `on_theme_changed`, sidebar
       icon refresh and the entry-cursor colour system (16 methods,
       1,290 ln). app.py 7,289 → 5,999 lines. All 354 method names
       verified body-identical (AST diff), MRO clean, 296-test baseline
       preserved. Windows run confirmed 296/296 PASSED after Phase A+B1.
     - ✅ Step 2b (2026-09-04): class body split into 4 mixins —
       `app_generation_mixin.py` (generation pipeline: generate,
       prompt/theme/image threads, progress, cancel — 24 methods),
       `app_system_mixin.py` (system tray, toast, escape, quit — 30),
       `app_cloud_mixin.py` (CLOUD_PROVIDERS + cloud cards, manual sync,
       auto-backup, startup registry — 26 + class attr),
       `app_delegates_mixin.py` (the delegate surface: gallery/template/
       settings adapters — 222). Supporting re-homes: `app_runtime.py`
       (optional-deps probing: thread_manager/pystray/sv_ttk/keyboard/
       ui_effects/pinned_dropdowns + WINDOWS detection) and `app_paths.py`
       (BASE_DIR..SESSIONS_FILE + mkdir side effects, re-imported at the
       same start-up point). app.py 5,999 → 2,589 lines (-71% cumulative
       from 8,891). The 3 pre-existing duplicate definitions keep their
       resolution semantics (winning copies stay in the app.py body /
       original relative order); all 341 defs verified AST-identical,
       MRO = theme → generation → system → cloud → delegates, ruff F821
       clean on every touched module, 296-test baseline preserved.
       (Windows re-run pending.)
   - HOTFIX (2026-09-03, field-reported): first real launch after the
     split crashed with `NameError: name 'SV_TTK_AVAILABLE' is not
     defined` in `app_theme_engine.py:530`. Root cause: apply_theme and
     the retheme helpers reference the runtime flags
     (`SV_TTK_AVAILABLE`, `sv_ttk`, `UI_EFFECTS_AVAILABLE`,
     `ThemeTransition`) that live in `app_runtime.py`; the B2a dep scan
     missed them because they were still app.py module globals at scan
     time, and all 296 unit tests stayed green because none of them
     instantiates the real app. Fix: `app_theme_engine.py` re-imports
     the flags from `app_runtime.py` (same conditional-`sv_ttk` pattern
     app.py uses — identical semantics, no duplicate probe). A project-
     wide ruff F821 scan now reports zero unresolved names except the
     known ImageTk case below. New `tests/test_app_smoke.py` builds the
     FULL FrogPaperApp headless, re-themes all 18 palettes and drives
     `on_theme_changed` — the startup path is now covered permanently
     (suite 296 → 301).
   - Note for Phase C: `_show_toast` references `ImageTk` which is never
     bound in that scope — the NameError is silently swallowed by
     `except Exception: pass`, so the toast shadow image never renders.
     Pre-existing behaviour, deliberately preserved verbatim through the
     move (do NOT "fix" by importing ImageTk without deciding whether the
     shadow should start appearing).
   - ✅ Phase C (2026-09-03): housekeeping pass — roadmap #7 fully
     complete. Removed the dead `_update_provider_visibility` wrapper
     (zero callers; called a method deleted from SettingsTab long ago —
     would have AttributeError'd if ever invoked). Removed the 3
     shadowed duplicate methods (dead first copies of `_on_minimize` and
     `advance_slideshow` in the delegates mixin — the app.py copies win
     via MRO — and the duplicate `on_fav_resize` copy, byte-identical to
     its twin). Deleted 4 redundant local re-imports flagged by ruff
     F811 (`TutorialManager` in app.py `__init__`, `threading` in
     file_watcher, `ImageEnhance` in gallery_tab's fade, and
     `ExpandableSection` in settings_providers' local import — kept
     `SetupGuideText`, which is genuinely lazy-loaded). Renamed the
     nested one-letter helper `R()` in rounded_widgets.py to
     `register_image()`. Def-level naming scan: the codebase is already
     snake_case everywhere except unittest's own `setUp`/`tearDown`
     (framework API — must stay). Added `ruff.toml` (F821 + F811,
     passing clean; F401 deliberately deferred — ~150 pre-existing
     unused imports, several are availability probes a bulk --fix would
     break) and `.pre-commit-config.yaml`; CI now runs a lint job before
     the Windows test matrix. 301-test baseline + real-app startup smoke
     re-verified after every removal.
   - ⬜ Open product decision (kept out of Phase C on purpose): the
     silent ImageTk toast-shadow bug (see note above) — importing
     ImageTk would make the toast shadow START appearing (visual
     change); suppressing it changes nothing. Left verbatim + ruff
     per-file-ignore documents why.

8. **Packaged app** (when you want the installed app updated)
   - Rebuild: run `build_frogpaper_exe.bat` (or ask me) — the spec + PyInstaller
     6.22.2 are ready; prebuild security check passes.
   - Then update `AppData\Local\Programs\FrogPaper\FrogPaper.exe` (your data —
     config, database, wallpapers — is untouched by that).

---

## PART 3 — Maintenance notes

- **Run tests:** double-click `tests\run_tests.bat` (expect "OK").
- **Rollback:** every change today has a pre-change copy in a timestamped
  `_backup_before_*` folder in this project root.
- **Log files:** `logs\frogpaper.log` (GUI) and `logs\daily_runner.log`
  (scheduled tasks) — both self-rotate at 2 MB with 3 backups.
- **If a config ever breaks:** `config.json.corrupt` beside it holds the
  broken original; delete/rename it and the app starts fresh.
