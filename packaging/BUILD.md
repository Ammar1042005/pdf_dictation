# Building PDF Dictation for Windows

This guide explains how to create a protected, installable Windows executable for PDF Dictation.

## Prerequisites

1. **Python 3.11+** installed
2. **Virtual environment** activated (recommended)
3. **Build dependencies**:
   ```powershell
   pip install -e ".[build]"
   ```
   This installs PyInstaller and PyArmor.

4. **Inno Setup** (optional, for creating installer):
   - Download from: https://jrsoftware.org/isdl.php
   - Install and add to PATH (or use `iscc` from the installation directory)

## Quick Build

The easiest way to build is using the provided PowerShell script:

```powershell
cd pdf_dictation
.\packaging\build_windows.ps1
```

This will:
- Clean previous builds
- Obfuscate code with PyArmor (for protection)
- Build a single-file exe with PyInstaller
- Restore original source code

The output will be in `dist/PDFDictation.exe`

## Build Options

### Without Code Protection

If you want to skip PyArmor obfuscation (faster build, but less protection):

```powershell
.\packaging\build_windows.ps1 -Protect:$false
```

### Skip PyArmor Check

If PyArmor is already installed and you want to skip the check:

```powershell
.\packaging\build_windows.ps1 -SkipPyArmor
```

## Manual Build Steps

If you prefer to build manually:

### 1. Install Dependencies

```powershell
pip install pyinstaller pyarmor
```

### 2. Obfuscate Code (Optional but Recommended)

```powershell
cd pdf_dictation
pyarmor gen --recursive --output pdf_dictation_protected pdf_dictation
```

Then replace the original:
```powershell
Remove-Item -Recurse -Force pdf_dictation
Move-Item pdf_dictation_protected pdf_dictation
```

### 3. Build with PyInstaller

```powershell
pyinstaller --noconfirm packaging/pdfdictation.spec
```

### 4. Restore Original Code (If Obfuscated)

```powershell
Remove-Item -Recurse -Force pdf_dictation
Move-Item pdf_dictation_original pdf_dictation
```

## Creating an Installer

After building the exe, you can create a professional installer using Inno Setup:

```powershell
iscc packaging/installer.iss /DAppVersion=1.0.0
```

Replace `1.0.0` with your actual version number. The installer will be created in `dist/PDFDictation-Setup-1.0.0.exe`

## Code Protection Details

### PyArmor Protection

The build uses PyArmor to protect your code from reverse engineering:

- **Restriction Mode 2**: Prevents dynamic code execution
- **Cross-platform protection**: Works across different Python installations
- **Anti-debugging**: Makes debugging difficult
- **Anti-tampering**: Detects if code has been modified
- **Advanced obfuscation**: Makes decompilation significantly harder

### Important Notes

- PyArmor protection is **not unbreakable**, but it makes reverse engineering very difficult
- Users who want to see the code should visit your GitHub repository
- The protection adds some overhead to the build process and executable size
- The executable will still require Windows to run (not cross-platform)

## Troubleshooting

### PyArmor Installation Fails

If PyArmor installation fails, the script will automatically fall back to building without protection.

### Build Fails with Import Errors

Make sure all dependencies are installed:
```powershell
pip install -e .
```

### Exe is Too Large

The single-file exe includes all dependencies and can be 50-100MB+. This is normal for PyInstaller with PySide6.

### Antivirus Flags the Exe

Some antivirus software may flag PyInstaller executables as false positives. This is common and can be addressed by:
- Code signing the executable (requires a certificate)
- Submitting to antivirus vendors for whitelisting

## Version Information

Update the version in:
1. `pdf_dictation/__init__.py` (the `__version__` variable)
2. The Inno Setup command: `/DAppVersion=X.Y.Z`

## License Compliance

The code protection aligns with your license requirements:
- Source code is available on GitHub for inspection
- The distributed binary is protected to prevent unauthorized modification
- Users can view the source code by visiting your repository
