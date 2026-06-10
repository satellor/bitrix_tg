import base64
import json
import os
import tempfile
import time
import asyncio
from pathlib import Path

import aiohttp
import redis.asyncio as redis
from fastapi import FastAPI, Request
import whisper  

WAPPI_TOKEN = os.getenv("WAPPI_TOKEN")
WAPPI_PROFILE_ID = os.getenv("WAPPI_PROFILE_ID")
WAPPI_BASE_URL = os.getenv("WAPPI_BASE_URL", "https://wappi.pro").rstrip("/")
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base")
OUT_QUEUE = os.getenv("WA_MESSAGES_QUEUE", "wa_messages")

app = FastAPI()
redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

whisper_model = whisper.load_model(WHISPER_MODEL, device="cpu")


def chat_to_recipient(chat_id: str) -> str:
    return chat_id.split("@")[0]


async def push_message(user_id: str, text: str, msg_type: str, contact_name: str = ""):
    data = {
        "source": "whatsapp",
        "user_id": user_id,
        "text": text,
        "type": msg_type,
        "contact_name": contact_name,
        "timestamp": int(time.time()),
    }
    await redis_client.lpush(OUT_QUEUE, json.dumps(data, ensure_ascii=False))


async def wappi_send_text(chat_id: str, text: str):
    url = f"{WAPPI_BASE_URL}/api/sync/message/send"
    headers = {"Authorization": WAPPI_TOKEN}
    params = {"profile_id": WAPPI_PROFILE_ID}
    payload = {
        "body": text,
        "recipient": chat_to_recipient(chat_id),
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, params=params, json=payload) as resp:
            body = await resp.text()
            if resp.status != 200:
                print("Wappi send error:", resp.status, body)


def iter_incoming_messages(payload: dict):
    raw = payload.get("messages")
    if not raw:
        return
    if isinstance(raw, list):
        for m in raw:
            yield m
    elif isinstance(raw, dict):
        yield raw


@app.post("/webhook/wappi")
async def wappi_webhook(request: Request):
    payload = await request.json()

    for msg in iter_incoming_messages(payload):
        if msg.get("wh_type") != "incoming_message":
            continue
        if msg.get("is_me"):
            continue

        chat_id = msg.get("chatId") or msg.get("from")
        if not chat_id:
            continue

        contact_name = msg.get("contact_name") or msg.get("senderName") or ""
        msg_type = msg.get("type")

        if msg_type == "chat":
            body = (msg.get("body") or "").strip()
            if not body:
                continue
            await push_message(chat_id, body, "text", contact_name)
            await wappi_send_text(chat_id, "Принято")
            continue

        if msg_type == "ptt":
            b64 = msg.get("body")
            if not b64:
                continue
            tmp = Path(tempfile.gettempdir()) / f"wa_{msg.get('id', 'voice')}.ogg"
            tmp.write_bytes(base64.b64decode(b64))
            try:
                loop = asyncio.get_running_loop()
                result = await loop.run_in_executor(
                    None, lambda: whisper_model.transcribe(str(tmp), beam_size=5)
                )
                text = result.get("text", "").strip()
                
                if text:
                    await push_message(chat_id, text, "voice", contact_name)
                    await wappi_send_text(chat_id, f"Распознано: {text[:100]}")
                else:
                    await wappi_send_text(chat_id, "Не удалось распознать речь")
            finally:
                tmp.unlink(missing_ok=True)
            continue

    return {"ok": True}


@app.get("/health")
async def health():
    return {"status": "ok"}
