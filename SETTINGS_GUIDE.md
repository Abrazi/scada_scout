# SCADA Scout Settings Guide

## Overview
SCADA Scout now includes a comprehensive **Settings Dialog** that allows you to fully customize the appearance of the application to match your preferences. Access it via **View → Settings** or press **Ctrl+,**.

## Features

### 1. Appearance Tab
Customize the overall theme and visual style:
- **Theme Selection**: Choose between Professional (light) and Dark themes
- **Custom Colors Toggle**: Enable to use your own color scheme
- **Component Size**: Adjust button and widget sizes (Small/Medium/Large)
- **Border Radius**: Control corner roundness (0-10px)

### 2. Typography Tab
Fine-tune text appearance:
- **UI Font Family**: Select the main application font (default: Segoe UI)
- **UI Font Size**: Adjust text size for dialogs and widgets (8-16pt)
- **Console Font Family**: Choose monospace font for event log (default: Consolas)
- **Console Font Size**: Set console text size (7-14pt)

### 3. Colors Tab
Full control over the application's color palette:
- **Primary Color**: Main brand color (buttons, highlights)
- **Accent Color**: Darker shade for hover effects
- **Success Color**: Positive status indicators
- **Warning Color**: Caution states
- **Error Color**: Error messages and alerts
- **Background Color**: Main window background
- **Text Color**: Primary text throughout the app

Each color can be selected using an intuitive color picker dialog.

### 4. Layout Tab
Adjust spacing and padding:
- **Widget Spacing**: Gap between UI elements (2-20px)
- **Widget Padding**: Internal padding for buttons/inputs (4-16px)
- **Dock Title Height**: Height of panel title bars (24-48px)
- **Toolbar Icon Size**: Size of toolbar icons (16-48px)

## Using the Settings

### Changing Colors
1. Open **View → Settings** (or press **Ctrl+,**)
2. Go to the **Colors** tab
3. Enable **Use Custom Colors** checkbox
4. Click any color button (e.g., "Primary Color")
5. Select your desired color in the picker
6. Click **Save** to apply changes

### Switching Themes
1. Open Settings dialog
2. In **Appearance** tab, select theme from dropdown
3. Disable "Use Custom Colors" to use the predefined theme
4. Click **Save**

### Adjusting Typography
1. Open Settings → **Typography** tab
2. Select font family from the dropdown
3. Adjust size using the spin box
4. Click **Save**
5. Changes apply immediately to the entire interface

### Restoring Defaults
- Click **Restore Defaults** button in any tab
- This resets ALL settings to factory values
- Changes take effect after clicking **Save**

## Persistence
All settings are automatically saved using Qt's QSettings system:
- **Organization**: ScadaScout
- **Application**: UI
- Settings persist across application restarts
- Configuration stored in platform-specific location:
  - **Linux**: `~/.config/ScadaScout/UI.conf`
  - **Windows**: Registry under `HKEY_CURRENT_USER\Software\ScadaScout\UI`
  - **macOS**: `~/Library/Preferences/com.ScadaScout.UI.plist`

## Tips
- **Dark Theme** is ideal for low-light environments
- **Professional Theme** provides a clean, corporate look
- Custom colors allow perfect brand alignment
- Larger fonts improve readability on high-DPI displays
- Console font should always be monospace for proper alignment

## Keyboard Shortcut
- **Ctrl+,** (Control + Comma): Quick access to Settings dialog

## Technical Details
- Dynamic stylesheet regeneration on settings change
- Uses `QColorDialog` for color selection
- `QFontComboBox` for font selection with live preview
- All changes applied without restart
- Thread-safe settings access via `QSettings`

## Example Use Cases

### Corporate Branding
1. Set Primary Color to company blue (#0066CC)
2. Set Accent Color to darker blue (#004C99)
3. Adjust Background to light gray (#F0F0F0)
4. Use company's standard font (Arial, Helvetica, etc.)

### High Contrast Mode
1. Use Dark theme
2. Increase font sizes (UI: 12pt, Console: 11pt)
3. Bright colors for status (Green: #00FF00, Red: #FF0000)

### Minimalist Style
1. Professional theme
2. Small component sizes
3. Minimal border radius (2px)
4. Reduced padding (4px)
5. Neutral colors (grays and blues)

## Troubleshooting

### Colors Not Applying
- Ensure "Use Custom Colors" is **checked** in Colors tab
- Click **Save** button after making changes
- Check that stylesheet regeneration completed without errors

### Font Not Changing
- Verify font is installed on your system
- Some fonts may not support all characters
- Console fonts should be monospace

### Settings Not Persisting
- Check file permissions on config directory
- Ensure QSettings has write access
- Verify application name matches in code

## Future Enhancements
Planned features for future releases:
- Export/Import settings profiles
- Per-device color coding
- Custom icon themes
- Layout presets (Compact, Standard, Spacious)
- High-DPI scaling options
- Accessibility modes (increased contrast, larger text)

---

**Version**: 1.0  
**Last Updated**: 2024  
**Author**: SCADA Scout Development Team
