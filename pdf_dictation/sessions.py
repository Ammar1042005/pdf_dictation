import hashlib
import json
import logging
from pdf_dictation import paths
log = logging.getLogger("pdf_dictation")
DIR = paths.data_dir() / "sessions"
OCR_DIR = paths.data_dir() / "ocr_cache"


def pdf_hash(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""): h.update(b)
    return h.hexdigest()


def text_hash(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def save(path, index, settings: dict, directory=DIR, page_number=None, chunk_text=None, extraction_settings=None):
    try:
        directory.mkdir(parents=True, exist_ok=True); h = pdf_hash(path)
        data = {"pdf_hash": h, "chunk_index": index, "settings": settings}
        if page_number is not None:
            data["page_number"] = page_number
        if chunk_text is not None:
            data["chunk_text_hash"] = text_hash(chunk_text)
        if extraction_settings is not None:
            data["extraction_settings_hash"] = text_hash(json.dumps(extraction_settings, sort_keys=True))
        (directory / f"{h}.json").write_text(json.dumps(data))
    except Exception as e: log.error("session save failed: %s", e)


def load(path, directory=DIR):
    try:
        h = pdf_hash(path); d = json.loads((directory / f"{h}.json").read_text())
        return d if d.get("pdf_hash") == h else None
    except Exception: return None


def save_ocr_cache(path, page_num, blocks, language, directory=OCR_DIR):
    """Save OCR results for a specific page of a PDF."""
    try:
        directory.mkdir(parents=True, exist_ok=True)
        h = pdf_hash(path)
        cache_file = directory / f"{h}_p{page_num}_{language}.json"
        cache_file.write_text(json.dumps({"pdf_hash": h, "page": page_num, "language": language, "blocks": blocks}))
        log.info("OCR cache saved: page %d", page_num)
    except Exception as e:
        log.error("OCR cache save failed (page %d): %s", page_num, e)


def load_ocr_cache(path, page_num, language, directory=OCR_DIR):
    """Load OCR results for a specific page of a PDF."""
    try:
        h = pdf_hash(path)
        cache_file = directory / f"{h}_p{page_num}_{language}.json"
        if not cache_file.exists():
            return None
        d = json.loads(cache_file.read_text())
        if d.get("pdf_hash") == h and d.get("page") == page_num and d.get("language") == language:
            log.info("OCR cache hit: page %d", page_num)
            blocks = []
            for block in d.get("blocks", []):
                rect, text = tuple(block[:2])
                word_bboxes = block[2] if len(block) > 2 else None
                if word_bboxes is not None:
                    word_bboxes = [(tuple(word[0]), word[1]) for word in word_bboxes]
                    blocks.append((tuple(rect), text, word_bboxes))
                else:
                    blocks.append((tuple(rect), text))
            return blocks
        return None
    except Exception as e:
        log.error("OCR cache load failed (page %d): %s", page_num, e)
        return None


def clear_ocr_cache(path=None, directory=OCR_DIR):
    """Clear OCR cache for a specific PDF or all PDFs."""
    try:
        if path:
            h = pdf_hash(path)
            for f in directory.glob(f"{h}_*.json"):
                f.unlink()
                log.info("Cleared OCR cache for PDF")
        else:
            for f in directory.glob("*.json"):
                f.unlink()
            log.info("Cleared all OCR cache")
    except Exception as e:
        log.error("OCR cache clear failed: %s", e)
