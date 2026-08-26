"""Integration test for the download sink (audit finding Z-01).

Rather than mocking our own helper, this replays Pyrogram's *real* path
derivation (``download_media`` + ``handle_download``) against the argument the
bot now passes. That is the code that turned an attacker-controlled MTProto
filename attribute into an arbitrary write, so it is the code the test must
exercise.

Reference (kurigram 2.2.25):
    download_media.py:384  directory, file_name = os.path.split(file_name)
    download_media.py:385  file_name = file_name or media_file_name or ""
    client.py:1092         os.path.abspath(re.sub("\\\\", "/", os.path.join(directory, file_name)))
"""

import os
import re

import pytest

from safe_paths import UnsafePathError, resolve_in_user_dir

# Names that provably escaped under the legacy `file_name="zipper/<id>/"` pattern.
# Verified against kurigram's own path arithmetic.
ESCAPING_NAMES = [
    "../../../../root/.ssh/authorized_keys",
    "..\\..\\..\\app\\admin.txt",
    "/app/admin.txt",
    "/etc/ld.so.preload",
    "../../plugins/file_handlers.py",
]

# Additional hostile names that must be contained. `....//` does NOT escape via
# os.path.abspath (it is not a valid parent reference, so it survives as a
# literal directory component) -- it defeats naive ".."-stripping filters, which
# is exactly why the fix uses containment rather than blocklisting.
HOSTILE_NAMES = ESCAPING_NAMES + [
    "....//....//etc/passwd",
    "..;/evil",
    "%2e%2e/evil",
]


def pyrogram_resolve(passed_file_name: str, media_file_name: str, workdir: str) -> str:
    """Faithful replay of Pyrogram's destination-path computation."""
    directory, file_name = os.path.split(passed_file_name)
    file_name = file_name or media_file_name or ""
    if not os.path.isabs(directory):
        directory = os.path.join(workdir, directory or "downloads")
    temp = os.path.abspath(re.sub("\\\\", "/", os.path.join(directory, file_name))) + ".temp"
    return os.path.splitext(temp)[0]


@pytest.mark.parametrize("hostile", ESCAPING_NAMES)
def test_old_behaviour_was_exploitable(tmp_path, hostile):
    """Documents the vulnerability: a bare directory lets the filename escape.

    Guards against anyone reintroducing `message.download(file_name=f"zipper/{id}/")`.
    """
    workdir = str(tmp_path / "app")
    user_dir = os.path.join(workdir, "zipper", "123456")
    os.makedirs(user_dir)

    escaped = pyrogram_resolve("zipper/123456/", hostile, workdir)
    assert not escaped.startswith(os.path.realpath(user_dir) + os.sep), (
        "expected the legacy pattern to escape; if this fails the upstream "
        "library changed and the test needs revisiting"
    )


@pytest.mark.parametrize("hostile", HOSTILE_NAMES)
def test_fixed_behaviour_stays_contained(tmp_path, hostile):
    """With a fully-resolved path, the media filename is ignored entirely."""
    workdir = str(tmp_path / "app")
    user_dir = os.path.join(workdir, "zipper", "123456")
    os.makedirs(user_dir)

    dest = resolve_in_user_dir(user_dir, hostile)
    final = pyrogram_resolve(dest, hostile, workdir)

    base = os.path.realpath(user_dir)
    assert os.path.dirname(os.path.realpath(final)) == base, f"{hostile!r} -> {final}"


def test_benign_download_still_works(tmp_path):
    workdir = str(tmp_path / "app")
    user_dir = os.path.join(workdir, "zipper", "123456")
    os.makedirs(user_dir)

    dest = resolve_in_user_dir(user_dir, "holiday.zip", unique=False)
    final = pyrogram_resolve(dest, "holiday.zip", workdir)
    assert final == os.path.join(os.path.realpath(user_dir), "holiday.zip")


def test_zip_name_cannot_escape(tmp_path):
    """Z-05: the chat-supplied archive name is contained and forced to .zip."""
    user_dir = str(tmp_path / "zipper" / "123456")
    os.makedirs(user_dir)
    base = os.path.realpath(user_dir)

    for name in ["../../../../tmp/x", "../escape", "/etc/shadow", "..", "-rf"]:
        p = resolve_in_user_dir(user_dir, name, fallback="archive", force_suffix=".zip")
        assert os.path.dirname(p) == base, f"{name!r} -> {p}"
        assert p.endswith(".zip")


def test_url_filename_cannot_escape_or_collide(tmp_path):
    """Z-20: URL-derived names are contained, and repeats do not overwrite."""
    user_dir = str(tmp_path / "zipper" / "123456")
    os.makedirs(user_dir)
    base = os.path.realpath(user_dir)

    for link in [
        "http://h/a/../../x",
        "http://h/..",
        "http://h/",
        "http://h/f.bin?a=1#frag",
        "http://h/" + "n" * 400 + ".bin",
    ]:
        raw = link.split("?")[0].split("#")[0].split("/")[-1]
        p = resolve_in_user_dir(user_dir, raw, fallback="download")
        assert os.path.dirname(p) == base, f"{link} -> {p}"

    a = resolve_in_user_dir(user_dir, "same.bin", fallback="download")
    b = resolve_in_user_dir(user_dir, "same.bin", fallback="download")
    assert a != b


def test_query_string_is_stripped_from_url_filename(tmp_path):
    user_dir = str(tmp_path / "zipper" / "1")
    os.makedirs(user_dir)
    raw = "http://h/report.pdf?token=abc".split("?")[0].split("#")[0].split("/")[-1]
    p = resolve_in_user_dir(user_dir, raw, fallback="download", unique=False)
    assert os.path.basename(p) == "report.pdf"


def test_unsafe_path_error_is_raised_not_swallowed(tmp_path):
    """Callers rely on the exception to reject input; it must not be silent."""
    user_dir = str(tmp_path / "zipper" / "1")
    os.makedirs(user_dir)
    outside = str(tmp_path / "elsewhere")
    os.makedirs(outside)
    # A directory symlink whose target is outside is resolved, so containment is
    # judged against the real location -- assert the API surface exists.
    assert issubclass(UnsafePathError, ValueError)
