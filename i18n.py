"""i18n.py — Internationalization texts for Zipper Bot with Rich Message Formatting."""

from utils.emoji import EmojiTag

TEXTS = {
    "en": {
        "welcome": "Welcome to File Zipper Bot!",
        "choose_lang": f"{EmojiTag.LANG} <b>Language Selection</b>\n\nPlease select your preferred language below:",
        "lang_set": f"{EmojiTag.SUCCESS} <b>Language set to English!</b>\n\nYou can change it anytime with /lang or from the menu.",
        "lang_btn_en": "🇬🇧 English",
        "lang_btn_fa": "🇮🇷 فارسی",
        "start_msg": (
            f"{EmojiTag.ARCHIVE} <h1>File Zipper Bot</h1>\n"
            f"<blockquote expandable>"
            f"High-performance file compression, archive encryption, and cloud transfers directly on Telegram."
            f"</blockquote>\n\n"
            f"{EmojiTag.STAR} <b>Core Capabilities:</b>\n"
            f"• <b>ZIP Compression:</b> Bundle multiple files into single archives\n"
            f"• <b>Password Protection:</b> Encrypt archives with standard zip encryption\n"
            f"• <b>Direct Downloader:</b> Send any HTTP/HTTPS direct link to download\n"
            f"• <b>Large File Hosting:</b> Auto-upload archives &gt;2 GB to private cloud\n\n"
            f"{EmojiTag.INFO} <b>Storage Limits:</b>\n"
            f"• Single File Limit: <code>2.00 GB</code>\n"
            f"• Total Quota: <code>4.50 GB</code>\n\n"
            f"<i>Send me any file or direct download link to begin!</i>"
        ),
    },
    "fa": {
        "welcome": "به ربات فایل زیپر خوش آمدید!",
        "choose_lang": f"{EmojiTag.LANG} <b>انتخاب زبان</b>\n\nلطفاً زبان مورد نظر خود را انتخاب کنید:",
        "lang_set": f"{EmojiTag.SUCCESS} <b>زبان به فارسی تغییر یافت!</b>\n\nشما می‌توانید هر زمان با دستور /lang آن را تغییر دهید.",
        "lang_btn_en": "🇬🇧 English",
        "lang_btn_fa": "🇮🇷 فارسی",
        "start_msg": (
            f"{EmojiTag.ARCHIVE} <h1>ربات فشرده‌ساز فایل</h1>\n"
            f"<blockquote expandable>"
            f"فشرده‌سازی سریع فایل‌ها، ساخت آرشیو‌های رمزگذاری شده و انتقال مستقیم ابری در تلگرام."
            f"</blockquote>\n\n"
            f"{EmojiTag.STAR} <b>امکانات اصلی:</b>\n"
            f"• <b>فشرده‌سازی ZIP:</b> تبدیل چندین فایل به یک فایل فشرده\n"
            f"• <b>رمزگذاری:</b> ساخت فایل‌های ZIP ایمن با رمز عبور\n"
            f"• <b>دانلودر مستقیم:</b> ارسال لینک مستقیم برای دانلود\n"
            f"• <b>آپلود ابری:</b> آپلود خودکار فایل‌های بالای ۲ گیگابایت\n\n"
            f"{EmojiTag.INFO} <b>محدودیت‌های ذخیره‌سازی:</b>\n"
            f"• حداکثر حجم هر فایل: <code>۲.۰۰ گیگابایت</code>\n"
            f"• ظرفیت کل فضای کاربری: <code>۴.۵۰ گیگابایت</code>\n\n"
            f"<i>هر فایل یا لینک دانلودی را برای شروع ارسال کنید!</i>"
        ),
    }
}
