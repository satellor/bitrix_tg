import asyncio, os, json, tempfile
from pathlib import Path
from aiogram import Bot, Dispatcher, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
import redis.asyncio as redis
from faster_whisper import WhisperModel
import time

BOT_TOKEN = os.getenv("BOT_TOKEN")
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base")

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
whisper = WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8")

async def send_to_redis(user_id: int, text: str, msg_type: str, file_id: str = None):
    data = {
        "user_id": user_id,
        "text": text,
        "type": msg_type,
        "file_id": file_id,
        "timestamp": int(time.time())
    }
    await redis_client.lpush("tg_messages", json.dumps(data))

@dp.message(lambda msg: msg.text and not msg.text.startswith('/'))
async def text_handler(msg: types.Message):
    await send_to_redis(msg.from_user.id, msg.text, "text")
    await msg.reply("Принято")

@dp.message(lambda msg: msg.voice)
async def voice_handler(msg: types.Message):
    processing = await msg.reply("Распознаю голос...")
    file = await bot.get_file(msg.voice.file_id)
    tmp = Path(tempfile.gettempdir()) / f"{msg.voice.file_unique_id}.ogg"
    await bot.download_file(file.file_path, destination=str(tmp))
    try:
        segments, _ = whisper.transcribe(str(tmp), beam_size=5)
        text = " ".join(seg.text for seg in segments)
        if text.strip():
            await send_to_redis(msg.from_user.id, text.strip(), "voice", msg.voice.file_id)
            await processing.edit_text(f"Распознано: {text[:100]}")
        else:
            await processing.edit_text("Не удалось распознать речь")
    except Exception as e:
        await processing.edit_text("Ошибка распознавания")
        print(e)
    finally:
        tmp.unlink(missing_ok=True)

async def main():
    print("Gateway started")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())