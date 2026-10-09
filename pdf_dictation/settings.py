import json
import logging
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
