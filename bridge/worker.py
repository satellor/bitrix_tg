import asyncio
import json
import os
import redis.asyncio as redis
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
IN_QUEUE = os.getenv("TG_MESSAGES_QUEUE", "tg_messages")
OUT_QUEUE = os.getenv("BITRIX_TASKS_QUEUE", "bitrix_tasks")
async def main():
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    print("Bridge running: reads", IN_QUEUE, "writes", OUT_QUEUE)
    while True:
        _, raw = await r.brpop(IN_QUEUE)
        msg = json.loads(raw)
        uid = msg["user_id"]
        text = (msg.get("text") or "").strip()
        if not text:
            continue
        task = {
            "user_id": uid,
            "crm_data": {
                "title": f"Telegram {uid}",
                "description": text[:8000],
                "name": f"TG user {uid}",
            },
        }
        await r.lpush(OUT_QUEUE, json.dumps(task, ensure_ascii=False))
        print("Sent to Bitrix queue for user", uid)
if __name__ == "__main__":
    asyncio.run(main())