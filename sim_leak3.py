"""Post-dial verification: frog rate should follow the dial (~12% default), moods varied."""
import sys, os, types, random
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

tk = types.ModuleType("tkinter")
class _D: pass
for n in ("Tk", "Toplevel", "Misc", "Widget", "Frame", "Label", "Canvas", "StringVar", "BooleanVar", "Entry", "Text", "PhotoImage"):
    setattr(tk, n, type(n, (_D,), {}))
sys.modules.setdefault("tkinter", tk)
for m in ("tkinter.ttk", "tkinter.filedialog", "tkinter.messagebox", "tkinter.font"):
    sys.modules.setdefault(m, types.ModuleType(m))

import theme_mixer

print("frog_sneak prob (no config.json -> default):", theme_mixer.get_frog_sneak_probability())

N = 400
random.seed(11)
c = Counter(); others = set()
for _ in range(N):
    s = theme_mixer.generate_themes(count=1, user_keywords=[], subject_lock=True,
                                    custom_subject="", explicit_subject="")[0]["components"]["subject"].lower()
    if "frog" in s:
        c["frog"] += 1
    else:
        c["other"] += 1
        others.add(s)
print("blank-subject: frog =", c["frog"], "/", N, "=", round(100 * c["frog"] / N, 1), "% ; distinct non-frog subjects:", len(others))

random.seed(22)
m = Counter()
for _ in range(200):
    t = theme_mixer.generate_themes(count=1, user_keywords=["frog"], subject_lock=True,
                                    custom_subject="frog", explicit_subject="frog")[0]
    m[t["components"]["mood"]] += 1
print("explicit-frog mood dist:", m.most_common(6))

random.seed(33)
sd = Counter()
for _ in range(60):
    sd[theme_mixer.generate_themes(count=1, user_keywords=[], subject_lock=True,
                                   custom_subject="", explicit_subject="")[0]["components"]["style"]] += 1
print("blank style spread:", sd.most_common(6))
print("stone-ish styles present:", [k for k in sd if "stoner" in k.lower()])

# same as the new daily_runner call
random.seed(44)
d = Counter()
for _ in range(200):
    d[theme_mixer.generate_themes(count=1)[0]["components"]["subject"].lower()] += 1
fr = sum(v for k, v in d.items() if "frog" in k)
print("daily-style (count=1, no keywords): frog =", fr, "/200 =", round(100 * fr / 200, 1), "%; distinct subjects:", len(d))
