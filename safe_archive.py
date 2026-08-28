"""Safe archive extraction and inspection (audit findings Z-02, Z-07, Z-06).

Design notes
------------
Archive metadata is attacker-controlled, so nothing declared in a header is
trusted. Two independent defences:

1. **Limits are enforced during extraction, not after.** The previous code
   summed the declared ``Size =`` fields, then re-checked the real size only
   *after* ``7z x`` had already written everything to disk -- a report, not a
   guard. Worse, the encrypted branch skipped the pre-check entirely. Here the
   extraction runs as a monitored child process and is killed the moment the
   output directory exceeds the byte or entry budget, which is format- and
   encryption-agnostic.

2. **Only regular files are ever read back.** ``os.walk`` reports a
   symlink-to-file as a file, and both ``os.path.getsize`` and ``open()`` follow
   it -- so an archive containing ``notes.txt -> /app/.env`` previously caused
   the bot to upload the link *target*. Collection uses ``os.lstat`` and accepts
   only ``S_ISREG``, then re-validates containment via ``realpath``.

Everything is async: the old code called ``subprocess.check_output``/
``check_call`` directly on the event loop, so one archive froze every user.

Residual risk (documented, not fixed here): we rely on p7zip stripping ``..``
from member paths during extraction. The containment check below catches
anything that lands inside the extraction root, but a path that escapes the
root entirely would not appear in the walk. Keep extraction confined to a
dedicated temp directory so such an escape cannot reach application files.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import stat
import subprocess
from dataclasses import dataclass, field

from safe_paths import is_within

# Defaults are deliberately conservative; callers may tighten them.
MAX_TOTAL_BYTES = 2 * 1024 * 1024 * 1024      # 2 GiB, matches the upload ceiling
MAX_ENTRIES = 2000                            # guards "enormous file count" bombs
MAX_EXTRACT_SECONDS = 600                     # wall-clock cap on a single archive
MAX_SINGLE_FILE_BYTES = 2 * 1024 * 1024 * 1024
_POLL_INTERVAL = 0.25

# The monitor samples periodically, so a fast writer can overshoot the budget
# between polls (measured: ~60 MB overshoot on a 10 MB budget with a deflate
# bomb on fast local disk). Extraction therefore targets a *soft* budget below
# the caller's hard limit, so the real ceiling is respected even in the worst
# case. The post-extraction check still enforces the hard limit exactly.
_OVERSHOOT_ALLOWANCE = 256 * 1024 * 1024

MAX_LIST_BYTES = 2 * 1024 * 1024              # 2 MiB ceiling on raw 7z listing output

# Concurrency ceiling: extraction and listing are CPU- and disk-heavy
_EXTRACT_SLOTS = asyncio.Semaphore(2)
# A no-password placeholder. Must not contain a NUL byte (execve rejects those)
# and must be something a real archive is vanishingly unlikely to use. An empty
# password would render as a bare `-p`, which makes 7z prompt interactively.
_NO_PASSWORD = "\x01-zipper-no-password-\x01"

# ── 7z runtime discovery ──────────────────────────────────────────────────────
# On Debian 12+ / Ubuntu 24.04 the `7z` on PATH is not a binary, it is a wrapper:
#
#     #! /bin/sh
#     exec /usr/lib/7zip/7z "$@"
#
# That target path is hardcoded and absolute. Under a relocated apt install --
# notably the Heroku apt buildpack, which unpacks everything below /app/.apt --
# the wrapper is reachable but its target is not, so `sh` cannot exec and exits
# 127. The user saw that as "Failed to extract: 7z exited with 127", which reads
# exactly like a corrupt archive. So: find an executable that genuinely runs,
# call it by absolute path, and name the failure when nothing works.
_EXEC_NOT_FOUND = 127

# Ordered by format coverage. 7za and 7zr handle progressively fewer formats, so
# they are last-resort fallbacks rather than preferences.
_SEVENZIP_NAMES = ("7zz", "7z", "7za", "7zr")

# Real binaries the distro wrappers delegate to, checked directly to sidestep a
# wrapper whose hardcoded path does not resolve.
_SEVENZIP_LIB_DIRS = (
    "/usr/lib/7zip",
    "/usr/libexec/p7zip",
    "/usr/lib/p7zip",
    "/usr/local/lib/7zip",
)

_sevenzip_path: str | None = None
_sevenzip_lock = asyncio.Lock()


def _sevenzip_candidates() -> list[str]:
    """Absolute paths worth probing, most preferred first."""
    candidates: list[str] = []

    override = os.getenv("SEVENZIP_BINARY", "").strip()
    if override:
        candidates.append(override)

    for name in _SEVENZIP_NAMES:
        found = shutil.which(name)
        if found:
            candidates.append(found)

    # The apt buildpack rewrites PATH but not the wrappers' internal paths, so
    # look for the relocated copies explicitly.
    prefixes = ["", os.path.join(os.getenv("HOME", "/app"), ".apt"), "/app/.apt"]
    for prefix in prefixes:
        for lib_dir in _SEVENZIP_LIB_DIRS:
            for name in _SEVENZIP_NAMES:
                candidates.append(os.path.join(prefix + lib_dir, name))

    seen = set()
    unique = []
    for candidate in candidates:
        if candidate not in seen:
            seen.add(candidate)
            unique.append(candidate)
    return unique


def _probe_sevenzip(candidate: str) -> bool:
    """True if `candidate` actually executes and identifies itself as 7-Zip.

    Exit status alone is not enough: a wrapper that cannot exec its target still
    "runs" and returns 127, so the banner is what proves a working runtime.
    """
    try:
        proc = subprocess.run(
            [candidate],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    if proc.returncode == _EXEC_NOT_FOUND:
        return False
    return b"7-Zip" in proc.stdout or b"7-Zip" in proc.stderr


def _find_sevenzip_blocking() -> str | None:
    for candidate in _sevenzip_candidates():
        if _probe_sevenzip(candidate):
            return candidate
    return None


async def sevenzip_path() -> str:
    """Return the absolute path of a working 7z executable, resolved once.

    Raises ArchiveToolMissing when no candidate runs.
    """
    global _sevenzip_path
    if _sevenzip_path:
        return _sevenzip_path

    async with _sevenzip_lock:
        if _sevenzip_path:
            return _sevenzip_path
        # Probing spawns processes, so keep it off the event loop.
        found = await asyncio.to_thread(_find_sevenzip_blocking)
        if not found:
            raise ArchiveToolMissing(
                "The 7z runtime is missing or cannot start on this host. "
                "Install the '7zip' package, or point SEVENZIP_BINARY at the executable."
            )
        _sevenzip_path = found
        print(f"7z runtime resolved: {found}")
        return _sevenzip_path


class ArchiveError(Exception):
    """Base class for extraction failures that are safe to show a user."""


class ArchiveTooLarge(ArchiveError):
    """Output exceeded the configured byte or entry budget."""


class ArchiveTimeout(ArchiveError):
    """Extraction exceeded its wall-clock budget."""


class ArchiveFailed(ArchiveError):
    """7z exited non-zero: corrupt, unsupported, or wrong password."""


class ArchiveToolMissing(ArchiveFailed):
    """No working 7z runtime could be found.

    Subclasses ArchiveFailed so existing handlers still catch it, but callers
    that care can report it separately -- an environment problem must not be
    reported to the user as "incorrect password or corrupt archive".
    """


@dataclass
class ExtractionResult:
    files: list[str] = field(default_factory=list)
    total_bytes: int = 0
    skipped_non_regular: int = 0
    skipped_outside: int = 0


def _tree_usage(root: str) -> tuple[int, int]:
    """Return (bytes, entry_count) for regular files under ``root``.

    Uses ``lstat`` so symlinks contribute their own trivial size rather than
    their target's -- a symlink to a huge file must not trip the size guard, and
    must not mask real growth either.
    """
    total = 0
    count = 0
    stack = [root]
    while stack:
        current = stack.pop()
        try:
            with os.scandir(current) as it:
                for entry in it:
                    try:
                        st = entry.stat(follow_symlinks=False)
                    except OSError:
                        continue
                    if stat.S_ISDIR(st.st_mode):
                        stack.append(entry.path)
                    else:
                        count += 1
                        if stat.S_ISREG(st.st_mode):
                            total += st.st_size
        except OSError:
            continue
    return total, count


def collect_safe_files(root: str, *, max_single_bytes: int = MAX_SINGLE_FILE_BYTES) -> ExtractionResult:
    """Collect regular files under ``root`` that are safe to read and upload.

    Rejects symlinks, hardlink-like specials, FIFOs, devices, sockets, and
    anything whose resolved path escapes ``root``.
    """
    result = ExtractionResult()
    root_real = os.path.realpath(root)

    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        # Never descend through a symlinked directory.
        kept_dirs = []
        for d in dirnames:
            full = os.path.join(dirpath, d)
            if os.path.islink(full):
                result.skipped_non_regular += 1
                continue
            kept_dirs.append(d)
        dirnames[:] = kept_dirs

        for name in filenames:
            full = os.path.join(dirpath, name)
            try:
                st = os.lstat(full)
            except OSError:
                result.skipped_non_regular += 1
                continue

            # lstat, not stat: the whole point is to see the link itself.
            if not stat.S_ISREG(st.st_mode):
                result.skipped_non_regular += 1
                continue

            # A regular file can still be reached via a symlinked parent that
            # points outside the root.
            if not is_within(root_real, full):
                result.skipped_outside += 1
                continue

            if st.st_size > max_single_bytes:
                continue

            result.files.append(full)
            result.total_bytes += st.st_size

    return result


async def _monitor_and_kill(proc: asyncio.subprocess.Process, dest: str,
                            max_bytes: int, max_entries: int) -> str | None:
    """Poll ``dest`` while ``proc`` runs; kill it if a budget is exceeded.

    Returns a reason string if the process was killed, else ``None``.
    """
    while proc.returncode is None:
        await asyncio.sleep(_POLL_INTERVAL)
        used, count = _tree_usage(dest)
        reason = None
        if used > max_bytes:
            reason = f"output exceeded {max_bytes} bytes"
        elif count > max_entries:
            reason = f"output exceeded {max_entries} entries"
        if reason:
            try:
                proc.kill()
            except ProcessLookupError:
                pass
            return reason
    return None


async def extract_archive(
    archive_path: str,
    dest_dir: str,
    *,
    password: str = "",
    max_bytes: int = MAX_TOTAL_BYTES,
    max_entries: int = MAX_ENTRIES,
    timeout: float = MAX_EXTRACT_SECONDS,
) -> ExtractionResult:
    """Extract ``archive_path`` into ``dest_dir`` under hard resource limits.

    Raises ArchiveTooLarge / ArchiveTimeout / ArchiveFailed.
    """
    os.makedirs(dest_dir, exist_ok=True)

    # Kill early enough that inter-poll overshoot cannot exceed the hard limit.
    soft_bytes = max(max_bytes - _OVERSHOOT_ALLOWANCE, max_bytes // 2)

    # An empty password would render as a bare `-p`, which makes 7z *prompt*.
    # With stdin at DEVNULL that is an immediate EOF rather than a hang, but a
    # placeholder keeps the intent explicit and the failure mode clean.
    pw = password if password else _NO_PASSWORD
    sevenzip = await sevenzip_path()

    async with _EXTRACT_SLOTS:
        proc = await asyncio.create_subprocess_exec(
            sevenzip, "x", f"-o{dest_dir}", f"-p{pw}", "-y",
            "-mmt=2", "-bso0", "-bse0", "-bsp0",
            archive_path,
            stdin=asyncio.subprocess.DEVNULL,   # never block on a prompt
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )

        monitor = asyncio.create_task(
            _monitor_and_kill(proc, dest_dir, soft_bytes, max_entries)
        )
        try:
            await asyncio.wait_for(proc.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            try:
                proc.kill()
            except ProcessLookupError:
                pass
            await proc.wait()
            raise ArchiveTimeout("extraction timed out")
        finally:
            kill_reason = None
            if monitor.done():
                kill_reason = monitor.result()
            else:
                monitor.cancel()
                try:
                    kill_reason = await monitor
                except asyncio.CancelledError:
                    kill_reason = None

    if kill_reason:
        raise ArchiveTooLarge(kill_reason)

    if proc.returncode == _EXEC_NOT_FOUND:
        # The resolved executable stopped working mid-flight (a wrapper whose
        # target went away). Re-resolve on the next call rather than caching it.
        global _sevenzip_path
        _sevenzip_path = None
        raise ArchiveToolMissing(f"{sevenzip} could not be executed")

    if proc.returncode != 0:
        raise ArchiveFailed(f"7z exited with {proc.returncode}")

    result = collect_safe_files(dest_dir)

    # Belt and braces: the monitor samples periodically, so a very fast write
    # burst between polls could land under the wire.
    if result.total_bytes > max_bytes:
        raise ArchiveTooLarge(f"extracted {result.total_bytes} bytes")
    if len(result.files) > max_entries:
        raise ArchiveTooLarge(f"extracted {len(result.files)} entries")

    return result


async def list_archive(archive_path: str, *, timeout: float = 60.0) -> tuple[str, bool]:
    """Return (raw 7z listing, exited_ok) without blocking the event loop or exhausting memory."""
    sevenzip = await sevenzip_path()
    async with _EXTRACT_SLOTS:
        proc = await asyncio.create_subprocess_exec(
            sevenzip, "l", "-slt", "-mmt=2", f"-p{_NO_PASSWORD}", archive_path,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        try:
            out, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            try:
                proc.kill()
            except ProcessLookupError:
                pass
            await proc.wait()
            raise ArchiveTimeout("listing timed out")

        if len(out) > MAX_LIST_BYTES:
            out = out[:MAX_LIST_BYTES]
        if proc.returncode == _EXEC_NOT_FOUND:
            global _sevenzip_path
            _sevenzip_path = None
            raise ArchiveToolMissing(f"{sevenzip} could not be executed")
        return out.decode("utf-8", "replace"), proc.returncode == 0


def looks_encrypted(listing: str) -> bool:
    """Detect encryption from a 7z listing."""
    if not listing:
        return False
    lowered = listing.lower()
    return (
        "encrypted = +" in lowered
        or "wrong password" in lowered
        or "characteristics = encrypted" in lowered
        or "cannot open encrypted archive" in lowered
        or "enter password" in lowered
        or "is encrypted" in lowered
    )
