# CatchSnap Browser Extension

A Chrome/Edge extension for downloading images from Snapchat Web.

## Features

- **Image Detection**: Automatically detects snap images on Snapchat Web
- **Manual Download**: Download button overlay on detected images - click to save
- **User Organization**: Downloads are organized into folders by username
- **Deduplication**: SHA256 hash-based duplicate detection prevents re-downloading the same image
- **Re-download Support**: Optional setting to allow re-downloading with incremental suffix

## Installation

### Chrome / Edge (Developer Mode)

1. Open Chrome/Edge and go to `chrome://extensions` (or `edge://extensions`)
2. Enable **Developer mode** (toggle in top right)
3. Click **Load unpacked**
4. Select this repository folder
5. The CatchSnap icon should appear in your toolbar

### First Time Setup

1. Navigate to [web.snapchat.com](https://web.snapchat.com)
2. Log in to your Snapchat account
3. Click the CatchSnap icon in the toolbar to view settings and stats

## Usage

Browse Snapchat Web normally. When a snap image is detected, a **Download** button appears in the top-right corner of the image. Click it to save the image.

- **Red button** = not yet downloaded
- **Green button** = already downloaded
- If "Allow Re-download" is enabled in settings, you can download the same image again (saved with a numeric suffix)

## Download Location

Media is saved to:
```
Downloads/
└── CatchSnap/
    └── {Username}/
        └── CatchSnap_{Username}_{hash}.jpg
```

The username is extracted from the snap viewer header, ensuring images are saved to the correct user's folder even when a different chat is open.

## Technical Details

### How It Works

1. **MutationObserver** detects new `<img>` elements (including blob URLs)
2. **Canvas API** captures fully rendered images
3. **SHA256 hashing** prevents duplicate downloads
4. **Chrome Downloads API** saves files with proper folder organization
5. **DOM-based username extraction** from snap viewer header for accurate attribution

### Permissions

- `downloads`: Save media to Downloads folder
- `storage`: Store settings and download history
- `activeTab`: Access current tab content
- `host_permissions`: Access web.snapchat.com

### Files

```
├── manifest.json           # Extension manifest (V3)
├── background.js           # Service worker for downloads
├── content/
│   ├── content.js          # Main entry point
│   ├── media-detector.js   # MutationObserver-based image detection
│   ├── image-capture.js    # Canvas-based image capture
│   └── user-parser.js      # Username/UUID extraction from DOM
├── popup/
│   ├── popup.html          # Settings & stats UI
│   ├── popup.js            # Popup logic
│   └── popup.css           # Styles
├── utils/
│   ├── hash.js             # SHA256 hashing
│   └── storage.js          # Chrome storage wrapper
└── icons/
    └── icon{16,48,128}.png # Extension icons
```

## Troubleshooting

### Extension not detecting images
- Make sure you're on `web.snapchat.com`
- Check that the extension is enabled in the popup
- Try refreshing the page

### Downloads not starting
- Check Chrome's download settings
- Ensure the Downloads folder is writable
- Check browser console for errors (filter by `[CatchSnap]`)

### Wrong user folder
- The extension extracts the username from the snap viewer header above the image
- If extraction fails, images are saved under `unknown` or `user_{UUID}`

## Development

To modify the extension:

1. Make changes to the source files
2. Go to `chrome://extensions`
3. Click the refresh icon on CatchSnap
4. Reload Snapchat Web to test changes

Console logs are prefixed with `[CatchSnap]` for easy filtering.

## License

MIT License - See repository root for details.
