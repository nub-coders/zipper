"""tests/test_sevenzip_resolution.py — 7z runtime discovery and the exit-127 failure mode."""

import os
import stat

import pytest

import safe_archive as sa
from safe_archive import ArchiveError, ArchiveFailed, ArchiveToolMissing


@pytest.fixture(autouse=True)
def _clear_cache():
    """The resolved path is cached module-wide; each test starts unresolved."""
    sa._sevenzip_path = None
    yield
    sa._sevenzip_path = None


@pytest.fixture
def real_sevenzip():
    found = sa._find_sevenzip_blocking()
    if not found:
        pytest.skip("no working 7z runtime on this host")
    sa._sevenzip_path = None
    return found


def _broken_wrapper(tmp_path) -> str:
    """A copy of the Debian wrapper whose hardcoded target does not exist.

    This is the shape that breaks under relocated apt installs: the script is on
    PATH and executable, but `exec` fails and sh exits 127.
    """
    path = tmp_path / "7z"
    path.write_text("#! /bin/sh\nexec /nonexistent/lib/7zip/7z \"$@\"\n")
    path.chmod(path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return str(path)


def test_probe_rejects_wrapper_that_cannot_exec(tmp_path):
    """Regression: exit 127 from the wrapper used to surface as a corrupt archive."""
    assert sa._probe_sevenzip(_broken_wrapper(tmp_path)) is False


def test_probe_accepts_a_working_binary(real_sevenzip):
    """A genuine 7-Zip identifies itself in its banner."""
    assert sa._probe_sevenzip(real_sevenzip) is True


def test_probe_rejects_a_missing_path(tmp_path):
    """A path that does not exist is not a candidate."""
    assert sa._probe_sevenzip(str(tmp_path / "definitely-absent")) is False


def test_probe_rejects_a_non_executable(tmp_path):
    """A readable but non-executable file is not a candidate."""
    path = tmp_path / "7z"
    path.write_text("not a program")
    assert sa._probe_sevenzip(str(path)) is False


async def test_resolution_skips_broken_wrapper(tmp_path, real_sevenzip, monkeypatch):
    """A broken wrapper earlier in the candidate list must not win."""
    broken = _broken_wrapper(tmp_path)
    monkeypatch.setattr(sa, "_sevenzip_candidates", lambda: [broken, real_sevenzip])

    assert await sa.sevenzip_path() == real_sevenzip


async def test_resolution_is_cached(real_sevenzip, monkeypatch):
    """Discovery spawns processes, so it must happen once per process."""
    calls = []

    def _probe(candidate):
        calls.append(candidate)
        return candidate == real_sevenzip

    monkeypatch.setattr(sa, "_sevenzip_candidates", lambda: [real_sevenzip])
    monkeypatch.setattr(sa, "_probe_sevenzip", _probe)

    first = await sa.sevenzip_path()
    second = await sa.sevenzip_path()

    assert first == second == real_sevenzip
    assert len(calls) == 1


async def test_missing_runtime_raises_named_error(tmp_path, monkeypatch):
    """With nothing runnable, the error names the environment problem."""
    monkeypatch.setattr(sa, "_sevenzip_candidates", lambda: [_broken_wrapper(tmp_path)])

    with pytest.raises(ArchiveToolMissing) as excinfo:
        await sa.sevenzip_path()

    assert "7z runtime" in str(excinfo.value)
    assert "SEVENZIP_BINARY" in str(excinfo.value)


def test_tool_missing_is_catchable_as_archive_failed():
    """Existing `except ArchiveFailed` handlers must keep working."""
    assert issubclass(ArchiveToolMissing, ArchiveFailed)
    assert issubclass(ArchiveToolMissing, ArchiveError)


def test_env_override_is_preferred(monkeypatch):
    """SEVENZIP_BINARY gives an operator an escape hatch on an odd host."""
    monkeypatch.setenv("SEVENZIP_BINARY", "/opt/custom/7zz")

    assert sa._sevenzip_candidates()[0] == "/opt/custom/7zz"


def test_candidates_include_relocated_apt_paths(monkeypatch):
    """The Heroku apt buildpack unpacks below /app/.apt, which the wrapper misses."""
    monkeypatch.setenv("HOME", "/app")

    candidates = sa._sevenzip_candidates()

    assert "/app/.apt/usr/lib/7zip/7z" in candidates
    assert len(candidates) == len(set(candidates)), "candidate list must be deduplicated"


async def test_extract_uses_resolved_binary(tmp_path, real_sevenzip):
    """End to end: a real archive still extracts through the resolved path."""
    import zipfile

    archive = tmp_path / "sample.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("note.txt", "resolved runtime")

    dest = tmp_path / "out"
    result = await sa.extract_archive(str(archive), str(dest), max_bytes=10**6, max_entries=10)

    assert [os.path.basename(f) for f in result.files] == ["note.txt"]
    assert sa._sevenzip_path == real_sevenzip
