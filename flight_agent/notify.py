"""Alertas: sempre imprime; se TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID estiverem definidos,
também envia pelo Telegram (com botão de compra quando houver link)."""
import html
import os
import re
import sys

API = "https://api.telegram.org/bot{token}/{method}"


def valid_token(token) -> bool:
    """Token do BotFather: '<id numérico>:<segredo>'."""
    return bool(re.fullmatch(r"\d+:[\w-]{30,}", token or ""))


def telegram_enabled() -> bool:
    return bool(os.getenv("TELEGRAM_BOT_TOKEN") and os.getenv("TELEGRAM_CHAT_ID"))


def send_telegram(text, button=None):
    """Envia `text` (HTML do Telegram). `button` = (rótulo, url) vira um botão abaixo da
    mensagem. Devolve True se o Telegram aceitou."""
    import requests
    payload = {"chat_id": os.environ["TELEGRAM_CHAT_ID"], "text": text,
               "parse_mode": "HTML", "disable_web_page_preview": True}
    if button:
        payload["reply_markup"] = {"inline_keyboard": [[{"text": button[0], "url": button[1]}]]}
    try:
        resp = requests.post(API.format(token=os.environ["TELEGRAM_BOT_TOKEN"], method="sendMessage"),
                             json=payload, timeout=30)
    except requests.RequestException as e:
        print(f"[erro] Telegram inacessível: {type(e).__name__}", file=sys.stderr)
        return False
    if resp.status_code != 200:
        print(f"[erro] Telegram HTTP {resp.status_code}: {resp.text[:200]}", file=sys.stderr)
        return False
    return True


def telegram_chat_ids(token):
    """Chats que mandaram mensagem ao bot recentemente: [(chat_id, nome)]."""
    import requests
    resp = requests.get(API.format(token=token, method="getUpdates"), timeout=30)
    resp.raise_for_status()
    chats = {}
    for upd in resp.json().get("result", []):
        chat = (upd.get("message") or upd.get("my_chat_member") or {}).get("chat")
        if chat:
            chats[chat["id"]] = chat.get("first_name") or chat.get("title") or ""
    return list(chats.items())


def notify(message: str, button=None) -> None:
    print(f"\n🔔 ALERTA: {message}")
    if telegram_enabled():
        send_telegram(f"🔔 {html.escape(message)}", button)
