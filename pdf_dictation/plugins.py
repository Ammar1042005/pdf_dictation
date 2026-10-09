"""External user plugins and voice profiles.

Plugins live outside packaged builds so EXE and Linux users can extend the
application without modifying its files. Python plugins are opt-in.
"""
import importlib.util
import json
import logging
from dataclasses import dataclass

from pdf_dictation import paths

log = logging.getLogger("pdf_dictation")


@dataclass(frozen=True)
class VoiceProfile:
    voice_id: str
    name: str


def directory():
    folder = paths.data_dir() / "plugins"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def load_voice_profiles():
    profiles = []
    for path in sorted(directory().glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            voice_id = str(data["voice_id"]).strip()
            name = str(data.get("name") or voice_id).strip()
            if voice_id and name:
                profiles.append(VoiceProfile(voice_id, name))
        except (OSError, ValueError, KeyError, TypeError) as exc:
            log.warning("Ignoring invalid voice profile %s: %s", path, exc)
    return profiles


def load_python_plugins():
    loaded = []
    profiles = []
    for path in sorted(directory().glob("*.py")):
        if path.name.startswith("_"):
            continue
        try:
            spec = importlib.util.spec_from_file_location(f"pdf_dictation_plugin_{path.stem}", path)
            if not spec or not spec.loader:
                raise RuntimeError("plugin loader unavailable")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            register = getattr(module, "register", None)
            if register:
                register(profiles)
            loaded.append(path.name)
        except (OSError, ImportError, RuntimeError, SyntaxError) as exc:
            log.warning("Ignoring plugin %s: %s", path, exc)
    return loaded, profiles


def load_enabled_voice_profiles():
    profiles = load_voice_profiles()
    _, plugin_profiles = load_python_plugins()
    for profile in plugin_profiles:
        if isinstance(profile, VoiceProfile):
            profiles.append(profile)
        elif isinstance(profile, dict) and profile.get("voice_id"):
            profiles.append(VoiceProfile(str(profile["voice_id"]), str(profile.get("name") or profile["voice_id"])))
    return profiles
