"""Google Drive API helpers for drive-uploader.

Handles OAuth, folder listing, and the resumable upload engine with:
  - 25 MB chunks (Frame.io-inspired sizing for fewer round-trips)
  - ProgressFileWrapper for sub-chunk progress updates
  - Session restore via resumable_uri (survives process restarts)
  - Server-side progress query to handle mid-chunk crashes correctly
"""

import io
import mimetypes
import os
import socket
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

SCOPES = ["https://www.googleapis.com/auth/drive"]
CHUNK_SIZE = 25 * 1024 * 1024  # 25 MB — must be a multiple of 256 KB

_HERE = Path(__file__).parent
CREDENTIALS_PATH = _HERE / "credentials.json"
TOKEN_PATH = _HERE / "token.json"


# ── Auth ──────────────────────────────────────────────────────────────────────

def get_service():
    """Return an authenticated Drive service. Runs OAuth flow on first use."""
    creds = None

    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CREDENTIALS_PATH.exists():
                raise FileNotFoundError(
                    f"credentials.json not found at {CREDENTIALS_PATH}.\n"
                    "Download it from Google Cloud Console → APIs & Services → Credentials."
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CREDENTIALS_PATH), SCOPES
            )
            creds = flow.run_local_server(port=0)

        TOKEN_PATH.write_text(creds.to_json())

    return build("drive", "v3", credentials=creds)


# ── Folder listing ────────────────────────────────────────────────────────────

def list_folders(service):
    """
    Return [{id, name, path, drive_name, drive_id, parent_id}] for My Drive
    and all Shared Drives the user has access to.

    drive_id:  "my_drive" for My Drive folders, or the Shared Drive's GUID.
    parent_id: the folder's immediate parent ID, normalized so that root-level
               folders (whose parent is not another folder in the list) get
               parent_id == drive_id (the sentinel).
    """
    folders = []

    # ── My Drive folders ──────────────────────────────────────────────────────
    my_drive_raw = []
    page_token = None
    while True:
        resp = service.files().list(
            q="mimeType='application/vnd.google-apps.folder' and trashed=false",
            spaces="drive",
            fields="nextPageToken, files(id, name, parents)",
            pageToken=page_token,
            pageSize=1000,
        ).execute()
        my_drive_raw.extend(resp.get("files", []))
        page_token = resp.get("nextPageToken")
        if not page_token:
            break

    # Normalize parent_id: if parent is not another My Drive folder → it's root
    my_drive_ids = {f["id"] for f in my_drive_raw}
    for f in my_drive_raw:
        raw_parent = (f.get("parents") or [None])[0]
        parent_id = raw_parent if raw_parent in my_drive_ids else "my_drive"
        folders.append({
            "id": f["id"],
            "name": f["name"],
            "path": f["name"],
            "drive_name": "My Drive",
            "drive_id": "my_drive",
            "parent_id": parent_id,
        })

    # ── Shared Drives ─────────────────────────────────────────────────────────
    try:
        sd_resp = service.drives().list(pageSize=50).execute()
        for drive in sd_resp.get("drives", []):
            drive_id = drive["id"]
            drive_name = drive["name"]
            drive_raw = []
            page_token = None
            while True:
                resp = service.files().list(
                    q="mimeType='application/vnd.google-apps.folder' and trashed=false",
                    spaces="drive",
                    corpora="drive",
                    driveId=drive_id,
                    includeItemsFromAllDrives=True,
                    supportsAllDrives=True,
                    fields="nextPageToken, files(id, name, parents)",
                    pageToken=page_token,
                    pageSize=1000,
                ).execute()
                drive_raw.extend(resp.get("files", []))
                page_token = resp.get("nextPageToken")
                if not page_token:
                    break

            # Normalize parent_id for this shared drive
            drive_folder_ids = {f["id"] for f in drive_raw}
            for f in drive_raw:
                raw_parent = (f.get("parents") or [None])[0]
                parent_id = raw_parent if raw_parent in drive_folder_ids else drive_id
                folders.append({
                    "id": f["id"],
                    "name": f["name"],
                    "path": f["name"],
                    "drive_name": drive_name,
                    "drive_id": drive_id,
                    "parent_id": parent_id,
                })
    except Exception:
        pass  # No Shared Drive access — fine

    folders.sort(key=lambda x: (x["drive_name"] == "My Drive", x["drive_name"], x["name"].lower()))
    return folders


# ── Progress-tracking file wrapper ────────────────────────────────────────────

class ProgressFileWrapper(io.RawIOBase):
    """Wraps a file, intercepting read() calls to report sub-chunk progress.

    This decouples UI update frequency from chunk size: even with 25 MB chunks,
    the progress bar moves as bytes are read from disk (which closely tracks
    bytes sent over the network).
    """

    def __init__(self, file_path: str, progress_callback):
        super().__init__()
        self._file = open(file_path, "rb")
        self._bytes_read = 0
        self._callback = progress_callback

    def read(self, n=-1):
        data = self._file.read(n)
        if data:
            self._bytes_read += len(data)
            self._callback(self._bytes_read)
        return data

    def readinto(self, b):
        n = self._file.readinto(b)
        if n:
            self._bytes_read += n
            self._callback(self._bytes_read)
        return n

    def seek(self, pos, whence=0):
        result = self._file.seek(pos, whence)
        self._bytes_read = self._file.tell()
        return result

    def tell(self):
        return self._file.tell()

    def readable(self):
        return True

    def seekable(self):
        return True

    def close(self):
        try:
            self._file.close()
        except Exception:
            pass
        super().close()


# ── Upload session management ─────────────────────────────────────────────────

def create_upload_request(service, file_path: str, folder_id: str, progress_callback):
    """Create a new resumable upload session. Does not start uploading.

    Returns (request, wrapper). Caller drives the upload by calling
    request.next_chunk() in a loop.
    """
    file_name = Path(file_path).name
    mime, _ = mimetypes.guess_type(file_path)
    mime = mime or "application/octet-stream"

    wrapper = ProgressFileWrapper(file_path, progress_callback)
    media = MediaIoBaseUpload(wrapper, mimetype=mime, chunksize=CHUNK_SIZE, resumable=True)

    request = service.files().create(
        body={"name": file_name, "parents": [folder_id]},
        media_body=media,
        supportsAllDrives=True,
        fields="id",
    )
    return request, wrapper


def restore_upload_request(service, file_path: str, folder_id: str,
                           resumable_uri: str, saved_progress: int, progress_callback):
    """Restore a previously interrupted resumable upload session.

    Queries the Drive server for the actual confirmed byte count (handles
    mid-chunk crashes where saved_progress may be ahead of what Drive received).

    Returns (request, wrapper, confirmed_bytes).
    """
    mime, _ = mimetypes.guess_type(file_path)
    mime = mime or "application/octet-stream"
    file_size = os.path.getsize(file_path)

    wrapper = ProgressFileWrapper(file_path, progress_callback)
    media = MediaIoBaseUpload(wrapper, mimetype=mime, chunksize=CHUNK_SIZE, resumable=True)

    # Build a new request object with the same parameters
    request = service.files().create(
        body={"name": Path(file_path).name, "parents": [folder_id]},
        media_body=media,
        supportsAllDrives=True,
        fields="id",
    )

    # Restore the session URI — next_chunk() skips initiation when this is set
    request.resumable_uri = resumable_uri

    # Ask Drive how many bytes it actually has (server is authoritative)
    confirmed = _query_server_progress(resumable_uri, service._http, file_size)
    if confirmed == 0 and saved_progress > 0:
        # Server returned nothing (possibly a 308 with no Range header meaning 0 bytes)
        # Fall back to saved_progress as a conservative estimate
        confirmed = 0  # safer to restart from 0 than to corrupt

    request.resumable_progress = confirmed

    # Seek the file wrapper to the confirmed position so the next read starts there
    wrapper.seek(confirmed)

    return request, wrapper, confirmed


def _query_server_progress(resumable_uri: str, http, file_size: int) -> int:
    """Ask Drive how many bytes it has confirmed for a resumable session.

    Uses the standard resumable upload protocol: PUT with Content-Range: bytes */N.
    Returns the confirmed byte count, or 0 if the session has expired/errored.
    """
    try:
        headers = {
            "Content-Range": f"bytes */{file_size}",
            "Content-Length": "0",
        }
        resp, _ = http.request(resumable_uri, "PUT", headers=headers)
        status = int(resp.status)
        if status == 308:  # Resume Incomplete
            range_header = resp.get("range", "")
            if range_header and "-" in range_header:
                return int(range_header.split("-")[1]) + 1
            return 0
        elif status in (200, 201):  # Already complete
            return file_size
    except (socket.error, OSError, Exception):
        pass
    return 0


# ── Drive folder creation ─────────────────────────────────────────────────────

def create_drive_folder(service, name: str, parent_id: str) -> str:
    """Create a folder in Drive under parent_id. Returns the new folder's ID."""
    result = service.files().create(
        body={
            "name": name,
            "mimeType": "application/vnd.google-apps.folder",
            "parents": [parent_id],
        },
        supportsAllDrives=True,
        fields="id",
    ).execute()
    return result["id"]
