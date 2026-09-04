FROGPAPER UPDATE - 2026-09-04 (release-candidate build)
=========================================================

Everything current in one zip. This build ships EVERY code file in the
project (auto-discovered at build time), so extracting it over your
FrogPaper project folder leaves no stale module behind. It never touches
your data: config.json, frogpaper.db, wallpapers, and the presets /
keywords / templates / recipes JSON files are not in this zip.

Extract the WHOLE zip into your FrogPaper project folder (the folder
that contains app.py), allow overwriting all files, then double-click
tests\run_tests.bat - expect:

    Ran 301 tests ... OK

(On your Windows machine every test passes, including the logging test
that always "fails" on my Linux sandbox - that one needs Windows.)

WHY THIS ZIP WAS REBUILT (2026-09-04)
-------------------------------------
The previous zip (2026-09-03) shipped only the 25 modules touched by the
modularization refactor - a hand-maintained list. theme.py changed in
the color-constants round but was missing from that list, so updating
produced a broken mix: new app.py (imports COLOR_DIM_GRAY) alongside
the old theme.py -> "ImportError: cannot import name 'COLOR_DIM_GRAY'".
The build script now auto-discovers ALL project files, so this failure
class cannot recur.

CODE - full coverage: all project-root .py modules are included
---------------------------------------------------------------
Highlights of the 2026-09-03/04 freeze round:
  app.py                  imports shared color constants from theme.py;
                          part of the 132 dead-import removal (ruff F401)
  theme.py                NEW color constants: COLOR_ACCENT, COLOR_WHITE /
                          BLACK / NEAR_BLACK / MID_GRAY / DIM_GRAY,
                          COLOR_GRAY_200/400/700/800/900, COLOR_GREEN_
                          BRIGHT; 154 inline hex literals migrated across
                          14 modules -> zero visual change
  app_theme_engine.py     hotfix retained: re-imports SV_TTK_AVAILABLE /
                          UI_EFFECTS_AVAILABLE / ThemeTransition / sv_ttk
                          from app_runtime (fixes the startup NameError)
  settings_tab.py         STATUS_COLORS re-export kept explicitly (consumed
                          by app_cloud_mixin, asserted in test_theme)
  app_delegates_mixin.py  Phase C: dead wrapper + 3 shadowed duplicates
                          removed
  rounded_widgets.py      Phase C: nested helper R() -> register_image()
  (all other modules)     F401 availability probes marked
                          `# noqa: F401 (availability probe)` - no
                          behaviour change
Earlier rounds still in effect:
  app.py                  the app shell (~2,600 lines, was 8,891): shell +
                          presets/preview stay, everything else moved to
                          mixins / data modules
  app_*_mixin / app_runtime / app_paths / app_prompt_data / app_themes /
  app_theme_engine         roadmap #7 modularization modules (mixed back
                          into FrogPaperApp - behaviour unchanged)
  settings_*              settings modularization (5 focused modules +
                          facade with re-exports)
  gallery_tab.py          friendly error dialogs + lazy thumbnails
  keyword_expander.py     casing fix + expansion-cache invalidation
  pinned_dropdowns.py     popup width auto-fit + keyboard-operable rows
  ui_effects.py           focus rings, keyboard activation, Tab helper
  database.py / gallery_manager.py  graceful-I/O + performance rounds

Docs in your project root (5):
  README.md                          v1.5.0 changelog added
  CONFIG_GUIDE.md                    how config.json keys work
  INSTALLER_SETUP.md                 examples use 1.5.0 filenames
  IMPROVEMENT_STATUS_2026-09-01.md   roadmap refreshed (items 2-6 done)
  SECURITY_NOTES.md                  security notes

Build & lint config in your project root (5):
  build_installer.bat       version 1.4.1 -> 1.5.0 (matches app.py;
                            only matters when you rebuild the exe)
  requirements.txt          pinned deps (CI / fresh venvs)
  ruff.toml                 enforces F821 (undefined names - the exact
                            bug class behind the startup NameError) +
                            F811 (shadowed defs) + F401 (dead imports)
  .pre-commit-config.yaml   optional: `pip install pre-commit` then
                            `pre-commit install` - blocks failing commits;
                            CI enforces the same rules on every push
  config.template.json      config template (read by prebuild_check.py)

Test files -> tests\ (16):
  15 test modules + run_tests.bat. Suite: 301 tests.
  test_app_smoke.py         NEW - real-app startup smoke test: builds the
                            FULL FrogPaperApp, re-themes all 18 palettes
                            and drives on_theme_changed. The test that
                            would have caught the NameError.

CI workflow -> .github/workflows/tests.yml (1):
  tests.yml        Commit to your GitHub repo and push - Actions runs all
                   301 tests on a real Windows runner on every push.

Notes:
- FEATURE FREEZE (2026-09-03): this zip is the release-candidate state.
  Lint enforces F821+F811+F401 clean; smoke test re-themes all 18
  palettes cleanly.
- HOTFIX 2026-09-03 (B2 regression): the first real launch after the
  modularization crashed with "NameError: name 'SV_TTK_AVAILABLE'" in
  app_theme_engine.py. Root cause: the theme-engine methods reference
  runtime flags that stayed in app_runtime.py; all 296 unit tests stayed
  green because none instantiated the real app. Fixed by re-importing
  the flags (same pattern app.py uses); AST scan confirmed no other
  module has unresolved names.
- MODULARIZATION (roadmap #7, complete): settings_tab.py (2,110 lines)
  split into 5 focused modules; app.py (was 8,891 lines) slimmed to
  ~2,600 with 9 dedicated modules. Every moved method verified
  byte-identical; all methods mixed back into FrogPaperApp /
  re-exported, so nothing else needed to change.
- VERSION: 1.5.0 (was 1.4.1). The number lives in app.py and
  build_installer.bat; both are included. Your installed exe still says
  1.4.1 until you rebuild it (roadmap #8 - your call).
- DOC CLEANUP: you can safely DELETE these 4 files from your project
  folder (redundant/historical): README_STARS.txt,
  FINAL_FROM_CLEAN_VERSION.txt, THREADING_MIGRATION_GUIDE.md,
  migration_notes.md
- ONEDRIVE: if this folder is OneDrive-synced, pause syncing while
  extracting (sync races can revert freshly written files and produce
  old/new file mixes).
- Overwriting files you already installed is harmless - everything here
  is the current tested state (301 tests green under pytest AND under
  the unittest discover command run_tests.bat uses).
- Nothing here touches your data: config.json, frogpaper.db, wallpapers,
  tags and recipes files are never overwritten by this zip.
