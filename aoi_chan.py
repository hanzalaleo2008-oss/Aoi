import datetime as dt
import logging
import os
import random
import pytz
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# Railway Environment Variable (သို့မဟုတ် တိုက်ရိုက်ထည့်ရန်)
TOKEN = os.getenv("TOKEN", "YOUR_NEW_TOKEN_HERE")
CHAT_ID = os.getenv("CHAT_ID", "YOUR_CHAT_ID_HERE")

# Logging သတ်မှတ်ခြင်း (Errors များကို ရှင်းလင်းစွာ သိရှိရန်)
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

MYANMAR_QUOTES = [
    "အရမ်းကြိုးစားနေတာ ဂုဏ်ယူပါတယ်။ အောက်တိုဘာ/နိုဝင်ဘာ IGCSE မှာ A* ထွက်မှာပါ!",
    "ဒီနေ့ လုပ်သမျှ ကြိုးစားမှုတိုင်းက အောင်မြင်မှုဆီကို တစ်လှမ်းချင်း ပိုနီးစပ်စေပါတယ်။",
    "ကိုယ်လုပ်နိုင်တယ်ဆိုတာကို ယုံကြည်ပါ။ ခက်ခဲတာတွေကို ကျော်ဖြတ်နိုင်စွမ်း ရှိပါတယ်။",
    "ဇွဲနဲ့လုံ့လက အခက်အခဲမှန်သမျှကို အနိုင်ယူနိုင်ပါတယ်။ ဒီနေ့ကို အကောင်းဆုံး ဖြတ်သန်းကြစို့!",
    "မင်းလုပ်နိုင်ပါတယ်! မင်းရဲ့ အိပ်မက်တွေဆီ ရောက်ဖို့ ဆက်တိုက်လျှောက်လှမ်းပါ။",
]

TIMETABLE_MY = {
    "Monday": (
        "📅 *တနင်္လာနေ့ အချိန်ဇယား*\n\n"
        "• 08:00 - 11:30: **Further Math & Math B** (Past Papers ဖြေဆိုခြင်း)\n"
        "• 12:00 - 13:30: **ESL** (အတန်းတက်ရန်)\n"
        "• 13:30 - 14:30: နေ့လယ်စာစားချိန်နှင့် အနားယူချိန်\n"
        "• 14:30 - 16:00: **Physics** (သဘောတရားနှင့် Formula များ)\n"
        "• 16:00 - 17:00: **Math B** (အတန်းတက်ရန်)\n"
        "• 17:00 - 19:30: **Chemistry** (လေ့ကျင့်ခန်းများ)\n"
        "• 20:30 - 22:00: **ICT** (သီအိုရီဖတ်ရှုခြင်း)"
    ),
    "Tuesday": (
        "📅 *အင်္ဂါနေ့ အချိန်ဇယား*\n\n"
        "• 08:00 - 11:30: **Further Math** (Past Paper ပြန်လည်သုံးသပ်ခြင်း)\n"
        "• 12:00 - 13:30: **Physics** (အတန်းတက်ရန်)\n"
        "• 13:30 - 14:30: နေ့လယ်စာစားချိန်နှင့် အနားယူချိန်\n"
        "• 14:30 - 18:30: **Chemistry & ICT** (တွက်ချက်မှုနှင့် လက်တွေ့)\n"
        "• 19:00 - 21:00: **Math B** (အတန်းတက်ရန်)\n"
        "• 21:00 - 22:00: **ESL** (Writing လေ့ကျင့်ခြင်း)"
    ),
    "Wednesday": (
        "📅 *ဗုဒ္ဓဟူးနေ့ အချိန်ဇယား (အားလပ်ရက်)*\n\n"
        "• *မှတ်ချက် - အစားထိုးအတန်းရှိက တက်ရန်*\n"
        "• 08:00 - 11:30: **Physics & Chemistry** ပြန်လည်ဖတ်ရှုခြင်း\n"
        "• 12:30 - 16:30: **Further Math & Math B** (Mock Past Papers)\n"
        "• 19:00 - 21:30: **ICT & ESL** လေ့ကျင့်ခြင်း"
    ),
    "Thursday": (
        "📅 *ကြာသပတေးနေ့ အချိန်ဇယား*\n\n"
        "• 08:00 - 12:30: **Physics & Chemistry** Past Papers\n"
        "• 13:30 - 14:45: **ESL** (အတန်းတက်ရန်)\n"
        "• 14:45 - 17:30: **Math B & Further Math** လေ့ကျင့်ခြင်း\n"
        "• 18:00 - 19:30: **ICT** (အတန်းတက်ရန်)\n"
        "• 20:30 - 22:00: **Chemistry** ပြန်လည်နွှေးခြင်း"
    ),
    "Friday": (
        "📅 *သောကြာနေ့ အချိန်ဇယား*\n\n"
        "• 08:00 - 12:00: **Further Math & Math B** (Calculus/Vectors)\n"
        "• 13:00 - 17:00: **Physics & ICT** Review\n"
        "• 17:00 - 18:30: **Physics** (အတန်းတက်ရန်)\n"
        "• 19:00 - 20:30: **Chemistry** (အတန်းတက်ရန်)\n"
        "• 20:30 - 22:00: **ESL** (ဝေါဟာရနှင့် သဒ္ဒါ)"
    ),
    "Saturday": (
        "📅 *စနေနေ့ အချိန်ဇယား (အားလပ်ရက်)*\n\n"
        "• *မှတ်ချက် - အစားထိုးအတန်းရှိက တက်ရန်*\n"
        "• 08:00 - 11:30: **Physics & Chemistry** အခြေခံများ\n"
        "• 12:30 - 16:30: **Further Math & Math B** Past Papers\n"
        "• 19:00 - 21:30: **ICT Practical & ESL Writing**"
    ),
    "Sunday": (
        "📅 *တနင်္ဂနွေနေ့ အချိန်ဇယား*\n\n"
        "• 08:00 - 10:00: **Math B** မနက်ပိုင်းတွက်ချက်မှုများ\n"
        "• 10:30 - 12:00: **Chemistry** (အတန်းတက်ရန်)\n"
        "• 13:00 - 16:00: **Physics & Further Math** Catch-up\n"
        "• 16:00 - 17:30: **ICT** (အတန်းတက်ရန်)\n"
        "• 17:30 - 20:00: တစ်ပတ်တာ သိပ္ပံဘာသာရပ်များ ပြန်လည်ကြည့်ရှုခြင်း\n"
        "• 20:00 - 21:30: **ESL** (အတန်းတက်ရန်)\n"
        "• 21:30 onwards: အနားယူခြင်းနှင့် အိပ်စက်ခြင်း"
    ),
}


async def today_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
  current_day = dt.datetime.now(pytz.timezone("Asia/Yangon")).strftime("%A")
  quote = random.choice(MYANMAR_QUOTES)
  schedule_text = (
      f"📅 **ယနေ့အတွက် အချိန်ဇယား**\n💬 *{quote}*\n\n"
      f"{TIMETABLE_MY.get(current_day, 'ဒီနေ့အတွက် အချိန်ဇယား မရှိသေးပါ။')}"
  )
  await update.message.reply_text(schedule_text, parse_mode="Markdown")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
  chat_id = update.effective_chat.id
  await update.message.reply_text(
      f"မင်္ဂလာပါ! Bot အလုပ်လုပ်နေပါပြီ။ သင့်ရဲ့ Chat ID မှာ: `{chat_id}` ဖြစ်ပါတယ်။"
  )


def main():
  # Token အမှန်ကို ထည့်ပါ သို့မဟုတ် Railway Variables မှာ သတ်မှတ်ပါ
  if TOKEN == "YOUR_NEW_TOKEN_HERE":
    print("Error: Please set your Telegram Bot Token!")
    return

  app = ApplicationBuilder().token(TOKEN).build()

  app.add_handler(CommandHandler("start", start))
  app.add_handler(CommandHandler("today", today_command))

  print("Bot is running smoothly...")
  # railway မှာ ချို့ယွင်းချက်မရှိ အလုပ်လုပ်စေရန် drop_pending_updates=True ထည့်ထားခြင်း
  app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
  main()
