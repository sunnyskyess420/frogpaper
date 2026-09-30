"""Quantify leak rates + show final prompt text for default frog subject."""
import sys, os, types, random
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

tk = types.ModuleType("tkinter")
class _Dummy: pass
for _n in ("Tk", "Toplevel", "Misc", "Widget", "Frame", "Label", "Canvas", "StringVar", "BooleanVar", "Entry", "Text", "PhotoImage"):
    setattr(tk, _n, type(_n, (_Dummy,), {}))
sys.modules.setdefault("tkinter", tk)
for _m in ("tkinter.ttk", "tkinter.filedialog", "tkinter.messagebox", "tkinter.font"):
    sys.modules.setdefault(_m, types.ModuleType(_m))

import theme_mixer
import daily_runner
from prompt_builder import build_prompt

N = 300
allkw = daily_runner.load_all_keywords()

# 1) daily runner: stoner style rate + frog subject rate
random.seed(123)
c_style, c_subj = Counter(), Counter()
for _ in range(N):
    t = theme_mixer.generate_themes(count=1, user_keywords=allkw)[0]
    c = t["components"]
    c_style[c["style"]] += 1
    c_subj[c["subject"]] += 1
print("=== daily_runner simulations (N=%d) ===" % N)
print("top styles:", c_style.most_common(6))
print("'retro stoner poster' picked:", c_style.get("retro stoner poster", 0), "times (%.1f%%)" % (100 * c_style.get("retro stoner poster", 0) / N))
print("subject was frog-ish:", sum(v for k, v in c_subj.items() if "frog" in k), "/", N)
print("top subjects:", c_subj.most_common(3))

# 2) GUI default: mood distribution
random.seed(456)
c_mood = Counter()
for _ in range(N):
    t = theme_mixer.generate_themes(count=1, user_keywords=["frog"], subject_lock=True,
                                    custom_subject="frog", explicit_subject="frog")[0]
    c_mood[t["components"]["mood"]] += 1
print()
print("=== GUI default (subject='frog') simulations (N=%d) ===" % N)
print("mood distribution:", c_mood.most_common(8))

# 3) no subject at all: frog rate
random.seed(789)
frog_n = 0
for _ in range(N):
    t = theme_mixer.generate_themes(count=1, user_keywords=[], subject_lock=True,
                                    custom_subject="", explicit_subject="")[0]
    if "frog" in t["components"]["subject"].lower() or "toad" in t["components"]["subject"].lower():
        frog_n += 1
print()
print("=== no-subject fallback (N=%d): frog/toad chosen %d times (%.1f%%) ===" % (N, frog_n, 100 * frog_n / N))

# 4) final prompt text for the default frog subject
t = theme_mixer.generate_themes(count=1, user_keywords=["frog"], subject_lock=True,
                                custom_subject="frog", explicit_subject="frog")[0]
p = build_prompt(t, style_mode="stylized")
print()
print("=== FINAL PROMPT (default path) ===")
print(p["prompt"])
print()
print("=== FINAL NEGATIVE PROMPT ===")
print(p["negative_prompt"])

# 5) demo: stoner style reaches the final prompt sentence for daily path
random.seed(42)
for _ in range(50):
    t = theme_mixer.generate_themes(count=1, user_keywords=allkw)[0]
    if t["components"]["style"] == "retro stoner poster":
        p2 = build_prompt(t, style_mode="stylized")
        print()
        print("=== DAILY-RUNNER SAMPLE WITH STONER STYLE ===")
        print("sentence:", t["sentence"])
        print("prompt:", p2["prompt"])
        break
