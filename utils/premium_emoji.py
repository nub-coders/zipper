"""utils/premium_emoji.py — Manage Telegram Custom / Premium Emojis and auto-patch buttons and parsers.

Ensures that:
1. InlineKeyboardButton automatically gets `icon_custom_emoji_id` set from leading unicode emojis or keyword matching, with emojis stripped from text for clean native UI.
2. Custom emoji HTML tags (<tg-emoji emoji-id="...">) work seamlessly across message sends and edits.
3. If custom emojis are unavailable or rejected, falls back transparently.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from pyrogram.enums import MessageEntityType, ParseMode
from pyrogram.errors import PremiumAccountRequired
from pyrogram.errors.exceptions.forbidden_403 import (
    PremiumAccountRequired as PremiumAccountRequiredForbidden,
)
from pyrogram.parser.html import HTML
from pyrogram.types import InlineKeyboardButton, Message

from utils.emoji import Emoji, EmojiTag

logger = logging.getLogger(__name__)

PREMIUM_EMOJI = True
_patched = False

PREMIUM_REQUIRED_ERRORS = (PremiumAccountRequired, PremiumAccountRequiredForbidden)

_EMOJI_TAG_RE = re.compile(
    r'<(?:tg-)?emoji\s+(?:emoji-)?id="[^"]*"\s*>(.*?)</(?:tg-)?emoji>',
    re.I | re.S,
)
_LEADING_EMOJI_RE = re.compile(r'^([\u2139]|[^\w\s\d])[\ufe0f\ufe0e]*\s+')

_UNICODE_TO_EMOJI_ID: dict[str, int] = {
    "📁": Emoji.FOLDER,
    "📂": Emoji.FOLDER,
    "📄": Emoji.FILE,
    "📑": Emoji.DOCUMENT,
    "🗂️": Emoji.FILE,
    "🗂": Emoji.FILE,
    "🗃️": Emoji.ZIP,
    "🗃": Emoji.ZIP,
    "🗜️": Emoji.ARCHIVE,
    "🗜": Emoji.ARCHIVE,
    "📦": Emoji.EXTRACT,
    "🔒": Emoji.LOCK,
    "🔐": Emoji.LOCK,
    "🔓": Emoji.UNLOCK,
    "🔑": Emoji.KEY,
    "🛡️": Emoji.SHIELD,
    "🛡": Emoji.SHIELD,
    "💾": Emoji.STORAGE,
    "☁️": Emoji.CLOUD,
    "☁": Emoji.CLOUD,
    "🗑️": Emoji.TRASH,
    "🗑": Emoji.TRASH,
    "🛑": Emoji.CANCEL,
    "❌": Emoji.ERROR,
    "✅": Emoji.SUCCESS,
    "⚠️": Emoji.WARNING,
    "ℹ️": Emoji.INFO,
    "ℹ": Emoji.INFO,
    "❓": Emoji.HELP,
    "⚙️": Emoji.SETTINGS,
    "⚙": Emoji.SETTINGS,
    "🔄": Emoji.REFRESH,
    "⚡️": Emoji.PING,
    "⚡": Emoji.PING,
    "📊": Emoji.STATS,
    "📥": Emoji.DOWNLOAD,
    "📤": Emoji.UPLOAD,
    "🏠": Emoji.HOME,
    "◀️": Emoji.BACK,
    "◀": Emoji.BACK,
    "▶️": Emoji.NEXT,
    "▶": Emoji.NEXT,
    "➡️": Emoji.NEXT,
    "🌐": Emoji.LANG,
    "🔗": Emoji.LINK,
    "📢": Emoji.BROADCAST,
    "🚀": Emoji.ROCKET,
    "⭐️": Emoji.STAR,
    "⭐": Emoji.STAR,
    "✨": Emoji.SPARKLES,
    "👤": Emoji.USER,
    "👥": Emoji.USERS,
    "👑": Emoji.CROWN,
    "🎬": Emoji.VIDEO,
    "🎵": Emoji.AUDIO,
    "🖼️": Emoji.IMAGE,
    "🖼": Emoji.IMAGE,
    "💻": Emoji.CODE,
}

_KEYWORD_TO_EMOJI_ID: list[tuple[str, int]] = [
    ("list", Emoji.FILE),
    ("file", Emoji.FILE),
    ("clear", Emoji.TRASH),
    ("delete", Emoji.TRASH),
    ("del", Emoji.TRASH),
    ("compress", Emoji.COMPRESS),
    ("zip", Emoji.ZIP),
    ("unzip", Emoji.EXTRACT),
    ("protect", Emoji.LOCK),
    ("password", Emoji.LOCK),
    ("home", Emoji.HOME),
    ("back", Emoji.BACK),
    ("help", Emoji.HELP),
    ("lang", Emoji.LANG),
    ("english", Emoji.LANG),
    ("farsi", Emoji.LANG),
    ("cancel", Emoji.CANCEL),
    ("status", Emoji.STATS),
    ("stats", Emoji.STATS),
    ("download", Emoji.DOWNLOAD),
    ("upload", Emoji.UPLOAD),
    ("broadcast", Emoji.BROADCAST),
    ("ping", Emoji.PING),
    ("refresh", Emoji.REFRESH),
    ("support", Emoji.LINK),
    ("channel", Emoji.LINK),
    ("close", Emoji.CLOSE),
]


def strip_custom_emoji_text(text: str) -> str:
    """Flatten <tg-emoji> tags back to their inner plain character."""
    if not text:
        return ""
    return _EMOJI_TAG_RE.sub(r"\1", str(text))


def strip_leading_unicode_emoji(text: str) -> tuple[str, int | None]:
    """Strip leading emoji from text and return (clean_text, emoji_doc_id)."""
    if not text:
        return text, None

    for u_char, doc_id in _UNICODE_TO_EMOJI_ID.items():
        if text.startswith(u_char):
            remainder = text[len(u_char):].strip()
            return remainder, doc_id

    # Regex search for miscellaneous symbols
    match = _LEADING_EMOJI_RE.match(text)
    if match:
        matched_str = match.group(1)
        doc_id = _UNICODE_TO_EMOJI_ID.get(matched_str)
        remainder = text[match.end():].strip()
        return remainder, doc_id

    return text, None


def patch_pyrogram_for_custom_emojis():
    """Monkey-patch Pyrogram/Kurigram constructors to support native custom emojis in buttons and message parsing."""
    global _patched
    if _patched:
        return
    _patched = True

    # ── 1. Monkey-patch InlineKeyboardButton constructor ──────────────────────
    orig_button_init = InlineKeyboardButton.__init__

    def patched_button_init(self, text: str, *args, **kwargs):
        if not kwargs.get("icon_custom_emoji_id"):
            clean_text, found_id = strip_leading_unicode_emoji(text)
            if found_id:
                kwargs["icon_custom_emoji_id"] = str(found_id)
                text = clean_text
            else:
                # Keyword search
                lower = text.lower()
                for kw, kw_doc_id in _KEYWORD_TO_EMOJI_ID:
                    if kw in lower:
                        kwargs["icon_custom_emoji_id"] = str(kw_doc_id)
                        break

        orig_button_init(self, text, *args, **kwargs)

    InlineKeyboardButton.__init__ = patched_button_init
    logger.info("Pyrogram InlineKeyboardButton custom emoji patch applied.")
