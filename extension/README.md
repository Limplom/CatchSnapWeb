# CatchSnap Browser Extension

A Chrome/Edge extension for downloading media from Snapchat Web.

## Features

- **Automatic Media Detection**: Detects images and videos on Snapchat Web
- **Complete Downloads**: Uses Canvas API for images and Blob fetch for videos - no truncation
- **User Organization**: Downloads are organized by username and UUID
- **Deduplication**: SHA256 hash-based duplicate detection
- **Three Download Modes**:
  - **Auto**: Automatically downloads all detected media
  - **Manual**: Shows download overlay buttons on media
  - **Hybrid**: Customize auto/manual per media type

## Installation

### Chrome / Edge (Developer Mode)

1. Open Chrome/Edge and go to `chrome://extensions` (or `edge://extensions`)
2. Enable **Developer mode** (toggle in top right)
3. Click **Load unpacked**
4. Select the `extension` folder from this repository
5. The CatchSnap icon should appear in your toolbar

### First Time Setup

1. Navigate to [web.snapchat.com](https://web.snapchat.com)
2. Log in to your Snapchat account
3. Click the CatchSnap icon in the toolbar
4. Configure your preferred download mode

## Usage

### Auto Mode (Default)
Simply browse Snapchat Web - all images and videos you view will be automatically downloaded to your Downloads folder under `CatchSnap/{Username}/`.

### Manual Mode
Hover over any image or video to see a download button. Click to download.

### Hybrid Mode
Choose which media types to auto-download and which require manual action.

## Download Location

Media is saved to:
```
Downloads/
└── CatchSnap/
    └── {Username}_{UUID}/
        ├── {hash}.jpg
        ├── {hash}.mp4
        └── ...
```

## Technical Details

### How It Works

1. **MutationObserver** detects new `<img>` and `<video>` elements with blob URLs
2. **Canvas API** captures fully rendered images (solves progressive JPEG issues)
3. **Blob Fetch** downloads complete video files
4. **SHA256 hashing** prevents duplicate downloads
5. **Chrome Downloads API** saves files with proper organization

### Permissions

- `downloads`: Save media to Downloads folder
- `storage`: Store settings and download history
- `activeTab`: Access current tab content
- `host_permissions`: Access web.snapchat.com

### Files

```
extension/
├── manifest.json           # Extension manifest (V3)
├── background.js           # Service worker for downloads
├── content/
│   ├── content.js          # Main entry point
│   ├── media-detector.js   # MutationObserver logic
│   ├── image-capture.js    # Canvas-based image capture
│   ├── video-capture.js    # Video blob extraction
│   └── user-parser.js      # Username/UUID extraction
├── popup/
│   ├── popup.html          # UI
│   ├── popup.js            # UI logic
│   └── popup.css           # Styles
├── utils/
│   ├── hash.js             # SHA256 hashing
│   └── storage.js          # Chrome storage wrapper
└── icons/
    └── icon{16,48,128}.png # Extension icons
```

## Troubleshooting

### Extension not detecting media
- Make sure you're on `web.snapchat.com` (not `snapchat.com`)
- Check that the extension is enabled (green status dot)
- Try refreshing the page

### Downloads not starting
- Check Chrome's download settings
- Ensure the Downloads folder is writable
- Check browser console for errors

### Duplicate downloads
- The extension uses hash-based deduplication
- Clear history in popup to reset deduplication

## Development

To modify the extension:

1. Make changes to the source files
2. Go to `chrome://extensions`
3. Click the refresh icon on CatchSnap
4. Reload Snapchat Web to test changes

Console logs are prefixed with `[CatchSnap]` for easy filtering.

## License

MIT License - See repository root for details.
