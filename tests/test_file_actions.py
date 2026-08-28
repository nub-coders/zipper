"""tests/test_file_actions.py — /my_files Actions Column and Per-File Callback Button Suite."""

import os
import re
import zipfile

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pyrogram.types import CallbackQuery

import config
from utils.emoji import Emoji, EmojiTag
from utils.rich_ui import _plain_fallback
from plugins.file_handlers import (
    FILES_PER_PAGE,
    _action_callback,
    _files_markup,
    _is_extractable,
    _paginate,
    _storage_entries,
    list_files,
)


def _make_storage(tmp_path, user_id):
    """Create a user storage dir under a patched config.ggg and return its path."""
    user_dir = tmp_path / "zipper" / str(user_id)
    user_dir.mkdir(parents=True)
    return user_dir


def _write_zip(path):
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("inner.txt", "payload")


async def _capture(tmp_path, target, page=0):
    """Run list_files against a fake storage dir, recording sends and edits apart."""
    calls = {"reply": [], "edit": []}

    async def fake_rich_reply(_target, html_text, **kwargs):
        calls["reply"].append((html_text, kwargs.get("reply_markup")))
        return MagicMock()

    async def fake_rich_edit(_target, html_text, **kwargs):
        calls["edit"].append((html_text, kwargs.get("reply_markup")))
        return MagicMock()

    with patch.object(config, "ggg", str(tmp_path)), \
         patch("plugins.file_handlers.is_user_on_chat", new=AsyncMock(return_value=True)), \
         patch("plugins.file_handlers.get_user_status", new=AsyncMock(return_value=(True, 5 * 1024**3, 0))), \
         patch("plugins.file_handlers.rich_reply", new=fake_rich_reply), \
         patch("plugins.file_handlers.rich_edit", new=fake_rich_edit):
        await list_files(MagicMock(), target, page=page)

    return calls


def _as_callback_query(user_id, data="my_files"):
    """A mock that passes isinstance(x, CallbackQuery), which is how _show_card routes.

    __class__ is overridden rather than using spec=: pyrogram assigns from_user and
    message in __init__, so a spec'd mock would reject them.
    """
    cb = MagicMock()
    cb.__class__ = CallbackQuery
    cb.from_user.id = user_id
    cb.data = data
    return cb


async def _render(tmp_path, user_id, page=0):
    """Render the card the way /my_files does and return (html, reply_markup)."""
    message = MagicMock()
    message.from_user.id = user_id

    calls = await _capture(tmp_path, message, page=page)
    assert not calls["edit"], "a command has no card to edit and must send a new one"
    return calls["reply"][0]


def _nav_row(markup):
    """Return the pagination row, or [] when the card is a single page.

    The nav row is identified by content rather than position so the test does not
    silently pass if the row order changes.
    """
    for row in markup.inline_keyboard:
        labels = [b.text for b in row]
        if any(l in ("Prev", "Next") or " of " in l for l in labels):
            return row
    return []


def _cell_row(html, filename):
    """Return the <tr> containing the given filename, tags intact."""
    for row in re.findall(r"<tr>(.*?)</tr>", html, flags=re.S):
        if filename in row:
            return row
    return ""


def _files_table(html):
    """Return the file listing table.

    Picked by its Actions header rather than by position: the card renders the
    Storage Overview table first, so "the first <table>" is the wrong one.
    """
    for table in re.findall(r"<table.*?</table>", html, flags=re.S):
        if "<th>Actions</th>" in table:
            return table
    return ""


# ─── Extractability Detection ────────────────────────────────────────────────

def test_is_extractable_uses_magic_bytes_not_just_extension(tmp_path):
    """A real zip named *.zip.temp must still be recognised: extension matching fails."""
    disguised = tmp_path / "2e443c68_lo.zip.temp"
    _write_zip(disguised)
    assert _is_extractable(str(disguised)) is True


def test_is_extractable_rejects_plain_file_and_directory(tmp_path):
    plain = tmp_path / "notes.txt"
    plain.write_text("hello")
    subdir = tmp_path / "folder"
    subdir.mkdir()
    assert _is_extractable(str(plain)) is False
    assert _is_extractable(str(subdir)) is False


def test_is_extractable_trusts_known_extension_without_magic(tmp_path):
    """A .rar with no readable header still gets an unzip action offered."""
    stub = tmp_path / "archive.rar"
    stub.write_bytes(b"\x00" * 32)
    assert _is_extractable(str(stub)) is True


# ─── Callback Data Contract ──────────────────────────────────────────────────

def test_action_callback_stays_within_telegram_64_byte_limit():
    long_name = "x" * 200 + ".zip"
    for prefix in ("delfile", "unzip"):
        data = _action_callback(prefix, long_name)
        assert len(data.encode("utf-8")) <= 64
        # Must remain a resolvable suffix of the real filename.
        assert long_name.endswith(data.split("|", 1)[1])


def test_action_callback_with_a_page_still_fits_and_resolves():
    """The page segment eats into the 64-byte budget and must not push it over."""
    long_name = "x" * 200 + ".zip"
    data = _action_callback("delfile", long_name, page=12)
    assert len(data.encode("utf-8")) <= 64
    prefix, page, suffix = data.split("|", 2)
    assert (prefix, page) == ("delfile", "12")
    assert long_name.endswith(suffix)


def test_action_callback_keeps_short_names_verbatim():
    assert _action_callback("delfile", "a.zip") == "delfile|a.zip"
    assert _action_callback("unzip", "a.zip") == "unzip|a.zip"
    assert _action_callback("delfile", "a.zip", page=3) == "delfile|3|a.zip"


# ─── Pagination Arithmetic ────────────────────────────────────────────────

def test_paginate_single_page_when_storage_fits():
    assert _paginate(FILES_PER_PAGE, 0) == (0, 1, 0)
    assert _paginate(0, 0) == (0, 1, 0)


def test_paginate_splits_and_offsets():
    assert _paginate(FILES_PER_PAGE + 1, 0) == (0, 2, 0)
    assert _paginate(FILES_PER_PAGE + 1, 1) == (1, 2, FILES_PER_PAGE)


def test_paginate_clamps_out_of_range_pages():
    """A card can outlive the storage it describes, so clamp instead of erroring."""
    assert _paginate(FILES_PER_PAGE + 1, 99) == (1, 2, FILES_PER_PAGE)
    assert _paginate(FILES_PER_PAGE + 1, -5) == (0, 2, 0)
    assert _paginate(3, 7) == (0, 1, 0)


def test_files_markup_never_mutates_the_shared_keyboard():
    """file_buttons is module-level and reused by other cards; adding a nav row to it
    in place would leak pagination into every screen that shares it."""
    from plugins.ui_components import file_buttons

    rows_before = [list(r) for r in file_buttons.inline_keyboard]

    assert _files_markup(0, 1) is file_buttons
    paged = _files_markup(0, 4)
    assert len(paged.inline_keyboard) == len(rows_before) + 1
    assert [list(r) for r in file_buttons.inline_keyboard] == rows_before
    # The shared rows are carried over unchanged, below the nav row.
    assert [list(r) for r in paged.inline_keyboard[1:]] == rows_before


# ─── Row Numbering Agreement ─────────────────────────────────────────────────

def test_storage_entries_includes_directories_so_indices_match_the_card(tmp_path):
    """/del, /unzip <n> and the card must agree even when a directory is present."""
    (tmp_path / "aaa_folder").mkdir()
    (tmp_path / "bbb.zip").write_bytes(b"PK\x03\x04")
    (tmp_path / "ccc.txt").write_text("x")
    assert _storage_entries(str(tmp_path)) == ["aaa_folder", "bbb.zip", "ccc.txt"]


def test_storage_entries_missing_dir_is_empty(tmp_path):
    assert _storage_entries(str(tmp_path / "nope")) == []


# ─── Rendered Card ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_actions_column_header_is_present(tmp_path):
    user_dir = _make_storage(tmp_path, 101)
    (user_dir / "notes.txt").write_text("hello")

    html, _ = await _render(tmp_path, 101)
    assert "<th>Actions</th>" in html
    # The pre-existing columns must survive.
    for header in ("<th>#</th>", "<th>File Name</th>", "<th>Size</th>", "<th>Type</th>"):
        assert header in html


@pytest.mark.asyncio
async def test_storage_overview_renders_above_the_file_table(tmp_path):
    """The quota summary leads the card; the listing follows it."""
    user_dir = _make_storage(tmp_path, 125)
    (user_dir / "notes.txt").write_text("hello")

    html, _ = await _render(tmp_path, 125)
    assert html.index("<th>Storage Overview</th>") < html.index("<th>Actions</th>")
    # Heading stays at the very top, tips stay at the very bottom.
    assert html.index("Your Files in Storage") < html.index("<th>Storage Overview</th>")
    assert html.index("<th>Actions</th>") < html.index("Quick Tips")


@pytest.mark.asyncio
async def test_non_archive_row_offers_delete_only(tmp_path):
    user_dir = _make_storage(tmp_path, 102)
    (user_dir / "notes.txt").write_text("hello")

    html, _ = await _render(tmp_path, 102)
    row = _cell_row(html, "notes.txt")
    assert 'data="delfile|0|notes.txt"' in row
    assert "unzip|" not in row


@pytest.mark.asyncio
async def test_archive_row_offers_delete_and_unzip(tmp_path):
    user_dir = _make_storage(tmp_path, 103)
    _write_zip(user_dir / "backup.zip")

    html, _ = await _render(tmp_path, 103)
    row = _cell_row(html, "backup.zip")
    assert 'data="delfile|0|backup.zip"' in row
    # unzip| carries no page: uncompress_preview in callback_handlers.py owns that
    # contract and parses exactly one separator.
    assert 'data="unzip|backup.zip"' in row


@pytest.mark.asyncio
async def test_actions_are_in_cell_callback_buttons_not_urls(tmp_path):
    """The buttons must sit inside the Actions <td> and carry callback data."""
    user_dir = _make_storage(tmp_path, 104)
    _write_zip(user_dir / "backup.zip")

    html, markup = await _render(tmp_path, 104)
    row = _cell_row(html, "backup.zip")
    cells = re.findall(r"<td>(.*?)</td>", row, flags=re.S)
    actions_cell = cells[-1]

    assert actions_cell.count("<tg-button") == 2
    assert 'type="callback_data"' in actions_cell
    assert "url=" not in actions_cell
    assert 'style="danger"' in actions_cell
    assert 'style="primary"' in actions_cell
    # No per-file reply-keyboard rows remain; the card keeps only its own buttons.
    flat = [b.callback_data for r in markup.inline_keyboard for b in r]
    assert not any(c and c.startswith("delfile|") for c in flat)


@pytest.mark.asyncio
async def test_button_numbering_matches_table_row_numbers(tmp_path):
    user_dir = _make_storage(tmp_path, 106)
    _write_zip(user_dir / "b_archive.zip")
    (user_dir / "a_notes.txt").write_text("hello")
    (user_dir / "c_clip.mp4").write_bytes(b"\x00" * 16)

    html, _ = await _render(tmp_path, 106)
    # sorted() order: a_notes.txt, b_archive.zip, c_clip.mp4
    archive_row = _cell_row(html, "b_archive.zip")
    assert "<td><code>2</code></td>" in archive_row
    assert 'data="unzip|b_archive.zip"' in archive_row
    # Only the archive row gets an unzip action.
    assert "unzip|" not in _cell_row(html, "a_notes.txt")
    assert "unzip|" not in _cell_row(html, "c_clip.mp4")


@pytest.mark.asyncio
async def test_existing_file_buttons_are_preserved(tmp_path):
    user_dir = _make_storage(tmp_path, 107)
    (user_dir / "notes.txt").write_text("hello")

    _, markup = await _render(tmp_path, 107)
    flat = [b.callback_data for row in markup.inline_keyboard for b in row]
    for expected in ("fzip", "clear", "my_files", "home"):
        assert expected in flat


# ─── Pagination Walkthrough ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_single_page_card_has_no_nav_row(tmp_path):
    """A storage that fits on one page must not grow a Prev/Next row."""
    user_dir = _make_storage(tmp_path, 108)
    for i in range(FILES_PER_PAGE):
        (user_dir / f"file_{i:02d}.txt").write_text("x")

    html, markup = await _render(tmp_path, 108)
    assert _nav_row(markup) == []
    files_table = _files_table(html)
    assert files_table.count("<tr>") == FILES_PER_PAGE + 1
    assert "Showing" not in html


@pytest.mark.asyncio
async def test_first_page_shows_next_but_not_prev(tmp_path):
    user_dir = _make_storage(tmp_path, 115)
    for i in range(FILES_PER_PAGE + 3):
        (user_dir / f"file_{i:02d}.txt").write_text("x")

    html, markup = await _render(tmp_path, 115)
    nav = _nav_row(markup)
    assert [b.text for b in nav] == ["1 of 2", "Next"]
    assert [b.callback_data for b in nav] == ["noop", "my_files|1"]

    # Only this page's rows are rendered, and the summary says what is on screen.
    files_table = _files_table(html)
    assert files_table.count("<tr>") == FILES_PER_PAGE + 1
    assert f"<code>1–{FILES_PER_PAGE}</code>" in html


@pytest.mark.asyncio
async def test_last_page_shows_prev_but_not_next(tmp_path):
    user_dir = _make_storage(tmp_path, 116)
    for i in range(FILES_PER_PAGE + 3):
        (user_dir / f"file_{i:02d}.txt").write_text("x")

    html, markup = await _render(tmp_path, 116, page=1)
    nav = _nav_row(markup)
    assert [b.text for b in nav] == ["Prev", "2 of 2"]
    assert [b.callback_data for b in nav] == ["my_files|0", "noop"]

    files_table = _files_table(html)
    assert files_table.count("<tr>") == 3 + 1
    assert f"<code>{FILES_PER_PAGE + 1}–{FILES_PER_PAGE + 3}</code>" in html


@pytest.mark.asyncio
async def test_nav_buttons_carry_arrow_icons_not_literal_glyphs(tmp_path):
    """Reply-keyboard labels stay plain text; the arrow is an icon_custom_emoji_id."""
    user_dir = _make_storage(tmp_path, 117)
    for i in range(FILES_PER_PAGE + 1):
        (user_dir / f"file_{i:02d}.txt").write_text("x")

    _, last = await _render(tmp_path, 117, page=1)
    by_label = {b.text: b for b in _nav_row(last)}
    assert by_label["Prev"].icon_custom_emoji_id == Emoji.BACK
    assert by_label["2 of 2"].icon_custom_emoji_id is None

    _, first = await _render(tmp_path, 117, page=0)
    next_btn = {b.text: b for b in _nav_row(first)}["Next"]
    assert next_btn.icon_custom_emoji_id == Emoji.NEXT


@pytest.mark.asyncio
async def test_page_two_row_numbers_continue_the_absolute_count(tmp_path):
    """/del N takes an absolute index, so row numbers must not restart per page."""
    user_dir = _make_storage(tmp_path, 118)
    for i in range(FILES_PER_PAGE + 2):
        (user_dir / f"file_{i:02d}.txt").write_text("x")

    html, _ = await _render(tmp_path, 118, page=1)
    # sorted() puts file_10 and file_11 last; they are entries 11 and 12.
    assert "<td><code>11</code></td>" in _cell_row(html, "file_10.txt")
    assert "<td><code>12</code></td>" in _cell_row(html, "file_11.txt")
    assert _cell_row(html, "file_00.txt") == ""


@pytest.mark.asyncio
async def test_delete_buttons_on_page_two_carry_that_page(tmp_path):
    """A delete must refresh the page the user was actually looking at."""
    user_dir = _make_storage(tmp_path, 119)
    for i in range(FILES_PER_PAGE + 2):
        (user_dir / f"file_{i:02d}.txt").write_text("x")

    html, _ = await _render(tmp_path, 119, page=1)
    assert 'data="delfile|1|file_10.txt"' in html


@pytest.mark.asyncio
async def test_out_of_range_page_clamps_to_the_last_one(tmp_path):
    user_dir = _make_storage(tmp_path, 120)
    for i in range(FILES_PER_PAGE + 1):
        (user_dir / f"file_{i:02d}.txt").write_text("x")

    _, markup = await _render(tmp_path, 120, page=99)
    assert [b.text for b in _nav_row(markup)] == ["Prev", "2 of 2"]


@pytest.mark.asyncio
async def test_page_callback_routes_to_the_requested_page():
    from plugins.file_handlers import list_files_callback

    cb = MagicMock()
    cb.data = "my_files|3"
    with patch("plugins.file_handlers.list_files", new=AsyncMock()) as render:
        await list_files_callback(MagicMock(), cb)
    assert render.await_args.kwargs["page"] == 3

    # The bare form is what "Refresh List" in file_buttons still sends.
    cb.data = "my_files"
    with patch("plugins.file_handlers.list_files", new=AsyncMock()) as render:
        await list_files_callback(MagicMock(), cb)
    assert render.await_args.kwargs["page"] == 0


@pytest.mark.asyncio
async def test_noop_callback_answers_so_the_indicator_does_not_hang():
    from plugins.file_handlers import noop_callback

    cb = MagicMock()
    cb.answer = AsyncMock()
    await noop_callback(MagicMock(), cb)
    cb.answer.assert_awaited_once()


# ─── Edit In Place vs Send ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_button_navigation_edits_the_card_in_place(tmp_path):
    """Paging must not leave a trail of stale cards behind in the chat."""
    user_dir = _make_storage(tmp_path, 121)
    for i in range(FILES_PER_PAGE + 1):
        (user_dir / f"file_{i:02d}.txt").write_text("x")

    calls = await _capture(tmp_path, _as_callback_query(121, "my_files|1"), page=1)
    assert not calls["reply"]
    assert len(calls["edit"]) == 1

    html, markup = calls["edit"][0]
    # The edited card is the full rich card, nav row and all.
    assert "<th>Actions</th>" in html
    assert [b.text for b in _nav_row(markup)] == ["Prev", "2 of 2"]


@pytest.mark.asyncio
async def test_command_sends_a_new_card_instead_of_editing(tmp_path):
    """/my_files arrives as a Message: there is no card of ours to edit."""
    user_dir = _make_storage(tmp_path, 122)
    (user_dir / "notes.txt").write_text("hello")

    message = MagicMock()
    message.from_user.id = 122
    calls = await _capture(tmp_path, message)

    assert not calls["edit"]
    assert len(calls["reply"]) == 1


@pytest.mark.asyncio
async def test_emptied_storage_edits_into_the_empty_state(tmp_path):
    """Deleting the last file should transform the card, not post a second one."""
    _make_storage(tmp_path, 123)

    calls = await _capture(tmp_path, _as_callback_query(123))
    assert not calls["reply"]
    html, markup = calls["edit"][0]
    assert "storage is currently empty" in html
    assert _nav_row(markup) == []


@pytest.mark.asyncio
async def test_membership_gate_also_edits_when_it_came_from_a_button(tmp_path):
    """The early-return branches must respect the same routing as the card itself."""
    calls = {"reply": [], "edit": []}

    async def fake_rich_reply(_t, html_text, **kwargs):
        calls["reply"].append(html_text)

    async def fake_rich_edit(_t, html_text, **kwargs):
        calls["edit"].append(html_text)

    with patch.object(config, "ggg", str(tmp_path)), \
         patch("plugins.file_handlers.is_user_on_chat", new=AsyncMock(return_value=False)), \
         patch("plugins.file_handlers.rich_reply", new=fake_rich_reply), \
         patch("plugins.file_handlers.rich_edit", new=fake_rich_edit):
        await list_files(MagicMock(), _as_callback_query(124))

    assert not calls["reply"]
    assert "Membership Required" in calls["edit"][0]


@pytest.mark.asyncio
async def test_action_buttons_carry_custom_emoji_icons(tmp_path):
    """Rich-text buttons have no icon_custom_emoji_id, so the icon rides in the label."""
    user_dir = _make_storage(tmp_path, 113)
    _write_zip(user_dir / "backup.zip")

    html, _ = await _render(tmp_path, 113)
    row = _cell_row(html, "backup.zip")
    del_btn = re.search(r'<tg-button[^>]*delfile\|0\|backup\.zip">(.*?)</tg-button>', row, re.S).group(1)
    unzip_btn = re.search(r'<tg-button[^>]*unzip\|backup\.zip">(.*?)</tg-button>', row, re.S).group(1)

    assert del_btn == f"{EmojiTag.TRASH} Del"
    assert unzip_btn == f"{EmojiTag.UNZIP} Unzip"
    assert f'emoji-id="{Emoji.TRASH}"' in del_btn
    assert f'emoji-id="{Emoji.UNZIP}"' in unzip_btn
    assert 'emoji-id="5785058280397082578">📂<' in unzip_btn


@pytest.mark.asyncio
async def test_fallback_keeps_action_labels_readable(tmp_path):
    """If rich delivery is rejected the grid must still name the actions."""
    user_dir = _make_storage(tmp_path, 114)
    _write_zip(user_dir / "backup.zip")

    html, _ = await _render(tmp_path, 114)
    plain = _plain_fallback(html)
    assert "<tg-button" not in plain
    assert "Del" in plain
    assert "Unzip" in plain


@pytest.mark.asyncio
async def test_filename_with_quote_cannot_break_out_of_the_attribute(tmp_path):
    """A double quote in a filename must not terminate data="..." early."""
    user_dir = _make_storage(tmp_path, 112)
    (user_dir / 'we"ird.txt').write_text("hello")

    html, _ = await _render(tmp_path, 112)
    assert 'data="delfile|0|we&quot;ird.txt"' in html
    assert 'data="delfile|0|we"' not in html


# ─── Delete Callback ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_callback_removes_file_and_refreshes(tmp_path):
    from plugins.file_handlers import delete_file_callback

    user_id = 109
    user_dir = _make_storage(tmp_path, user_id)
    target = user_dir / "backup.zip"
    _write_zip(target)
    (user_dir / "keep.txt").write_text("hello")

    cb = MagicMock()
    cb.from_user.id = user_id
    cb.data = "delfile|0|backup.zip"
    cb.answer = AsyncMock()

    refresh = AsyncMock()
    with patch.object(config, "ggg", str(tmp_path)), \
         patch("plugins.file_handlers.list_files", new=refresh):
        await delete_file_callback(MagicMock(), cb)

    assert not target.exists()
    assert (user_dir / "keep.txt").exists()
    refresh.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_callback_on_missing_file_alerts_and_keeps_storage(tmp_path):
    from plugins.file_handlers import delete_file_callback

    user_id = 110
    user_dir = _make_storage(tmp_path, user_id)
    (user_dir / "keep.txt").write_text("hello")

    cb = MagicMock()
    cb.from_user.id = user_id
    cb.data = "delfile|0|gone.zip"
    cb.answer = AsyncMock()

    refresh = AsyncMock()
    with patch.object(config, "ggg", str(tmp_path)), \
         patch("plugins.file_handlers.list_files", new=refresh):
        await delete_file_callback(MagicMock(), cb)

    assert (user_dir / "keep.txt").exists()
    refresh.assert_not_awaited()
    assert cb.answer.await_args.kwargs.get("show_alert") is True


@pytest.mark.asyncio
async def test_delete_callback_resolves_truncated_callback_data(tmp_path):
    """A name too long for callback_data is keyed by suffix and must still resolve."""
    from plugins.file_handlers import delete_file_callback

    user_id = 111
    user_dir = _make_storage(tmp_path, user_id)
    long_name = "y" * 120 + ".zip"
    target = user_dir / long_name
    _write_zip(target)

    cb = MagicMock()
    cb.from_user.id = user_id
    cb.data = _action_callback("delfile", long_name, page=0)
    cb.answer = AsyncMock()

    with patch.object(config, "ggg", str(tmp_path)), \
         patch("plugins.file_handlers.list_files", new=AsyncMock()):
        await delete_file_callback(MagicMock(), cb)

    assert not os.path.exists(target)
