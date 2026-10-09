"""Per-OS user data locations and bundled-resource lookup (works frozen or from source)."""
import os
import sys
from pathlib import Path

APP = "PDFDictation"


def data_dir():
    if sys.platform == "win32": base = Path(os.environ.get("APPDATA", Path.home() / "AppData/Roaming"))
    elif sys.platform == "darwin": base = Path.home() / "Library/Application Support"
    else: base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
    d = base / APP; d.mkdir(parents=True, exist_ok=True); return d


def log_file(): return data_dir() / "pdf_dictation.log"
def resource(rel): return Path(getattr(sys, "_MEIPASS", Path(__file__).parent)) / rel
