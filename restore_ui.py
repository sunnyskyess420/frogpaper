"""restore_ui.py
--------------
Themed preview/confirmation dialog for restoring a wallpaper collection from
a folder.

Flow: the caller scans a folder off the main thread, then hands the remote
records here. The dialog renders a dry-run plan (nothing is written), lets the
user change the conflict policy and re-plans instantly, and only executes after
the user presses "Restore". Execution runs on a background thread; progress is
pushed to the UI through ``schedule_ui_update``.

All actual planning/execution lives in cloud_restore.py -- this module is
presentation plus threading only.
"""

import logging
import threading
import tkinter as tk
from pathlib import Path
from tkinter import ttk

import cloud_restore as cr
from app_runtime import run_background, schedule_ui_update
from utils import load_config

try:
    from app_themes import THEMES
except Exception:  # pragma: no cover - theme module is always present in-app
    THEMES = {}

logger = logging.getLogger(__name__)

_FALLBACK_PALETTE = {
    "bg": "#1b1e23",
    "card_bg": "#22252a",
    "text": "#e6e6e6",
    "muted": "#9aa0a6",
    "accent": "#4f9d69",
    "entrybg": "#2b2f35",
    "border_color": "#3a3f45",
}

_STATUS_TAGS = {
    cr.RestoreStatus.MISSING: "[new]",
    cr.RestoreStatus.IDENTICAL: "[present]",
    cr.RestoreStatus.INVALID: "[invalid]",
    cr.RestoreStatus.NO_SPACE: "[no space]",
}


def _shade(hex_color, amount):
    """Shift a #rrggbb colour by *amount* per channel (matches settings_tab)."""
    try:
        value = hex_color.lstrip("#")
        r, g, b = (int(value[i:i + 2], 16) for i in (0, 2, 4))
        return "#%02x%02x%02x" % tuple(
            max(0, min(255, channel + amount)) for channel in (r, g, b))
    except (AttributeError, ValueError):
        return hex_color


def _palette(app):
    """Theme palette with the extra keys this dialog uses.

    ``app_themes.THEMES`` has no ``card_bg``; settings_tab derives it from
    ``panel2``. Mirror that so the dialog matches the Settings page.
    """
    theme = getattr(app, "current_theme_name", "darkforest")
    pal = dict(THEMES.get(theme, _FALLBACK_PALETTE))
    base = pal.get("panel2") or pal.get("panel") or pal.get("bg")
    pal.setdefault("bg", _FALLBACK_PALETTE["bg"])
    pal.setdefault("card_bg", _shade(base, -8) if base else _FALLBACK_PALETTE["card_bg"])
    pal.setdefault("text", _FALLBACK_PALETTE["text"])
    pal.setdefault("muted", _FALLBACK_PALETTE["muted"])
    pal.setdefault("accent", _FALLBACK_PALETTE["accent"])
    pal.setdefault("entrybg", pal.get("elevated") or _FALLBACK_PALETTE["entrybg"])
    pal.setdefault("border_color",
                   pal.get("separator") or _FALLBACK_PALETTE["border_color"])
    return pal


def _human_bytes(count):
    size = float(count)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"


def _item_tag(item):
    if item.status == cr.RestoreStatus.CONFLICT:
        if item.target is None:
            return "[skip]"
        return "[overwrite]" if item.will_overwrite else "[keep both]"
    return _STATUS_TAGS.get(item.status, "[?]")


class RestorePreviewDialog:
    """Modal plan preview with progress and cancel."""

    def __init__(self, app, source, records, app_dir, on_finished=None,
                 on_closed=None, manifest=None):
        self.app = app
        self.source = source
        self.records = records
        self.app_dir = Path(app_dir)
        self.on_finished = on_finished
        self.on_closed = on_closed
        self.manifest = manifest
        self.pal = _palette(app)

        self.cancel_event = threading.Event()
        self._running = False
        self._closed = False
        self.result = None

        self.policy_var = tk.StringVar(
            value=load_config().get("restore_conflict_policy", "keep_both")
        )
        self.plan = self._build_plan()
        self._build()
        self._refresh()

    # ── plan ────────────────────────────────────────────────────────────

    def _build_plan(self):
        policy = self.policy_var.get()
        overwrite = policy == "overwrite"
        return cr.build_plan(
            self.records,
            self.app_dir,
            conflict_policy=policy if policy in cr.CONFLICT_POLICIES else "keep_both",
            overwrite=overwrite,
        )

    # ── widgets ─────────────────────────────────────────────────────────

    def _build(self):
        pal = self.pal
        dlg = tk.Toplevel(self.app.root)
        self.dlg = dlg
        dlg.title("Restore from Folder")
        dlg.configure(bg=pal["bg"])
        dlg.transient(self.app.root)
        dlg.protocol("WM_DELETE_WINDOW", self._close)
        dlg.minsize(640, 480)

        body = tk.Frame(dlg, bg=pal["bg"], padx=16, pady=12)
        body.pack(fill="both", expand=True)

        tk.Label(
            body, text="Restore from Folder", font=("Segoe UI", 16, "bold"),
            fg=pal["text"], bg=pal["bg"], anchor="w",
        ).pack(fill="x")

        self.source_label = tk.Label(
            body, text="", font=("Segoe UI", 9), fg=pal["muted"],
            bg=pal["bg"], anchor="w",
        )
        self.source_label.pack(fill="x", pady=(2, 10))

        options = tk.Frame(body, bg=pal["card_bg"], padx=12, pady=10,
                           highlightthickness=1,
                           highlightbackground=pal.get("border_color", pal["card_bg"]))
        options.pack(fill="x")
        tk.Label(
            options, text="If a file already exists:",
            font=("Segoe UI", 10, "bold"), fg=pal["text"], bg=pal["card_bg"],
        ).pack(anchor="w")

        radio_row = tk.Frame(options, bg=pal["card_bg"])
        radio_row.pack(anchor="w", pady=(6, 2))
        for label, value in (
            ("Keep both", "keep_both"),
            ("Skip it", "skip"),
            ("Overwrite", "overwrite"),
        ):
            tk.Radiobutton(
                radio_row, text=label, variable=self.policy_var, value=value,
                font=("Segoe UI", 10), fg=pal["text"], bg=pal["card_bg"],
                selectcolor=pal.get("entrybg", pal["card_bg"]),
                activebackground=pal["card_bg"], activeforeground=pal["text"],
                command=self._on_policy_change,
            ).pack(side="left", padx=(0, 18))

        self.policy_hint = tk.Label(
            options, text="", font=("Segoe UI", 9), fg=pal["muted"],
            bg=pal["card_bg"], anchor="w", justify="left",
        )
        self.policy_hint.pack(fill="x", pady=(4, 0))

        list_wrap = tk.Frame(body, bg=pal["bg"])
        list_wrap.pack(fill="both", expand=True, pady=10)

        self.text = tk.Text(
            list_wrap, height=12, wrap="none", font=("Consolas", 9),
            bg=pal.get("entrybg", pal["card_bg"]), fg=pal["text"],
            insertbackground=pal["text"], relief="flat",
            highlightthickness=1,
            highlightbackground=pal.get("border_color", pal["bg"]),
        )
        scrollbar = ttk.Scrollbar(list_wrap, orient="vertical",
                                  command=self.text.yview)
        self.text.configure(yscrollcommand=scrollbar.set)
        self.text.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.text.bind("<MouseWheel>",
                       lambda e: (self.text.yview_scroll(int(-e.delta / 120), "units"), "break")[1])
        self.text.configure(state="disabled")

        progress_row = tk.Frame(body, bg=pal["bg"])
        progress_row.pack(fill="x", pady=(0, 6))
        self.progress = ttk.Progressbar(progress_row, mode="determinate", maximum=100)
        self.progress.pack(side="left", fill="x", expand=True)
        self.progress_label = tk.Label(
            progress_row, text="", font=("Segoe UI", 9), fg=pal["muted"],
            bg=pal["bg"], width=28, anchor="e",
        )
        self.progress_label.pack(side="right", padx=(10, 0))

        buttons = tk.Frame(body, bg=pal["bg"])
        buttons.pack(fill="x", pady=(6, 0))

        self.open_btn = ttk.Button(buttons, text="Open Wallpaper Folder",
                                   command=self._open_folder, state="disabled")
        self.open_btn.pack(side="left")

        self.close_btn = ttk.Button(buttons, text="Cancel", command=self._close)
        self.close_btn.pack(side="right")
        self.restore_btn = ttk.Button(buttons, text="Restore",
                                      command=self._start_restore)
        self.restore_btn.pack(side="right", padx=(0, 8))

        self.status_label = tk.Label(
            body, text="", font=("Segoe UI", 9), fg=pal["muted"],
            bg=pal["bg"], anchor="w", justify="left", wraplength=620,
        )
        self.status_label.pack(fill="x")

        self._center()

    def _center(self):
        self.dlg.update_idletasks()
        width = max(720, self.dlg.winfo_reqwidth())
        height = max(560, self.dlg.winfo_reqheight())
        parent = self.app.root
        x = parent.winfo_rootx() + (parent.winfo_width() - width) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - height) // 2
        self.dlg.geometry(f"{width}x{height}+{max(0, x)}+{max(0, y)}")

    # ── plan rendering ──────────────────────────────────────────────────

    def _on_policy_change(self):
        if self._running:
            return
        self.plan = self._build_plan()
        self._refresh()

    def _refresh(self):
        plan = self.plan
        folder_name = (
            getattr(self.source, "label", None)
            or Path(getattr(self.source, "root", "")).name
            or "backup folder"
        )
        self.source_label.config(
            text=f"From: {folder_name}  ·  {len(self.records)} images found  ·  "
                 f"{_human_bytes(plan.needed_bytes)} to copy  ·  "
                 f"{_human_bytes(plan.free_bytes)} free on disk"
        )
        self.policy_hint.config(text={
            "keep_both": "Existing files are never touched. Restored copies get "
                         "a “(restored YYYY-MM-DD)” suffix.",
            "skip": "Files that already exist and differ are left alone and not restored.",
            "overwrite": "Files that differ WILL be replaced. This cannot be undone.",
        }.get(self.policy_var.get(), ""))

        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        for item in plan.items:
            tag = _item_tag(item)
            line = f"{tag:<12} {item.remote.rel_path}"
            if item.reason and item.status != cr.RestoreStatus.MISSING:
                line += f"   — {item.reason}"
            self.text.insert("end", line + "\n")
        self.text.configure(state="disabled")

        pending = len(plan.pending())
        self.restore_btn.config(
            state="normal" if pending and not self._running else "disabled",
            text=f"Restore {pending} file{'s' if pending != 1 else ''}" if pending else "Nothing to restore",
        )
        self.status_label.config(text=plan.summary())

        counts = plan.counts()
        if counts[cr.RestoreStatus.NO_SPACE.value]:
            self.progress_label.config(text="Not enough free space")
        else:
            self.progress_label.config(text=f"{pending} file(s) queued")

    # ── execution ───────────────────────────────────────────────────────

    def _start_restore(self):
        if self._running or not self.plan.pending():
            return
        self._remember_policy()
        self._running = True
        self.cancel_event.clear()
        self.restore_btn.config(state="disabled")
        for child in self.dlg.winfo_children():
            self._set_radios(child, "disabled")
        self.progress.configure(maximum=max(1, len(self.plan.pending())), value=0)

        executor = cr.RestoreExecutor(self.source, self.plan)
        run_background(self._worker, executor)

    def _remember_policy(self):
        """Persist the conflict choice so the next restore starts there."""
        policy = self.policy_var.get()
        try:
            config = load_config()
            if config.get("restore_conflict_policy") != policy:
                config["restore_conflict_policy"] = policy
                from utils import save_config

                save_config(config)
        except Exception as exc:
            logger.warning("Could not remember the conflict policy: %s", exc)

    def _set_radios(self, widget, state):
        for child in widget.winfo_children():
            if isinstance(child, tk.Radiobutton):
                child.configure(state=state)
            self._set_radios(child, state)

    def _worker(self, executor):
        try:
            result = executor.run(progress=self._on_progress,
                                  cancel=self.cancel_event)
        except Exception as exc:  # defensive: never leave the dialog stuck
            logger.exception("Restore worker crashed")
            result = cr.RestoreResult(failures=[], cancelled=False)
            result.failures.append((None, str(exc)))
        schedule_ui_update(self._finish, result)

    def _on_progress(self, index, total, item):
        # Runs on the worker thread.
        schedule_ui_update(self._tick, index, total, item.remote.rel_path)

    def _tick(self, index, total, rel_path):
        if self._closed:
            return
        self.progress.configure(value=index)
        self.progress_label.config(text=f"{index}/{total}  {rel_path}")

    def _finish(self, result):
        if self._closed:
            return
        self._running = False
        self.result = result
        self.progress.configure(value=self.progress.cget("maximum"))
        self.progress_label.config(text=result.summary())
        restored_tags = self._import_metadata(result)
        self.status_label.config(
            text=result.summary()
            + (f" · {restored_tags} files re-tagged" if restored_tags else ""))
        self.close_btn.config(text="Close")
        self.restore_btn.config(state="disabled", text="Done")
        self.open_btn.config(state="normal")

        if result.failures:
            self.text.configure(state="normal")
            self.text.insert("end", "\nFailures:\n")
            for item, error in result.failures:
                path = item.remote.rel_path if item is not None else "(unknown)"
                self.text.insert("end", f"  {path}: {error}\n")
            self.text.configure(state="disabled")
            self.text.see("end")

        if self.on_finished is not None:
            try:
                self.on_finished(result)
            except Exception:
                logger.exception("restore completion callback failed")

    def _import_metadata(self, result):
        """Merge tags/prompt params from a manifest in the source folder.

        Only files written by *this* run are eligible, so a skipped conflict
        can never inherit another file's tags. Returns the number of files
        that received tags.
        """
        if not result.written:
            return 0
        try:
            from backup_manifest import apply_manifest, apply_manifest_from_folder

            # A manifest fetched from the cloud wins; a folder restore falls
            # back to the copy sitting in the chosen directory.
            if self.manifest:
                counts = apply_manifest(
                    self.manifest, result.written, self.app_dir)
            else:
                source_root = getattr(self.source, "root", None)
                if not source_root:
                    return 0
                counts = apply_manifest_from_folder(
                    source_root, result.written, self.app_dir)
        except Exception:
            logger.exception("Metadata import failed")
            return 0
        return (counts or {}).get("tagged", 0)

    def _open_folder(self):
        opener = getattr(self.app, "_open_wallpapers_folder", None)
        if opener is not None:
            opener()

    def _close(self):
        if self._running:
            self.cancel_event.set()
            self.close_btn.config(text="Cancelling…", state="disabled")
            return
        self._closed = True
        try:
            self.dlg.grab_release()
        except tk.TclError:
            pass
        self.dlg.destroy()
        if self.on_closed is not None:
            try:
                self.on_closed()
            except Exception:
                logger.exception("restore close callback failed")
