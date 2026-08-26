"""Regression tests for safe archive handling (audit findings Z-02, Z-07).

These exercise the real ``7z`` binary. They are skipped when it is absent so the
rest of the suite still runs, but CI must install ``p7zip-full`` or the two
highest-value guards here go unverified.

Environment note: verified against 7-Zip 23.01. p7zip's own symlink handling is
part of the defence, so the ``test_symlink_*`` cases double as an upstream
behaviour check -- if a future version starts materialising escaping links, they
fail and tell us the Python-side guard is now load-bearing.
"""

import asyncio
import os
import shutil
import stat
import zipfile

import pytest

from safe_archive import (
    ArchiveFailed,
    ArchiveTooLarge,
    collect_safe_files,
    extract_archive,
    looks_encrypted,
)

requires_7z = pytest.mark.skipif(
    shutil.which("7z") is None, reason="7z not installed"
)

CANARY = "CANARY-SHOULD-NEVER-BE-UPLOADED"


# ---------------------------------------------------------------- collection --

def test_collect_rejects_symlink_to_outside_file(tmp_path):
    """The core Z-02 guard: a symlink must never be collected for upload."""
    secret = tmp_path / "secret.txt"
    secret.write_text(CANARY)
    root = tmp_path / "extract"
    root.mkdir()
    (root / "innocent.txt").symlink_to(secret)
    (root / "real.txt").write_text("fine")

    result = collect_safe_files(str(root))

    assert [os.path.basename(f) for f in result.files] == ["real.txt"]
    assert result.skipped_non_regular == 1
    # Prove the canary is unreachable through the returned set.
    for f in result.files:
        assert CANARY not in open(f).read()


def test_collect_rejects_symlink_to_absolute_path(tmp_path):
    root = tmp_path / "extract"
    root.mkdir()
    (root / "passwd.txt").symlink_to("/etc/passwd")
    result = collect_safe_files(str(root))
    assert result.files == []
    assert result.skipped_non_regular == 1


def test_collect_does_not_descend_symlinked_directory(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text(CANARY)
    root = tmp_path / "extract"
    root.mkdir()
    (root / "sub").symlink_to(outside, target_is_directory=True)

    result = collect_safe_files(str(root))

    assert result.files == []
    assert result.skipped_non_regular >= 1


def test_collect_rejects_fifo_and_specials(tmp_path):
    root = tmp_path / "extract"
    root.mkdir()
    os.mkfifo(str(root / "pipe"))          # would block forever on read
    (root / "ok.bin").write_bytes(b"x")

    result = collect_safe_files(str(root))

    assert [os.path.basename(f) for f in result.files] == ["ok.bin"]
    assert result.skipped_non_regular == 1


def test_collect_accepts_nested_regular_files(tmp_path):
    root = tmp_path / "extract"
    (root / "a" / "b").mkdir(parents=True)
    (root / "a" / "b" / "deep.txt").write_text("hello")
    (root / "top.txt").write_text("hi")

    result = collect_safe_files(str(root))

    assert sorted(os.path.basename(f) for f in result.files) == ["deep.txt", "top.txt"]
    assert result.total_bytes == 7


def test_collect_skips_oversized_single_file(tmp_path):
    root = tmp_path / "extract"
    root.mkdir()
    (root / "big.bin").write_bytes(b"x" * 1000)
    (root / "small.bin").write_bytes(b"x")

    result = collect_safe_files(str(root), max_single_bytes=100)

    assert [os.path.basename(f) for f in result.files] == ["small.bin"]


# ---------------------------------------------------------------- extraction --

def _make_bomb(path, uncompressed_bytes):
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        z.writestr("bomb.bin", b"\0" * uncompressed_bytes)


@requires_7z
def test_decompression_bomb_is_killed_mid_extraction(tmp_path):
    """Z-07: limits must bind during extraction, not after it completes."""
    bomb = tmp_path / "bomb.zip"
    _make_bomb(bomb, 300 * 1024 * 1024)
    assert bomb.stat().st_size < 1_000_000, "bomb should be tiny on the wire"

    dest = tmp_path / "out"
    with pytest.raises(ArchiveTooLarge):
        asyncio.run(
            extract_archive(str(bomb), str(dest), max_bytes=8 * 1024 * 1024, timeout=120)
        )

    # The hard limit must hold despite the sampling interval.
    used = sum(
        os.path.getsize(os.path.join(r, f))
        for r, _, fs in os.walk(dest)
        for f in fs
    )
    assert used < 8 * 1024 * 1024 + 256 * 1024 * 1024, f"overshoot too large: {used}"


@requires_7z
def test_legitimate_archive_still_extracts(tmp_path):
    src = tmp_path / "ok.zip"
    with zipfile.ZipFile(src, "w") as z:
        z.writestr("a.txt", "alpha")
        z.writestr("nested/b.txt", "beta")

    dest = tmp_path / "out"
    result = asyncio.run(extract_archive(str(src), str(dest), max_bytes=10 * 1024 * 1024))

    assert sorted(os.path.basename(f) for f in result.files) == ["a.txt", "b.txt"]
    assert result.total_bytes == 9


@requires_7z
def test_entry_count_limit_enforced(tmp_path):
    src = tmp_path / "many.zip"
    with zipfile.ZipFile(src, "w") as z:
        for i in range(500):
            z.writestr(f"f{i}.txt", "x")

    dest = tmp_path / "out"
    with pytest.raises(ArchiveTooLarge):
        asyncio.run(extract_archive(str(src), str(dest), max_entries=50, timeout=120))


@requires_7z
def test_corrupt_archive_raises_archive_failed(tmp_path):
    bad = tmp_path / "bad.zip"
    bad.write_bytes(b"PK\x03\x04 this is not a real archive")
    dest = tmp_path / "out"
    with pytest.raises(ArchiveFailed):
        asyncio.run(extract_archive(str(bad), str(dest)))


@requires_7z
def test_wrong_password_raises_rather_than_hanging(tmp_path):
    """A bad password must fail fast, not block on an interactive prompt."""
    payload = tmp_path / "x.txt"
    payload.write_text("data")
    src = tmp_path / "enc.7z"
    os.system(f"7z a -p'correct-horse' -mhe=on {src} {payload} >/dev/null 2>&1")
    if not src.exists():
        pytest.skip("could not create encrypted fixture")

    dest = tmp_path / "out"
    with pytest.raises((ArchiveFailed, ArchiveTooLarge)):
        asyncio.run(
            extract_archive(str(src), str(dest), password="wrong-password", timeout=30)
        )


@requires_7z
def test_no_password_archive_does_not_prompt(tmp_path):
    """Regression: the placeholder password must not contain a NUL byte.

    execve rejects embedded NULs, which previously raised ValueError before 7z
    even started.
    """
    src = tmp_path / "plain.zip"
    with zipfile.ZipFile(src, "w") as z:
        z.writestr("a.txt", "alpha")
    dest = tmp_path / "out"
    result = asyncio.run(extract_archive(str(src), str(dest), timeout=30))
    assert len(result.files) == 1


@requires_7z
def test_symlink_in_tar_is_never_uploaded(tmp_path):
    """End-to-end Z-02: tar with a symlink -> nothing readable escapes.

    p7zip 23.01 rewrites absolute targets under the extraction root (leaving a
    dangling link) and refuses escaping relative ones. Either way the collector
    must return no symlink.
    """
    secret = tmp_path / "secret.txt"
    secret.write_text(CANARY)
    build = tmp_path / "build"
    build.mkdir()
    (build / "readme.txt").write_text("harmless")
    os.symlink(str(secret), str(build / "notes.txt"))
    tar = tmp_path / "links.tar"
    assert os.system(f"tar -cf {tar} -C {build} .") == 0

    dest = tmp_path / "out"
    result = asyncio.run(extract_archive(str(tar), str(dest), max_bytes=10 * 1024 * 1024))

    names = [os.path.basename(f) for f in result.files]
    assert "notes.txt" not in names, "symlink must not be collected"
    for f in result.files:
        assert stat.S_ISREG(os.lstat(f).st_mode)
        assert CANARY not in open(f, "rb").read().decode("utf-8", "replace")


@requires_7z
def test_zip_with_unix_symlink_attr_is_never_uploaded(tmp_path):
    """Same guarantee for ZIP members carrying S_IFLNK in external_attr."""
    secret = tmp_path / "secret.txt"
    secret.write_text(CANARY)

    src = tmp_path / "link.zip"
    with zipfile.ZipFile(src, "w") as z:
        for name, target in [("abs.txt", str(secret)), ("rel.txt", "../secret.txt")]:
            zi = zipfile.ZipInfo(name)
            zi.create_system = 3
            zi.external_attr = (stat.S_IFLNK | 0o777) << 16
            z.writestr(zi, target)
        z.writestr("plain.txt", "harmless")

    dest = tmp_path / "out"
    try:
        result = asyncio.run(extract_archive(str(src), str(dest), max_bytes=10 * 1024 * 1024))
    except ArchiveFailed:
        # p7zip refuses the archive outright -- also an acceptable outcome.
        return

    for f in result.files:
        assert stat.S_ISREG(os.lstat(f).st_mode)
        assert CANARY not in open(f, "rb").read().decode("utf-8", "replace")


def test_looks_encrypted_detection():
    assert looks_encrypted("Path = a.txt\nEncrypted = +\n")
    assert looks_encrypted("Wrong password : something")
    assert not looks_encrypted("Path = a.txt\nEncrypted = -\n")
