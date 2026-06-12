"""
Object Storage Interface
Provides a unified interface for Local Mock Storage and Google Drive Integration.
"""
import os
import shutil
import io
from pathlib import Path
from loguru import logger

from app.core.config import settings

class LocalObjectStore:
    """Mock interface for Object Storage. Writes to local disk."""
    
    def __init__(self):
        self.bucket_path = settings.DATA_DIR / "object_store"
        self.bucket_path.mkdir(parents=True, exist_ok=True)
        
    def upload_file(self, source_path: Path, destination_key: str):
        dest_path = self.bucket_path / destination_key
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, dest_path)
        logger.info(f"[LocalStore] Uploaded {source_path} to {destination_key}")
        return str(dest_path)

    def upload_content(self, content: bytes, destination_key: str):
        dest_path = self.bucket_path / destination_key
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        with open(dest_path, "wb") as f:
            f.write(content)
        logger.info(f"[LocalStore] Uploaded content to {destination_key}")
        return str(dest_path)
        
    def download_file(self, object_key: str, destination_path: Path):
        source_path = self.bucket_path / object_key
        if not source_path.exists():
            raise FileNotFoundError(f"Object {object_key} not found in store.")
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, destination_path)
        logger.info(f"[LocalStore] Downloaded {object_key} to {destination_path}")
        return str(destination_path)
        
    def get_presigned_url(self, object_key: str, expiration=3600):
        source_path = self.bucket_path / object_key
        if not source_path.exists():
            return None
        return f"file://{source_path.absolute()}"


class GoogleDriveStore:
    """Google Drive integration using Service Account."""
    
    def __init__(self, credentials_path: str, folder_id: str):
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
        
        self.folder_id = folder_id
        self.scopes = ['https://www.googleapis.com/auth/drive.file']
        
        creds = service_account.Credentials.from_service_account_file(
            credentials_path, scopes=self.scopes
        )
        self.service = build('drive', 'v3', credentials=creds)
        logger.info("[DriveStore] Authenticated with Google Drive.")
        
    def upload_file(self, source_path: Path, destination_key: str):
        from googleapiclient.http import MediaFileUpload
        
        file_metadata = {
            'name': destination_key.split('/')[-1],
            'parents': [self.folder_id]
        }
        media = MediaFileUpload(str(source_path), resumable=True)
        file = self.service.files().create(
            body=file_metadata, media_body=media, fields='id'
        ).execute()
        
        logger.info(f"[DriveStore] Uploaded {source_path} as Drive ID: {file.get('id')}")
        return file.get('id')

    def upload_content(self, content: bytes, destination_key: str):
        from googleapiclient.http import MediaIoBaseUpload
        
        file_metadata = {
            'name': destination_key.split('/')[-1],
            'parents': [self.folder_id]
        }
        media = MediaIoBaseUpload(io.BytesIO(content), mimetype='application/octet-stream', resumable=True)
        file = self.service.files().create(
            body=file_metadata, media_body=media, fields='id'
        ).execute()
        
        logger.info(f"[DriveStore] Uploaded content as Drive ID: {file.get('id')}")
        return file.get('id')
        
    def download_file(self, object_key: str, destination_path: Path):
        # In Google Drive, object_key usually needs to be the File ID
        # Since our previous system uses paths (e.g. "uploads/filename"), 
        # a robust system would search for the file ID by name.
        # For simplicity, we assume object_key passed here is the File ID returned by upload.
        from googleapiclient.http import MediaIoBaseDownload
        
        request = self.service.files().get_media(fileId=object_key)
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        
        with io.FileIO(str(destination_path), 'wb') as fh:
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while done is False:
                status, done = downloader.next_chunk()
        
        logger.info(f"[DriveStore] Downloaded file ID {object_key} to {destination_path}")
        return str(destination_path)
        
    def get_presigned_url(self, object_key: str, expiration=3600):
        # We can return the webViewLink or use Google Drive API to generate a link.
        try:
            file = self.service.files().get(fileId=object_key, fields='webViewLink').execute()
            return file.get('webViewLink')
        except Exception as e:
            logger.error(f"[DriveStore] Failed to get link: {e}")
            return None


# ──────────────────── Instantiate Store ────────────────────

creds_path = settings.BASE_DIR / "credentials.json"

if creds_path.exists() and settings.GOOGLE_DRIVE_FOLDER_ID:
    logger.info("Initializing Google Drive Object Store.")
    object_store = GoogleDriveStore(str(creds_path), settings.GOOGLE_DRIVE_FOLDER_ID)
else:
    logger.info("Credentials not found or GOOGLE_DRIVE_FOLDER_ID not set. Falling back to Local Mock Store.")
    object_store = LocalObjectStore()
