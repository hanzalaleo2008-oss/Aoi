import os
import logging
import re
import ast
import operator
import requests
import yt_dlp
from datetime import datetime

from telegram import Update, ChatPermissions, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    MessageReactionHandler,
    ContextTypes,
    filters,
)

# -------------------------------------------------------------------
# Configuration & Setup (Lines 1 - 30)
# -------------------------------------------------------------------
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

group_settings = {}
user_history = {}
custom_filters = {}
user_notes = {}
user_warnings = {}

PREMIUM_EMOJIS = {
    "sparkle": "5368324170671202286",
    "star": "5368324170671202287",
    "crown": "5368324170671202288",
}

VALID_COMMANDS = {
    "start", "help", "forwardblock", "linkblock", "autoban", "joineddelete",
    "track", "check", "info", "permission", "setopen", "setclosed",
    "welcome", "setwelcome", "goodbye", "setgoodbye", "telegraph",
    "idcopytoggle", "mlbb", "id", "idcopy", "replydone", "recdone",
    "setrecdone", "calculator", "setfilter", "deletefilter",
    "ban", "unban", "mute", "kick", "play", "stop", "skip", "queue",
    "note", "notes", "clearNotes", "warn", "warnings", "clearwarn",
    "ping", "serverinfo", "poll", "dice", "weather", "about"
}

def extract_premium_emoji_text(message) -> str:
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
        'welcome': False,
        'welcome_text': "မင်္ဂလာပါ {mention} ရှင်! {name} မှ ကြိုဆိုပါတယ် ✨",
        'goodbye': False,
        'goodbye_text': "{name} ထွက်သွားပါပြီ 😢",
        'idcopy': True,
        'replydone': False,
        'recdone': False,
        'recdone_text': "Order Completed! Thank you ❤️",
        'calculator': True,
        'music': True,
    })

async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if not update.effective_chat or update.effective_chat.type == "private":
        return True
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    try:
        member = await context.bot.get_chat_member(chat_id, user_id)
        return member.status in ['creator', 'administrator']
    except Exception:
        return False

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
        await update.message.reply_text(f"⚠️ Usage: `/{key} on` သို့မဟုတ် `/{key} off`", parse_mode='Markdown')

# -------------------------------------------------------------------
# Security & Protection Commands
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
# Tracking & Info Commands
# -------------------------------------------------------------------
async def cmd_track(update: Update, context: ContextTypes.DEFAULT_TYPE): 
    await toggle_setting(update, context, 'track', 'User Track')

async def cmd_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if update.message.reply_to_message:
        user_id = update.message.reply_to_message.from_user.id
    
    history = user_history.get(user_id, [])
    if not history:
        await update.message.reply_text("No history recorded.")
        return

    text = "<b>User History Log:</b>\n"
    for item in history[-10:]:
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
    )
    await update.message.reply_text(info_text, parse_mode='HTML')

# -------------------------------------------------------------------
# Open / Close Group Management
# -------------------------------------------------------------------
async def open_group(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    settings = get_chat_settings(chat_id)
    permissions = ChatPermissions(can_send_messages=True, can_send_photos=True, can_send_videos=True, can_send_other_messages=True)
    try:
        await context.bot.set_chat_permissions(chat_id=chat_id, permissions=permissions)
        await context.bot.send_message(chat_id=chat_id, text=settings['open_text'], parse_mode='HTML')
    except Exception as e:
        logging.error(f"Failed to open group: {e}")

async def close_group(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    settings = get_chat_settings(chat_id)
    permissions = ChatPermissions(can_send_messages=False)
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

async def cmd_setclosed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context): return
    formatted_text = extract_premium_emoji_text(update.message)
    if formatted_text:
        get_chat_settings(update.effective_chat.id)['closed_text'] = formatted_text
        await update.message.reply_text("✅ Closed Message ပြောင်းလဲပြီးပါပြီရှင် ✨", parse_mode='HTML')

# -------------------------------------------------------------------
# Welcome & Goodbye Management
# -------------------------------------------------------------------
async def cmd_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE): 
    await toggle_setting(update, context, 'welcome', 'Welcome Message')

async def cmd_goodbye(update: Update, context: ContextTypes.DEFAULT_TYPE): 
    await toggle_setting(update, context, 'goodbye', 'Goodbye Message')

async def cmd_setwelcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context): return
    formatted_text = extract_premium_emoji_text(update.message)
    if formatted_text:
        get_chat_settings(update.effective_chat.id)['welcome_text'] = formatted_text
        await update.message.reply_text("✅ Welcome Message ပြောင်းပြီးပါပြီရှင် ✨", parse_mode='HTML')

async def cmd_setgoodbye(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context): return
    formatted_text = extract_premium_emoji_text(update.message)
    if formatted_text:
        get_chat_settings(update.effective_chat.id)['goodbye_text'] = formatted_text
        await update.message.reply_text("✅ Goodbye Message ပြောင်းပြီးပါပြီရှင် ✨", parse_mode='HTML')

# -------------------------------------------------------------------
# Telegraph Page Generator Function
# -------------------------------------------------------------------
async def cmd_telegraph(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message or not update.message.reply_to_message.text:
        await update.message.reply_text("⚠️ Telegraph ပြုလုပ်လိုသော စာကို Reply ပြန်ပြီး `/telegraph [Title]` ဟု ရိုက်ပေးပါရှင် ✨")
        return

    title = " ".join(context.args) if context.args else "Aoi Chan Note"
    content_text = update.message.reply_to_message.text

    try:
        acc_res = requests.get("https://api.telegra.ph/createAccount", params={"short_name": "AoiChan"}).json()
        access_token = acc_res['result']['access_token']
        content_json = [{"tag": "p", "children": [content_text]}]

        page_res = requests.post("https://api.telegra.ph/createPage", data={
            "access_token": access_token,
            "title": title,
            "content": str(content_json).replace("'", '"'),
            "return_content": "false"
        }).json()

        if page_res.get('ok'):
            url = page_res['result']['url']
            await update.message.reply_text(f"🔗 <b>Telegraph Link ဖန်တီးပြီးပါပြီ:</b>\n{url}", parse_mode='HTML')
        else:
            await update.message.reply_text("❌ Telegraph Link ဖန်တီးရာတွင် အဆင်မပြေပါရှင်။")
    except Exception as e:
        logging.error(f"Telegraph error: {e}")
        await update.message.reply_text("❌ Telegraph Service ချိတ်ဆက်မှု အဆင်မပြေပါရှင်။")

# -------------------------------------------------------------------
# Store & MLBB Commands
# -------------------------------------------------------------------
async def cmd_idcopy_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE): 
    await toggle_setting(update, context, 'idcopy', 'ID Copy System')

async def cmd_replydone(update: Update, context: ContextTypes.DEFAULT_TYPE): 
    await toggle_setting(update, context, 'replydone', 'Reply Done Buttons')

async def cmd_recdone(update: Update, context: ContextTypes.DEFAULT_TYPE): 
    await toggle_setting(update, context, 'recdone', 'Reaction Auto Done')

async def cmd_setrecdone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context): return
    formatted_text = extract_premium_emoji_text(update.message)
    if not formatted_text:
        full_text = update.message.text.partition(' ')[2].strip()
        formatted_text = full_text if full_text else ""

    if formatted_text:
        get_chat_settings(update.effective_chat.id)['recdone_text'] = formatted_text
        await update.message.reply_text("✅ Reaction Done Message ကို ပြောင်းလဲပြီးပါပြီရှင် ✨", parse_mode='HTML')
    else:
        await update.message.reply_text("⚠️ Usage: `/setrecdone Order completed! Thank you ❤️`", parse_mode='Markdown')

async def cmd_calculator(update: Update, context: ContextTypes.DEFAULT_TYPE): 
    await toggle_setting(update, context, 'calculator', 'Calculator Auto-math')

async def cmd_idcopy_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message or not update.message.reply_to_message.text:
        await update.message.reply_text("⚠️ Customer ၏ Game ID စာကို Reply ပြန်ပြီး `/idcopy` ဟု အသုံးပြုပါရှင် 💕")
        return

    text = update.message.reply_to_message.text
    numbers = re.findall(r'\d+', text)

    if not numbers:
        await update.message.reply_text("❌ Reply ပြန်ထားသော စာထဲတွင် ID ဂဏန်းများ ရှာမတွေ့ပါရှင်။")
        return

    user_id = numbers[0]
    server_id = numbers[1] if len(numbers) > 1 else None

    if server_id:
        response_text = f"🎮 <b>MLBB ID Information:</b>\n\n• <b>Game ID:</b> <code>{user_id}</code>\n• <b>Server ID:</b> <code>{server_id}</code>"
    else:
        response_text = f"🎮 <b>MLBB ID Information:</b>\n\n• <b>Game ID:</b> <code>{user_id}</code>"

    await update.message.reply_text(response_text, parse_mode='HTML')

# -------------------------------------------------------------------
# Music Commands (Updated with yt-dlp Real Audio Streaming)
# -------------------------------------------------------------------
async def cmd_play(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("⚠️ ကျေးဇူးပြု၍ ဖွင့်လိုသော သီချင်းနာမည် သို့မဟုတ် YouTube Link ထည့်ပေးပါရှင်။ ဥပမာ: `/play [Song Name or Link]`", parse_mode='Markdown')
        return
    
    query = " ".join(context.args)
    msg = await update.message.reply_text(f"🎵 <b>Searching & Downloading:</b> <code>{query}</code>\nခဏစောင့်ပေးပါရှင် ✨", parse_mode='HTML')

    try:
        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'outtmpl': 'downloads/%(id)s.%(ext)s',
            'noplaylist': True,
            'default_search': 'ytsearch1',
        }

        os.makedirs("downloads", exist_ok=True)

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(query, download=True)
            if 'entries' in info:
                info = info['entries'][0]
            
            file_id = info['id']
            title = info.get('title', 'Unknown Title')
            audio_file = f"downloads/{file_id}.mp3"

        if os.path.exists(audio_file):
            await update.message.reply_audio(
                audio=open(audio_file, 'rb'),
                title=title,
                performer="Aoi Chan Music Bot",
                caption=f"🎵 <b>Now Playing:</b> {title} ✨"
            )
            await msg.delete()
            try:
                os.remove(audio_file)
            except Exception:
                pass
        else:
            await msg.edit_text("❌ သီချင်းဖိုင် ဒေါင်းလုဒ်လုပ်ရာတွင် အဆင်မပြေပါရှင်။")

    except Exception as e:
        logging.error(f"Play command error: {e}")
        await msg.edit_text(f"❌ သီချင်းရှာဖွေရာတွင် အမှားအယွင်း ဖြစ်ပေါ်သွားပါပြီရှင်။")

async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context): return
    await update.message.reply_text("⏹️ သီချင်းဖွင့်ခြင်းကို ရပ်ဆိုင်းလိုက်ပါပြီရှင်။", parse_mode='HTML')

async def cmd_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context): return
    await update.message.reply_text("⏭️ နောက်ထပ်သီချင်းသို့ ကျော်လိုက်ပါပြီရှင်။", parse_mode='HTML')

async def cmd_queue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎶 <b>Current Music Queue:</b>\n• (လက်ရှိတွင် သီချင်းစာရင်း အလွတ်ဖြစ်နေပါသည်)", parse_mode='HTML')

# -------------------------------------------------------------------
# Advanced Features Added (Notes, Warnings, Utilities)
# -------------------------------------------------------------------
async def cmd_note(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context): return
    chat_id = update.effective_chat.id
    args = context.args
    if len(args) >= 2:
        title = args[0].lower()
        content = " ".join(args[1:])
        user_notes.setdefault(chat_id, {})[title] = content
        await update.message.reply_text(f"📝 Note <b>{title}</b> ကို သိမ်းဆည်းပြီးပါပြီရှင် ✨", parse_mode='HTML')
    else:
        await update.message.reply_text("⚠️ Usage: `/note [title] [content]`", parse_mode='Markdown')

async def cmd_notes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    notes = user_notes.get(chat_id, {})
    if not notes:
        await update.message.reply_text("📭 ဒီ Group ထဲမှာ သိမ်းထားတဲ့ Notes တွေ မရှိသေးပါဘူးရှင်။")
        return
    text = "<b>📚 Saved Group Notes:</b>\n"
    for title in notes.keys():
        text += f"• <code>{title}</code>\n"
    await update.message.reply_text(text, parse_mode='HTML')

async def cmd_clear_notes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context): return
    chat_id = update.effective_chat.id
    if chat_id in user_notes:
        user_notes[chat_id].clear()
        await update.message.reply_text("🗑️ Group Notes အားလုံးကို ဖျက်ဆီးလိုက်ပါပြီရှင်။")

async def cmd_warn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context): return
    if not update.message.reply_to_message:
        await update.message.reply_text("⚠️ သတိပေးလိုသူ၏ စာကို Reply ပြန်၍ `/warn` ဟု အသုံးပြုပါရှင်။")
        return
    user = update.message.reply_to_message.from_user
    chat_id = update.effective_chat.id
    key = (chat_id, user.id)
    user_warnings[key] = user_warnings.get(key, 0) + 1
    count = user_warnings[key]
    
    await update.message.reply_text(f"⚠️ {user.first_name} ကို သတိပေးချက် ထုတ်ပြန်လိုက်ပါပြီ။ (စုစုပေါင်း: {count}/3)")
    if count >= 3:
        try:
            await context.bot.ban_chat_member(chat_id, user.id)
            await update.message.reply_text(f"🚫 သတိပေးချက် ၃ ကြိမ်ပြည့်သွားသဖြင့် {user.first_name} ကို Ban လိုက်ပါပြီရှင်။")
        except Exception:
            pass

async def cmd_warnings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        await update.message.reply_text("⚠️ ကြည့်ရှုလိုသူ၏ စာကို Reply ပြန်၍ `/warnings` ဟု ရိုက်ပါ။")
        return
    user = update.message.reply_to_message.from_user
    chat_id = update.effective_chat.id
    count = user_warnings.get((chat_id, user.id), 0)
    await update.message.reply_text(f"ℹ️ {user.first_name} ရဲ့ လက်ရှိ သတိပေးချက်အရေအတွက်: <b>{count}</b>", parse_mode='HTML')

async def cmd_clear_warn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context): return
    if not update.message.reply_to_message: return
    user = update.message.reply_to_message.from_user
    chat_id = update.effective_chat.id
    user_warnings[(chat_id, user.id)] = 0
    await update.message.reply_text(f"✅ {user.first_name} ၏ သတိပေးချက်များကို ရှင်းလင်းပေးလိုက်ပါပြီရှင်။")

async def cmd_ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🏓 Pong! Bot is active and running smoothly ✨")

async def cmd_server_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "💻 <b>Server & Bot System Information:</b>\n\n"
        "• Python Version: 3.10+\n"
        "• Telegram Library: python-telegram-bot\n"
        "• Bot Status: Online & Operational 🚀"
    )
    await update.message.reply_text(text, parse_mode='HTML')

async def cmd_dice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_dice(chat_id=update.effective_chat.id, emoji="🎲")

async def cmd_about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 <b>Aoi Chan Bot v2.5</b>\nDeveloped with love for high-performance Telegram group management! 💕", parse_mode='HTML')

# -------------------------------------------------------------------
# Custom Filters & Moderation Commands
# -------------------------------------------------------------------
async def cmd_setfilter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context): return
    chat_id = update.effective_chat.id
    args = context.args
    if len(args) >= 2:
        keyword = args[0].lower()
        content = " ".join(args[1:])
        custom_filters.setdefault(chat_id, {})[keyword] = content
        await update.message.reply_text(f"✅ Filter <b>{keyword}</b> ကို သတ်မှတ်လိုက်ပါပြီရှင် ✨", parse_mode='HTML')

async def cmd_deletefilter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context): return
    chat_id = update.effective_chat.id
    args = context.args
    if args:
        keyword = args[0].lower()
        if chat_id in custom_filters and keyword in custom_filters[chat_id]:
            del custom_filters[chat_id][keyword]
            await update.message.reply_text(f"✅ Filter <b>{keyword}</b> ကို ဖြုတ်လိုက်ပါပြီရှင် ✨", parse_mode='HTML')

async def cmd_ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context): return
    if update.message.reply_to_message:
        user = update.message.reply_to_message.from_user
        await context.bot.ban_chat_member(update.effective_chat.id, user.id)
        await update.message.reply_text(f"🚫 {user.first_name} ကို Ban လိုက်ပါပြီရှင်။")

async def cmd_unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context): return
    if update.message.reply_to_message:
        user = update.message.reply_to_message.from_user
        await context.bot.unban_chat_member(update.effective_chat.id, user.id)
        await update.message.reply_text(f"✅ {user.first_name} ကို Unban လိုက်ပါပြီရှင်။")

async def cmd_mute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context): return
    if update.message.reply_to_message:
        user = update.message.reply_to_message.from_user
        await context.bot.restrict_chat_member(update.effective_chat.id, user.id, permissions=ChatPermissions(can_send_messages=False))
        await update.message.reply_text(f"🔇 {user.first_name} ကို Mute လိုက်ပါပြီရှင်။")

async def cmd_kick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context): return
    if update.message.reply_to_message:
        user = update.message.reply_to_message.from_user
        await context.bot.ban_chat_member(update.effective_chat.id, user.id)
        await context.bot.unban_chat_member(update.effective_chat.id, user.id)
        await update.message.reply_text(f"👞 {user.first_name} ကို Kick လိုက်ပါပြီရှင်။")

async def handle_unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return
    text = update.message.text.split()[0].lower()
    cmd_name = text.replace("/", "").split("@")[0]

    if cmd_name not in VALID_COMMANDS:
        girl_tone_msg = (
            f"ဟယ်... <code>/{cmd_name}</code> ဆိုတဲ့ Command လေးက မရှိသေးဘူးဖြစ်နေတယ်ရှင် 🥺\n\n"
            f"Command ရိုက်တာ မှားသွားတာဖြစ်နိုင်ပါတယ်နော် ✨\n"
            f"ရနိုင်တဲ့ Command လေးတွေကို ကြည့်ရှုချင်ရင်တော့ <b>/help</b> လေးကို နှိပ်ပြီး စစ်ဆေးပေးပါနော် 💕"
        )
        await update.message.reply_text(girl_tone_msg, parse_mode='HTML')

async def handle_message_events(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return
    chat_id = update.effective_chat.id
    settings = get_chat_settings(chat_id)
    text = update.message.text.strip()
    raw_text = text.lower()

    if text.startswith("/"):
        await handle_unknown_command(update, context)
        return

    user = update.effective_user
    if user:
        u_list = user_history.setdefault(user.id, [])
        u_list.append({'first_name': user.first_name, 'username': user.username or ''})
        if len(u_list) > 50: u_list.pop(0)

    if settings.get('permission', False) and await is_admin(update, context):
        if raw_text in ["open", "/open"]:
            await open_group(chat_id, context)
            return
        elif raw_text in ["closed", "close", "/closed"]:
            await close_group(chat_id, context)
            return

    if settings.get('linkblock', False) and not await is_admin(update, context):
        if "http://" in text or "https://" in text or "t.me" in text:
            try:
                await update.message.delete()
            except Exception:
                pass
            return

    if chat_id in custom_filters and raw_text in custom_filters[chat_id]:
        await update.message.reply_text(custom_filters[chat_id][raw_text], parse_mode='HTML')
        return

    chat_notes = user_notes.get(chat_id, {})
    if raw_text in chat_notes:
        await update.message.reply_text(chat_notes[raw_text], parse_mode='HTML')
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

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "မင်္ဂလာပါရှင်၊ Aoi Chan Bot မှ ကြိုဆိုပါတယ်! ✨\n\n"
        "စမ်းသပ်ချင်သည့် Command များကို ရိုက်နှိပ်၍ အသုံးပြုနိုင်ပါသည်။\n"
        "အသေးစိတ် Command များကို ကြည့်ရှုရန် <b>/help</b> ကို နှိပ်ပါရှင်။"
    )
    keyboard = [[InlineKeyboardButton("👉 [Click Here to View Manual]", url="https://telegra.ph/Aoi-Chan-Bot--Usage-Guide--Commands-Manual-07-26")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(text, parse_mode='HTML', reply_markup=reply_markup)

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "<b>✨ Aoi Chan Commands List (Extended Version) ✨</b>\n\n"
        "<b>🛡️ 1. Security & Protection</b>\n"
        "• <code>/forwardblock on/off</code> - Forward စာများ ပိတ်/ဖွင့်\n"
        "• <code>/linkblock on/off</code> - Link များ ပိတ်/ဖွင့်\n"
        "• <code>/autoban on/off</code> - ထွက်သွားသူများကို Auto-Ban\n"
        "• <code>/joineddelete on/off</code> - Joined စာများ ဖျက်ရန်\n\n"
        "<b>🏪 2. Group Management & Notes</b>\n"
        "• <code>/permission on/off</code> - Open/Closed စနစ်\n"
        "• <code>/note [title] [text]</code> - Note အသစ်မှတ်ရန်\n"
        "• <code>/notes</code> - မှတ်ထားသော Notes များကိုကြည့်ရန်\n"
        "• <code>/warn</code> - အပြစ်ပေးသတိပေးရန်\n"
        "• <code>/warnings</code> - သတိပေးချက်အရေအတွက်ကြည့်ရန်\n\n"
        "<b>🎵 3. Music Player System</b>\n"
        "• <code>/play [Song/Link]</code> - သီချင်းစတင်ဖွင့်ရန်\n"
        "• <code>/stop</code> / <code>/skip</code> / <code>/queue</code>\n\n"
        "<b>🛍️ 4. Store & Orders</b>\n"
        "• <code>/recdone on/off</code> - Reaction Auto Done စနစ်\n"
        "• <code>/setrecdone [Text]</code> - Done Message ပြောင်းရန်\n"
        "• <code>/idcopy (Reply msg)</code> - Game ID သီးသန့်ထုတ်ရန်\n"
        "• <code>/calculator on/off</code> - Auto Math စနစ်\n\n"
        "<b>⚙️ 5. Custom Filters & Admin tools</b>\n"
        "• <code>/setfilter [key] [text]</code> - Keyword Filter မှတ်ရန်\n"
        "• <code>/ban, /unban, /mute, /kick</code> - ချက်ချင်းအရေးယူရန်"
    )
    keyboard = [[InlineKeyboardButton("👉 [Click Here to View Manual]", url="https://telegra.ph/Aoi-Chan-Bot--Usage-Guide--Commands-Manual-07-26")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(help_text, parse_mode='HTML', reply_markup=reply_markup)

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    
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

    app.add_handler(CommandHandler("welcome", cmd_welcome))
    app.add_handler(CommandHandler("setwelcome", cmd_setwelcome))
    app.add_handler(CommandHandler("goodbye", cmd_goodbye))
    app.add_handler(CommandHandler("setgoodbye", cmd_setgoodbye))

    app.add_handler(CommandHandler("telegraph", cmd_telegraph))
    app.add_handler(CommandHandler("idcopytoggle", cmd_idcopy_toggle))
    app.add_handler(CommandHandler(["mlbb", "id", "idcopy"], cmd_idcopy_reply))
    app.add_handler(CommandHandler("replydone", cmd_replydone))
    app.add_handler(CommandHandler("recdone", cmd_recdone))
    app.add_handler(CommandHandler("setrecdone", cmd_setrecdone))
    app.add_handler(CommandHandler("calculator", cmd_calculator))

    app.add_handler(CommandHandler("play", cmd_play))
    app.add_handler(CommandHandler("stop", cmd_stop))
    app.add_handler(CommandHandler("skip", cmd_skip))
    app.add_handler(CommandHandler("queue", cmd_queue))

    # Extended Features handlers
    app.add_handler(CommandHandler("note", cmd_note))
    app.add_handler(CommandHandler("notes", cmd_notes))
    app.add_handler(CommandHandler("clearNotes", cmd_clear_notes))
    app.add_handler(CommandHandler("warn", cmd_warn))
    app.add_handler(CommandHandler("warnings", cmd_warnings))
    app.add_handler(CommandHandler("clearwarn", cmd_clear_warn))
    app.add_handler(CommandHandler("ping", cmd_ping))
    app.add_handler(CommandHandler("serverinfo", cmd_server_info))
    app.add_handler(CommandHandler("dice", cmd_dice))
    app.add_handler(CommandHandler("about", cmd_about))

    app.add_handler(CommandHandler("setfilter", cmd_setfilter))
    app.add_handler(CommandHandler("deletefilter", cmd_deletefilter))
    app.add_handler(CommandHandler("ban", cmd_ban))
    app.add_handler(CommandHandler("unban", cmd_unban))
    app.add_handler(CommandHandler("mute", cmd_mute))
    app.add_handler(CommandHandler("kick", cmd_kick))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message_events))
    app.add_handler(MessageReactionHandler(handle_reaction_events))

    logging.info("Aoi Chan Bot is starting...")
    app.run_polling()

if __name__ == '__main__':
    main()
