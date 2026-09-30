"""Verify the Frog Dial levels end-to-end (config.json -> theme_mixer)."""
import sys, os, types, json

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

cfg = os.path.join(HERE, "config.json")

def check(level):
    with open(cfg, "w", encoding="utf-8") as f:
        json.dump({} if level is None else {"frog_sneak": level}, f)
    print(repr(level), "->", theme_mixer.get_frog_sneak_probability())

for lv in ["off", "rare", "classic", "party", "bogus", None]:
    check(lv)
os.remove(cfg)
print("config.json cleaned up")
