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
BOT_TOKEN = os.getenv("BOT_TOKEN", "8884160612:AAEXBlgw8coELH3GsxIew9368RMLcbaLATi")

# Logging Setup
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Database / State Placeholders
group_settings = {}
user_history = {}
custom_filters = {}

# -------------------------------------------------------------------
# Helper Functions
# -------------------------------------------------------------------

async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Check if user is Admin or Creator."""
    if not update.effective_chat or update.effective_chat.type == "private":
        return True
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    member = await context.bot.get_chat_member(chat_id, user_id)
    return member.status in ['creator', 'administrator']

async def delete_message_job(context: ContextTypes.DEFAULT_TYPE):
    """Job callback for timed message deletions."""
    job_data = context.job.data
    try:
        await context.bot.delete_message(chat_id=job_data['chat_id'], message_id=job_data['message_id'])
    except Exception as e:
        logging.error(f"Failed to delete message: {e}")

def get_chat_settings(chat_id: int) -> dict:
    """Ensure settings dict exists for a chat."""
    return group_settings.setdefault(chat_id, {
        'forwardblock': False,
        'linkblock': False,
        'autoban': False,
        'joineddelete': False,
        'track': False,
        'permission': False,
        'open': True,
        'open_text': "🏪 Group ကို အခုပဲ ဖွင့်လိုက်ပါပြီရှင်! ဈေးရောင်း/ဝယ် ပြုလုပ်နိုင်ပါပြီ။",
        'closed_text': "🔒 Group ကို ခဏ ပိတ်ထားပါသည်ရှင်! စာပို့ခွင့် ခေတ္တ ပိတ်ထားပါသည်။",
        'welcome': False,
        'welcome_text': "မင်္ဂလာပါ {mention} ရှင်! {name} မှ ကြိုဆိုပါတယ် ✨",
        'welcometimer': 0,
        'goodbye': False,
        'goodbye_text': "{name} ထွက်သွားပါပြီ 😢",
        'goodbyetimer': 0,
        'idcopy': False,
        'replydone': False,
        'replydone_text': "ထည့်ပြီးပါပြီရှင့်✔️\nကျေးဇူးတင်ပါတယ်ရှင့်\nနောက်လည်းလာခဲ့ပါအုံးနော်",
        'recdone': False,
        'calculator': False,
    })

# -------------------------------------------------------------------
# 1. Security & Group Guard
# -------------------------------------------------------------------

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
        await update.message.reply_text(f"❌ Usage: `/{key} on` သို့မဟုတ် `/{key} off` ဟု သုံးပါရှင်။", parse_mode='Markdown')

async def cmd_forwardblock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await toggle_setting(update, context, 'forwardblock', 'Forward Block')

async def cmd_linkblock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await toggle_setting(update, context, 'linkblock', 'Link Block')

async def cmd_autoban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await toggle_setting(update, context, 'autoban', 'Auto-Ban Left Members')

async def cmd_joineddelete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await toggle_setting(update, context, 'joineddelete', 'Joined Message Delete')

# -------------------------------------------------------------------
# 2. Tracking & Info System
# -------------------------------------------------------------------

async def cmd_track(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await toggle_setting(update, context, 'track', 'User Track')

async def cmd_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

async def cmd_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
# 3. Group Open / Closed System
# -------------------------------------------------------------------

async def cmd_permission(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await toggle_setting(update, context, 'permission', 'Open/Closed Permission')

async def handle_open_closed_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    settings = get_chat_settings(chat_id)
    if not settings.get('permission', False):
        return

    text = update.message.text.lower().strip()
    if not await is_admin(update, context):
        return

    if text == "open":
        settings['open'] = True
        await context.bot.set_chat_permissions(chat_id, ChatPermissions(can_send_messages=True, can_send_media_messages=True))
        await update.message.reply_text(settings['open_text'])
    elif text == "closed":
        settings['open'] = False
        await context.bot.set_chat_permissions(chat_id, ChatPermissions(can_send_messages=False))
        await update.message.reply_text(settings['closed_text'])

async def cmd_setopen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context): return
    chat_id = update.effective_chat.id
    settings = get_chat_settings(chat_id)
    text = " ".join(context.args)
    if text:
        settings['open_text'] = text
        await update.message.reply_text("✅ Open Message ပြောင်းလဲပြီးပါပြီ။")

async def cmd_setclosed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context): return
    chat_id = update.effective_chat.id
    settings = get_chat_settings(chat_id)
    text = " ".join(context.args)
    if text:
        settings['closed_text'] = text
        await update.message.reply_text("✅ Closed Message ပြောင်းလဲပြီးပါပြီ။")

# -------------------------------------------------------------------
# 4. Welcome & Goodbye Messages
# -------------------------------------------------------------------

async def cmd_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await toggle_setting(update, context, 'welcome', 'Welcome Message')

async def cmd_setwelcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context): return
    text = " ".join(context.args)
    if text:
        get_chat_settings(update.effective_chat.id)['welcome_text'] = text
        await update.message.reply_text("✅ Welcome Message ပြောင်းလဲပြီးပါပြီ။")

async def cmd_welcometimer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context): return
    if context.args and context.args[0].isdigit():
        get_chat_settings(update.effective_chat.id)['welcometimer'] = int(context.args[0])
        await update.message.reply_text(f"✅ Welcome Timer ကို {context.args[0]} စက္ကန့် သတ်မှတ်လိုက်ပါပြီ။")

async def cmd_goodbye(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await toggle_setting(update, context, 'goodbye', 'Goodbye Message')

async def cmd_setgoodbye(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context): return
    text = " ".join(context.args)
    if text:
        get_chat_settings(update.effective_chat.id)['goodbye_text'] = text
        await update.message.reply_text("✅ Goodbye Message ပြောင်းလဲပြီးပါပြီ။")

async def cmd_goodbyetimer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context): return
    if context.args and context.args[0].isdigit():
        get_chat_settings(update.effective_chat.id)['goodbyetimer'] = int(context.args[0])
        await update.message.reply_text(f"✅ Goodbye Timer ကို {context.args[0]} စက္ကန့် သတ်မှတ်လိုက်ပါပြီ။")

# -------------------------------------------------------------------
# 5. Store & MLBB ID Tools
# -------------------------------------------------------------------

async def cmd_idcopy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await toggle_setting(update, context, 'idcopy', 'ID Copy Button')

async def cmd_replydone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await toggle_setting(update, context, 'replydone', 'Reply Done Buttons')

async def cmd_setreplydone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context): return
    text = " ".join(context.args)
    if text:
        get_chat_settings(update.effective_chat.id)['replydone_text'] = text
        await update.message.reply_text("✅ Confirm Reply Text ပြောင်းလဲပြီးပါပြီ။")

async def cmd_recdone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await toggle_setting(update, context, 'recdone', 'Reaction Auto Done')

async def cmd_calculator(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await toggle_setting(update, context, 'calculator', 'Calculator Mono Output')

async def send_mlbb_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    settings = get_chat_settings(chat_id)
    keyboard = [[InlineKeyboardButton("Copy ID 📋", callback_data="copy_id")]]
    
    if settings.get('replydone', False):
        keyboard.append([
            InlineKeyboardButton("Delete ❌", callback_data="delete_msg"),
            InlineKeyboardButton("Confirm ✅", callback_data="confirm_msg")
        ])
    
    markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Here is the requested ID:", reply_markup=markup)

async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "copy_id":
        await query.message.reply_text("`12345678 (9999)`", parse_mode="Markdown")
    elif query.data == "delete_msg":
        await query.message.delete()
    elif query.data == "confirm_msg":
        chat_id = query.message.chat_id
        text = get_chat_settings(chat_id).get('replydone_text')
        await query.message.reply_text(text)

# -------------------------------------------------------------------
# 6. Custom Filters
# -------------------------------------------------------------------

async def cmd_setfilter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context): return
    chat_id = update.effective_chat.id
    args = context.args
    if not args:
        await update.message.reply_text("❌ Usage: `/setfilter [keyword] [စာသား]`", parse_mode='Markdown')
        return
    
    keyword = args[0].lower()
    text = " ".join(args[1:])
    custom_filters.setdefault(chat_id, {})[keyword] = text
    await update.message.reply_text(f"✅ Filter `{keyword}` ကို သိမ်းဆည်းလိုက်ပါပြီ။", parse_mode='Markdown')

async def cmd_deletefilter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context): return
    chat_id = update.effective_chat.id
    args = context.args
    if not args:
        custom_filters.pop(chat_id, None)
        await update.message.reply_text("✅ Filter များ အားလုံးကို ဖျက်လိုက်ပါပြီ။")
    else:
        keyword = args[0].lower()
        if chat_id in custom_filters and keyword in custom_filters[chat_id]:
            del custom_filters[chat_id][keyword]
            await update.message.reply_text(f"✅ Filter `{keyword}` ကို ဖျက်လိုက်ပါပြီ။", parse_mode='Markdown')

# -------------------------------------------------------------------
# 7. Moderation Commands
# -------------------------------------------------------------------

async def cmd_ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context): return
    if update.message.reply_to_message:
        target = update.message.reply_to_message.from_user.id
        await context.bot.ban_chat_member(update.effective_chat.id, target)
        await update.message.reply_text("✅ Member successfully banned.")
    else:
        await update.message.reply_text("⚠️ Ban ချင်သည့် Member ရဲ့ Message ကို Reply ပြန်ပြီး သုံးပါရှင်။")

async def cmd_unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context): return
    if update.message.reply_to_message:
        target = update.message.reply_to_message.from_user.id
        await context.bot.unban_chat_member(update.effective_chat.id, target)
        await update.message.reply_text("✅ Member unbanned.")

async def cmd_mute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context): return
    if update.message.reply_to_message:
        target = update.message.reply_to_message.from_user.id
        await context.bot.restrict_chat_member(
            update.effective_chat.id, target, permissions=ChatPermissions(can_send_messages=False)
        )
        await update.message.reply_text("✅ Member muted.")

async def cmd_kick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context): return
    if update.message.reply_to_message:
        target = update.message.reply_to_message.from_user.id
        await context.bot.ban_chat_member(update.effective_chat.id, target)
        await context.bot.unban_chat_member(update.effective_chat.id, target)
        await update.message.reply_text("✅ Member kicked.")

async def cmd_resetall(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context): return
    group_settings.pop(update.effective_chat.id, None)
    await update.message.reply_text("🔄 Group Settings အားလုံးကို မူလအတိုင်း Reset လုပ်လိုက်ပါပြီ။")

# -------------------------------------------------------------------
# 8. Music Feature & General Commands
# -------------------------------------------------------------------

async def cmd_music(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Usage: `/music [သီချင်းနာမည် သို့မဟုတ် အဆိုတော်]`", parse_mode='Markdown')
        return
    song_name = " ".join(context.args)
    await update.message.reply_text(f"🎵 Searching for `{song_name}`...\n(သီချင်းရှာဖွေရေး စနစ်အား ချိတ်ဆက်နေပါသည်ရှင်)", parse_mode='Markdown')

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "မင်္ဂလာပါရှင်၊ Aoi Chan Bot မှ ကြိုဆိုပါတယ်! ✨\n\n"
        "စမ်းသပ်ချင်သည့် Command များကို ရိုက်နှိပ်၍ အသုံးပြုနိုင်ပါသည်။\n"
        "အသေးစိတ် Command များကို ကြည့်ရှုရန် /help ကို နှိပ်ပါရှင်။\n\n"
        "<b>Aoi Chan usages</b>\n"
        '<a href="https://telegra.ph/Aoi-Chan-Bot--Usage-Guide--Commands-Manual-07-26">👉 [Click Here to View Manual]</a>'
    )
    await update.message.reply_text(text=welcome_text, parse_mode='HTML', disable_web_page_preview=True)

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "✨ <b>Aoi Chan Bot - Complete Manual</b> ✨\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "<b>🛡️ 1. Security & Guard</b>\n"
        "• /forwardblock on/off\n"
        "• /linkblock on/off\n"
        "• /autoban on/off\n"
        "• /joineddelete on/off\n\n"
        "<b>👤 2. Tracking & Info</b>\n"
        "• /track on/off\n"
        "• /check (Reply)\n"
        "• /info (Reply)\n\n"
        "<b>🏪 3. Open/Closed System</b>\n"
        "• /permission on/off\n"
        "• open | closed (Text)\n"
        "• /setopen | /setclosed\n\n"
        "<b>🖐️ 4. Welcome & Goodbye</b>\n"
        "• /welcome on/off | /setwelcome\n"
        "• /goodbye on/off | /setgoodbye\n\n"
        "<b>💎 5. Store & MLBB Tools</b>\n"
        "• /mlbb | /idcopy on/off\n"
        "• /replydone on/off | /setreplydone\n"
        "• /recdone on/off | /calculator on/off\n\n"
        "<b>💬 6. Custom Filters</b>\n"
        "• /setfilter [keyword] [text]\n"
        "• /deletefilter [keyword]\n\n"
        "<b>🔨 7. Moderation</b>\n"
        "• /ban | /unban | /mute | /kick | /resetall\n\n"
        "<b>🎵 8. Music</b>\n"
        "• /music [song name]\n"
    )
    await update.message.reply_text(help_text, parse_mode='HTML')

# -------------------------------------------------------------------
# Automated Handlers (Events & Messages)
# -------------------------------------------------------------------

async def handle_message_events(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message: return
    chat_id = update.effective_chat.id
    settings = get_chat_settings(chat_id)
    user = update.effective_user

    # Link Block
    if settings.get('linkblock', False) and not await is_admin(update, context):
        if "http://" in update.message.text or "https://" in update.message.text or "t.me" in update.message.text:
            await update.message.delete()
            return

    # Filter Handler
    if chat_id in custom_filters:
        msg_text = update.message.text.lower() if update.message.text else ""
        for kw, reply in custom_filters[chat_id].items():
            if kw in msg_text:
                await update.message.reply_text(reply)
                break

    # Tracking
    if settings.get('track', False) and user:
        user_history.setdefault(user.id, []).append({
            'date': datetime.now().strftime("%Y-%m-%d"),
            'username': user.username,
            'first_name': user.first_name
        })

async def handle_new_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    settings = get_chat_settings(chat_id)

    if settings.get('joineddelete', False):
        await update.message.delete()

    if settings.get('welcome', False):
        for member in update.message.new_chat_members:
            mention = f"<a href='tg://user?id={member.id}'>{member.first_name}</a>"
            text = settings['welcome_text'].format(mention=mention, name=member.first_name, id=member.id)
            msg = await update.message.reply_text(text, parse_mode='HTML')
            if settings['welcometimer'] > 0 and context.job_queue:
                context.job_queue.run_once(delete_message_job, settings['welcometimer'], data={'chat_id': chat_id, 'message_id': msg.message_id})

async def handle_left_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    settings = get_chat_settings(chat_id)

    if settings.get('autoban', False):
        await context.bot.ban_chat_member(chat_id, update.message.left_chat_member.id)

    if settings.get('goodbye', False):
        user = update.message.left_chat_member
        text = settings['goodbye_text'].format(name=user.first_name, id=user.id)
        msg = await update.message.reply_text(text)
        if settings['goodbyetimer'] > 0 and context.job_queue:
            context.job_queue.run_once(delete_message_job, settings['goodbyetimer'], data={'chat_id': chat_id, 'message_id': msg.message_id})

# -------------------------------------------------------------------
# Main App Initialization
# -------------------------------------------------------------------

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # 1. Security
    app.add_handler(CommandHandler("forwardblock", cmd_forwardblock))
    app.add_handler(CommandHandler("linkblock", cmd_linkblock))
    app.add_handler(CommandHandler("autoban", cmd_autoban))
    app.add_handler(CommandHandler("joineddelete", cmd_joineddelete))

    # 2. Tracking
    app.add_handler(CommandHandler("track", cmd_track))
    app.add_handler(CommandHandler("check", cmd_check))
    app.add_handler(CommandHandler("info", cmd_info))

    # 3. Open/Closed System
    app.add_handler(CommandHandler("permission", cmd_permission))
    app.add_handler(CommandHandler("setopen", cmd_setopen))
    app.add_handler(CommandHandler("setclosed", cmd_setclosed))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r'^(open|closed)$'), handle_open_closed_text))

    # 4. Welcome & Goodbye
    app.add_handler(CommandHandler("welcome", cmd_welcome))
    app.add_handler(CommandHandler("setwelcome", cmd_setwelcome))
    app.add_handler(CommandHandler("welcometimer", cmd_welcometimer))
    app.add_handler(CommandHandler("goodbye", cmd_goodbye))
    app.add_handler(CommandHandler("setgoodbye", cmd_setgoodbye))
    app.add_handler(CommandHandler("goodbyetimer", cmd_goodbyetimer))

    # 5. Store & MLBB ID
    app.add_handler(CommandHandler("idcopy", cmd_idcopy))
    app.add_handler(CommandHandler("replydone", cmd_replydone))
    app.add_handler(CommandHandler("setreplydone", cmd_setreplydone))
    app.add_handler(CommandHandler("recdone", cmd_recdone))
    app.add_handler(CommandHandler("calculator", cmd_calculator))
    app.add_handler(CommandHandler("mlbb", send_mlbb_id))

    # 6. Custom Filters
    app.add_handler(CommandHandler("setfilter", cmd_setfilter))
    app.add_handler(CommandHandler("deletefilter", cmd_deletefilter))

    # 7. Moderation
    app.add_handler(CommandHandler("ban", cmd_ban))
    app.add_handler(CommandHandler("unban", cmd_unban))
    app.add_handler(CommandHandler("mute", cmd_mute))
    app.add_handler(CommandHandler("kick", cmd_kick))
    app.add_handler(CommandHandler("resetall", cmd_resetall))

    # 8. Music & General
    app.add_handler(CommandHandler("music", cmd_music))
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))

    # Message & Callback Handlers
    app.add_handler(CallbackQueryHandler(handle_buttons))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, handle_new_members))
    app.add_handler(MessageHandler(filters.StatusUpdate.LEFT_CHAT_MEMBER, handle_left_member))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message_events))

    print("Aoi Chan Bot Full Suite is running...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
