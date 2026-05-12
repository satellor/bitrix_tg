import asyncio
import os
from aiogram import Bot, Dispatcher

#токен из переменных окружения
TOKEN = os.getenv("BOT_TOKEN")

async def main():
    bot = Bot(token=TOKEN)
    dp = Dispatcher()

    print("Бот успешно запущен и слушает сообщения...")

    # ЗАПУСК ПОЛЛИНГА
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Бот остановлен")