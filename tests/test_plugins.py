import json

from pdf_dictation import plugins


def test_load_voice_profiles(tmp_path, monkeypatch):
    monkeypatch.setattr(plugins, "directory", lambda: tmp_path)
    (tmp_path / "voice.json").write_text(
        json.dumps({"name": "Study Voice", "voice_id": "local.voice"}), encoding="utf-8"
    )
    assert plugins.load_voice_profiles()[0] == plugins.VoiceProfile("local.voice", "Study Voice")


def test_invalid_voice_profiles_are_ignored(tmp_path, monkeypatch):
    monkeypatch.setattr(plugins, "directory", lambda: tmp_path)
    (tmp_path / "broken.json").write_text("not json", encoding="utf-8")
    assert plugins.load_voice_profiles() == []
