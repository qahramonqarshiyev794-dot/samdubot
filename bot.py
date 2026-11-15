import asyncio
import logging
import os
import secrets
from collections import defaultdict, deque

from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.enums import ChatAction
from aiogram.filters import Command
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from dotenv import load_dotenv
from google import genai

load_dotenv("main.env")

TELEGRAM_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
MODEL = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")
MAX_HISTORY = int(os.getenv("MAX_HISTORY", "20"))  # har bir foydalanuvchi uchun oxirgi xabarlar soni
SYSTEM_PROMPT = os.getenv(
    "SYSTEM_PROMPT",
    "Siz Telegramdagi samimiy va amaliy yordamchisiz. Foydalanuvchi qaysi tilda "
    "yozsa, o'sha tilda javob bering. Oddiy suhbatlashing, savollarga javob "
    "bering va so'ralgan vazifalarni imkon qadar bajarib bering: matn yozish yoki "
    "tahrirlash, tarjima, rejalashtirish, tushuntirish va g'oyalar taklif qilish. "
    "Muhim ma'lumot yetishmasa, aniqlashtiruvchi savol bering; bilmagan "
    "ma'lumotingizni to'qimang. Javoblarni foydalanuvchi talabiga mos, lo'nda "
    "va tushunarli qiling.",
)

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("ai-bot")

bot = Bot(TELEGRAM_TOKEN)
dp = Dispatcher()
client = genai.Client(api_key=GEMINI_API_KEY)
START_KEYBOARD = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="Yordam"), KeyboardButton(text="Admin")]],
    resize_keyboard=True,
)

# Har bir chat uchun suhbat tarixi (xotirada saqlanadi)
history: dict[int, deque] = defaultdict(lambda: deque(maxlen=MAX_HISTORY))
chat_locks: dict[int, asyncio.Lock] = defaultdict(asyncio.Lock)


def split_text(text: str, limit: int = 4000):
    """Telegram 4096 belgidan uzun xabarni qabul qilmaydi."""
    while text:
        yield text[:limit]
        text = text[limit:]


async def health_check(_: web.Request) -> web.Response:
    return web.Response(text="ok")


@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "Salom! Men suhbatlashish va turli vazifalarda yordam beradigan "
        "sun'iy intellekt yordamchisiman. Savolingizni yoki topshirig'ingizni "
        "yozing.",
        reply_markup=START_KEYBOARD,
    )


@dp.message(Command("help"))
@dp.message(F.text.casefold() == "yordam")
async def cmd_help(message: Message):
    await message.answer(
        "Men bilan oddiy suhbatlashing yoki vazifa bering. Masalan:\n"
        "- matn yozish yoki tahrirlash\n"
        "- tarjima va tushuntirish\n"
        "- reja tuzish yoki g'oya topish\n"
        "Suhbatni yangidan boshlash uchun /reset buyrug'ini yuboring.\n"
        "Admin bilan bog'lanish: /admin"
    )


@dp.message(Command("admin"))
@dp.message(F.text.casefold() == "admin")
async def cmd_admin(message: Message):
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Admin bilan bog'lanish",
                    url="https://t.me/QARSHIYEV200",
                )
            ]
        ]
    )
    await message.answer(
        "Admin bilan bog'lanish uchun tugmani bosing:",
        reply_markup=keyboard,
    )


@dp.message(Command("reset"))
async def cmd_reset(message: Message):
    async with chat_locks[message.chat.id]:
        history.pop(message.chat.id, None)
    await message.answer("Suhbat tarixi tozalandi.")


@dp.message(F.text)
async def handle_text(message: Message):
    chat_id = message.chat.id
    async with chat_locks[chat_id]:

        async def keep_typing():
            while True:
                try:
                    await message.bot.send_chat_action(chat_id, ChatAction.TYPING)
                except Exception:
                    log.exception("Telegram chat action xatosi")
                    return
                await asyncio.sleep(4)

        typing_task = asyncio.create_task(keep_typing())
        user_turn = {"role": "user", "parts": [{"text": message.text}]}
        try:
            response = await client.aio.models.generate_content(
                model=MODEL,
                contents=[*history[chat_id], user_turn],
                config=genai.types.GenerateContentConfig(
                    max_output_tokens=1500,
                    system_instruction=SYSTEM_PROMPT,
                ),
            )
            answer = (response.text or "").strip()
            if answer:
                history[chat_id].extend(
                    (user_turn, {"role": "model", "parts": [{"text": answer}]})
                )
            else:
                answer = "Javob olinmadi, qayta urinib ko'ring."
        except Exception:
            log.exception("Gemini API xatosi")
            answer = "Kechirasiz, xatolik yuz berdi. Birozdan keyin qayta urinib ko'ring."
        finally:
            typing_task.cancel()
            await asyncio.gather(typing_task, return_exceptions=True)

        for part in split_text(answer):
            await message.answer(part)


async def run_polling() -> None:
    log.info("Bot polling rejimida ishga tushdi")
    await dp.start_polling(bot)


def create_render_app(hostname: str, webhook_secret: str) -> web.Application:
    app = web.Application()
    app.router.add_get("/health", health_check)
    setup_application(app, dp, bot=bot)
    SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
        secret_token=webhook_secret,
    ).register(app, path="/telegram")

    async def register_webhook(_: web.Application) -> None:
        await bot.set_webhook(
            url=f"https://{hostname}/telegram",
            secret_token=webhook_secret,
            allowed_updates=dp.resolve_used_update_types(),
        )
        log.info("Telegram webhook ro'yxatdan o'tkazildi")

    app.on_startup.append(register_webhook)
    return app


def main() -> None:
    if os.getenv("RENDER") == "true":
        hostname = os.getenv("RENDER_EXTERNAL_HOSTNAME")
        if not hostname:
            raise RuntimeError("Render tashqi host nomi aniqlanmadi")

        app = create_render_app(hostname, secrets.token_urlsafe(32))
        web.run_app(
            app,
            host="0.0.0.0",
            port=int(os.getenv("PORT", "10000")),
        )
        return

    asyncio.run(run_polling())


if __name__ == "__main__":
    main()
