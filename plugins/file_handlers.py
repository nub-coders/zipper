"""plugins/file_handlers.py — File Management, Downloads, and Directory Actions with Bot API 10.2 & 10.3 Rich UI."""

import os
import shutil

import config
from config import collection
from plugins.ui_components import (
    back_buttons,
    cancel_markup,
    file_buttons,
    nofile_buttons,
    pass_button,
)
from pyrogram import Client, filters
from pyrogram.enums import ButtonStyle
from pyrogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from batch_manager import enqueue_link_message, enqueue_media_message
from tools import (
    ARCHIVE_EXTENSIONS,
    get_file_size_info,
    get_user_status,
    has_archive_magic,
    is_compressed,
    is_user_on_chat,
)
from user_state import (
    get_busy_reason,
    is_user_busy,
)
from utils.emoji import Emoji, EmojiTag
from utils.rich_ui import (
    rich_button,
    rich_edit,
    rich_esc,
    rich_heading,
    rich_kv_table,
    rich_reply,
    rich_table,
)


# ─── Size Formatter ───────────────────────────────────────────────────────────

def _fmt_size(size_bytes: int) -> str:
    """Return a human-readable size string."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 ** 2:
        return f"{size_bytes / 1024:.2f} KB"
    elif size_bytes < 1024 ** 3:
        return f"{size_bytes / (1024 ** 2):.2f} MB"
    else:
        return f"{size_bytes / (1024 ** 3):.2f} GB"


# ─── Storage Indexing ─────────────────────────────────────────────────────────

# How many files one /my_files page lists. Every row on a page gets its own action
# buttons, and each <tg-button> costs ~80 characters of markup inside the single
# message body, so paging keeps the card well clear of the message length limit.
FILES_PER_PAGE = 10


def _paginate(total: int, page: int) -> tuple[int, int, int]:
    """Clamp a requested page and return (page, total_pages, start_index).

    Clamping rather than rejecting matters because a card can outlive the storage
    it describes: deleting the last file on page 3 must land on a real page.
    """
    total_pages = max(1, (total + FILES_PER_PAGE - 1) // FILES_PER_PAGE)
    page = max(0, min(page, total_pages - 1))
    return page, total_pages, page * FILES_PER_PAGE


def _files_markup(page: int, total_pages: int) -> InlineKeyboardMarkup:
    """Keyboard for the /my_files card, prefixed with a nav row when it pages.

    file_buttons is a shared module-level markup, so its rows are copied into a new
    markup instead of being appended to: mutating it would leak this card's nav row
    into every other screen that reuses it.
    """
    if total_pages <= 1:
        return file_buttons

    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(
            "Prev",
            callback_data=f"my_files|{page - 1}",
            style=ButtonStyle.PRIMARY,
            icon_custom_emoji_id=Emoji.BACK,
        ))
    # The indicator has to be a button because a keyboard row cannot hold plain text.
    # noop_callback answers the tap so it does not spin as if the bot had hung.
    nav_row.append(InlineKeyboardButton(
        f"{page + 1} of {total_pages}",
        callback_data="noop",
        style=ButtonStyle.DEFAULT,
    ))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton(
            "Next",
            callback_data=f"my_files|{page + 1}",
            style=ButtonStyle.PRIMARY,
            icon_custom_emoji_id=Emoji.NEXT,
        ))

    return InlineKeyboardMarkup([nav_row] + list(file_buttons.inline_keyboard))


def _storage_entries(user_dir: str) -> list[str]:
    """Return storage entries in the exact order /my_files numbers them.

    /del, /unzip <n> and the Actions column must all agree on what "3" means, so
    they share this one listing instead of each re-deriving it. Directories are
    included because get_file_size_info() lists them too.
    """
    try:
        return sorted(os.listdir(user_dir))
    except OSError:
        return []


def _is_extractable(file_path: str) -> bool:
    """Cheap synchronous archive test for rendering one table row.

    Deliberately stops short of is_compressed()'s third stage, which shells out to
    7z: /my_files would pay one subprocess per row. Magic bytes first so that a
    mangled name like `foo.zip.temp` (extension match fails) is still offered an
    unzip action.
    """
    try:
        if not os.path.isfile(file_path):
            return False
    except OSError:
        return False
    return has_archive_magic(file_path) or file_path.lower().endswith(ARCHIVE_EXTENSIONS)


def _action_callback(prefix: str, filename: str, page: int | None = None) -> str:
    """Build callback data keyed by filename suffix, matching the unzip| contract.

    Indices are not used as the key: the list can change between render and tap,
    and a stale index would delete the wrong file. A stale suffix resolves to the
    right file or to nothing. `page` is carried along so a refresh after the action
    returns to the page the user was actually looking at.
    """
    head = prefix if page is None else f"{prefix}|{page}"
    data = f"{head}|{filename}"
    if len(data.encode("utf-8")) > 64:
        data = f"{head}|{filename[-50:]}"
    return data


def _detect_file_badge(filename: str) -> str:
    """Return an icon badge for the file type."""
    lower = filename.lower()
    if lower.endswith((".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz", ".tgz", ".tbz2", ".txz", ".zst", ".iso", ".cab", ".arj", ".lzh", ".apk", ".jar", ".deb", ".rpm", ".cbz", ".cbr")):
        return f"{EmojiTag.ZIP} ZIP"
    elif lower.endswith((".mp4", ".mkv", ".mov", ".avi", ".webm", ".flv", ".vob", ".wmv")):
        return f"{EmojiTag.VIDEO} Video"
    elif lower.endswith((".mp3", ".flac", ".ogg", ".wav", ".m4a", ".aac", ".opus", ".wma")):
        return f"{EmojiTag.AUDIO} Audio"
    elif lower.endswith((".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".svg", ".ico", ".tiff")):
        return f"{EmojiTag.IMAGE} Image"
    elif lower.endswith((".py", ".js", ".html", ".css", ".json", ".sh", ".c", ".cpp", ".rs", ".go", ".java", ".ts", ".php", ".rb")):
        return f"{EmojiTag.CODE} Code"
    elif lower.endswith((".pdf", ".docx", ".doc", ".txt", ".rtf", ".odt", ".epub")):
        return f"{EmojiTag.DOCUMENT} Doc"
    return f"{EmojiTag.FILE} File"


# ─── Commands ────────────────────────────────────────────────────────────────

@Client.on_message(filters.private & filters.command("my_files"))
async def list_files_command(client: Client, message: Message):
    await list_files(client, message)


@Client.on_callback_query(filters.regex(r"^my_files(?:\|\d+)?$"))
async def list_files_callback(client: Client, callback_query: CallbackQuery):
    parts = (callback_query.data or "").split("|")
    page = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
    await list_files(client, callback_query, page=page)


@Client.on_callback_query(filters.regex(r"^noop$"))
async def noop_callback(client: Client, callback_query: CallbackQuery):
    """Absorb taps on non-interactive labels such as the page indicator."""
    await callback_query.answer()


@Client.on_message(filters.private & filters.command("del"))
async def delete_file(client: Client, message: Message):
    user_id = message.from_user.id
    user_dir = f"{config.ggg}/zipper/{user_id}"

    try:
        file_number = int(message.text.split("/del ")[1]) - 1
    except (IndexError, ValueError):
        return await rich_reply(
            message,
            f"{EmojiTag.WARNING} <b>Invalid file number.</b>\n\nUsage: <code>/del &lt;number&gt;</code> (check numbers via <code>/my_files</code>)",
            reply_markup=file_buttons,
            client=client,
        )

    if not os.path.exists(user_dir):
        return await rich_reply(
            message,
            f"{EmojiTag.INFO} <b>Your directory is empty.</b> Send me any file to get started.",
            reply_markup=nofile_buttons,
            client=client,
        )

    files = _storage_entries(user_dir)
    if 0 <= file_number < len(files):
        target = os.path.join(user_dir, files[file_number])
        deleted_name = files[file_number]
        try:
            if os.path.isdir(target):
                shutil.rmtree(target, ignore_errors=True)
            else:
                os.remove(target)
            return await rich_reply(
                message,
                f"{EmojiTag.SUCCESS} <b>File deleted successfully!</b>\n\n🗑️ Removed: <code>{rich_esc(deleted_name)}</code>",
                reply_markup=file_buttons,
                client=client,
            )
        except OSError as e:
            return await rich_reply(
                message,
                f"{EmojiTag.ERROR} <b>Failed to delete:</b> <code>{rich_esc(e)}</code>",
                reply_markup=file_buttons,
                client=client,
            )

    return await rich_reply(
        message,
        f"{EmojiTag.ERROR} <b>Invalid file number.</b> Use <code>/my_files</code> to view valid indices.",
        reply_markup=file_buttons,
        client=client,
    )


@Client.on_callback_query(filters.regex(r"^delfile\|\d+\|"))
async def delete_file_callback(client: Client, callback_query: CallbackQuery):
    """Delete one file straight from the /my_files Actions column."""
    user_id = callback_query.from_user.id
    user_dir = f"{config.ggg}/zipper/{user_id}"
    _, page_str, name_end = callback_query.data.split("|", 2)
    page = int(page_str)

    target_name = None
    for f in _storage_entries(user_dir):
        if f.endswith(name_end):
            target_name = f
            break

    if not target_name:
        return await callback_query.answer("File not found in storage.", show_alert=True)

    target = os.path.join(user_dir, target_name)
    try:
        if os.path.isdir(target):
            shutil.rmtree(target, ignore_errors=True)
        else:
            os.remove(target)
    except OSError as e:
        print(f"Failed to delete {target}: {e}")
        return await callback_query.answer(f"Failed to delete: {e}", show_alert=True)

    await callback_query.answer(f"Deleted {target_name}")
    # Re-render: the remaining rows renumber, so leaving the old card up would leave
    # every action button pointing at a stale row number. _paginate() clamps the page
    # in case that deletion emptied the last one.
    await list_files(client, callback_query, page=page)


@Client.on_message(filters.private & filters.command("clear"))
async def clear_files(client: Client, message: Message):
    from tools import handle_clear_files
    user_id = message.from_user.id
    message_text = await handle_clear_files(user_id, back_buttons)
    formatted = f"{EmojiTag.TRASH} <b>{message_text}</b>"
    await rich_reply(message, formatted, reply_markup=back_buttons, client=client)


@Client.on_callback_query(filters.regex(r"^clear$"))
async def clear_files_callback(client: Client, callback_query: CallbackQuery):
    from tools import handle_clear_files
    user_id = callback_query.from_user.id
    message_text = await handle_clear_files(user_id, back_buttons)
    formatted = f"{EmojiTag.TRASH} <b>{message_text}</b>"
    await rich_edit(callback_query, formatted, reply_markup=back_buttons, client=client)


@Client.on_message(filters.private & filters.command("fzip"))
async def zip_files_command(client: Client, message: Message):
    user_id = message.from_user.id
    if await is_user_busy(user_id):
        reason = await get_busy_reason(user_id)
        return await rich_reply(
            message,
            f"{EmojiTag.CLOCK} <b>Please wait</b>\n\nYour file is currently {reason}.\nYou can zip your files once it finishes.",
            reply_markup=cancel_markup,
            client=client,
        )

    user_dir = f"{config.ggg}/zipper/{user_id}"
    files = [f for f in os.listdir(user_dir) if os.path.isfile(os.path.join(user_dir, f))] if os.path.exists(user_dir) else []

    if not files:
        return await rich_reply(
            message,
            f"{EmojiTag.INFO} <b>You don't have files to zip yet.</b>\n\nSend me any files or direct links first, then use <code>/fzip</code>.",
            reply_markup=back_buttons,
            client=client,
        )

    total_bytes = sum(os.path.getsize(os.path.join(user_dir, f)) for f in files)

    html_content = (
        f"{rich_heading(f'{EmojiTag.LOCK} ZIP Archive Creation', level=1)}\n"
        f"<b>Files to bundle:</b> <code>{len(files)}</code>\n"
        f"<b>Total uncompressed size:</b> <code>{_fmt_size(total_bytes)}</code>\n\n"
        f"<b>Select your ZIP security preference:</b>\n"
        f"• <b>Protected ZIP:</b> Encrypted with custom password\n"
        f"• <b>Regular ZIP:</b> Standard fast archive without password"
    )
    await rich_reply(message, html_content, reply_markup=pass_button, client=client)


@Client.on_callback_query(filters.regex(r"^fzip$"))
async def zip_files_callback(client: Client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    if await is_user_busy(user_id):
        reason = await get_busy_reason(user_id)
        return await rich_edit(
            callback_query,
            f"{EmojiTag.CLOCK} <b>Please wait</b>\n\nYour file is currently {reason}.\nYou can zip your files once it finishes.",
            reply_markup=cancel_markup,
            client=client,
        )

    user_dir = f"{config.ggg}/zipper/{user_id}"
    files = [f for f in os.listdir(user_dir) if os.path.isfile(os.path.join(user_dir, f))] if os.path.exists(user_dir) else []

    if not files:
        return await rich_edit(
            callback_query,
            f"{EmojiTag.INFO} <b>You don't have files to zip yet.</b>\n\nSend me any files or direct links first, then use <code>/fzip</code>.",
            reply_markup=back_buttons,
            client=client,
        )

    total_bytes = sum(os.path.getsize(os.path.join(user_dir, f)) for f in files)

    html_content = (
        f"{rich_heading(f'{EmojiTag.LOCK} ZIP Archive Creation', level=1)}\n"
        f"<b>Files to bundle:</b> <code>{len(files)}</code>\n"
        f"<b>Total uncompressed size:</b> <code>{_fmt_size(total_bytes)}</code>\n\n"
        f"<b>Select your ZIP security preference:</b>\n"
        f"• <b>Protected ZIP:</b> Encrypted with custom password\n"
        f"• <b>Regular ZIP:</b> Standard fast archive without password"
    )
    await rich_edit(callback_query, html_content, reply_markup=pass_button, client=client)


@Client.on_message(filters.private & filters.command("unzip"))
async def unzip_command(client: Client, message: Message):
    user_id = message.from_user.id

    if await is_user_busy(user_id):
        reason = await get_busy_reason(user_id)
        return await rich_reply(
            message,
            f"{EmojiTag.CLOCK} <b>Please wait</b>\n\nYour file is currently {reason}.\nYou can use <code>/unzip</code> once it finishes.",
            reply_markup=cancel_markup,
            client=client,
        )

    user_dir = f"{config.ggg}/zipper/{user_id}"
    if not os.path.exists(user_dir):
        return await rich_reply(
            message,
            f"{EmojiTag.INFO} <b>Your directory is empty.</b> Send me a compressed file first.",
            reply_markup=nofile_buttons,
            client=client,
        )

    files = [f for f in sorted(os.listdir(user_dir)) if os.path.isfile(os.path.join(user_dir, f))]
    if not files:
        return await rich_reply(
            message,
            f"{EmojiTag.INFO} <b>Your directory is empty.</b> Send me a compressed file first.",
            reply_markup=nofile_buttons,
            client=client,
        )

    # Check if a specific file index or name was passed: e.g. /unzip 1 or /unzip archive.zip
    text_parts = message.text.strip().split(maxsplit=1) if message.text else []
    if len(text_parts) > 1 and text_parts[1].strip():
        arg = text_parts[1].strip()
        matched_file = None
        # Try as 1-based index from /my_files. Resolve against the same listing the
        # card numbers, not the files-only list below: a directory in storage would
        # otherwise shift every index and unzip the wrong entry.
        try:
            idx = int(arg) - 1
            entries = _storage_entries(user_dir)
            if 0 <= idx < len(entries):
                target = entries[idx]
                if await is_compressed(os.path.join(user_dir, target)):
                    matched_file = target
        except ValueError:
            pass

        # Try as exact filename or suffix match
        if not matched_file:
            for f in files:
                if f == arg or f.endswith(arg):
                    if await is_compressed(os.path.join(user_dir, f)):
                        matched_file = f
                        break

        if matched_file:
            cb_data = _action_callback("unzip", matched_file)
            markup = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(f"Inspect {matched_file}", callback_data=cb_data, style=ButtonStyle.PRIMARY, icon_custom_emoji_id=Emoji.ZIP)
                ],
                [
                    InlineKeyboardButton("Dismiss", callback_data="dismiss", style=ButtonStyle.DEFAULT, icon_custom_emoji_id=Emoji.CLOSE)
                ]
            ])
            return await rich_reply(
                message,
                f"{rich_heading(f'{EmojiTag.EXTRACT} Archive Selected', level=2)}\n\n"
                f"Selected: <code>{rich_esc(matched_file)}</code>\n\nClick below to inspect and extract contents:",
                reply_markup=markup,
                client=client,
            )

    compressed_files = []
    for f in files:
        if await is_compressed(os.path.join(user_dir, f)):
            compressed_files.append(f)

    if not compressed_files:
        return await rich_reply(
            message,
            f"{EmojiTag.WARNING} <b>No compressed archive found in your storage.</b>",
            reply_markup=nofile_buttons,
            client=client,
        )

    buttons = []
    for f in compressed_files:
        cb_data = _action_callback("unzip", f)
        buttons.append([
            InlineKeyboardButton(f"{f}", callback_data=cb_data, style=ButtonStyle.PRIMARY, icon_custom_emoji_id=Emoji.ZIP)
        ])

    buttons.append([InlineKeyboardButton("Dismiss", callback_data="dismiss", style=ButtonStyle.DEFAULT, icon_custom_emoji_id=Emoji.CLOSE)])
    markup = InlineKeyboardMarkup(buttons)

    await rich_reply(
        message,
        f"{rich_heading(f'{EmojiTag.EXTRACT} Select Archive to Extract', level=2)}\n\n"
        f"Select a compressed archive from your storage below:",
        reply_markup=markup,
        client=client,
    )


# ─── Media & Link Dispatchers ─────────────────────────────────────────────────

@Client.on_message(
    filters.private
    & (filters.document | filters.photo | filters.video | filters.audio
       | filters.voice | filters.video_note | filters.sticker | filters.animation)
)
async def handle_media(client: Client, message: Message):
    await enqueue_media_message(client, message)


@Client.on_message(
    filters.private
    & filters.text
    & ~filters.command([
        "start", "help", "my_files", "clear", "del", "fzip", "unzip",
        "status", "rst", "users", "set", "ad", "get", "broadcast",
        "reboot", "skip", "ping", "stats", "lang",
    ])
)
async def handle_links(client: Client, message: Message):
    if message.text.startswith("http"):
        await enqueue_link_message(client, message)


# ─── File Listing ─────────────────────────────────────────────────────────────

async def _show_card(client, target, html_text, reply_markup):
    """Edit the card in place when it came from a button, else send a new one.

    Paging is the reason: walking Prev/Next through storage would otherwise leave a
    trail of stale cards, each with buttons still pointing at the page it was
    rendered for. /my_files itself arrives as a Message and has nothing to edit.
    """
    if isinstance(target, CallbackQuery):
        return await rich_edit(target, html_text, reply_markup=reply_markup, client=client)
    return await rich_reply(target, html_text, reply_markup=reply_markup, client=client)


async def list_files(client, message, page: int = 0):
    user_id = message.from_user.id

    if not await is_user_on_chat(client, user_id):
        button = InlineKeyboardMarkup([
            [InlineKeyboardButton("Join Main Channel", url="https://t.me/nub_coders", style=ButtonStyle.PRIMARY, icon_custom_emoji_id=Emoji.LINK)],
            [InlineKeyboardButton("Join Support Channel", url="https://t.me/nub_coder_s", style=ButtonStyle.PRIMARY, icon_custom_emoji_id=Emoji.LINK)],
        ])
        text = f"{EmojiTag.LOCK} <b>Membership Required</b>\n\nYou must join @nub_coders and @nub_coder_s to use this bot."
        return await _show_card(client, message, text, button)

    _, max_storage, _ = await get_user_status(collection, user_id)
    user_dir = f"{config.ggg}/zipper/{user_id}"
    os.makedirs(user_dir, exist_ok=True)

    total_size, remaining_storage, files = get_file_size_info(user_dir, max_storage)

    if not files:
        msg_text = (
            f"{rich_heading(f'{EmojiTag.FOLDER} Your Storage Directory', level=1)}\n\n"
            f"Your storage is currently empty.\n\n"
            f"<i>Send any document, photo, video, or direct HTTP link to get started!</i>"
        )
        return await _show_card(client, message, msg_text, nofile_buttons)

    files_page, total_pages, start = _paginate(len(files), page)
    page_files = files[start:start + FILES_PER_PAGE]

    # Build native rich table
    table_rows = []
    for offset, f in enumerate(page_files):
        number = start + offset + 1
        f_path = os.path.join(user_dir, f)
        f_size = os.path.getsize(f_path) if os.path.exists(f_path) else 0
        badge = _detect_file_badge(f)

        # Callback buttons live in the cell itself: <tg-button type="callback_data">
        # is part of the message body, unlike a reply-keyboard button. The label
        # carries a <tg-emoji> icon rather than icon_custom_emoji_id, which only
        # exists on reply-keyboard buttons.
        actions = rich_button(
            f"{EmojiTag.TRASH} Del",
            callback_data=_action_callback("delfile", f, page=files_page),
            style="danger",
        )
        if _is_extractable(f_path):
            actions += " " + rich_button(
                f"{EmojiTag.UNZIP} Unzip",
                callback_data=_action_callback("unzip", f),
                style="primary",
            )

        table_rows.append((
            f"<code>{number}</code>",
            f"<code>{rich_esc(f[:24] + '...' if len(f) > 27 else f)}</code>",
            f"<code>{_fmt_size(f_size)}</code>",
            badge,
            actions,
        ))

    headers = ["#", "File Name", "Size", "Type", "Actions"]
    files_table = rich_table(headers, table_rows)

    used_gb = total_size / (1024 ** 3)
    free_gb = remaining_storage / (1024 ** 3)

    summary_pairs = [
        ("Total Files", f"<code>{len(files)}</code>"),
        ("Used Space", f"<code>{used_gb:.2f} GB</code>"),
        ("Available Space", f"<code>{free_gb:.2f} GB</code>"),
    ]
    if total_pages > 1:
        summary_pairs.insert(1, ("Showing", f"<code>{start + 1}–{start + len(page_files)}</code>"))
    summary_table = rich_kv_table(summary_pairs, headers=["Storage Overview", "Value"])

    tips = [
        "Tap <b>Del</b> or <b>Unzip</b> in the <b>Actions</b> column to act on that row",
        "<b>Unzip</b> only appears for rows that are actually extractable",
    ]
    if total_pages > 1:
        tips.append("Use <b>Prev</b> and <b>Next</b> below to walk through your files")
    tips.append("Click <b>Compress Files</b> to pack into a ZIP archive")

    tip_lines = "\n".join(f"• {t}" for t in tips)
    # Overview first: it is fixed-height, so the file table below it does not shift
    # position as the user pages, and the quota is visible without scrolling past
    # ten rows of files.
    content = (
        f"{rich_heading(f'{EmojiTag.FOLDER} Your Files in Storage', level=1)}\n"
        f"{summary_table}\n\n"
        f"{files_table}\n\n"
        f"💡 <b>Quick Tips:</b>\n"
        f"{tip_lines}"
    )

    await _show_card(client, message, content, _files_markup(files_page, total_pages))
