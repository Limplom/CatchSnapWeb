# CatchSnap Android App

Android app for capturing Snapchat Web traffic and downloading blobs (images/videos).

## Features

- Opens Snapchat Web in a WebView
- Intercepts all HTTP traffic (requests/responses)
- Automatically downloads blob URLs (images, videos)
- Validates downloaded files
- Saves everything to local storage

## Requirements

- Android Studio Hedgehog (2023.1.1) or newer
- Android SDK 34 (Android 14)
- Minimum Android version: 7.0 (API 24)

## Setup

1. Open Android Studio
2. Select "Open an Existing Project"
3. Navigate to `android-app/` directory
4. Wait for Gradle sync to complete

## Icon Resources

**IMPORTANT**: You need to add app icons before building!

The project references icons in `AndroidManifest.xml`:
- `@mipmap/ic_launcher`
- `@mipmap/ic_launcher_round`

### Option 1: Use Android Studio Image Asset Tool
1. Right-click on `app` module
2. Select `New > Image Asset`
3. Configure launcher icon
4. Generate icons for all densities

### Option 2: Manual Icon Placement
Create these directories and add PNG files:
```
app/src/main/res/
├── mipmap-mdpi/
│   ├── ic_launcher.png (48x48)
│   └── ic_launcher_round.png (48x48)
├── mipmap-hdpi/
│   ├── ic_launcher.png (72x72)
│   └── ic_launcher_round.png (72x72)
├── mipmap-xhdpi/
│   ├── ic_launcher.png (96x96)
│   └── ic_launcher_round.png (96x96)
├── mipmap-xxhdpi/
│   ├── ic_launcher.png (144x144)
│   └── ic_launcher_round.png (144x144)
└── mipmap-xxxhdpi/
    ├── ic_launcher.png (192x192)
    └── ic_launcher_round.png (192x192)
```

## Build

### Debug Build
```bash
./gradlew assembleDebug
```
APK location: `app/build/outputs/apk/debug/app-debug.apk`

### Release Build (Unsigned)
```bash
./gradlew assembleRelease
```

## Installation

### Via ADB
```bash
adb install app/build/outputs/apk/debug/app-debug.apk
```

### Manual Installation
1. Transfer APK to device
2. Enable "Install from Unknown Sources"
3. Open APK file on device

## Usage

1. Launch the app
2. Wait for Snapchat Web to load
3. Log in to your Snapchat account
4. Browse Snaps - all media will be captured automatically
5. Press Back/Home to save logs

## Output Location

All captured data is saved to:
```
/Android/data/com.catchsnap/files/traffic_logs/android_{timestamp}/
├── requests_{timestamp}.json
├── responses_{timestamp}.json
├── downloaded_blobs_{timestamp}.json
├── summary_{timestamp}.json
└── blobs/
    ├── {hash}.jpg
    ├── {hash}.mp4
    └── ...
```

## Accessing Files

### Via Android Studio Device File Explorer
1. View > Tool Windows > Device File Explorer
2. Navigate to `/data/data/com.catchsnap/files/traffic_logs/`

### Via ADB
```bash
adb shell "run-as com.catchsnap ls -la /data/data/com.catchsnap/files/traffic_logs/"
adb pull /sdcard/Android/data/com.catchsnap/files/traffic_logs/
```

### Via USB File Transfer
1. Connect device via USB
2. Navigate to: `Internal Storage/Android/data/com.catchsnap/files/traffic_logs/`

## Troubleshooting

### Snapchat shows "Browser not supported"
- The app uses a Chrome Mobile user agent to bypass detection
- If still blocked, try updating the user agent in `MainActivity.kt`

### Blobs not downloading
- Check Logcat for "[BLOB]" messages
- Ensure JavaScript is enabled
- Verify JavaScript Bridge is working: look for "[BlobCapture]" logs

### App crashes on startup
- Check Logcat for error messages
- Verify all permissions are granted
- Ensure Android version >= 7.0

## Development

### Enable Debug Logging
Set in `MainActivity.kt`:
```kotlin
WebView.setWebContentsDebuggingEnabled(true)
```

Then use Chrome DevTools:
1. Open `chrome://inspect` in Chrome on PC
2. Connect Android device via USB
3. Click "inspect" on WebView

### View Logcat
```bash
adb logcat -s CatchSnap:* BlobDownloader:* TrafficLogger:* StorageManager:*
```

## Architecture

- **MainActivity**: WebView host + lifecycle management
- **SnapWebViewClient**: Traffic interception
- **BlobDownloader**: JavaScript Bridge for blob capture
- **TrafficLogger**: Request/Response logging
- **StorageManager**: File I/O operations
- **BlobValidator**: File integrity validation
- **blob_capture.js**: JavaScript injection for blob detection

## License

Same as parent project.
