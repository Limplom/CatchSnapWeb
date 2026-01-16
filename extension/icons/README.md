# CatchSnap Icons

## Required Icons

The extension requires the following icon sizes:
- `icon16.png` - 16x16 pixels (toolbar)
- `icon48.png` - 48x48 pixels (extension management)
- `icon128.png` - 128x128 pixels (Chrome Web Store)

## Creating Icons

### Option 1: Use the included placeholder icons
The extension includes placeholder SVG-based icons that will work for development.

### Option 2: Create custom icons
Design icons using these specifications:
- **Format**: PNG with transparency
- **Colors**: Snapchat yellow (#FFFC00) on transparent background
- **Design**: Camera or snap-related icon

### Recommended Tools
- Figma (free)
- Adobe Illustrator
- Inkscape (free)

### Icon Design Guidelines
1. Keep it simple - icons need to be recognizable at 16px
2. Use the Snapchat yellow (#FFFC00) as primary color
3. Ensure good contrast on both light and dark browser themes
4. Test visibility in Chrome's toolbar (both light and dark mode)

## Current Placeholder Icons

The extension uses emoji-based placeholders in the popup. For production:
1. Replace icon16.png, icon48.png, icon128.png with proper PNG files
2. Update manifest.json if needed
