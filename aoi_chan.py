import datetime as dt
import logging
import random
import pytz
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# သင့်ရဲ့ တကယ့် Bot Token နဲ့ Chat ID များကို တိုက်ရိုက်ထည့်သွင်းထားပါသည်
TOKEN = "8884160612:AAEXBlgw8coEtH3GsxIew9368RMfcbatATI"
CHAT_ID = "7291770711"

# Errors များကို စောင့်ကြည့်ရန် Logging သတ်မှတ်ခြင်း
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# အားပေးစကားများနှင့် Motivation များ
MYANMAR_QUOTES = [
    "အရမ်းကြိုးစားနေတာ ဂုဏ်ယူပါတယ်။ အောက်တိုဘာ/နိုဝင်ဘာ IGCSE မှာ A* ထွက်မှာပါ!",
    "ဒီနေ့ လုပ်သမျှ ကြိုးစားမှုတိုင်းက အောင်မြင်မှုဆီကို တစ်လှမ်းချင်း ပိုနီးစပ်စေပါတယ်။",
    "ကိုယ်လုပ်နိုင်တယ်ဆိုတာကို ယုံကြည်ပါ။ ခက်ခဲတာတွေကို ကျော်ဖြတ်နိုင်စွမ်း ရှိပါတယ်။",
    "ဇွဲနဲ့လုံ့လက အခက်အခဲမှန်သမျှကို အနိုင်ယူနိုင်ပါတယ်။ ဒီနေ့ကို အကောင်းဆုံး ဖြတ်သန်းကြစို့!",
    "မင်းလုပ်နိုင်ပါတယ်! မင်းရဲ့ အိပ်မက်တွေဆီ ရောက်ဖို့ ဆက်တိုက်လျှောက်လှမ်းပါ။",
]

# အသေးစိတ် IGCSE တစ်ပတ်တာ အချိန်ဇယား
TIMETABLE_MY = {
    "Monday": (
        "📅 *တနင်္လာနေ့ အချိန်ဇယား*\n\n"
        "• 08:00 - 11:30: **Further Math & Math B** (Vectors & Calculus Past Papers)\n"
        "• 12:00 - 13:30: **ESL** (Reading Exercise 5 & 6 Summary Writing)\n"
        "• 13:30 - 14:30: နေ့လယ်စာစားချိန်နှင့် အနားယူချိန်\n"
        "• 14:30 - 16:00: **Physics** (Forces, Motion & Momentum $p=mv$)\n"
        "• 16:00 - 17:00: **Math B** (Matrices & Transformations)\n"
        "• 17:00 - 19:30: **Chemistry** (Moles Calculation & Stoichiometry)\n"
        "• 20:30 - 22:00: **ICT** (Computer Systems & Input/Output Devices)"
    ),
    "Tuesday": (
        "📅 *အင်္ဂါနေ့ အချိန်ဇယား*\n\n"
        "• 08:00 - 11:30: **Further Math** (Matrices & Simultaneous Equations)\n"
        "• 12:00 - 13:30: **Physics** (Work, Energy & Power $W=Fs$)\n"
        "• 13:30 - 14:30: နေ့လယ်စာစားချိန်နှင့် အနားယူချိန်\n"
        "• 14:30 - 18:30: **Chemistry & ICT** (Electrolysis & Database Access Practice)\n"
        "• 19:00 - 21:00: **Math B** (Functions, Graphs & Coordinate Geometry)\n"
        "• 21:00 - 22:00: **ESL** (Directed Writing: Letters & Articles)"
    ),
    "Wednesday": (
        "📅 *ဗုဒ္ဓဟူးနေ့ အချိန်ဇယား (အားလပ်ရက် / Revision)*\n\n"
        "• *မှတ်ချက် - အစားထိုးအတန်းရှိက တက်ရန်*\n"
        "• 08:00 - 11:30: **Physics & Chemistry** Formulas & Organic Mapping\n"
        "• 12:30 - 16:30: **Further Math & Math B** (Mock Past Papers Timed)\n"
        "• 19:00 - 21:30: **ICT Practical & ESL Listening** Practice"
    ),
    "Thursday": (
        "📅 *ကြာသပတေးနေ့ အချိန်ဇယား*\n\n"
        "• 08:00 - 12:30: **Physics & Chemistry** Alternative to Practical (ATP)\n"
        "• 13:30 - 14:45: **ESL** (Reading Comprehension)\n"
        "• 14:45 - 17:30: **Math B & Further Math** (Trigonometry & 3D Problems)\n"
        "• 18:00 - 19:30: **ICT** (Web Authoring HTML & CSS Basics)\n"
        "• 20:30 - 22:00: **Chemistry** (Energetics & Bond Energy)"
    ),
    "Friday": (
        "📅 *သောကြာနေ့ အချိန်ဇယား*\n\n"
        "• 08:00 - 12:00: **Further Math & Math B** (AP/GP Series & Binomial Expansion)\n"
        "• 13:00 - 17:00: **Physics & ICT** (Thermal Physics & CSS Styling)\n"
        "• 17:00 - 18:30: **Physics** (အတန်းတက်ရန်)\n"
        "• 19:00 - 20:30: **Chemistry** (အတန်းတက်ရန်)\n"
        "• 20:30 - 22:00: **ESL** (Vocabulary, Idioms & Grammar)"
    ),
    "Saturday": (
        "📅 *စနေနေ့ အချိန်ဇယား (အားလပ်ရက် / Mock Test)*\n\n"
        "• *မှတ်ချက် - အစားထိုးအတန်းရှိက တက်ရန်*\n"
        "• 08:00 - 11:30: **Physics & Chemistry** Waves & Refractive Index ($n=\\frac{\\sin i}{\\sin r$)\n"
        "• 12:30 - 16:30: **Further Math & Math B** Full Past Paper Simulation\n"
        "• 19:00 - 21:30: **ICT Practical Spreadsheet & ESL Essay**"
    ),
    "Sunday": (
        "📅 *တနင်္ဂနွေနေ့ အချိန်ဇယား*\n\n"
        "• 08:00 - 10:00: **Math B** Complex Numbers & Advanced Algebra\n"
        "• 10:30 - 12:00: **Chemistry** (အတန်းတက်ရန်)\n"
        "• 13:00 - 16:00: **Physics & Further Math** Catch-up Review\n"
        "• 16:00 - 17:30: **ICT** (အတန်းတက်ရန်)\n"
        "• 17:30 - 20:00: သိပ္ပံဘာသာရပ်များ Flashcard ပြန်လည်ကြည့်ရှုခြင်း\n"
        "• 20:00 - 21:30: **ESL** (အတန်းတက်ရန်)\n"
        "• 21:30 onwards: အနားယူခြင်းနှင့် အိပ်စက်ခြင်း"
    ),
}


# မနက်ပိုင်း အလိုအလျောက် ပို့ပေးမည့် ဖန်ရှင်
async def send_morning_message(context: ContextTypes.DEFAULT_TYPE):
  current_day = dt.datetime.now(pytz.timezone("Asia/Yangon")).strftime("%A")
  quote = random.choice(MYANMAR_QUOTES)
  schedule_text = (
      f"🌅 **မင်္ဂလာနံနက်ခင်းပါ! ထလို့ရပါပြီ!**\n💬 *{quote}*\n\n"
      f"{TIMETABLE_MY.get(current_day, 'ဒီနေ့အတွက် အချိန်ဇယား မရှိသေးပါ။')}"
  )
  try:
    await context.bot.send_message(
        chat_id=CHAT_ID, text=schedule_text, parse_mode="Markdown"
    )
  except Exception as e:
    logger.error(f"Failed to send morning message: {e}")


# /today လို့ ရိုက်လိုက်ရင် ထိုနေ့အတွက် အချိန်ဇယားပြမည့် command
async def today_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
  current_day = dt.datetime.now(pytz.timezone("Asia/Yangon")).strftime("%A")
  quote = random.choice(MYANMAR_QUOTES)
  schedule_text = (
      f"📅 **ယနေ့အတွက် အချိန်ဇယား**\n💬 *{quote}*\n\n"
      f"{TIMETABLE_MY.get(current_day, 'ဒီနေ့အတွက် အချိန်ဇယား မရှိသေးပါ။')}"
  )
  await update.message.reply_text(schedule_text, parse_mode="Markdown")


# /start လို့ ရိုက်လိုက်ရင် အလုပ်လုပ်မည့် command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
  await update.message.reply_text(
      "မင်္ဂလာပါ! Aoi Study Bot အောင်မြင်စွာ အလုပ်လုပ်နေပါပြီ။ 📅 အချိန်မရွေး"
      " /today လို့ ရိုက်ပြီး အချိန်ဇယားကို စစ်ဆေးနိုင်ပါတယ်။"
  )


def main():
  # Telegram Application တည်ဆောက်ခြင်း
  app = (
      ApplicationBuilder()
      .token(TOKEN)
      .connect_timeout(30.0)
      .read_timeout(30.0)
      .write_timeout(30.0)
      .build()
  )

  app.add_handler(CommandHandler("start", start))
  app.add_handler(CommandHandler("today", today_command))

  # မြန်မာစံတော်ချိန် (Asia/Yangon) ဖြင့် မနက် ၇ နာရီတိတိတိုင်း ပို့ရန် သတ်မှတ်ခြင်း
  burma_tz = pytz.timezone("Asia/Yangon")
  t = dt.time(hour=7, minute=0, second=0, tzinfo=burma_tz)

  job_queue = app.job_queue
  job_queue.run_daily(send_morning_message, time=t)

  print("Bot is running smoothly with your Chat ID and Token...")
  app.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
  main()
