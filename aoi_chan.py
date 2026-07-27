import os
import logging
import re
import ast
import operator
import difflib
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

# Telegram Premium Emoji Database
PREMIUM_EMOJIS = {
    "sparkle": "5368324170671202286",
    "star": "5368324170671202287",
    "crown": "5368324170671202288",
}

def get_tg_emoji(emoji_name: str, fallback: str = "✨") -> str:
    emoji_id = PREMIUM_EMOJIS.get(emoji_name)
    if emoji_id:
        return f'<tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji>'
    return fallback

# Premium Emoji Parser Helper Function
def extract_premium_emoji_text(message) -> str:
    """
    Message ထဲတွင်ပါသော Custom Premium Emoji များကို <tg-emoji> HTML tag သို့ အလိုအလျောက် ပြောင်းလဲပေးသည့် Function
    """
    if not message or not message.text:
        return ""

    full_text = message.text.partition(' ')[2].strip()
    if not full_text:
        return ""

    entities = message.entities or []
    text_offset = message.text.find(full_text)
    
    formatted_text = ""
    last_idx = text_offset
    
    for entity in entities:
        if entity.offset >= text_offset:
            formatted_text += message.text[last_idx:entity.offset]
            
            if entity.type == "custom_emoji":
                emoji_char = message.text[entity.offset : entity.offset + entity.length]
                formatted_text += f'<tg-emoji emoji-id="{entity.custom_emoji_id}">{emoji_char}</tg-emoji>'
            else:
                formatted_text += message.text[entity.offset : entity.offset + entity.length]
                
            last_idx = entity.offset + entity.length

    formatted_text += message.text[last_idx:]
    return formatted_text

# Safe Arithmetic Evaluator
OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.USub: operator.neg,
}

def safe_eval(expr: str):
    def _eval(node):
        if isinstance(node, ast.Constant):
            return node.value
        elif isinstance(node, ast.Num):
            return node.n
        elif isinstance(node, ast.BinOp):
            return OPERATORS[type(node.op)](_eval(node.left), _eval(node.right))
        elif isinstance(node, ast.UnaryOp):
            return OPERATORS[type(node.op)](_eval(node.operand))
        else:
            raise TypeError(f"Unsupported node type: {type(node)}")

    parsed = ast.parse(expr, mode='eval')
    return _eval(parsed.body)

# All Command Help Guidelines for Incorrect Usage
COMMAND_HELP = {
    "forwardblock": "• Usage: `/forwardblock on` သို့မဟုတ် `/forwardblock off`",
    "linkblock": "• Usage: `/linkblock on` သို့မဟုတ် `/linkblock off`",
    "autoban": "• Usage: `/autoban on` သို့မဟုတ် `/autoban off`",
    "joineddelete": "• Usage: `/joineddelete on` သို့မဟုတ် `/joineddelete off`",
    "track": "• Usage: `/track on` သို့မဟုတ် `/track off`",
    "check": "• Usage: User စာကို Reply ပြန်ပြီး `/check` ဟု ရိုက်ပါ။",
    "info": "• Usage: User စာကို Reply ပြန်ပြီး `/info` ဟု ရိုက်ပါ။",
    "permission": "• Usage: `/permission on` သို့မဟုတ် `/permission off`",
    "setopen": "• Usage: `/setopen [စာသား]`\n💡 Example: `/setopen Group ဖွင့်လိုက်ပါပြီရှင်`",
    "setclosed": "• Usage: `/setclosed [စာသား]`\n💡 Example: `/setclosed Group ခဏပိတ်ထားပါသည်ရှင်`",
    "opentimer": "• Usage: `/opentimer [အချိန်]`\n💡 Example: `/opentimer 8:00 am`",
    "closedtimer": "• Usage: `/closedtimer [အချိန်]`\n💡 Example: `/closedtimer 11:00 pm`",
    "welcome": "• Usage: `/welcome on` သို့မဟုတ် `/welcome off`",
    "setwelcome": "• Usage: `/setwelcome [စာသား]`",
    "welcometimer": "• Usage: `/welcometimer [စက္ကန့်]`",
    "goodbye": "• Usage: `/goodbye on` သို့မဟုတ် `/goodbye off`",
    "setgoodbye": "• Usage: `/setgoodbye [စာသား]`",
    "goodbyetimer": "• Usage: `/goodbyetimer [စက္ကန့်]`",
    "mlbb": "• Usage: Customer ID စာကို Reply ပြန်ပြီး `/mlbb` သို့မဟုတ် `/idcopy` ဟု ရိုက်ပါ။",
    "idcopy": "• Usage: Customer ID စာကို Reply ပြန်ပြီး `/idcopy` သို့မဟုတ် `/mlbb` ဟု ရိုက်ပါ။",
    "idcopytoggle": "• Usage: `/idcopytoggle on` သို့မဟုတ် `/idcopytoggle off`",
    "replydone": "• Usage: `/replydone on` သို့မဟုတ် `/replydone off`",
    "setreplydone": "• Usage: `/setreplydone [စာသား]`",
    "recdone": "• Usage: `/recdone on` သို့မဟုတ် `/recdone off`",
    "calculator": "• Usage: `/calculator on` သို့မဟုတ် `/calculator off`",
    "getid": "• Usage: Custom Emoji ပါသော စာကို Reply ပြန်ပြီး `/getid` ဟု ရိုက်ပါ။",
    "setfilter": "• Usage: `/setfilter [keyword] [text]`\n💡 Example: `/setfilter kpay 09123456789`",
    "deletefilter": "• Usage: `/deletefilter [keyword]`",
    "ban": "• Usage: Member Message ကို Reply ပြီး `/ban` ဟု ရိုက်ပါ။",
    "unban": "• Usage: Member Message ကို Reply ပြီး `/unban` ဟု ရိုက်ပါ။",
    "mute": "• Usage: Member Message ကို Reply ပြီး `/mute` ဟု ရိုက်ပါ။",
    "kick": "• Usage: Member Message ကို Reply ပြီး `/kick` ဟု ရိုက်ပါ။",
    "resetall": "• Usage: `/resetall` (Group Settings အားလုံး Reset လုပ်ရန်)",
    "music": "• Usage: `/music [သီချင်းနာမည်]`\n💡 Example: `/music Blue Mingalabar`",
}

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
        await update.message.reply_text("⚠️ ဒီ Command ကို Admin များသာ အသုံးပြုနိုင်ပါတယ်နော် ✨")
        return
    chat_id = update.effective_chat.id
    args = context.args
    settings = get_chat_settings(chat_id)
    if args and args[0].lower() in ['on', 'off']:
        state = (args[0].lower() == 'on')
        settings[key] = state
        await update.message.reply_text(f"✅ {name} စနစ်ကို `{state}` သို့ ပြောင်းလဲလိုက်ပါပြီရှင် ✨", parse_mode='Markdown')
    else:
        guide = COMMAND_HELP.get(key, f"• Usage: `/{key} on` သို့မဟုတ် `/{key} off`")
        await update.message.reply_text(
            f"⚠️ **အသုံးပြုပုံ လွဲမှားနေပါတယ်နော်!**\n\n"
            f"{guide}\n\n"
            f"စစ်ဆေးပြီး ပြန်လည်ရိုက်ပေးပါဦးနော် 💕",
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
# 3. Open/Closed System
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
        await context.bot.send_message(chat_id=chat_id, text=settings['open_text'], parse_mode='HTML')
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
        await context.bot.send_message(chat_id=chat_id, text=settings['closed_text'], parse_mode='HTML')
    except Exception as e:
        logging.error(f"Failed to close group: {e}")

async def cmd_permission(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await toggle_setting(update, context, 'permission', 'Open/Closed Permission')

async def cmd_setopen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context): return
    formatted_text = extract_premium_emoji_text(update.message)
    if formatted_text:
        get_chat_settings(update.effective_chat.id)['open_text'] = formatted_text
        await update.message.reply_text("✅ Open Message ပြောင်းလဲပြီးပါပြီရှင် ✨", parse_mode='HTML')
    else:
        await update.message.reply_text("⚠️ **Usage:** `/setopen [စာသား]`", parse_mode='Markdown')

async def cmd_setclosed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context): return
    formatted_text = extract_premium_emoji_text(update.message)
    if formatted_text:
        get_chat_settings(update.effective_chat.id)['closed_text'] = formatted_text
        await update.message.reply_text("✅ Closed Message ပြောင်းလဲပြီးပါပြီရှင် ✨", parse_mode='HTML')
    else:
        await update.message.reply_text("⚠️ **Usage:** `/setclosed [စာသား]`", parse_mode='Markdown')

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
        await update.message.reply_text("⚠️ **Usage:** `/opentimer 8:00 am` သို့မဟုတ် `/opentimer 0`", parse_mode='Markdown')
        return

    val = " ".join(context.args)
    if val == "0":
        if settings['opentimer_job']:
            settings['opentimer_job'].schedule_removal()
            settings['opentimer_job'] = None
        await update.message.reply_text("✅ Open Timer ကို ပိတ်လိုက်ပါပြီရှင် ✨")
        return

    parsed_time = parse_time_input(val)
    if not parsed_time:
        await update.message.reply_text("⚠️ အချိန်ပုံစံ လွဲမှားနေပါတယ်နော်! ဥပမာ - `8:00 am` သို့မဟုတ် `08:00`", parse_mode='Markdown')
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
    await update.message.reply_text(f"⏰ Daily Open Timer ကို {parsed_time.strftime('%I:%M %p')} သို့ သတ်မှတ်လိုက်ပါပြီရှင် ✨")

async def cmd_closedtimer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context): return
    chat_id = update.effective_chat.id
    settings = get_chat_settings(chat_id)

    if not context.args:
        await update.message.reply_text("⚠️ **Usage:** `/closedtimer 11:00 pm` သို့မဟုတ် `/closedtimer 0`", parse_mode='Markdown')
        return

    val = " ".join(context.args)
    if val == "0":
        if settings['closedtimer_job']:
            settings['closedtimer_job'].schedule_removal()
            settings['closedtimer_job'] = None
        await update.message.reply_text("✅ Closed Timer ကို ပိတ်လိုက်ပါပြီရှင် ✨")
        return

    parsed_time = parse_time_input(val)
    if not parsed_time:
        await update.message.reply_text("⚠️ အချိန်ပုံစံ လွဲမှားနေပါတယ်နော်! ဥပမာ - `11:00 pm` သို့မဟုတ် `23:00`", parse_mode='Markdown')
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
    await update.message.reply_text(f"⏰ Daily Closed Timer ကို {parsed_time.strftime('%I:%M %p')} သို့ သတ်မှတ်လိုက်ပါပြီရှင် ✨")

# -------------------------------------------------------------------
# 4. Welcome & Goodbye
# -------------------------------------------------------------------
async def cmd_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await toggle_setting(update, context, 'welcome', 'Welcome Message')

async def cmd_setwelcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context): return
    formatted_text = extract_premium_emoji_text(update.message)
    if formatted_text:
        get_chat_settings(update.effective_chat.id)['welcome_text'] = formatted_text
        await update.message.reply_text("✅ Welcome Message ပြောင်းလဲပြီးပါပြီရှင် ✨", parse_mode='HTML')
    else:
        await update.message.reply_text("⚠️ **Usage:** `/setwelcome [စာသား]`", parse_mode='Markdown')

async def cmd_welcometimer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context): return
    if context.args and context.args[0].isdigit():
        sec = int(context.args[0])
        get_chat_settings(update.effective_chat.id)['welcometimer'] = sec
        await update.message.reply_text(f"✅ Welcome Timer ကို {sec} စက္ကန့် သတ်မှတ်လိုက်ပါပြီရှင် ✨")
    else:
        await update.message.reply_text("⚠️ **Usage:** `/welcometimer [စက္ကန့်]`", parse_mode='Markdown')

async def cmd_goodbye(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await toggle_setting(update, context, 'goodbye', 'Goodbye Message')

async def cmd_setgoodbye(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context): return
    formatted_text = extract_premium_emoji_text(update.message)
    if formatted_text:
        get_chat_settings(update.effective_chat.id)['goodbye_text'] = formatted_text
        await update.message.reply_text("✅ Goodbye Message ပြောင်းလဲပြီးပါပြီရှင် ✨", parse_mode='HTML')
    else:
        await update.message.reply_text("⚠️ **Usage:** `/setgoodbye [စာသား]`", parse_mode='Markdown')

async def cmd_goodbyetimer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context): return
    if context.args and context.args[0].isdigit():
        sec = int(context.args[0])
        get_chat_settings(update.effective_chat.id)['goodbyetimer'] = sec
        await update.message.reply_text(f"✅ Goodbye Timer ကို {sec} စက္ကန့် သတ်မှတ်လိုက်ပါပြီရှင် ✨")
    else:
        await update.message.reply_text("⚠️ **Usage:** `/goodbyetimer [စက္ကန့်]`", parse_mode='Markdown')

# -------------------------------------------------------------------
# 5. Store & MLBB Tools
# -------------------------------------------------------------------
async def cmd_idcopy_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await toggle_setting(update, context, 'idcopy', 'ID Copy System')

async def cmd_replydone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await toggle_setting(update, context, 'replydone', 'Reply Done Buttons')

async def cmd_setreplydone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context): return
    formatted_text = extract_premium_emoji_text(update.message)
    if formatted_text:
        get_chat_settings(update.effective_chat.id)['replydone_text'] = formatted_text
        await update.message.reply_text("✅ Confirm Reply Text ပြောင်းလဲပြီးပါပြီရှင် ✨", parse_mode='HTML')
    else:
        await update.message.reply_text("⚠️ **Usage:** `/setreplydone [စာသား]`", parse_mode='Markdown')

async def cmd_recdone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await toggle_setting(update, context, 'recdone', 'Reaction Auto Done')

async def cmd_calculator(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await toggle_setting(update, context, 'calculator', 'Calculator Auto-math')

async def cmd_idcopy_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message or not update.message.reply_to_message.text:
        await update.message.reply_text("⚠️ Customer ၏ Game ID စာကို Reply ပြန်ပြီး `/idcopy` သို့မဟုတ် `/mlbb` ဟု အသုံးပြုပါရှင် 💕", parse_mode='Markdown')
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
            f"🎮 <b>MLBB ID Information:</b>\n\n"
            f"• <b>Game ID:</b> <code>{user_id}</code>\n"
            f"• <b>Server ID:</b> <code>{server_id}</code>\n\n"
            f"💡 <i>ဂဏန်းပေါ်ကို Tap နှိပ်ရုံဖြင့် တိုက်ရိုက် Copy ကူးနိုင်ပါသည်။</i>"
        )
    else:
        response_text = (
            f"🎮 <b>MLBB ID Information:</b>\n\n"
            f"• <b>Game ID:</b> <code>{user_id}</code>\n\n"
            f"💡 <i>ဂဏန်းပေါ်ကို Tap နှိပ်ရုံဖြင့် တိုက်ရိုက် Copy ကူးနိုင်ပါသည်။</i>"
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
    await update.message.reply_text(response_text, parse_mode='HTML', reply_markup=markup)

async def cmd_get_emoji_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        await update.message.reply_text("⚠️ Premium Emoji ပါသော စာကို Reply ပြန်ပြီး `/getid` ဟု အသုံးပြုပါရှင် 💕", parse_mode='Markdown')
        return

    reply_msg = update.message.reply_to_message
    entities = reply_msg.entities or reply_msg.caption_entities

    if not entities:
        await update.message.reply_text("❌ Reply ပြန်ထားသော စာထဲတွင် Premium Emoji မတွေ့ပါရှင်။")
        return

    found_ids = []
    for entity in entities:
        if entity.type == "custom_emoji":
            found_ids.append(f"• Emoji ID: <code>{entity.custom_emoji_id}</code>")

    if found_ids:
        text = "<b>Found Premium Emoji IDs:</b>\n\n" + "\n".join(found_ids)
        await update.message.reply_text(text, parse_mode='HTML')
    else:
        await update.message.reply_text("❌ Reply ပြန်ထားသော စာထဲတွင် Premium Emoji မတွေ့ပါရှင်။")

async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "delete_msg":
        await query.message.delete()
    elif query.data == "confirm_msg":
        chat_id = query.message.chat_id
        text = get_chat_settings(chat_id).get('replydone_text')
        await query.message.reply_text(text, parse_mode='HTML')

# -------------------------------------------------------------------
# 6. Custom Filters
# -------------------------------------------------------------------
async def cmd_setfilter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context): return
    chat_id = update.effective_chat.id
    args = context.args
    if not args or len(args) < 2:
        await update.message.reply_text(
            "⚠️ **` /setfilter ` အသုံးပြုပုံ လွဲမှားနေပါတယ်နော်!**\n\n"
            "📖 **Correct Usage:**\n"
            "`/setfilter [keyword] [reply_text]`\n\n"
            "💡 **Example:**\n"
            "`/setfilter kpay 09123456789`\n\n"
            "စစ်ဆေးပြီး ပြန်လည်ရိုက်ပေးပါနော် 💕",
            parse_mode='Markdown'
        )
        return
    
    keyword = args[0].lower()
    formatted_text = extract_premium_emoji_text(update.message)
    filter_text = formatted_text.partition(' ')[2].strip()

    custom_filters.setdefault(chat_id, {})[keyword] = filter_text
    await update.message.reply_text(f"✅ Filter <b>{keyword}</b> ကို သိမ်းဆည်းလိုက်ပါပြီရှင် ✨", parse_mode='HTML')

async def cmd_deletefilter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context): return
    chat_id = update.effective_chat.id
    args = context.args
    if not args:
        custom_filters.pop(chat_id, None)
        await update.message.reply_text("✅ Filter များ အားလုံးကို ဖျက်လိုက်ပါပြီရှင် ✨")
    else:
        keyword = args[0].lower()
        if chat_id in custom_filters and keyword in custom_filters[chat_id]:
            del custom_filters[chat_id][keyword]
            await update.message.reply_text(f"✅ Filter <b>{keyword}</b> ကို ဖျက်လိုက်ပါပြီရှင် ✨", parse_mode='HTML')

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
        await update.message.reply_text("⚠️ Ban ချင်သည့် Member ရဲ့ Message ကို Reply ပြန်ပြီး သုံးပါရှင် 💕")

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
    await update.message.reply_text("🔄 Group Settings အားလုံးကို မူလအတိုင်း Reset လုပ်လိုက်ပါပြီရှင် ✨")

# -------------------------------------------------------------------
# 8. Music Downloader & Main System Commands
# -------------------------------------------------------------------
async def cmd_music(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "⚠️ **သီချင်းနာမည် ထည့်ရန် လိုအပ်ပါတယ်နော်!**\n\n"
            "📖 **Usage:** `/music [သီချင်းနာမည်]`\n"
            "💡 **Example:** `/music Blue Mingalabar`",
            parse_mode='Markdown'
        )
        return

    song_name = " ".join(context.args)
    status_msg = await update.message.reply_text(f"🎵 `{song_name}` ကို Aoi Chan ရှာဖွေပေးနေပါတယ်... ခဏစောင့်ပေးပါနော် ⏳", parse_mode='Markdown')

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
            caption=f"✨ <b>{title}</b> - {artist}\n🎵 <i>Aoi Chan Music System</i>",
            parse_mode='HTML'
        )
        await status_msg.delete()

    except Exception as e:
        logging.error(f"Music API error: {e}")
        await status_msg.edit_text("❌ သီချင်း ရှာဖွေရာတွင် အမှားအယွင်း ရှိနေပါသည်။")

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sparkle = get_tg_emoji("sparkle", "✨")
    welcome_text = (
        f"မင်္ဂလာပါရှင်၊ Aoi Chan Bot မှ ကြိုဆိုပါတယ်! {sparkle}\n\n"
        "စမ်းသပ်ချင်သည့် Command များကို ရိုက်နှိပ်၍\n"
        "အသုံးပြုနိုင်ပါသည်။\n\n"
        "အသေးစိတ် Command များကို ကြည့်ရှုရန် /help ကို\n"
        "နှိပ်ပါရှင်။\n\n"
        "<b>Aoi Chan usages</b>"
    )
    
    telegraph_url = "https://telegra.ph/Aoi-Chan-Bot--Usage-Guide--Commands-Manual-07-26"
    keyboard = [[InlineKeyboardButton("👉 [Click Here to View Manual]", url=telegraph_url)]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        text=welcome_text,
        parse_mode='HTML',
        reply_markup=reply_markup
    )

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sparkle = get_tg_emoji("sparkle", "✨")
    
    help_text = (
        f"{sparkle} <b>Aoi Chan Bot - Command Manual</b> {sparkle}\n\n"
        "🛡 <b>1. Security & Guard</b>\n"
        "• /forwardblock on/off - Forward စာများ ပိတ်/ဖွင့်\n"
        "• /linkblock on/off - Link များ ပိတ်/ဖွင့်\n"
        "• /autoban on/off - ထွက်သွားသူများကို Auto-Ban\n"
        "• /joineddelete on/off - Joined Message များ ဖျက်ရန်\n\n"
        "👤 <b>2. Tracking & Info</b>\n"
        "• /track on/off - User History မှတ်တမ်းတင်စနစ်\n"
        "• /check - User History ကြည့်ရန် (Reply ပြန်ပါ)\n"
        "• /info - User Info ကြည့်ရန် (Reply ပြန်ပါ)\n\n"
        "🏪 <b>3. Open/Closed System</b>\n"
        "• /permission on/off - Open/Closed စနစ် ပိတ်/ဖွင့်\n"
        "• open | closed - စာဖြင့် တိုက်ရိုက် Permission ပိတ်/ဖွင့်\n"
        "• /setopen | /setclosed - Message စာသား ပြောင်းရန်\n"
        "• /opentimer | /closedtimer - အချိန်ဖြင့် Timer ပေးရန်\n\n"
        "👋 <b>4. Welcome & Goodbye</b>\n"
        "• /welcome on/off | /setwelcome | /welcometimer\n"
        "• /goodbye on/off | /setgoodbye | /goodbyetimer\n\n"
        "💎 <b>5. Store & MLBB Tools</b>\n"
        "• /mlbb | /idcopy - Customer Game ID Extract လုပ်ရန် (Reply ပြန်ပါ)\n"
        "• /idcopytoggle on/off - ID Copy စနစ် ပိတ်/ဖွင့်\n"
        "• /replydone on/off | /setreplydone - Confirm/Delete ခလုတ်စနစ်\n"
        "• /recdone on/off - Reaction Auto Done စနစ်\n"
        "• /calculator on/off - Auto-Math တွက်ချက်မှုစနစ်\n"
        "• /getid - Custom Emoji ID ထုတ်ယူရန် (Reply ပြန်ပါ)\n\n"
        "💬 <b>6. Custom Filters</b>\n"
        "• /setfilter [keyword] [text] - Filter အသစ်ထည့်ရန်\n"
        "• /deletefilter [keyword] - Filter ဖျက်ရန်\n\n"
        "⚒ <b>7. Moderation</b>\n"
        "• /ban | /unban | /mute | /kick | /resetall - အဖွဲ့ဝင်များ ထိန်းချုပ်ရန်\n\n"
        "🎵 <b>8. Music Downloader</b>\n"
        "• /music [song_name] - သီချင်းရှာဖွေ ဒေါင်းလုဒ်ဆွဲရန်\n"
    )
    
    telegraph_url = "https://telegra.ph/Aoi-Chan-Bot--Usage-Guide--Commands-Manual-07-26"
    keyboard = [[InlineKeyboardButton("👉 [Click Here to View Manual]", url=telegraph_url)]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        text=help_text, 
        parse_mode='HTML', 
        reply_markup=reply_markup
    )

# -------------------------------------------------------------------
# Smart Unknown Command Handler
# -------------------------------------------------------------------
async def handle_unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return

    user_cmd = update.message.text.split()[0].lstrip('/').lower()
    
    all_commands = list(COMMAND_HELP.keys())
    matches = difflib.get_close_matches(user_cmd, all_commands, n=1, cutoff=0.4)

    if matches:
        closest_cmd = matches[0]
        guide_text = COMMAND_HELP[closest_cmd]
        
        reply_msg = (
            f"⚠️ **`/{user_cmd}` ဆိုတဲ့ Command မရှိပါဘူးရှင့်!**\n\n"
            f"Aoi Chan ထင်တာ ရိုက်ချင်တာ `/{closest_cmd}` ဖြစ်မယ်ထင်ပါတယ်နော် ✨\n\n"
            f"📖 **အသုံးပြုပုံ Guidelines:**\n{guide_text}\n\n"
            f"💡 *ပြန်လည်စစ်ဆေးပြီး နောက်တစ်ကြိမ် မှန်အောင် ရိုက်ပေးပါဦးနော်!*"
        )
    else:
        reply_msg = (
            f"❌ **`/{user_cmd}` ဆိုတဲ့ Command ကို ရှာမတွေ့ပါဘူးရှင့်!**\n\n"
            f"Command များကို မှန်ကန်စွာ ကြည့်ရှုချင်ရင် `/help` ကို နှိပ်ပြီး စစ်ဆေးပေးပါနော် 💕"
        )

    await update.message.reply_text(reply_msg, parse_mode='Markdown')

# -------------------------------------------------------------------
# Message Handler Events
# -------------------------------------------------------------------
async def handle_message_events(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return
    chat_id = update.effective_chat.id
    settings = get_chat_settings(chat_id)
    text = update.message.text.strip()
    raw_text = text.lower()

    if settings.get('permission', False) and await is_admin(update, context):
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
                result = safe_eval(text)
                formatted = f"{int(result):,}" if isinstance(result, float) and result.is_integer() else f"{result:,}"
                await update.message.reply_text(f"<code>{formatted}</code> ပါရှင့်!", parse_mode='HTML')
                return
            except Exception:
                pass

    if chat_id in custom_filters:
        for kw, reply in custom_filters[chat_id].items():
            if kw in raw_text:
                await update.message.reply_text(reply, parse_mode='HTML')
                break

# -------------------------------------------------------------------
# Application Main Function
# -------------------------------------------------------------------
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Base Commands
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    
    # 1. Security & Guard
    app.add_handler(CommandHandler("forwardblock", cmd_forwardblock))
    app.add_handler(CommandHandler("linkblock", cmd_linkblock))
    app.add_handler(CommandHandler("autoban", cmd_autoban))
    app.add_handler(CommandHandler("joineddelete", cmd_joineddelete))
    
    # 2. Tracking & Info
    app.add_handler(CommandHandler("track", cmd_track))
    app.add_handler(CommandHandler("check", cmd_check))
    app.add_handler(CommandHandler("info", cmd_info))
    
    # 3. Open/Closed System
    app.add_handler(CommandHandler("permission", cmd_permission))
    app.add_handler(CommandHandler("setopen", cmd_setopen))
    app.add_handler(CommandHandler("setclosed", cmd_setclosed))
    app.add_handler(CommandHandler("opentimer", cmd_opentimer))
    app.add_handler(CommandHandler("closedtimer", cmd_closedtimer))

    # 4. Welcome & Goodbye
    app.add_handler(CommandHandler("welcome", cmd_welcome))
    app.add_handler(CommandHandler("setwelcome", cmd_setwelcome))
    app.add_handler(CommandHandler("welcometimer", cmd_welcometimer))
    app.add_handler(CommandHandler("goodbye", cmd_goodbye))
    app.add_handler(CommandHandler("setgoodbye", cmd_setgoodbye))
    app.add_handler(CommandHandler("goodbyetimer", cmd_goodbyetimer))

    # 5. Store & MLBB Tools
    app.add_handler(CommandHandler("idcopytoggle", cmd_idcopy_toggle))
    app.add_handler(CommandHandler(["mlbb", "id", "idcopy"], cmd_idcopy_reply))
    app.add_handler(CommandHandler("getid", cmd_get_emoji_id))
    app.add_handler(CommandHandler("replydone", cmd_replydone))
    app.add_handler(CommandHandler("setreplydone", cmd_setreplydone))
    app.add_handler(CommandHandler("recdone", cmd_recdone))
    app.add_handler(CommandHandler("calculator", cmd_calculator))

    # 6. Custom Filters
    app.add_handler(CommandHandler("setfilter", cmd_setfilter))
    app.add_handler(CommandHandler("deletefilter", cmd_deletefilter))

    # 7. Moderation
    app.add_handler(CommandHandler("ban", cmd_ban))
    app.add_handler(CommandHandler("unban", cmd_unban))
    app.add_handler(CommandHandler("mute", cmd_mute))
    app.add_handler(CommandHandler("kick", cmd_kick))
    app.add_handler(CommandHandler("resetall", cmd_resetall))

    # 8. Music Downloader
    app.add_handler(CommandHandler("music", cmd_music))

    # Smart Catch Unknown Commands
    app.add_handler(MessageHandler(filters.COMMAND, handle_unknown_command))

    # Callbacks & Messages Handler
    app.add_handler(CallbackQueryHandler(handle_buttons))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message_events))

    app.run_polling()

if __name__ == "__main__":
    main()
