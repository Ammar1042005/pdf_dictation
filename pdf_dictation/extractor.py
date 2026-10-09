"""PDF -> ordered sequence of Chunk / ImageItem (position-aware, with automatic OCR for scanned pages)."""
import logging
import re
from dataclasses import dataclass
from . import ocr, sessions
from .chunker import TextChunker, ImageItem
from .textprep import looks_like_code

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
    word_bboxes: list = None


@dataclass
class Loaded:
    items: list
    pages: int
    ocr_pages: int = 0
    skipped_pages: list = None
    warnings: list = None


def reading_order(entries, page_w):
    """Order entries by full-width bands and detected left/right columns."""
    key_y = lambda e: (e.rect[1], e.rect[0])
    out, band = [], []

    def flush():
        if not band:
            return
        ordered = sorted(band, key=key_y)
        if len(ordered) < 2:
            out.extend(ordered); band.clear(); return

        # A large gap between block centres is a more reliable column boundary
        # than the page midpoint when margins or columns are asymmetric.
        by_x = sorted(ordered, key=lambda e: (e.rect[0] + e.rect[2]) / 2)
        gaps = [
            (
                (by_x[i + 1].rect[0] + by_x[i + 1].rect[2]) / 2
                - (by_x[i].rect[0] + by_x[i].rect[2]) / 2,
                i,
            )
            for i in range(len(by_x) - 1)
        ]
        gap, split = max(gaps)
        min_gap = max(24.0, page_w * 0.08)
        if gap < min_gap:
            out.extend(ordered)
        else:
            left = sorted(by_x[:split + 1], key=key_y)
            right = sorted(by_x[split + 1:], key=key_y)
            out.extend(left + right)
        band.clear()

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


def classify_image(rect, text_entries, page_rect, vector=False):
    """Classify figures using nearby caption text, position, and occupied area."""
    x0, y0, x1, y1 = rect
    height = max(1.0, y1 - y0)
    nearby = []
    for entry_rect, text in text_entries:
        ex0, ey0, ex1, ey1 = entry_rect
        vertical_gap = min(abs(ey0 - y1), abs(y0 - ey1))
        horizontal_overlap = max(0.0, min(x1, ex1) - max(x0, ex0))
        if vertical_gap <= max(36.0, height * 0.35) and horizontal_overlap >= 0.2 * min(x1 - x0, ex1 - ex0):
            nearby.append(text.strip())
    caption = next(
        (text for text in nearby if re.match(r"^(?:figure|fig\.|diagram|chart|table)\b", text, re.I)),
        "",
    )
    page_area = max(1.0, (page_rect[2] - page_rect[0]) * (page_rect[3] - page_rect[1]))
    area_fraction = ((x1 - x0) * (y1 - y0)) / page_area
    kind = "vector diagram" if vector else ("figure" if caption or area_fraction >= 0.12 else "image")
    return kind, caption


def vector_diagram_regions(page, min_area=2500):
    """Find substantial clusters of PDF drawing commands that are likely diagrams."""
    try:
        drawings = page.get_drawings()
    except (AttributeError, RuntimeError, ValueError):
        return []
    if len(drawings) < 4:
        return []
    rects = [tuple(d["rect"]) for d in drawings if d.get("rect")]
    if not rects:
        return []
    bounds = (
        min(r[0] for r in rects), min(r[1] for r in rects),
        max(r[2] for r in rects), max(r[3] for r in rects),
    )
    if (bounds[2] - bounds[0]) * (bounds[3] - bounds[1]) < min_area:
        return []
    return [bounds]


def search_document(doc, query, limit=200):
    """Return page/rectangle matches for a case-insensitive document search."""
    query = query.strip()
    if not query:
        return []
    matches = []
    for page_number, page in enumerate(doc, 1):
        try:
            rects = page.search_for(query)
        except (AttributeError, RuntimeError, ValueError):
            rects = []
        for rect in rects:
            matches.append((page_number, tuple(rect)))
            if len(matches) >= limit:
                return matches
    return matches


def table_entries(page, page_number):
    """Return table regions as row-major text entries when PyMuPDF detects them."""
    try:
        tables = page.find_tables().tables
    except (AttributeError, RuntimeError, ValueError):
        return []
    entries = []
    for table in tables:
        rows = table.extract()
        text = "\n".join(" | ".join(cell or "" for cell in row) for row in rows)
        if text.strip():
            entries.append(Entry(tuple(table.bbox), "text", text))
    return entries


def load_items(path, min_w=100, min_h=100, chunker=None, ocr_mode="auto", ocr_lang="eng", progress=None, use_ocr_cache=True):
    try:
        import pymupdf as fitz
        doc = fitz.open(path)
    except Exception as e: raise PdfError(f"Cannot open PDF: {e}")
    if doc.needs_pass: raise PdfError("PDF is password-protected.")
    chunker, items, n_ocr, skipped_pages, warnings = chunker or TextChunker(), [], 0, [], []
    ocr_ok = ocr_mode == "auto" and ocr.available(ocr_lang)
    for pno, page in enumerate(doc, 1):
        if progress: progress(pno, len(doc))          # may raise PdfError to cancel
        try:
            blocks = [(tuple(b[:4]), b[4]) for b in page.get_text("blocks") if b[6] == 0 and b[4].strip()]
            scanned = False
            if needs_ocr(blocks) and ocr_mode == "auto":
                if ocr_ok:
                    # Check OCR cache first
                    cached_blocks = None
                    if use_ocr_cache:
                        cached_blocks = sessions.load_ocr_cache(path, pno, ocr_lang)
                    if cached_blocks is not None:
                        blocks = cached_blocks
                        scanned = True
                        n_ocr += 1
                        log.info("OCR cache used: page %d", pno)
                    else:
                        blocks, scanned = ocr.ocr_blocks(page, ocr_lang), True; n_ocr += 1; log.info("OCR p%d", pno)
                        # Save to cache
                        if use_ocr_cache:
                            sessions.save_ocr_cache(path, pno, blocks, ocr_lang)
                else:
                    skipped_pages.append(pno)
                    reason = ocr.availability_error(ocr_lang)
                    warnings.append(f"Page {pno}: text layer is missing. {reason}")
            entries = [
                Entry(block[0], "text", block[1], block[2] if len(block) > 2 else None)
                for block in blocks
            ]
            detected_tables = table_entries(page, pno)
            for table in detected_tables:
                entries = [
                    entry for entry in entries
                    if not fitz.Rect(entry.rect).intersects(fitz.Rect(table.rect))
                ]
            entries.extend(detected_tables)
            text_entries = [(e.rect, e.payload) for e in entries if e.kind == "text"]
            for im in page.get_image_info():
                r = tuple(im["bbox"])
                if keep_image(r, min_w, min_h) and not (scanned and is_page_scan(r, tuple(page.rect))):
                    kind, caption = classify_image(r, text_entries, tuple(page.rect))
                    entries.append(Entry(r, "image", ImageItem(pno, r, kind, caption))); log.info("%s p%d", kind, pno)
            for r in vector_diagram_regions(page):
                kind, caption = classify_image(r, text_entries, tuple(page.rect), vector=True)
                entries.append(Entry(r, "image", ImageItem(pno, r, kind, caption)))
                log.info("vector diagram p%d", pno)
            for e in reading_order(entries, page.rect.width):
                if e.kind == "image": items.append(e.payload)
                else:
                    text = e.payload.replace("-\n", "")
                    code_block = looks_like_code(text)
                    new = chunker.create_chunks(text if code_block else text.replace("\n", " "),
                                                pno, preserve_lines=code_block)
                    for c in new:
                        c.bbox = e.rect
                        c.word_bboxes = e.word_bboxes
                    items.extend(new)
        except Exception as ex:
            skipped_pages.append(pno)
            warnings.append(f"Page {pno}: extraction failed ({ex}).")
            log.error("page %d parse failed: %s", pno, ex)
    if not any(not isinstance(i, ImageItem) for i in items):
        raise PdfError(OCR_HELP if skipped_pages else "No extractable text found in this PDF.")
    page_count = len(doc)
    doc.close()
    log.info("loaded %d items from %d pages (%d OCR)", len(items), page_count, n_ocr)
    return Loaded(items, page_count, n_ocr, skipped_pages, warnings)
