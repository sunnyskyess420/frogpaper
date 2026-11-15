"""Fair random picks: every option is used before any option repeats.

`random.choice` over the option lists is uniform, but two things make the
"random" button feel stuck: the lists are clustered (18% of subjects contain
frog/toad, so five clicks show a frog 63% of the time) and plain sampling can
repeat the same value twice in a row.

This module keeps a shuffled bag per dropdown: values are dealt out one at a
time, and only when the bag is empty is it reshuffled with a different order.
Position is stored in config.json as two integers per dropdown, so a restart
continues the cycle instead of starting over.

    picker = FairPicker(load_config, save_config)
    picker.pick("subject", SUBJECT_OPTIONS)

Degrades quietly: without a usable config the bag still works for the session.
"""

from __future__ import annotations

import hashlib
import logging
import random
from typing import Callable, Iterable

logger = logging.getLogger(__name__)

STATE_KEY = "random_draw_state"


def _signature(pool: list[str]) -> str:
    """Short fingerprint of the pool, so an edited list starts a fresh cycle."""
    joined = "|".join(pool).encode("utf-8")
    return hashlib.sha1(joined).hexdigest()[:12]


class FairPicker:
    """Deals each option once per cycle, per category."""

    def __init__(self, config_loader: Callable[[], dict] | None = None,
                 config_saver: Callable[[dict], None] | None = None,
                 rng: random.Random | None = None) -> None:
        self._load = config_loader
        self._save = config_saver
        self._rng = rng or random.Random()
        self._state: dict[str, dict] = {}
        self._bags: dict[tuple, list[str]] = {}
        if self._load is not None:
            try:
                raw = self._load().get(STATE_KEY) or {}
                if isinstance(raw, dict):
                    self._state = {k: v for k, v in raw.items() if isinstance(v, dict)}
            except Exception as exc:
                logger.debug("fair picker: could not load state: %s", exc)

    # ── internals ────────────────────────────────────────────────────────
    def _bag(self, category: str, pool: list[str], seed: int, sig: str) -> list[str]:
        key = (category, seed, sig)
        bag = self._bags.get(key)
        if bag is None:
            bag = list(pool)
            random.Random(seed).shuffle(bag)
            if len(self._bags) > 64:  # old pools are dead weight
                self._bags.clear()
            self._bags[key] = bag
        return bag

    def _persist(self) -> None:
        if self._save is None:
            return
        try:
            cfg = self._load() if self._load is not None else {}
            cfg = dict(cfg or {})
            cfg[STATE_KEY] = self._state
            self._save(cfg)
        except Exception as exc:
            logger.debug("fair picker: could not save state: %s", exc)

    # ── public ───────────────────────────────────────────────────────────
    def pick(self, category: str, options: Iterable[str]) -> str:
        """Return the next unused option, reshuffling only when the bag empties."""
        pool = [str(o) for o in options if o and str(o).strip()]
        if not pool:
            return ""

        sig = _signature(pool)
        state = self._state.get(category)
        fresh = (
            not isinstance(state, dict)
            or state.get("sig") != sig
            or not isinstance(state.get("index"), int)
            or state["index"] < 0
            or state["index"] >= len(pool)
        )
        if fresh:
            state = {"seed": self._rng.randrange(1, 2**31 - 1), "index": 0, "sig": sig}
            self._state[category] = state

        bag = self._bag(category, pool, state["seed"], sig)
        value = bag[state["index"]]
        state["index"] += 1
        self._persist()
        return value

    def remaining(self, category: str, options: Iterable[str]) -> int:
        """How many options are still unused in the current cycle."""
        pool = [str(o) for o in options if o and str(o).strip()]
        state = self._state.get(category) or {}
        if not isinstance(state, dict) or state.get("sig") != _signature(pool):
            return len(pool)
        index = state.get("index") or 0
        return max(0, len(pool) - index)

    def reset(self, category: str | None = None) -> None:
        """Forget the current cycle (all categories when *category* is None)."""
        if category is None:
            self._state.clear()
            self._bags.clear()
        else:
            self._state.pop(category, None)
        self._persist()


def pick_colour_pair(picker: FairPicker | None = None) -> tuple[str, str]:
    """A valid (family, variation) pair, dealt fairly when a picker is given."""
    import app_prompt_data as data

    families = [f for f in data.COLOR_FAMILIES if f]
    if picker is None:
        family = random.choice(families)
    else:
        family = picker.pick("color_family", families)

    variations = data.color_variation_options(family)
    if picker is None:
        variation = random.choice(variations)
    else:
        variation = picker.pick(f"color_variation:{family}", variations)
    return family, variation
