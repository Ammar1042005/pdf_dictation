# ROLE AND TASK

You are a senior Python / PySide6 engineer joining an existing open-source project called **PDF Dictation**. Below is a complete description of what it does, how it is built, the invariants that must never break, and what is unfinished. Read all of it before writing code. After it, I will give you a **change request** (at the very end). Implement it without breaking the existing behaviour, and follow the working rules in section 12.

If I have not attached the source files, ask me to paste the files you need (list exact filenames) before you edit anything. Never invent code for files you have not seen.

---

# 1. WHAT THE PROJECT IS

A desktop app (Windows 10/11 and Linux) that helps a person **copy a PDF textbook into a physical notebook by hand**, without looking at the screen. It is NOT a normal "read aloud" tool. It is a *controlled dictation system*:

1. Extract text from a PDF (OCR if the PDF is scanned).
2. Split it into small chunks using a custom **word-unit** algorithm (about 3 units per chunk).
3. Speak ONE chunk aloud with offline TTS.
4. Compute how long a human needs to handwrite that chunk (**characters x seconds-per-character**).
5. Stay silent for exactly that time (timer starts only AFTER the speech finishes).
6. Speak the next chunk automatically.
7. Automatically **pause when a figure/image is reached**, until the user presses Space.
8. Everything is operable from the keyboard.

Primary design goal: *a person can write in a paper notebook for an hour without touching the computer.* When requirements conflict, favour that goal. Priority order: reliable timing > correct chunking > image pauses > keyboard operation > progress persistence > accurate reading order > clean UI > viewer features.

The app is offline-first: no PDF content is ever sent anywhere.

The project must stay **packageable** (PyInstaller exe for Windows, .deb/tarball for Linux). Packaging is an after-development step, but do not make changes that would break it (see section 10).

---

# 2. TECH STACK

- Python 3.11+
- PySide6 (GUI, QTimer, QThread)
- PyMuPDF (`import fitz`) for text blocks, image boxes, page rendering, OCR bridge
- pyttsx3 for offline TTS (SAPI5 on Windows, espeak-ng on Linux)
- Tesseract (external program, optional) for OCR via PyMuPDF's `get_textpage_ocr`
- pytest for tests
- No other runtime dependencies. Keep it that way unless there is a strong reason.

---

# 3. PROJECT LAYOUT

```
pdf_dictation/                  <- repo root
├── app.py                      thin launcher (used by PyInstaller): from pdf_dictation.gui import main
├── pyproject.toml              deps, gui-script "pdfdictation", dynamic version
├── README.md
├── pdf_dictation/              <- the Python package
│   ├── __init__.py             __version__
│   ├── __main__.py             python -m pdf_dictation
│   ├── gui.py                  Win (main window), Loader (QThread), main()
│   ├── settings_dialog.py      SettingsDialog (QDialog)
│   ├── settings.py             load()/save() of the Settings dataclass as JSON
│   ├── controller.py           State enum, Settings dataclass, Controller (state machine)  <- Qt-free
│   ├── chunker.py              Chunk, ImageItem, WordRules, word_weight, char_count, writing_time, TextChunker  <- Qt-free
│   ├── extractor.py            PDF -> ordered list of Chunk/ImageItem; reading order; OCR decision
│   ├── ocr.py                  tessdata(), available(), ocr_blocks()
│   ├── speech.py               SpeechEngine (pyttsx3 in worker threads)
│   ├── textprep.py             prepare_speech(): spoken-form text (punctuation names, "3.2" -> "3 point 2")
│   ├── sessions.py             progress save/load keyed by SHA-256 of the PDF
│   └── paths.py                per-OS data dir, log file, bundled-resource lookup
├── tests/test_core.py          pytest suite (no Qt, no PDF, no TTS needed)
├── packaging/                  pdfdictation.spec, build_linux.sh, installer.iss, pdfdictation.desktop
└── .github/workflows/release.yml   CI: tests + builds on windows-latest and ubuntu-22.04
```

Note: the original idea was subfolders (`pdf/`, `dictation/`, `speech/`, `ui/`); the real code uses a flat package. Keep to what exists unless I ask for a reorganisation.

---

# 4. THE CORE ALGORITHMS (DO NOT CHANGE SEMANTICS WITHOUT ASKING)

## 4.1 Word weight (`chunker.word_weight`)
- Count the alphabetic characters in the token (`letters`). If it has none (e.g. `2025`), count its alphanumeric characters instead.
- 0 -> weight 0.0 (lone punctuation, attaches to the current chunk for free).
- 1..`short_max` (default 3) letters -> `short_weight` (default **0.5**).
- more than `short_max` letters -> `long_weight` (default **1.0**).
- Punctuation never increases length: `cell,` `(cell)` `book.` all count 4 letters -> 1.0. `DNA` -> 0.5, `H2O` -> 2 letters -> 0.5, `2025` -> 1.0.

## 4.2 Chunking (`TextChunker.create_chunks(text, page_number)`)
- Text is split into **paragraphs** with `re.finditer(r"\S(?:.|\n(?!\s*\n))*", text)` (NO `re.S` flag; a blank line ends a paragraph). Chunks never span paragraphs.
- Inside a paragraph, tokens are `\S+`. Add tokens one by one, accumulating units.
- **Close the chunk** when `units >= target` (default 3.0) OR (`units >= sentence_min` (default 1.5) AND the token ends with one of `. ? ! ; :`).
- Words are never split. A chunk may exceed 3 (e.g. 3.5). Examples: "The cell membrane controls" = 0.5+1+1+1 = 3.5; "I am studying mitochondria" = 3.0.
- A trailing remainder with `units < 1.0` is merged back into the previous chunk of the same paragraph (avoids absurdly tiny chunks).
- Each `Chunk` stores: `text, words, word_units, character_count, page_number, start_position, end_position, bbox` (bbox = rectangle of the source text block on the page; set by the extractor; used for highlighting).

## 4.3 Writing time (`chunker.char_count`, `chunker.writing_time`)
- `char_count` = number of **alphanumeric** characters. Spaces and punctuation are NOT counted (so "The cell is large." = 14).
- `writing_time = chars * seconds_per_char + extra_pause`. Defaults: 0.75 s/char, 0 s extra. Example: 23 chars -> 17.25 s. Never add hidden time.

## 4.4 Speech text vs timing text
`textprep.prepare_speech(text, speak_punctuation, normalize)` only changes what is SPOKEN (e.g. "Fig." -> "Figure", "3.2" -> "3 point 2", optionally ", comma,"). It must never affect `character_count` or timing.

---

# 5. DICTATION STATE MACHINE (`controller.py`)

`Controller(items, speech, settings, clock=time.monotonic, on_change=callback)` is **pure Python, Qt-free, and fully testable** with a fake speech engine and a fake clock. The GUI calls `controller.tick()` every 100 ms (QTimer). Never use `sleep()`.

`items` is a flat ordered list of `Chunk` and `ImageItem` objects (`ImageItem(page_number, bbox)`).

States: `IDLE` (no items), `READY`, `SPEAKING`, `WRITING`, `PAUSED`, `IMAGE_PAUSED`, `FINISHED`, `ERROR` (reserved).

Transitions:
- `_enter()`: if current item is an `ImageItem` and `pause_at_images` -> `IMAGE_PAUSED`; if images are disabled it skips them. If it is a `Chunk` -> compute `remaining = writing_time(...)`, call `speech.speak(prepare_speech(...))`, state `SPEAKING`. Past the end -> `FINISHED`.
- `tick()`: `SPEAKING` and `not speech.is_speaking()` -> `deadline = clock() + remaining`, state `WRITING` (**the timer starts only after speech ends**). `WRITING` and `clock() >= deadline` -> `index += 1`, `_enter()`.
- `toggle()` (Space): `READY` -> start; `SPEAKING` -> stop speech, `PAUSED` (remembers it came from SPEAKING); `WRITING` -> freeze `remaining`, `PAUSED`; `PAUSED` -> if it came from WRITING, resume the remaining time, else re-speak the chunk; `IMAGE_PAUSED` -> `index += 1`, `_enter()`.
- `repeat()` (R): stop speech, re-enter current chunk (re-speak, then FULL timer again, do not advance). Ignored on images.
- `next()` / `prev()` (arrows): stop speech, move one item, land in `PAUSED` (never auto-speaks, to avoid accidental skipping). Pressing Space then plays the item (or IMAGE_PAUSED if it is an image).
- `stop()` (Esc): stop speech, state `READY` (position kept).

`Settings` (dataclass in controller.py, shared by controller, GUI, dialog and settings.py) fields and defaults:
`seconds_per_char=0.75, extra_pause=0.0, pause_at_images=True, speak_punctuation=False, normalize=True, target=3.0, short_weight=0.5, long_weight=1.0, short_max=3, min_img_w=100, min_img_h=100, voice_id="", rate=150, volume=1.0, ocr_mode="auto", ocr_language="eng"`; method `word_rules()` builds a `WordRules`.

**Settings object identity matters:** the GUI updates the one `Settings` instance *in place* (`setattr` loop) so the live controller sees changes immediately. Do not replace the object.

---

# 6. PDF EXTRACTION (`extractor.load_items`)

`load_items(path, min_w, min_h, chunker, ocr_mode, ocr_lang, progress) -> Loaded(items, pages, ocr_pages)`.
Per page:
1. `page.get_text("blocks")` -> text blocks with coordinates (type 0 only).
2. If the page has fewer than 20 text characters (`needs_ocr`) and `ocr_mode == "auto"`: if Tesseract is available, OCR the page (`ocr.ocr_blocks`, 200 dpi) and mark it scanned; otherwise count it as skipped.
3. `page.get_image_info()` -> image bounding boxes. Drop images smaller than `min_w` x `min_h` (PDF points, not screen pixels) to ignore icons/bullets/logos. On OCR'd pages also drop an image covering >= 85 % of the page (that is the scan itself, not a figure).
4. `reading_order(entries, page_width)`: full-width entries (>= 60 % of page width) act as separators; between them, entries are ordered **left column top->bottom, then right column top->bottom**, split by whether the block's centre is left/right of the page midpoint. Images are ordered with text, so an image appears at its true position among the text.
5. Text blocks: `-\n` is joined (de-hyphenation), `\n` -> space, then chunked; each chunk gets `bbox` = block rectangle.
6. `progress(page_no, total)` is called before each page (outside the per-page try/except) and may raise `PdfError` to cancel.
Errors raised as `PdfError`: cannot open, password-protected, no text at all (message differs if OCR was needed but unavailable). A failing page is logged and skipped, never crashes the load.

`gui.Loader` (QThread) runs `load_items` off the GUI thread, emits `progress/done/failed`; Cancel uses `requestInterruption`.

---

# 7. SPEECH (`speech.py`)

`SpeechEngine(rate, volume, voice_id)` with `speak, stop, pause, resume, is_speaking, voices`.
- Each `speak()` starts a daemon thread that creates a fresh `pyttsx3` engine and calls `runAndWait()` (so the GUI never blocks).
- `_speaking` is set True **before** the thread starts (prevents a race where `tick()` thinks speech already finished).
- A generation counter (`_gen`) makes stale threads harmless after `stop()`.
- Pause is emulated: `pause()` = `stop()`, and the controller re-speaks the chunk on resume.
- Known risk: on Windows, pyttsx3/SAPI5 in a non-main thread may need `pythoncom.CoInitialize()`; if TTS is silent on Windows, check this first. On Linux `espeak-ng` must be installed.

---

# 8. GUI (`gui.py`, `settings_dialog.py`)

- Main window `Win`: "Open PDF…" and "Settings…" buttons, spinners for seconds-per-character and extra pause, page preview label, large coloured status label (colour AND text, never colour alone), current-chunk text, info line (`Page x / N  Item i / M  Writing time`), progress bar for the writing countdown.
- Keyboard (Qt `ApplicationShortcut`, so it works when the viewer lacks focus): **Space** pause/resume/continue, **R** repeat, **Left/Right** previous/next, **Esc** stop.
- There is currently **no on-screen Start/Pause button**; Space starts dictation after a PDF is opened.
- Preview: renders the current page with PyMuPDF at zoom 1.2, highlights the current chunk (yellow; exact words via `page.search_for`, filtered to the block, falling back to the whole block `bbox`), or outlines the image in red when paused at an image.
- `refresh()` runs on every state change and saves progress.
- On open: asks "Resume from previous position?" if a session exists for that exact file.
- Settings dialog: all fields in section 5; "Test Voice" button; note that chunk/image/OCR changes apply the next time a PDF is opened (changing chunking mid-document would shift chunk indices and lose the user's place).

---

# 9. PERSISTENCE AND PATHS

- `paths.data_dir()`: `%APPDATA%\PDFDictation` (Windows) or `$XDG_DATA_HOME` / `~/.local/share/PDFDictation` (Linux). Holds `settings.json`, `sessions/<sha256>.json`, `pdf_dictation.log`. Never write next to the program.
- Session file: `{"pdf_hash", "chunk_index", "settings"}`. `sessions.load` returns None if the stored hash does not match the file, so progress can never apply to a different PDF.
- Logging: metadata only (page numbers, counts, errors), never document text.

---

# 10. PACKAGING CONSTRAINTS (so future changes don't break builds)

- Entry point is `app.py` -> `pdf_dictation.gui.main`. Keep `main()` importable.
- Use `paths.resource()` for any bundled data file (works under PyInstaller's `sys._MEIPASS`).
- If you add a dynamically-imported module or a data file, add it to `hiddenimports`/`datas` in `packaging/pdfdictation.spec`.
- Any new dependency must be added to `pyproject.toml`, work on Windows and Linux, and ideally run offline.
- Builds must run on the target OS (no cross-compiling); CI does this on tag push.

---

# 11. TESTS (`tests/test_core.py`) AND HOW TO RUN

Run: `pip install -e ".[dev]"` then `pytest -q`. The 22 current tests need no Qt/PDF/TTS: word weights (incl. punctuation cases), timing example (14 chars -> 10.5 s), chunk examples (3.5 units/23 chars/17.25 s; 3.0 units), no word splitting, paragraph separation, sentence boundary, controller (timer starts after speech; image pause; pause freeze; repeat), reading order (two columns), image size filter, session save/load/hash mismatch, text prep, settings round-trip, OCR helpers.
Not yet covered: image detection against real sample PDFs (needs PyMuPDF), GUI, real TTS, real OCR.
**Every behavioural change must come with a test**, and the whole suite must pass.

---

# 12. INVARIANTS (NEVER VIOLATE)

1. Never read the PDF continuously; one chunk = one utterance, then silence.
2. The writing timer starts only after speech finishes.
3. Never use `time.sleep()` or any blocking call on the GUI thread; use QTimer/QThread.
4. Use a monotonic clock for timing.
5. Never split a word across chunks; never merge paragraphs to hit a target.
6. Do not count spaces or punctuation in writing time (unless a deliberate, documented setting changes this).
7. Do not add hidden extra time.
8. Do not pause merely because a page contains an image; pause at the image's *position* in reading order, and ignore tiny images.
9. Never lose the user's position; never apply progress to a different PDF.
10. Never send document content over the network; any online feature must be optional and off by default.
11. Keep `chunker.py` and `controller.py` free of Qt imports.
12. Never crash on bad input: show a clear message instead (corrupt, encrypted, empty, scanned without OCR, TTS missing).

# 13. WORKING RULES FOR YOU (THE AI)

- Make the smallest change that fully solves the request; do not refactor unrelated code.
- Give me **complete updated files** (not fragments) for every file you change, with the filename above each code block, plus any new files. If a change is tiny, a precise find/replace diff is acceptable.
- Add or update tests; tell me the exact command to run them.
- If the request conflicts with an invariant in section 12, say so and propose the closest compliant alternative before coding.
- State assumptions briefly; ask at most one clarifying question, and only if truly blocked.
- Keep Windows AND Linux working; mention any OS-specific behaviour.
- End with: what changed, how to test it manually, and any new limitations.

---

# 14. KNOWN LIMITATIONS / UNFINISHED (candidate improvements)

- No on-screen Start/Pause/Repeat/Previous/Next buttons; no page navigation or zoom controls in the viewer; the image is outlined but the view does not zoom to it.
- Shortcuts are application-level only (not OS-global) and are not configurable; `F` (restart chunk) and `+`/`-` (speech rate) are not implemented.
- No audible state announcements (e.g. "image detected" beep).
- Vector diagrams/charts drawn as paths are not detected (only embedded raster images).
- Two-column detection is a simple midpoint heuristic; unusual layouts, sidebars or tables may be misordered; captions are treated as plain text.
- OCR results are not cached (re-OCR on every open); OCR language is a single code.
- Chunks that cross a page boundary are not merged (each text block is chunked separately).
- Number/abbreviation normalisation is minimal.
- No tests with real PDFs; GUI and TTS untested in CI.
- Packaging files exist but have not been exercised end-to-end; no app icon, no LICENSE, placeholder maintainer email in `build_linux.sh`; no macOS or AppImage build.

# 15. COMMON CUSTOMISATION RECIPES (where to edit)

- Change word weights, target size or short-word limit: Settings dialog, or defaults in `controller.Settings` / `chunker.WordRules`.
- Different writing speed model (e.g. per-word instead of per-character): `chunker.writing_time` and `char_count` (+ tests).
- New chunk-boundary rules: `TextChunker._para` in `chunker.py`.
- New image rules (e.g. also pause at charts, relative size thresholds, vector figures): `extractor.load_items` / `keep_image`.
- Different reading order or column logic: `extractor.reading_order`.
- New TTS backend (Piper, Coqui, cloud-optional): implement the same interface as `SpeechEngine` (`speak, stop, pause, resume, is_speaking, voices`) and pass it to `Controller`; keep `is_speaking()` true from the moment `speak()` returns until playback ends.
- New keyboard shortcut: add to the shortcut tuple in `Win.__init__` and a method on `Controller`.
- New setting: add a field to `controller.Settings` (with a default), a widget + `result_settings` entry in `settings_dialog.py`, and use it where needed; `settings.load` already ignores unknown/old keys.
- New language/OCR: Settings -> OCR language (Tesseract code, e.g. `hin`, `guj`), plus the matching Tesseract language data installed; TTS voice must also support the language.
- UI translation or theme: `gui.py` strings and style sheets.

---

# 16. COMPLETE CURRENT SOURCE CODE

These are the exact current files. Treat them as the source of truth if they differ from the prose above.

## FILE: pyproject.toml

````toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "pdf-dictation"
dynamic = ["version"]
description = "Controlled PDF dictation for copying textbooks by hand"
readme = "README.md"
requires-python = ">=3.11"
dependencies = ["PySide6>=6.6", "PyMuPDF>=1.24", "pyttsx3>=2.90"]

[project.optional-dependencies]
dev = ["pytest"]
build = ["pyinstaller>=6.6"]

[project.gui-scripts]
pdfdictation = "pdf_dictation.gui:main"

[tool.setuptools.dynamic]
version = { attr = "pdf_dictation.__version__" }

[tool.setuptools.packages.find]
include = ["pdf_dictation*"]
````

## FILE: app.py

````python
from pdf_dictation.gui import main

if __name__ == "__main__":
    main()
````

## FILE: pdf_dictation/__init__.py

````python
__version__ = "0.1.0"
````

## FILE: pdf_dictation/__main__.py

````python
from pdf_dictation.gui import main
main()
````

## FILE: pdf_dictation/paths.py

````python
"""Per-OS user data locations and bundled-resource lookup (works frozen or from source)."""
import os, sys
from pathlib import Path

APP = "PDFDictation"


def data_dir():
    if sys.platform == "win32": base = Path(os.environ.get("APPDATA", Path.home() / "AppData/Roaming"))
    elif sys.platform == "darwin": base = Path.home() / "Library/Application Support"
    else: base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
    d = base / APP; d.mkdir(parents=True, exist_ok=True); return d


def log_file(): return data_dir() / "pdf_dictation.log"
def resource(rel): return Path(getattr(sys, "_MEIPASS", Path(__file__).parent)) / rel
````

## FILE: pdf_dictation/chunker.py

````python
"""Deterministic word-unit chunking and writing-time calculation."""
import re
from dataclasses import dataclass


@dataclass
class Chunk:
    text: str
    words: list
    word_units: float
    character_count: int
    page_number: int
    start_position: int = 0
    end_position: int = 0
    bbox: tuple = None   # block rectangle on the page (for highlighting)


@dataclass
class ImageItem:
    page_number: int
    bbox: tuple


@dataclass
class WordRules:
    short_weight: float = 0.5
    long_weight: float = 1.0
    short_max: int = 3          # 1..short_max letters => short_weight
    target: float = 3.0
    sentence_min: float = 1.5   # close early at . ? ! ; : if at least this many units


def letters(tok): return sum(c.isalpha() for c in tok)
def char_count(text): return sum(c.isalnum() for c in text)  # no spaces/punctuation


def word_weight(tok, r=WordRules()):
    n = letters(tok) or char_count(tok)   # pure numbers: count digits
    if n == 0:
        return 0.0                         # lone punctuation
    return r.short_weight if n <= r.short_max else r.long_weight


def writing_time(chars, seconds_per_char=0.75, extra_pause=0.0):
    return chars * seconds_per_char + extra_pause


class TextChunker:
    def __init__(self, rules=None):
        self.rules = rules or WordRules()

    def create_chunks(self, text, page_number=1):
        out = []
        for para in re.finditer(r"\S(?:.|\n(?!\s*\n))*", text):
            out.extend(self._para(para.group(), para.start(), page_number))
        return out

    def _para(self, para, base, page):
        r, chunks, cur, units = self.rules, [], [], 0.0

        def flush():
            nonlocal cur, units
            if not cur:
                return
            ws = [m.group() for m in cur]
            c = Chunk(" ".join(ws), ws, units, sum(char_count(w) for w in ws), page,
                      base + cur[0].start(), base + cur[-1].end())
            if chunks and units < 1.0:   # avoid tiny trailing chunk: merge back
                p = chunks[-1]
                p.words += ws; p.text = " ".join(p.words); p.word_units += units
                p.character_count += c.character_count; p.end_position = c.end_position
            else:
                chunks.append(c)
            cur, units = [], 0.0

        for m in re.finditer(r"\S+", para):
            cur.append(m)
            units += word_weight(m.group(), r)
            if units >= r.target or (units >= r.sentence_min and m.group()[-1] in ".?!;:"):
                flush()
        flush()
        return chunks
````

## FILE: pdf_dictation/controller.py

````python
"""Qt-free dictation state machine. Drive it by calling tick() every ~100 ms."""
import time
from enum import Enum
from dataclasses import dataclass
from .chunker import ImageItem, WordRules, writing_time
from .textprep import prepare_speech


class State(Enum):
    IDLE = "IDLE"; READY = "READY"; SPEAKING = "SPEAKING"; WRITING = "WRITING"
    PAUSED = "PAUSED"; IMAGE_PAUSED = "IMAGE_PAUSED"; FINISHED = "FINISHED"; ERROR = "ERROR"


@dataclass
class Settings:
    seconds_per_char: float = 0.75
    extra_pause: float = 0.0
    pause_at_images: bool = True
    speak_punctuation: bool = False
    normalize: bool = True
    target: float = 3.0
    short_weight: float = 0.5
    long_weight: float = 1.0
    short_max: int = 3
    min_img_w: int = 100
    min_img_h: int = 100
    voice_id: str = ""
    rate: int = 150
    volume: float = 1.0
    ocr_mode: str = "auto"      # "auto" | "off"
    ocr_language: str = "eng"

    def word_rules(self):
        return WordRules(self.short_weight, self.long_weight, self.short_max, self.target)


class Controller:
    def __init__(self, items, speech, settings=None, clock=time.monotonic, on_change=None):
        self.items, self.speech = items, speech
        self.s = settings or Settings()
        self.clock, self.on_change = clock, on_change or (lambda: None)
        self.index, self.state = 0, State.READY if items else State.IDLE
        self.remaining, self.deadline, self._paused_from = 0.0, 0.0, None

    @property
    def item(self): return self.items[self.index] if self.index < len(self.items) else None

    def time_left(self):
        if self.state == State.WRITING: return max(0.0, self.deadline - self.clock())
        return self.remaining

    def _set(self, st): self.state = st; self.on_change()

    def _enter(self):
        it = self.item
        if it is None: return self._set(State.FINISHED)
        if isinstance(it, ImageItem):
            if self.s.pause_at_images: return self._set(State.IMAGE_PAUSED)
            self.index += 1; return self._enter()
        self.remaining = writing_time(it.character_count, self.s.seconds_per_char, self.s.extra_pause)
        self.speech.speak(prepare_speech(it.text, self.s.speak_punctuation, self.s.normalize))
        self._set(State.SPEAKING)

    def tick(self):
        if self.state == State.SPEAKING and not self.speech.is_speaking():
            self.deadline = self.clock() + self.remaining; self._set(State.WRITING)  # timer starts AFTER speech
        elif self.state == State.WRITING and self.clock() >= self.deadline:
            self.index += 1; self.remaining = 0.0; self._enter()

    def start(self):
        if self.state in (State.READY, State.PAUSED): self._enter()

    def toggle(self):
        st = self.state
        if st == State.IMAGE_PAUSED: self.index += 1; self._enter()
        elif st == State.SPEAKING: self.speech.stop(); self._paused_from = st; self._set(State.PAUSED)
        elif st == State.WRITING:
            self.remaining = max(0.0, self.deadline - self.clock())
            self._paused_from = st; self._set(State.PAUSED)
        elif st == State.PAUSED:
            if self._paused_from == State.WRITING:
                self.deadline = self.clock() + self.remaining; self._set(State.WRITING)
            else: self._enter()
            self._paused_from = None
        elif st == State.READY: self.start()

    def repeat(self):
        if isinstance(self.item, ImageItem) or self.item is None: return
        self.speech.stop(); self._enter()   # re-speak, then full timer again

    def _move(self, d):
        n = self.index + d
        if 0 <= n < len(self.items):
            self.speech.stop(); self.index = n; self.remaining = 0.0
            self._paused_from = None; self._set(State.PAUSED)  # waits for user to resume

    def next(self): self._move(1)
    def prev(self): self._move(-1)

    def stop(self):
        self.speech.stop(); self._set(State.READY)
````

## FILE: pdf_dictation/textprep.py

````python
"""Speech-friendly text preparation (optional; never changes what counts for timing)."""
import re

NAMES = {",": "comma", ".": "period", ";": "semicolon", ":": "colon", "?": "question mark", "!": "exclamation mark"}


def prepare_speech(text, speak_punctuation=False, normalize=True):
    if normalize:
        text = re.sub(r"\bFig\.", "Figure", text)
        text = re.sub(r"\be\.g\.", "for example", text)
        text = re.sub(r"\bi\.e\.", "that is", text)
        text = re.sub(r"(?<=\d)\.(?=\d)", " point ", text)   # 3.2 -> 3 point 2
    if speak_punctuation:
        text = re.sub(r"([,.;:?!])", lambda m: f", {NAMES[m.group(1)]},", text)
    return text
````

## FILE: pdf_dictation/settings.py

````python
import json, logging
from dataclasses import asdict
from pdf_dictation import paths
from pdf_dictation.controller import Settings


def _file(): return paths.data_dir() / "settings.json"


def load(path=None):
    s = Settings()
    try:
        for k, v in json.loads((path or _file()).read_text()).items():
            if hasattr(s, k): setattr(s, k, type(getattr(s, k))(v))   # ignore unknown/old keys
    except FileNotFoundError: pass
    except Exception as e: logging.getLogger("pdf_dictation").error("settings load failed: %s", e)
    return s


def save(s, path=None):
    try: (path or _file()).write_text(json.dumps(asdict(s), indent=2))
    except Exception as e: logging.getLogger("pdf_dictation").error("settings save failed: %s", e)
````

## FILE: pdf_dictation/sessions.py

````python
import hashlib, json, logging
from pathlib import Path
from pdf_dictation import paths
log = logging.getLogger("pdf_dictation")
DIR = paths.data_dir() / "sessions"


def pdf_hash(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""): h.update(b)
    return h.hexdigest()


def save(path, index, settings: dict, directory=DIR):
    try:
        directory.mkdir(parents=True, exist_ok=True); h = pdf_hash(path)
        (directory / f"{h}.json").write_text(json.dumps({"pdf_hash": h, "chunk_index": index, "settings": settings}))
    except Exception as e: log.error("session save failed: %s", e)


def load(path, directory=DIR):
    try:
        h = pdf_hash(path); d = json.loads((directory / f"{h}.json").read_text())
        return d if d.get("pdf_hash") == h else None
    except Exception: return None
````

## FILE: pdf_dictation/speech.py

````python
"""Non-blocking offline TTS (pyttsx3). Pause is emulated: stop, then re-speak."""
import threading, logging


class SpeechEngine:
    def __init__(self, rate=150, volume=1.0, voice_id=None):
        self.rate, self.volume, self.voice_id = rate, volume, voice_id
        self._speaking, self._engine, self._gen = False, None, 0

    def voices(self):
        try:
            import pyttsx3
            return [(v.id, v.name) for v in pyttsx3.init().getProperty("voices")]
        except Exception: return []

    def speak(self, text):
        self.stop()
        self._gen += 1; gen = self._gen
        self._speaking = True          # set before thread start: no race with tick()
        threading.Thread(target=self._run, args=(text, gen), daemon=True).start()

    def _run(self, text, gen):
        try:
            import pyttsx3
            e = pyttsx3.init(); self._engine = e
            e.setProperty("rate", self.rate); e.setProperty("volume", self.volume)
            if self.voice_id: e.setProperty("voice", self.voice_id)
            e.say(text); e.runAndWait()
        except Exception as ex:
            logging.getLogger("pdf_dictation").error("TTS error: %s", ex)
        finally:
            if gen == self._gen: self._speaking = False

    def stop(self):
        self._gen += 1; self._speaking = False
        try:
            if self._engine: self._engine.stop()
        except Exception: pass

    def pause(self): self.stop()
    def resume(self): pass   # controller re-speaks the chunk
    def is_speaking(self): return self._speaking
````

## FILE: pdf_dictation/ocr.py

````python
"""Offline OCR via PyMuPDF's built-in Tesseract bridge (needs the Tesseract program + language data installed)."""


def tessdata():
    try:
        import fitz
        return fitz.get_tessdata()
    except Exception:
        return None


def available(): return tessdata() is not None


def ocr_blocks(page, lang="eng", dpi=200):
    tp = page.get_textpage_ocr(language=lang, dpi=dpi, full=True, tessdata=tessdata())
    return [(tuple(b[:4]), b[4]) for b in page.get_text("blocks", textpage=tp) if b[6] == 0 and b[4].strip()]
````

## FILE: pdf_dictation/extractor.py

````python
"""PDF -> ordered sequence of Chunk / ImageItem (position-aware, with automatic OCR for scanned pages)."""
import logging
from dataclasses import dataclass
from . import ocr
from .chunker import TextChunker, ImageItem

log = logging.getLogger("pdf_dictation")
OCR_HELP = ("This looks like a scanned PDF but OCR is unavailable. Install Tesseract "
            "(Windows: github.com/UB-Mannheim/tesseract, Linux: sudo apt install tesseract-ocr) "
            "and restart; set TESSDATA_PREFIX if it is still not found.")


class PdfError(Exception): pass


@dataclass
class Entry:
    rect: tuple
    kind: str      # "text" | "image"
    payload: object


@dataclass
class Loaded:
    items: list
    pages: int
    ocr_pages: int = 0


def reading_order(entries, page_w):
    """Full-width entries split the page into bands; inside a band: left column, then right."""
    key_y = lambda e: (e.rect[1], e.rect[0])
    out, band = [], []

    def flush():
        L = [e for e in band if (e.rect[0] + e.rect[2]) / 2 < page_w / 2]
        R = [e for e in band if e not in L]
        out.extend(sorted(L, key=key_y) + sorted(R, key=key_y)); band.clear()

    for e in sorted(entries, key=key_y):
        if e.rect[2] - e.rect[0] >= 0.6 * page_w: flush(); out.append(e)
        else: band.append(e)
    flush()
    return out


def keep_image(rect, min_w, min_h): return (rect[2] - rect[0]) >= min_w and (rect[3] - rect[1]) >= min_h
def needs_ocr(blocks): return sum(len(t.strip()) for _, t in blocks) < 20


def is_page_scan(rect, page_rect, frac=0.85):
    """True if an image covers most of the page, i.e. it IS the scan, not a figure."""
    a = max(0, rect[2] - rect[0]) * max(0, rect[3] - rect[1])
    return a >= frac * (page_rect[2] - page_rect[0]) * (page_rect[3] - page_rect[1])


def load_items(path, min_w=100, min_h=100, chunker=None, ocr_mode="auto", ocr_lang="eng", progress=None):
    try:
        import fitz
        doc = fitz.open(path)
    except Exception as e: raise PdfError(f"Cannot open PDF: {e}")
    if doc.needs_pass: raise PdfError("PDF is password-protected.")
    chunker, items, n_ocr, skipped = chunker or TextChunker(), [], 0, 0
    ocr_ok = ocr_mode == "auto" and ocr.available()
    for pno, page in enumerate(doc, 1):
        if progress: progress(pno, len(doc))          # may raise PdfError to cancel
        try:
            blocks = [(tuple(b[:4]), b[4]) for b in page.get_text("blocks") if b[6] == 0 and b[4].strip()]
            scanned = False
            if needs_ocr(blocks) and ocr_mode == "auto":
                if ocr_ok:
                    blocks, scanned = ocr.ocr_blocks(page, ocr_lang), True; n_ocr += 1; log.info("OCR p%d", pno)
                else: skipped += 1
            entries = [Entry(r, "text", t) for r, t in blocks]
            for im in page.get_image_info():
                r = tuple(im["bbox"])
                if keep_image(r, min_w, min_h) and not (scanned and is_page_scan(r, tuple(page.rect))):
                    entries.append(Entry(r, "image", ImageItem(pno, r))); log.info("image p%d", pno)
            for e in reading_order(entries, page.rect.width):
                if e.kind == "image": items.append(e.payload)
                else:
                    new = chunker.create_chunks(e.payload.replace("-\n", "").replace("\n", " "), pno)
                    for c in new: c.bbox = e.rect
                    items.extend(new)
        except Exception as ex: log.error("page %d parse failed: %s", pno, ex)
    if not any(not isinstance(i, ImageItem) for i in items):
        raise PdfError(OCR_HELP if skipped else "No extractable text found in this PDF.")
    log.info("loaded %d items from %d pages (%d OCR)", len(items), len(doc), n_ocr)
    return Loaded(items, len(doc), n_ocr)
````

## FILE: pdf_dictation/settings_dialog.py

````python
from dataclasses import replace
from PySide6.QtWidgets import (QDialog, QFormLayout, QDialogButtonBox, QDoubleSpinBox, QSpinBox, QCheckBox,
                               QComboBox, QLineEdit, QPushButton, QLabel, QVBoxLayout)
from pdf_dictation.speech import SpeechEngine


def _dspin(lo, hi, v, step=0.25):
    w = QDoubleSpinBox(); w.setRange(lo, hi); w.setSingleStep(step); w.setDecimals(2); w.setValue(v); return w


class SettingsDialog(QDialog):
    def __init__(self, s, voices, parent=None):
        super().__init__(parent); self.setWindowTitle("Settings"); self.s = s
        f = QFormLayout()
        self.spc = _dspin(0.05, 5, s.seconds_per_char); self.extra = _dspin(0, 30, s.extra_pause, 1)
        self.target = _dspin(1, 10, s.target, 0.5); self.sw = _dspin(0, 5, s.short_weight, 0.25)
        self.lw = _dspin(0, 5, s.long_weight, 0.25)
        self.smax = QSpinBox(); self.smax.setRange(1, 10); self.smax.setValue(s.short_max)
        self.voice = QComboBox(); self.voice.addItem("System default", "")
        for vid, name in voices: self.voice.addItem(name, vid)
        i = self.voice.findData(s.voice_id); self.voice.setCurrentIndex(max(i, 0))
        self.rate = QSpinBox(); self.rate.setRange(60, 350); self.rate.setValue(s.rate)
        self.vol = _dspin(0, 1, s.volume, 0.1)
        test = QPushButton("Test Voice"); test.clicked.connect(self.test_voice)
        self.pimg = QCheckBox("Pause at images"); self.pimg.setChecked(s.pause_at_images)
        self.iw = QSpinBox(); self.iw.setRange(0, 2000); self.iw.setValue(s.min_img_w)
        self.ih = QSpinBox(); self.ih.setRange(0, 2000); self.ih.setValue(s.min_img_h)
        self.punct = QCheckBox("Speak punctuation"); self.punct.setChecked(s.speak_punctuation)
        self.norm = QCheckBox("Normalize abbreviations/numbers"); self.norm.setChecked(s.normalize)
        self.ocr = QComboBox(); self.ocr.addItems(["auto", "off"]); self.ocr.setCurrentText(s.ocr_mode)
        self.ocrlang = QLineEdit(s.ocr_language)
        for lab, w in (("OCR for scanned pages", self.ocr), ("OCR language (e.g. eng, hin)", self.ocrlang),("Target word-units per chunk", self.target), ("Seconds per character", self.spc),
                       ("Extra pause (s)", self.extra), ("Short word weight", self.sw), ("Long word weight", self.lw),
                       ("Short word max letters", self.smax), ("Voice", self.voice), ("Speech rate", self.rate),
                       ("Volume", self.vol), ("", test), ("", self.pimg), ("Min image width", self.iw),
                       ("Min image height", self.ih), ("", self.punct), ("", self.norm)): f.addRow(lab, w)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept); bb.rejected.connect(self.reject)
        note = QLabel("Chunk and image settings apply the next time a PDF is opened."); note.setWordWrap(True)
        lay = QVBoxLayout(self); lay.addLayout(f); lay.addWidget(note); lay.addWidget(bb)

    def result_settings(self):
        return replace(self.s, seconds_per_char=self.spc.value(), extra_pause=self.extra.value(),
                       target=self.target.value(), short_weight=self.sw.value(), long_weight=self.lw.value(),
                       short_max=self.smax.value(), voice_id=self.voice.currentData() or "", rate=self.rate.value(),
                       volume=self.vol.value(), pause_at_images=self.pimg.isChecked(), min_img_w=self.iw.value(),
                       min_img_h=self.ih.value(), speak_punctuation=self.punct.isChecked(),
                       normalize=self.norm.isChecked(), ocr_mode=self.ocr.currentText(),
                       ocr_language=self.ocrlang.text().strip() or "eng")

    def test_voice(self):
        r = self.result_settings()
        self._tmp = SpeechEngine(r.rate, r.volume, r.voice_id or None); self._tmp.speak("This is a test of the selected voice.")
````

## FILE: pdf_dictation/gui.py

````python
import sys, logging
from pathlib import Path
import fitz
from PySide6.QtCore import QTimer, Qt, QThread, QRectF, Signal
from PySide6.QtGui import QShortcut, QKeySequence, QPixmap, QImage, QPainter, QPen, QColor
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QPushButton, QFileDialog, QMessageBox, QDoubleSpinBox, QProgressBar, QProgressDialog)
from pdf_dictation import sessions, settings as cfg
from pdf_dictation.chunker import TextChunker
from pdf_dictation.settings_dialog import SettingsDialog
from pdf_dictation.chunker import ImageItem
from pdf_dictation.controller import Controller, Settings, State
from pdf_dictation.extractor import load_items, PdfError
from pdf_dictation.speech import SpeechEngine

from pdf_dictation import paths
logging.basicConfig(filename=str(paths.log_file()), level=logging.INFO)
COLORS = {State.SPEAKING: "#1e88e5", State.WRITING: "#f9a825", State.IMAGE_PAUSED: "#e53935",
          State.PAUSED: "#757575", State.FINISHED: "#43a047"}
LABELS = {State.SPEAKING: "🔊 SPEAKING", State.WRITING: "✍ WRITING", State.IMAGE_PAUSED:
          "⏸ IMAGE DETECTED — press SPACE to continue", State.PAUSED: "⏸ PAUSED",
          State.FINISHED: "✓ FINISHED", State.READY: "READY", State.IDLE: "OPEN A PDF"}


class Loader(QThread):
    """Reads/OCRs the PDF off the GUI thread."""
    progress = Signal(int, int); done = Signal(object); failed = Signal(str)

    def __init__(self, path, s):
        super().__init__(); self.path, self.s = path, s

    def run(self):
        s = self.s

        def prog(i, n):
            if self.isInterruptionRequested(): raise PdfError("Loading cancelled.")
            self.progress.emit(i, n)
        try:
            self.done.emit(load_items(self.path, s.min_img_w, s.min_img_h, TextChunker(s.word_rules()),
                                      s.ocr_mode, s.ocr_language, prog))
        except PdfError as e: self.failed.emit(str(e))
        except Exception as e: self.failed.emit(f"Unexpected error: {e}")


class Win(QMainWindow):
    def __init__(self):
        super().__init__(); self.setWindowTitle("PDF Dictation"); self.ctl = None; self.path = None; self.doc = None
        self.settings = cfg.load(); self.speech = SpeechEngine(); self.apply_speech(); self.pages = 0
        w = QWidget(); self.setCentralWidget(w); root = QVBoxLayout(w)
        top = QHBoxLayout(); b = QPushButton("Open PDF…"); b.clicked.connect(self.open_pdf); top.addWidget(b)
        sb = QPushButton("Settings…"); sb.clicked.connect(self.open_settings); top.addWidget(sb)
        self.spc = QDoubleSpinBox(); self.spc.setRange(0.05, 5); self.spc.setSingleStep(0.25)
        self.spc.setValue(self.settings.seconds_per_char); self.spc.valueChanged.connect(lambda v: setattr(self.settings, "seconds_per_char", v))
        self.extra = QDoubleSpinBox(); self.extra.setRange(0, 30); self.extra.setValue(self.settings.extra_pause)
        self.extra.valueChanged.connect(lambda v: setattr(self.settings, "extra_pause", v))
        for lab, sp in (("Sec/char", self.spc), ("Extra pause", self.extra)): top.addWidget(QLabel(lab)); top.addWidget(sp)
        root.addLayout(top)
        self.view = QLabel(alignment=Qt.AlignCenter); self.view.setMinimumHeight(300); root.addWidget(self.view, 1)
        self.status = QLabel("OPEN A PDF", alignment=Qt.AlignCenter); self.status.setStyleSheet("font:bold 28px;padding:12px")
        self.chunk = QLabel("", alignment=Qt.AlignCenter, wordWrap=True); self.chunk.setStyleSheet("font-size:22px")
        self.info = QLabel(""); self.bar = QProgressBar(); self.bar.setRange(0, 1000)
        for x in (self.status, self.chunk, self.info, self.bar): root.addWidget(x)
        for key, fn in (("Space", "toggle"), ("R", "repeat"), ("Left", "prev"), ("Right", "next"), ("Esc", "stop")):
            sc = QShortcut(QKeySequence(key), self); sc.setContext(Qt.ApplicationShortcut)
            sc.activated.connect(lambda f=fn: self.ctl and getattr(self.ctl, f)())
        t = QTimer(self); t.timeout.connect(self.tick); t.start(100)

    def open_pdf(self):
        p, _ = QFileDialog.getOpenFileName(self, "PDF", "", "PDF (*.pdf)")
        if not p: return
        dlg = QProgressDialog("Reading PDF (scanned pages are OCR'd, this can take a while)…", "Cancel", 0, 100, self)
        dlg.setWindowModality(Qt.WindowModal); dlg.setMinimumDuration(500)
        self.loader = Loader(p, self.settings)
        self.loader.progress.connect(lambda i, n: (dlg.setMaximum(n), dlg.setValue(i)))
        self.loader.failed.connect(lambda m: (dlg.close(), QMessageBox.critical(self, "Error", m)))
        self.loader.done.connect(lambda res: (dlg.close(), self.on_loaded(p, res)))
        dlg.canceled.connect(self.loader.requestInterruption)
        self.loader.start()

    def on_loaded(self, p, res):
        self.pages, self.doc, self.path = res.pages, fitz.open(p), p
        if res.ocr_pages:
            QMessageBox.information(self, "OCR used", f"{res.ocr_pages} scanned page(s) were read with OCR. "
                                    "Accuracy depends on scan quality; check the preview if a chunk sounds wrong.")
        self.ctl = Controller(res.items, self.speech, self.settings, on_change=self.refresh)
        s = sessions.load(p)
        if s and QMessageBox.question(self, "Resume", "Resume from previous position?") == QMessageBox.Yes:
            self.ctl.index = min(s["chunk_index"], len(res.items) - 1)
        self.refresh()

    def tick(self):
        if not self.ctl: return
        self.ctl.tick()
        if self.ctl.state == State.WRITING:
            tot = max(0.001, self.ctl.item.character_count * self.settings.seconds_per_char + self.settings.extra_pause)
            self.bar.setValue(int(1000 * (1 - self.ctl.time_left() / tot)))
            self.status.setText(f"✍ WRITING  {self.ctl.time_left():.1f}s")

    def refresh(self):
        c = self.ctl; st = c.state; it = c.item
        self.status.setText(LABELS[st]); self.status.setStyleSheet(
            f"font:bold 28px;padding:12px;color:white;background:{COLORS.get(st, '#455a64')}")
        if it is not None:
            self.chunk.setText("[IMAGE]" if isinstance(it, ImageItem) else it.text)
            self.info.setText(f"Page {it.page_number} / {self.pages}   Item {c.index + 1} / {len(c.items)}"
                              + ("" if isinstance(it, ImageItem) else f"   Writing time: {c.remaining or 0:.2f}s"))
            self.show_page(it)
        if self.path: sessions.save(self.path, c.index, {"seconds_per_character": self.settings.seconds_per_char})

    def apply_speech(self):
        s = self.settings; self.speech.rate, self.speech.volume, self.speech.voice_id = s.rate, s.volume, s.voice_id or None

    def open_settings(self):
        d = SettingsDialog(self.settings, self.speech.voices(), self)
        if d.exec():
            for k, v in vars(d.result_settings()).items(): setattr(self.settings, k, v)  # in place: controller sees it
            cfg.save(self.settings); self.apply_speech()
            self.spc.setValue(self.settings.seconds_per_char); self.extra.setValue(self.settings.extra_pause)

    def show_page(self, it):
        if not self.doc: return
        page, z = self.doc[it.page_number - 1], 1.2
        pix = page.get_pixmap(matrix=fitz.Matrix(z, z))
        pm = QPixmap.fromImage(QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888).copy())
        p = QPainter(pm)
        if isinstance(it, ImageItem):
            p.setPen(QPen(QColor("#e53935"), 5)); rects = [it.bbox]
        else:
            p.setPen(Qt.NoPen); p.setBrush(QColor(255, 235, 59, 120))
            try: found = [tuple(r) for r in page.search_for(it.text) if fitz.Rect(r).intersects(fitz.Rect(it.bbox))] if it.bbox else []
            except Exception: found = []
            rects = found or ([it.bbox] if it.bbox else [])   # exact words, else the whole block (e.g. OCR pages)
        for r in rects: p.drawRect(QRectF(r[0] * z, r[1] * z, (r[2] - r[0]) * z, (r[3] - r[1]) * z))
        p.end()
        self.view.setPixmap(pm.scaledToHeight(max(300, self.view.height()), Qt.SmoothTransformation))


def main():
    a = QApplication(sys.argv); a.setApplicationName("PDF Dictation")
    w = Win(); w.resize(900, 800); w.show(); sys.exit(a.exec())


if __name__ == "__main__":
    main()
````

## FILE: tests/test_core.py

````python
import pytest
from pdf_dictation.chunker import *
from pdf_dictation.controller import Controller, State, Settings
from pdf_dictation.extractor import reading_order, Entry, keep_image
from pdf_dictation import sessions


@pytest.mark.parametrize("w,e", [("a", .5), ("an", .5), ("the", .5), ("cell", 1), ("mitochondria", 1),
                                 ("cell,", 1), ("(cell)", 1), ("book.", 1), ("DNA", .5), ("2025", 1)])
def test_weights(w, e): assert word_weight(w) == e


def test_timing(): assert writing_time(char_count("The cell is large."), 0.75) == 10.5


def test_example_chunks():
    c = TextChunker().create_chunks("The cell membrane controls the movement of substances")
    assert c[0].text == "The cell membrane controls" and c[0].word_units == 3.5 and c[0].character_count == 23
    assert writing_time(c[0].character_count) == 17.25
    assert TextChunker().create_chunks("I am studying mitochondria")[0].word_units == 3.0


def test_words_never_split_and_paragraphs_separate():
    c = TextChunker().create_chunks("electroencephalography\n\nNext para here")
    assert c[0].text == "electroencephalography" and len(c) == 2


def test_sentence_boundary():
    c = TextChunker().create_chunks("The cell is large. Another one here today")
    assert c[0].text == "The cell is large."


class FakeSpeech:
    def __init__(s): s.on = False; s.said = []
    def speak(s, t): s.on = True; s.said.append(t)
    def stop(s): s.on = False
    def is_speaking(s): return s.on


def make(items):
    t = [0.0]; sp = FakeSpeech()
    return Controller(items, sp, Settings(), clock=lambda: t[0]), sp, t


def test_timer_starts_after_speech_and_image_pause():
    ch = TextChunker().create_chunks("The cell membrane controls")  # 23 chars -> 17.25 s
    c, sp, t = make(ch + [ImageItem(1, (0, 0, 200, 200))] + TextChunker().create_chunks("Hello world today"))
    c.start(); assert c.state == State.SPEAKING
    t[0] = 100; c.tick(); assert c.state == State.SPEAKING
    sp.on = False; c.tick(); assert c.state == State.WRITING
    t[0] = 100 + 17; c.tick(); assert c.state == State.WRITING
    t[0] = 100 + 17.3; c.tick(); assert c.state == State.IMAGE_PAUSED
    c.toggle(); assert c.state == State.SPEAKING and sp.said[-1] == "Hello world today"


def test_pause_freezes_and_repeat_restarts():
    c, sp, t = make(TextChunker().create_chunks("The cell membrane controls"))
    c.start(); sp.on = False; c.tick(); t[0] = 10; c.toggle()
    assert c.state == State.PAUSED; t[0] = 500; c.toggle()
    assert c.state == State.WRITING and abs(c.time_left() - 7.25) < 1e-9
    c.repeat(); assert c.state == State.SPEAKING and len(sp.said) == 2 and c.index == 0


def test_reading_order_two_columns():
    E = lambda r, n: Entry(r, "text", n)
    es = [E((0, 0, 600, 50), "title"), E((320, 60, 580, 100), "R1"), E((20, 60, 280, 100), "L1"),
          E((20, 110, 280, 150), "L2")]
    assert [e.payload for e in reading_order(es, 600)] == ["title", "L1", "L2", "R1"]
    assert not keep_image((0, 0, 20, 20), 100, 100)


def test_sessions(tmp_path):
    a, b = tmp_path / "a.pdf", tmp_path / "b.pdf"; a.write_bytes(b"A"); b.write_bytes(b"B")
    sessions.save(str(a), 43, {}, tmp_path)
    assert sessions.load(str(a), tmp_path)["chunk_index"] == 43 and sessions.load(str(b), tmp_path) is None


def test_textprep():
    from pdf_dictation.textprep import prepare_speech as p
    assert p("Figure 3.2 shows it.") == "Figure 3 point 2 shows it."
    assert p("Fig. 1") == "Figure 1"
    assert p("The cell, large.", speak_punctuation=True) == "The cell, comma, large, period,"
    assert p("A, b.", speak_punctuation=False) == "A, b."


def test_settings_roundtrip(tmp_path):
    from pdf_dictation import settings as cfg
    s = cfg.load(tmp_path / "x.json"); assert s.seconds_per_char == 0.75      # missing file -> defaults
    s.seconds_per_char, s.rate = 1.25, 170; cfg.save(s, tmp_path / "x.json")
    r = cfg.load(tmp_path / "x.json"); assert (r.seconds_per_char, r.rate) == (1.25, 170)
    assert r.word_rules().target == 3.0


def test_ocr_helpers():
    from pdf_dictation.extractor import needs_ocr, is_page_scan
    assert needs_ocr([]) and needs_ocr([((0, 0, 1, 1), "  p. 3 ")]) and not needs_ocr([((0, 0, 1, 1), "A real paragraph of text here.")])
    assert is_page_scan((0, 0, 600, 790), (0, 0, 612, 792)) and not is_page_scan((50, 50, 300, 300), (0, 0, 612, 792))


def test_ocr_settings_roundtrip(tmp_path):
    from pdf_dictation import settings as cfg
    s = cfg.load(tmp_path / "o.json"); assert (s.ocr_mode, s.ocr_language) == ("auto", "eng")
    s.ocr_language = "hin"; cfg.save(s, tmp_path / "o.json"); assert cfg.load(tmp_path / "o.json").ocr_language == "hin"
````

## FILE: packaging/pdfdictation.spec

````
# Build: pyinstaller --noconfirm packaging/pdfdictation.spec   (run on each target OS)
from PyInstaller.utils.hooks import collect_submodules
hidden = collect_submodules("pyttsx3") + collect_submodules("pdf_dictation")
a = Analysis(["../app.py"], pathex=[".."], hiddenimports=hidden,
             excludes=["tkinter", "PySide6.QtWebEngineCore", "PySide6.QtQuick", "PySide6.QtQml", "PySide6.Qt3DCore"])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="PDFDictation", console=False)
coll = COLLECT(exe, a.binaries, a.datas, name="PDFDictation")
````

## FILE: packaging/build_linux.sh

````bash
#!/usr/bin/env bash
# Produces dist/pdf-dictation_<ver>_amd64.deb and dist/PDFDictation-<ver>-linux-x86_64.tar.gz
set -euo pipefail
cd "$(dirname "$0")/.."
VER=$(python -c "import pdf_dictation as p; print(p.__version__)")
pyinstaller --noconfirm packaging/pdfdictation.spec
P=build/deb/pdf-dictation_${VER}_amd64
rm -rf build/deb; mkdir -p "$P/DEBIAN" "$P/opt/pdfdictation" "$P/usr/bin" "$P/usr/share/applications"
cp -r dist/PDFDictation/* "$P/opt/pdfdictation/"
ln -s /opt/pdfdictation/PDFDictation "$P/usr/bin/pdfdictation"
cp packaging/pdfdictation.desktop "$P/usr/share/applications/"
cat > "$P/DEBIAN/control" <<CTL
Package: pdf-dictation
Version: $VER
Architecture: amd64
Maintainer: PDF Dictation Maintainers <maintainers@example.com>
Depends: espeak-ng, libegl1, libxkbcommon0, libxcb-cursor0
Description: Controlled PDF dictation for copying textbooks by hand
CTL
dpkg-deb --build --root-owner-group "$P" dist/
tar czf "dist/PDFDictation-${VER}-linux-x86_64.tar.gz" -C dist PDFDictation
````

## FILE: packaging/installer.iss

````
; Needs Inno Setup. Run after PyInstaller:  iscc packaging\installer.iss /DAppVersion=0.1.0
#ifndef AppVersion
#define AppVersion "0.1.0"
#endif
[Setup]
AppName=PDF Dictation
AppVersion={#AppVersion}
DefaultDirName={autopf}\PDF Dictation
DefaultGroupName=PDF Dictation
OutputDir=..\dist
OutputBaseFilename=PDFDictation-Setup-{#AppVersion}
Compression=lzma2
ArchitecturesInstallIn64BitMode=x64compatible
[Files]
Source: "..\dist\PDFDictation\*"; DestDir: "{app}"; Flags: recursesubdirs
[Icons]
Name: "{group}\PDF Dictation"; Filename: "{app}\PDFDictation.exe"
Name: "{autodesktop}\PDF Dictation"; Filename: "{app}\PDFDictation.exe"; Tasks: desktopicon
[Tasks]
Name: desktopicon; Description: "Create a desktop icon"
````

## FILE: packaging/pdfdictation.desktop

````
[Desktop Entry]
Type=Application
Name=PDF Dictation
Comment=Dictate PDF text for handwriting
Exec=pdfdictation
Categories=Education;Utility;
Terminal=false
````

## FILE: .github/workflows/release.yml

````yaml
name: build
on:
  push: { tags: ["v*"] }
  workflow_dispatch:
jobs:
  build:
    strategy:
      matrix: { os: [windows-latest, ubuntu-22.04] }   # old glibc => runs on more Linux distros
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - if: runner.os == 'Linux'
        run: sudo apt-get update && sudo apt-get install -y espeak-ng
      - run: pip install -e ".[dev,build]"
      - run: pytest -q
      - if: runner.os == 'Windows'
        shell: pwsh
        run: |
          pyinstaller --noconfirm packaging/pdfdictation.spec
          choco install innosetup -y
          & "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" packaging\installer.iss
      - if: runner.os == 'Linux'
        run: ./packaging/build_linux.sh
      - uses: actions/upload-artifact@v4
        with: { name: "${{ matrix.os }}", path: "dist/*.exe\ndist/*.deb\ndist/*.tar.gz" }
````

## FILE: README.md

````markdown
# PDF Dictation
Controlled dictation for copying a PDF into a paper notebook: speak a chunk, stay silent while you write, speak the next, and pause at figures.

## Install
    python -m venv .venv
    .venv\Scripts\Activate.ps1      # Windows PowerShell   (CMD: .venv\Scripts\activate.bat)
    source .venv/bin/activate       # Linux
    pip install -e ".[dev]"
    python app.py
Linux TTS needs `espeak-ng` (`sudo apt install espeak-ng`). Tests: `pytest`.

## How it works
* **Word units:** 1–3 letters = 0.5, 4+ letters = 1.0 (punctuation ignored; numbers count digits). Chunks close at ≥3.0 units, or earlier at a sentence mark once ≥1.5. Words are never split; paragraphs never merge.
* **Writing time:** alphanumeric characters × 0.75 s (+ optional extra pause). Spaces/punctuation excluded. The timer starts only after speech finishes.
* **Images:** images ≥100×100 pt are placed in reading order among text blocks; dictation pauses *at* the image. Two-column pages are handled (full-width blocks split bands, then left column, then right).
* **Keys:** Space pause/resume/continue · R repeat · ←/→ previous/next (lands paused) · Esc stop.
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
OCR, settings dialog, speak-punctuation/normalization, vector-diagram detection, in-page highlighting and AppImage are not implemented yet.
````

---

# MY CHANGE REQUEST

(Replace this line with what you want, e.g. "Add on-screen Start/Pause/Repeat buttons", "Add Hindi/Gujarati support end to end", "Cache OCR results per PDF hash", "Make shortcuts configurable".)
