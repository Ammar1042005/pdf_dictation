# PDF Dictation
Controlled dictation for copying a PDF into a paper notebook: speak a chunk, stay silent while you write, speak the next, and pause at figures.

## Quick Start (For Users)

If you just want to use the application, you don't need to download the entire repository or install Python. Simply download the **PDFDictation.exe** executable from the [latest GitHub release](https://github.com/Ammar1042005/pdf_dictation/releases) and run it. The executable is self-contained and includes all necessary dependencies.

**Important:** The packaged executable is provided for convenience and personal use. The executable must not be reverse engineered, decompiled, or modified. Users who wish to study the source code, modify the application, or understand its internals should obtain the source code from the official project repository at https://github.com/Ammar1042005/pdf_dictation

## Credits

PDF Dictation was created by **Shaikh Mhammad Ammar**.

## Install (For Developers)
Create and activate a virtual environment, then install the project in editable mode:

### Windows PowerShell

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

### Windows Command Prompt

```bat
python -m venv .venv
.venv\Scripts\activate.bat
python -m pip install -e ".[dev]"
```

### Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

## Run

With the virtual environment activated, start the desktop application with either command:

```bash
python app.py
```

or:

```bash
python -m pdf_dictation
```

If the package was installed with the virtual environment active, the GUI script can also be used:

```bash
pdfdictation
```

To run it without activating the environment on Windows:

```powershell
.venv\Scripts\python.exe app.py
```

Linux TTS needs `espeak-ng` (`sudo apt install espeak-ng`). Tests: `pytest` (GUI tests use Qt's offscreen platform in CI).
On Windows, run `powershell -ExecutionPolicy Bypass -File packaging/install_ocr.ps1 -Install` for an optional WinGet-assisted Tesseract installation. The script is explicit about failures and never changes OCR settings automatically.
Quality checks: `ruff check .` and `pyright`.
CI tests Python 3.11, 3.12, and 3.13 on Windows and Ubuntu. Release packaging remains pinned to Python 3.11. Linux releases can use `packaging/build_linux.sh` for a portable tarball; `packaging/build_appimage.sh` stages an AppImage and uses `appimagetool` when available.
The application runs locally and does not require cloud APIs, API keys, authentication tokens, or network access at runtime. PDF processing uses `pymupdf`; OCR uses locally installed Tesseract when enabled; speech uses the local `pyttsx3` backend.
The application includes a local document-and-speech icon in the desktop window and packaged builds.
Updates are opt-in in Settings. Enable “Check GitHub for updates at startup” when you want release checks. Official release sources are built into the application and cannot be edited by users; additional official mirrors can be added in future application releases. Checks are read-only, use a short timeout, and open the verified GitHub release page for manual installation; the application never silently replaces files.
## License

PDF Dictation uses the **PDF Dictation Source-Available Non-Commercial License**.

### Key Terms:

- **Source Code**: May be studied, modified, and shared for non-commercial purposes with attribution and the same restrictions
- **Commercial Use**: Selling the project, using it commercially, or monetizing any feature is prohibited
- **Packaged Executables**: The Windows executable (PDFDictation.exe), Linux packages, AppImages, and other compiled distributions **must not be**:
  - Reverse engineered
  - Decompiled
  - Disassembled
  - Modified, patched, or repackaged
  - Redistributed or sold
  - Unpacked for creating derivative distributions

### For Source Code Access:

Users who wish to study the program, modify it, or understand its internals must obtain the source code from the official project repository:
**https://github.com/Ammar1042005/pdf_dictation**

The repository is the designated location for studying the program and its source code. Reverse engineering or attempting to extract source code from the packaged executable is strictly prohibited.

The full license includes definitions for contribution, limited patent grant, attribution, termination, no-sublicensing, trademark, warranty, and liability terms.
Primary controls and live dictation status elements expose accessible names and descriptions, with a predictable keyboard focus order for screen readers.
Main text uses Qt font sizes that follow desktop scaling, and status colors adapt to high-contrast system palettes.
Settings includes an opt-in privacy-safe diagnostics export containing environment and selected settings only; PDF text, OCR text, and document paths are not included.
Packaged users can extend the application without modifying the EXE or Linux package. Enable **External plugins and voice profiles** in Settings, then use **Open plugins folder**. Add JSON voice profiles containing `{"name": "My Voice", "voice_id": "installed-system-voice-id"}` to expose installed local TTS voices under a custom name. Python plugin files may define `register(profiles)`, append `{"name": "...", "voice_id": "..."}` dictionaries to `profiles`, and are loaded only after this setting is enabled. Python plugins are trusted code and can access the user account. Voice audio engines still need to be installed in the operating system; a profile does not bypass OS voice licensing or installation.

## How it works
* **Word units:** 1–3 letters = 0.5, 4+ letters = 1.0 (punctuation ignored; numbers count digits). Chunks close at ≥3.0 units, or earlier at a sentence mark once ≥1.5. Words are never split; paragraphs never merge.
* **Writing time:** alphanumeric characters × 0.75 s (+ optional extra pause). Spaces/punctuation excluded. The timer starts only after speech finishes.
* **Images:** images ≥100×100 pt are placed in reading order among text blocks; dictation pauses *at* the image. Two-column pages are handled (full-width blocks split bands, then left column, then right).
* **Keyboard shortcuts:** Space pause/resume/continue · R/F repeat · ←/→ previous/next (lands paused) · Esc stop · +/- adjust speech rate.
* **On-screen controls:** Start/Pause, Repeat, Previous, and Next buttons are available in the main window.
* **Speech modes:** prose ignores symbols by default; enable **Speak punctuation** for sentence punctuation or **Speak code symbols** in Settings to hear brackets, operators, quotes, underscores, and other code characters.
  The default **Automatic** speech profile detects code-like chunks and speaks their special characters while keeping ordinary prose natural. Use **Prose** or **Code** in Settings to override detection.
* **PDF viewer:** Includes a scrollable page-thumbnail panel, page navigation (spinbox), back/forward page history, zoom controls (0.5x to 3.0x), document-wide search with page/result navigation, and in-session page bookmarks. Selecting a thumbnail jumps to that page. The viewer automatically shows the current chunk's page and highlights the current text or image.
* Progress is saved per PDF hash in `~/.pdf_dictation/sessions`. Log: `~/pdf_dictation.log`.

## OCR (scanned PDFs)
Pages with no text layer are OCR'd automatically (Settings → OCR). It needs the Tesseract program plus language data:
Windows: install from github.com/UB-Mannheim/tesseract · Linux: `sudo apt install tesseract-ocr` (+ e.g. `tesseract-ocr-hin`).
Full-page scan images are not treated as figures; real figures on scanned pages are still detected.

## Build installers
Everything is a normal Python package (`pdfdictation` command, `python -m pdf_dictation`), so the same code builds for both OSes.
Builds must be run on the target OS (PyInstaller does not cross-compile); the included GitHub Actions workflow does this automatically.

| Target | Command | Output (`dist/`) |
|---|---|---|
| Windows | `pip install -e ".[build]"` then `pyinstaller --noconfirm packaging/pdfdictation.spec` then `iscc packaging\installer.iss` | `PDFDictation-Setup-<ver>.exe` (no Python needed) |
| Debian/Ubuntu | `./packaging/build_linux.sh` | `.deb` (installs espeak-ng automatically) + portable `.tar.gz` |
| Any | push a tag like `v0.1.0` | CI builds and uploads all artifacts |

User data (settings, progress, log) lives in `%APPDATA%\PDFDictation` or `~/.local/share/PDFDictation`, never next to the program.
Before public release: set a real maintainer in `build_linux.sh`, add a LICENSE and an icon, and consider code-signing the Windows installer (otherwise SmartScreen warns).

## Known limitations
AppImage builds are not implemented yet.
