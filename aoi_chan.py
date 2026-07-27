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
# Security & Group Guard Commands
# -------------------------------------------------------------------
async def cmd_forwardblock(update, context): await toggle_setting(update, context, 'forwardblock', 'Forward Block')
async def cmd_linkblock(update, context): await toggle_setting(update, context, 'linkblock', 'Link Block')
async def cmd_autoban(update, context): await toggle_setting(update, context, 'autoban', 'Auto-Ban')
async def cmd_joineddelete(update, context): await toggle_setting(update, context, 'joineddelete', 'Joined Delete')

# -------------------------------------------------------------------
# Tracking & Info
# -------------------------------------------------------------------
async def cmd_track(update, context): await toggle_setting(update, context, 'track', 'User Track')

async def cmd_check(update, context):
    user_id = update.effective_user.id
    if update.message.reply_to_message:
        user_id = update.message.reply_to_message.from_user.id
    history = user_history.get(user_id, [])
    if not history:
        await update.message.reply_text("No history recorded starting from 11 July 2026.")
        return
    text = "<b>User History Log:</b>\n"
    for item in history:
        text += f"• Name: {item['first_name']} | @{item['username']}\n"
    await update.message.reply_text(text, parse_mode='HTML')

async def cmd_info(update, context):
    user = update.effective_user
    if update.message.reply_to_message:
        user = update.message.reply_to_message.from_user
    info_text = (
        f"<b>👤 User Information:</b>\n\n"
        f"• First Name: {user.first_name}\n"
        f"• Username: @{user.username if user.username else 'N/A'}\n"
        f"• User ID: <code>{user.id}</code>\n"
        f"• Is Bot: {user.is_bot}\n"
    )
    await update.message.reply_text(info_text, parse_mode='HTML')

# -------------------------------------------------------------------
# (Continue with all other functions: open/close group, timers, welcome/goodbye, MLBB tools, filters, moderation, music, etc.)
# -------------------------------------------------------------------

# -------------------------------------------------------------------
# General Commands
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

    # Wrong command helper
    app.add_handler(MessageHandler(filters.COMMAND, wrong_command_helper))

    # Register all other handlers
    app.add_handler(CommandHandler("forwardblock",
