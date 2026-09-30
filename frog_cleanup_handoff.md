# FrogPaper — Frog/Stoner Leakage Cleanup · Handoff

**Date:** 2026-09-29 · **Working copy:** shallow clone of `sunnyskyess420/frogpaper` @ upstream `1fb7b8d`
**Patch files:** `frog_cleanup.diff` (raw diff → `git apply`) · `0001-Clean-stoner-leftovers-*.patch` (mailbox → `git am`)
**Status:** Part 1 DONE (stoner leftovers + frog force-defaults). Part 2 PENDING (frog bias → "Frog Dial"). **Nothing pushed upstream — owner wants review first.**

---

## TL;DR for the next AI

FrogPaper's prompt generator inherited the owner's original "stoner frog" concept. Two leak classes were found and quantified with a local harness (no APIs, no image generation, $0):

1. **Stoner leftovers** — `"plaid stoner frog pattern"` (subjects pool), `"retro stoner poster"` (styles pool), a `weed_elements` block, `STYLE_ALIASES["stoner"]`, and the `avoid` list being fed back as generation keywords. Measured pre-fix: **80/300 (26.7%)** of daily-runner prompts got style `retro stoner poster`.
2. **Frog force-defaults** — subject box pre-filled `"frog"` on launch + theme_mixer "frog bias" branches (80%/85% subject, 70% mood/atmosphere). Measured pre-fix: **92.7%** of blank runs produced frogs; mood `"playful"` **300/300** when subject=frog.

**Owner's accepted direction:** frogs stay THE brand, but must not be forced. User-paid outputs must respect user intent. The frog bias becomes a user-facing probability ("Frog Dial"). Do not remove frogs — make them optional/probabilistic.

## DONE in this working copy (2026-09-29)

| File | Change |
|---|---|
| `keywords.json` | Removed `"plaid stoner frog pattern"` (subjects) and `"retro stoner poster"` (styles). Renamed `weed_elements` → `_weed_elements` (+ `_weed_elements_note`) so the `_` prefix excludes it from `daily_runner.load_all_keywords()` and `keyword_expander._load_keywords()`. |
| `theme_mixer.py` | Removed `STYLE_ALIASES["stoner"]` → `"retro stoner poster"` mapping. |
| `app.py` | Subject box no longer pre-filled with `"frog"` (all 3 build paths now `insert(0, "")`); `startup_subject` default `"frog"` → `""` (init + auto-generate fallback `or ""`). |
| `settings_persistence.py` | Saved `startup_subject` no longer falls back to `"frog"`. |
| `prompt_tab.py` | "Reset Quick Build fields" no longer sets subject to `"frog"`. |
| `config.template.json` | `"startup_subject": "frog"` → `""`. |
| `app_generation_mixin.py` | filename/subject fallback `'frog'` → `'wallpaper'`. |
| `daily_runner.py`, `keyword_expander.py` | `avoid` block (negatives: bong/rig/pipe/text…) no longer loaded as generation vocabulary. |

**Post-fix verification (same harness):** `retro stoner poster` picked **0/300** (was 80/300). JSON valid; all edited files pass `python -m py_compile`. **NOT runtime-tested** (analysis env lacks tkinter) — run the test suite.

## REMAINING — next tasks

### T1 (main task) — Replace frog-bias blocks with the "Frog Dial" (`theme_mixer.py`)
Find and remove/replace (search strings provided — line numbers shift):
- `# General bias toward frog subjects even without explicit frog keywords (85% chance)` — the fixed 85% frog pick branch.
- The `# Bias toward frog subjects when frog detected in keywords (80% chance)` branch above it.
- `frog_moods = ["mystical", "serene", "whimsical"]` block (70% frog moods).
- Frog atmosphere block (`env_atmospheres = [...]`, 70%).
- `frog_detected and random.random() < 0.6` scenic bias.
- Frog scenic handling in `build_sentence()` (also rename the misleading variable `fish_detected`).
- Review with owner: `STYLE_ALIASES["frog"]`, `MOOD_ALIASES["frog"]`, `COMPOSITION_ALIASES["frog"]` — currently make every explicit-frog image samey (`"playful"` 100%).
- **Keep:** frog pinned first in the subject dropdown (`app_prompt_data.py` sort), frog logo/sounds/styles/styles — that's the brand.

Proposed design (owner to confirm numbers + UI placement):
- New setting `frog_sneak`: **Off / Rare (p≈0.05) / Classic (p≈0.12, suggested default) / Frog Party (p≈0.5)**; persist like other settings (`settings_persistence.py` + settings UI).
- Rule: explicit subject set → never inject frog (unless the subject itself contains "frog"). Subject blank → with probability `p` pick a frog subject; else normal pool.
- Owner delight feature (requested): small chance a frog "sneaks into" an image as a background detail. Check `prompt_builder.py` scene support first; tie to the dial.

### T2 — frog shortlist filter
`frog_subjects = [s for s in kw["subjects"] if "frog" in s.lower()]` — becomes redundant once T1 lands; delete along with the bias branches.

### T3 — Do NOT "clean" these (they are correct)
`prompt_builder.py` frog anatomy lock (~L411–417) and frog environment handling (~L576–582): correct when the subject actually is a frog. Leave as-is.

### T4 — Stoner-adjacent vocabulary (owner decision)
Review: mood `"trippy"` / `"chill"`; styles `"psychedelic"` / `"blacklight glow"` / `"cozy vapor lounge"`; atmospheres `"smoke-filled room"` / `"neon lily pond"`; colors `"acid green"` / `"emerald smoke"` / `"lavender haze"`; `_weed_elements` block (delete if unwanted). `negative_presets.json` "bong" entry is a negative — fine as-is.

### T5 — Verification
- `python -m pytest tests/ -q` (CI expectations: `.github/workflows/tests.yml`). Some tests need tkinter/PIL.
- Re-run harnesses in this working copy: `python sim_leak.py`, `python sim_leak2.py` (tkinter stub included). Expect: 0 stoner styles; frog rate governed by the dial after T1.
- Manual: launch app → subject box blank; generate with blank subject; scan prompts for "stoner" occurrences.
- Note: existing users' saved `config.json` may still hold `"startup_subject": "frog"`; optionally migrate (blank it) or leave — minor.

## Applying the patch
```bash
git checkout -b fix/frog-stoner-cleanup   # from up-to-date main
git apply frog_cleanup.diff               # or: git am 0001-Clean-stoner-leftovers-*.patch
python -m pytest tests/ -q
```
**Do not push without owner sign-off.**

## Meta / artifacts
- Repro harnesses: `sim_leak.py`, `sim_leak2.py` (root of this working copy; stub tkinter so they run without a GUI env).
- This working copy is a shallow clone (`--depth 50`); `git am` may need the exact parent — `git apply` always works.
- All analysis was local text processing: no images generated, no provider APIs called, no money spent.

---

## UPDATE 2026-09-29 (part 2) — Frog Dial core landed

Second commit on `fix/frog-stoner-cleanup` (`0002-*.patch`; `frog_cleanup.diff` now covers both commits):

- `theme_mixer.py`:
  * Deleted the 80%/85% frog-subject bias branches → replaced with **Frog Dial** check: `if frog_sneak > 0 and random.random() < frog_sneak: pick frog subject`.
  * New `get_frog_sneak_probability()` reads `config.json` key `"frog_sneak"`: `off`=0 · `rare`=0.05 · `classic`=0.12 (default) · `party`=0.5.
  * General (non-dial) subject pool now **excludes frog entries**, so the dial number is the true frog rate on blank runs.
  * Deleted the 70% frog mood block and 70% frog atmosphere block (normal pools now).
  * Removed `"frog"` from `MOOD_ALIASES` (was forcing mood `"playful"` 100% of frog runs), `STYLE_ALIASES`, `COMPOSITION_ALIASES` → "frog" now classifies as a plain subject word.
  * Renamed `fish_detected` → `frog_detected` in `build_sentence()`.
- `daily_runner.py`: no longer feeds the whole keyword bank as user keywords (that forced identical frog+lily compounds every day).
- `config.template.json`: added `"frog_sneak": "classic"`.

**Verified (harness `sim_leak3.py`):** blank-subject frog rate **11.8%** (was 92.7%); daily-style runs: 45 distinct subjects (was a single repeated sentence); explicit-frog moods varied (was "playful" 100/100); zero stoner styles. All files compile.

**Still remaining:**
1. Settings-screen toggle for `frog_sneak` (currently users edit `config.json` manually; `save_settings` preserves the key since it starts from `load_config()`).
2. Optional "background frog detail" delight feature (owner's request) — needs `prompt_builder.py` scene support; gate by dial.
3. T4 vocabulary review (owner decision) + `_weed_elements` delete-or-keep; `negative_presets.json` bong entry is fine as a negative.
4. Run project tests (`pytest tests/ -q`) in a full environment; then owner review → PR.
5. Optional: review `"cat"` alias entries (MOOD/STYLE/COMPOSITION) for the same consistency treatment.

---

## UPDATE 2026-09-29 (part 3) — Settings toggle + final default cleanups

Third commit on `fix/frog-stoner-cleanup`:

- `app.py`: new `app.frog_sneak_var` (initialized from config, default `"classic"`); stale comment fixed.
- `settings_categories.py`: added a **"Frog sneak" dropdown** (off/rare/classic/party) to the Auto-Generate settings card; helper text no longer says "leave as 'frog'".
- `settings_persistence.py`: persists `frog_sneak` on save; remembered-settings subject fallback no longer `"frog"`; comment updated.
- `check_dial.py`: verification script for the dial levels.

**Verified:** `get_frog_sneak_probability()` returns 0 / 0.05 / 0.12 / 0.5 for off/rare/classic/party, falls back to 0.12 for invalid values. All edited files compile.

**Remaining (final):** run project tests in a full env (`pytest tests/ -q`), owner review → PR. Optional: background-frog delight feature, T4 vocabulary review.

---

## UPDATE 2026-09-29 (part 4) — Sneaky frog cameo (owner's delight feature)

Fourth commit on `fix/frog-stoner-cleanup`:

- `theme_mixer.py`: when a random (non-explicit) run didn't pick a frog subject, a **frog cameo** can still sneak in: at half the dial chance, one of 3 subtle phrasing variants is appended to the scene ("with a tiny frog subtly hidden in the scene details", etc.). Never fires for explicit subjects; dial "off" disables it entirely.
- `sim_leak3.py`: now also counts cameos.
- Tests: ran the suite locally — results **identical to the `main` baseline** in this environment (3 failures / 14 errors / 71 skipped, all from missing tkinter/GUI deps in the analysis box, not from these changes). Re-run in a full env before release.

**Numbers (classic default):** ~12% frog subject + ~5% cameo ⇒ roughly 1 in 6 random images has a frog somewhere; explicit subjects never get one unless the user typed a frog. Tweak rate in `theme_mixer.py` (`frog_sneak * 0.5`) or phrasing list if desired.

**Remaining:** run tests in a full env; owner review → PR.

---

## UPDATE 2026-09-29 (part 5) — Docs + PR draft

Fifth commit on `fix/frog-stoner-cleanup`:

- `CONFIG_GUIDE.md`: `startup_subject` default corrected to blank; new `frog_sneak` row documented.
- `pr_draft_frog_cleanup.md`: ready-to-paste PR title/body for the owner.

**Remaining:** full-env test run; open the PR (draft provided).
