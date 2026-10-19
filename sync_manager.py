"""
sync_manager.py
---------------
Cloud sync engine for FrogPaper with delta sync, conflict resolution, and favorites protection.
"""

import hashlib
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

from utils import get_app_dir, load_config

logger = logging.getLogger(__name__)

BASE_DIR = get_app_dir()
WALLPAPERS_DIR = BASE_DIR / "wallpapers"
GENERATED_DIR = WALLPAPERS_DIR / "generated"
MANUAL_DIR = WALLPAPERS_DIR / "manual"
FAVORITES_DIR = WALLPAPERS_DIR / "favorites"
STYLED_DIR = WALLPAPERS_DIR / "styled"

SYNC_METADATA_FILE = BASE_DIR / "sync_metadata.json"


class SyncManager:
    """Manages cloud sync with delta detection and conflict resolution."""
    
    def __init__(self, app):
        self.app = app
        self.sync_metadata = self._load_sync_metadata()
        self.sync_in_progress = False
        self.sync_progress = 0
        self.sync_total = 0
        self.sync_status = "Idle"
        self.providers = {}
        
    def _load_sync_metadata(self) -> Dict:
        """Load sync metadata from JSON file."""
        try:
            if SYNC_METADATA_FILE.exists():
                import json
                with open(SYNC_METADATA_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load sync metadata: {e}")
        return {"files": {}, "last_sync": None}
    
    def pre_authenticate(self, main_root=None):
        """Pre-authenticate all cloud providers on the main thread.
        
        This should be called BEFORE spawning the background sync thread so that
        any OAuth dialogs (e.g. Dropbox re-auth) run safely on the main thread.
        
        Args:
            main_root: The app's main tkinter root window for OAuth dialogs.
        """
        self._initialize_providers(main_root=main_root)
        # Only return actually authenticated providers
        self.providers = {k: v for k, v in self.providers.items() if v.authenticated}
        return self.providers
    
    def _initialize_providers(self, main_root=None):
        """Initialize cloud provider instances.
        
        Args:
            main_root: If provided, providers that need interactive re-auth will
                       use this window for dialogs. If None (background thread),
                       providers that need re-auth will be silently skipped.
        """
        from cloud_providers import get_provider
        from utils import has_oauth_token
        
        providers = {}
        
        logger.info("Initializing cloud providers...")
        
        if has_oauth_token("google_drive"):
            logger.info("Google Drive token found, initializing provider...")
            providers["google_drive"] = get_provider("google_drive")
            if providers["google_drive"]:
                success = providers["google_drive"].authenticate()
                logger.info(f"Google Drive authentication: {'success' if success else 'failed'}")
        
        if has_oauth_token("onedrive"):
            logger.info("OneDrive token found, initializing provider...")
            providers["onedrive"] = get_provider("onedrive")
            if providers["onedrive"]:
                success = providers["onedrive"].authenticate()
                logger.info(f"OneDrive authentication: {'success' if success else 'failed'}")
        
        if has_oauth_token("dropbox"):
            logger.info("Dropbox token found, initializing provider...")
            providers["dropbox"] = get_provider("dropbox")
            if providers["dropbox"]:
                # Pass main_root only for Dropbox (has interactive OAuth flow)
                success = providers["dropbox"].authenticate(main_root=main_root)
                logger.info(f"Dropbox authentication: {'success' if success else 'failed'}")
                if success:
                    logger.info(f"Dropbox client authenticated: {providers['dropbox'].authenticated}")
                else:
                    logger.warning("Dropbox authentication failed")
        
        self.providers = providers
        logger.info(f"Initialized {len(providers)} cloud providers")
        return providers
    
    def _save_sync_metadata(self):
        """Save sync metadata to JSON file."""
        try:
            import json
            with open(SYNC_METADATA_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.sync_metadata, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save sync metadata: {e}")
    
    def _compute_file_hash(self, file_path: Path) -> str:
        """Compute SHA-256 hash of a file for delta detection."""
        try:
            hash_sha256 = hashlib.sha256()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_sha256.update(chunk)
            return hash_sha256.hexdigest()
        except Exception as e:
            logger.error(f"Failed to compute hash for {file_path}: {e}")
            return ""
    
    def _get_sync_scope(self) -> List[Path]:
        """Get list of directories to sync based on user settings."""
        config = load_config()
        sync_scope = config.get("sync_scope", "everything")
        
        directories = []
        
        if sync_scope == "favorites":
            directories = [FAVORITES_DIR]
        else:
            # "everything" or any unrecognized value → all wallpapers
            directories = [GENERATED_DIR, MANUAL_DIR, FAVORITES_DIR, STYLED_DIR]
        
        return [d for d in directories if d.exists()]
    
    def _is_favorite(self, file_path: Path) -> bool:
        """Check if a file is in the favorites directory."""
        try:
            return FAVORITES_DIR in file_path.parents or file_path.parent == FAVORITES_DIR
        except Exception:
            return False
    
    def _detect_changes(self) -> Tuple[List[Path], List[Path], List[Path]]:
        """Detect added, modified, and deleted files since last sync.
        
        Returns:
            Tuple of (added_files, modified_files, deleted_files)
        """
        added = []
        modified = []
        deleted = []
        
        sync_dirs = self._get_sync_scope()
        logger.info(f"Sync directories: {sync_dirs}")
        current_files = set()
        
        # Scan current files
        for directory in sync_dirs:
            logger.info(f"Scanning directory: {directory}")
            if not directory.exists():
                logger.warning(f"Directory does not exist: {directory}")
                continue
                
            for file_path in directory.rglob("*"):
                if file_path.is_file() and file_path.suffix.lower() in {'.png', '.jpg', '.jpeg', '.webp'}:
                    current_files.add(file_path)
                    current_hash = self._compute_file_hash(file_path)
                    file_key = str(file_path.relative_to(BASE_DIR))
                    
                    logger.info(f"Found file: {file_key}")
                    
                    if file_key not in self.sync_metadata["files"]:
                        added.append(file_path)
                        logger.info(f"Added file detected: {file_key}")
                    elif self.sync_metadata["files"][file_key]["hash"] != current_hash:
                        modified.append(file_path)
                        logger.info(f"Modified file detected: {file_key}")
        
        logger.info(f"Total files found: {len(current_files)}, Added: {len(added)}, Modified: {len(modified)}")
        
        # Detect deleted files
        for file_key in self.sync_metadata["files"]:
            file_path = BASE_DIR / file_key
            if file_path not in current_files:
                deleted.append(file_path)
        
        return added, modified, deleted
    
    def _resolve_conflict(self, local_file: Path, remote_file: Path, is_manual: bool = False) -> Path:
        """Resolve sync conflict between local and remote files.
        
        Args:
            local_file: Local file path
            remote_file: Remote/cloud file path
            is_manual: If True, prompt user for choice; if False, use "local wins" policy
            
        Returns:
            Path to the file that should be kept
        """
        # Protect favorites from overwrite
        if self._is_favorite(local_file):
            logger.info(f"Protecting favorite from overwrite: {local_file.name}")
            return local_file
        
        if is_manual:
            # messagebox cannot be called from a background thread.
            # If this is ever needed, use root.after(0, ...) with a
            # threading.Event to wait for the result.
            logger.warning(
                "Manual conflict resolution requested from background thread "
                "— falling back to local-wins policy for %s",
                local_file.name,
            )
            return local_file
        else:
            # Automatic sync: "local wins" policy
            logger.info(f"Auto-resolving conflict with 'local wins' policy: {local_file.name}")
            return local_file
    
    def perform_sync(self, is_manual: bool = False) -> Dict:
        """Perform sync with cloud storage.
        
        Args:
            is_manual: If True, use user choice for conflicts; if False, use "local wins"
            
        Returns:
            Dict with sync results: added, modified, deleted, conflicts, errors
        """
        logger.info("Starting sync process...")
        if self.sync_in_progress:
            logger.warning("Sync already in progress")
            return {"status": "busy"}
        
        self.sync_in_progress = True
        self.sync_status = "Initializing providers..."
        self.sync_progress = 0
        results = {
            "added": 0,
            "modified": 0,
            "deleted": 0,
            "conflicts": 0,
            "errors": 0,
            # Files already in the cloud that this install is not allowed to
            # overwrite (uploaded by a different OAuth client). Counted apart
            # from errors because retrying can never fix them.
            "unwritable": 0,
            "status": "completed"
        }
        
        try:
            # Initialize cloud providers (skip if already authenticated from pre_authenticate)
            already_authed = all(p.authenticated for p in self.providers.values()) if self.providers else False
            if not already_authed:
                logger.info("Initializing cloud providers...")
                self._initialize_providers()  # No main_root — safe for background thread
            else:
                logger.info(f"Reusing {len(self.providers)} pre-authenticated providers")
            
            # Filter out any providers that failed authentication
            self.providers = {k: v for k, v in self.providers.items() if v.authenticated}
            
            if not self.providers:
                logger.info("No cloud providers available, skipping sync")
                self.sync_status = "No cloud connection"
                results["status"] = "no_cloud"
                return results
            
            logger.info(f"Cloud providers initialized: {list(self.providers.keys())}")
            
            # Detect changes
            self.sync_status = "Detecting changes..."
            logger.info("Detecting file changes...")
            added, modified, deleted = self._detect_changes()
            self.sync_total = len(added) + len(modified) + len(deleted)
            
            logger.info(f"Changes detected: {len(added)} added, {len(modified)} modified, {len(deleted)} deleted")
            
            if self.sync_total == 0:
                self.sync_status = "No changes to sync"
                logger.info("No changes detected, skipping sync")
                return results
            
            # Process added files
            self.sync_status = "Uploading new files..."
            for idx, file_path in enumerate(added):
                try:
                    self.sync_progress = idx + 1
                    uploaded = self._upload_file(file_path)
                    if uploaded:  # Only count if at least one upload succeeded
                        results["added"] += 1
                        self._update_single_file_metadata(file_path, uploaded)
                        self._save_sync_metadata()  # persist after each file
                    else:
                        logger.warning(f"Upload failed for {file_path}, not counting as added")
                        self._count_upload_failure(results, file_path)
                except Exception as e:
                    logger.error(f"Failed to upload {file_path}: {e}")
                    results["errors"] += 1
            
            # Process modified files (with conflict resolution)
            self.sync_status = "Syncing modified files..."
            offset = len(added)
            for idx, file_path in enumerate(modified):
                try:
                    self.sync_progress = offset + idx + 1
                    # Check for conflicts (simplified - in real implementation would check remote)
                    if self._is_favorite(file_path):
                        logger.info(f"Skipping favorite modification: {file_path.name}")
                        continue
                    
                    uploaded = self._upload_file(file_path)
                    if uploaded:
                        results["modified"] += 1
                        self._update_single_file_metadata(file_path, uploaded)
                        self._save_sync_metadata()  # persist after each file
                    else:
                        # A failed update must never be reported as a synced
                        # change: the cloud copy is still the old bytes.
                        logger.warning(
                            f"Upload failed for {file_path}, not counting as modified")
                        self._count_upload_failure(results, file_path)
                except Exception as e:
                    logger.error(f"Failed to upload modified {file_path}: {e}")
                    results["errors"] += 1
            
            # Process deleted files
            self.sync_status = "Removing deleted files..."
            offset = len(added) + len(modified)
            for idx, file_path in enumerate(deleted):
                try:
                    self.sync_progress = offset + idx + 1
                    self._delete_remote_file(file_path)
                    results["deleted"] += 1
                    # Remove from metadata
                    file_key = str(file_path.relative_to(BASE_DIR))
                    self.sync_metadata["files"].pop(file_key, None)
                    self._save_sync_metadata()  # persist after each deletion
                except Exception as e:
                    logger.error(f"Failed to delete remote {file_path}: {e}")
                    results["errors"] += 1
            
            # Final metadata refresh + timestamp
            self.sync_status = "Updating metadata..."
            self._update_sync_metadata()
            self.sync_metadata["last_sync"] = datetime.now().isoformat()
            self._save_sync_metadata()

            # Portable metadata (tags / prompt params / safe config) so a
            # restore can rebuild the library, not just the image files.
            self.sync_status = "Backing up metadata..."
            self._upload_backup_manifest(results)
            
            # Update last backup timestamp in UI
            if hasattr(self.app, 'last_backup_var'):
                self.app.last_backup_var.set(f"Last backup: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
            
            self.sync_status = "Complete"
            self.sync_progress = self.sync_total
            logger.info(f"Sync completed: {results}")
            
        except Exception as e:
            logger.error(f"Sync failed: {e}")
            self.sync_status = "Failed"
            results["status"] = "failed"
            results["errors"] += 1
        finally:
            self.sync_in_progress = False
        
        return results
    
    def _get_cloud_subfolder(self, file_path: Path) -> str:
        """Determine the cloud subfolder name based on the local directory.
        
        Maps local folders to cloud subfolder names:
          wallpapers/generated -> 'Generated'
          wallpapers/favorites -> 'Favorites'
          wallpapers/styled    -> 'Styled'
        """
        try:
            parent_name = file_path.parent.name.lower()
            mapping = {
                'generated': 'Generated',
                'manual': 'Manual',
                'favorites': 'Favorites',
                'styled': 'Styled',
            }
            return mapping.get(parent_name, '')
        except Exception:
            return ''

    def _count_upload_failure(self, results, file_path):
        """Record an upload that did not happen, distinguishing permission.

        ``_upload_file`` sets ``self._last_unwritable`` when every provider that
        failed did so because the remote copy belongs to another client. Those
        files need a human decision, not a retry, so they get their own tally
        instead of inflating the generic error count.
        """
        results["errors"] += 1
        if getattr(self, "_last_unwritable", False):
            results["unwritable"] += 1
            logger.warning(
                f"{file_path} exists in the cloud but belongs to another "
                "FrogPaper install; it cannot be overwritten by this one")

    def _upload_file(self, file_path: Path) -> Dict[str, str]:
        """Upload a file to all connected cloud providers.

        Determines the correct cloud subfolder based on the file's local
        directory and passes it to each provider. Returns ``{provider: id}``
        so the id can be recorded and the remote copy deleted later.
        """
        logger.info(f"Attempting to upload: {file_path}")
        
        if not self.providers:
            logger.error("No cloud providers available for upload")
            return None
        
        subfolder = self._get_cloud_subfolder(file_path)
        logger.info(f"Available providers: {list(self.providers.keys())}, subfolder: {subfolder or '(root)'}")
        
        uploaded = {}
        self._last_unwritable = False  # never inherit the previous file's verdict
        unwritable = False
        failed = 0
        for provider_name, provider in self.providers.items():
            try:
                logger.info(f"Uploading to {provider_name}...")
                logger.info(f"Provider authenticated: {provider.authenticated}")
                result = provider.upload_file(file_path, subfolder=subfolder)
                if result:
                    uploaded[provider_name] = result
                    logger.info(f"Synced {file_path.name} to {provider_name}")
                else:
                    failed += 1
                    unwritable = unwritable or (
                        getattr(provider, "last_upload_reason", None) == "no_access")
                    logger.warning(f"Upload to {provider_name} returned None")
            except Exception as e:
                logger.error(f"Failed to upload to {provider_name}: {e}")
                import traceback
                logger.error(f"Upload error traceback: {traceback.format_exc()}")

        # Only a file that is unwritable on every failing provider gets the
        # special tally; a mixed result means a retry may still help.
        self._last_unwritable = bool(failed) and unwritable and not uploaded
        return uploaded
    
    def _upload_backup_manifest(self, results):
        """Write backup-manifest.json and push it to every provider.

        Non-fatal by design: a manifest problem must never fail a sync that
        already moved the images. Reuses the hashes ``_update_sync_metadata``
        just computed, so this costs no extra disk reads.
        """
        try:
            import backup_manifest

            hashes = {}
            for file_key, entry in self.sync_metadata.get("files", {}).items():
                digest = entry.get("hash") if isinstance(entry, dict) else None
                if digest:
                    hashes[file_key.replace("\\", "/")] = digest

            path, manifest = backup_manifest.write_manifest(
                BASE_DIR, hashes=hashes)
        except Exception as e:
            logger.warning(f"Could not write backup manifest: {e}")
            results["manifest_error"] = str(e)
            return

        uploaded = 0
        for provider_name, provider in (self.providers or {}).items():
            try:
                if provider.upload_file(path, subfolder=""):
                    uploaded += 1
                    logger.info(f"Uploaded backup manifest to {provider_name}")
            except Exception as e:
                logger.warning(f"Manifest upload to {provider_name} failed: {e}")

        results["manifest_images"] = len(manifest["images"])
        results["manifest_uploaded"] = uploaded

    def _delete_remote_file(self, file_path: Path):
        """Delete the remote copies of a locally deleted file.

        Deletes only when a remote id was recorded *and* the remote size still
        matches what we uploaded -- a file edited by hand in the cloud is left
        alone rather than silently destroyed.
        """
        try:
            file_key = str(file_path.relative_to(BASE_DIR))
        except ValueError:
            logger.warning(
                f"{file_path} is outside the app directory; skipping remote delete")
            return

        entry = (self.sync_metadata.get("files") or {}).get(file_key) or {}
        remote = entry.get("remote") or {}
        if not remote:
            logger.info(
                f"No remote id recorded for {file_key}; leaving the cloud copy")
            return

        expected_size = entry.get("size")
        for provider_name, file_ref in remote.items():
            provider = (self.providers or {}).get(provider_name)
            if provider is None or not getattr(provider, "authenticated", False):
                logger.info(f"Skipping remote delete on {provider_name}: not connected")
                continue
            try:
                actual_size = provider.get_file_size(file_ref)
                if (expected_size is not None and actual_size is not None
                        and int(actual_size) != int(expected_size)):
                    logger.info(
                        f"{file_key} changed on {provider_name}; not deleting")
                    continue
                if provider.delete_file(file_ref):
                    logger.info(f"Deleted {file_key} from {provider_name}")
            except Exception as e:
                logger.warning(
                    f"Remote delete failed for {file_key} on {provider_name}: {e}")
    
    def _update_single_file_metadata(self, file_path: Path, remote=None):
        """Update metadata for a single file (called after each successful upload)."""
        file_key = str(file_path.relative_to(BASE_DIR))
        file_hash = self._compute_file_hash(file_path)
        previous = self.sync_metadata["files"].get(file_key) or {}
        merged_remote = dict(previous.get("remote") or {})
        merged_remote.update(remote or {})
        self.sync_metadata["files"][file_key] = {
            "hash": file_hash,
            "modified": datetime.fromtimestamp(file_path.stat().st_mtime).isoformat(),
            "size": file_path.stat().st_size,
            "remote": merged_remote,
        }

    def _update_sync_metadata(self):
        """Full metadata refresh — scans all local files and rebuilds the file index."""
        sync_dirs = self._get_sync_scope()
        
        for directory in sync_dirs:
            for file_path in directory.rglob("*"):
                if file_path.is_file() and file_path.suffix.lower() in {'.png', '.jpg', '.jpeg', '.webp'}:
                    file_key = str(file_path.relative_to(BASE_DIR))
                    file_hash = self._compute_file_hash(file_path)
                    
                    existing = self.sync_metadata["files"].get(file_key) or {}
                    entry = {
                        "hash": file_hash,
                        "modified": datetime.fromtimestamp(file_path.stat().st_mtime).isoformat(),
                        "size": file_path.stat().st_size,
                    }
                    if existing.get("remote"):
                        entry["remote"] = existing["remote"]
                    self.sync_metadata["files"][file_key] = entry
    
    def get_sync_status(self) -> Dict:
        """Get current sync status for UI display."""
        return {
            "last_sync": self.sync_metadata.get("last_sync"),
            "in_progress": self.sync_in_progress,
            "files_tracked": len(self.sync_metadata.get("files", {})),
            "cloud_connected": any([
                self._has_cloud_connection("google_drive"),
                self._has_cloud_connection("onedrive"),
                self._has_cloud_connection("dropbox")
            ])
        }
    
    def _has_cloud_connection(self, provider: str) -> bool:
        """Check if specific cloud provider is connected."""
        from utils import has_oauth_token
        return has_oauth_token(provider)
