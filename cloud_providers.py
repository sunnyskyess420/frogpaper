"""
cloud_providers.py
------------------
OAuth and API integration for cloud storage providers (Google Drive, OneDrive, Dropbox).
"""

import logging
import webbrowser
from typing import Dict, Optional, List
from pathlib import Path

logger = logging.getLogger(__name__)

# Google Drive OAuth configuration
GOOGLE_CLIENT_ID = "YOUR_GOOGLE_CLIENT_ID"  # Will be loaded from config
GOOGLE_CLIENT_SECRET = "YOUR_GOOGLE_CLIENT_SECRET"  # Will be loaded from config
GOOGLE_REDIRECT_URI = "http://localhost:8080/callback"
GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive.metadata.readonly"
]

# OneDrive OAuth configuration
ONEDRIVE_CLIENT_ID = "YOUR_ONEDRIVE_CLIENT_ID"  # Will be loaded from config
ONEDRIVE_CLIENT_SECRET = "YOUR_ONEDRIVE_CLIENT_SECRET"  # Will be loaded from config
ONEDRIVE_REDIRECT_URI = "http://localhost:8080/callback"
ONEDRIVE_SCOPES = ["Files.ReadWrite"]

# Dropbox OAuth configuration
DROPBOX_APP_KEY = "YOUR_DROPBOX_APP_KEY"  # Will be loaded from config
DROPBOX_APP_SECRET = "YOUR_DROPBOX_APP_SECRET"  # Will be loaded from config
DROPBOX_REDIRECT_URI = "http://localhost:8080/callback"


def load_config_credentials():
    """Load OAuth credentials from config.json."""
    global GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET
    global ONEDRIVE_CLIENT_ID, ONEDRIVE_CLIENT_SECRET
    global DROPBOX_APP_KEY, DROPBOX_APP_SECRET
    
    try:
        from utils import load_config
        config = load_config()
        
        if config.get("google_client_id"):
            GOOGLE_CLIENT_ID = config["google_client_id"]
        if config.get("google_client_secret"):
            GOOGLE_CLIENT_SECRET = config["google_client_secret"]
        
        if config.get("onedrive_client_id"):
            ONEDRIVE_CLIENT_ID = config["onedrive_client_id"]
        if config.get("onedrive_client_secret"):
            ONEDRIVE_CLIENT_SECRET = config["onedrive_client_secret"]
        
        if config.get("dropbox_app_key"):
            DROPBOX_APP_KEY = config["dropbox_app_key"]
        if config.get("dropbox_app_secret"):
            DROPBOX_APP_SECRET = config["dropbox_app_secret"]
            
        logger.info("Loaded OAuth credentials from config")
    except Exception as e:
        logger.warning(f"Failed to load OAuth credentials from config: {e}")


# Load credentials on module import
load_config_credentials()


class GoogleDriveProvider:
    """Google Drive OAuth and API integration."""
    
    def __init__(self):
        self.service = None
        self.authenticated = False
        self._folder_id_cache = None  # Cache FrogPaper folder ID for the session
        self._subfolder_cache = {}    # Cache subfolder IDs: {"Generated": "id1", ...}
        
    def authenticate(self) -> bool:
        """Authenticate with Google Drive via OAuth."""
        try:
            from google_auth_oauthlib.flow import InstalledAppFlow
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            import json
            
            # Try to load existing credentials from token storage
            from utils import get_oauth_token
            token_data = get_oauth_token("google_drive")
            
            if token_data:
                try:
                    credentials = Credentials.from_authorized_user_info(
                        json.loads(token_data), GOOGLE_SCOPES
                    )
                    if credentials.valid:
                        self.service = self._build_service(credentials)
                        self.authenticated = True
                        logger.info("Google Drive authenticated from stored token")
                        return True
                    elif credentials.expired and credentials.refresh_token:
                        credentials.refresh(Request())
                        self._save_token(credentials)
                        self.service = self._build_service(credentials)
                        self.authenticated = True
                        logger.info("Google Drive token refreshed")
                        return True
                except Exception as e:
                    logger.warning(f"Failed to load Google Drive credentials: {e}")
            
            # Need new authentication flow
            flow = InstalledAppFlow.from_client_config(
                {
                    "installed": {
                        "client_id": GOOGLE_CLIENT_ID,
                        "client_secret": GOOGLE_CLIENT_SECRET,
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "redirect_uris": [GOOGLE_REDIRECT_URI]
                    }
                },
                scopes=GOOGLE_SCOPES
            )
            
            credentials = flow.run_local_server(port=8080)
            
            # Save token
            self._save_token(credentials)
            
            # Build service
            self.service = self._build_service(credentials)
            self.authenticated = True
            logger.info("Google Drive authentication successful")
            return True
            
        except ImportError:
            logger.error("Google Drive libraries not installed. Install: pip install google-api-python-client google-auth-oauthlib")
            return False
        except Exception as e:
            logger.error(f"Google Drive authentication failed: {e}")
            return False
    
    def _build_service(self, credentials):
        """Build Google Drive service object."""
        from googleapiclient.discovery import build
        return build('drive', 'v3', credentials=credentials)
    
    def _save_token(self, credentials):
        """Save OAuth token to storage."""
        from utils import save_oauth_token
        import json
        token_data = json.dumps({
            "token": credentials.token,
            "refresh_token": credentials.refresh_token,
            "token_uri": credentials.token_uri,
            "client_id": credentials.client_id,
            "client_secret": credentials.client_secret,
            "scopes": credentials.scopes
        })
        save_oauth_token("google_drive", token_data)

    def _ensure_frogpaper_folder(self) -> Optional[str]:
        """Find or create a 'FrogPaper' folder in Google Drive and return its ID.
        
        Results are cached for the lifetime of this provider instance so we don't
        make a redundant API call on every single file upload.
        """
        if self._folder_id_cache:
            return self._folder_id_cache
        
        if not self.authenticated or not self.service:
            return None
        try:
            results = self.service.files().list(
                q="name='FrogPaper' and mimeType='application/vnd.google-apps.folder' and trashed=false",
                fields="files(id, name)",
                spaces="drive"
            ).execute()
            folders = results.get('files', [])
            if folders:
                folder_id = folders[0]['id']
                logger.info(f"FrogPaper folder found: {folder_id}")
                self._folder_id_cache = folder_id
                return folder_id
            file_metadata = {
                'name': 'FrogPaper',
                'mimeType': 'application/vnd.google-apps.folder'
            }
            folder = self.service.files().create(
                body=file_metadata,
                fields='id'
            ).execute()
            folder_id = folder.get('id')
            logger.info(f"FrogPaper folder created: {folder_id}")
            self._folder_id_cache = folder_id
            return folder_id
        except Exception as e:
            logger.error(f"Failed to find/create FrogPaper folder: {e}")
            return None

    def _ensure_subfolder(self, parent_id: str, subfolder_name: str) -> Optional[str]:
        """Find or create a subfolder inside a parent folder. Results are cached."""
        if subfolder_name in self._subfolder_cache:
            return self._subfolder_cache[subfolder_name]

        try:
            query = f"name='{subfolder_name}' and '{parent_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
            results = self.service.files().list(
                q=query,
                fields="files(id, name)",
                spaces="drive"
            ).execute()
            folders = results.get('files', [])
            if folders:
                folder_id = folders[0]['id']
                logger.info(f"Subfolder '{subfolder_name}' found: {folder_id}")
                self._subfolder_cache[subfolder_name] = folder_id
                return folder_id

            file_metadata = {
                'name': subfolder_name,
                'mimeType': 'application/vnd.google-apps.folder',
                'parents': [parent_id]
            }
            folder = self.service.files().create(
                body=file_metadata,
                fields='id'
            ).execute()
            folder_id = folder.get('id')
            logger.info(f"Subfolder '{subfolder_name}' created: {folder_id}")
            self._subfolder_cache[subfolder_name] = folder_id
            return folder_id
        except Exception as e:
            logger.error(f"Failed to find/create subfolder '{subfolder_name}': {e}")
            return None

    def upload_file(self, file_path: Path, folder_id: Optional[str] = None, subfolder: str = "") -> Optional[str]:
        """Upload file to Google Drive, inside the FrogPaper folder.

        If a file with the same name already exists in the folder, it will be
        updated in-place instead of creating a duplicate.
        """
        if not self.authenticated or not self.service:
            logger.error("Google Drive not authenticated")
            return None

        parent_folder = folder_id or self._ensure_frogpaper_folder()
        if not parent_folder:
            logger.error("No target folder available")
            return None

        # Resolve subfolder if specified (e.g. "Generated", "Favorites", "Styled")
        if subfolder:
            target_folder = self._ensure_subfolder(parent_folder, subfolder)
            if not target_folder:
                logger.error(f"Could not create subfolder '{subfolder}', falling back to root")
                target_folder = parent_folder
        else:
            target_folder = parent_folder

        try:
            from googleapiclient.http import MediaFileUpload

            # Check if a file with the same name already exists in the folder
            existing_id = None
            local_size = file_path.stat().st_size
            query = f"name='{file_path.name}' and '{target_folder}' in parents and trashed=false"
            results = self.service.files().list(
                q=query,
                fields="files(id, name, size)",
                spaces="drive"
            ).execute()
            existing = results.get('files', [])
            if existing:
                existing_id = existing[0]['id']
                remote_size = int(existing[0].get('size', 0))
                if remote_size == local_size:
                    logger.info(f"Skipped {file_path.name} — unchanged ({local_size} bytes)")
                    return existing_id
                logger.info(f"Found existing file {file_path.name} (id={existing_id}), size changed {remote_size} -> {local_size}, updating")

            media = MediaFileUpload(str(file_path), resumable=True)

            if existing_id:
                # Update existing file -- no duplicates
                result = self.service.files().update(
                    fileId=existing_id,
                    media_body=media,
                    fields='id'
                ).execute()
                logger.info(f"Updated {file_path.name} in Google Drive FrogPaper folder")
            else:
                # Create new file
                file_metadata = {
                    'name': file_path.name,
                    'parents': [target_folder]
                }
                result = self.service.files().create(
                    body=file_metadata,
                    media_body=media,
                    fields='id'
                ).execute()
                logger.info(f"Uploaded {file_path.name} to Google Drive FrogPaper folder")

            return result.get('id')

        except Exception as e:
            logger.error(f"Failed to upload to Google Drive: {e}")
            return None
    
    def list_files(self, folder_id: Optional[str] = None) -> List[Dict]:
        """List files in Google Drive."""
        if not self.authenticated or not self.service:
            logger.error("Google Drive not authenticated")
            return []
        
        try:
            query = f"'{folder_id}' in parents" if folder_id else ""
            results = self.service.files().list(
                q=query,
                fields="files(id, name, mimeType, size, modifiedTime)"
            ).execute()
            
            files = results.get('files', [])
            logger.info(f"Listed {len(files)} files from Google Drive")
            return files
            
        except Exception as e:
            logger.error(f"Failed to list Google Drive files: {e}")
            return []
    
    def download_file(self, file_id: str, dest_path: Path) -> bool:
        """Download file from Google Drive."""
        if not self.authenticated or not self.service:
            logger.error("Google Drive not authenticated")
            return False
        
        try:
            request = self.service.files().get_media(fileId=file_id)
            
            with open(dest_path, 'wb') as f:
                from googleapiclient.http import MediaIoBaseDownload
                downloader = MediaIoBaseDownload(f, request)
                done = False
                while done is False:
                    status, done = downloader.next_chunk()
            
            logger.info(f"Downloaded file {file_id} to {dest_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to download from Google Drive: {e}")
            return False


class OneDriveProvider:
    """OneDrive OAuth and API integration."""
    
    def __init__(self):
        self.client = None
        self.authenticated = False
        self._folder_id_cache = None  # Cache FrogPaper folder ID for the session
        self._subfolder_cache = {}    # Cache subfolder IDs: {"Generated": "id1", ...}
        
    def authenticate(self) -> bool:
        """Authenticate with OneDrive via OAuth."""
        try:
            import msal
            
            # Try to load existing token
            from utils import get_oauth_token
            token_data = get_oauth_token("onedrive")
            
            app = msal.PublicClientApplication(
                client_id=ONEDRIVE_CLIENT_ID,
                authority="https://login.microsoftonline.com/common"
            )
            
            if token_data:
                try:
                    import json
                    token_cache = json.loads(token_data)
                    app.token_cache.deserialize(token_cache)
                    
                    accounts = app.get_accounts()
                    if accounts:
                        result = app.acquire_token_silent(ONEDRIVE_SCOPES, account=accounts[0])
                        if result and "access_token" in result:
                            self.client = result["access_token"]
                            self.authenticated = True
                            logger.info("OneDrive authenticated from stored token")
                            return True
                except Exception as e:
                    logger.warning(f"Failed to load OneDrive credentials: {e}")
            
            # Need new authentication
            result = app.acquire_token_interactive(
                scopes=ONEDRIVE_SCOPES,
                redirect_uri=ONEDRIVE_REDIRECT_URI
            )
            
            if "access_token" in result:
                self.client = result["access_token"]
                self.authenticated = True
                
                # Save token cache
                self._save_token(app.token_cache.serialize())
                
                logger.info("OneDrive authentication successful")
                return True
            else:
                logger.error(f"OneDrive authentication failed: {result.get('error_description')}")
                return False
                
        except ImportError:
            logger.error("OneDrive libraries not installed. Install: pip install msal")
            return False
        except Exception as e:
            logger.error(f"OneDrive authentication failed: {e}")
            return False
    
    def _save_token(self, token_cache: str):
        """Save OAuth token to storage."""
        from utils import save_oauth_token
        save_oauth_token("onedrive", token_cache)
    
    def _ensure_frogpaper_folder(self) -> Optional[str]:
        """Find or create a FrogPaper folder in OneDrive and return its ID.
        
        Results are cached for the lifetime of this provider instance.
        """
        if self._folder_id_cache:
            return self._folder_id_cache
        
        if not self.authenticated or not self.client:
            return None
        try:
            import requests
            headers = {"Authorization": f"Bearer {self.client}"}
            # Check if folder exists
            resp = requests.get(
                "https://graph.microsoft.com/v1.0/me/drive/root/children?$filter=name eq 'FrogPaper'",
                headers=headers
            )
            items = resp.json().get("value", [])
            if items:
                folder_id = items[0]["id"]
                logger.info(f"FrogPaper folder found in OneDrive: {folder_id}")
                self._folder_id_cache = folder_id
                return folder_id
            # Create it
            resp = requests.post(
                "https://graph.microsoft.com/v1.0/me/drive/root/children",
                headers={**headers, "Content-Type": "application/json"},
                json={"name": "FrogPaper", "folder": {}, "@microsoft.graph.conflictBehavior": "rename"}
            )
            if resp.status_code == 201:
                folder_id = resp.json()["id"]
                logger.info(f"FrogPaper folder created in OneDrive: {folder_id}")
                self._folder_id_cache = folder_id
                return folder_id
            logger.error(f"Failed to create OneDrive FrogPaper folder: {resp.text}")
            return None
        except Exception as e:
            logger.error(f"Failed to find/create OneDrive FrogPaper folder: {e}")
            return None

    def _ensure_subfolder(self, parent_id: str, subfolder_name: str) -> Optional[str]:
        """Find or create a subfolder inside a parent folder. Results are cached."""
        if subfolder_name in self._subfolder_cache:
            return self._subfolder_cache[subfolder_name]

        try:
            import requests
            headers = {"Authorization": f"Bearer {self.client}"}
            resp = requests.get(
                f"https://graph.microsoft.com/v1.0/me/drive/items/{parent_id}/children?$filter=name eq '{subfolder_name}'",
                headers=headers
            )
            items = resp.json().get("value", [])
            if items:
                folder_id = items[0]["id"]
                logger.info(f"OneDrive subfolder '{subfolder_name}' found: {folder_id}")
                self._subfolder_cache[subfolder_name] = folder_id
                return folder_id

            resp = requests.post(
                f"https://graph.microsoft.com/v1.0/me/drive/items/{parent_id}/children",
                headers={**headers, "Content-Type": "application/json"},
                json={"name": subfolder_name, "folder": {}, "@microsoft.graph.conflictBehavior": "rename"}
            )
            if resp.status_code == 201:
                folder_id = resp.json()["id"]
                logger.info(f"OneDrive subfolder '{subfolder_name}' created: {folder_id}")
                self._subfolder_cache[subfolder_name] = folder_id
                return folder_id
            logger.error(f"Failed to create OneDrive subfolder '{subfolder_name}': {resp.text}")
            return None
        except Exception as e:
            logger.error(f"Failed to find/create OneDrive subfolder '{subfolder_name}': {e}")
            return None

    def upload_file(self, file_path: Path, folder_id: Optional[str] = None, subfolder: str = "") -> Optional[str]:
        """Upload file to OneDrive, inside the FrogPaper folder.

        If a file with the same name already exists, it will be replaced
        in-place instead of creating a duplicate.
        """
        if not self.authenticated or not self.client:
            logger.error("OneDrive not authenticated")
            return None

        try:
            import requests

            parent_folder = folder_id or self._ensure_frogpaper_folder()
            if not parent_folder:
                logger.error("No target folder available")
                return None

            # Resolve subfolder if specified
            if subfolder:
                target_folder = self._ensure_subfolder(parent_folder, subfolder)
                if not target_folder:
                    logger.error(f"Could not create subfolder '{subfolder}', falling back to root")
                    target_folder = parent_folder
            else:
                target_folder = parent_folder

            # Check if file already exists and is unchanged
            local_size = file_path.stat().st_size
            check_url = f"https://graph.microsoft.com/v1.0/me/drive/items/{target_folder}:/{file_path.name}"
            check_resp = requests.get(check_url, headers={"Authorization": f"Bearer {self.client}"})
            if check_resp.status_code == 200:
                remote_size = check_resp.json().get("size", 0)
                if remote_size == local_size:
                    logger.info(f"Skipped {file_path.name} — unchanged ({local_size} bytes)")
                    return check_resp.json().get("id")
                logger.info(f"Found existing {file_path.name} on OneDrive, size changed {remote_size} -> {local_size}, updating")

            upload_url = f"https://graph.microsoft.com/v1.0/me/drive/items/{target_folder}:/{file_path.name}:/createUploadSession"

            headers = {
                "Authorization": f"Bearer {self.client}",
                "Content-Type": "application/json"
            }

            # Tell OneDrive to replace existing files, not create duplicates
            body = {
                "item": {
                    "@microsoft.graph.conflictBehavior": "replace"
                }
            }

            response = requests.post(upload_url, headers=headers, json=body)
            if response.status_code == 200:
                upload_url = response.json().get("uploadUrl")

                # Upload file in chunks
                with open(file_path, 'rb') as f:
                    chunk_size = 327680  # 320KB chunks

                    for offset in range(0, local_size, chunk_size):
                        f.seek(offset)
                        chunk = f.read(chunk_size)

                        chunk_headers = {
                            "Authorization": f"Bearer {self.client}",
                            "Content-Length": str(len(chunk)),
                            "Content-Range": f"bytes {offset}-{min(offset + len(chunk) - 1, local_size - 1)}/{local_size}"
                        }

                        response = requests.put(upload_url, headers=chunk_headers, data=chunk)
                        if response.status_code not in [200, 201, 202]:
                            logger.error(f"Upload chunk failed: {response.text}")
                            return None

                logger.info(f"Uploaded {file_path.name} to OneDrive FrogPaper folder (replace mode)")
                return response.json().get("id")
            else:
                logger.error(f"Failed to create upload session: {response.text}")
                return None

        except Exception as e:
            logger.error(f"Failed to upload to OneDrive: {e}")
            return None
    
    def list_files(self, folder_id: Optional[str] = None) -> List[Dict]:
        """List files in OneDrive."""
        if not self.authenticated or not self.client:
            logger.error("OneDrive not authenticated")
            return []
        
        try:
            import requests
            
            endpoint = f"/me/drive/items/{folder_id}/children" if folder_id else "/me/drive/root/children"
            url = f"https://graph.microsoft.com/v1.0{endpoint}"
            
            headers = {
                "Authorization": f"Bearer {self.client}"
            }
            
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                files = response.json().get("value", [])
                logger.info(f"Listed {len(files)} files from OneDrive")
                return files
            else:
                logger.error(f"Failed to list OneDrive files: {response.text}")
                return []
                
        except Exception as e:
            logger.error(f"Failed to list OneDrive files: {e}")
            return []
    
    def download_file(self, file_id: str, dest_path: Path) -> bool:
        """Download file from OneDrive."""
        if not self.authenticated or not self.client:
            logger.error("OneDrive not authenticated")
            return False
        
        try:
            import requests
            
            url = f"https://graph.microsoft.com/v1.0/me/drive/items/{file_id}/content"
            headers = {
                "Authorization": f"Bearer {self.client}"
            }
            
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                with open(dest_path, 'wb') as f:
                    f.write(response.content)
                logger.info(f"Downloaded file {file_id} to {dest_path}")
                return True
            else:
                logger.error(f"Failed to download from OneDrive: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to download from OneDrive: {e}")
            return False


class DropboxProvider:
    """Dropbox OAuth and API integration."""
    
    def __init__(self):
        self.client = None
        self.authenticated = False
        self._folder_exists_cache = False  # Cache that FrogPaper folder was verified
    
    def _save_dropbox_token(self, access_token: str, refresh_token: str, expires_at: float):
        """Save Dropbox OAuth token data (access + refresh) as JSON."""
        import json, time
        from utils import save_oauth_token
        token_data = json.dumps({
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_at": expires_at,
        })
        save_oauth_token("dropbox", token_data)
        logger.info("Dropbox token data saved (access + refresh)")
    
    def _load_dropbox_token(self) -> Optional[dict]:
        """Load and parse stored Dropbox token data."""
        import json
        from utils import get_oauth_token
        token_data = get_oauth_token("dropbox")
        if not token_data:
            return None
        try:
            parsed = json.loads(token_data)
            if isinstance(parsed, dict) and "access_token" in parsed:
                return parsed
            # Legacy format: raw access token string — migrate
            logger.info("Legacy Dropbox token format detected, will re-authenticate")
            return None
        except (json.JSONDecodeError, TypeError):
            # Legacy raw string token
            logger.info("Dropbox token is not JSON, treating as legacy format")
            return None
    
    def _try_refresh_token(self, token_data: dict) -> bool:
        """Attempt to refresh an expired access token using the refresh token."""
        import dropbox
        refresh_token = token_data.get("refresh_token", "")
        if not refresh_token:
            logger.warning("No refresh token available for Dropbox")
            return False
        try:
            import requests
            resp = requests.post(
                "https://api.dropboxapi.com/oauth2/token",
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                    "client_id": DROPBOX_APP_KEY,
                    "client_secret": DROPBOX_APP_SECRET,
                },
                timeout=30,
            )
            if resp.status_code == 200:
                result = resp.json()
                new_access = result["access_token"]
                new_refresh = result.get("refresh_token", refresh_token)
                # Dropbox returns expires_in (seconds); default 4 hours if missing
                import time
                expires_in = result.get("expires_in", 14400)
                expires_at = time.time() + expires_in - 300  # 5-min buffer
                # Update stored tokens
                self._save_dropbox_token(new_access, new_refresh, expires_at)
                self.client = dropbox.Dropbox(new_access)
                self.client.users_get_current_account()
                self.authenticated = True
                logger.info("Dropbox token refreshed successfully")
                return True
            else:
                logger.warning(f"Dropbox token refresh failed: {resp.status_code} {resp.text}")
                return False
        except Exception as e:
            logger.warning(f"Dropbox token refresh error: {e}")
            return False
    
    def authenticate(self, main_root=None) -> bool:
        """Authenticate with Dropbox via OAuth.
        
        Args:
            main_root: The app's main tkinter root window. If provided, dialogs
                       will use this window (required when called from main thread).
                       If None, no interactive re-auth is attempted (safe for
                       background threads).
        """
        try:
            import dropbox
            from dropbox import DropboxOAuth2FlowNoRedirect
            import webbrowser, time, json
            
            # ── Try to load and use existing token ─────────────────────
            token_data = self._load_dropbox_token()
            
            if token_data:
                access_token = token_data["access_token"]
                expires_at = token_data.get("expires_at", 0)
                
                # If token hasn't expired yet, try using it directly
                if time.time() < expires_at:
                    try:
                        self.client = dropbox.Dropbox(access_token)
                        self.client.users_get_current_account()
                        self.authenticated = True
                        logger.info("Dropbox authenticated from stored token")
                        return True
                    except Exception as e:
                        logger.warning(f"Stored Dropbox token test failed: {e}")
                else:
                    logger.info("Dropbox access token expired, attempting refresh...")
                
                # Token expired or test failed — try refresh
                if self._try_refresh_token(token_data):
                    return True
                
                # Refresh failed — token is dead, clear it
                logger.warning("Dropbox token expired and refresh failed, need re-auth")
                from utils import delete_oauth_token
                delete_oauth_token("dropbox")
            
            # ── Need interactive OAuth re-authorization ─────────────────
            if main_root is None:
                logger.warning("Dropbox needs re-auth but no main_root provided (background thread). "
                               "Cannot show dialog. Please re-authenticate from the Settings tab.")
                return False
            
            auth_flow = DropboxOAuth2FlowNoRedirect(
                DROPBOX_APP_KEY,
                consumer_secret=DROPBOX_APP_SECRET,
                token_access_type='offline'
            )
            
            authorize_url = auth_flow.start()
            logger.info(f"Opening Dropbox authorization URL: {authorize_url}")
            webbrowser.open(authorize_url)
            
            # Use the app's main root window for dialogs (safe on main thread)
            from tkinter import simpledialog, messagebox
            
            messagebox.showinfo(
                "Dropbox Authorization",
                "1. A browser window should have opened with Dropbox.\n"
                "2. Sign in to your Dropbox account.\n"
                "3. Click 'Continue' then 'Allow' to authorize FrogPaper.\n"
                "4. Copy the authorization code shown on the page.\n\n"
                "Click OK to enter the authorization code.",
                parent=main_root
            )
            
            auth_code = simpledialog.askstring(
                "Dropbox Authorization",
                "Paste the authorization code from Dropbox:",
                parent=main_root,
                show='*'
            )
            
            if not auth_code:
                logger.error("No authorization code provided")
                return False
            
            try:
                auth_result = auth_flow.finish(auth_code)
                access_token = auth_result.access_token
                refresh_token = auth_result.refresh_token
                # Calculate expiry: Dropbox typically gives 4 hours
                expires_at = time.time() + 14400 - 300  # 5-min safety buffer
                
                # Save both tokens
                self._save_dropbox_token(access_token, refresh_token, expires_at)
                
                # Create Dropbox client
                self.client = dropbox.Dropbox(access_token)
                self.client.users_get_current_account()
                self.authenticated = True
                
                logger.info("Dropbox authentication successful via OAuth (offline token)")
                return True
                
            except Exception as e:
                logger.error(f"Failed to complete Dropbox OAuth flow: {e}")
                return False
            
        except ImportError:
            logger.error("Dropbox libraries not installed. Install: pip install dropbox")
            return False
        except Exception as e:
            logger.error(f"Dropbox authentication failed: {e}")
            return False
    
    def upload_file(self, file_path: Path, folder_path: str = "", subfolder: str = "") -> Optional[str]:
        """Upload file to Dropbox, organized into subfolders inside /FrogPaper/."""
        if not self.authenticated or not self.client:
            logger.error("Dropbox not authenticated")
            return None
        
        try:
            import dropbox
            logger.info(f"Starting Dropbox upload for: {file_path.name}")
            
            # Build target path: /FrogPaper/Subfolder/filename or /FrogPaper/filename
            effective_subfolder = subfolder or folder_path
            if effective_subfolder:
                target_path = f"/FrogPaper/{effective_subfolder}/{file_path.name}"
            else:
                target_path = f"/FrogPaper/{file_path.name}"
            logger.info(f"Target path: {target_path}")
            
            # Ensure base FrogPaper folder exists (skip if already verified this session)
            if not self._folder_exists_cache:
                try:
                    self.client.files_create_folder("/FrogPaper")
                    logger.info("FrogPaper folder created")
                except Exception as e:
                    error_str = str(e).lower()
                    if "already exists" in error_str or "path" in error_str:
                        logger.info("FrogPaper folder already exists")
                    else:
                        logger.warning(f"Folder creation note: {e}")
                self._folder_exists_cache = True
            
            # Ensure subfolder exists if needed
            if effective_subfolder:
                subfolder_path = f"/FrogPaper/{effective_subfolder}"
                try:
                    self.client.files_create_folder(subfolder_path)
                    logger.info(f"Subfolder {subfolder_path} created")
                except Exception as e:
                    error_str = str(e).lower()
                    if "already exists" in error_str or "path" in error_str:
                        pass  # already exists, fine
                    else:
                        logger.warning(f"Subfolder creation note: {e}")
            
            # Check if file already exists and is unchanged
            local_size = file_path.stat().st_size
            try:
                metadata = self.client.files_get_metadata(target_path)
                if metadata.size == local_size:
                    logger.info(f"Skipped {file_path.name} — unchanged ({local_size} bytes)")
                    return metadata.id
                logger.info(f"Found existing {file_path.name} on Dropbox, size changed {metadata.size} -> {local_size}, updating")
            except Exception:
                pass  # File doesn't exist yet, proceed with upload

            with open(file_path, 'rb') as f:
                file_data = f.read()
                
                result = self.client.files_upload(file_data, target_path, mode=dropbox.files.WriteMode.overwrite)
                logger.info(f"Upload successful! File ID: {result.id}")
                return result.id
            
        except Exception as e:
            logger.error(f"Failed to upload to Dropbox: {e}")
            import traceback
            logger.error(f"Upload error traceback: {traceback.format_exc()}")
            return None
    
    def list_files(self, folder_path: str = "") -> List[Dict]:
        """List files in Dropbox."""
        if not self.authenticated or not self.client:
            logger.error("Dropbox not authenticated")
            return []

        try:
            import dropbox
            result = self.client.files_list_folder(folder_path)
            files = []

            for entry in result.entries:
                if isinstance(entry, dropbox.files.FileMetadata):
                    files.append({
                        "id": entry.id,
                        "name": entry.name,
                        "size": entry.size,
                        "modified": entry.server_modified
                    })

            logger.info(f"Listed {len(files)} files from Dropbox")
            return files

        except Exception as e:
            logger.error(f"Failed to list Dropbox files: {e}")
            return []
    
    def download_file(self, file_id: str, dest_path: Path) -> bool:
        """Download file from Dropbox."""
        if not self.authenticated or not self.client:
            logger.error("Dropbox not authenticated")
            return False
        
        try:
            # Get file metadata to get path
            metadata = self.client.files_get_metadata(file_id)
            if hasattr(metadata, 'path_lower'):
                self.client.files_download_to_file(dest_path, metadata.path_lower)
                logger.info(f"Downloaded file {file_id} to {dest_path}")
                return True
            else:
                logger.error(f"Could not get path for file {file_id}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to download from Dropbox: {e}")
            return False


def get_provider(provider_name: str):
    """Get provider instance by name."""
    providers = {
        "google_drive": GoogleDriveProvider,
        "onedrive": OneDriveProvider,
        "dropbox": DropboxProvider
    }
    
    provider_class = providers.get(provider_name)
    if provider_class:
        return provider_class()
    else:
        logger.error(f"Unknown provider: {provider_name}")
        return None
