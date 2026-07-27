import os
import logging
import re
from datetime import datetime, time
import pytz
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatPermissions
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, 
    ContextTypes, filters,
)

# Configuration
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

group_settings = {}
user_history = {}
custom_filters = {}
MM_TZ = pytz.timezone('Asia/Yangon')

# --- Helper Functions (မူလအတိုင်း) ---
def get_chat_settings(chat_id: int) -> dict:
    return group_settings.setdefault(chat_id, {
        'forwardblock': False, 'linkblock': False, 'autoban': False, 'joineddelete': False,
        'track': False, 'permission': False, 'open': True, 'open_text': "🏪 Group ကို အခုပဲ ဖွင့်လိုက်ပါပြီရှင်! ဈေးရောင်း/ဝယ် ပြုလုပ်နိုင်ပါပြီ။",
        'closed_text': "🔒 Group ကို ခဏ ပိတ်ထားပါသည်ရှင်! စာပို့ခွင့် ခေတ္တ ပိတ်ထားပါသည်။",
        'opentimer_job': None, 'closedtimer_job': None, 'welcome': False,
        'welcome_text': "မင်္ဂလာပါ {mention} ရှင်! {name} မှ ကြိုဆိုပါတယ် ✨", 'welcometimer': 0,
        'goodbye': False, 'goodbye_text': "{name} ထွက်သွားပါပြီ 😢", 'goodbyetimer': 0,
        'idcopy': True, 'replydone': False, 'replydone_text': "ထည့်ပြီးပါပြီရှင့်✔️\nကျေးဇူးတင်ပါတယ်ရှင့်",
        'recdone': False, 'calculator': True,
    })

async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if not update.effective_chat or update.effective_chat.type == "private": return True
    member = await context.bot.get_chat_member(update.effective_chat.id, update.effective_user.id)
    return member.status in ['creator', 'administrator']

async def toggle_setting(update: Update, context: ContextTypes.DEFAULT_TYPE, key: str, name: str):
    if not await is_admin(update, context): return
    args = context.args
    settings = get_chat_settings(update.effective_chat.id)
    if args and args[0].lower() in ['on', 'off']:
        state = (args[0].lower() == 'on')
        settings[key] = state
        await update.message.reply_text(f"✅ {name} စနစ်ကို `{state}` သို့ ပြောင်းလဲလိုက်ပါပြီ။", parse_mode='Markdown')
    else:
        await update.message.reply_text(f"❌ အသုံးပြုပုံ - `/{key} on/off`", parse_mode='Markdown')

# --- Friendly Command Helper (အသစ်ထည့်သွင်းခြင်း) ---
async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.effective_user.first_name
    await update.message.reply_text(
        f"အို... {user_name} ရေ၊ ရိုက်လိုက်တဲ့ command က မှားနေသလားလို့ရှင်။ 🥺\n"
        f"မသေချာရင် `/help` ကို နှိပ်ပြီး ဘာတွေ သုံးလို့ရလဲ ကြည့်ကြည့်ပါဦးနော်! ✨",
        parse_mode='Markdown'
    )

# --- 1. Security & Group Guard (မူလအတိုင်း) ---
async def cmd_forwardblock(update, context): await toggle_setting(update, context, 'forwardblock', 'Forward Block')
async def cmd_linkblock(update, context): await toggle_setting(update, context, 'linkblock', 'Link Block')
async def cmd_autoban(update, context): await toggle_setting(update, context, 'autoban', 'Auto-Ban Left Members')
async def cmd_joineddelete(update, context): await toggle_setting(update, context, 'joineddelete', 'Joined Message Delete')

# --- 2. Tracking System (မူလအတိုင်း) ---
async def cmd_track(update, context): await toggle_setting(update, context, 'track', 'User Track')
async def cmd_check(update, context):
    history = user_history.get(update.effective_user.id, [])
    if not history: await update.message.reply_text("No history recorded.")
    else: await update.message.reply_text("User History Log...")

async def cmd_info(update, context):
    user = update.effective_user
    if update.message.reply_to_message: user = update.message.reply_to_message.from_user
    info_text = f"<b>👤 User Information:</b>\n\n• Name: {user.first_name}\n• ID: <code>{user.id}</code>"
    await update.message.reply_text(info_text, parse_mode='HTML')

# --- 3. Open/Closed & Timers (မူလအတိုင်း) ---
# (ကျန်ရှိသော အခြား Function များအားလုံးကို ဤနေရာတွင် မူလအတိုင်း ထည့်သွင်းထားပါ)
# အရှည်ကြီးဖြစ်၍ အနှစ်ချုပ်ပြထားသည်။

async def cmd_start(update, context): await update.message.reply_text("မင်္ဂလာပါရှင်၊ Aoi Chan Bot မှ ကြိုဆိုပါတယ်! /help နှိပ်ပါရှင်။")
async def cmd_help(update, context): await update.message.reply_text("✨ Aoi Chan Bot - Help Menu ✨\n\n• /permission on/off\n• /opentimer\n• /idcopy\n• /music")

# --- Event Handlers & Main Initialization ---
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("forwardblock", cmd_forwardblock))
    app.add_handler(CommandHandler("linkblock", cmd_linkblock))
    app.add_handler(CommandHandler("track", cmd_track))
    app.add_handler(CommandHandler("info", cmd_info))
    
    # Callback & Messages
    app.add_handler(CallbackQueryHandler(None)) # handle_buttons
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), None)) # handle_message_events

    # --- Friendly Error Handler ---
    # Command အားလုံး စစ်ပြီးမှ မတွေ့သည့် command များအတွက်
    app.add_handler(MessageHandler(filters.COMMAND, unknown_command))

    app.run_polling()

if __name__ == "__main__":
    main()
