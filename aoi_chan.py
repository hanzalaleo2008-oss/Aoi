import os
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatPermissions
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# Configuration: Reads token safely from Railway Environment Variable
BOT_TOKEN = os.getenv("BOT_TOKEN", "8884160612:AAEXBlgw8coEtH3GsxIew9368RMfcbatATI")

# Logging Setup
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Database / State Placeholders
group_settings = {}
user_history = {}  # Tracks user history
custom_filters = {}

# -------------------------------------------------------------------
# Helper Functions
# -------------------------------------------------------------------

async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Check if the user invoking the command is an admin or group owner."""
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    member = await context.bot.get_chat_member(chat_id, user_id)
    return member.status in ['creator', 'administrator']

async def delete_message_job(context: ContextTypes.DEFAULT_TYPE):
    """Job callback to handle timed message deletions."""
    job_data = context.job.data
    try:
        await context.bot.delete_message(chat_id=job_data['chat_id'], message_id=job_data['message_id'])
    except Exception as e:
        logging.error(f"Failed to delete message: {e}")

# -------------------------------------------------------------------
# Basic Commands
# -------------------------------------------------------------------

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for the /start command with HTML link."""
    welcome_text = (
        "မင်္ဂလာပါရှင်၊ Aoi Chan Bot မှ ကြိုဆိုပါတယ်! ✨\n\n"
        "စမ်းသပ်ချင်သည့် Command များကို ရိုက်နှိပ်၍ အသုံးပြုနိုင်ပါသည်။\n\n"
        "<b>Aoi Chan usages</b>\n"
        '<a href="https://telegra.ph/Aoi-Chan-Bot--Usage-Guide--Commands-Manual-07-26">👉 [Click Here to View Usages]</a>'
    )
    
    await update.message.reply_text(
        text=welcome_text,
        parse_mode='HTML',
        disable_web_page_preview=True
    )

async def cmd_calculator(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Toggle calculator output state."""
    chat_id = update.effective_chat.id
    args = context.args
    if args and args[0].lower() in ['on', 'off']:
        state = args[0].lower() == 'on'
        group_settings.setdefault(chat_id, {})['calculator'] = state
        await update.message.reply_text(
            f"Calculator status: `{state}` (Mono output enabled for auto-copy)", 
            parse_mode='Markdown'
        )

async def cmd_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check historical username/name changes recorded since July 11, 2026."""
    user_id = update.effective_user.id
    if update.message.reply_to_message:
        user_id = update.message.reply_to_message.from_user.id
    
    history = user_history.get(user_id, [])
    if not history:
        await update.message.reply_text("No history recorded starting from 11 July 2026.")
        return

    text = "<b>User History Log (From 11 July 2026):</b>\n"
    for item in history:
        text += f"• Name: {item['first_name']} | @{item['username']}\n"
    await update.message.reply_text(text, parse_mode='HTML')

# -------------------------------------------------------------------
# MLBB ID & Inline Buttons
# -------------------------------------------------------------------

async def cmd_idcopy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Toggle ID Copy feature."""
    chat_id = update.effective_chat.id
    args = context.args
    if args and args[0].lower() in ['on', 'off']:
        state = (args[0].lower() == 'on')
        group_settings.setdefault(chat_id, {})['idcopy'] = state
        await update.message.reply_text(f"ID Copy feature set to: {args[0]}")

async def send_mlbb_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send MLBB ID with interactive action buttons."""
    chat_id = update.effective_chat.id
    keyboard = [[InlineKeyboardButton("Copy ID 📋", callback_data="copy_id")]]
    
    if group_settings.get(chat_id, {}).get('replydone', False):
        keyboard.append([
            InlineKeyboardButton("Delete ❌", callback_data="delete_msg"),
            InlineKeyboardButton("Confirm ✅", callback_data="confirm_msg")
        ])
    
    markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Here is the requested ID:", reply_markup=markup)

async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle callback queries from inline keyboard buttons."""
    query = update.callback_query
    await query.answer()

    if query.data == "copy_id":
        await query.message.reply_text("`12345678 (9999)`", parse_mode="Markdown")
    elif query.data == "delete_msg":
        await query.message.delete()
    elif query.data == "confirm_msg":
        chat_id = query.message.chat_id
        text = group_settings.get(
            chat_id, {}
        ).get('replydone_text', "ထည့်ပြီးပါပြီရှင့်✔️\nကျေးဇူးတင်ပါတယ်ရှင့်\nနောက်လည်းလာခဲ့ပါအုံးနော်")
        await query.message.reply_text(text)

# -------------------------------------------------------------------
# Moderation Commands
# -------------------------------------------------------------------

async def cmd_ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        return
    if update.message.reply_to_message:
        target_user = update.message.reply_to_message.from_user.id
        await context.bot.ban_chat_member(update.effective_chat.id, target_user)
        await update.message.reply_text("Member successfully banned.")

async def cmd_unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        return
    if update.message.reply_to_message:
        target_user = update.message.reply_to_message.from_user.id
        await context.bot.unban_chat_member(update.effective_chat.id, target_user)
        await update.message.reply_text("Member unbanned.")

async def cmd_kick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        return
    if update.message.reply_to_message:
        target_user = update.message.reply_to_message.from_user.id
        await context.bot.ban_chat_member(update.effective_chat.id, target_user)
        await context.bot.unban_chat_member(update.effective_chat.id, target_user)
        await update.message.reply_text("Member kicked.")

# -------------------------------------------------------------------
# Message Handlers & Automated Actions
# -------------------------------------------------------------------

async def handle_forward_block(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Automatically block and delete forwarded messages if setting is active."""
    chat_id = update.effective_chat.id
    if group_settings.get(chat_id, {}).get('forwardblock', False):
        if not await is_admin(update, context):
            await update.message.delete()
            warning = await update.message.reply_text("Forwarding messages is not allowed in this group.")
            if context.job_queue:
                context.job_queue.run_once(
                    delete_message_job, 15, data={'chat_id': chat_id, 'message_id': warning.message_id}
                )

async def track_user_changes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Log user details when tracking is enabled."""
    chat_id = update.effective_chat.id
    user = update.effective_user
    if user and group_settings.get(chat_id, {}).get('track', False):
        user_history.setdefault(user.id, []).append({
            'date': datetime.now().strftime("%Y-%m-%d"),
            'username': user.username,
            'first_name': user.first_name
        })

async def handle_joined_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Delete system messages when new members join."""
    chat_id = update.effective_chat.id
    if group_settings.get(chat_id, {}).get('joineddelete', False):
        if update.message.new_chat_members:
            await update.message.delete()

# -------------------------------------------------------------------
# Main Initialization
# -------------------------------------------------------------------

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Register Command Handlers
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("calculator", cmd_calculator))
    app.add_handler(CommandHandler("check", cmd_check))
    app.add_handler(CommandHandler("idcopy", cmd_idcopy))
    app.add_handler(CommandHandler("ban", cmd_ban))
    app.add_handler(CommandHandler("unban", cmd_unban))
    app.add_handler(CommandHandler("kick", cmd_kick))

    # Register Event / Message Handlers
    app.add_handler(CallbackQueryHandler(handle_buttons))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, handle_joined_delete))
    app.add_handler(MessageHandler(filters.FORWARDED, handle_forward_block))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, track_user_changes))

    print("Bot is running...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()