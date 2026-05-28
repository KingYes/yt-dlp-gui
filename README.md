# yt-dlp GUI

A cross-platform desktop GUI for [yt-dlp](https://github.com/yt-dlp/yt-dlp), built with Python and [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter).

Download videos, audio, and playlists from YouTube and [hundreds of other sites](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md) with a simple graphical interface. Available as a standalone executable for Windows, macOS, and Linux.

## Features

### Download

- Single URL or batch download (paste multiple URLs, one per line)
- Playlist and channel detection with smart prompting for ambiguous links
- Concurrent downloads (up to 5 simultaneous)
- Drag-and-drop URLs into the window
- Clipboard monitoring — automatically adds copied URLs
- Download queue with reordering, removal, and persistence across sessions
- Auto-retry on transient failures (up to 2 retries)

### Format & Quality

- Preset formats: Best (video+audio), 720p, 480p, Audio Only (MP3)
- Custom format picker — preview a video to select specific video and audio streams by resolution, codec, and bitrate
- Post-download conversion: MP4, MKV, WebM, MP3, AAC, FLAC, WAV, OGG

### Subtitles

- Download subtitles: embed in file, save as separate file, or burn into video
- Language picker with manual and auto-generated subtitle support
- Select All / individual language checkboxes
- Default subtitle language configurable in settings

### Chapters

- Split downloads by chapter
- Selective chapter picker — download only specific chapters

### Sections

- Download a specific time range of a video (start/end timestamps)
- Supports `MM:SS` and `HH:MM:SS` formats

### Preview

- Fetch video metadata (title, uploader, duration) before downloading
- Inspect available formats, subtitle languages, and chapters
- Playlist item count display

### Queue

- Add downloads while one is already running
- Reorder items (move up/down) or remove them
- Queue is persisted to disk and restored on restart
- Next queued item starts automatically when the current download finishes

### Progress

- Simple view: progress bar with percentage, speed, and ETA
- Detailed view: per-item progress bars with status icons
- Retry individual failed items from the detailed view
- Overall counter for batch downloads (e.g. "3 of 10")
- Indeterminate progress bar and status text for chapter-based downloads
- Post-processing status updates (e.g. merging, moving)

### Settings

- **Appearance**: theme (System / Dark / Light), UI scale (80%–150%), language selection (English, Hebrew — add more via JSON files)
- **Download defaults**: speed limit, simultaneous downloads (1–5), embed thumbnail, embed metadata, subtitle languages, clipboard monitoring
- **Network**: proxy support, browser cookies (Chrome, Firefox, Edge, Safari, Brave, Opera, Vivaldi), Netscape cookie file
- **Advanced**: portable mode (config stored next to executable)

### System Integration

- System tray icon — minimize to tray instead of closing; downloads continue in the background
- Tray notifications for download events
- OS-level notifications on download completion (macOS, Windows, Linux)
- Auto-update check against GitHub releases with in-app banner
- First-run setup wizard that downloads and installs FFmpeg automatically

### State Persistence

- Remembers last URLs, output folder, format selection, and window size
- Download history panel (last 100 downloads with status, date, size, URL)
- Lifetime statistics in the status bar: videos, audio, playlists, total bytes transferred

## Installation

### Download a Pre-built Release (Recommended)

1. Go to the [Releases page](https://github.com/KingYes/yt-dlp-gui/releases)
2. Download the binary for your platform:
   - **Windows**: `yt-dlp-gui-windows.exe`
   - **macOS**: `yt-dlp-gui-macos`
   - **Linux**: `yt-dlp-gui-linux`
3. Run the executable — no Python installation required
4. On first launch, the app will offer to download FFmpeg automatically if it is not already installed

### Build from Source

```bash
git clone https://github.com/KingYes/yt-dlp-gui.git
cd yt-dlp-gui

# Create a virtual environment
python -m venv venv
source venv/bin/activate   # macOS/Linux
venv\Scripts\activate      # Windows

# Install dependencies
pip install -r requirements.txt

# Run the app
python main.py
```

**Requirements**: Python 3.12+ and [FFmpeg](https://ffmpeg.org/) (for audio extraction, format merging, and subtitle burning).

### Building a Standalone Executable

```bash
pip install pyinstaller

pyinstaller --noconfirm --onefile --windowed \
  --name "yt-dlp-gui" \
  --hidden-import customtkinter \
  --collect-data customtkinter \
  main.py
```

The executable will be in the `dist/` directory.

## Running Tests

```bash
pip install pytest
pytest
```

## Project Structure

```
main.py               Entry point
app.py                Main application window and UI
download_manager.py   yt-dlp wrapper with progress hooks, retry, and concurrent downloads
i18n.py               Lightweight JSON-based internationalization module
state.py              Persistent JSON state (stats, history, queue, settings)
settings_window.py    Settings dialog UI
setup_wizard.py       First-run FFmpeg download wizard
tray.py               System tray icon (pystray)
updater.py            Auto-update checker against GitHub releases
utils.py              URL validation, format helpers, OS utilities
locales/              Translation JSON files (en.json, he.json, ...)
tests/                Unit tests (pytest)
pyproject.toml        Ruff, mypy, and pytest configuration
requirements.txt      Runtime dependencies
```

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
