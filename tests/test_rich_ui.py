"""tests/test_rich_ui.py — Test suite for Bot API 10.2 & 10.3 Rich UI features and fallbacks in Zipper Bot."""

import pytest
from pyrogram.enums import ButtonStyle
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, InputRichMessage
from utils.emoji import Emoji, EmojiTag
from utils.premium_emoji import patch_pyrogram_for_custom_emojis, strip_leading_unicode_emoji
from utils.rich_ui import (
    _has_rich_only_tags,
    _plain_fallback,
    _render_monospace_grid_table,
    rich_button,
    rich_button_row,
    rich_details,
    rich_esc,
    rich_heading,
    rich_kv_table,
    rich_note,
    rich_table,
    rich_to_plain,
)


def test_rich_builders():
    """Test rich message builders."""
    h1 = rich_heading("Main Title", level=1)
    assert h1 == "<h1>Main Title</h1>"

    h2 = rich_heading("Section Header", level=2)
    assert h2 == "<h2>Section Header</h2>"

    note = rich_note("This is a tip", expandable=False)
    assert note == "<blockquote>This is a tip</blockquote>"

    exp_note = rich_note("Expandable tip", expandable=True)
    assert exp_note == "<blockquote expandable>Expandable tip</blockquote>"

    btn = rich_button("Download", "https://example.com/file.zip")
    assert btn == '<tg-button type="url" url="https://example.com/file.zip">Download</tg-button>'

    cb_btn = rich_button("Del", callback_data="delfile|a.zip", style="danger")
    assert cb_btn == '<tg-button type="callback_data" style="danger" data="delfile|a.zip">Del</tg-button>'

    copy_btn = rich_button("Copy Link", copy_text="https://t.me/x")
    assert copy_btn == '<tg-button type="copy_text" text="https://t.me/x">Copy Link</tg-button>'

    with pytest.raises(ValueError):
        rich_button("Broken")

    row = rich_button_row(cb_btn, copy_btn, align="right")
    assert row == f'<tg-button-row align="right">{cb_btn}{copy_btn}</tg-button-row>'

    det = rich_details("Commands", "• /start\n• /help", open=True)
    assert det == "<details open><summary>Commands</summary>• /start\n• /help</details>"


def test_rich_table_generation():
    """Test native rich table and kv-table generation."""
    headers = ["#", "File Name", "Size"]
    rows = [
        ("1", "document.pdf", "1.20 MB"),
        ("2", "video.mp4", "150.00 MB"),
    ]
    tbl = rich_table(headers, rows)
    assert "<table border=\"1\">" in tbl
    assert "<th>#</th><th>File Name</th><th>Size</th>" in tbl
    assert "<td>1</td><td>document.pdf</td><td>1.20 MB</td>" in tbl
    assert "<td>2</td><td>video.mp4</td><td>150.00 MB</td>" in tbl
    assert tbl.endswith("</table>")

    kv = rich_kv_table([
        ("Used", "1.50 GB"),
        ("Free", "3.00 GB"),
    ], headers=["Resource", "Value"])
    assert "<th>Resource</th><th>Value</th>" in kv
    assert "<td><b>Used</b></td><td>1.50 GB</td>" in kv
    assert "<td><b>Free</b></td><td>3.00 GB</td>" in kv


def test_rich_tags_detection():
    """Test detection of Bot API 10.2+ rich tags."""
    assert _has_rich_only_tags("<h1>Title</h1>") is True
    assert _has_rich_only_tags("<table><tr><td>1</td></tr></table>") is True
    assert _has_rich_only_tags("<details><summary>S</summary>B</details>") is True
    assert _has_rich_only_tags('<tg-button url="https://x.com">Btn</tg-button>') is True
    assert _has_rich_only_tags("<mark>Highlight</mark>") is True
    assert _has_rich_only_tags("<b>Plain bold text</b>") is False
    assert _has_rich_only_tags("<code>code snippet</code>") is False
    assert _has_rich_only_tags("") is False


def test_plain_fallback_table():
    """Test fallback conversion of HTML table to monospace grid table."""
    html_table = (
        "<table>"
        "<tr><th>Metric</th><th>Value</th></tr>"
        "<tr><td>Files</td><td>12</td></tr>"
        "<tr><td>Used Storage</td><td>1.45 GB</td></tr>"
        "</table>"
    )
    fallback = _render_monospace_grid_table(html_table)
    assert "<pre>" in fallback
    assert "┌" in fallback and "┬" in fallback and "┐" in fallback
    assert "Metric" in fallback and "Value" in fallback
    assert "Files" in fallback and "12" in fallback
    assert "├" in fallback and "┼" in fallback and "┤" in fallback
    assert "└" in fallback and "┴" in fallback and "┘" in fallback
    assert "</pre>" in fallback


def test_plain_fallback_full():
    """Test full plain fallback converting h1, details, mark, and tables."""
    full_html = (
        "<h1>User Dashboard</h1>\n"
        "<details><summary>More Info</summary>Detailed information here</details>\n"
        "<mark>Alert!</mark>\n"
        '<tg-button url="https://files.nubcoders.com/dl">Download</tg-button>\n'
        "<table><tr><th>Col1</th><th>Col2</th></tr><tr><td>A</td><td>B</td></tr></table>"
    )
    fallback = _plain_fallback(full_html)
    assert "<b>User Dashboard</b>" in fallback
    assert "<blockquote expandable>" in fallback
    assert "<b>More Info</b>" in fallback
    assert "Detailed information here" in fallback
    assert "<b>Alert!</b>" in fallback
    assert '<a href="https://files.nubcoders.com/dl">Download</a>' in fallback
    assert "<pre>" in fallback
    assert "Col1" in fallback


def test_input_rich_message():
    """Test InputRichMessage compatibility with Kurigram."""
    rich_msg = InputRichMessage(html="<h1>Welcome</h1><p>Testing InputRichMessage</p>")
    assert hasattr(rich_msg, "html") or hasattr(rich_msg, "write")
    assert rich_msg.html == "<h1>Welcome</h1><p>Testing InputRichMessage</p>"


def test_custom_emoji_button_patch():
    """Test monkey-patching of InlineKeyboardButton."""
    patch_pyrogram_for_custom_emojis()

    # 1. Leading emoji extraction
    btn1 = InlineKeyboardButton("🗂️ My Files", callback_data="my_files", style=ButtonStyle.SUCCESS)
    assert getattr(btn1, "icon_custom_emoji_id", None) == str(Emoji.FILE)
    assert btn1.text == "My Files"
    assert btn1.style == ButtonStyle.SUCCESS

    # 2. Keyword fallback matching
    btn2 = InlineKeyboardButton("Compress", callback_data="fzip", style=ButtonStyle.PRIMARY)
    assert getattr(btn2, "icon_custom_emoji_id", None) == str(Emoji.COMPRESS)
    assert btn2.style == ButtonStyle.PRIMARY

    # 3. Explicit icon_custom_emoji_id preserved
    btn3 = InlineKeyboardButton("Custom", callback_data="custom", icon_custom_emoji_id=Emoji.STAR)
    assert getattr(btn3, "icon_custom_emoji_id", None) == Emoji.STAR


def test_ui_components_keyboards():
    """Test all predefined UI keyboards in plugins/ui_components.py."""
    from plugins.ui_components import (
        back_buttons,
        cancel_all_markup,
        cancel_markup,
        common_buttons,
        file_buttons,
        home_buttons,
        lang_markup,
        pass_button,
    )

    for kb in [home_buttons, common_buttons, back_buttons, pass_button, file_buttons, cancel_markup, cancel_all_markup, lang_markup]:
        assert isinstance(kb, InlineKeyboardMarkup)
        assert len(kb.inline_keyboard) > 0
        for row in kb.inline_keyboard:
            for btn in row:
                assert isinstance(btn, InlineKeyboardButton)
                assert btn.text != ""


def test_i18n_and_templates():
    """Test internationalization templates with custom emoji tags."""
    from i18n import TEXTS

    for lang in ("en", "fa"):
        assert lang in TEXTS
        assert "start_msg" in TEXTS[lang]
        assert "<tg-emoji" in TEXTS[lang]["start_msg"]
        assert "<h1>" in TEXTS[lang]["start_msg"]


def test_rich_to_plain():
    """Test conversion of rich HTML to clean plain text."""
    html_text = "<h1>Title</h1><p>Some text</p><table><tr><td>Cell1</td><td>Cell2</td></tr></table>"
    plain = rich_to_plain(html_text)
    assert "<h1>" not in plain
    assert "<table>" not in plain
    assert "Title" in plain
    assert "Cell1" in plain


def test_normalize_html_newline_preservation():
    """Test that _normalize_html converts \n to <br/> outside <table> and <pre>."""
    from utils.rich_ui import _normalize_html

    sample = (
        "<b>Section:</b>\n"
        "• Item 1\n"
        "• Item 2\n\n"
        "<table><tr><th>H</th></tr><tr><td>D</td></tr></table>\n\n"
        "<pre>Line A\nLine B</pre>"
    )
    normalized = _normalize_html(sample)
    assert "<b>Section:</b><br/>• Item 1<br/>• Item 2" in normalized
    assert "<table><tr><th>H</th></tr><tr><td>D</td></tr></table>" in normalized
    assert "<pre>Line A\nLine B</pre>" in normalized


def test_heading_with_emoji():
    """Test that custom emojis inside rich_heading are placed correctly inside the <h1> tag."""
    h = rich_heading(f"{EmojiTag.ARCHIVE} File Zipper Bot", level=1)
    assert h.startswith("<h1><tg-emoji")
    assert "File Zipper Bot</h1>" in h


def test_nuloader_envelope_modes():
    """Test that _build_envelope in nuloader_upload properly embeds different expiry modes."""
    from nuloader_upload import _build_envelope

    preamble_7d, epilogue_7d, content_type_7d = _build_envelope("test.zip", "days_7")
    assert b'name="expiry_mode"\r\n\r\ndays_7\r\n' in preamble_7d
    assert b'filename="test.zip"' in preamble_7d
    assert "multipart/form-data; boundary=" in content_type_7d

    preamble_5dl, _, _ = _build_envelope("test.zip", "downloads_5")
    assert b'name="expiry_mode"\r\n\r\ndownloads_5\r\n' in preamble_5dl


def test_batch_manager_progress_card():
    """Test progress card formatting with batch metrics (completed/total/queued)."""
    from batch_manager import UserDownloadBatch, _build_progress_card
    from unittest.mock import MagicMock

    mock_client = MagicMock()
    mock_msg = MagicMock()
    mock_msg.document.file_name = "archive.tar.gz"
    mock_msg.document.file_size = 100 * 1024 * 1024
    mock_msg.photo = None
    mock_msg.video = None
    mock_msg.audio = None
    mock_msg.voice = None
    mock_msg.video_note = None
    mock_msg.sticker = None
    mock_msg.animation = None
    mock_msg.text = None

    batch = UserDownloadBatch(
        user_id=12345,
        chat_id=12345,
        client=mock_client,
        active_msg=mock_msg,
        queue=[MagicMock(), MagicMock()],  # 2 queued
        downloaded_count=2,  # 2 already downloaded
        total_in_batch=5,    # 2 downloaded + 1 active + 2 queued = 5
    )

    card = _build_progress_card(
        batch,
        current=50 * 1024 * 1024,
        total=100 * 1024 * 1024,
        speed=5.25,
        eta=9.5,
    )

    assert "Downloading Files (3/5)" in card
    assert "archive.tar.gz" in card
    assert "50.00 MB / 100.00 MB" in card
    assert "2 / 5" in card
    assert "2 file(s)" in card
    assert "5.25 MB/s" in card
    assert "50.0%" in card


@pytest.mark.asyncio
async def test_batch_manager_relocation():
    """Test that _relocate_status_message_to_bottom deletes previous status message and sends new one."""
    from batch_manager import UserDownloadBatch, _relocate_status_message_to_bottom
    from unittest.mock import AsyncMock, MagicMock

    mock_client = MagicMock()
    mock_client.send_message = AsyncMock(return_value=MagicMock(id=999))

    old_status = MagicMock(id=100)
    old_status.delete = AsyncMock()

    batch = UserDownloadBatch(
        user_id=12345,
        chat_id=12345,
        client=mock_client,
        status_msg=old_status,
        last_progress_info={"current": 1024, "total": 2048, "speed": 1.0, "eta": 1.0, "elapsed": 1.0},
    )

    await _relocate_status_message_to_bottom(batch)

    # Old status message must be deleted
    old_status.delete.assert_awaited_once()
    # New message must be created
    assert batch.status_msg is not None
    assert batch.status_msg.id == 999


@pytest.mark.asyncio
async def test_batch_manager_cancellation():
    """Test cancel_user_batch clearing queue and cancelling timers."""
    from batch_manager import cancel_user_batch, get_user_batch
    from unittest.mock import MagicMock

    mock_client = MagicMock()
    batch = await get_user_batch(99999, 99999, mock_client)
    batch.queue.extend([MagicMock(), MagicMock(), MagicMock()])
    assert len(batch.queue) == 3

    await cancel_user_batch(99999)
    assert len(batch.queue) == 0
