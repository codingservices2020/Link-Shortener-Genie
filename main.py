import os
import re
import requests
from gdshortener import ISGDShortener
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, filters, ConversationHandler
)
from keep_alive import keep_alive
keep_alive()

# from dotenv import load_dotenv
# load_dotenv()

# Bot token
TOKEN = os.getenv("TOKEN")

# Initialize GDShortener
gds = ISGDShortener()

# States for conversations
CUSTOM_URL, CUSTOM_ALIAS = range(2)
LOGSTATS_URL = range(1)
EXPAND_URL = range(1)

# Lookup long URL from short
def lookup_isgd(short_url):
    api = "https://is.gd/forward.php"
    params = {"format": "json", "shorturl": short_url.replace("https://is.gd/", "")}
    response = requests.get(api, params=params).json()
    return response.get("url")

# Start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "Welcome to the is.gd URL Shortener Bot! \u2702\ufe0f\n\n"
        "Send a long URL to shorten it, or use /help to see all commands."
    )
    await update.message.reply_text(msg)


# Default shortener (for plain URLs)
async def shorten(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    if not url or not url.startswith("http"):
        await update.message.reply_text("Please send a valid URL starting with http or https.")
        return
    try:
        short = gds.shorten(url)[0]
        await update.message.reply_text(f"🔰*Shortened Link*🔰\n\n"
                                        f"*🔗 Link:* {short}",
                                        parse_mode="Markdown"
                                        )
    except Exception as e:
        message = extract_error_message(str(e))
        await update.message.reply_text(f"❌ Error: {message}")

# --- Custom Conversation ---
async def custom_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Please send the URL you want to shorten.")
    return CUSTOM_URL

async def custom_get_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    if not url or not url.startswith("http"):
        await update.message.reply_text("Please send a valid URL starting with http or https.")
        return
    context.user_data['custom_url'] = url
    await update.message.reply_text(f"Now send me the custom alias you want which must be at least 5 characters long.\n\n"
                                    f"*For Example:* If you enter *thor5*, then short URL will be like this https://is.gd/thor5",
                                    parse_mode="Markdown"
                                    )
    return CUSTOM_ALIAS

async def custom_get_alias(update: Update, context: ContextTypes.DEFAULT_TYPE):
    alias = update.message.text.strip()
    url = context.user_data['custom_url']
    try:
        short = gds.shorten(url, custom_url=alias)[0]
        await update.message.reply_text(f"🔰*Custom Short URL*🔰\n\n"
                                        f"*🔗 Link:* {short}",
                                        parse_mode="Markdown"
                                        )
    except Exception as e:
        message = extract_error_message(str(e))
        await update.message.reply_text(f"❌ Error: {message}")
    return ConversationHandler.END

# --- LogStats Conversation ---
async def logstats_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Please send the URL to shorten whose stats you want to monitor.")
    return LOGSTATS_URL

async def logstats_get_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    if not url or not url.startswith("http"):
        await update.message.reply_text("Please send a valid URL starting with http or https.")
        return
    try:
        short = gds.shorten(url, log_stat=True)[0]
        link_statistics = f"https://is.gd/stats.php?url={short.split('/')[-1]}"
        await update.message.reply_text(f"🔰*Short Link with Statistics*🔰\n\n"
                                        f"✅ *Stats-enabled Short URL:* {short}\n\n"
                                        f"🌐 To see the stats of this short link, visit this [web-page]({link_statistics})",
                                        parse_mode="Markdown"
                                        )
    except Exception as e:
        message = extract_error_message(str(e))
        await update.message.reply_text(f"❌ Error: {message}")
    return ConversationHandler.END

# --- Expand Conversation ---
async def expand_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Please send the short is.gd URL you want to expand.")
    return EXPAND_URL

async def expand_get_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    short_url = update.message.text.strip()
    try:
        long = lookup_isgd(short_url)
        await update.message.reply_text(f"🔰*Expanded URL*🔰\n\n"
                                        f"*🔗 Link:* {long}",
                                        parse_mode="Markdown"
                                        )
    except Exception as e:
        message = extract_error_message(str(e))
        await update.message.reply_text(f"❌ Error: {message}")
    return ConversationHandler.END

# --- Cancel ---
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Operation cancelled.")
    return ConversationHandler.END


def extract_error_message(error_text: str) -> str:
    match = re.findall(r"Error description: \[(.*?)\]", error_text)
    return match[-1] if match else error_text

# ------------------ Help Command ------------------ #
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        """
Commands available:
/start - Short URL without customisation
/custom – Custom short URL
/logstats – Shorten URL with stats logging
/expand – Expand short URL
/help - Show this help message
"""
    )

# --- Main Function ---
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))

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

    # This must be added last!
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, shorten))

    print("Bot is running...")
    app.run_polling()

if __name__ == '__main__':
    main()
