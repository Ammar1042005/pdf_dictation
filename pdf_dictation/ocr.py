"""Offline OCR via PyMuPDF's built-in Tesseract bridge (needs the Tesseract program + language data installed)."""
from pathlib import Path


def tessdata():
    try:
        import pymupdf
        return pymupdf.get_tessdata()
    except Exception:
        return None


def available(language="eng"):
    root = tessdata()
    if not root:
        return False
    directory = Path(root)
    return directory.is_dir() and all(
        (directory / f"{part}.traineddata").is_file()
        for part in language.split("+") if part
    )


def availability_error(language="eng"):
    root = tessdata()
    if not root:
        return "Tesseract is not installed or its tessdata directory could not be found."
    directory = Path(root)
    missing = [
        part for part in language.split("+") if part and not (directory / f"{part}.traineddata").is_file()
    ]
    if missing:
        return f"OCR language data is missing: {', '.join(missing)}."
    return None


def ocr_blocks(page, lang="eng", dpi=200):
    tp = page.get_textpage_ocr(language=lang, dpi=dpi, full=True, tessdata=tessdata())
    words_by_block = {}
    for word in page.get_text("words", textpage=tp):
        block_no = word[5]
        words_by_block.setdefault(block_no, []).append((tuple(word[:4]), word[4]))
    return [
        (tuple(block[:4]), block[4], words_by_block.get(block[5], []))
        for block in page.get_text("blocks", textpage=tp)
        if block[6] == 0 and block[4].strip()
    ]
