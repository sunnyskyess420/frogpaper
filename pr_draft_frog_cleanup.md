# PR Draft — Clean up stoner leftovers & make frog presence user-controllable ("Frog Dial")

> Paste this into the GitHub PR description. Branch: `fix/frog-stoner-cleanup`

## Summary

Removes leftover "stoner frog" artifacts from prompt generation and replaces the hard-coded frog defaults/biases with a user-facing probability setting. Frogs remain the app's signature — they just stop being forced on people who didn't ask for them.

## Changes

- **Stoner leftovers removed**: `"plaid stoner frog pattern"` (subjects) + `"retro stoner poster"` (styles) deleted; `weed_elements` renamed to `_weed_elements` (excluded from automatic keyword sweeps); `STYLE_ALIASES["stoner"]` removed; the `avoid` list is no longer fed back as generation vocabulary.
- **Frog force-defaults removed**: Subject box starts blank (was pre-filled "frog"); startup subject, reset button, settings text and filename fallbacks no longer default to "frog".
- **Frog Dial**: new `frog_sneak` setting (`off` / `rare` ≈5% / `classic` ≈12% default / `party` ≈50%) exposed in Settings → Auto-Generate. Replaces the hard-coded 80%/85% subject bias and 70% mood/atmosphere biases. The non-dial subject pool excludes frogs, so the configured rate is the real frog rate.
- **Frog cameo**: at half the dial chance, on random (non-explicit) runs, a tiny frog can hide in the scene details — three subtle phrasings; never fires for explicit subjects; disabled when the dial is off.
- **Daily runner fixed**: no longer feeds the whole keyword bank as input (that produced the same frog+lily compound every single day).
- **Docs**: `CONFIG_GUIDE.md` updated; `frog_cleanup_handoff.md` + simulation harnesses (`sim_leak*.py`, `check_dial.py`) included.

## Verification

- Simulated 400+ generation runs per path (`sim_leak3.py`): blank-run frog rate **92.7% → ~12%** (dial-driven); `retro stoner poster` occurrences **26.7% → 0%**; explicit subjects never receive frogs.
- Test suite: results identical to `main` baseline in a headless environment (GUI-dependent tests skipped/failed for missing tkinter only). Please run `pytest tests/ -q` with full deps.

## Notes for reviewer

- "frog" stays pinned first in the subject dropdown — intentional brand choice, not a bug.
- Nothing here touches image generation itself; prompt text only, no provider/API changes.
