"""utils/rich_ui.py — Bot API 10.2 & 10.3 Rich Message Helpers for Zipper Bot.

Shared, reusable builders and safe senders for native Telegram Rich Blocks:
  - <h1>-<h6> page titles and section headers
  - <table> native tabular layouts for file lists, storage stats, and diagnostics
  - <details><summary> collapsible dropdown sections
  - <blockquote expandable> expandable blockquotes for security notes / guides
  - <tg-button url="..."> native rich text buttons
  - <tg-button type="callback_data" data="..."> in-text callback buttons (usable in <td>)
  - <tg-button-row align="..."> grouped rows of rich text buttons
  - <tg-emoji emoji-id="..."> custom/premium emoji glyphs
  - InputRichMessage server-side parsing with newline & whitespace preservation
  - send_rich_message_draft / RichDraft for live animated streaming progress
  - Monospace grid table fallback (<pre>┌──┬──┐</pre>) and standard HTML fallback

Graceful degradation: Every sender safely falls back to standard MTProto send_message
with ParseMode.HTML and clean formatting if rich delivery is unsupported or rejected.
"""

from __future__ import annotations

import html as _html
import logging
import re
from typing import Any, Iterable, Sequence

from pyrogram.enums import ParseMode
from pyrogram.types import InputRichMessage, ReplyParameters

logger = logging.getLogger("pyrogram")

__all__ = [
    "RICH_AVAILABLE",
    "rich_esc",
    "rich_heading",
    "rich_note",
    "rich_table",
    "rich_button",
    "rich_button_row",
    "rich_details",
    "rich_kv_table",
    "rich_code",
    "rich_to_plain",
    "rich_caption",
    "rich_send",
    "rich_reply",
    "rich_edit",
    "rich_answer",
    "ephemeral_edit",
    "ephemeral_delete",
    "RichDraft",
]

# ── Capability Probe ─────────────────────────────────────────────────────────
try:
    from pyrogram import Client as _Client
    RICH_AVAILABLE = hasattr(_Client, "send_rich_message")
except Exception:
    RICH_AVAILABLE = False

_RICH_ONLY_TAGS = (
    "h1", "h2", "h3", "h4", "h5", "h6",
    "table", "thead", "tbody", "tr", "th", "td",
    "details", "summary", "mark", "sub", "sup",
    "tg-button", "tg-button-row", "button",
)
_BLOCK_BREAK_RE = re.compile(
    r"</(?:h[1-6]|tr|details|summary|blockquote|table|pre)>", re.I
)
_CELL_BREAK_RE = re.compile(r"</(?:th|td)>", re.I)
_EMOJI_TAG_RE = re.compile(
    r'<(?:tg-)?emoji\s+(?:emoji-)?id="[^"]*"\s*>(.*?)</(?:tg-)?emoji>', re.I | re.S
)
_ANY_TAG_RE = re.compile(r"<[^>]+>")
_RICH_TAGS_RE = re.compile(
    r"</?(?:h[1-6]|table|thead|tbody|tr|th|td|details|summary|mark|sub|sup|tg-button|tg-button-row|button)\b", re.I
)


def _has_rich_only_tags(html_text: str) -> bool:
    """Check if html_text contains Bot API 10.2+ rich tags that require InputRichMessage."""
    if not html_text:
        return False
    return bool(_RICH_TAGS_RE.search(str(html_text)))


# ── Builders ────────────────────────────────────────────────────────────────

def rich_esc(value: Any) -> str:
    """HTML-escape untrusted text (filenames, usernames, errors)."""
    if value is None:
        return ""
    return _html.escape(str(value), quote=False)


def _attr(value: Any) -> str:
    """Escape a value for use inside a double-quoted HTML attribute.

    rich_esc() leaves quotes alone, which is fine for body text but would let a
    filename containing a double quote close the attribute early and inject
    further attributes into the tag.
    """
    if value is None:
        return ""
    return _html.escape(str(value), quote=True)


def rich_heading(text: str, level: int = 1) -> str:
    """<h1>-<h6> title / section header."""
    level = max(1, min(6, int(level)))
    return f"<h{level}>{text}</h{level}>"


def rich_note(text: str, expandable: bool = False) -> str:
    """<blockquote> note or <blockquote expandable>."""
    attr = " expandable" if expandable else ""
    return f"<blockquote{attr}>{text}</blockquote>"


def rich_code(value: Any) -> str:
    """<code> wrapped, escaped."""
    return f"<code>{rich_esc(value)}</code>"


def rich_button(
    text: str,
    url: str | None = None,
    *,
    callback_data: str | None = None,
    copy_text: str | None = None,
    style: str | None = None,
) -> str:
    """Native Rich Message inline button (<tg-button>) for Telegram Bot API 10.3+.

    Exactly one of url / callback_data / copy_text picks the button type. The
    callback form is the only way to get a tappable action *inside* a table cell:
    reply-keyboard buttons can only be attached below a message, but a rich-text
    button is part of the message body and so may live in a <td>.

    `style` maps to Telegram's button styles: default, primary, success, danger.
    """
    style_attr = f' style="{_attr(style)}"' if style else ""
    if callback_data is not None:
        return f'<tg-button type="callback_data"{style_attr} data="{_attr(callback_data)}">{text}</tg-button>'
    if copy_text is not None:
        return f'<tg-button type="copy_text"{style_attr} text="{_attr(copy_text)}">{text}</tg-button>'
    if url is None:
        raise ValueError("rich_button() needs one of url, callback_data or copy_text")
    return f'<tg-button type="url"{style_attr} url="{_attr(url)}">{text}</tg-button>'


def rich_button_row(*buttons: str, align: str | None = None) -> str:
    """Group rich_button() results onto one row (<tg-button-row>)."""
    align_attr = f' align="{_attr(align)}"' if align else ""
    inner = "".join(b for b in buttons if b)
    return f"<tg-button-row{align_attr}>{inner}</tg-button-row>"


def rich_table(headers: Sequence[str] | None, rows: Iterable[Sequence[Any]], border: int = 1) -> str:
    """Native Bot API 10.2+ Rich Block table.
    
    Cells are emitted verbatim so EmojiTag / <code> / <tg-emoji> work.
    """
    parts = [f'<table border="{int(border)}">']
    if headers:
        cells = "".join(f"<th>{'' if h is None else h}</th>" for h in headers)
        parts.append(f"<tr>{cells}</tr>")
    for row in rows or ():
        cells = "".join(f"<td>{'' if c is None else c}</td>" for c in row)
        parts.append(f"<tr>{cells}</tr>")
    parts.append("</table>")
    return "".join(parts)


def rich_kv_table(pairs: Iterable[tuple[str, Any]], headers: Sequence[str] | None = None, border: int = 1) -> str:
    """Two-column key/value table from an iterable of (key, value) pairs."""
    rows = [
        (f"<b>{k}</b>", v)
        for k, v in (pairs or ())
        if v is not None
    ]
    return rich_table(headers, rows, border=border)


def rich_details(summary: str, body: str, open: bool = False) -> str:
    """Collapsible <details><summary> dropdown section."""
    attr = " open" if open else ""
    return f"<details{attr}><summary>{summary}</summary>{body}</details>"


# ── Plain-Text & Fallback Handlers ──────────────────────────────────────────

def _normalize_html(html_text: str) -> str:
    """Format and normalize HTML for Telegram InputRichMessage.
    
    Converts plain text newlines into <br/> so Telegram's server-side HTML parser
    does not collapse multiple lines of text/bullets into a single horizontal paragraph,
    while preserving <pre> and <table> block structures.
    """
    if not html_text:
        return ""
    text = str(html_text)
    text = re.sub(r'href=([^\s">]+)', r'href="\1"', text)

    # Protect <pre> and <table> blocks from newline conversion
    placeholders = {}
    def _save_block(m):
        key = f"__PROTECTED_BLOCK_{len(placeholders)}__"
        placeholders[key] = m.group(0)
        return key

    text = re.sub(
        r'(<pre\b[^>]*>.*?</pre>|<table\b[^>]*>.*?</table>)',
        _save_block,
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )

    # Convert newlines to <br/>
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\n", "<br/>")

    # Clean up redundant <br/> tags around block boundaries
    block_tags = "h[1-6]|blockquote|details|summary|p|div|ul|ol|li|table|thead|tbody|tr|th|td|pre"
    text = re.sub(r'(<(?::' + block_tags + r')\b[^>]*>)(?:\s*<br\s*/?>)+', r'\1', text, flags=re.IGNORECASE)
    text = re.sub(r'(?:<br\s*/?>\s*)+(</(?:' + block_tags + r')\b[^>]*>)', r'\1', text, flags=re.IGNORECASE)

    # Restore protected blocks
    for key, val in placeholders.items():
        text = text.replace(key, val)

    return text


def _render_monospace_grid_table(table_html: str) -> str:
    """Convert an HTML <table> into a clean Unicode monospace grid table in <pre>."""
    headers = [
        re.sub(r'<[^>]+>', '', h).strip()
        for h in re.findall(r'<th[^>]*>(.*?)</th>', table_html, flags=re.DOTALL | re.IGNORECASE)
    ]
    rows_raw = re.findall(r'<tr[^>]*>(.*?)</tr>', table_html, flags=re.DOTALL | re.IGNORECASE)

    parsed_rows = []
    for r in rows_raw:
        cells = [
            re.sub(r'<[^>]+>', '', c).strip()
            for c in re.findall(r'<td[^>]*>(.*?)</td>', r, flags=re.DOTALL | re.IGNORECASE)
        ]
        if cells:
            parsed_rows.append(cells)

    if not parsed_rows and not headers:
        return ""

    all_matrix = ([headers] if headers else []) + parsed_rows
    num_cols = max(len(r) for r in all_matrix)
    col_widths = [0] * num_cols
    for row in all_matrix:
        for idx, cell in enumerate(row):
            if idx < num_cols:
                col_widths[idx] = max(col_widths[idx], len(cell))

    def make_row(row_cells, left="│", mid="│", right="│"):
        cells_fmt = []
        for i in range(num_cols):
            val = row_cells[i] if i < len(row_cells) else ""
            cells_fmt.append(f" {val.ljust(col_widths[i])} ")
        return left + mid.join(cells_fmt) + right

    def make_border(left="├", mid="┼", right="┤", fill="─"):
        parts = [fill * (w + 2) for w in col_widths]
        return left + mid.join(parts) + right

    out = ["<pre>"]
    out.append(make_border("┌", "┬", "┐"))
    if headers:
        out.append(make_row(headers))
        out.append(make_border("├", "┼", "┤"))
    for r in parsed_rows:
        out.append(make_row(r))
    out.append(make_border("└", "┴", "┘"))
    out.append("</pre>")
    return "\n".join(out)


def _plain_fallback(html_text: str) -> str:
    """Standard Telegram HTML fallback for clients that don't render rich tags natively.
    
    Transforms:
      - <br/> / <br> -> \n
      - <table> -> clean monospace grid table in <pre>
      - <details><summary> -> <blockquote><b>Summary</b>\nBody</blockquote>
      - <h1>-<h6> -> <b>...</b>
      - <mark> -> <b>...</b>
      - <tg-button type="url"> -> <a href="...">...</a>
      - <tg-button type="callback_data"|"copy_text"> -> <b>label</b> (no plain equivalent)
      - <tg-button-row> -> unwrapped
    """
    if not html_text:
        return ""
    text = str(html_text)
    text = re.sub(r'href=([^\s">]+)', r'href="\1"', text)

    # 1. Convert <details><summary> -> <blockquote>
    def _replace_details(m):
        summary = m.group(1).strip()
        body = m.group(2).strip()
        return f"<blockquote expandable>\n<b>{summary}</b>\n{body}\n</blockquote>"

    text = re.sub(
        r'<details[^>]*>\s*<summary>(.*?)</summary>(.*?)</details>',
        _replace_details,
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )

    # 2. Convert <h1>-<h6> -> <b>
    text = re.sub(r'<h[1-6][^>]*>(.*?)</h[1-6]>', r'\n<b>\1</b>\n', text, flags=re.DOTALL | re.IGNORECASE)

    # 3. Convert <mark> -> <b>
    text = re.sub(r'<mark>(.*?)</mark>', r'<b>\1</b>', text, flags=re.DOTALL | re.IGNORECASE)

    # 4. Convert <tg-button> -> <a> (url) or bold label (callback / copy_text)
    def _replace_button(m):
        attrs, label = m.group(1), m.group(2)
        url_match = re.search(r'\burl="([^"]*)"', attrs, flags=re.IGNORECASE)
        if url_match:
            return f'<a href="{url_match.group(1)}">{label}</a>'
        # A callback button cannot survive as standard HTML. Emit the label so the
        # row still reads sensibly instead of a link that goes nowhere.
        return f"<b>{label}</b>"

    text = re.sub(r'<tg-button\b([^>]*)>(.*?)</tg-button>', _replace_button, text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'</?tg-button-row\b[^>]*>', '', text, flags=re.IGNORECASE)

    # 5. Convert <br/> -> \n
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)

    # 6. Convert <table> -> Monospace Grid Box Table
    def _replace_table(m):
        return _render_monospace_grid_table(m.group(0))

    text = re.sub(r'<table[^>]*>.*?</table>', _replace_table, text, flags=re.DOTALL | re.IGNORECASE)

    # Clean up empty multiple newlines
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def rich_to_plain(html_text: str) -> str:
    """Strip all HTML tags to return clean readable plain text."""
    if not html_text:
        return ""
    text = str(html_text)
    text = _EMOJI_TAG_RE.sub(r"\1", text)
    text = _CELL_BREAK_RE.sub("\x1f", text)
    text = _BLOCK_BREAK_RE.sub("\n", text)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = _ANY_TAG_RE.sub("", text)
    text = _html.unescape(text)
    text = re.sub(r"\x1f+(?=\s*(?:\n|$))", "", text)
    text = text.replace("\x1f", " • ")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def rich_caption(html_text: str) -> str:
    """Downgrade rich HTML for media captions."""
    return _plain_fallback(html_text)


def _input_rich(html_text: str) -> InputRichMessage:
    return InputRichMessage(html=_normalize_html(html_text))


def _is_group(chat_type: Any) -> bool:
    value = getattr(chat_type, "value", chat_type)
    return value in ("group", "supergroup")


# ── Senders & Editors ───────────────────────────────────────────────────────

async def rich_send(
    client,
    chat_id: int | str,
    html_text: str,
    *,
    reply_markup=None,
    receiver_user_id=None,
    callback_query_id=None,
    reply_to_message_id=None,
    reply_parameters=None,
    message_thread_id=None,
    disable_notification=None,
    protect_content=None,
    effect_id=None,
):
    """Send a rich message using Bot API 10.2+ InputRichMessage with transparent fallback."""
    if not html_text:
        return None

    if reply_parameters is None and reply_to_message_id:
        reply_parameters = ReplyParameters(message_id=reply_to_message_id)

    if RICH_AVAILABLE and (receiver_user_id or _has_rich_only_tags(html_text)):
        try:
            return await client.send_rich_message(
                chat_id=chat_id,
                rich_message=_input_rich(html_text),
                reply_markup=reply_markup,
                receiver_user_id=receiver_user_id,
                callback_query_id=callback_query_id,
                reply_parameters=reply_parameters,
                message_thread_id=message_thread_id,
                disable_notification=disable_notification,
                protect_content=protect_content,
                effect_id=effect_id,
            )
        except Exception as e:
            logger.debug(f"[rich_send] rich delivery failed, falling back: {e}")

    try:
        return await client.send_message(
            chat_id=chat_id,
            text=_plain_fallback(html_text),
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup,
            reply_parameters=reply_parameters,
            message_thread_id=message_thread_id,
            disable_notification=disable_notification,
            protect_content=protect_content,
            effect_id=effect_id,
            link_preview_options=None,
        )
    except Exception as e:
        logger.debug(f"[rich_send] plain send failed: {e}")
        return None


async def rich_reply(
    message,
    html_text: str,
    *,
    reply_markup=None,
    ephemeral: bool = False,
    quote: bool = True,
    client=None,
):
    """Reply to a message or callback query with rich formatting."""
    if not html_text:
        return None

    # CallbackQuery
    if hasattr(message, "data") and hasattr(message, "message"):
        app = client or getattr(message, "_client", None)
        cb_user = getattr(message, "from_user", None)
        inner_msg = getattr(message, "message", None)
        chat = getattr(inner_msg, "chat", None)
        if not chat:
            return None
        receiver_user_id = cb_user.id if (ephemeral and cb_user and _is_group(chat.type)) else None
        return await rich_send(
            app,
            chat.id,
            html_text,
            reply_markup=reply_markup,
            receiver_user_id=receiver_user_id,
            reply_to_message_id=getattr(inner_msg, "id", None) if quote else None,
            message_thread_id=getattr(inner_msg, "message_thread_id", None),
        )

    # Standard Message
    chat = getattr(message, "chat", None)
    if not chat:
        return None
    app = client or getattr(message, "_client", None)
    from_user = getattr(message, "from_user", None)
    receiver_user_id = from_user.id if (ephemeral and from_user and _is_group(chat.type)) else None

    reply_parameters = None
    if quote and not receiver_user_id:
        ephemeral_id = getattr(message, "ephemeral_message_id", None)
        if ephemeral_id:
            reply_parameters = ReplyParameters(ephemeral_message_id=ephemeral_id)
        elif getattr(message, "id", 0):
            reply_parameters = ReplyParameters(message_id=message.id)

    return await rich_send(
        app,
        chat.id,
        html_text,
        reply_markup=reply_markup,
        receiver_user_id=receiver_user_id,
        reply_parameters=reply_parameters,
        message_thread_id=getattr(message, "message_thread_id", None),
    )


async def rich_edit(
    target,
    html_text: str,
    *,
    reply_markup=None,
    chat_id=None,
    message_id=None,
    client=None,
):
    """Edit an existing message to display rich HTML."""
    if not html_text:
        return None

    # CallbackQuery
    if hasattr(target, "data") and hasattr(target, "message"):
        app = client or getattr(target, "_client", None)
        msg = getattr(target, "message", None)
        if msg and hasattr(msg, "chat") and hasattr(msg, "id"):
            chat_id = msg.chat.id
            message_id = msg.id
        if app is not None and chat_id and message_id:
            return await _rich_edit_via_client(app, chat_id, message_id, html_text, reply_markup)
        try:
            return await target.edit_message_text(
                _plain_fallback(html_text), parse_mode=ParseMode.HTML, reply_markup=reply_markup
            )
        except Exception as e:
            logger.debug(f"[rich_edit] cq plain edit failed: {e}")
            return None

    # Message instance
    if hasattr(target, "chat") and hasattr(target, "id"):
        app = client or getattr(target, "_client", None)
        chat_id = target.chat.id
        message_id = target.id
        if app is not None:
            return await _rich_edit_via_client(app, chat_id, message_id, html_text, reply_markup)
        try:
            return await target.edit_text(
                _plain_fallback(html_text),
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup,
                link_preview_options=None,
            )
        except Exception as e:
            logger.debug(f"[rich_edit] message plain edit failed: {e}")
            return None

    # Bare Client + ids
    return await _rich_edit_via_client(target, chat_id, message_id, html_text, reply_markup)


async def _rich_edit_via_client(app, chat_id, message_id, html_text, reply_markup):
    if chat_id is None or not message_id:
        return None

    plain_text = _plain_fallback(html_text)

    if RICH_AVAILABLE and _has_rich_only_tags(html_text):
        try:
            from pyrogram import raw, utils, types
            peer = await app.resolve_peer(chat_id)
            input_rich = _input_rich(html_text).write()
            parsed = await utils.parse_text_entities(app, plain_text, ParseMode.HTML, None)
            r = await app.invoke(
                raw.functions.messages.EditMessage(
                    peer=peer,
                    id=message_id,
                    message=parsed["message"],
                    entities=parsed["entities"],
                    rich_message=input_rich,
                    reply_markup=await reply_markup.write(app) if reply_markup else None,
                )
            )
            for i in r.updates:
                if isinstance(i, (raw.types.UpdateEditMessage, raw.types.UpdateEditChannelMessage)):
                    return await types.Message._parse(
                        app, i.message, {i.id: i for i in r.users}, {i.id: i for i in r.chats}
                    )
        except Exception as e:
            logger.debug(f"[rich_edit] raw rich edit failed, falling back: {e}")

    try:
        return await app.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=plain_text,
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup,
            link_preview_options=None,
        )
    except Exception as e:
        logger.debug(f"[rich_edit] plain edit failed: {e}")
        return None


async def rich_answer(
    callback_query,
    html_text: str,
    *,
    reply_markup=None,
    client=None,
):
    """Ephemeral rich response to a button click."""
    if not html_text:
        return None

    app = client or getattr(callback_query, "_client", None)
    message = getattr(callback_query, "message", None)
    chat = getattr(message, "chat", None)
    user = getattr(callback_query, "from_user", None)
    if app is None or chat is None:
        return None

    receiver_user_id = user.id if (user and _is_group(getattr(chat, "type", None))) else None
    return await rich_send(
        app,
        chat.id,
        html_text,
        reply_markup=reply_markup,
        receiver_user_id=receiver_user_id,
        callback_query_id=getattr(callback_query, "id", None) if receiver_user_id else None,
        message_thread_id=getattr(message, "message_thread_id", None),
    )


# ── Ephemeral Maintenance ───────────────────────────────────────────────────

def _ephemeral_receiver(message):
    eph_id = getattr(message, "ephemeral_message_id", None)
    if not eph_id:
        return None
    chat = getattr(message, "chat", None)
    receiver = getattr(message, "receiver_user", None) or getattr(message, "from_user", None)
    receiver_id = getattr(receiver, "id", None)
    if chat is None or not receiver_id:
        return None
    return chat.id, receiver_id, eph_id


async def ephemeral_edit(message, html_text: str, *, reply_markup=None, client=None):
    """Edit an ephemeral message via edit_ephemeral_message_text."""
    if not html_text:
        return None
    target = _ephemeral_receiver(message)
    if target is None:
        return await rich_edit(message, html_text, reply_markup=reply_markup, client=client)

    app = client or getattr(message, "_client", None)
    if app is None:
        return None
    chat_id, receiver_id, eph_id = target
    try:
        return await app.edit_ephemeral_message_text(
            chat_id=chat_id,
            receiver_user_id=receiver_id,
            ephemeral_message_id=eph_id,
            text=rich_caption(html_text),
            reply_markup=reply_markup,
        )
    except Exception as e:
        logger.debug(f"[ephemeral_edit] failed: {e}")
        return None


async def ephemeral_delete(message, *, client=None) -> bool:
    """Delete an ephemeral message via delete_ephemeral_message."""
    if message is None:
        return False
    target = _ephemeral_receiver(message)
    app = client or getattr(message, "_client", None)
    if target is None:
        try:
            await message.delete()
            return True
        except Exception as e:
            logger.debug(f"[ephemeral_delete] plain delete failed: {e}")
            return False

    if app is None:
        return False
    chat_id, receiver_id, eph_id = target
    try:
        await app.delete_ephemeral_message(
            chat_id=chat_id,
            receiver_user_id=receiver_id,
            ephemeral_message_id=eph_id,
        )
        return True
    except Exception as e:
        logger.debug(f"[ephemeral_delete] failed: {e}")
        return False


# ── Streaming Drafts ────────────────────────────────────────────────────────

class RichDraft:
    """Streaming progress via send_rich_message_draft with final persistent send."""

    __slots__ = (
        "client", "chat_id", "message_thread_id", "draft_id",
        "_last_html", "_finished", "_result", "_drafts_ok",
    )

    def __init__(self, client, chat_id, *, message_thread_id=None, draft_id=None):
        self.client = client
        self.chat_id = chat_id
        self.message_thread_id = message_thread_id
        self.draft_id = draft_id or self._new_id(client)
        self._last_html = None
        self._finished = False
        self._result = None
        self._drafts_ok = RICH_AVAILABLE and hasattr(client, "send_rich_message_draft")

    @staticmethod
    def _new_id(client):
        try:
            value = client.rnd_id()
        except Exception:
            import random
            value = random.getrandbits(63)
        return value or 1

    async def update(self, html_text: str) -> bool:
        """Push a live progress frame."""
        if not html_text:
            return False
        self._last_html = html_text
        if not self._drafts_ok:
            return False
        try:
            await self.client.send_rich_message_draft(
                chat_id=self.chat_id,
                draft_id=self.draft_id,
                rich_message=_input_rich(html_text),
                message_thread_id=self.message_thread_id,
            )
            return True
        except Exception as e:
            logger.debug(f"[RichDraft] draft update failed: {e}")
            self._drafts_ok = False
            return False

    async def finish(self, html_text: str = None, *, reply_markup=None, **kwargs):
        """Persist the final message that the user keeps."""
        self._finished = True
        final_html = html_text or self._last_html
        if not final_html:
            return None
        self._result = await rich_send(
            self.client,
            self.chat_id,
            final_html,
            reply_markup=reply_markup,
            message_thread_id=self.message_thread_id,
            **kwargs,
        )
        return self._result

    @property
    def result(self):
        return self._result

    def discard(self) -> None:
        """Finalise without persisting anything."""
        self._finished = True
        self._last_html = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if not self._finished and exc_type is None:
            await self.finish()
        return False
