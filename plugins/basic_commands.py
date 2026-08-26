"""plugins/basic_commands.py — Basic Commands and Status Dashboard with Bot API 10.2 & 10.3 Rich UI."""

import config
from config import collection
from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, Message, ReplyParameters
from stats_manager import get_user_stats
from tools import get_file_size_info, get_text, get_user_status, set_user_lang
from user_state import get_busy_reason, is_user_busy
from utils.emoji import EmojiTag
from utils.rich_ui import (
    rich_details,
    rich_edit,
    rich_heading,
    rich_kv_table,
    rich_note,
    rich_reply,
    rich_send,
)
from plugins.ui_components import (
    back_buttons,
    cancel_all_markup,
    common_buttons,
    home_buttons,
    lang_markup,
)


# ─── Start & Home ─────────────────────────────────────────────────────────────

@Client.on_message(filters.private & filters.command("start"))
async def start_command(client: Client, message: Message):
    text = get_text(collection, message.from_user.id, "start_msg")
    await rich_reply(
        message,
        text,
        reply_markup=home_buttons,
        client=client,
    )


@Client.on_callback_query(filters.regex(r"^home$"))
async def home_callback(client: Client, callback_query: CallbackQuery):
    text = get_text(collection, callback_query.from_user.id, "start_msg")
    await rich_edit(
        callback_query,
        text,
        reply_markup=home_buttons,
        client=client,
    )


# ─── Language Commands ────────────────────────────────────────────────────────

@Client.on_message(filters.private & filters.command("lang"))
async def lang_command(client: Client, message: Message):
    user_id = message.from_user.id
    lang_text = get_text(collection, user_id, "choose_lang")
    await rich_reply(message, lang_text, reply_markup=lang_markup, client=client)


@Client.on_callback_query(filters.regex(r"^lang_menu$"))
async def lang_menu_callback(client: Client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    lang_text = get_text(collection, user_id, "choose_lang")
    await rich_edit(callback_query, lang_text, reply_markup=lang_markup, client=client)


@Client.on_callback_query(filters.regex(r"^setlang_(en|fa)$"))
async def set_lang_handler(client: Client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    lang_code = callback_query.matches[0].group(1)
    set_user_lang(collection, user_id, lang_code)

    success_msg = get_text(collection, user_id, "lang_set")
    await rich_edit(callback_query, success_msg, reply_markup=home_buttons, client=client)


# ─── Help & Documentation ─────────────────────────────────────────────────────

def _build_help_html(user_id: int) -> str:
    """Build the rich help guide with collapsible categories."""
    return (
        f"{rich_heading(f'{EmojiTag.HELP} Help & Documentation', level=1)}\n"
        f"{rich_note('Complete guide on file management, archive compression, and cloud storage.')}\n\n"
        + rich_details(
            "⚡ Basic Commands",
            "• <code>/start</code> — Open the main dashboard and menu\n"
            "• <code>/status</code> — View your storage usage & lifetime stats\n"
            "• <code>/help</code> — Show this documentation guide\n"
            "• <code>/lang</code> — Switch bot language (English / فارسی)",
            open=True,
        )
        + "\n\n"
        + rich_details(
            "📂 File Management",
            "• <code>/my_files</code> — View all your uploaded files in a table\n"
            "• <code>/del &lt;number&gt;</code> — Delete a specific file by its table index\n"
            "• <code>/clear</code> — Remove all files currently in your storage",
            open=False,
        )
        + "\n\n"
        + rich_details(
            "🗜️ Archive & Security",
            "• <code>/fzip</code> — Pack your uploaded files into a ZIP archive\n"
            "• <code>/unzip</code> — Inspect or extract archives in your storage\n"
            "• Choose between standard ZIP or password-protected AES encryption",
            open=False,
        )
        + "\n\n"
        + rich_details(
            "☁️ Large Cloud Uploads (>2 GB)",
            "• Telegram restricts bot uploads to 2.00 GB maximum.\n"
            "• Archives exceeding 2.00 GB are automatically uploaded to high-speed NuLoader cloud with direct download links.",
            open=False,
        )
        + "\n\n"
        + rich_details(
            "💾 Storage Quotas & Limits",
            "• <b>Single File Limit:</b> <code>2.00 GB</code>\n"
            "• <b>Total Storage Quota:</b> <code>4.50 GB</code>\n"
            "• <b>Active Workers:</b> Multi-threaded parallel processing",
            open=False,
        )
    )


@Client.on_message(filters.private & filters.command("help"))
async def help_command(client: Client, message: Message):
    help_html = _build_help_html(message.from_user.id)
    await rich_reply(
        message,
        help_html,
        reply_markup=common_buttons,
        client=client,
    )


@Client.on_callback_query(filters.regex(r"^help$"))
async def help_callback(client: Client, callback_query: CallbackQuery):
    help_html = _build_help_html(callback_query.from_user.id)
    await rich_edit(
        callback_query,
        help_html,
        reply_markup=common_buttons,
        client=client,
    )


# ─── Status & Dashboard ───────────────────────────────────────────────────────

async def _build_status_html_and_markup(user_id: int):
    """Build a rich status card with stats table, storage quota table, and active task indicators."""
    user_stats = await get_user_stats(user_id)
    user_dir = f"{config.ggg}/zipper/{user_id}"
    _, max_storage, max_file_size = get_user_status(collection, user_id)
    total_size, remaining_storage, files = get_file_size_info(user_dir, max_storage)

    # 1. Statistics Table
    stats_pairs = [
        ("Files Processed", f"<code>{user_stats['files_sent']}</code>"),
        ("Password ZIPs", f"<code>{user_stats['zip_with_pass']}</code>"),
        ("Regular ZIPs", f"<code>{user_stats['zip_without_pass']}</code>"),
        ("Cloud Uploads", f"<code>{user_stats['external_uploads']}</code>"),
    ]
    stats_table = rich_kv_table(stats_pairs, headers=["Metric", "Count"])

    # 2. Storage Table
    used_gb = total_size / (1024 ** 3)
    free_gb = remaining_storage / (1024 ** 3)
    quota_gb = max_storage / (1024 ** 3)
    limit_gb = max_file_size / (1024 ** 3)

    storage_pairs = [
        ("Used Storage", f"<code>{used_gb:.2f} GB</code>"),
        ("Available", f"<code>{free_gb:.2f} GB</code>"),
        ("Total Quota", f"<code>{quota_gb:.2f} GB</code>"),
        ("Files in Storage", f"<code>{len(files)}</code>"),
        ("Max File Size", f"<code>{limit_gb:.1f} GB</code>"),
    ]
    storage_table = rich_kv_table(storage_pairs, headers=["Resource", "Allocation"])

    parts = [
        rich_heading(f"{EmojiTag.STATS} User Dashboard & Quota", level=1),
        "<b>📊 Lifetime Statistics</b>",
        stats_table,
        "\n<b>💾 Storage Allocation</b>",
        storage_table,
    ]

    markup = home_buttons

    is_busy = await is_user_busy(user_id)
    if is_busy:
        reason = await get_busy_reason(user_id)
        if reason == "downloading":
            status_text = f"{EmojiTag.DOWNLOAD} <b>Status:</b> Downloading a file…"
        elif reason == "zipping":
            status_text = f"{EmojiTag.COMPRESS} <b>Status:</b> Compressing files…"
        elif reason == "extracting":
            status_text = f"{EmojiTag.ZIP} <b>Status:</b> Extracting files…"
        else:
            status_text = f"{EmojiTag.UPLOAD} <b>Status:</b> Uploading file…"

        parts.append(f"\n{rich_note(status_text)}")
        markup = cancel_all_markup
    elif user_id in config.user_ids:
        parts.append(f"\n{rich_note(f'{EmojiTag.CLOCK} <b>Status:</b> Your file(s) are queued')}")
        markup = cancel_all_markup

    return "\n".join(parts), markup


@Client.on_callback_query(filters.regex(r"^status$"))
async def status_callback_handler(client: Client, callback_query: CallbackQuery):
    html_text, markup = await _build_status_html_and_markup(callback_query.from_user.id)
    await rich_edit(callback_query, html_text, reply_markup=markup, client=client)


@Client.on_message(filters.private & filters.command("status"))
async def user_status_command(client: Client, message: Message):
    html_text, markup = await _build_status_html_and_markup(message.from_user.id)
    await rich_reply(message, html_text, reply_markup=markup, client=client)
