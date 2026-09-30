"""Repro harness: run FrogPaper's real theme generation to expose frog/stoner bias."""
import sys, os, types, random

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

# --- Stub tkinter (utils.py imports it at module level for type hints) ---
tk = types.ModuleType("tkinter")
class _Dummy: pass
for _n in ("Tk", "Toplevel", "Misc", "Widget", "Frame", "Label", "Canvas", "StringVar", "BooleanVar", "Entry", "Text", "PhotoImage"):
    setattr(tk, _n, type(_n, (_Dummy,), {}))
sys.modules.setdefault("tkinter", tk)
for _m in ("tkinter.ttk", "tkinter.filedialog", "tkinter.messagebox", "tkinter.font"):
    sys.modules.setdefault(_m, types.ModuleType(_m))

import theme_mixer

print("=" * 72)
print("A) Static leak inventory")
print("=" * 72)
kw = theme_mixer.load_keywords()
frog_subjects = [s for s in kw.get("subjects", []) if "frog" in s.lower()]
print(f"subjects containing 'frog' ({len(frog_subjects)}):")
for s in frog_subjects:
    print("   -", s)
print()
print("styles pool stoner-ish:", [s for s in kw.get("styles", []) if "stoner" in s.lower() or "psychedelic" in s.lower() or "blacklight" in s.lower()])
print("style alias 'stoner' ->", theme_mixer.STYLE_ALIASES.get("stoner"))
print("weed_elements:", kw.get("weed_elements"))

print()
print("=" * 72)
print("B) daily_runner path: ALL keywords.json values passed as user_keywords")
print("=" * 72)
import daily_runner
allkw = daily_runner.load_all_keywords()
print("total keywords loaded:", len(allkw))
stonerish = [w for w in allkw if any(x in w.lower() for x in ("stoner", "weed", "bong", "joint", "grinder"))]
print("stoner/weed-ish keywords fed in:", stonerish)
tokens = theme_mixer.tokenize_keywords(allkw)
print("'frog' token present:", "frog" in tokens)
buckets = theme_mixer.sort_user_keywords(allkw)
alias_hits = [theme_mixer.STYLE_ALIASES[t] for t in buckets.get("styles", []) if t in theme_mixer.STYLE_ALIASES]
print("style bucket tokens:", sorted(set(buckets.get("styles", []))))
print("style alias hits that can be chosen:", sorted(set(alias_hits)))
print()
random.seed(42)
for trial in range(3):
    t = theme_mixer.generate_themes(count=1, user_keywords=allkw)[0]
    c = t["components"]
    print(f"--- daily runner trial {trial + 1} ---")
    print("  subject:   ", c["subject"])
    print("  style:     ", c["style"])
    print("  mood:      ", c["mood"])
    print("  atmosphere:", c["atmosphere"])

print()
print("=" * 72)
print("C) GUI default path: sidebar subject pre-filled 'frog' (explicit_subject='frog')")
print("=" * 72)
random.seed(1)
for trial in range(3):
    t = theme_mixer.generate_themes(
        count=1, user_keywords=["frog"], subject_lock=True,
        custom_subject="frog", explicit_subject="frog")[0]
    c = t["components"]
    print(f"--- GUI default trial {trial + 1} ---")
    print("  subject:   ", c["subject"])
    print("  style:     ", c["style"])
    print("  mood:      ", c["mood"])
    print("  atmosphere:", c["atmosphere"])

print()
print("=" * 72)
print("D) No explicit subject at all -> 'general frog bias' branch")
print("=" * 72)
random.seed(7)
for trial in range(5):
    t = theme_mixer.generate_themes(count=1, user_keywords=[], subject_lock=True,
                                    custom_subject="", explicit_subject="")[0]
    print(f"  trial {trial + 1}: subject = {t['components']['subject']!r}")
