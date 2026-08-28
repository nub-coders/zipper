"""utils/emoji.py — Curated Telegram Custom Emoji IDs and Tag Builders for Zipper Bot.

IDs curated from official & verified Telegram emoji packs:
  - TgAndroidIcons (https://t.me/addemoji/TgAndroidIcons)
  - NewsEmoji (https://t.me/addemoji/NewsEmoji)
  - EmojiStatus (https://t.me/addemoji/EmojiStatus)
  - DMJUnigramAnimationEmoji
"""

from __future__ import annotations


class Emoji:
    # ── File Formats & Types ──────────────────────────────────────────────────
    ZIP            = 5877316724830768997   # 🗃  TgAndroidIcons
    FOLDER         = 5877316724830768997   # 📁  TgAndroidIcons
    FILE           = 5877316724830768997   # 📄  TgAndroidIcons
    DOCUMENT       = 5877316724830768997   # 📑  TgAndroidIcons
    ARCHIVE        = 5877316724830768997   # 🗜️  TgAndroidIcons
    VIDEO          = 5775981206319402773   # 🎬  TgAndroidIcons
    AUDIO          = 5891249688933305846   # 🎵  TgAndroidIcons
    IMAGE          = 5814690801665446789   # 🖼  TgAndroidIcons
    CODE           = 5988023995125993550   # 💻  TgAndroidIcons

    # ── Status & Navigation ───────────────────────────────────────────────────
    SUCCESS        = 5776375003280838798   # ✅  TgAndroidIcons
    ERROR          = 5778527486270770928   # ❌  TgAndroidIcons
    TICK           = 5774022692642492953   # ✅  Custom tick
    UNTICK         = 5778479949572738874   # ❌  Custom untick
    WARNING        = 5881702736843511327   # ⚠️  TgAndroidIcons
    INFO           = 5879785854284599288   # ℹ️  TgAndroidIcons
    LOADING        = 5787237370709413702   # ⚙️  DMJUnigramAnimationEmoji
    SETTINGS       = 5787237370709413702   # ⚙️  DMJUnigramAnimationEmoji
    REFRESH        = 5877410604225924969   # 🔄  TgAndroidIcons
    PING           = 5843553939672274145   # ⚡️  TgAndroidIcons
    STATS          = 5877485980901971030   # 📊  TgAndroidIcons
    CLOCK          = 5881855848946338165   # ⏱  TgAndroidIcons

    # ── Security & Quotas ─────────────────────────────────────────────────────
    LOCK           = 5879895758202735862   # 🔒  TgAndroidIcons
    UNLOCK         = 6034962180875490251   # 🔓  TgAndroidIcons
    KEY            = 6005570495603282482   # 🔑  TgAndroidIcons
    SHIELD         = 5926783847453692661   # 🛡   TgAndroidIcons
    STORAGE        = 5877485980901971030   # 💾  TgAndroidIcons
    CLOUD          = 5857290546459973028   # ☁️  TgAndroidIcons
    TRASH          = 5778527486270770928   # 🗑  TgAndroidIcons
    CANCEL         = 5872829476143894491   # 🛑  TgAndroidIcons

    # ── Actions & Arrows ──────────────────────────────────────────────────────
    DOWNLOAD       = 5877219383691972108   # 📥  TgAndroidIcons
    UPLOAD         = 5913236481220022288   # 📤  TgAndroidIcons
    COMPRESS       = 5877316724830768997   # 🗜️  TgAndroidIcons
    EXTRACT        = 5877468380125990242   # 📦  TgAndroidIcons
    UNZIP          = 5785058280397082578   # 📂  open folder, used on the Actions unzip button
    HOME           = 5967822972931542886   # 🏠  TgAndroidIcons
    BACK           = 5877629862306385808   # ◀️  TgAndroidIcons
    NEXT           = 5884123981706956210   # ➡️  TgAndroidIcons
    CLOSE          = 5778527486270770928   # ❌  TgAndroidIcons
    HELP           = 5879785854284599288   # ❓  TgAndroidIcons
    LANG           = 5879585266426973039   # 🌐  TgAndroidIcons
    LINK           = 5778586619380503542   # 🔗  TgAndroidIcons
    BROADCAST      = 5424818078833715060   # 📢  NewsEmoji
    ROCKET         = 5857290546459973028   # 🚀  DMJUnigramAnimationEmoji
    STAR           = 5807752501042089473   # ⭐️  EmojiStatus
    SPARKLES       = 5989815447459991163   # ✨  CenterOfEmoji980633
    USER           = 5771887475421090729   # 👤  TgAndroidIcons
    USERS          = 5942877472163892475   # 👥  TgAndroidIcons
    CROWN          = 5807868868886009920   # 👑  EmojiStatus

    # ── Keycap Digits ─────────────────────────────────────────────────────────
    KEYCAP_1       = 5877478146864846721   # 1️⃣
    KEYCAP_2       = 5877478146864846722   # 2️⃣
    KEYCAP_3       = 5877478146864846723   # 3️⃣
    KEYCAP_4       = 5877478146864846724   # 4️⃣
    KEYCAP_5       = 5877478146864846725   # 5️⃣
    KEYCAP_6       = 5877478146864846726   # 6️⃣
    KEYCAP_7       = 5877478146864846727   # 7️⃣
    KEYCAP_8       = 5877478146864846728   # 8️⃣
    KEYCAP_9       = 5877478146864846729   # 9️⃣
    KEYCAP_10      = 5877478146864846730   # 🔟


def keycap_id(n: int) -> int | None:
    """Return the custom emoji ID for number 1-10."""
    mapping = {
        1: Emoji.KEYCAP_1,
        2: Emoji.KEYCAP_2,
        3: Emoji.KEYCAP_3,
        4: Emoji.KEYCAP_4,
        5: Emoji.KEYCAP_5,
        6: Emoji.KEYCAP_6,
        7: Emoji.KEYCAP_7,
        8: Emoji.KEYCAP_8,
        9: Emoji.KEYCAP_9,
        10: Emoji.KEYCAP_10,
    }
    return mapping.get(n)


class EmojiTag:
    """Pre-rendered Telegram custom emoji HTML tags for use in HTML message text.

    Spelling: <tg-emoji emoji-id="...">glyph</tg-emoji>
    """
    # File formats
    ZIP            = f'<tg-emoji emoji-id="{Emoji.ZIP}">🗃</tg-emoji>'
    FOLDER         = f'<tg-emoji emoji-id="{Emoji.FOLDER}">📁</tg-emoji>'
    FILE           = f'<tg-emoji emoji-id="{Emoji.FILE}">📄</tg-emoji>'
    DOCUMENT       = f'<tg-emoji emoji-id="{Emoji.DOCUMENT}">📑</tg-emoji>'
    ARCHIVE        = f'<tg-emoji emoji-id="{Emoji.ARCHIVE}">🗜️</tg-emoji>'
    VIDEO          = f'<tg-emoji emoji-id="{Emoji.VIDEO}">🎬</tg-emoji>'
    AUDIO          = f'<tg-emoji emoji-id="{Emoji.AUDIO}">🎵</tg-emoji>'
    IMAGE          = f'<tg-emoji emoji-id="{Emoji.IMAGE}">🖼</tg-emoji>'
    CODE           = f'<tg-emoji emoji-id="{Emoji.CODE}">💻</tg-emoji>'

    # Status & Navigation
    SUCCESS        = f'<tg-emoji emoji-id="{Emoji.SUCCESS}">✅</tg-emoji>'
    ERROR          = f'<tg-emoji emoji-id="{Emoji.ERROR}">❌</tg-emoji>'
    TICK           = f'<tg-emoji emoji-id="{Emoji.TICK}">✅</tg-emoji>'
    UNTICK         = f'<tg-emoji emoji-id="{Emoji.UNTICK}">❌</tg-emoji>'
    WARNING        = f'<tg-emoji emoji-id="{Emoji.WARNING}">⚠️</tg-emoji>'
    INFO           = f'<tg-emoji emoji-id="{Emoji.INFO}">ℹ️</tg-emoji>'
    LOADING        = f'<tg-emoji emoji-id="{Emoji.LOADING}">⚙️</tg-emoji>'
    SETTINGS       = f'<tg-emoji emoji-id="{Emoji.SETTINGS}">⚙️</tg-emoji>'
    REFRESH        = f'<tg-emoji emoji-id="{Emoji.REFRESH}">🔄</tg-emoji>'
    PING           = f'<tg-emoji emoji-id="{Emoji.PING}">⚡</tg-emoji>'
    STATS          = f'<tg-emoji emoji-id="{Emoji.STATS}">📊</tg-emoji>'
    CLOCK          = f'<tg-emoji emoji-id="{Emoji.CLOCK}">⏱</tg-emoji>'

    # Security & Storage
    LOCK           = f'<tg-emoji emoji-id="{Emoji.LOCK}">🔒</tg-emoji>'
    UNLOCK         = f'<tg-emoji emoji-id="{Emoji.UNLOCK}">🔓</tg-emoji>'
    KEY            = f'<tg-emoji emoji-id="{Emoji.KEY}">🔑</tg-emoji>'
    SHIELD         = f'<tg-emoji emoji-id="{Emoji.SHIELD}">🛡</tg-emoji>'
    STORAGE        = f'<tg-emoji emoji-id="{Emoji.STORAGE}">💾</tg-emoji>'
    CLOUD          = f'<tg-emoji emoji-id="{Emoji.CLOUD}">☁️</tg-emoji>'
    TRASH          = f'<tg-emoji emoji-id="{Emoji.TRASH}">🗑</tg-emoji>'
    CANCEL         = f'<tg-emoji emoji-id="{Emoji.CANCEL}">🛑</tg-emoji>'

    # Actions
    DOWNLOAD       = f'<tg-emoji emoji-id="{Emoji.DOWNLOAD}">📥</tg-emoji>'
    UPLOAD         = f'<tg-emoji emoji-id="{Emoji.UPLOAD}">📤</tg-emoji>'
    COMPRESS       = f'<tg-emoji emoji-id="{Emoji.COMPRESS}">🗜️</tg-emoji>'
    EXTRACT        = f'<tg-emoji emoji-id="{Emoji.EXTRACT}">📦</tg-emoji>'
    UNZIP          = f'<tg-emoji emoji-id="{Emoji.UNZIP}">📂</tg-emoji>'
    HOME           = f'<tg-emoji emoji-id="{Emoji.HOME}">🏠</tg-emoji>'
    BACK           = f'<tg-emoji emoji-id="{Emoji.BACK}">◀️</tg-emoji>'
    NEXT           = f'<tg-emoji emoji-id="{Emoji.NEXT}">➡️</tg-emoji>'
    CLOSE          = f'<tg-emoji emoji-id="{Emoji.CLOSE}">❌</tg-emoji>'
    HELP           = f'<tg-emoji emoji-id="{Emoji.HELP}">❓</tg-emoji>'
    LANG           = f'<tg-emoji emoji-id="{Emoji.LANG}">🌐</tg-emoji>'
    LINK           = f'<tg-emoji emoji-id="{Emoji.LINK}">🔗</tg-emoji>'
    BROADCAST      = f'<tg-emoji emoji-id="{Emoji.BROADCAST}">📢</tg-emoji>'
    ROCKET         = f'<tg-emoji emoji-id="{Emoji.ROCKET}">🚀</tg-emoji>'
    STAR           = f'<tg-emoji emoji-id="{Emoji.STAR}">⭐️</tg-emoji>'
    SPARKLES       = f'<tg-emoji emoji-id="{Emoji.SPARKLES}">✨</tg-emoji>'
    USER           = f'<tg-emoji emoji-id="{Emoji.USER}">👤</tg-emoji>'
    USERS          = f'<tg-emoji emoji-id="{Emoji.USERS}">👥</tg-emoji>'
    CROWN          = f'<tg-emoji emoji-id="{Emoji.CROWN}">👑</tg-emoji>'
