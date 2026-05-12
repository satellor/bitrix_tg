import asyncio
import json
import os
import redis.asyncio as redis
import aiohttp

BITRIX_WEBHOOK = os.getenv("BITRIX_WEBHOOK_URL")

redis_client = redis.Redis(host='redis', port=6379, decode_responses=True)

async def create_lead(lead_data):
    fields = {
        "TITLE": lead_data.get("title", "Заявка из Telegram"),
        "COMMENTS": lead_data.get("description", ""),
        "NAME": lead_data.get("name", "Клиент Telegram"),
    }
    if lead_data.get("phone"):
        fields["PHONE"] = [{"VALUE": lead_data["phone"], "VALUE_TYPE": "WORK"}]
    
    async with aiohttp.ClientSession() as session:
        url = f"{BITRIX_WEBHOOK}crm.lead.add.json"
        async with session.post(url, json={"fields": fields}) as resp:
            result = await resp.json()
            if result.get("result"):
                print(f"✅ Лид {result['result']} создан")
                return True
            else:
                print(f"❌ Ошибка: {result}")
                return False

async def main():
    print("🚀 Bitrix коннектор запущен, жду задачи...")
    while True:
        _, data = await redis_client.brpop("bitrix_tasks")
        task = json.loads(data)
        print(f"📥 Получена задача от {task['user_id']}")
        await create_lead(task["crm_data"])

if __name__ == "__main__":
    asyncio.run(main())
