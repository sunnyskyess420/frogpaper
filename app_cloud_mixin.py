"""Cloud sync / backup / startup-registry methods for FrogPaperApp
(roadmap #7 Phase B step 2).

Extracted verbatim from app.py: the CLOUD_PROVIDERS class attribute and
the cloud account cards, manual sync, auto-backup scheduler and the
Windows run-on-startup registry helpers.

All methods are mixed into FrogPaperApp (see app.py), so behaviour is
unchanged: state still lives on self / self.app and every caller keeps
working untouched.
"""

import logging

from app_runtime import run_background, schedule_ui_update

logger = logging.getLogger(__name__)



class FrogPaperAppCloudMixin:
    """Mixed into FrogPaperApp (see app.py); methods are verbatim."""

    

    # ── Cloud Account Methods ───────────────────────────────────────────────

    # ── Unified cloud account management ─────────────────────────────────

    CLOUD_PROVIDERS = {
        "google_drive": {
            "display_name": "Google Drive",
            "id_config_key": "google_client_id",
            "secret_config_key": "google_client_secret",
            "class_name": "GoogleDriveProvider",
            "module": "cloud_providers",
        },
        "onedrive": {
            "display_name": "OneDrive",
            "id_config_key": "onedrive_client_id",
            "secret_config_key": "onedrive_client_secret",
            "class_name": "OneDriveProvider",
            "module": "cloud_providers",
        },
        "dropbox": {
            "display_name": "Dropbox",
            "id_config_key": "dropbox_app_key",
            "secret_config_key": "dropbox_app_secret",
            "class_name": "DropboxProvider",
            "module": "cloud_providers",
        },
    }

    def _update_all_cloud_cards(self):
        """Update all cloud provider card UIs based on current token state."""
        from utils import has_oauth_token
        for provider_name in self.CLOUD_PROVIDERS:
            connected = has_oauth_token(provider_name)
            if hasattr(self, '_toggle_cloud_card'):
                self._toggle_cloud_card(provider_name, connected)

    def _cloud_connect(self, provider_name):
        """Unified connect/disconnect handler for all cloud providers.

        If currently connected → disconnect.
        If not connected → validate credentials and connect.
        """
        from utils import has_oauth_token, delete_oauth_token, load_config, save_config

        info = self.CLOUD_PROVIDERS.get(provider_name)
        if not info:
            return

        display_name = info["display_name"]

        # ── DISCONNECT path ────────────────────────────────────────────
        if has_oauth_token(provider_name):
            if not self._dialog.ask(
                f"Disconnect {display_name}",
                f"Disconnect {display_name}?\n\n"
                f"Your cloud sync will stop working until you reconnect."
            ):
                return
            try:
                delete_oauth_token(provider_name)
                logger.info(f"Disconnected {provider_name}")
            except Exception as e:
                logger.error(f"Failed to delete {provider_name} token: {e}")
            if hasattr(self, '_toggle_cloud_card'):
                self._toggle_cloud_card(provider_name, False)
            self.status_var.set(f"{display_name} disconnected")
            return

        # ── CONNECT path ──────────────────────────────────────────────
        id_var = getattr(self, f"{provider_name}_id_var", None)
        secret_var = getattr(self, f"{provider_name}_secret_var", None)
        if not id_var or not secret_var:
            self._dialog.error(display_name, "Internal error: credential fields not found.")
            return

        client_id = id_var.get().strip()
        client_secret = secret_var.get().strip()
        if not client_id or not client_secret:
            self._dialog.warning(
                f"{display_name} Connection",
                f"Please enter your {display_name} credentials in the fields above."
            )
            return

        # Save credentials to config
        config = load_config()
        config[info["id_config_key"]] = client_id
        config[info["secret_config_key"]] = client_secret
        save_config(config)

        # Update module-level globals so the provider picks them up
        import cloud_providers
        id_global = f"{provider_name.upper().replace('GOOGLE_DRIVE', 'GOOGLE')}_CLIENT_ID"
        secret_global = f"{provider_name.upper().replace('GOOGLE_DRIVE', 'GOOGLE')}_CLIENT_SECRET"
        # Map to actual global names used in cloud_providers.py
        global_map = {
            "google_drive": ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET"),
            "onedrive": ("ONEDRIVE_CLIENT_ID", "ONEDRIVE_CLIENT_SECRET"),
            "dropbox": ("DROPBOX_APP_KEY", "DROPBOX_APP_SECRET"),
        }
        g_id, g_secret = global_map.get(provider_name, (id_global, secret_global))
        setattr(cloud_providers, g_id, client_id)
        setattr(cloud_providers, g_secret, client_secret)

        # Instantiate provider and authenticate in a background thread
        # Google's run_local_server() blocks the main thread (freezes UI)
        # so we offload it and update the card when done.
        def _auth_and_update():
            try:
                mod = __import__(info["module"], fromlist=[info["class_name"]])
                cls = getattr(mod, info["class_name"])
                provider = cls()

                kwargs = {}
                if provider_name == "dropbox":
                    kwargs["main_root"] = self.root

                success = provider.authenticate(**kwargs)

                # Schedule UI update on the main thread
                schedule_ui_update(_on_auth_done, success, None)
            except Exception as e:
                logger.error(f"{provider_name} connection error: {e}")
                schedule_ui_update(_on_auth_done, False, str(e))

        def _on_auth_done(success, error_msg):
            if success:
                if hasattr(self, '_toggle_cloud_card'):
                    self._toggle_cloud_card(provider_name, True)
                self._dialog.info(f"{display_name} Connection",
                                  f"Successfully connected to {display_name}!")
            else:
                if hasattr(self, '_toggle_cloud_card'):
                    self._toggle_cloud_card(provider_name, False,
                                            error_msg=(error_msg or "Authentication failed")[:60])
                self._dialog.warning(
                    f"{display_name} Connection",
                    f"Failed to connect to {display_name}.\n\n"
                    f"Check that your credentials are correct and that the API is enabled."
                    + (f"\n\nError: {error_msg}" if error_msg else "")
                )

        self.status_var.set(f"Connecting to {display_name}...")
        run_background(_auth_and_update)

    # ── Cloud card UI state management ─────────────────────────────────

    def _toggle_cloud_card(self, provider_name, connected, error_msg=None):
        """Switch a cloud provider card between connected / not-connected / error.

        This method is called by:
          - _update_all_cloud_cards() at startup
          - _cloud_connect() after connect/disconnect attempt
          - _update_google_drive_status() / _update_onedrive_status() / _update_dropbox_status()
        """
        refs = getattr(self, '_cloud_card_refs', {}).get(provider_name)
        if not refs:
            return

        from settings_tab import STATUS_COLORS
        pal = self.THEMES.get(getattr(self, 'current_theme_name', 'darkforest'), self.THEMES['darkforest'])
        _muted = pal['muted']
        _card_bg = pal.get('card_bg', pal['bg'])

        accent_bar = refs['accent_bar']
        dot_canvas = refs['dot_canvas']
        dot_id = refs['dot_id']
        status_lbl = refs['status_lbl']
        cred_frame = refs['cred_frame']
        connected_frame = refs['connected_frame']
        error_frame = refs['error_frame']
        error_lbl = refs['error_lbl']
        guide_toggle = refs['setup_guide_toggle']
        guide_frame = refs['guide_frame']

        if error_msg:
            # ── ERROR state ──
            accent_bar.config(bg=STATUS_COLORS['error'])
            dot_canvas.itemconfig(dot_id, fill=STATUS_COLORS['error'])
            status_lbl.config(text='Error', fg=STATUS_COLORS['error'])
            cred_frame.grid_remove()
            connected_frame.grid_remove()
            error_frame.grid()
            error_lbl.config(text=error_msg)
            guide_toggle.grid_remove()
            guide_frame.grid_remove()
        elif connected:
            # ── CONNECTED state ──
            accent_bar.config(bg=STATUS_COLORS['connected'])
            dot_canvas.itemconfig(dot_id, fill=STATUS_COLORS['connected'])
            status_lbl.config(text='Connected', fg=STATUS_COLORS['connected'])
            cred_frame.grid_remove()
            error_frame.grid_remove()
            connected_frame.grid()
            guide_toggle.grid_remove()
            guide_frame.grid_remove()
        else:
            # ── NOT CONNECTED state ──
            accent_bar.config(bg=STATUS_COLORS['not_connected'])
            dot_canvas.itemconfig(dot_id, fill=STATUS_COLORS['not_connected'])
            status_lbl.config(text='Not connected', fg=_muted)
            connected_frame.grid_remove()
            error_frame.grid_remove()
            cred_frame.grid()
            guide_toggle.grid()

    # ── Legacy cloud status methods (kept for backward compat) ──────────────

    def _update_google_drive_status(self):
        from utils import has_oauth_token
        if hasattr(self, '_toggle_cloud_card'):
            self._toggle_cloud_card("google_drive", has_oauth_token("google_drive"))

    def _update_onedrive_status(self):
        from utils import has_oauth_token
        if hasattr(self, '_toggle_cloud_card'):
            self._toggle_cloud_card("onedrive", has_oauth_token("onedrive"))

    def _update_dropbox_status(self):
        from utils import has_oauth_token
        if hasattr(self, '_toggle_cloud_card'):
            self._toggle_cloud_card("dropbox", has_oauth_token("dropbox"))

    def _connect_google_drive(self):
        self._cloud_connect("google_drive")

    def _connect_onedrive(self):
        self._cloud_connect("onedrive")

    def _connect_dropbox(self):
        self._cloud_connect("dropbox")

    def _manual_sync(self):
        """Perform manual sync with user choice for conflicts."""
        logger.info("Manual sync button clicked")
        try:
            if not hasattr(self, 'sync_manager') or self.sync_manager is None:
                from sync_manager import SyncManager
                self.sync_manager = SyncManager(self)
                logger.info("SyncManager initialized")
            
            if self.sync_manager is None:
                raise Exception("SyncManager initialization failed")
            
            # Clear sync metadata to force fresh sync
            try:
                self.sync_manager.sync_metadata = {"files": {}, "last_sync": None}
                self.sync_manager._save_sync_metadata()
                logger.info("Sync metadata cleared for fresh sync")
            except Exception as e:
                logger.warning(f"Failed to clear sync metadata: {e}")
            
            # Pre-authenticate all providers on the MAIN thread so OAuth
            # dialogs (Dropbox) work correctly — they cannot run in a background
            # thread (tkinter requirement).
            logger.info("Pre-authenticating cloud providers on main thread...")
            self.sync_status_var.set("Authenticating...")
            self.root.update_idletasks()
            providers = self.sync_manager.pre_authenticate(main_root=self.root)
            
            if not providers:
                logger.info("No cloud providers authenticated, aborting sync")
                self.sync_status_var.set("No cloud connection")
                self._dialog.warning("Sync", "No cloud providers are connected. Please set up a cloud account in Settings first.")
                return
            
            logger.info(f"Pre-authenticated providers: {list(providers.keys())}")
            logger.info("Starting manual sync...")
            self.sync_status_var.set("Syncing...")
            if hasattr(self, '_sync_status_lbl'):
                self._sync_status_lbl.config(text="Syncing...")
            self.root.update_idletasks()
            
            # Run sync in background thread to prevent UI freeze
            # Providers are already authenticated, so no dialogs needed in the thread
            run_background(self._run_manual_sync)
            logger.info("Sync thread started")
        except Exception as e:
            logger.error(f"Manual sync initialization failed: {e}")
            self.sync_status_var.set(f"Sync failed: {e}")
            self._dialog.error("Sync Error", "Could not start cloud sync. Check your internet connection and cloud account settings.")

    def _run_manual_sync(self):
        """Run manual sync in background thread."""
        try:
            # Ensure sync_manager exists
            if not hasattr(self, 'sync_manager') or self.sync_manager is None:
                from sync_manager import SyncManager
                self.sync_manager = SyncManager(self)
                logger.info("SyncManager initialized in background thread")
            
            if self.sync_manager is None:
                raise Exception("SyncManager is None in background thread")
            
            # Start periodic progress updates
            self._start_sync_progress_updates()
            
            # Reuse already-authenticated providers from pre_authenticate.
            # _initialize_providers is called inside perform_sync but since
            # providers are already set and tokens are fresh, it will just
            # reload and validate them (no dialogs needed).
            results = self.sync_manager.perform_sync(is_manual=True)
            
            # Stop progress updates
            self._stop_sync_progress_updates()
            
            # Update UI from main thread
            schedule_ui_update(self._on_sync_complete, results)
        except Exception as e:
            logger.error(f"Manual sync failed: {e}")
            self._stop_sync_progress_updates()
            schedule_ui_update(self._on_sync_error, str(e))

    def _start_sync_progress_updates(self):
        """Start periodic updates of sync progress in status bar."""
        if hasattr(self, '_sync_progress_job'):
            try:
                self.root.after_cancel(self._sync_progress_job)
            except Exception:
                pass
        
        def update_progress():
            if not hasattr(self, 'sync_manager') or not self.sync_manager.sync_in_progress:
                return
            
            progress = self.sync_manager.sync_progress
            total = self.sync_manager.sync_total
            status = self.sync_manager.sync_status
            
            if total > 0:
                percent = int((progress / total) * 100)
                self.status_var.set(f"Sync: {status} ({progress}/{total} - {percent}%)")
            else:
                self.status_var.set(f"Sync: {status}")
            
            self._sync_progress_job = self.root.after(500, update_progress)
        
        self._sync_progress_job = self.root.after(500, update_progress)

    def _stop_sync_progress_updates(self):
        """Stop periodic sync progress updates."""
        if hasattr(self, '_sync_progress_job'):
            try:
                self.root.after_cancel(self._sync_progress_job)
            except Exception:
                pass

    def _on_sync_complete(self, results):
        """Handle sync completion."""
        if results.get("status") == "no_cloud":
            self.sync_status_var.set("No cloud accounts connected")
            if hasattr(self, '_sync_status_lbl'):
                self._sync_status_lbl.config(text="No cloud connection")
            self._dialog.warning("Sync Failed", "No cloud accounts are connected. Please connect a cloud provider in Settings first.")
        elif results.get("status") == "failed":
            self.sync_status_var.set("Sync failed")
            if hasattr(self, '_sync_status_lbl'):
                self._sync_status_lbl.config(text="Sync failed")
            self._dialog.error("Sync Failed", f"Sync encountered {results.get('errors', 0)} errors. Check logs for details.")
        else:
            summary = f"Added: {results.get('added', 0)}, Modified: {results.get('modified', 0)}, Deleted: {results.get('deleted', 0)}"
            self.sync_status_var.set("Sync complete")
            if hasattr(self, '_sync_status_lbl'):
                self._sync_status_lbl.config(text=f"Done — {results.get('added', 0)} up")
            self._dialog.info("Sync Complete", f"Sync completed successfully.\n\n{summary}")

    def _on_sync_error(self, error_message):
        """Handle sync error."""
        self.sync_status_var.set("Sync failed")
        if hasattr(self, '_sync_status_lbl'):
            self._sync_status_lbl.config(text="Sync failed")
        self._dialog.error("Sync Error", f"Sync failed: {error_message}")

    def _get_tray_sync_status(self):
        """Get sync status for tray menu display."""
        if not hasattr(self, 'sync_manager'):
            return "Not initialized"
        
        status = self.sync_manager.get_sync_status()
        if status.get('in_progress'):
            return "Syncing..."
        elif status.get('cloud_connected'):
            return "Connected"
        else:
            return "No connection"

    def _tray_sync_now(self, icon=None, item=None):
        """Trigger manual sync from tray menu."""
        def _do():
            self._tray_restore()
            self.root.after(100, self._manual_sync)
        schedule_ui_update(_do)

    def _tray_show_sync_status(self, icon=None, item=None):
        """Show sync status dialog from tray menu."""
        def _do():
            self._tray_restore()
            if not hasattr(self, 'sync_manager'):
                from sync_manager import SyncManager
                self.sync_manager = SyncManager(self)
            
            status = self.sync_manager.get_sync_status()
            status_text = f"Last Sync: {status.get('last_sync', 'Never')}\n"
            status_text += f"Files Tracked: {status.get('files_tracked', 0)}\n"
            status_text += f"Cloud Connected: {'Yes' if status.get('cloud_connected') else 'No'}\n"
            status_text += f"Sync In Progress: {'Yes' if status.get('in_progress') else 'No'}"
            
            self._dialog.info("Sync Status", status_text)
        schedule_ui_update(_do)

    def _setup_auto_backup(self):
        """Setup automatic daily backup scheduling."""
        from utils import load_config
        config = load_config()
        
        if config.get("auto_backup_enabled", False):
            self._start_backup_scheduler()
        else:
            self._stop_backup_scheduler()

    def _start_backup_scheduler(self):
        """Start the automatic backup scheduler.

        Fires once per day at the user-configured time (default 02:00).
        If the scheduled time was missed (app was closed/asleep), it runs
        shortly after the next launch instead.
        """
        # Stop any existing scheduler first
        self._stop_backup_scheduler()

        self._backup_stop_event.clear()

        def backup_scheduler():
            """Background thread: wait until target time, sync, repeat daily."""
            from utils import load_config
            from datetime import datetime, timedelta

            while not self._backup_stop_event.is_set():
                try:
                    config = load_config()
                    if not config.get("auto_backup_enabled", False):
                        break

                    target_hour = config.get("auto_backup_hour", 2)
                    target_minute = config.get("auto_backup_minute", 0)
                    now = datetime.now()

                    # Build today's target datetime
                    target = now.replace(hour=target_hour, minute=target_minute,
                                          second=0, microsecond=0)

                    # If target already passed today, check if we already synced today
                    if now >= target:
                        last_sync_str = config.get("auto_backup_last_run", "")
                        already_ran_today = False
                        if last_sync_str:
                            try:
                                last_run = datetime.fromisoformat(last_sync_str)
                                if last_run.date() == now.date():
                                    already_ran_today = True
                            except (ValueError, TypeError):
                                pass

                        if not already_ran_today:
                            # Missed today's window — run now (catch-up)
                            logger.info("Missed backup window, running catch-up backup now")
                            self._run_scheduled_backup()
                        # Otherwise already ran today, sleep until tomorrow

                    # Sleep until target time (or re-check in 60s if stop requested)
                    now = datetime.now()
                    target = now.replace(hour=target_hour, minute=target_minute,
                                          second=0, microsecond=0)
                    if now >= target:
                        # Past today's target, aim for tomorrow
                        target += timedelta(days=1)
                    wait_secs = (target - now).total_seconds()

                    # Wake up every 60s to check for stop signal
                    while wait_secs > 0 and not self._backup_stop_event.is_set():
                        sleep_chunk = min(60, wait_secs)
                        self._backup_stop_event.wait(timeout=sleep_chunk)
                        wait_secs -= 60

                    if self._backup_stop_event.is_set():
                        break

                    # Time to back up
                    self._run_scheduled_backup()

                except Exception as e:
                    logger.error(f"Backup scheduler error: {e}")
                    self._backup_stop_event.wait(timeout=60)

        self.backup_scheduler_job = run_background(backup_scheduler)
        logger.info("Automatic backup scheduler started")

    def _run_scheduled_backup(self):
        """Execute a scheduled backup (called from scheduler thread)."""
        try:
            from sync_manager import SyncManager
            if not self.sync_manager:
                self.sync_manager = SyncManager(self)

            # Keep-alive nudge to the main thread (thread-safe via ThreadManager)
            schedule_ui_update(lambda: None)

            results = self.sync_manager.perform_sync(is_manual=False)
            logger.info(f"Automatic backup completed: {results}")

            # Record successful run time
            from utils import load_config, save_config
            config = load_config()
            from datetime import datetime
            config["auto_backup_last_run"] = datetime.now().isoformat()
            save_config(config)

            # Update UI
            if hasattr(self, 'last_backup_var'):
                schedule_ui_update(self.last_backup_var.set,
                    f"Last backup: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        except Exception as e:
            logger.error(f"Scheduled backup failed: {e}")

    def _stop_backup_scheduler(self):
        """Stop the automatic backup scheduler."""
        self._backup_stop_event.set()
        self.backup_scheduler_job = None
        logger.info("Automatic backup scheduler stopped")



    def _get_startup_registry(self) -> bool:
        """Return True if FrogPaper is registered in the Windows startup registry key or Task Scheduler."""
        # Check registry first
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0, winreg.KEY_READ
            )
            try:
                winreg.QueryValueEx(key, "FrogPaper")
                return True
            except FileNotFoundError:
                pass
            finally:
                winreg.CloseKey(key)
        except Exception:
            pass
        
        # Check Task Scheduler as fallback
        try:
            import subprocess
            task_name = "FrogPaperStartup"
            cmd = ['schtasks', '/Query', '/TN', task_name]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                logger.info("[Startup] Found startup entry in Task Scheduler")
                return True
        except Exception:
            pass
        
        return False

    def _set_startup_task_scheduler(self, enable: bool):
        """Alternative method using Windows Task Scheduler when registry access fails."""
        try:
            import subprocess
            import sys
            from pathlib import Path
            
            task_name = "FrogPaperStartup"
            
            if enable:
                # Determine the correct launch command based on execution mode
                if getattr(sys, 'frozen', False):
                    # Running as PyInstaller EXE
                    exe_path = Path(sys.executable).resolve()
                    target = str(exe_path)
                    logger.info(f"[Startup] Setting startup task for EXE at: {target}")
                else:
                    # Running as script — launch via python
                    import __main__
                    script_path = Path(getattr(__main__, '__file__', 'app.py')).resolve()
                    python_exe = Path(sys.executable).resolve()
                    target = f'"{python_exe}" "{script_path}"'
                    logger.info(f"[Startup] Setting startup task for script at: {target}")
                
                # Create/Update the scheduled task
                cmd = [
                    'schtasks', '/Create',
                    '/TN', task_name,
                    '/TR', target,
                    '/SC', 'ONLOGON',
                    '/RL', 'HIGHEST',
                    '/F'
                ]
                
                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode == 0:
                    logger.info(f"[Startup] Task created successfully: {target}")
                    self.status_var.set("Run on startup enabled (via Task Scheduler).")
                else:
                    logger.error(f"[Startup] Task creation failed: {result.stderr}")
                    self.status_var.set(f"Failed to enable startup: {result.stderr}")
                    raise Exception(f"Task creation failed: {result.stderr}")
            else:
                # Delete the scheduled task
                cmd = ['schtasks', '/Delete', '/TN', task_name, '/F']
                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode == 0:
                    logger.info("[Startup] Task deleted successfully")
                    self.status_var.set("Run on startup disabled (via Task Scheduler).")
                else:
                    # Task might not exist, which is fine
                    if "not found" in result.stderr.lower() or "could not be found" in result.stderr.lower():
                        logger.info("[Startup] Task not found to delete")
                        self.status_var.set("Run on startup disabled (was not enabled).")
                    else:
                        logger.error(f"[Startup] Task deletion failed: {result.stderr}")
                        self.status_var.set(f"Failed to disable startup: {result.stderr}")
                        raise Exception(f"Task deletion failed: {result.stderr}")
                        
        except Exception as e:
            logger.error(f"[Startup] Task Scheduler error: {e}")
            self.status_var.set(f"Failed to {'enable' if enable else 'disable'} startup via Task Scheduler: {e}")
            raise

    def _set_startup_registry(self, enable: bool):
        """Add or remove FrogPaper from the Windows startup registry key.
        
        Handles both source and EXE modes, quoted paths with spaces, avoids duplicates,
        removes cleanly when disabled, and logs failures clearly.
        """
        try:
            import winreg
            import sys
            from pathlib import Path
            
            # Try KEY_ALL_ACCESS first for better permission handling
            try:
                key = winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER,
                    r"Software\Microsoft\Windows\CurrentVersion\Run",
                    0, winreg.KEY_ALL_ACCESS
                )
            except PermissionError:
                # Fallback to KEY_SET_VALUE if KEY_ALL_ACCESS fails
                logger.warning("[Startup] KEY_ALL_ACCESS failed, trying KEY_SET_VALUE")
                key = winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER,
                    r"Software\Microsoft\Windows\CurrentVersion\Run",
                    0, winreg.KEY_SET_VALUE
                )
            
            if enable:
                # Determine the correct launch command based on execution mode
                if getattr(sys, 'frozen', False):
                    # Running as PyInstaller EXE
                    exe_path = Path(sys.executable).resolve()
                    # Use quotes to handle paths with spaces
                    target = f'"{exe_path}"'
                    logger.info(f"[Startup] Setting startup for EXE at: {target}")
                else:
                    # Running as script — launch via python
                    import __main__
                    script_path = Path(getattr(__main__, '__file__', 'app.py')).resolve()
                    python_exe = Path(sys.executable).resolve()
                    target = f'"{python_exe}" "{script_path}"'
                    logger.info(f"[Startup] Setting startup for script at: {target}")
                
                # Check for existing entry to avoid duplicates
                try:
                    existing_value = winreg.QueryValueEx(key, "FrogPaper")[0]
                    if existing_value == target:
                        logger.info("[Startup] Registry entry already exists with correct value, skipping.")
                        winreg.CloseKey(key)
                        return
                    else:
                        logger.info(f"[Startup] Updating existing registry entry. Old: {existing_value}, New: {target}")
                except FileNotFoundError:
                    logger.info("[Startup] No existing registry entry found, creating new one.")
                
                # Set the new value
                winreg.SetValueEx(key, "FrogPaper", 0, winreg.REG_SZ, target)
                logger.info(f"[Startup] Registry entry added successfully: {target}")
                self.status_var.set("Run on startup enabled.")
            else:
                # Remove the registry entry
                try:
                    existing_value = winreg.QueryValueEx(key, "FrogPaper")[0]
                    winreg.DeleteValue(key, "FrogPaper")
                    logger.info(f"[Startup] Registry entry removed successfully: {existing_value}")
                    self.status_var.set("Run on startup disabled.")
                except FileNotFoundError:
                    logger.info("[Startup] No registry entry found to remove.")
                    self.status_var.set("Run on startup disabled (was not enabled).")
                except Exception as e:
                    logger.error(f"[Startup] Error removing registry entry: {e}")
                    self.status_var.set(f"Error disabling startup: {e}")
                    raise
            
            winreg.CloseKey(key)
        except PermissionError as e:
            logger.error(f"[Startup] Permission denied accessing registry: {e}")
            # Try alternative method using Task Scheduler
            self._set_startup_task_scheduler(enable)
        except Exception as e:
            logger.error(f"[Startup] Registry error: {e}")
            self.status_var.set(f"Failed to {'enable' if enable else 'disable'} startup: {e}")
            raise

    def _on_run_on_startup_changed(self):
        """Handle run-on-startup toggle."""
        new_value = self.run_on_startup_var.get()
        try:
            self._set_startup_registry(new_value)
            self.run_on_startup_enabled = new_value
            state = "enabled" if new_value else "disabled"
            self.status_var.set(f"Run on startup {state}.")
        except Exception as e:
            # If both methods fail, revert the checkbox
            logger.error(f"[Startup] Failed to change startup setting: {e}")
            self.run_on_startup_var.set(self.run_on_startup_enabled)
            self.status_var.set(f"Failed to change startup setting. Try running as administrator.")
