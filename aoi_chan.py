import os
import logging
import re
import ast
import operator
import requests

from telegram import Update, ChatPermissions
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    MessageReactionHandler,
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

PREMIUM_EMOJIS = {
    "sparkle": "5368324170671202286",
    "star": "5368324170671202287",
    "crown": "5368324170671202288",
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

# -------------------------------------------------------------------
# Reactions Handler
# -------------------------------------------------------------------
async def handle_reaction_events(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reaction = update.message_reaction
    if not reaction: return
    
    chat_id = reaction.chat.id
    settings = get_chat_settings(chat_id)

    if not settings.get('recdone', False): return

    user_id = reaction.user.id if reaction.user else None
    if user_id:
        try:
            member = await context.bot.get_chat_member(chat_id, user_id)
            if member.status not in ['creator', 'administrator']:
                return
        except Exception as e:
            logging.error(f"Reaction admin check error: {e}")
            return

    if reaction.new_reaction:
        message_id = reaction.message_id
        done_text = settings.get('recdone_text', 'Order Completed! Thank you ❤️')
        
        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text=done_text,
                reply_to_message_id=message_id,
                parse_mode='HTML'
            )
        except Exception as e:
            logging.error(f"Failed to send recdone reaction reply: {e}")

# -------------------------------------------------------------------
# General Message Handler
# -------------------------------------------------------------------
async def handle_message_events(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return
    chat_id = update.effective_chat.id
    settings = get_chat_settings(chat_id)
    text = update.message.text.strip()
    raw_text = text.lower()

    user = update.effective_user
    if user:
        u_list = user_history.setdefault(user.id, [])
        u_list.append({'first_name': user.first_name, 'username': user.username or ''})
        if len(u_list) > 50:
            u_list.pop(0)

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
    await update.message.reply_text("မင်္ဂလာပါရှင်၊ Aoi Chan Bot မှ ကြိုဆိုပါတယ်! ✨\nCommands များကို /help တွင် ကြည့်နိုင်ပါတယ်ရှင်။")

# -------------------------------------------------------------------
# Help Menu (Telegraph Link - "click here")
# -------------------------------------------------------------------
async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "<b>✨ Aoi Chan Bot Manual ✨</b>\n\n"
        "Commands နှင့် အသုံးပြုပုံ အပြည့်အစုံကို အောက်ပါ link တွင် ကြည့်ရှုနိုင်ပါသည်ရှင်:\n"
        '👉 <a href="https://telegra.ph/Aoi-Chan-Bot--Usage-Guide--Commands-Manual-07-26">click here</a>'
    )
    await update.message.reply_text(help_text, parse_mode='HTML', disable_web_page_preview=False)

# -------------------------------------------------------------------
# Main Setup & Application Builder
# -------------------------------------------------------------------
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

    app.add_handler(CommandHandler("setfilter", cmd_setfilter))
    app.add_handler(CommandHandler("deletefilter", cmd_deletefilter))

    app.add_handler(CommandHandler("ban", cmd_ban))
    app.add_handler(CommandHandler("unban", cmd_unban))
    app.add_handler(CommandHandler("mute", cmd_mute))
    app.add_handler(CommandHandler("kick", cmd_kick))

    app.add_handler(MessageReactionHandler(handle_reaction_events))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message_events))

    app.run_polling(allowed_updates=["message", "edited_message", "message_reaction"])

if __name__ == "__main__":
    main()
