"""Create privacy-safe diagnostic reports without document content."""
import json
import platform
from datetime import datetime, timezone
from pathlib import Path

from . import ocr


def report(settings, speech=None):
    report_data = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "application": "PDFDictation",
        "python": platform.python_version(),
        "platform": platform.platform(),
        "pymupdf": _version("pymupdf"),
        "settings": {
            "ocr_mode": settings.ocr_mode,
            "ocr_language": settings.ocr_language,
            "use_ocr_cache": settings.use_ocr_cache,
            "speech_profile": settings.speech_profile,
            "writing_profile": settings.writing_profile,
        },
        "ocr": {
            "configured_language_available": ocr.available(settings.ocr_language),
        },
    }
    if speech is not None:
        report_data["speech"] = speech.diagnostics()
    return report_data


def write_report(path, settings, speech=None):
    Path(path).write_text(json.dumps(report(settings, speech), indent=2), encoding="utf-8")


def _version(module_name):
    try:
        module = __import__(module_name)
        return getattr(module, "__version__", "unknown")
    except Exception:
        return "unavailable"
