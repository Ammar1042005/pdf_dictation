"""Opt-in, read-only GitHub release checks.

The updater never downloads or replaces application files. It reports a verified
release URL so the user can review and install an update manually.
"""
import json
import re
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

# Application-controlled release sources. Add future official mirrors here and
# publish the change with the application; users cannot redirect update checks.
UPDATE_SOURCES = (
    "https://github.com/Ammar1042005/pdf_dictation",
)


@dataclass(frozen=True)
class Release:
    version: str
    url: str
    name: str


def _version(value):
    match = re.search(r"\d+(?:\.\d+){1,3}", value or "")
    return tuple(int(part) for part in match.group(0).split(".")) if match else ()


def repository_api_url(repository):
    match = re.fullmatch(r"https?://github\.com/([^/]+)/([^/#?]+?)(?:\.git)?/?", repository.strip())
    if not match:
        raise ValueError("Update repository must be a GitHub repository URL.")
    return f"https://api.github.com/repos/{match.group(1)}/{match.group(2)}/releases/latest"


def check_latest(current_version, repository, timeout=5):
    if not repository.strip():
        return None
    request = Request(
        repository_api_url(repository),
        headers={"Accept": "application/vnd.github+json", "User-Agent": "PDF-Dictation"},
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
        raise RuntimeError(f"Update check failed: {exc}") from exc
    tag = str(payload.get("tag_name", ""))
    url = str(payload.get("html_url", ""))
    if not tag or not url.startswith("https://github.com/"):
        raise RuntimeError("GitHub returned an invalid release response.")
    release = Release(tag, url, str(payload.get("name") or tag))
    return release if _version(tag) > _version(current_version) else None


def check_latest_sources(current_version, repositories=UPDATE_SOURCES, timeout=5):
    """Return the newest release found across the trusted application sources."""
    sources = tuple(repositories)
    releases = []
    errors = []
    for repository in sources:
        try:
            release = check_latest(current_version, repository, timeout)
        except (RuntimeError, ValueError) as exc:
            errors.append(str(exc))
        else:
            if release:
                releases.append(release)
    if not releases:
        if errors and len(errors) == len(sources):
            raise RuntimeError("; ".join(errors))
        return None
    return max(releases, key=lambda release: _version(release.version))
