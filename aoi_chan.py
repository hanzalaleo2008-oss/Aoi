import os
import logging
import re
from datetime import datetime, time
import pytz
import requests

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatPermissions
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
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

def get_chat_settings(chat_id: int) -> dict:
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
        'replydone_text': "ထည့်ပြီးပါပြီရှင့်✔️\nကျေးဇူးတင်ပါတယ်ရှင့်\nနောက်လည်းလာခဲ့ပါအုံးနော်",
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
            f"❌ **Command အသုံးပြုပုံ မှားယွင်းနေပါသည်။**\n\n"
            f"💡 **Example:**\n"
            f"• `/{key} on` (စနစ်ဖွင့်ရန်)\n"
            f"• `/{key} off` (စနစ်ပိတ်ရန်)",
            parse_mode='Markdown'
        )

# -------------------------------------------------------------------
# 1. Security & Guard
# -------------------------------------------------------------------

async def cmd_forwardblock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await toggle_setting(update, context, 'forwardblock', 'Forward Block')

async def cmd_linkblock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await toggle_setting(update, context, 'linkblock', 'Link Block')

async def cmd_autoban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await toggle_setting(update, context, 'autoban', 'Auto-Ban Left Members')

async def cmd_joineddelete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await toggle_setting(update, context, 'joineddelete', 'Joined Message Delete')

# -------------------------------------------------------------------
# 2. Tracking & Info
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

    text = "<b>User History Log:</b>\n"
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
# 3. Open / Closed System
# -------------------------------------------------------------------

async def open_group(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    settings = get_chat_settings(chat_id)
    permissions = ChatPermissions(
        can_send_messages=True, can_send_audios=True, can_send_documents=True,
        can_send_photos=True, can_send_videos=True, can_send_video_notes=True,
        can_send_voice_notes=True, can_send_polls=True, can_send_other_messages=True,
        can_add_web_page_previews=True
    )
    try:
        await context.bot.set_chat_permissions(chat_id=chat_id, permissions=permissions)
        await context.bot.send_message(chat_id=chat_id, text=settings['open_text'])
    except Exception as e:
        logging.error(f"Failed to open group: {e}")

async def close_group(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    settings = get_chat_settings(chat_id)
    permissions = ChatPermissions(
        can_send_messages=False, can_send_audios=False, can_send_documents=False,
        can_send_photos=False, can_send_videos=False, can_send_video_notes=False,
        can_send_voice_notes=False, can_send_polls=False, can_send_other_messages=False,
        can_add_web_page_previews=False
    )
    try:
        await context.bot.set_chat_permissions(chat_id=chat_id, permissions=permissions)
        await context.bot.send_message(chat_id=chat_id, text=settings['closed_text'])
    except Exception as e:
        logging.error(f"Failed to close group: {e}")

async def cmd_permission(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await toggle_setting(update, context, 'permission', 'Open/Closed Permission')

async def cmd_setopen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context): return
    chat_id = update.effective_chat.id
    text = update.message.text.partition(' ')[2].strip()
    if text:
        get_chat_settings(chat_id)['open_text'] = text
        await update.message.reply_text("✅ Open Message ပြောင်းလဲပြီးပါပြီ။")
    else:
        await update.message.reply_text("❌ **Usage:** `/setopen [စာသား]`", parse_mode='Markdown')

async def cmd_setclosed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context): return
    chat_id = update.effective_chat.id
    text = update.message.text.partition(' ')[2].strip()
    if text:
        get_chat_settings(chat_id)['closed_text'] = text
        await update.message.reply_text("✅ Closed Message ပြောင်းလဲပြီးပါပြီ။")
    else:
        await update.message.reply_text("❌ **Usage:** `/setclosed [စာသား]`", parse_mode='Markdown')

async def scheduled_open_job(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.data
    if get_chat_settings(chat_id).get('permission', False):
        await open_group(chat_id, context)

async def scheduled_close_job(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.data
    if get_chat_settings(chat_id).get('permission', False):
        await close_group(chat_id, context)

def parse_time_input(time_str: str) -> time | None:
    time_str = time_str.strip().lower()
    for fmt in ("%I:%M %p", "%I:%M%p", "%H:%M"):
        try:
            return datetime.strptime(time_str, fmt).time()
        except ValueError:
            pass
    return None

async def cmd_opentimer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context): return
    chat_id = update.effective_chat.id
    settings = get_chat_settings(chat_id)

    if not context.args:
        await update.message.reply_text("❌ **Usage:** `/opentimer 8:00 am` သို့မဟုတ် `/opentimer 0`", parse_mode='Markdown')
        return

    val = " ".join(context.args)
    if val == "0":
        if settings['opentimer_job']:
            settings['opentimer_job'].schedule_removal()
            settings['opentimer_job'] = None
        await update.message.reply_text("✅ Open Timer ကို ပိတ်လိုက်ပါပြီ။")
        return

    parsed_time = parse_time_input(val)
    if not parsed_time:
        await update.message.reply_text("❌ အချိန်ပုံစံ မမှန်ပါ။ ဥပမာ - `8:00 am` သို့မဟုတ် `08:00`", parse_mode='Markdown')
        return

    if settings['opentimer_job']:
        settings['opentimer_job'].schedule_removal()

    job = context.job_queue.run_daily(
        scheduled_open_job,
        time=parsed_time.replace(tzinfo=MM_TZ),
        data=chat_id,
        name=f"open_{chat_id}"
    )
    settings['opentimer_job'] = job
    await update.message.reply_text(f"⏰ Daily Open Timer ကို {parsed_time.strftime('%I:%M %p')} သို့ သတ်မှတ်လိုက်ပါပြီ။")

async def cmd_closedtimer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context): return
    chat_id = update.effective_chat.id
    settings = get_chat_settings(chat_id)

    if not context.args:
        await update.message.reply_text("❌ **Usage:** `/closedtimer 11:00 pm` သို့မဟုတ် `/closedtimer 0`", parse_mode='Markdown')
        return

    val = " ".join(context.args)
    if val == "0":
        if settings['closedtimer_job']:
            settings['closedtimer_job'].schedule_removal()
            settings['closedtimer_job'] = None
        await update.message.reply_text("✅ Closed Timer ကို ပိတ်လိုက်ပါပြီ။")
        return

    parsed_time = parse_time_input(val)
    if not parsed_time:
        await update.message.reply_text("❌ အချိန်ပုံစံ မမှန်ပါ။ ဥပမာ - `11:00 pm` သို့မဟုတ် `23:00`", parse_mode='Markdown')
        return

    if settings['closedtimer_job']:
        settings['closedtimer_job'].schedule_removal()

    job = context.job_queue.run_daily(
        scheduled_close_job,
        time=parsed_time.replace(tzinfo=MM_TZ),
        data=chat_id,
        name=f"close_{chat_id}"
    )
    settings['closedtimer_job'] = job
    await update.message.reply_text(f"⏰ Daily Closed Timer ကို {parsed_time.strftime('%I:%M %p')} သို့ သတ်မှတ်လိုက်ပါပြီ။")

# -------------------------------------------------------------------
# 4. Welcome & Goodbye
# -------------------------------------------------------------------

async def cmd_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await toggle_setting(update, context, 'welcome', 'Welcome Message')

async def cmd_setwelcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context): return
    text = update.message.text.partition(' ')[2].strip()
    if text:
        get_chat_settings(update.effective_chat.id)['welcome_text'] = text
        await update.message.reply_text("✅ Welcome Message ပြောင်းလဲပြီးပါပြီ။")
    else:
        await update.message.reply_text("❌ **Usage:** `/setwelcome [စာသား]`", parse_mode='Markdown')

async def cmd_welcometimer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context): return
    if context.args and context.args[0].isdigit():
        sec = int(context.args[0])
        get_chat_settings(update.effective_chat.id)['welcometimer'] = sec
        await update.message.reply_text(f"✅ Welcome Timer ကို {sec} စက္ကန့် သတ်မှတ်လိုက်ပါပြီ။")
    else:
        await update.message.reply_text("❌ **Usage:** `/welcometimer [စက္ကန့်]`", parse_mode='Markdown')

async def cmd_goodbye(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await toggle_setting(update, context, 'goodbye', 'Goodbye Message')

async def cmd_setgoodbye(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context): return
    text = update.message.text.partition(' ')[2].strip()
    if text:
        get_chat_settings(update.effective_chat.id)['goodbye_text'] = text
        await update.message.reply_text("✅ Goodbye Message ပြောင်းလဲပြီးပါပြီ။")
    else:
        await update.message.reply_text("❌ **Usage:** `/setgoodbye [စာသား]`", parse_mode='Markdown')

async def cmd_goodbyetimer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context): return
    if context.args and context.args[0].isdigit():
        sec = int(context.args[0])
        get_chat_settings(update.effective_chat.id)['goodbyetimer'] = sec
        await update.message.reply_text(f"✅ Goodbye Timer ကို {sec} စက္ကန့် သတ်မှတ်လိုက်ပါပြီ။")
    else:
        await update.message.reply_text("❌ **Usage:** `/goodbyetimer [စက္ကန့်]`", parse_mode='Markdown')

# -------------------------------------------------------------------
# 5. Store & MLBB Tools
# -------------------------------------------------------------------

async def cmd_idcopy_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await toggle_setting(update, context, 'idcopy', 'ID Copy System')

async def cmd_replydone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await toggle_setting(update, context, 'replydone', 'Reply Done Buttons')

async def cmd_setreplydone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context): return
    text = update.message.text.partition(' ')[2].strip()
    if text:
        get_chat_settings(update.effective_chat.id)['replydone_text'] = text
        await update.message.reply_text("✅ Confirm Reply Text ပြောင်းလဲပြီးပါပြီ။")
    else:
        await update.message.reply_text("❌ **Usage:** `/setreplydone [စာသား]`", parse_mode='Markdown')

async def cmd_recdone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await toggle_setting(update, context, 'recdone', 'Reaction Auto Done')

async def cmd_calculator(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await toggle_setting(update, context, 'calculator', 'Calculator Auto-math')

async def cmd_idcopy_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message or not update.message.reply_to_message.text:
        await update.message.reply_text("⚠️ Customer ၏ Game ID စာကို Reply ပြန်ပြီး `/idcopy` သို့မဟုတ် `/id` ဟု အသုံးပြုပါရှင်။", parse_mode='Markdown')
        return

    text = update.message.reply_to_message.text
    numbers = re.findall(r'\d+', text)

    if not numbers:
        await update.message.reply_text("❌ Reply ပြန်ထားသော စာထဲတွင် ID ဂဏန်းများ ရှာမတွေ့ပါရှင်။")
        return

    user_id = numbers[0]
    server_id = numbers[1] if len(numbers) > 1 else None

    if server_id:
        response_text = (
            f"🎮 **MLBB ID Information:**\n\n"
            f"• **Game ID:** `{user_id}`\n"
            f"• **Server ID:** `{server_id}`\n\n"
            f"💡 *ဂဏန်းပေါ်ကို Tap နှိပ်ရုံဖြင့် တိုက်ရိုက် Copy ကူးနိုင်ပါသည်။*"
        )
    else:
        response_text = (
            f"🎮 **MLBB ID Information:**\n\n"
            f"• **Game ID:** `{user_id}`\n\n"
            f"💡 *ဂဏန်းပေါ်ကို Tap နှိပ်ရုံဖြင့် တိုက်ရိုက် Copy ကူးနိုင်ပါသည်။*"
        )

    chat_id = update.effective_chat.id
    settings = get_chat_settings(chat_id)
    keyboard = []

    if settings.get('replydone', False):
        keyboard.append([
            InlineKeyboardButton("Delete ❌", callback_data="delete_msg"),
            InlineKeyboardButton("Confirm ✅", callback_data="confirm_msg")
        ])

    markup = InlineKeyboardMarkup(keyboard) if keyboard else None
    await update.message.reply_text(response_text, parse_mode='Markdown', reply_markup=markup)

async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "delete_msg":
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
        await update.message.reply_text("❌ **Usage:** `/setfilter [keyword] [text]`", parse_mode='Markdown')
        return
    
    keyword = args[0].lower()
    full_text = update.message.text.partition(' ')[2].strip()
    filter_text = full_text.partition(' ')[2].strip()
    
    custom_filters.setdefault(chat_id, {})[keyword] = filter_text
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
# 7. Moderation
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
# 8. Music Downloader & General Info (Full Help Menu)
# -------------------------------------------------------------------

async def cmd_music(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ **Usage:** `/music [song name]`", parse_mode='Markdown')
        return

    song_name = " ".join(context.args)
    status_msg = await update.message.reply_text(f"🎵 `{song_name}` ကို ရှာဖွေနေပါသည်... ခဏစောင့်ပေးပါရှင် ⏳", parse_mode='Markdown')

    try:
        search_url = f"https://api.deezer.com/search?q={requests.utils.quote(song_name)}&limit=1"
        response = requests.get(search_url, timeout=10).json()

        if not response.get('data'):
            await status_msg.edit_text("❌ သီချင်း ရှာမတွေ့ပါရှင်။")
            return

        track = response['data'][0]
        title = track.get('title', 'Unknown Title')
        artist = track.get('artist', {}).get('name', 'Unknown Artist')
        audio_url = track.get('preview')

        if not audio_url:
            await status_msg.edit_text("❌ သီချင်း Audio File ရယူ၍ မရနိုင်ပါရှင်။")
            return

        await context.bot.send_audio(
            chat_id=update.effective_chat.id,
            audio=audio_url,
            title=title,
            performer=artist,
            caption=f"✨ **{title}** - {artist}\n🎵 *Aoi Chan Music System*",
            parse_mode='Markdown'
        )
        await status_msg.delete()

    except Exception as e:
        logging.error(f"Music API error: {e}")
        await status_msg.edit_text("❌ သီချင်း ရှာဖွေရာတွင် အမှားအယွင်း ရှိနေပါသည်။")

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = "မင်္ဂလာပါရှင်၊ Aoi Chan Bot မှ ကြိုဆိုပါတယ်! ✨\n\nအသေးစိတ် Command များကို ကြည့်ရှုရန် /help ကို နှိပ်ပါရှင်။"
    await update.message.reply_text(text=welcome_text)

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "<b>1. Security & Guard</b>\n"
        "• /forwardblock on/off\n"
        "• /linkblock on/off\n"
        "• /autoban on/off\n"
        "• /joineddelete on/off\n\n"
        "<b>2. Tracking & Info</b>\n"
        "• /track on/off\n"
        "• /check (Reply)\n"
        "• /info (Reply)\n\n"
        "<b>3. Open/Closed System</b>\n"
        "• /permission on/off\n"
        "• open | closed (Text)\n"
        "• /setopen | /setclosed\n"
        "• /opentimer | /closedtimer\n\n"
        "<b>4. Welcome & Goodbye</b>\n"
        "• /welcome on/off | /setwelcome | /welcometimer\n"
        "• /goodbye on/off | /setgoodbye | /goodbyetimer\n\n"
        "<b>5. Store & MLBB Tools</b>\n"
        "• /mlbb | /idcopy (Reply to Customer ID)\n"
        "• /replydone on/off | /setreplydone\n"
        "• /recdone on/off | /calculator on/off\n\n"
        "<b>6. Custom Filters</b>\n"
        "• /setfilter [keyword] [text]\n"
        "• /deletefilter [keyword]\n\n"
        "<b>7. Moderation</b>\n"
        "• /ban | /unban | /mute | /kick | /resetall\n\n"
        "<b>8. Music Downloader</b>\n"
        "• /music [song name]\n"
    )
    await update.message.reply_text(help_text, parse_mode='HTML')

# -------------------------------------------------------------------
# Event Message Listener & Main Initialization
# -------------------------------------------------------------------

async def handle_message_events(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return
    chat_id = update.effective_chat.id
    settings = get_chat_settings(chat_id)
    text = update.message.text.strip()

    if settings.get('permission', False) and await is_admin(update, context):
        raw_text = text.lower()
        if raw_text in ["open", "/open"]:
            await open_group(chat_id, context)
            return
        elif raw_text in ["closed", "close", "/closed"]:
            await close_group(chat_id, context)
            return

    if settings.get('linkblock', False) and not await is_admin(update, context):
        if "http://" in text or "https://" in text or "t.me" in text:
            await update.message.delete()
            return

    if settings.get('calculator', True):
        if re.match(r'^[0-9\+\-\*\/\(\)\.\s]+$', text) and any(op in text for op in ['+', '-', '*', '/']):
            try:
                result = eval(text, {"__builtins__": None}, {})
                formatted = f"{int(result):,}" if isinstance(result, float) and result.is_integer() else f"{result:,}"
                await update.message.reply_text(f"<code>{formatted}</code> ပါရှင့်!", parse_mode='HTML')
                return
            except Exception:
                pass

    if chat_id in custom_filters:
        msg_text = text.lower()
        for kw, reply in custom_filters[chat_id].items():
            if kw in msg_text:
                await update.message.reply_text(reply)
                break

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

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
    app.add_handler(CommandHandler(["id", "idcopy", "mlbb"], cmd_idcopy_reply))
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
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))

    app.add_handler(CallbackQueryHandler(handle_buttons))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message_events))

    app.run_polling()

if __name__ == "__main__":
    main()
