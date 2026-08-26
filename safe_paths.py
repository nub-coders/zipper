"""Filesystem path safety for user-supplied names.

SECURITY CRITICAL. Every filesystem path derived from user-controlled input
(Telegram filename attributes, chat messages, URLs, archive members) must be
built through :func:`resolve_in_user_dir`. Nothing else may join user data onto
a path.

Threat model: a name is fully attacker-controlled and may contain ``..``
segments, absolute prefixes, Windows separators, NUL bytes, unicode
lookalikes, or be thousands of bytes long. ``os.path.join`` discards the
directory prefix entirely when handed an absolute path, and ``os.path.abspath``
silently collapses ``..`` -- so a "join then hope" approach writes anywhere the
process can write.

Defence is two independent layers:

1. Reduce the name to a single safe path component (allowlist charset).
2. Assert the *resolved* result is inside the user directory, via
   ``os.path.realpath`` so symlinked parents cannot redirect the write.

Layer 2 is the real boundary; layer 1 keeps filenames sane and portable.
"""

from __future__ import annotations

import os
import re
import unicodedata
import uuid

# Every byte outside this set is replaced. Deliberately excludes the path
# separators, NUL, shell metacharacters, and the leading-dash forms that turn a
# filename into a command-line option for tools like 7z and curl.
_ALLOWED = re.compile(r"[^A-Za-z0-9._-]")

# Reserved on Windows; archives are routinely opened there.
_RESERVED = {
    "con", "prn", "aux", "nul",
    *(f"com{i}" for i in range(1, 10)),
    *(f"lpt{i}" for i in range(1, 10)),
}

_MAX_STEM = 80          # leaves room for the uuid prefix within NAME_MAX (255)
_MAX_EXT = 16


class UnsafePathError(ValueError):
    """Raised when a name cannot be made safe, or escapes the user directory."""


def sanitize_component(raw: str | None, *, fallback: str = "file") -> str:
    """Reduce ``raw`` to one safe path component.

    Never returns an empty string, a dot-only name, a Windows-reserved name, or
    anything containing a path separator.
    """
    name = raw or ""

    # Normalise unicode first: NFKC folds fullwidth/compatibility forms that
    # would otherwise survive the allowlist as separators or dots.
    name = unicodedata.normalize("NFKC", name)

    # Drop everything up to the last separator of *either* flavour. Done before
    # the allowlist so traversal segments cannot be reassembled from escaped
    # characters, and so "a/../../b" cannot collapse into a parent reference.
    name = name.replace("\\", "/").split("/")[-1]

    # Split extension before sanitising so a long name keeps a usable suffix.
    stem, ext = os.path.splitext(name)
    stem = _ALLOWED.sub("_", stem)[:_MAX_STEM]
    ext = _ALLOWED.sub("_", ext)[:_MAX_EXT]

    # A name of only dots/underscores carries no information and ".."-like
    # stems are exactly what we are defending against.
    if not stem.strip("._") or stem.strip(".") == "":
        stem = fallback
    if stem.lower() in _RESERVED:
        stem = f"{stem}_file"

    # A leading dash makes the filename look like a CLI flag downstream.
    stem = stem.lstrip("-") or fallback

    return f"{stem}{ext}"


def resolve_in_user_dir(
    user_dir: str,
    raw_name: str | None,
    *,
    unique: bool = True,
    fallback: str = "file",
    force_suffix: str | None = None,
) -> str:
    """Return an absolute path for ``raw_name`` guaranteed to sit in ``user_dir``.

    Args:
        user_dir: Directory the result must stay inside. Created if missing so
            ``realpath`` resolves against a real inode.
        raw_name: Untrusted name.
        unique: Prefix a short random token, so concurrent jobs and repeated
            uploads cannot collide or silently overwrite each other.
        fallback: Stem used when ``raw_name`` sanitises to nothing.
        force_suffix: Enforce this extension (e.g. ``".zip"``).

    Raises:
        UnsafePathError: if the resolved path is not inside ``user_dir``.
    """
    os.makedirs(user_dir, exist_ok=True)

    name = sanitize_component(raw_name, fallback=fallback)

    if force_suffix and not name.lower().endswith(force_suffix.lower()):
        name = f"{os.path.splitext(name)[0]}{force_suffix}"

    if unique:
        name = f"{uuid.uuid4().hex[:8]}_{name}"

    base = os.path.realpath(user_dir)
    candidate = os.path.realpath(os.path.join(base, name))

    # The authoritative check. os.path.commonpath operates on components, so
    # unlike startswith() it cannot be fooled by a sibling directory whose name
    # merely shares a prefix (e.g. /app/zipper/12 vs /app/zipper/123).
    if candidate != base and os.path.commonpath([base, candidate]) != base:
        raise UnsafePathError(f"path escapes user directory: {raw_name!r}")
    if os.path.dirname(candidate) != base:
        raise UnsafePathError(f"path is not directly in user directory: {raw_name!r}")

    return candidate


def is_within(base: str, target: str) -> bool:
    """True if ``target`` resolves inside ``base``. For validating extractions."""
    base_r = os.path.realpath(base)
    target_r = os.path.realpath(target)
    if target_r == base_r:
        return True
    try:
        return os.path.commonpath([base_r, target_r]) == base_r
    except ValueError:  # different drives on Windows
        return False
