# PDF Dictation - Comprehensive Project Documentation

**Version:** 0.001 
**Author:** Shaikh Mhammad Ammar  
**Repository:** https://github.com/Ammar1042005/pdf_dictation  
**License:** PDF Dictation Source-Available Non-Commercial License  

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Features and Functionality](#features-and-functionality)
3. [Architecture and Module Structure](#architecture-and-module-structure)
4. [Dependencies and Tools](#dependencies-and-tools)
5. [Build and Deployment](#build-and-deployment)
6. [Testing and Quality Assurance](#testing-and-quality-assurance)
7. [Configuration and Settings](#configuration-and-settings)
8. [References and Resources](#references-and-resources)

---

## Project Overview

### Purpose
PDF Dictation is a desktop application designed to assist users in copying textbooks by hand through controlled dictation. The application speaks text chunks from PDF documents, pauses for the user to write, and automatically resumes speaking the next chunk. It intelligently handles images, tables, and two-column layouts.

### Core Problem Solved
- Enables efficient hand-copying of PDF textbooks
- Provides structured dictation with automatic timing
- Handles complex PDF layouts (columns, images, tables)
- Works entirely offline with no cloud dependencies
- Saves progress automatically for resuming later

### Target Users
- Students and researchers who need to copy textbooks by hand
- Accessibility users who benefit from audio assistance
- Non-commercial users requiring offline PDF reading assistance

### Key Characteristics
- **Platform:** Windows (primary), Linux (secondary)
- **Language:** Python 3.11+
- **Framework:** PySide6 (Qt for Python)
- **Architecture:** Desktop GUI application with offline processing
- **Privacy:** All processing local, no cloud APIs or data transmission

---

## Features and Functionality

### 1. PDF Processing and Extraction

#### Text Extraction
- **Tool:** PyMuPDF (pymupdf)
- **Capabilities:**
  - Extracts text from PDF documents
  - Preserves reading order and positioning
  - Handles multi-column layouts (detects left/right columns)
  - Processes text blocks with bounding box information
  - Supports full-width band detection for column separation

#### Image Detection
- **Minimum Size:** 100×100 points (configurable)
- **Types Detected:**
  - Figures and diagrams
  - Images embedded in text flow
  - Tables (detected as separate entities)
- **Behavior:**
  - Images placed in reading order among text blocks
  - Dictation pauses at images (user presses Space to continue)
  - Vector diagram region detection for complex layouts

#### OCR (Optical Character Recognition)
- **Engine:** Tesseract via PyMuPDF bridge
- **Usage:** Automatic for pages without text layer
- **Supported Languages:** Any Tesseract language data (default: English)
- **Caching:** OCR results cached per page to speed up repeated loads
- **Installation:**
  - Windows: Install from https://github.com/UB-Mannheim/tesseract
  - Linux: `sudo apt install tesseract-ocr`

#### Document Search
- **Scope:** Document-wide text search
- **Features:**
  - Search across all pages
  - Results with page numbers
  - Direct navigation to search results
  - GUI dropdown for result selection

#### Text Highlighting
- **Purpose:** Visual indication of current dictation chunk in PDF preview
- **Implementation:**
  - Uses QPainter to draw highlights on page render
  - Yellow semi-transparent highlight for text chunks (RGBA: 255, 235, 59, 120)
  - Red outline for images (5px width, color: #e53935)
- **Techniques:**
  - Uses word-level bounding boxes when available
  - Falls back to text search within chunk bounding box
  - Highlights all matching rectangles for multi-line chunks
- **Performance:**
  - Highlighting applied during page rendering
  - Cached page pixmap reused when highlight changes
  - Only visible region rendered for large pages
- **Tools Used:**
  - PySide6 QPainter for drawing
  - PyMuPDF for bounding box information
  - Qt color palette for theme-aware colors

### 2. Text Chunking Algorithm

#### Word Unit Calculation
- **Short Words (1-3 letters):** 0.5 units
- **Long Words (4+ letters):** 1.0 unit
- **Punctuation:** Ignored
- **Numbers:** Count digits as letters
- **Chunk Target:** 3.0 units (configurable)

#### Chunk Rules
- **Minimum Units:** 1.5 to close at sentence marks (. ? ! ; :)
- **Maximum Units:** 3.0 (configurable)
- **Constraints:**
  - Words never split across chunks
  - Paragraphs never merged
  - Sentence boundaries respected when possible
- **Configurable Parameters:**
  - `target`: Target word units per chunk (default: 3.0)
  - `short_weight`: Weight for short words (default: 0.5)
  - `long_weight`: Weight for long words (default: 1.0)
  - `short_max`: Maximum letters for short word classification (default: 3)

#### Writing Time Calculation
- **Base Formula:** `alphanumeric characters × seconds_per_char + extra_pause`
- **Default Rate:** 0.75 seconds per character
- **Profiles:**
  - **Prose:** Counts alphanumeric characters only
  - **Code:** Counts symbols (operators, brackets, etc.)
  - **Equations:** Counts mathematical symbols
  - **Custom:** User-defined character sets
- **Timer:** Starts only after speech finishes

### 3. Speech Engine

#### TTS Backend
- **Library:** pyttsx3 (offline text-to-speech)
- **Platform Support:**
  - Windows: SAPI5 (native Windows voices)
  - Linux: espeak-ng (must be installed system-wide)
  - macOS: nsss (native macOS voices)

#### Speech Modes
- **Prose Mode:** 
  - Ignores symbols by default
  - Natural speech for ordinary text
- **Code Symbols Mode:**
  - Speaks punctuation (, . ; : ? !)
  - Speaks code symbols (brackets, operators, quotes, etc.)
- **Automatic Mode (Default):**
  - Detects code-like chunks using heuristics
  - Speaks symbols for code chunks
  - Natural speech for prose chunks
  - Detection criteria: ≥2 symbols or (≥1 symbol + ≥3 identifiers)

#### Text Preparation
- **Normalization:**
  - "Fig." → "Figure"
  - "e.g." → "for example"
  - "i.e." → "that is"
  - "3.2" → "3 point 2" (numbers with decimals)
- **Symbol Names:** Maps symbols to spoken names (e.g., "+" → "plus", "(" → "left parenthesis")

#### Speech Engine Design
- **Fresh Engine per Utterance:** Creates new engine for each chunk to avoid stale state
- **Thread Safety:** Each utterance in its own worker thread
- **No Shared Locks:** stop() never blocks GUI thread
- **Error Detection:** Detects when speech finishes too fast (indicates failure)
- **Retry Logic:** Retries once on suspiciously fast completion

#### Voice Management
- **Voice Selection:** User can choose from available system voices
- **Voice Testing:** Test button to preview selected voice before using
- **Voice Status:** Shows number of detected voices and alerts if saved voice is unavailable
- **Rate Control:** Adjustable speech rate (default: 150 words per minute, range: 60-350)
- **Volume Control:** Adjustable volume (default: 1.0, range: 0.0-1.0)
- **Plugin Voices:** Custom voice profiles via JSON files
- **Voice Detection:** Automatically enumerates pyttsx3 voices on startup
- **Platform Differences:**
  - Windows: SAPI5 voices (system registry)
  - Linux: espeak-ng voices (system installation)
  - macOS: nsss voices (system voices)

#### Handwriting Calibration
- **Purpose:** Customize writing time based on individual handwriting speed
- **Method:**
  - User writes a sample sentence
  - User enters elapsed time
  - System calculates seconds per character
  - Automatically sets custom writing profile
- **Sample Text:** "The quick brown fox writes this sample sentence for calibration."
- **Calculation:** `seconds / character_count`
- **Result:** Updates "seconds per character" setting and switches to "custom" profile

### 4. Dictation Controller

#### State Machine
The controller implements a deterministic state machine driven by `tick()` calls every ~100ms:

**States:**
- `IDLE`: No document loaded
- `READY`: Document loaded, ready to start
- `SPEAKING`: Currently speaking a chunk
- `WRITING`: Paused for user to write (timer running)
- `PAUSED`: User paused (no timer)
- `IMAGE_PAUSED`: Paused at image (user must press Space to continue)
- `FINISHED`: Reached end of document
- `ERROR`: Speech engine error

#### Transitions
- **Start:** READY → SPEAKING
- **Speech Complete:** SPEAKING → WRITING
- **Writing Timer Complete:** WRITING → SPEAKING (next chunk)
- **User Pause:** Any active state → PAUSED
- **Resume:** PAUSED → SPEAKING
- **Image Detected:** SPEAKING → IMAGE_PAUSED
- **Continue from Image:** IMAGE_PAUSED → SPEAKING
- **Next:** Move to next chunk (lands in PAUSED)
- **Previous:** Move to previous chunk (lands in PAUSED)
- **Stop:** Any → READY or IDLE

#### Timer Management
- **Writing Timer:** Counts down during WRITING state
- **Display:** Shows remaining time in status bar
- **Progress Bar:** Visual indicator of writing progress
- **Adjustment:** User can adjust rate with +/- keys

### 5. User Interface

#### Performance Optimizations
- **Preview Caching:**
  - Page renderings cached by (page_number, zoom) key
  - Cache cleared when new PDF loaded
  - Reduces redundant page rendering
  - Zoom levels rounded to 2 decimal places for cache key
- **Thumbnail Caching:**
  - Page thumbnails cached separately
  - 120×160px icons for thumbnail panel
  - Generated on PDF load
  - Cache cleared when new PDF loaded
- **Visible Region Rendering:**
  - Only visible page region rendered during scroll
  - Renders 2x viewport size for smooth scrolling
  - Significant performance improvement for large pages
  - Uses clip parameter in PyMuPDF
- **Lazy Loading:**
  - Thumbnails generated on demand
  - Not all pages rendered at once
  - Progress dialog during PDF loading

#### Page History Navigation
- **Purpose:** Track visited pages for back/forward navigation
- **Implementation:**
  - Maintains list of visited page numbers
  - Current position tracked with index
  - History cleared when new PDF loaded
- **Features:**
  - Back button returns to previous page
  - Forward button returns to next page in history
  - Buttons disabled when at history boundaries
  - Automatic history tracking on page changes
- **Indicators:**
  - Back button disabled when at beginning of history
  - Forward button disabled when at end of history

#### Main Window Components
- **PDF Viewer:**
  - Scrollable page preview with click-to-select chunks
  - Page thumbnail panel (120×160px icons, scrollable)
  - Zoom controls (0.5x to 3.0x with spinbox and +/- buttons)
  - Click on preview to select dictation chunks
  - Automatic highlight of current chunk (yellow for text, red for images)
  - Two-column layout handling
  - Splitter for resizable thumbnail/preview area
  - Efficient rendering (only visible region rendered)
  - Page caching for performance
- **Page Navigation:**
  - Page number spinbox (1 to 9999)
  - "Go" button to jump to specific page
  - Back/Forward buttons for page history navigation
  - Total page count display
  - Automatic page sync with current chunk
  - Page spinbox updates when chunk changes
- **Controls:**
  - Start/Pause button (text changes based on state)
  - Repeat button (repeat current chunk)
  - Previous button (move to previous item, lands paused)
  - Next button (move to next item, lands paused)
  - All buttons have minimum width of 100px
- **Status Display:**
  - Large status label (20pt bold, SPEAKING/WRITING/PAUSED/etc.)
  - Status colors adapt to system palette
  - Current chunk text display (16pt, word wrap)
  - Position info (page X/Y, item N/M, writing time)
  - Writing time display (showing remaining time)
  - Progress bar for writing timer (0-1000 range, 10px height)
- **Search:**
  - Search text input with placeholder
  - Search button
  - Results dropdown (260px minimum width)
  - Results show page numbers
  - Direct navigation to selected result
  - Return key triggers search
- **Bookmarks:**
  - Bookmark current page button
  - Bookmark list (70px max height, collapsible)
  - Quick navigation to bookmarked pages
  - List shows when bookmarks exist
  - Item activation opens bookmarked page
- **Click-to-Select:**
  - Click on PDF preview to select text chunks
  - Finds chunk containing clicked position
  - Uses word-level bounding boxes for accuracy
  - Converts screen coordinates to PDF coordinates
  - Skips images (only text chunks selectable)
  - Words normalized (case, punctuation) for matching
  - Controller jumps to selected chunk
- **Settings:**
  - Seconds per character (0.05 to 5.0)
  - Extra pause (0 to 30 seconds)

#### Keyboard Shortcuts
- **Space:** Pause/Resume/Continue
- **R or F:** Repeat current chunk
- **Left Arrow:** Previous item (lands paused)
- **Right Arrow:** Next item (lands paused)
- **Esc:** Stop dictation
- **+ / -:** Adjust speech rate (±10 WPM)

#### Accessibility
- **Screen Reader Support:**
  - All controls have accessible names and descriptions
  - Predictable keyboard focus order (Tab order defined in code)
  - Qt offscreen platform for CI testing
  - Main controls have semantic descriptions
- **Visual Accessibility:**
  - Qt font sizes follow desktop scaling
  - Status colors adapt to high-contrast system palettes
  - Large, readable status text (20pt for status, 16pt for chunks)
  - Status colors use Qt palette (Highlight, HighlightedText)
- **Keyboard Navigation:**
  - Full tab order defined for all controls
  - Logical focus sequence (Open PDF → Settings → Page controls → Zoom → Search → Bookmarks → Dictation buttons)
  - Shortcuts for all major functions
  - No mouse required for basic operation

#### Settings Dialog
Configurable settings include:
- **Timing:**
  - Seconds per character (0.05 to 5.0)
  - Extra pause (0 to 30 seconds)
  - Writing profile (prose/code/equations/custom)
  - Handwriting calibration tool
- **Chunking:**
  - Target word units (1 to 10)
  - Short/long word weights (0 to 5)
  - Short word max length (1 to 10)
- **Speech:**
  - Voice selection (dropdown with system voices)
  - Voice status (number of voices, availability check)
  - Voice test button (preview selected voice)
  - Speech rate (60 to 350 WPM)
  - Volume (0.0 to 1.0)
  - Speech profile (prose/code/automatic)
  - Speak punctuation toggle
  - Speak symbols toggle
  - Text normalization toggle
- **OCR:**
  - OCR mode (auto/off)
  - OCR language (text input, e.g., "eng", "hin")
  - OCR cache toggle
  - Clear OCR cache button
- **Images:**
  - Pause at images toggle
  - Minimum image width (0 to 2000 points)
  - Minimum image height (0 to 2000 points)
- **Updates:**
  - Auto-update check toggle
- **Plugins:**
  - Enable external plugins toggle
  - Open plugins folder button (opens system file manager)
- **Diagnostics:**
  - Export diagnostics button (privacy-safe JSON export)

#### License Dialog
- Displays full license text
- Clickable GitHub repository link
- Checkbox agreement required
- Accept/Decline buttons
- Opens on first run if not previously accepted

### 6. Session Management

#### Progress Saving
- **Storage:** `~/.pdf_dictation/sessions/` (Linux) or `%APPDATA%\PDFDictation\sessions\` (Windows)
- **Method:** Per-PDF hash using SHA-256
- **Saved Data:**
  - PDF hash (for file identification)
  - Current chunk index
  - Page number
  - Chunk text hash (for accurate resume)
  - Extraction settings hash (detects changed settings)
  - User timing settings
- **Resume Behavior:**
  - Asks user if they want to resume on load
  - Matches chunk by text hash if possible
  - Falls back to saved index if text changed

#### OCR Cache
- **Storage:** `~/.pdf_dictation/ocr_cache/`
- **Key:** PDF hash + page number + language
- **Content:** OCR text blocks for the page
- **Benefit:** Avoids re-OCR on repeated loads

### 7. Plugin System

#### Purpose
Allows users to extend the application without modifying the executable or package files. This is especially useful for packaged builds where users cannot modify application files directly.

#### Plugin Location
- **Windows:** `%APPDATA%\PDFDictation\plugins\`
- **Linux:** `~/.local/share/PDFDictation/plugins/`
- **macOS:** `~/Library/Application Support/PDFDictation/plugins/`
- **Auto-creation:** Folder created automatically when "Open plugins folder" is clicked

#### Voice Profiles (JSON)
- **Purpose:** Expose system voices under custom names without programming
- **File Extension:** `.json`
- **Format:**
  ```json
  {
    "name": "My Custom Voice",
    "voice_id": "HKEY_LOCAL_MACHINE\\SOFTWARE\\Microsoft\\Speech\\Voices\\Tokens\\TTS_MS_EN-US_ZIRA_11.0"
  }
  ```
- **Features:**
  - Rename system voices to memorable names
  - Group related voices
  - Create language-specific profiles
  - Easy to create (no programming required)
- **Validation:**
  - JSON parsing with error handling
  - Type conversion for voice_id and name
  - Invalid profiles are logged and ignored
- **Loading:**
  - Loaded on startup if plugins enabled
  - Sorted alphabetically by filename
  - Profiles starting with underscore (_) are ignored

#### Python Plugins
- **Purpose:** Programmatic extension of voice profiles and application functionality
- **File Extension:** `.py`
- **Interface:**
  ```python
  def register(profiles):
      profiles.append({"name": "Plugin Voice", "voice_id": "voice-id"})
  ```
- **Capabilities:**
  - Add custom voice profiles programmatically
  - Dynamic voice profile generation
  - Integration with external voice systems
  - Extend application functionality (trusted code)
- **Security:**
  - Plugins are trusted code (full user account access)
  - Opt-in only (must be enabled in settings)
  - Files starting with underscore (_) are ignored
  - No sandboxing or security restrictions
- **Loading:**
  - Uses Python's importlib.util for dynamic loading
  - Each plugin loaded in isolated namespace
  - register() function called with profiles list
  - Errors are logged but don't prevent other plugins from loading
- **Implementation:**
  - Uses importlib.util.spec_from_file_location
  - spec.loader.exec_module() for execution
  - Handles import errors gracefully
  - Logs warnings for failed plugins

#### Plugin Integration in UI
- **Settings Dialog:**
  - "Enable external plugins and voice profiles" checkbox
  - "Open plugins folder" button
  - Opens system file manager to plugin directory
- **Voice Selection:**
  - Plugin voices appear in voice dropdown
  - Combined with system voices
  - Sorted alphabetically
- **Voice Status:**
  - Shows total voice count (system + plugins)
  - Alerts if saved voice is unavailable

#### Tools Used
- **importlib.util:** Dynamic Python module loading
- **json:** JSON profile parsing
- **pathlib:** File system operations
- **logging:** Error and warning logging
- **QFileDialog / os.startfile / subprocess:** Open plugin folder

### 8. Update Checker

#### Design Principles

#### Design Principles
- **Opt-in:** Must be enabled in settings
- **Read-only:** Never downloads or replaces files
- **Application-controlled:** Release sources built into application
- **User-controlled:** Opens GitHub release page for manual installation

#### Implementation
- **Sources:** Hardcoded list of official repositories
  - Primary: https://github.com/Ammar1042005/pdf_dictation
- **API:** GitHub Releases API
- **Timeout:** 5 seconds
- **Check Frequency:** On startup if enabled
- **User Action:** Opens release page in browser for manual download

### 9. Diagnostics

#### Privacy-Safe Report
- **Excludes:**
  - PDF document content
  - OCR text
  - Document paths
  - User settings values (only keys reported)
- **Includes:**
  - Application version
  - Python version
  - Platform information
  - PyMuPDF version
  - OCR availability status
  - Speech engine diagnostics
  - Selected settings (keys only)
- **Format:** JSON
- **Use:** Troubleshooting without exposing user data

---

## Architecture and Module Structure

### Module Organization

```
pdf_dictation/
├── __init__.py          # Version definition
├── __main__.py          # Module entry point
├── gui.py               # Main GUI window and widgets
├── controller.py       # Dictation state machine (Qt-free)
├── chunker.py           # Text chunking and timing algorithms
├── extractor.py         # PDF extraction and OCR integration
├── speech.py            # TTS engine wrapper
├── textprep.py          # Speech-friendly text preparation
├── ocr.py               # OCR interface and availability checks
├── settings.py          # Settings persistence
├── settings_dialog.py   # Settings UI
├── sessions.py          # Progress and OCR cache management
├── paths.py             # Platform-specific paths
├── updater.py           # GitHub release checker
├── plugins.py           # External plugin system
└── diagnostics.py       # Privacy-safe diagnostic reports
```

### Module Responsibilities

#### gui.py
- **Purpose:** Main application window and UI logic
- **Key Classes:**
  - `Win`: Main QMainWindow with all UI components
  - `LicenseDialog`: License agreement dialog
  - `PreviewLabel`: Clickable PDF preview widget
  - `Loader`: Background thread for PDF loading
- **Responsibilities:**
  - UI layout and event handling
  - PDF preview rendering
  - Thumbnail generation
  - Search functionality
  - Keyboard shortcuts
  - Plugin integration
  - Settings dialog invocation

#### controller.py
- **Purpose:** Qt-free dictation state machine
- **Key Classes:**
  - `Controller`: Main state machine driver
  - `State`: Enum of dictation states
  - `Settings`: Configuration dataclass
- **Responsibilities:**
  - State transitions
  - Timer management
  - Speech coordination
  - Writing time calculation
  - Pause/resume logic
  - Image detection handling

#### chunker.py
- **Purpose:** Text chunking and timing algorithms
- **Key Classes:**
  - `Chunk`: Text chunk with metadata
  - `ImageItem`: Image placeholder
  - `WordRules`: Chunking parameters
  - `TextChunker`: Main chunking logic
- **Responsibilities:**
  - Word unit calculation
  - Chunk boundary detection
  - Writing time calculation
  - Code/prose detection
  - Character counting per profile

#### extractor.py
- **Purpose:** PDF extraction and OCR integration
- **Key Classes:**
  - `Entry`: PDF block (text or image)
  - `Loaded`: Extraction result with metadata
- **Responsibilities:**
  - PDF parsing with PyMuPDF
  - Reading order detection
  - Column detection (left/right)
  - Image classification
  - Table detection
  - OCR integration
  - Vector diagram detection
  - Document search

#### speech.py
- **Purpose:** TTS engine wrapper
- **Key Classes:**
  - `SpeechEngine`: Main speech engine interface
- **Responsibilities:**
  - Voice enumeration
  - Speech synthesis
  - Rate/volume control
  - Thread management
  - Error detection
  - Retry logic
  - Plugin voice integration

#### textprep.py
- **Purpose:** Speech-friendly text preparation
- **Functions:**
  - `prepare_speech()`: Normalize and enhance text for TTS
  - `looks_like_code()`: Detect code-like chunks
- **Responsibilities:**
  - Text normalization
  - Symbol name expansion
  - Punctuation speaking
  - Code detection heuristics

#### ocr.py
- **Purpose:** OCR interface and availability checks
- **Functions:**
  - `available()`: Check OCR readiness
  - `availability_error()`: Report missing OCR components
  - `ocr_blocks()`: Perform OCR on a page
- **Responsibilities:**
  - Tesseract integration
  - Language data availability
  - OCR execution
  - Tessdata directory detection

#### settings.py
- **Purpose:** Settings persistence
- **Functions:**
  - `load()`: Load settings from JSON
  - `save()`: Save settings to JSON
- **Responsibilities:**
  - Settings serialization
  - Type conversion
  - Error handling
  - Migration from old versions

#### sessions.py
- **Purpose:** Progress and OCR cache management
- **Functions:**
  - `save()`: Save progress for a PDF
  - `load()`: Load progress for a PDF
  - `save_ocr_cache()`: Cache OCR results
  - `load_ocr_cache()`: Load cached OCR
- **Responsibilities:**
  - PDF hashing
  - Text hashing
  - JSON serialization
  - Cache invalidation

#### paths.py
- **Purpose:** Platform-specific path resolution
- **Functions:**
  - `data_dir()`: Application data directory
  - `log_file()`: Log file path
  - `resource()`: Resource file path
- **Responsibilities:**
  - Cross-platform path handling
  - XDG compliance (Linux)
  - AppData compliance (Windows)

#### updater.py
- **Purpose:** GitHub release checker
- **Key Classes:**
  - `Release`: Release information
- **Functions:**
  - `check_latest()`: Check for updates
  - `repository_api_url()`: Build GitHub API URL
- **Responsibilities:**
  - GitHub API interaction
  - Version comparison
  - Network error handling
  - Timeout management

#### plugins.py
- **Purpose:** External plugin system
- **Key Classes:**
  - `VoiceProfile`: Voice profile data
- **Functions:**
  - `load_voice_profiles()`: Load JSON profiles
  - `load_python_plugins()`: Load Python plugins
- **Responsibilities:**
  - Plugin discovery
  - JSON parsing
  - Python module loading
  - Error handling
  - Security (opt-in only)

#### diagnostics.py
- **Purpose:** Privacy-safe diagnostic reports
- **Functions:**
  - `report()`: Generate diagnostic data
  - `write_report()`: Write report to file
- **Responsibilities:**
  - Environment information collection
  - Version detection
  - Privacy preservation
  - JSON formatting

### Data Flow

#### Document Loading Flow
```
User selects PDF → Loader thread started
→ PDF opened with PyMuPDF
→ Pages extracted
→ OCR if needed (with cache check)
→ Reading order calculated
→ Images detected and classified
→ Text chunked
→ Items passed to Controller
→ Controller state set to READY
→ Thumbnails generated
→ UI updated
```

#### Dictation Flow
```
User clicks Start → Controller state: SPEAKING
→ Speech engine speaks chunk
→ GUI shows "SPEAKING" status
→ Speech completes → Controller state: WRITING
→ Writing timer starts
→ GUI shows progress bar
→ Timer expires → Controller state: SPEAKING
→ Next chunk spoken
→ ... repeat until FINISHED
```

#### Settings Persistence Flow
```
User changes setting → Settings object updated
→ On save: Settings serialized to JSON
→ Written to data_dir()/settings.json
→ On load: JSON parsed
→ Type conversion applied
→ Settings object reconstructed
```

---

## Dependencies and Tools

### Core Dependencies

#### PySide6 (>=6.6)
- **Purpose:** Qt for Python GUI framework
- **Usage:**
  - MainWindow, widgets, layouts
  - Event handling and signals/slots
  - Timer and threading
  - PDF rendering (QImage, QPixmap)
  - Platform integration
- **Components Used:**
  - QtCore: QTimer, Qt, QThread, Signal, QPoint, QSize
  - QtGui: QShortcut, QKeySequence, QPixmap, QImage, QPainter, QPen, QColor, QFont, QPalette, QIcon
  - QtWidgets: QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFileDialog, QMessageBox, QDoubleSpinBox, QSpinBox, QProgressBar, QProgressDialog, QLineEdit, QComboBox, QListWidget, QListWidgetItem, QSplitter, QDialog, QTextEdit, QCheckBox, QScrollArea

#### PyMuPDF (>=1.24)
- **Purpose:** PDF processing library
- **Usage:**
  - PDF opening and parsing
  - Text extraction
  - Image extraction
  - OCR integration (Tesseract bridge)
  - Block and word level positioning
  - Document search
- **Key Functions:**
  - `fitz.open()`: Open PDF
  - `page.get_text()`: Extract text
  - `page.get_images()`: Extract images
  - `page.get_textpage_ocr()`: OCR page
  - `page.search_for()`: Search text

#### pyttsx3 (>=2.90)
- **Purpose:** Offline text-to-speech library
- **Usage:**
  - Cross-platform TTS abstraction
  - Voice enumeration
  - Speech synthesis
  - Rate and volume control
- **Platform Backends:**
  - Windows: SAPI5 (requires pythoncom)
  - Linux: espeak-ng
  - macOS: nsss

### Development Dependencies

#### pytest
- **Purpose:** Testing framework
- **Usage:**
  - Unit tests
  - Integration tests
  - GUI tests (with offscreen platform)
- **Test Files:**
  - `test_core.py`: Core logic tests
  - `test_gui.py`: GUI component tests
  - `test_plugins.py`: Plugin system tests
  - `test_sample_pdfs.py`: PDF processing tests
  - `test_updater.py`: Update checker tests

#### ruff (>=0.6)
- **Purpose:** Fast Python linter
- **Configuration:**
  - Target version: Python 3.11
  - Line length: 120
  - Rules: E4, E9, F (syntax and runtime errors)
  - Excludes: .venv, build, dist

#### pyright (>=1.1.380)
- **Purpose:** Static type checker
- **Configuration:**
  - Type checking mode: basic
  - Includes: pdf_dictation module
  - Excludes: .venv, build, dist, tests
  - Disabled checks: missing imports, type stubs, assignment type, argument type, optional member access, optional subscript

### Build Dependencies

#### pyinstaller (>=6.6)
- **Purpose:** Python application packaging
- **Usage:**
  - Single-file executable creation
  - Dependency collection
  - Icon embedding
  - Manifest embedding
- **Spec File:** `packaging/pdfdictation.spec`
- **Excludes:** tkinter, QtWebEngineCore, QtQuick, QtQml, Qt3DCore, matplotlib, numpy, pandas

#### pyarmor (>=8.0)
- **Purpose:** Code protection (optional)
- **Usage:**
  - Source code obfuscation
  - License enforcement
- **Workflow:** Run before PyInstaller

### System Dependencies

#### Windows
- **Python:** 3.11+ (for development)
- **Tesseract:** Optional (for OCR)
  - Download: https://github.com/UB-Mannheim/tesseract
- **Inno Setup:** For installer creation
  - Download: https://jrsoftware.org/isdl.php

#### Linux
- **Python:** 3.11+ (for development)
- **espeak-ng:** Required for TTS
  - Install: `sudo apt install espeak-ng`
- **Tesseract:** Optional (for OCR)
  - Install: `sudo apt install tesseract-ocr`
- **System Libraries:** Required for Qt
  - libegl1
  - libxkbcommon0
  - libxcb-cursor0

### Optional Dependencies

#### pythoncom
- **Purpose:** Windows COM initialization for SAPI5
- **Platform:** Windows only
- **Installed with:** pyttsx3

#### appimagetool
- **Purpose:** AppImage creation for Linux
- **Platform:** Linux only
- **Download:** https://github.com/AppImage/AppImageKit/releases

---

## Build and Deployment

### Build Process

#### Windows Build
1. **Prerequisites:**
   - Python 3.11 installed
   - Virtual environment activated
   - Dependencies installed: `pip install -e ".[build]"`
2. **Build Steps:**
   ```powershell
   pyinstaller --noconfirm packaging/pdfdictation.spec
   ```
3. **Output:** `dist/PDFDictation.exe` (single-file executable)
4. **Installer Creation (Optional):**
   ```powershell
   choco install innosetup -y
   "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" packaging\installer.iss
   ```
5. **Final Output:** `dist/PDFDictation-Setup-<ver>.exe`

#### Linux Build
1. **Prerequisites:**
   - Python 3.11 installed
   - espeak-ng installed: `sudo apt install espeak-ng`
   - Virtual environment activated
   - Dependencies installed: `pip install -e ".[build]"`
2. **Build Steps:**
   ```bash
   ./packaging/build_linux.sh
   ```
3. **Outputs:**
   - `dist/pdf-dictation_<ver>_amd64.deb` (Debian package)
   - `dist/PDFDictation-<ver>-linux-x86_64.tar.gz` (portable tarball)
4. **AppImage Build (Incomplete):**
   ```bash
   ./packaging/build_appimage.sh
   ```
   - Note: AppImage builds are not fully implemented yet

### PyInstaller Spec File

#### Configuration
- **Mode:** Single-file executable
- **Entry Point:** `app.py`
- **Working Directory:** `pdf_dictation/pdf_dictation/`
- **Data Files:**
  - `pdf_dictation/assets` → `pdf_dictation/assets`
  - `LICENSE` → `.`
- **Hidden Imports:**
  - `pyttsx3` (all submodules)
  - `pdf_dictation` (all submodules)
  - `pymupdf` (all submodules)
  - PySide6 (handled by built-in hooks)
- **Excludes:**
  - tkinter
  - PySide6.QtWebEngineCore
  - PySide6.QtQuick
  - PySide6.QtQml
  - PySide6.Qt3DCore
  - matplotlib
  - numpy
  - pandas
- **Console:** Hidden (windowed application)
- **Icon:** `pdf_dictation/assets/pdf_dictation.svg`

### CI/CD Pipeline

#### GitHub Actions Workflow
- **Trigger:** Push to tags matching `v*`
- **Manual Trigger:** workflow_dispatch
- **Jobs:**

##### Compatibility Testing
- **Matrix:**
  - OS: windows-latest, ubuntu-22.04
  - Python: 3.11, 3.12, 3.13
- **Steps:**
  - Checkout code
  - Setup Python
  - Install espeak-ng (Linux only)
  - Install dependencies: `pip install -e ".[dev]"`
  - Run tests with offscreen Qt platform

##### Build and Release
- **Matrix:**
  - OS: windows-latest, ubuntu-22.04
  - Python: 3.11 (pinned for releases)
- **Steps:**
  - Checkout code
  - Setup Python 3.11
  - Install espeak-ng (Linux only)
  - Install dependencies: `pip install -e ".[dev,build]"`
  - Run tests
  - Run linter: `ruff check .`
  - Run type checker: `pyright`
  - **Windows:**
    - Build with PyInstaller
    - Install Inno Setup
    - Create installer
  - **Linux:**
    - Run build_linux.sh
  - Upload artifacts (exe, deb, tar.gz)

### Distribution

#### Windows Distribution
- **Formats:**
  - Single-file executable: `PDFDictation.exe`
  - Installer: `PDFDictation-Setup-<ver>.exe`
- **Requirements:** None (self-contained)
- **User Installation:** Run installer or copy executable

#### Linux Distribution
- **Formats:**
  - Debian package: `pdf-dictation_<ver>_amd64.deb`
  - Portable tarball: `PDFDictation-<ver>-linux-x86_64.tar.gz`
- **Debian Package:**
  - Auto-installs espeak-ng dependency
  - Installs to `/opt/pdfdictation/`
  - Creates symlink in `/usr/bin/pdfdictation`
  - Adds desktop entry
- **Portable Tarball:**
  - Extracts to `PDFDictation/` directory
  - Requires manual dependency installation
  - User must install espeak-ng, libegl1, libxkbcommon0, libxcb-cursor0

### User Data Locations

#### Windows
- **Application Data:** `%APPDATA%\PDFDictation\`
- **Subdirectories:**
  - `settings.json` - User settings
  - `sessions/` - Progress data (per PDF)
  - `ocr_cache/` - OCR cache
  - `plugins/` - User plugins
- **Log File:** `%APPDATA%\PDFDictation\pdf_dictation.log`

#### Linux
- **Application Data:** `~/.local/share/PDFDictation/`
- **Subdirectories:** Same as Windows
- **Log File:** `~/.local/share/PDFDictation/pdf_dictation.log`

### Code Protection (Optional)

#### PyArmor Integration
- **Purpose:** Source code obfuscation
- **Usage:**
  ```bash
  pyarmor gen --recursive pdf_dictation
  pyinstaller --noconfirm packaging/pdfdictation.spec
  ```
- **Output:** Protected executable with obfuscated Python code
- **Status:** Supported but not mandatory

---

## Testing and Quality Assurance

### Test Suite

#### Test Files

##### test_core.py
- **Purpose:** Core logic tests
- **Coverage:**
  - Word weight calculation
  - Writing time calculation
  - Timing profiles (prose, code, equations)
  - Diagnostics report privacy
- **Example Tests:**
  - `test_weights`: Verify word unit calculation
  - `test_timing`: Verify writing time formula
  - `test_timing_profiles`: Verify character counting per profile
  - `test_diagnostics_report_excludes_document_content`: Verify privacy

##### test_gui.py
- **Purpose:** GUI component tests
- **Platform:** Offscreen Qt platform
- **Coverage:**
  - Widget initialization
  - Event handling
  - Accessibility features

##### test_plugins.py
- **Purpose:** Plugin system tests
- **Coverage:**
  - JSON voice profile loading
  - Python plugin loading
  - Error handling

##### test_sample_pdfs.py
- **Purpose:** PDF processing tests
- **Coverage:**
  - Text extraction
  - Image detection
  - Column detection
  - OCR integration
  - Search functionality

##### test_updater.py
- **Purpose:** Update checker tests
- **Coverage:**
  - Version comparison
  - GitHub API interaction
  - Error handling

### Quality Tools

#### Ruff (Linter)
- **Purpose:** Fast Python linting
- **Configuration:**
  - Target: Python 3.11
  - Line length: 120
  - Rules: E4, E9, F (syntax and runtime errors)
- **Usage:**
  ```bash
  ruff check .
  ```

#### Pyright (Type Checker)
- **Purpose:** Static type checking
- **Configuration:**
  - Mode: basic
  - Strictness: Relaxed (many checks disabled for rapid development)
- **Disabled Checks:**
  - reportMissingImports
  - reportMissingTypeStubs
  - reportAssignmentType
  - reportArgumentType
  - reportOptionalMemberAccess
  - reportOptionalSubscript
- **Usage:**
  ```bash
  pyright
  ```

### Testing Strategy

#### Unit Tests
- **Scope:** Individual functions and classes
- **Focus:** Core algorithms (chunking, timing, OCR)
- **Mocking:** External dependencies (TTS, OCR, file system)

#### Integration Tests
- **Scope:** Module interactions
- **Focus:** Controller state machine, plugin system
- **Real Dependencies:** PDF files, TTS engines

#### GUI Tests
- **Scope:** UI components
- **Platform:** Offscreen Qt platform (headless)
- **Focus:** Widget behavior, accessibility

#### Compatibility Tests
- **Scope:** Cross-platform compatibility
- **Matrix:**
  - Python: 3.11, 3.12, 3.13
  - OS: Windows, Ubuntu 22.04
- **CI:** GitHub Actions

### Manual Testing Checklist

#### PDF Loading
- [ ] Plain text PDF loads correctly
- [ ] Scanned PDF with OCR loads correctly
- [ ] Multi-column PDF loads correctly
- [ ] PDF with images loads correctly
- [ ] PDF with tables loads correctly
- [ ] Large PDF (>100 pages) loads without timeout

#### Dictation
- [ ] Start/Pause works correctly
- [ ] Writing timer is accurate
- [ ] Image pause works
- [ ] Previous/Next navigation works
- [ ] Repeat works
- [ ] Stop works
- [ ] Finish state reached at end

#### Settings
- [ ] All settings persist
- [ ] Voice selection works
- [ ] Rate adjustment works
- [ ] Volume adjustment works
- [ ] OCR settings work
- [ ] Chunking settings work

#### Accessibility
- [ ] Keyboard shortcuts work
- [ ] Screen reader announces controls
- [ ] High-contrast mode works
- [ ] Font scaling works

#### Platform-Specific
- [ ] Windows: SAPI5 voices work
- [ ] Linux: espeak-ng works
- [ ] OCR works on both platforms
- [ ] File paths are correct on both platforms

---

## Configuration and Settings

### Settings Structure

#### Settings Dataclass
```python
@dataclass
class Settings:
    seconds_per_char: float = 0.75      # Base writing time per character
    extra_pause: float = 0.0            # Additional pause after each chunk
    writing_profile: str = "prose"      # "prose" | "code" | "equations" | "custom"
    pause_at_images: bool = True        # Pause dictation at images
    speak_punctuation: bool = False     # Speak sentence punctuation
    speak_symbols: bool = False         # Speak code symbols
    speech_profile: str = "automatic"   # "prose" | "code" | "automatic"
    normalize: bool = True              # Normalize text (e.g., "Fig." → "Figure")
    target: float = 3.0                 # Target word units per chunk
    short_weight: float = 0.5           # Weight for short words (1-3 letters)
    long_weight: float = 1.0            # Weight for long words (4+ letters)
    short_max: int = 3                  # Max letters for short word classification
    min_img_w: int = 100                # Minimum image width (points)
    min_img_h: int = 100                # Minimum image height (points)
    voice_id: str = ""                  # Selected voice ID
    rate: int = 150                     # Speech rate (words per minute)
    volume: float = 1.0                 # Speech volume (0.0 to 1.0)
    ocr_mode: str = "auto"              # "auto" | "off"
    ocr_language: str = "eng"           # OCR language code
    use_ocr_cache: bool = True          # Enable OCR caching
    auto_update: bool = False           # Check for updates on startup
    enable_plugins: bool = False        # Enable external plugins
    license_accepted: bool = False      # License agreement status
```

### Default Values Rationale

#### Timing Defaults
- **seconds_per_char: 0.75**
  - Based on average handwriting speed
  - 0.75s per character ≈ 80 characters per minute
  - Adjustable for different writing speeds

- **extra_pause: 0.0**
  - No additional pause by default
  - User can add pause for longer rests

- **writing_profile: "prose"**
  - Most common use case (textbooks)
  - Counts only alphanumeric characters
  - Ignores symbols and punctuation

#### Chunking Defaults
- **target: 3.0**
  - Balance between short and long chunks
  - 3 units ≈ 6-9 words (typical dictation chunk)
  - Adjustable for memory span

- **short_weight: 0.5, long_weight: 1.0**
  - Short words (1-3 letters) count half
  - Long words (4+ letters) count full
  - Prevents very short chunks from many small words

- **short_max: 3**
  - Classification threshold for short words
  - "a", "an", "the" are short
  - "cell", "book" are long

#### Speech Defaults
- **speech_profile: "automatic"**
  - Best of both worlds
  - Detects code chunks automatically
  - Natural speech for prose

- **rate: 150**
  - Normal speech rate
  - Adjusted with +/- keys
  - Range: typically 50-400 WPM

- **volume: 1.0**
  - Full volume by default
  - Adjustable in settings

#### OCR Defaults
- **ocr_mode: "auto"**
  - OCR when needed (no text layer)
  - No unnecessary OCR on text PDFs
  - Can be disabled for performance

- **ocr_language: "eng"**
  - English by default
  - User can change for other languages
  - Supports multiple languages (e.g., "eng+hin")

- **use_ocr_cache: True**
  - Improves performance on repeated loads
  - Caches per page
  - Can be disabled for disk space

### Settings Migration

#### Strategy
- **Forward Compatible:** Old settings files load with new versions
- **Backward Compatible:** Unknown keys ignored
- **Type Conversion:** Automatic type conversion on load
- **No Breaking Changes:** Settings structure evolves gracefully

#### Implementation
```python
def load(path=None):
    s = Settings()
    try:
        for k, v in json.loads((path or _file()).read_text()).items():
            if hasattr(s, k):  # Ignore unknown keys
                setattr(s, k, type(getattr(s, k))(v))  # Type conversion
    except FileNotFoundError: pass
    except Exception as e: logging.getLogger("pdf_dictation").error("settings load failed: %s", e)
    return s
```

### Platform-Specific Paths

#### Windows
- **Data Directory:** `%APPDATA%\PDFDictation`
- **Log File:** `%APPDATA%\PDFDictation\pdf_dictation.log`
- **Implementation:** Uses `os.getenv('APPDATA')`

#### Linux
- **Data Directory:** `~/.local/share/PDFDictation`
- **Log File:** `~/.local/share/PDFDictation/pdf_dictation.log`
- **Implementation:** Uses `os.getenv('XDG_DATA_HOME')` or `~/.local/share`

#### macOS
- **Data Directory:** `~/Library/Application Support/PDFDictation`
- **Log File:** `~/Library/Logs/PDFDictation/pdf_dictation.log`
- **Implementation:** Uses `os.path.expanduser('~/Library/Application Support')`

---

## References and Resources

### Project References

#### Repository
- **Main Repository:** https://github.com/Ammar1042005/pdf_dictation
- **Issues:** https://github.com/Ammar1042005/pdf_dictation/issues
- **Releases:** https://github.com/Ammar1042005/pdf_dictation/releases

#### Documentation
- **README:** `README.md` (project root)
- **License:** `LICENSE` (project root)
- **Spec File:** `packaging/pdfdictation.spec`
- **Build Scripts:** `packaging/build_linux.sh`, `packaging/build_appimage.sh`

### Dependency Documentation

#### PySide6
- **Website:** https://www.qt.io/
- **Documentation:** https://doc.qt.io/qtforpython/
- **API Reference:** https://doc.qt.io/qtforpython/PySide6/
- **License:** LGPLv3 / GPL

#### PyMuPDF
- **Website:** https://pymupdf.readthedocs.io/
- **Documentation:** https://pymupdf.readthedocs.io/en/latest/
- **GitHub:** https://github.com/pymupdf/PyMuPDF
- **License:** AGPL-3.0

#### pyttsx3
- **Website:** https://pyttsx3.readthedocs.io/
- **Documentation:** https://pyttsx3.readthedocs.io/en/latest/
- **GitHub:** https://github.com/nateshmbhat/pyttsx3
- **License:** MPL-2.0

#### PyInstaller
- **Website:** https://pyinstaller.org/
- **Documentation:** https://pyinstaller.org/en/stable/
- **GitHub:** https://github.com/pyinstaller/pyinstaller
- **License:** GPL-2.0

#### Tesseract OCR
- **Website:** https://github.com/tesseract-ocr/tesseract
- **Documentation:** https://tesseract-ocr.github.io/
- **Windows Build:** https://github.com/UB-Mannheim/tesseract/wiki
- **License:** Apache-2.0

#### espeak-ng
- **Website:** https://github.com/espeak-ng/espeak-ng
- **Documentation:** https://espeak-ng.github.io/
- **License:** GPL-3.0+

### Development Tools

#### pytest
- **Website:** https://docs.pytest.org/
- **Documentation:** https://docs.pytest.org/en/stable/
- **License:** MIT

#### ruff
- **Website:** https://docs.astral.sh/ruff/
- **Documentation:** https://docs.astral.sh/ruff/stable/
- **License:** MIT

#### pyright
- **Website:** https://github.com/microsoft/pyright
- **Documentation:** https://microsoft.github.io/pyright/
- **License:** MIT

### Build Tools

#### Inno Setup
- **Website:** https://jrsoftware.org/isdl.php
- **Documentation:** https://jrsoftware.org/ishelp/
- **License:** Permission-based (free for all)

#### AppImageKit
- **Website:** https://github.com/AppImage/AppImageKit
- **Documentation:** https://docs.appimage.org/
- **License:** MIT

### Platform Documentation

#### Windows
- **SAPI5 Documentation:** https://docs.microsoft.com/en-us/previous-versions/windows/desktop/ee718625(v=vs.85)
- **AppData Specification:** https://docs.microsoft.com/en-us/windows/win32/shell/knownfolderid

#### Linux
- **XDG Base Directory Specification:** https://specifications.freedesktop.org/basedir-spec/basedir-spec-latest.html
- **Desktop Entry Specification:** https://specifications.freedesktop.org/desktop-entry-spec/

### Standards and Best Practices

#### Python
- **PEP 8:** Style Guide for Python Code
- **PEP 484:** Type Hints
- **PEP 518:** pyproject.toml
- **PEP 621:** Project metadata in pyproject.toml

#### Accessibility
- **WCAG 2.1:** Web Content Accessibility Guidelines
- **Qt Accessibility:** https://doc.qt.io/qt-6/accessible.html

#### Packaging
- **PyInstaller Hooks:** https://github.com/pyinstaller/pyinstaller-hooks-contrib
- **Linux Packaging:** https://www.debian.org/doc/debian-policy/ch-binary.html

### Security Considerations

#### Plugin Security
- **Opt-in Only:** Plugins must be enabled by user
- **Trusted Code:** Python plugins have full user account access
- **No Sandboxing:** Plugins run with same privileges as application
- **User Education:** Plugin folder location shown in settings

#### Update Security
- **Read-only:** Never downloads or replaces files
- **Verified Sources:** Release sources hardcoded in application
- **Manual Installation:** User reviews and installs updates
- **No Silent Updates:** Always requires user action

#### Data Privacy
- **Local Processing:** All processing done locally
- **No Cloud APIs:** No network calls during operation
- **No Telemetry:** No usage data collection
- **Privacy-Safe Diagnostics:** Excludes document content

### Performance Optimization

#### PDF Loading
- **Background Thread:** Loading in separate thread to avoid UI freeze
- **OCR Caching:** OCR results cached per page
- **Progress Reporting:** Real-time progress updates
- **Cancellation:** User can cancel long loads

#### Speech Engine
- **Fresh Engine per Utterance:** Avoids stale state
- **Thread Safety:** Each utterance in own thread
- **No Blocking:** stop() never blocks GUI
- **Error Detection:** Detects failed speech quickly

#### GUI
- **Thumbnail Caching:** Page thumbnails cached
- **Preview Caching:** Page previews cached
- **Lazy Loading:** Thumbnails generated on demand
- **Efficient Rendering:** Only render visible area

### Known Limitations

#### AppImage
- **Status:** Not fully implemented
- **Issue:** Requires appimagetool integration
- **Workaround:** Use tarball or deb package

#### Linux Dependencies
- **Issue:** Tarball requires manual dependency installation
- **Required:** espeak-ng, libegl1, libxkbcommon0, libxcb-cursor0
- **Solution:** Use deb package for automatic dependency installation

#### OCR Performance
- **Issue:** OCR can be slow on large scanned PDFs
- **Mitigation:** OCR caching per page
- **User Control:** Can disable OCR if not needed

#### Speech Engine Limitations
- **Windows:** Limited to installed SAPI5 voices
- **Linux:** Requires espeak-ng installation
- **Quality:** Depends on system voice quality
- **Latency:** Small delay before speech starts

#### Two-Column Detection
- **Issue:** Complex layouts may not be detected correctly
- **Heuristic:** Uses gap detection between columns
- **Edge Cases:** Asymmetric margins may cause issues

### Future Enhancements

#### Potential Features
- **AppImage Builds:** Complete AppImage support
- **Cross-Compilation:** Linux builds from Windows (with Docker)
- **More OCR Languages:** Better language support
- **Custom Writing Profiles:** User-defined character sets
- **Voice Training:** Custom voice synthesis
- **Export Features:** Export dictation to audio
- **Cloud Sync:** Sync progress across devices (opt-in)
- **Mobile Version:** Android/iOS port

#### Technical Improvements
- **Better Column Detection:** Machine learning-based layout analysis
- **Faster OCR:** GPU-accelerated OCR
- **Better Speech:** Neural TTS engines
- **Smaller Executable:** Reduce bundle size
- **Faster Startup:** Optimize import times
- **Better Caching:** More aggressive caching strategies

---

## Appendix

### Version History

#### Version 0.1.0
- Initial release
- Core dictation functionality
- PDF extraction with OCR
- Basic GUI
- Settings persistence
- Session management
- Plugin system
- Update checker
- Windows and Linux builds

### License Summary

#### PDF Dictation Source-Available Non-Commercial License

**Key Points:**
- Source code: Study, modify, share for non-commercial use
- Packaged executables: No reverse engineering, decompiling, or modification
- Commercial use: Prohibited
- Attribution: Required
- Repository: Official source for studying the program

**For Users:**
- Download executable from GitHub releases
- Use for personal, educational, research purposes
- Do not reverse engineer or decompile
- For source code, visit the repository

**For Developers:**
- Study source code from repository
- Modify for non-commercial purposes
- Share modifications with same license
- Do not redistribute modified executables

### Contact and Support

#### Author
- **Name:** Shaikh Mhammad Ammar
- **Repository:** https://github.com/Ammar1042005/pdf_dictation

#### Support
- **Issues:** https://github.com/Ammar1042005/pdf_dictation/issues
- **Documentation:** This file and README.md
- **License:** LICENSE file in project root

### Acknowledgments

#### Third-Party Libraries
- PySide6 (Qt for Python)
- PyMuPDF (PDF processing)
- pyttsx3 (Text-to-speech)
- PyInstaller (Packaging)
- Tesseract (OCR)
- espeak-ng (Linux TTS)

#### Development Tools
- pytest (Testing)
- ruff (Linting)
- pyright (Type checking)
- GitHub Actions (CI/CD)

---

**Document Version:** 1.0  
**Last Updated:** 2026-10-29  
**Status:** Complete
