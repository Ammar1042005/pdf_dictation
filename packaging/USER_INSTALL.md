# PDF Dictation - Installation Guide for Windows

## System Requirements

- **Operating System**: Windows 10 or later (64-bit)
- **Disk Space**: ~100 MB for installation
- **Memory**: 4 GB RAM recommended
- **No additional dependencies required** - everything is bundled!

## Installation

### Option 1: Using the Installer (Recommended)

1. Download `PDFDictation-Setup-X.Y.Z.exe` from the [GitHub Releases](https://github.com/Ammar1042005/pdf_dictation/releases) page
2. Double-click the installer to run it
3. Follow the installation wizard:
   - Choose installation location (default: `C:\Program Files\PDF Dictation`)
   - Select whether to create a desktop icon
   - Click "Install"
4. Wait for installation to complete
5. Click "Finish" to launch PDF Dictation

### Option 2: Using the Standalone Executable

1. Download `PDFDictation.exe` from the [GitHub Releases](https://github.com/Ammar1042005/pdf_dictation/releases) page
2. Place the file in any folder on your computer
3. Double-click `PDFDictation.exe` to run it

**Note**: The standalone exe is self-contained and doesn't require installation. You can move it anywhere or place it on a USB drive.

## First Launch

When you first run PDF Dictation:

1. The application window will open
2. Click "Open PDF…" to select a PDF file
3. Configure settings (speech rate, voice, etc.) by clicking "Settings…"
4. Click "Start" to begin dictation

## Uninstallation

### If Installed via Installer

1. Open Windows Settings → Apps → Installed Apps
2. Find "PDF Dictation" in the list
3. Click "Uninstall" and follow the prompts

### If Using Standalone Exe

Simply delete the `PDFDictation.exe` file and any settings files in:
- `%APPDATA%\pdf_dictation\` (application settings)
- `%LOCALAPPDATA%\pdf_dictation\` (cache and temporary files)

## Troubleshooting

### Antivirus Warning

Some antivirus software may flag the executable as a false positive. This is common for applications packaged with PyInstaller. If you see a warning:

1. Allow the file in your antivirus settings
2. Or download from the official GitHub repository only

### Application Won't Start

1. Make sure you're using Windows 10 or later (64-bit)
2. Right-click `PDFDictation.exe` → Properties → check "Unblock" if present
3. Run as Administrator if you encounter permission issues

### Missing Features

The standalone exe includes all required features:
- PDF viewing and navigation
- Text-to-speech with adjustable rate
- OCR for scanned PDFs
- Bookmarks and search
- Session saving

No additional downloads or installations are needed!

## Updates

To update PDF Dictation:

1. Download the latest version from [GitHub Releases](https://github.com/Ammar1042005/pdf_dictation/releases)
2. If using the installer, run the new installer (it will update automatically)
3. If using the standalone exe, replace the old exe with the new one

Your settings and sessions will be preserved automatically.

## Source Code

PDF Dictation is open source! If you want to view the source code, report issues, or contribute:

- **GitHub Repository**: https://github.com/Ammar1042005/pdf_dictation
- **License**: See the LICENSE file in the repository

The distributed executable is protected to prevent unauthorized modification, but the full source code is available on GitHub for transparency and community contributions.

## Support

If you encounter issues:

1. Check the [GitHub Issues](https://github.com/Ammar1042005/pdf_dictation/issues) page for known problems
2. Search existing discussions before creating a new issue
3. When reporting an issue, include:
   - Windows version
   - PDF Dictation version
   - Steps to reproduce the problem
   - Any error messages

## Privacy

PDF Dictation:
- Does not collect or transmit any data
- Does not require internet connection (except for update checking, which can be disabled)
- Stores all data locally on your computer
- Does not include any telemetry or analytics
