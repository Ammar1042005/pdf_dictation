# PDF Dictation Limitations Checklist

Use this checklist to track reliability, accuracy, usability, and release improvements.

## Priority levels

- **P0 — Critical:** correctness, data integrity, or basic usability
- **P1 — High:** reliable everyday use
- **P2 — Medium:** accuracy, compatibility, or maintainability
- **P3 — Low:** release polish and nice-to-have features

## P0 — Correctness and safety

- [x] Build a representative PDF fixture collection:
  - [x] Single-column documents
  - [x] Two-column documents
  - [x] Asymmetric columns
  - [x] Tables
  - [x] Sidebars and captions
  - [x] Figures and mixed text/images
  - [x] Scanned pages
  - [x] Code listings and formulas
- [x] Improve layout detection for tables, sidebars, captions, and mixed columns.
- [x] Add regression tests for every currently supported PDF layout.
- [x] Report skipped pages and extraction failures visibly in the GUI.
- [x] Add a PDF loading summary showing extracted pages, OCR pages, skipped pages, and warnings.
- [x] Add safe application shutdown handling:
  - [x] Stop active speech
  - [x] Interrupt and wait for PDF loader threads
  - [x] Close the current PDF document
- [x] Make session resume robust when extraction or chunking settings change.
- [x] Store enough session identity to resume by content, not only by chunk index:
  - [x] Page number
  - [x] Chunk text hash
  - [x] Extraction settings hash

## P1 — High priority reliability and accuracy

- [x] Improve OCR setup diagnostics.
- [x] Validate configured OCR languages before loading a document.
- [x] Preserve OCR word-level bounding boxes.
- [x] Improve OCR highlighting and mouse selection accuracy.
- [x] Add document speech profiles:
  - [x] Prose
  - [x] Code
  - [x] Automatic
- [x] Detect mixed prose/code pages automatically.
- [x] Improve speech-backend diagnostics for Windows and Linux.
- [x] Show the selected TTS voice and backend status.
- [x] Improve speech failure detection using engine callbacks where available.
- [x] Add clear speech retry and failure information.
- [x] Add integration tests for real or mocked TTS behavior.

## P2 — Medium priority accuracy improvements

- [x] Add user handwriting-speed calibration.
- [x] Add writing-time profiles for:
  - [x] Prose
  - [x] Code
  - [x] Equations
  - [x] Custom handwriting speed
- [x] Add token-aware chunking for:
  - [x] Code
  - [x] Formulas
  - [x] URLs
  - [x] Long identifiers
  - [x] Long uninterrupted tokens
- [x] Improve sentence-boundary detection:
  - [x] Abbreviations
  - [x] Decimal numbers
  - [x] Bullet lists
  - [x] Source code
- [x] Add explicit table detection and table reading modes.
- [x] Improve image classification using captions, surrounding text, position, and area.
- [x] Detect vector diagrams made from PDF drawing commands.
- [x] Add pixmap caching for preview pages.
- [x] Render only visible preview regions where practical.
- [x] Improve preview selection using extracted coordinates instead of text search alone.
- [x] Add document-wide search.
- [x] Add bookmarks.
- [x] Add GUI integration tests.
- [x] Add OCR integration tests.
- [x] Add sample-PDF extraction tests.
- [x] Add linting and type checking to CI.
- [x] Test supported Python, operating system, and dependency combinations in CI.

## P3 — Release and usability improvements

- [x] Add navigation history with back/forward controls.

- [x] Provide a simpler built-in OCR installation experience where licensing permits.
- [ ] Add Windows code signing.
- [x] Add an application icon.
- [x] Add a LICENSE file.
- [ ] Replace placeholder maintainer/package metadata.
- [x] Add AppImage or another portable Linux package.
- [ ] Improve accessibility:
  - [x] Accessible widget labels
  - [x] Keyboard focus order
  - [x] Screen-reader support
  - [x] High-contrast support
  - [x] Scalable fonts
- [ ] Add localization support using Qt translation resources.
- [x] Add an opt-in diagnostic export that excludes document text.
- [x] Add opt-in GitHub release update checks with manual installation.

## Recommended implementation phases

### Phase 1 — Correctness and safety

- [ ] Complete the P0 checklist.
- [ ] Establish the representative PDF fixture suite.
- [ ] Add regression tests before changing layout algorithms.

### Phase 2 — Accuracy

- [ ] Complete OCR word-position support.
- [ ] Add table and code-block handling.
- [ ] Add automatic prose/code speech selection.
- [ ] Improve image and diagram detection.
- [ ] Add chunking profiles.

### Phase 3 — Usability

- [ ] Add search.
- [ ] Add bookmarks and navigation history.
- [ ] Optimize preview rendering.
- [ ] Add handwriting calibration.
- [ ] Improve accessibility.

### Phase 4 — Quality and distribution

- [ ] Add full integration coverage.
- [ ] Add linting and type checking to CI.
- [ ] Test supported platform/dependency combinations.
- [ ] Complete installer, signing, icon, license, and portable-package work.
