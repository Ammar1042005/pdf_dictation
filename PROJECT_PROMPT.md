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

# MY CHANGE REQUEST

(Replace this line with what you want, e.g. "Add on-screen Start/Pause/Repeat buttons", "Add Hindi/Gujarati support end to end", "Cache OCR results per PDF hash", "Make shortcuts configurable".)
