import json
import logging

import tkinter as tk
from tkinter import ttk

from utils import load_config, save_config, get_app_dir


logger = logging.getLogger(__name__)


class SessionManager:
    """Session state save/load and settings memory.

    Now backed by SQLite (sessions table) via database.py.
    """

    def __init__(self, app):
        self.app = app

    def _collect_session_state(self):
        """Return a dict capturing the current Prompt Builder working state."""
        app = self.app
        template_var_values = {}
        template_widgets = getattr(app, "template_variable_widgets", {}) or {}
        for var_name, widget in template_widgets.items():
            if hasattr(widget, "get"):
                try:
                    template_var_values[var_name] = widget.get()
                except Exception:
                    pass

        # Collect negative prompt preset selections
        neg_preset_selections = {}
        if hasattr(app, '_neg_preset_vars'):
            for key, var in app._neg_preset_vars.items():
                if hasattr(var, 'get'):
                    try:
                        neg_preset_selections[key] = var.get()
                    except Exception:
                        neg_preset_selections[key] = False

        # Collect negative prompt custom terms
        neg_custom_terms = ""
        if hasattr(app, '_neg_custom_var'):
            if hasattr(app._neg_custom_var, 'get'):
                try:
                    neg_custom_terms = app._neg_custom_var.get()
                except Exception:
                    neg_custom_terms = ""

        return {
            "subject": app.get_active_subject(),
            "style": app.get_active_style(),
            "lighting": app.get_active_lighting(),
            "mood": app.get_active_mood(),
            "color": app.get_active_color(),
            "atmosphere": app.get_active_atmosphere(),
            "mode": app.get_active_mode(),
            "subject_lock": app.get_active_subject_lock(),
            "negative_prompt": app.get_active_negative_prompt(),
            "neg_preset_selections": neg_preset_selections,
            "neg_custom_terms": neg_custom_terms,
            "pb_view": getattr(app, "prompt_builder_mode_var", tk.StringVar()).get(),
            "selected_template": app.template_var.get() if hasattr(app, "template_var") else "",
            "template_variable_values": template_var_values,
        }


    def _restore_session_state(self, state):
        """Apply a previously saved session state dict to the current Prompt Builder."""
        app = self.app
        app.set_active_subject(state.get("subject", ""))
        app.set_active_style(state.get("style", ""))
        app.set_active_lighting(state.get("lighting", ""))
        app.set_active_mood(state.get("mood", ""))
        app.set_active_color(state.get("color", ""))
        app.set_active_atmosphere(state.get("atmosphere", ""))
        mode = state.get("mode", "")
        if mode:
            app.set_active_mode(mode)
        app.set_active_subject_lock(state.get("subject_lock", True))
        neg = state.get("negative_prompt", "")
        if neg:
            app.set_active_negative_prompt(neg)

        # Restore negative prompt preset selections
        neg_preset_selections = state.get("neg_preset_selections", {})
        if neg_preset_selections and hasattr(app, '_neg_preset_vars'):
            for key, selected in neg_preset_selections.items():
                if key in app._neg_preset_vars:
                    if hasattr(app._neg_preset_vars[key], 'set'):
                        try:
                            app._neg_preset_vars[key].set(selected)
                        except Exception:
                            pass

        # Restore negative prompt custom terms
        neg_custom_terms = state.get("neg_custom_terms", "")
        if neg_custom_terms and hasattr(app, '_neg_custom_var'):
            if hasattr(app._neg_custom_var, 'set'):
                try:
                    app._neg_custom_var.set(neg_custom_terms)
                except Exception:
                    pass

        # Rebuild the combined negative prompt from restored selections
        if hasattr(app, '_rebuild_neg_combined'):
            try:
                app._rebuild_neg_combined()
            except Exception:
                pass

        # Restore Prompt Builder view mode
        pb_view = state.get("pb_view", "")
        if pb_view and hasattr(app, "prompt_builder_mode_var"):
            app.prompt_builder_mode_var.set(pb_view)
            app.update_prompt_builder_mode()

        # Restore selected template and its variable values
        selected_template = state.get("selected_template", "")
        if selected_template and hasattr(app, "template_var"):
            # Only restore if the template still exists in the list
            names = list(app.template_combo["values"]) if hasattr(app, "template_combo") else []
            if selected_template in names:
                app.template_var.set(selected_template)
                app._update_template_detail_label()
                app.loadtemplate()
                # Now overwrite widget values with saved variable values
                saved_vars = state.get("template_variable_values", {})
                template_widgets = getattr(app, "template_variable_widgets", {}) or {}
                for var_name, value in saved_vars.items():
                    if var_name in template_widgets:
                        widget = template_widgets[var_name]
                        if hasattr(widget, "set"):
                            try:
                                widget.set(value)
                            except Exception:
                                pass


    def _db_get_all_sessions(self):
        """Load all sessions from DB, with JSON fallback. Returns dict of {name: state_dict}."""
        import database
        if hasattr(database, 'DB_AVAILABLE') and database.DB_AVAILABLE:
            from database import Session as DBSession

            session = database.get_db_session()
            try:
                rows = session.query(DBSession).all()
                result = {}
                for row in rows:
                    tvv = None
                    if row.template_variable_values:
                        try:
                            tvv = json.loads(row.template_variable_values)
                        except Exception:
                            tvv = {}
                    result[row.name] = {
                        "subject": row.subject or "",
                        "style": row.style or "",
                        "lighting": row.lighting or "",
                        "mood": row.mood or "",
                        "color": row.color or "",
                        "atmosphere": row.atmosphere or "",
                        "mode": row.mode or "",
                        "subject_lock": row.subject_lock if row.subject_lock is not None else True,
                        "negative_prompt": row.negative_prompt or "",
                        "neg_preset_selections": json.loads(row.neg_preset_selections) if row.neg_preset_selections else {},
                        "neg_custom_terms": row.neg_custom_terms or "",
                        "pb_view": row.pb_view or "",
                        "selected_template": row.selected_template or "",
                        "template_variable_values": tvv or {},
                    }
                return result
            finally:
                session.close()
        else:
            # JSON fallback when DB is unavailable
            sessions_file = get_app_dir() / "sessions.json"
            if sessions_file.exists():
                with open(sessions_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            return {}


    def _db_save_session(self, name, state_dict):
        """Save or update a session in DB, with JSON fallback."""
        import database
        if hasattr(database, 'DB_AVAILABLE') and database.DB_AVAILABLE:
            from database import Session as DBSession

            session = database.get_db_session()
            try:
                existing = session.query(DBSession).filter(DBSession.name == name).first()
                tvv = json.dumps(
                    state_dict.get("template_variable_values", {}), ensure_ascii=False
                ) if state_dict.get("template_variable_values") else None

                if existing:
                    existing.subject = state_dict.get("subject", "")
                    existing.style = state_dict.get("style", "")
                    existing.lighting = state_dict.get("lighting", "")
                    existing.mood = state_dict.get("mood", "")
                    existing.color = state_dict.get("color", "")
                    existing.atmosphere = state_dict.get("atmosphere", "")
                    existing.mode = state_dict.get("mode", "")
                    existing.subject_lock = state_dict.get("subject_lock", True)
                    existing.negative_prompt = state_dict.get("negative_prompt", "")
                    existing.neg_preset_selections = json.dumps(state_dict.get("neg_preset_selections", {}), ensure_ascii=False) if state_dict.get("neg_preset_selections") else None
                    existing.neg_custom_terms = state_dict.get("neg_custom_terms", "")
                    existing.pb_view = state_dict.get("pb_view", "")
                    existing.selected_template = state_dict.get("selected_template", "")
                    existing.template_variable_values = tvv
                else:
                    session.add(DBSession(
                        name=name,
                        subject=state_dict.get("subject", ""),
                        style=state_dict.get("style", ""),
                        lighting=state_dict.get("lighting", ""),
                        mood=state_dict.get("mood", ""),
                        color=state_dict.get("color", ""),
                        atmosphere=state_dict.get("atmosphere", ""),
                        mode=state_dict.get("mode", ""),
                        subject_lock=state_dict.get("subject_lock", True),
                        negative_prompt=state_dict.get("negative_prompt", ""),
                        neg_preset_selections=json.dumps(state_dict.get("neg_preset_selections", {}), ensure_ascii=False) if state_dict.get("neg_preset_selections") else None,
                        neg_custom_terms=state_dict.get("neg_custom_terms", ""),
                        pb_view=state_dict.get("pb_view", ""),
                        selected_template=state_dict.get("selected_template", ""),
                        template_variable_values=tvv,
                    ))
                session.commit()
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()
        else:
            # JSON fallback when DB is unavailable
            sessions_file = get_app_dir() / "sessions.json"
            sessions = {}
            if sessions_file.exists():
                with open(sessions_file, "r", encoding="utf-8") as f:
                    sessions = json.load(f)
            sessions[name] = state_dict
            with open(sessions_file, "w", encoding="utf-8") as f:
                json.dump(sessions, f, ensure_ascii=False, indent=2)


    def _db_delete_session(self, name):
        """Delete a session from DB, with JSON fallback."""
        import database
        if hasattr(database, 'DB_AVAILABLE') and database.DB_AVAILABLE:
            from database import Session as DBSession

            session = database.get_db_session()
            try:
                session.query(DBSession).filter(DBSession.name == name).delete()
                session.commit()
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()
        else:
            # JSON fallback when DB is unavailable
            sessions_file = get_app_dir() / "sessions.json"
            if sessions_file.exists():
                with open(sessions_file, "r", encoding="utf-8") as f:
                    sessions = json.load(f)
                if name in sessions:
                    del sessions[name]
                    with open(sessions_file, "w", encoding="utf-8") as f:
                        json.dump(sessions, f, ensure_ascii=False, indent=2)


    def load_session(self):
        """Show a list of saved sessions and restore the selected one."""
        app = self.app

        sessions = self._db_get_all_sessions()
        if not sessions:
            app._dialog.info("No Sessions", "No saved sessions found.")
            return

        dialog = tk.Toplevel(app.root)
        dialog.title("Load Session")
        dialog.geometry("420x320")
        dialog.resizable(True, True)
        dialog.transient(app.root)
        dialog.grab_set()

        from utils import center_window
        center_window(app.root, dialog)

        ttk.Label(dialog, text="Select a session to restore:").pack(anchor="w", padx=14, pady=(14, 4))

        list_frame = ttk.Frame(dialog)
        list_frame.pack(padx=14, fill="both", expand=True, pady=(0, 8))
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical")
        session_list = tk.Listbox(list_frame, yscrollcommand=scrollbar.set, selectmode="single", height=10)
        scrollbar.config(command=session_list.yview)
        session_list.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        session_names = list(sessions.keys())
        for sname in session_names:
            session_list.insert(tk.END, sname)
        if session_names:
            session_list.selection_set(0)

        def do_load():
            sel = session_list.curselection()
            if not sel:
                return
            chosen = session_names[sel[0]]
            state = sessions[chosen]
            try:
                app._restore_session_state(state)
                app.status_var.set(f"Session loaded: '{chosen}'")
                dialog.destroy()
            except Exception as e:
                app._dialog.error("Restore Error", "Could not restore the saved session. The session file may be corrupted. Try a different session.")

        def do_delete():
            sel = session_list.curselection()
            if not sel:
                return
            chosen = session_names[sel[0]]
            if not app._dialog.ask("Delete Session", f"Delete session '{chosen}'?"):
                return
            try:
                self._db_delete_session(chosen)
                session_list.delete(sel[0])
                session_names.pop(sel[0])
            except Exception as e:
                app._dialog.error("Delete Error", "Could not delete the session. It may be in use or protected.")

        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(pady=(0, 12))
        ttk.Button(btn_frame, text="Load", command=do_load).pack(side="left", padx=6)
        ttk.Button(btn_frame, text="Delete", command=do_delete).pack(side="left", padx=6)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side="left", padx=6)

        session_list.bind("<Double-Button-1>", lambda e: do_load())
        session_list.focus_set()


    def save_current_settings_for_memory(self):

        app = self.app
        
        # Always save negative prompt selections (user preference)
        neg_preset_selections = {}
        if hasattr(app, '_neg_preset_vars'):
            for key, var in app._neg_preset_vars.items():
                if hasattr(var, 'get'):
                    try:
                        neg_preset_selections[key] = var.get()
                    except Exception:
                        neg_preset_selections[key] = False
        
        neg_custom_terms = ""
        if hasattr(app, '_neg_custom_var'):
            if hasattr(app._neg_custom_var, 'get'):
                try:
                    neg_custom_terms = app._neg_custom_var.get()
                except Exception:
                    neg_custom_terms = ""
        
        config = load_config()
        config["last_neg_preset_selections"] = neg_preset_selections
        config["last_neg_custom_terms"] = neg_custom_terms
        
        if app.remember_settings_var.get():

            config["last_style_mode"] = app.get_active_mode()

            config["last_subject"] = app.get_active_subject()

            config["last_style"] = app.get_active_style()


            config["last_lighting"] = app.get_active_lighting()

            config["last_mood"] = app.get_active_mood()

            config["last_color"] = app.get_active_color()

        save_config(config)


    def save_session(self):
        """Prompt for a session name and save current Prompt Builder state to DB."""
        app = self.app
        from datetime import datetime

        dialog = tk.Toplevel(app.root)
        dialog.title("Save Session")
        dialog.geometry("380x160")
        dialog.resizable(False, False)
        dialog.transient(app.root)
        dialog.grab_set()

        from utils import center_window
        center_window(app.root, dialog)

        ttk.Label(dialog, text="Session name:").pack(anchor="w", padx=14, pady=(14, 0))
        _subj = (app.get_active_subject() or "").strip().title() or "Session"
        default_name = datetime.now().strftime(f"{_subj} %Y-%m-%d %H:%M")
        name_var = tk.StringVar(value=default_name)
        name_entry = ttk.Entry(dialog, textvariable=name_var, width=46)
        name_entry.pack(padx=14, pady=(4, 12), fill="x")
        app.configure_entry_cursor(name_entry)
        name_entry.selection_range(0, tk.END)
        name_entry.focus_set()

        def do_save():
            name = name_var.get().strip()
            if not name:
                app._dialog.warning("Name Required", "Please enter a session name.")
                return
            try:
                state_dict = app._collect_session_state()
                self._db_save_session(name, state_dict)
                app.status_var.set(f"Session saved: '{name}'")
                dialog.destroy()
            except Exception as e:
                app._dialog.error("Save Error", "Could not save the session. Check that the app folder is accessible.")

        btn_frame = ttk.Frame(dialog)
        btn_frame.pack()
        ttk.Button(btn_frame, text="Save", command=do_save).pack(side="left", padx=6)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side="left", padx=6)
