# Drive Uploader

A macOS app for uploading any file or folder to Google Drive with a true resumable upload engine — built for large video files that need to survive network interruptions.

---

## What it does

- **Upload any file or folder** from anywhere on your Mac (external drives, NAS, local storage)
- **Resumable uploads** — if your network drops mid-upload, it picks up exactly where it left off (session URI saved after every chunk)
- **Up to 3 concurrent uploads** for fast folder delivery
- **Real-time progress** with data rate and ETA
- **ZIP or Keep Structure** mode for folder uploads
- **Hierarchical Drive folder picker** — browse your real Google Drive folder tree

---

## Features

- 🎨 Dark macOS-style UI (CustomTkinter)
- 📂 Hierarchical Google Drive folder picker — browse Shared Drives and My Drive as collapsible trees
- ⚡ 25 MB chunks with sub-chunk progress for smooth UI updates
- 🔁 Exponential backoff retry on transient network errors
- 💾 Upload state persisted to disk — survives crashes and app restarts
- 🔒 Google Drive OAuth (one-time browser login, token saved locally)

---

## Requirements

- macOS 12+
- Python 3.14 ([python.org](https://www.python.org/downloads/))
- A Google Cloud project with the Drive API enabled ([setup guide below](#google-drive-setup))

---

## Installation

### 1. Clone the repo
```bash
git clone https://github.com/CanadianWiteout/drive-uploader.git
cd drive-uploader
```

### 2. Install dependencies
```bash
/Library/Frameworks/Python.framework/Versions/3.14/bin/pip3 install -r requirements.txt
```

### 3. Add your Google credentials
Download `credentials.json` from Google Cloud Console (see [setup below](#google-drive-setup)) and place it in the project folder.

### 4. Run
```bash
/Library/Frameworks/Python.framework/Versions/3.14/bin/python3 main.py
```

On first launch, a browser window opens for Google OAuth — sign in and approve. A `token.json` is saved and you won't be asked again.

---

## Building a standalone .app

To create a self-contained macOS app (no Python required to run):

```bash
bash build.sh
cp -r "dist/Drive Uploader.app" /Applications/
```

The first build takes ~2 minutes. Re-run `build.sh` any time you update the source.

---

## Google Drive Setup

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Create a new project (or use an existing one)
3. Enable the **Google Drive API** — search for it in the API Library
4. Go to **APIs & Services → Credentials → Create Credentials → OAuth 2.0 Client ID**
5. Choose **Desktop app**, give it a name, click Create
6. Download the JSON file and rename it `credentials.json`
7. Place it in the `drive-uploader` folder

> **Cost:** The Drive API is completely free for personal use. No billing setup required.

---

## Usage

1. Open the app
2. Click **+ Add Files** or **+ Add Folder** to queue uploads
3. Click **Pick Drive Folder** to choose your upload destination
4. Click **Upload All** — progress bars show per-file status with rate and ETA
5. If a upload is interrupted, reopen the app and click **Resume** — it continues from where it left off

---

## Upload Modes

| Mode | What it does |
|---|---|
| **Keep Structure** | Recreates the folder tree inside Drive |
| **ZIP** | Compresses the folder to a single `.zip` before uploading |

---

## File Structure

```
drive-uploader/
├── main.py          # GUI app
├── drive.py         # Google Drive API + resumable upload engine
├── state.py         # Upload session persistence
├── config.py        # Persistent settings (~/.drive-uploader-config.json)
├── requirements.txt
├── build.sh         # PyInstaller standalone build script
├── credentials.json # (you add this — not committed)
└── token.json       # (auto-created on first login — not committed)
```

---

## Updating the app

Edit source files freely, then:
```bash
# Quick test during development
/Library/Frameworks/Python.framework/Versions/3.14/bin/python3 main.py

# Rebuild the .app when ready
bash build.sh && cp -r "dist/Drive Uploader.app" /Applications/
```

---

## Part of the Kootenay Color Toolset

- [kc-project-creator](https://github.com/CanadianWiteout/kc-project-creator) — Project folder structure creator
- [resolve-uploader](https://github.com/CanadianWiteout/resolve-uploader) — Auto-upload Resolve exports + email client
