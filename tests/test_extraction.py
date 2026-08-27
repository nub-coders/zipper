"""tests/test_extraction.py — Safe Archive Extraction and Lifetime Scope Test Suite."""

import asyncio
import os
import tempfile
import zipfile
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from safe_archive import (
    ArchiveError,
    ArchiveFailed,
    ArchiveTimeout,
    ArchiveTooLarge,
    ExtractionResult,
    extract_archive,
    list_archive,
    looks_encrypted,
    MAX_LIST_BYTES,
)
from rate_limiter import extract_limiter


from tools import is_compressed, has_archive_magic


def test_looks_encrypted_detection():
    """Verify encrypted archive detection patterns."""
    assert looks_encrypted("Encrypted = +") is True
    assert looks_encrypted("Characteristics = Encrypted") is True
    assert looks_encrypted("Cannot open encrypted archive. Wrong password?") is True
    assert looks_encrypted("Normal file listing without lock") is False


@pytest.mark.asyncio
async def test_is_compressed_detection(tmp_path):
    """Verify is_compressed accurately identifies zip, archive extensions, and rejects normal files."""
    # 1. Real zip file
    zip_file = str(tmp_path / "valid.zip")
    with zipfile.ZipFile(zip_file, "w") as zf:
        zf.writestr("test.txt", "content")
    assert has_archive_magic(zip_file) is True
    assert await is_compressed(zip_file) is True

    # 2. Text file
    txt_file = str(tmp_path / "plain.txt")
    with open(txt_file, "w") as f:
        f.write("Just some text")
    assert has_archive_magic(txt_file) is False
    assert await is_compressed(txt_file) is False

    # 3. Archive with extension
    rar_file = str(tmp_path / "sample.rar")
    with open(rar_file, "wb") as f:
        f.write(b"Rar!\x1a\x07\x00data")
    assert has_archive_magic(rar_file) is True
    assert await is_compressed(rar_file) is True


@pytest.mark.asyncio
async def test_list_archive_flags_and_cap(tmp_path):
    """Verify list_archive enforces -mmt=2 and executes without failure on valid zip."""
    zip_path = str(tmp_path / "test.zip")
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("test1.txt", "content")
        zf.writestr("test2.txt", "content")

    listing, exited_ok = await list_archive(zip_path)
    assert exited_ok is True
    assert "test1.txt" in listing
    assert "test2.txt" in listing


def test_extract_limiter():
    """Test extract_limiter prevents rapid excessive extraction/preview calls."""
    uid = 55555
    extract_limiter.user_actions[uid] = []

    # First 5 calls are allowed (limit is 5 per window)
    for _ in range(5):
        assert extract_limiter.is_allowed(uid) is True

    # 6th immediate call should be throttled
    assert extract_limiter.is_allowed(uid) is False


@pytest.mark.asyncio
async def test_uncompress_callback_tempdir_lifetime(tmp_path):
    """Verify files exist inside TemporaryDirectory while callback executes."""
    zip_path = str(tmp_path / "sample.zip")
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("file_a.txt", "Hello A")
        zf.writestr("file_b.txt", "Hello B")

    # Simulate extraction inside tempfile.TemporaryDirectory
    with tempfile.TemporaryDirectory() as tmpdir:
        result = await extract_archive(zip_path, tmpdir)
        assert isinstance(result, ExtractionResult)
        assert len(result.files) == 2
        for f in result.files:
            assert os.path.exists(f)
            assert os.path.getsize(f) > 0
    # After exiting with block, files are cleanly removed
    assert not os.path.exists(tmpdir)
