# Dropdown improvement plan — implementation status

Companion to `FrogPaper-dropdown-improvement-plan.md` (kept outside the repo).
Last updated after the instrumentation pass.

## Done

**Phase 0 — baseline tool**
`tools/option_audit.py` reports option counts, duplicates, cross-list overlap,
leading-case anomalies, near-duplicate pairs, misfiled/low-control terms, colour
validity and real usage. Exit code is 1 on a hard defect, so it can gate CI.

```
python tools/option_audit.py              # report
python tools/option_audit.py --write-docs # refresh docs/option-baseline.md
```

**Phase 1 — instrumentation**
- `image_events` table (`database.py`): one row per option field per event, so
  every pick stays queryable after the image is gone.
- `image_events.py`: `log_generation`, `log_favorite`, `log_wallpaper`,
  `log_delete`, plus `counts()` — per value: uses, favourites, deletes,
  wallpaper sets, split by source.
- Every generation is recorded: `_generate_image_thread` now saves parameters
  for *all* images (falling back to a live snapshot of the eight fields when a
  caller passes no `ui_values`), and `daily_runner.py` records its own runs with
  `source="daily_runner"`.
- `source` is threaded through the app: `manual` by default, `startup_auto` from
  the startup generator, `random_theme` after the dice button.
- Deleting an image now snapshots its parameters into the event log *before*
  the `prompt_params` row is removed — the strongest negative signal is no
  longer thrown away.
- Favourites (add and remove, including deleting a favourite) and wallpaper
  sets are logged. Wallpapers are logged inside `set_wallpaper()`, so the
  gallery button, the slideshow and the tray all count.
- `remember_settings` now defaults to on (template, app default, settings
  loader); an existing config keeps whatever the user saved.

**Phase 2 — report**
`tools/option_report.py` prints uses, favourites, deletes, wallpaper sets,
sources, never-used options and hand-typed values per dropdown. Databases that
predate the event log fall back to `prompt_params` with a clear note.

```
python tools/option_report.py --since 2026-11-01 --top 20
python tools/option_report.py --field mood --top 0
```

The equivalent SQL, for anyone who wants it raw:

```sql
-- uses / deletes per value and source (favourites and wallpapers are
-- image-level rows joined back on image_path; see image_events.counts())
SELECT field, value, source,
       SUM(event = 'generated') AS uses,
       SUM(event = 'deleted')   AS deletes
FROM image_events
WHERE field <> ''
GROUP BY field, value, source;
```

**Phase 3 — repair (complete)**
- `unset haze` typo, near-duplicate pairs, genre words in Mood and the 13
  lighting terms in Style were fixed before this pass.
- Leading-case anomalies fixed in Setting (8 entries) and Lighting (2), with
  `canonical_option()` mapping the old spellings so saved sessions, presets and
  restored configs still resolve.
- `dark` / `sinister` collapsed to `dark`; `contemplative` dropped.
- `arctic aurora` moved from Lighting to Atmosphere, where the weather entries
  (`rain`, `snow`, `storm front`) now sit in their own block, `WEATHER_ATMOSPHERES`.

**Phase 4 — colour validity**
- Retired adjectives came back where they carry meaning (`high contrast`,
  `translucent`, `hazy`, `dusty`, `vintage`, `sepia`, `frosted`, `desaturated`,
  `faded`, `monochrome`); 33 variations offered instead of 23.
- A validity matrix replaces the blanket prune: `is_valid_color_combo()` blocks
  contradictions per family (`deep white`, `neon brown`, `pastel black`, ...),
  `color_variation_options()` narrows the second dropdown to the family, and
  `pick_color_pair()` keeps every random path valid.
- Retired colour words stay resolvable: `COLOR_FAMILIES_PARSE` /
  `COLOR_VARIATIONS_PARSE` are what `parse_color_value()` receives, so a preset
  saved as `washed out forest green` still produces a palette instead of `""`.

**Phase 6 — locks**
`tests/test_option_hygiene.py` (25 tests) covers every section-3 defect,
`tests/test_image_events.py` (8 tests) covers the event log including the
delete path, and `tests/test_golden_prompts.py` snapshots prompt text for one
theme per mode plus five awkward cases. Regenerate deliberately:

```
python tests/test_golden_prompts.py --update
```

**Phase 5 — UX (partial)**: type-to-filter and recently-used are in.
- Every dropdown with more than `FILTER_MIN_ITEMS` (12) options opens with a
  filter box at the top; typing narrows the list as you go, Enter takes the top
  match, Escape closes. All seven lists qualify (33–91 options each).
- A "🕘 RECENTLY USED" section (last 5 picks, newest first) sits under the
  favourites and above the full list. It persists in `config.json` under
  `recent_options` and is per dropdown.
- Choices are remembered on click, on Enter, on keyboard selection and on typed
  free text, so the row reflects how you actually pick.
- Still open: grouping by category (needs a category for each of the 89
  subjects) and ordering by usage (needs logged picks first).

## Random draw fairness

The dice button (and the startup randomiser) now deals from a shuffled bag per
dropdown (`random_pick.py`) instead of `random.choice`: every option is used
once before any repeats, and the position is stored in `config.json` under
`random_draw_state`, so a restart continues the cycle. Editing a list starts a
fresh cycle automatically.

Why it was needed: 89 random clicks used to hit 61 distinct subjects, with one
subject appearing 4 times. The bag makes that 89 of 89, no repeats.

Caveat worth remembering: the bag changes *order*, not *mix*. 18% of the subject
list is frog/toad entries, so a frog still shows up in roughly two of every five
clicks - that is the list composition, not the randomiser.

## Picks that got mangled (found while answering "is random biased?")

- **Mood was breaking the subject phrase.** `theme_mixer` expanded every mood
  into a comma chain for the scene clause (`epic` -> `grand, epic, monumental`)
  and then handed the same chain to the subject anchor, which keeps only the
  first word. The prompt opened with `Single main subject: Grand, frog` for all
  46 moods. The anchor now receives the raw mood (`Epic frog`); the scene clause
  keeps the rich phrasing. Covered by `tests/test_mood_anchor.py`.
- **The location-subject branch is dead code for the current lists.**
  `build_sentence()` clears `setting` and `atmosphere` when the subject matches
  `_ENV_SUBJECT_TOKENS`, but none of the 89 subjects match those tokens any more
  (the pruned entries - `crystal cave`, `underwater city`, `ancient temple` -
  were the ones that did). Measured over 40 explicit runs: subject, setting,
  lighting, atmosphere and style survived into the final prompt every time;
  colour is reworded (never dropped) and mood was the only genuine loss.
- **The palette really is stated twice** - once as its own early section, once
  inside the scene sentence. Left alone on purpose: sitting the palette early
  was a deliberate earlier fix ("a colour word at the end of the prompt is
  ignored"), so removing the early copy would undo it.

## Deliberately not done

- **Phase 4 — pruning to target sizes.** Subject is 89 (target 70–80) and
  Setting 90 (target 80). The rule is "survives if uses ≥ 2", and the event log
  only starts collecting now, so the first honest prune waits for a couple of
  weeks of rows.
- **Phase 4 — colour down to ~12 variations per family.** The matrix replaced
  arbitrary narrowing (1,980 combos, 29 blocked). If the count itself is the
  problem, cut `COLOR_VARIATIONS` and the matrix follows.
- **Phase 5 — UX (rest).** No grouping by category, no usage ordering, no
  "add typed value to the list" action. Pins existed before; filter and recents
  are new.
- **Phase 6 — changelog and version bump.** Done in 1.9.0: `RELEASE_NOTES_v1.9.0.md`,
  README changelog entry, `APP_VERSION` and the installer script bumped together.

## Deviations worth knowing

- The plan asked for a `seed` field. No provider here exposes a seed parameter,
  so a seed would be fiction; `prompt_hash` (first 16 hex chars of SHA-1 over
  the prompt) is stored instead, which at least groups identical requests.
- `image_events` keeps one row per field per event, not one row per image:
  that is what makes "uses by option value" a single grouped query.

## Test notes

`%LOCALAPPDATA%\Python\bin\python.exe` (3.14) has Tkinter, Pillow and
SQLAlchemy, so `python -m unittest discover -s tests -t .` runs the whole suite
there — 755 tests green. The bundled AutoClaw Python can run the data and tool
tests only (no Tkinter, no SQLAlchemy), and earlier notes about needing two
interpreters are obsolete.
