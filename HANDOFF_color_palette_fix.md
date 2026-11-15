# Handoff — FrogPaper: colour palette is ignored in generated prompts

Paste this whole file into Devin / z.ai / Cline as the task brief. It is written to be
self-contained: no prior conversation needed.

---

## 1. What the project is

**FrogPaper** is a Windows desktop wallpaper generator (Python 3.13, Tkinter, Pillow).
The user picks dropdowns — Subject, Mode, Lighting, Color Family + Color Variation,
Setting, Atmosphere — and the app assembles a long structured prompt, sends it to
**Pollinations.ai** (free, no API key), and saves a 1920×1080 PNG to `wallpapers/generated/`.

Repo root (this machine): `C:\Users\alive\OneDrive\Desktop\FrogPaper Dropdown fix\frogpaper-main`
Relevant modules: `prompt_builder.py`, `prompt_validator.py`, `prompt_refiner.py`,
`cloud_providers.py`, `wallpaper_generator.py` (`_generate_pollinations`), `prompt_tab.py`.

## 2. The reported bug

Four generated wallpapers came back almost monochrome — grey fog, no amber, no blue,
no fuchsia — even though the log showed the colour was selected:

```
Generating: subject='cat' style='stylized' lighting='arctic aurora'
setting='autumn forest path' atmosphere='forest fog' mood='eerie'
color='bold amber' mode='stylized'
```

The colour selection *was* reaching the prompt text. It was simply having no effect.

## 3. Root cause (measured, not assumed)

Two independent problems in `build_prompt()`:

1. **The user's explicit palette was never strengthened.** `prompt_validator.strengthen_color()`
   existed and was applied to *theme* palettes inside `theme_mixer.py`, but the palette the
   user picks in the sidebar went into the prompt as the bare tag `bold amber.`
2. **The palette was section 4 of 8, landing at word 53 of 118** — after ~50 words of
   subject-lock boilerplate ("Eerie cat is fully visible… Nothing obscures or competes with
   Eerie cat"), then `forest fog` and `strong silhouettes`. By the time the model reads the
   colour it has already committed to a dark, foggy, silhouette scene.

Evidence. Same prompt, same model (`flux-realism`), same seed (98765), prompt text varied by
exactly one factor. Metric: **mean chroma** = mean of `max(R,G,B) - min(R,G,B)` over a 320px
downscale, range 0–255 (0 = grey, ~100 = vivid).

| Prompt variant | mean chroma |
|---|---|
| Shipped prompt (`bold amber` at word 53) | **9.4** |
| Raw text + "colour palette" label, moved to front | 13.3 |
| `strengthen_color` wording, original position | 24.1 |
| `strengthen_color` wording + moved to front | **35.3** |
| Short plain prompt with colour (control) | 57.6 |

Takeaways: moving the raw words forward alone does nothing (13.3). The phrasing is what
lands (24.1). Both together are best (35.3). `enhance=true` vs `false` made no difference
(34.7 both, identical cached bytes) — do not touch that setting for this bug.

## 4. What is already changed (current state of the code)

### `prompt_builder.py`

Guarded import now includes `strengthen_color`:

```python
# Import prompt validator for audit functionality
try:
    from prompt_validator import audit_prompt_variables, log_prompt_audit, get_audit_warnings, format_audit_summary, strengthen_color  # noqa: F401  (availability probe)
    VALIDATOR_AVAILABLE = True
except ImportError:
    VALIDATOR_AVAILABLE = False
```

After palette extraction (line ~500):

```python
    # Strengthen the palette into an explicit "… palette with … tones" phrase.
    # A bare colour word ("bold amber") is largely ignored by image models and
    # comes back grey; the explicit palette phrasing is what actually lands.
    # Idempotent for theme palettes that theme_mixer already strengthened.
    if palette and VALIDATOR_AVAILABLE:
        try:
            palette = clean_text(strengthen_color(palette)) or palette
        except Exception:
            logger.debug("strengthen_color failed for %r", palette, exc_info=True)
```

Assembly order (line ~665) — palette is now second:

```python
    sections = [
        s1_subject,
        s4_palette,      # colour before scene/lighting so the model commits to it first
        s2_scene,
        s3_lighting,
        s5_composition,
        s6_style,
        s7_quality,
        s8_exclusions,
    ]
```

Module docstring and `build_prompt` docstring were updated to
`mood+subject → palette → scene → lighting → composition → style → quality → negatives`.

### `prompt_refiner.py`

This module parses a built prompt back into sections and reassembles it (the "refine"
button). It mirrored the old order and would have silently undone the fix, so:

* `parse_prompt()` free-clause assignment is now **content-first**: palette/lighting/mood
  are matched by keyword before anything falls back to scene. The old rule
  "the first free clause is always scene" is gone — it mis-filed the now-leading palette.
* `reassemble_prompt()` key order is now
  `subject, palette, scene, lighting, mood, composition, style, quality, main`.
* Both docstrings updated.

### `tests/test_prompt_builder.py`

* `test_fixed_section_order` — now asserts `subject < palette < scene < style < quality`,
  matching `refreshing blues tones` (the strengthened form of the fixture's `cool blues`).
* New: `test_user_color_becomes_explicit_palette_phrase`, `test_theme_palette_strengthening_is_idempotent`.
* `test_user_color_beats_theme_palette` — now asserts `"pink" in prompt.lower()` instead of
  the literal `"neon pink"` (see §5 for why).

Status: `python tests\test_prompt_builder.py` → **41 tests, OK**. `prompt_builder`,
`prompt_refiner` and `prompt_validator` all import clean.

Verified end-to-end through the real builder: the cat prompt now renders a warm amber autumn
forest (mean chroma 34.7, up from 9.4).

## 5. The open tradeoff — exact modifier words vs. palette phrasing

`build_prompt()` now **replaces** the user's raw colour with
`prompt_validator.strengthen_color()` output. That is what makes colour show up, but it can
swallow the user's exact wording.

Current behaviour of the mapping table `_COLOR_STRENGTHENING` in `prompt_validator.py`:

| UI value | Emitted phrase | Verdict |
|---|---|---|
| `bold amber` | `bold warm amber palette with golden honey tones` | good — keeps "bold" |
| `vivid crimson` | `vivid crimson red palette with deep blood-red tones` | good |
| `electric blue` | `electric blue palette with cool azure tones` | good |
| `muted gold` | `muted golden glow palette with warm amber tones` | good |
| `pastel teal` | `teal soft pastel palette with gentle muted tones` | keeps "pastel", but "soft"+"pastel" is redundant |
| `smoky fuchsia` | `smoky fuchsia palette` | good |
| **`neon pink`** | **`pink-dominant palette with soft pink hues`** | **bad — "neon" deleted, intensity flipped to "soft"** |
| **`neon green`** | **`emerald green palette with verdant tones`** | **bad — "neon" deleted** |

Why `neon` specifically: `strengthen_color()` deliberately strips
`_LIGHTING_QUALIFIER_WORDS = {neon, glowing, backlit, bioluminescent, blacklight,
cinematic, volumetric}` so those words are not "prepended as palette modifiers". Reasonable
when they arrive from a lighting field; wrong when the user typed them into the colour field.
The lookup then falls through to the base colour key (`pink` → soft/pastel mapping), which is
why intensity is not just lost but inverted.

### Options

**A. Leave it.** Consistent with the pre-existing `theme_mixer` path, zero risk, but "neon
pink" produces a muted pastel — a visible regression for that combination.

**B. Preserve stranded modifiers (small, surgical).** In `strengthen_color()`, after the
strengthened phrase is chosen, re-attach any raw modifier token that is missing from the
result, e.g. `neon` + `pink-dominant palette with vivid pink hues`. Requires a small
intensity fix-up so `soft` is swapped out when the modifier implies high saturation
(`neon`, `vivid`, `electric`, `fluorescent`). ~15 lines, testable without image generation.

**C. Rework `_COLOR_STRENGTHENING`** so all 47 UI modifiers survive with correct intensity.
Highest quality, but it is a ~63 colour-family × 47 modifier surface and really needs visual
QA per family to avoid regressions elsewhere.

Recommendation: **B** if the goal is to stop lying about the user's words; **C** only if
someone can eyeball generated samples per family. Whichever is chosen, keep the palette
*label* (`… palette with … tones`) — that is the part that made colour appear at all, and it
must stay ahead of the scene clause.

Nothing else depends on the raw string: `prompt_validator.audit_prompt_variables()` accepts
the strengthened phrase as a match for the raw UI value (via `_candidate_phrases`), so no
false "colour missing" warnings appear in the UI today, and that stays true for B and C.

## 6. Environment gotchas

* **No git repo here.** `git log` fails — there is no history or diff to consult. Snapshot
  the two files before editing.
* Running scripts: `python -c "import prompt_builder"` fails from this shell because cwd is
  not on `sys.path`. Use `sys.path.insert(0, os.getcwd())` or run a file that does it.
* `pytest` is **not installed**. Tests are `unittest`; run `python tests\test_prompt_builder.py`.
  `python -m unittest tests.test_prompt_builder` fails for the same `sys.path` reason.
* `tkinter` is absent in this CLI environment, so anything importing `prompt_tab`, `utils`,
  `style_transfer` or `app.py` cannot be imported here. Do not try to run GUI tests; edit and
  reason, then hand back for a manual run.
* Pillow warns that `Image.getdata()` is deprecated (harmless).
* Pollinations free tier is currently flaky: HTTP 402 / 429 are common, and a pollinations.ai
  watermark appears even with `nologo=true`. Leave ≥40 s between generation requests, retry
  on 402/429/503, and keep test images small (1024×576).
* Identical prompt + seed returns a byte-identical cached image. Two "different" cat
  wallpapers in `wallpapers/generated/` were identical files for this reason — do not read
  that as a duplicate-save bug.
* `_MODE_CONFIG[...]["quality_lead"]` already contains "vivid saturated colours". It did not
  prevent grey output; do not "fix" colour by adding more emphasis words there.

## 7. Verification recipe

```python
import sys, os; sys.path.insert(0, os.getcwd())
import prompt_builder as pb
theme = {"theme_id": 1, "sentence": "on an autumn forest path, forest fog",
         "mood": "eerie", "subject_negatives": "",
         "components": {"subject": "cat", "style": "stylized", "lighting": "arctic aurora",
                        "color": "bold amber", "atmosphere": "forest fog", "mood": "eerie"}}
prompt = pb.build_prompt(theme, style_mode="stylized")["prompt"]
# expect: "... Nothing obscures or competes with Eerie cat. bold warm amber palette with
#           golden honey tones. on an autumn forest path, forest fog. arctic aurora. ..."
```

Then GET
`https://image.pollinations.ai/prompt/<quote(prompt)>?model=flux-realism&width=1024&height=576&nologo=true&enhance=true&seed=98765`
and compute mean chroma on a 320px downscale. Target: **> 30**. Anything near 10 means the
palette has drifted back behind the scene clause or lost its strengthening.
