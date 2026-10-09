import os
import io
import re
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, filters, ConversationHandler
)
from shortio import (
    shorten_url, shorten_multiple_urls,
    expand_url, update_short_url_slug,
    get_stats, get_qr_for_url,
    SHORTIO_DOMAIN
)
from keep_alive import keep_alive
keep_alive()

# from dotenv import load_dotenv
# load_dotenv()


# Bot token
TOKEN = os.getenv("TOKEN")

# Custom Emoji HTML strings for messages
CRACKER_EMOJI = '<tg-emoji emoji-id="5276032951342088188">💥</tg-emoji>'
LINK_EMOJI = '<tg-emoji emoji-id="5271604874419647061">🔗</tg-emoji>'
CANCEL_EMOJI = '<tg-emoji emoji-id="5240241223632954241">🚫</tg-emoji>'
CROSS_EMOJI = '<tg-emoji emoji-id="5210952531676504517">❌</tg-emoji>'
RECYCLE_EMOJI = '<tg-emoji emoji-id="4967897119760319376">♻️</tg-emoji>'
BOT_EMOJI = '<tg-emoji emoji-id="5372981976804366741">🤖</tg-emoji>'
GREEN_TICK_EMOJI = '<tg-emoji emoji-id="6003394583566749782">✅</tg-emoji>'
RED_TICK_EMOJI = '<tg-emoji emoji-id="6006039858219324431">✅</tg-emoji>'
NAMASTE_EMOJI = '<tg-emoji emoji-id="5472189549473963781">🙏</tg-emoji>'
WARNING_EMOJI = '<tg-emoji emoji-id="5420323339723881652">⚠️</tg-emoji>'
FIRE_EMOJI = '<tg-emoji emoji-id="5424972470023104089">🔥</tg-emoji>'
GLOBE_EMOJI = '<tg-emoji emoji-id="5447410659077661506">🌍</tg-emoji>'
PENCIL_EMOJI = '<tg-emoji emoji-id="5395444784611480792">✍️</tg-emoji>'
HUMAN_TAP_EMOJI = '<tg-emoji emoji-id="5019759554234156094">👆</tg-emoji>'
CLICK_EMOJI = '<tg-emoji emoji-id="5368800761717203681">👇</tg-emoji>'
BULB_EMOJI = '<tg-emoji emoji-id="5422439311196834318">💡</tg-emoji>'




# Regex to detect all URLs in a message
URL_PATTERN = re.compile(r'https?://[^\s]+')

# States for conversations
CUSTOM_URL, CUSTOM_ALIAS = range(2)
LOGSTATS_URL = range(1)
EXPAND_URL = range(1)
QRCODE_URL = range(1)
EDIT_TARGET, EDIT_NEW_SLUG = range(2)


# --- Start Command ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "👋 Welcome to the Short.io URL Shortener Bot!\n\n"
        "• Send a URL (or multiple URLs at once) to shorten them.\n"
        "• Use /custom to create a custom short link.\n"
        "• Use /editslug to change the shortcode (slug) of an existing link.\n"
        "• Use /QRcode to generate a QR code for any link.\n"
        "• Use /logstats to check click stats.\n"
        "• Use /expand to see where a short link leads.\n"
        "• Use /help for the full command list."
    )
    await update.message.reply_text(msg)


# --- Default Shortener (Handles single or multiple URLs) ---
async def shorten(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    urls = URL_PATTERN.findall(text)

    if not urls:
        await update.message.reply_text("❌ Please send valid URL(s) starting with http:// or https://")
        return

    # Single URL
    if len(urls) == 1:
        url = urls[0]
        result = shorten_url(url)
        if result.get("success"):
            short = result["shortURL"]
            await update.message.reply_text(
                f"{CRACKER_EMOJI} <b>Shortened URL</b> {CRACKER_EMOJI}\n\n"
                f"<b>{LINK_EMOJI} Short Link:</b> {short}",
                parse_mode="HTML"
            )
        else:
            error_message = result.get("error", "Unknown error")
            await update.message.reply_text(f"❌ Error: {error_message}")
        return

    # Multiple URLs (Bulk shortening)
    status_msg = await update.message.reply_text(f"⏳ Shortening {len(urls)} URLs in bulk...")
    bulk_result = shorten_multiple_urls(urls)

    if bulk_result.get("success"):
        results = bulk_result.get("results", [])
        lines = [f"🔰 *Shortened URLs ({len(results)})* 🔰\n"]
        for idx, item in enumerate(results, start=1):
            if item.get("success") and item.get("shortURL"):
                lines.append(f"*{idx}.* `{item['originalURL']}`\n👉 {item['shortURL']}\n")
            else:
                lines.append(f"*{idx}.* `{item['originalURL']}`\n❌ Failed: {item.get('error', 'Error')}\n")

        reply_content = "\n".join(lines)

        # Telegram message length safety check (max 4096 chars)
        if len(reply_content) > 4000:
            for chunk in [reply_content[i:i+4000] for i in range(0, len(reply_content), 4000)]:
                await update.message.reply_text(chunk, parse_mode="Markdown")
        else:
            await update.message.reply_text(reply_content, parse_mode="Markdown")

        try:
            await status_msg.delete()
        except Exception:
            pass
    else:
        error_message = bulk_result.get("error", "Failed to shorten URLs.")
        await status_msg.edit_text(f"❌ Error: {error_message}")


# --- Custom Short URL Conversation ---
async def custom_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Please send the URL you want to shorten:")
    return CUSTOM_URL


async def custom_get_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    if not url or not (url.startswith("http://") or url.startswith("https://")):
        await update.message.reply_text("❌ Please send a valid URL starting with http:// or https://")
        return CUSTOM_URL

    context.user_data['custom_url'] = url
    domain_display = SHORTIO_DOMAIN if SHORTIO_DOMAIN else "example.com"
    await update.message.reply_text(
        f"Now send me the custom alias you want.\n\n"
        f"*For Example:* If you enter *mylink*, your short URL will be `https://{domain_display}/mylink`",
        parse_mode="Markdown"
    )
    return CUSTOM_ALIAS


async def custom_get_alias(update: Update, context: ContextTypes.DEFAULT_TYPE):
    alias = update.message.text.strip()
    url = context.user_data.get('custom_url')

    result = shorten_url(url, custom_alias=alias)
    if result.get("success"):
        short = result["shortURL"]
        await update.message.reply_text(
                f"{CRACKER_EMOJI} <b>Shortened URL</b> {CRACKER_EMOJI}\n\n"
                f"<b>{LINK_EMOJI} Short Link:</b> {short}",
                parse_mode="HTML"
            )
        return ConversationHandler.END
    else:
        error_message = result.get("error", "Error creating custom link.")
        if result.get("status_code") == 409 or "already exists" in str(error_message).lower():
            await update.message.reply_text("❌ This alias is already taken. Please enter a different alias (or /cancel):")
            return CUSTOM_ALIAS
        else:
            await update.message.reply_text(f"❌ Error: {error_message}\n\nPlease try another alias or send /cancel:")
            return CUSTOM_ALIAS


# --- Edit Slug (Shortcode) Conversation ---
async def editslug_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Support inline arguments: /editslug <old_link> <new_slug>
    if context.args and len(context.args) >= 2:
        target_link = context.args[0].strip()
        new_slug = context.args[1].strip()
        res = update_short_url_slug(target_link, new_slug)
        if res.get("success"):
            await update.message.reply_text(
                f"{CRACKER_EMOJI} <b>Shortcode Updated Successfully</b> {CRACKER_EMOJI}\n\n"
                f"<b>{LINK_EMOJI} New Short Link:</b> {res['shortURL']}\n"
                f"<b>{GLOBE_EMOJI} Target URL:</b> {res['originalURL']}\n"
                f"<b>{PENCIL_EMOJI} Slug Changed:</b> `{res.get('old_slug')}` ➔ `{res.get('new_slug')}`",
                parse_mode="HTML"
            )
        else:
            await update.message.reply_text(f"❌ Error: {res.get('error', 'Update failed')}")
        return ConversationHandler.END

    await update.message.reply_text("Please send the existing short link or slug you want to edit:")
    return EDIT_TARGET


async def editslug_get_target(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target = update.message.text.strip()
    expand_res = expand_url(target)

    if not expand_res.get("success"):
        await update.message.reply_text(
            f"❌ Could not find link: {expand_res.get('error', 'Link not found.')}\n\n"
            f"Please enter a valid Short.io link/slug (or /cancel):"
        )
        return EDIT_TARGET

    context.user_data['edit_target'] = target
    context.user_data['edit_old_slug'] = expand_res.get("path")
    context.user_data['edit_orig_url'] = expand_res.get("originalURL")

    await update.message.reply_text(
        f"{GREEN_TICK_EMOJI} <b>Found Link:</b>\n"
        f"<b>{LINK_EMOJI} Current Link:</b> {expand_res.get('shortURL')}\n"
        f"<b>{GLOBE_EMOJI} Target URL:</b> {expand_res.get('originalURL')}\n"
        f"<b>{PENCIL_EMOJI} Current Slug:</b> `{expand_res.get('path')}`\n\n"
        f"Please send the <b>new custom slug</b> (shortcode) you want:",
        parse_mode="HTML"
    )
    return EDIT_NEW_SLUG


async def editslug_get_new_slug(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_slug = update.message.text.strip()
    target = context.user_data.get('edit_target')

    res = update_short_url_slug(target, new_slug)
    if res.get("success"):
        await update.message.reply_text(
            f"{CRACKER_EMOJI} <b>Shortcode Updated Successfully</b> {CRACKER_EMOJI}\n\n"
            f"<b>{LINK_EMOJI} New Short Link:</b> {res['shortURL']}\n"
            f"<b>{GLOBE_EMOJI} Target URL:</b> {res['originalURL']}\n"
            f"<b>{PENCIL_EMOJI} Slug Changed:</b> `{res.get('old_slug')}` ➔ `{res.get('new_slug')}`",
            parse_mode="HTML"
        )
        return ConversationHandler.END
    else:
        error = res.get("error", "Failed to update slug.")
        if "already exists" in str(error).lower():
            await update.message.reply_text("❌ This slug is already in use by another link. Please enter a different slug (or /cancel):")
            return EDIT_NEW_SLUG
        else:
            await update.message.reply_text(f"❌ Error: {error}\n\nPlease enter a different slug (or /cancel):")
            return EDIT_NEW_SLUG


# --- LogStats Conversation ---
async def logstats_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Please send the short link (e.g. `https://up.s.gy/xyz` or `xyz`) whose click statistics you want to check, "
        "or send a new URL to shorten with tracking enabled.",
        parse_mode="Markdown"
    )
    return LOGSTATS_URL


async def logstats_get_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text.strip()
    if not user_input:
        await update.message.reply_text("Please enter a valid link or alias.")
        return LOGSTATS_URL

    # If it's an existing short link or path, fetch stats
    stats = get_stats(user_input)
    if stats.get("success"):
        await update.message.reply_text(
            f"{CRACKER_EMOJI} <b>Link Statistics</b> {CRACKER_EMOJI}\n\n"
            f"<b>{LINK_EMOJI} Short Link:</b> {stats.get('shortURL')}\n"
            f"<b>{GLOBE_EMOJI} Target URL:</b> {stats.get('originalURL')}\n\n"
            f"{CLICK_EMOJI} <b>Total Clicks:</b> {stats.get('totalClicks', 0)}\n"
            f"{HUMAN_TAP_EMOJI} <b>Human Clicks:</b> {stats.get('humanClicks', 0)}",
            parse_mode="HTML"
        )
        return ConversationHandler.END

    # If it's a new long URL, shorten it and notify user
    if user_input.startswith("http://") or user_input.startswith("https://"):
        result = shorten_url(user_input)
        if result.get("success"):
            short = result["shortURL"]
            await update.message.reply_text(
                f"{CRACKER_EMOJI} <b>Short Link with Statistics</b> {CRACKER_EMOJI}\n\n"
                f"<b>{LINK_EMOJI} Short URL:</b> {short}\n\n"
                f"<b>{GLOBE_EMOJI} Click analytics</b> are automatically tracked. You can check stats anytime with /logstats!",
                parse_mode="HTML"
            )
            return ConversationHandler.END

    await update.message.reply_text(
        f"❌ Could not retrieve statistics: {stats.get('error', 'Invalid link or not found.')}"
    )
    return ConversationHandler.END


# --- Expand Conversation ---
async def expand_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Please send the short link or alias you want to expand:")
    return EXPAND_URL


async def expand_get_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    short_url = update.message.text.strip()
    result = expand_url(short_url)
    if result.get("success"):
        long_url = result.get("originalURL")
        await update.message.reply_text(
            f"{CRACKER_EMOJI} <b>Expanded URL</b> {CRACKER_EMOJI}\n\n"
            f"<b>{LINK_EMOJI} Original Link:</b> {long_url}",
            parse_mode="HTML"
        )
    else:
        error_message = result.get("error", "Link not found.")
        await update.message.reply_text(f"❌ Error: {error_message}")
    return ConversationHandler.END


# --- QR Code Helper & Conversation ---
async def process_and_send_qr(update: Update, url_text: str):
    if not url_text:
        await update.message.reply_text("Please send a valid link or URL.")
        return

    status_msg = await update.message.reply_text("⏳ Generating QR code...")
    qr_result = get_qr_for_url(url_text)

    if qr_result.get("success"):
        short_url = qr_result.get("shortURL", url_text)
        caption = (
            f"{CRACKER_EMOJI} <b>QR Code Generated</b> {CRACKER_EMOJI}\n\n"
            f"<b>{LINK_EMOJI} Link:</b> {short_url}"
        )
        try:
            if qr_result.get("image_bytes"):
                photo_file = io.BytesIO(qr_result["image_bytes"])
                photo_file.name = "qrcode.png"
                await update.message.reply_photo(
                    photo=photo_file,
                    caption=caption,
                    parse_mode="HTML"
                )
            elif qr_result.get("qr_url"):
                await update.message.reply_photo(
                    photo=qr_result["qr_url"],
                    caption=caption,
                    parse_mode="HTML"
                )
        except Exception as photo_err:
            if qr_result.get("qr_url"):
                await update.message.reply_photo(
                    photo=qr_result["qr_url"],
                    caption=caption,
                    parse_mode="HTML"
                )
            else:
                await status_msg.edit_text(f"❌ Error sending QR photo: {photo_err}")
                return

        try:
            await status_msg.delete()
        except Exception:
            pass
    else:
        error_message = qr_result.get("error", "Failed to generate QR code.")
        await status_msg.edit_text(f"❌ Error: {error_message}")


async def qrcode_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Support inline argument e.g. /QRcode https://example.com
    if context.args:
        url_arg = " ".join(context.args).strip()
        await process_and_send_qr(update, url_arg)
        return ConversationHandler.END

    await update.message.reply_text("Please send the URL or short link you want to generate a QR code for:")
    return QRCODE_URL


async def qrcode_get_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url_text = update.message.text.strip()
    await process_and_send_qr(update, url_text)
    return ConversationHandler.END


# --- Cancel ---
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Operation cancelled.")
    return ConversationHandler.END


# --- Help Command ---
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"{BOT_EMOJI} <b>Available Commands:</b>\n\n"
        f"/start - Start the bot\n"
        f"/custom - Create a custom alias short URL\n"
        f"/editslug - Edit/change the shortcode (slug) of an existing short link\n"
        f"/logstats - View click statistics for a short link\n"
        f"/expand - Expand a short link to its original destination\n"
        f"/QRcode - Generate a QR code for a link\n"
        f"/cancel - Cancel the current conversation\n"
        f"/help - Show this help message\n\n"
        f"<b>{BULB_EMOJI} Tip:</b> You can also send multiple URLs in a single message to shorten them all at once!",
        parse_mode="HTML"
    )


# --- Main Function ---
def main():
    if not TOKEN:
        print("❌ Error: Telegram Bot TOKEN is missing in .env file.")
        return

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("cancel", cancel))

    # Conversation handlers
    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler("custom", custom_start)],
        states={
            CUSTOM_URL: [MessageHandler(filters.TEXT & ~filters.COMMAND, custom_get_url)],
            CUSTOM_ALIAS: [MessageHandler(filters.TEXT & ~filters.COMMAND, custom_get_alias)],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    ))

    app.add_handler(ConversationHandler(
        entry_points=[
            CommandHandler(["editslug", "edit", "slug", "updateslug"], editslug_start)
        ],
        states={
            EDIT_TARGET: [MessageHandler(filters.TEXT & ~filters.COMMAND, editslug_get_target)],
            EDIT_NEW_SLUG: [MessageHandler(filters.TEXT & ~filters.COMMAND, editslug_get_new_slug)],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    ))

    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler("logstats", logstats_start)],
        states={
            LOGSTATS_URL: [MessageHandler(filters.TEXT & ~filters.COMMAND, logstats_get_url)],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    ))

    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler("expand", expand_start)],
        states={
            EXPAND_URL: [MessageHandler(filters.TEXT & ~filters.COMMAND, expand_get_url)],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    ))

    app.add_handler(ConversationHandler(
        entry_points=[
            CommandHandler(["QRcode", "qrcode", "qr", "QR"], qrcode_start)
        ],
        states={
            QRCODE_URL: [MessageHandler(filters.TEXT & ~filters.COMMAND, qrcode_get_url)],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    ))

    # Default message handler for plain text URLs (single or multi)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, shorten))

    print("🚀 Short.io Telegram Bot is running...")
    app.run_polling()


if __name__ == '__main__':
    main()
