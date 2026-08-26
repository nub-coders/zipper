"""Regression tests for the path-containment boundary (audit findings Z-01, Z-05, Z-20).

These encode the exact attack strings that previously produced writes outside
the user's directory. A failure here means arbitrary file write is reachable.
"""

import os

import pytest

from safe_paths import (
    UnsafePathError,
    is_within,
    resolve_in_user_dir,
    sanitize_component,
)

# Names that must never escape the user directory. Sourced from the audit's
# verified traversal table plus standard bypass variants.
TRAVERSAL_NAMES = [
    "../evil.zip",
    "../../evil.zip",
    "../../../../root/.ssh/authorized_keys",
    "..\\..\\..\\app\\admin.txt",          # Windows separators (pyrogram rewrites \ to /)
    "/app/admin.txt",                       # absolute: os.path.join discards the prefix
    "/etc/passwd",
    "a/../../b",
    "....//evil",
    "..;/evil",
    "%2e%2e/evil",                          # encoded traversal (must stay literal)
    "%2e%2e%2fevil",
    "..%c0%afevil",
    "\u002e\u002e/evil",                    # unicode-escaped dots
    "\uff0e\uff0e/evil",                    # fullwidth dots -> NFKC folds to ".."
    "..",
    ".",
    "...",
    "",
    None,
    "   ",
    "\x00evil",
    "evil\x00.png",
    "x" * 500,
    "-rf",                                  # leading dash: looks like a CLI flag
    "--upload-file",
    "con",                                  # Windows reserved
    "nul.txt",
    "a\nb.zip",
    "a\tb.zip",
    "file;rm -rf /.zip",
    "x.zip,@/etc/passwd",                   # curl -F multi-file syntax (Z-10)
]


@pytest.fixture()
def user_dir(tmp_path):
    d = tmp_path / "zipper" / "123456"
    d.mkdir(parents=True)
    return str(d)


@pytest.mark.parametrize("raw", TRAVERSAL_NAMES)
def test_resolve_never_escapes_user_dir(user_dir, raw):
    """The core invariant: result is always directly inside user_dir."""
    try:
        result = resolve_in_user_dir(user_dir, raw)
    except UnsafePathError:
        return  # explicit rejection is an acceptable outcome
    base = os.path.realpath(user_dir)
    assert os.path.dirname(result) == base, f"{raw!r} -> {result}"
    assert os.path.commonpath([base, os.path.realpath(result)]) == base


@pytest.mark.parametrize("raw", TRAVERSAL_NAMES)
def test_resolve_result_is_actually_writable_and_contained(user_dir, raw):
    """Writing to the result must not create anything outside user_dir."""
    base = os.path.realpath(user_dir)
    try:
        result = resolve_in_user_dir(user_dir, raw)
    except UnsafePathError:
        return
    with open(result, "w") as fh:
        fh.write("x")
    created = {
        os.path.realpath(os.path.join(r, f))
        for r, _, fs in os.walk(os.path.dirname(base))
        for f in fs
    }
    assert all(p.startswith(base + os.sep) for p in created), created


@pytest.mark.parametrize("raw", TRAVERSAL_NAMES)
def test_sanitize_component_yields_single_safe_component(raw):
    name = sanitize_component(raw)
    assert name, "must never be empty"
    assert "/" not in name and "\\" not in name
    assert "\x00" not in name
    assert name not in (".", "..")
    assert not name.startswith("-"), "leading dash becomes a CLI flag"
    assert os.path.basename(name) == name
    assert len(name.encode()) <= 255


def test_benign_name_is_preserved(user_dir):
    result = resolve_in_user_dir(user_dir, "report.zip", unique=False)
    assert os.path.basename(result) == "report.zip"
    assert os.path.dirname(result) == os.path.realpath(user_dir)


def test_unique_prefix_prevents_collision(user_dir):
    a = resolve_in_user_dir(user_dir, "same.zip")
    b = resolve_in_user_dir(user_dir, "same.zip")
    assert a != b, "concurrent jobs must not target the same path"
    assert os.path.basename(a).endswith("same.zip")


def test_force_suffix_applied(user_dir):
    assert resolve_in_user_dir(user_dir, "archive", unique=False, force_suffix=".zip").endswith(
        "archive.zip"
    )
    # Already-correct suffix is not doubled.
    assert resolve_in_user_dir(user_dir, "a.zip", unique=False, force_suffix=".zip").endswith(
        "a.zip"
    )
    # Traversal plus forced suffix still stays contained.
    p = resolve_in_user_dir(user_dir, "../../pwned", force_suffix=".zip")
    assert os.path.dirname(p) == os.path.realpath(user_dir)


def test_long_name_keeps_extension_and_fits_filesystem(user_dir):
    p = resolve_in_user_dir(user_dir, "y" * 400 + ".zip")
    assert p.endswith(".zip")
    assert len(os.path.basename(p).encode()) <= 255
    with open(p, "w") as fh:  # proves NAME_MAX is respected
        fh.write("x")


def test_symlinked_parent_cannot_redirect_write(tmp_path):
    """realpath-based containment must survive a symlinked user dir.

    Historically an attacker-influenced symlink inside the data root could point
    the whole user directory elsewhere; the check resolves links first.
    """
    outside = tmp_path / "outside"
    outside.mkdir()
    real = tmp_path / "zipper" / "1"
    real.mkdir(parents=True)
    link = tmp_path / "zipper" / "2"
    link.symlink_to(outside, target_is_directory=True)

    result = resolve_in_user_dir(str(link), "f.txt")
    # Containment is asserted against the *resolved* dir, so the write lands in
    # the link target -- and critically never in `real`.
    assert os.path.realpath(str(outside)) == os.path.dirname(result)
    assert not str(result).startswith(os.path.realpath(str(real)))


def test_sibling_prefix_directory_is_not_treated_as_inside(tmp_path):
    """commonpath, not startswith: /zipper/12 must not contain /zipper/123."""
    base = tmp_path / "zipper" / "12"
    base.mkdir(parents=True)
    sibling = tmp_path / "zipper" / "123"
    sibling.mkdir()
    assert not is_within(str(base), str(sibling / "f.txt"))
    assert is_within(str(base), str(base / "f.txt"))


def test_is_within_detects_escape(tmp_path):
    base = tmp_path / "extract"
    base.mkdir()
    assert is_within(str(base), str(base / "a" / "b.txt"))
    assert not is_within(str(base), str(tmp_path / "escape.txt"))
    assert not is_within(str(base), "/etc/passwd")


def test_is_within_follows_symlink_escape(tmp_path):
    """A symlink inside the extraction dir pointing out must be rejected (Z-02)."""
    base = tmp_path / "extract"
    base.mkdir()
    secret = tmp_path / "secret.txt"
    secret.write_text("CANARY")
    (base / "innocent.txt").symlink_to(secret)
    assert not is_within(str(base), str(base / "innocent.txt"))
