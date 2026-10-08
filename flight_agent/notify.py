"""Alerts: always printed; when TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID are set, also sent
via Telegram (with a booking button when there is a link)."""
import html
import os
import re
import sys

API = "https://api.telegram.org/bot{token}/{method}"


def valid_token(token) -> bool:
    """BotFather token: '<numeric id>:<secret>'."""
    return bool(re.fullmatch(r"\d+:[\w-]{30,}", token or ""))


def telegram_enabled() -> bool:
    return bool(os.getenv("TELEGRAM_BOT_TOKEN") and os.getenv("TELEGRAM_CHAT_ID"))


def send_telegram(text, button=None):
    """Send `text` (Telegram HTML). `button` = (label, url) becomes a button under the message.
    Returns True if Telegram accepted it."""
    import requests
    payload = {"chat_id": os.environ["TELEGRAM_CHAT_ID"], "text": text,
               "parse_mode": "HTML", "disable_web_page_preview": True}
    if button:
        payload["reply_markup"] = {"inline_keyboard": [[{"text": button[0], "url": button[1]}]]}
    try:
        resp = requests.post(API.format(token=os.environ["TELEGRAM_BOT_TOKEN"], method="sendMessage"),
                             json=payload, timeout=30)
    except requests.RequestException as e:
        print(f"[error] Telegram unreachable: {type(e).__name__}", file=sys.stderr)
        return False
    if resp.status_code != 200:
        print(f"[error] Telegram HTTP {resp.status_code}: {resp.text[:200]}", file=sys.stderr)
        return False
    return True


def telegram_chat_ids(token):
    """Chats that recently messaged the bot: [(chat_id, name)]."""
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
    print(f"\n🔔 ALERT: {message}")
    if telegram_enabled():
        send_telegram(f"🔔 {html.escape(message)}", button)
