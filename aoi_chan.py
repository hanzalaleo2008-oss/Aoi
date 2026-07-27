import os
import logging
import re
from datetime import datetime, time
import pytz
import requests

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ChatPermissions
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ChatMemberHandler,
    ContextTypes,
    filters,
)

# -------------------------------------------------------------------
# Configuration & Setup
# -------------------------------------------------------------------
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

group_settings = {}
user_history = {}
custom_filters = {}
MM_TZ = pytz.timezone('Asia/Yangon')

# -------------------------------------------------------------------
# Utility Functions
# -------------------------------------------------------------------
def get_chat_settings(chat_id: int) -> dict:
    return group_settings.setdefault(chat_id, {
        'forwardblock': False,
        'linkblock': False,
        'autoban': False,
        'joineddelete': False,
        'track': False,
        'permission': False,
        'open': True,
        'open_text': "🏪 Group ကို အခုပဲ ဖွင့်လိုက်ပါပြီရှင်!",
        'closed_text': "🔒 Group ကို ခဏ ပိတ်ထားပါသည်ရှင်!",
        'opentimer_job': None,
        'closedtimer_job': None,
        'welcome': False,
        'welcome_text': "မင်္ဂလာပါ {mention} ရှင်! {name} မှ ကြိုဆိုပါတယ် ✨",
        'welcometimer': 0,
        'goodbye': False,
        'goodbye_text': "{name} ထွက်သွားပါပြီ 😢",
        'goodbyetimer': 0,
        'idcopy': True,
        'replydone': False,
        'replydone_text': "✔️ ထည့်ပြီးပါပြီရှင့်\nကျေးဇူးတင်ပါတယ်\nနောက်လည်းလာခဲ့ပါအုံးနော်",
        'recdone': False,
        'calculator': True,
    })

async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if not update.effective_chat or update.effective_chat.type == "private":
        return True
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    member = await context.bot.get_chat_member(chat_id, user_id)
    return member.status in ['creator', 'administrator']

async def toggle_setting(update: Update, context: ContextTypes.DEFAULT_TYPE, key: str, name: str):
    if not await is_admin(update, context):
        await update.message.reply_text("⚠️ ဒီ Command ကို Admin များသာ အသုံးပြုနိုင်ပါသည်။")
        return
    chat_id = update.effective_chat.id
    args = context.args
    settings = get_chat_settings(chat_id)
    if args and args[0].lower() in ['on', 'off']:
        state = (args[0].lower() == 'on')
        settings[key] = state
        await update.message.reply_text(f"✅ {name} စနစ်ကို `{state}` သို့ ပြောင်းလဲလိုက်ပါပြီ။", parse_mode='Markdown')
    else:
        await update.message.reply_text(
            f"❌ အိုင်း… Command မှားသွားပါပြီနော် 💕\n\n"
            f"💡 Example:\n"
            f"• `/{key} on`\n"
            f"• `/{key} off`\n\n"
            f"မမက အေးဆေးပြောပေးမယ်နော် ✨",
            parse_mode='Markdown'
        )

# -------------------------------------------------------------------
# Friendly Wrong Command Helper
# -------------------------------------------------------------------
async def wrong_command_helper(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message and update.message.text.startswith("/"):
        cmd = update.message.text.split()[0]
        known_cmds = [
            "/start","/help","/forwardblock","/linkblock","/autoban","/joineddelete",
            "/track","/check","/info","/permission","/setopen","/setclosed",
            "/opentimer","/closedtimer","/welcome","/setwelcome","/welcometimer",
            "/goodbye","/setgoodbye","/goodbyetimer","/idcopy","/replydone",
            "/setreplydone","/recdone","/calculator","/setfilter","/deletefilter",
            "/ban","/unban","/mute","/kick","/resetall","/music"
        ]
        if cmd not in known_cmds:
            await update.message.reply_text(
                f"အိုင်း… မမ့ Command `{cmd}` ကို မသိဘူးလေ 😘\n\n"
                f"💡 သုံးလို့ရတဲ့ Command များကို ကြည့်ချင်ရင် `/help` ကို သုံးပါနော် ✨\n"
                f"မမက အချိန်တိုင်း အေးဆေးညွှန်ပေးမယ် 💕",
                parse_mode='Markdown'
            )

# -------------------------------------------------------------------
# Example Commands (keeping old ones intact)
# -------------------------------------------------------------------
async def cmd_start(update, context):
    await update.message.reply_text("မင်္ဂလာပါရှင်၊ Aoi Chan Bot မှ ကြိုဆိုပါတယ်! ✨\n\nအသေးစိတ် Command များကို ကြည့်ရန် /help ကို သုံးပါ။")

async def cmd_help(update, context):
    help_text = (
        "✨ <b>Aoi Chan Bot - Help Menu</b> ✨\n\n"
        "• /permission on/off - Group Open/Close\n"
        "• /opentimer - Set Open Time\n"
        "• /closedtimer - Set Close Time\n"
        "• /idcopy - Copy Game ID\n"
        "• /replydone - Confirm/Delete Buttons\n"
        "• /welcome - Toggle Welcome\n"
        "• /music - Download Audio Preview\n"
    )
    await update.message.reply_text(help_text, parse_mode='HTML')

# -------------------------------------------------------------------
# Main Initialization
# -------------------------------------------------------------------
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Register core commands
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))

    # Register wrong command helper (catch-all)
    app.add_handler(MessageHandler(filters.COMMAND, wrong_command_helper))

    # Keep all other handlers (forwardblock, linkblock, etc.)
    app.add_handler(CommandHandler("forwardblock", cmd_forwardblock))
    app.add_handler(CommandHandler("linkblock", cmd_linkblock))
    app.add_handler(CommandHandler("autoban", cmd_autoban))
    app.add_handler(CommandHandler("joineddelete", cmd_joineddelete))
    app.add_handler(CommandHandler("track", cmd_track))
    app.add_handler(CommandHandler("check", cmd_check))
    app.add_handler(CommandHandler("info", cmd_info))
    app.add_handler(CommandHandler("permission", cmd_permission))
    app.add_handler(CommandHandler("setopen", cmd_setopen))
    app.add_handler(CommandHandler("setclosed", cmd_setclosed))
    app.add_handler(CommandHandler("opentimer", cmd_opentimer))
    app.add_handler(CommandHandler("closedtimer", cmd_closedtimer))
    app.add_handler(CommandHandler("welcome", cmd_welcome))
    app.add_handler(CommandHandler("setwelcome", cmd_setwelcome))
    app.add_handler(CommandHandler("welcometimer", cmd_welcometimer))
    app.add_handler(CommandHandler("goodbye", cmd_goodbye))
    app.add_handler(CommandHandler("setgoodbye", cmd_setgoodbye))
    app.add_handler(CommandHandler("goodbyetimer", cmd_goodbyetimer))
    app.add_handler(CommandHandler("idcopy", cmd_idcopy_toggle))
    app.add_handler(CommandHandler("replydone", cmd_replydone))
    app.add_handler(CommandHandler("setreplydone", cmd_setreplydone))
    app.add_handler(CommandHandler("recdone", cmd_recdone))
    app.add_handler(CommandHandler("calculator", cmd_calculator))
    app.add_handler(CommandHandler("setfilter", cmd_setfilter))
    app.add_handler(CommandHandler("deletefilter", cmd_deletefilter))
    app.add_handler(CommandHandler("ban", cmd_ban))
    app.add_handler(CommandHandler("unban", cmd_unban))
    app.add_handler(CommandHandler("mute", cmd_mute))
    app.add_handler(CommandHandler("kick", cmd_kick))
    app.add_handler(CommandHandler("resetall", cmd_resetall))
    app.add_handler(CommandHandler("music", cmd_music))

    app.run_polling()

if __name__ == "__main__":
    main()
