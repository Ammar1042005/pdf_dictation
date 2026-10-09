import json

import pytest

from pdf_dictation import updater
from pdf_dictation.controller import Settings


def test_repository_api_url():
    assert updater.repository_api_url("https://github.com/example/pdf-dictation") == (
        "https://api.github.com/repos/example/pdf-dictation/releases/latest"
    )


def test_default_update_repository():
    assert Settings().auto_update is False
    assert updater.UPDATE_SOURCES == ("https://github.com/Ammar1042005/pdf_dictation",)


def test_invalid_repository_is_rejected():
    with pytest.raises(ValueError):
        updater.repository_api_url("https://example.com/project")


def test_check_latest_reports_new_release(monkeypatch):
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return json.dumps({
                "tag_name": "v0.2.0",
                "html_url": "https://github.com/example/pdf-dictation/releases/tag/v0.2.0",
                "name": "PDF Dictation 0.2.0",
            }).encode()

    monkeypatch.setattr(updater, "urlopen", lambda request, timeout: Response())
    release = updater.check_latest("0.1.0", "https://github.com/example/pdf-dictation")
    assert release is not None
    assert release.url.endswith("v0.2.0")


def test_check_latest_returns_none_when_current(monkeypatch):
    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def read(self): return b'{"tag_name":"v0.1.0","html_url":"https://github.com/example/pdf-dictation/releases/1"}'

    monkeypatch.setattr(updater, "urlopen", lambda request, timeout: Response())
    assert updater.check_latest("0.1.0", "https://github.com/example/pdf-dictation") is None


def test_check_latest_sources_uses_newest_release(monkeypatch):
    releases = {
        "https://one.example": updater.Release(
            "0.2.0", "https://github.com/example/one/releases/2", "Two"
        ),
        "https://two.example": updater.Release(
            "0.3.0", "https://github.com/example/two/releases/3", "Three"
        ),
    }
    monkeypatch.setattr(updater, "check_latest", lambda current, repository, timeout: releases[repository])
    latest = updater.check_latest_sources("0.1.0", releases)
    assert latest is not None
    assert latest.version == "0.3.0"
