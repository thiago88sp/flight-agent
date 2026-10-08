"""Price watches: re-run saved searches and alert (Telegram) when the target price is reached.

Made to run unattended (GitHub Actions or cron):

  python -m flight_agent.watch                     # check every active watch
  python -m flight_agent.watch --list              # show the watches and their state
  python -m flight_agent.watch --telegram-chat-id  # find your chat id
  python -m flight_agent.watch --test              # send a test message on Telegram

Watches: the WATCHES variable (JSON, used on GitHub Actions) or the WATCHES_FILE file
(default watches.json, created by the "Watch" button in the web app).
State (lowest price seen, last alert): the WATCH_STATE file (default watch_state.json).

Alert rules: alert when the lowest price is <= target; after that, alert again only if it drops
below the last alerted price. Once the end date passes, send a summary and stop.
"""
import argparse
import html
import json
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

from . import config, notify, parsing, providers, search  # noqa: F401 (config reads .env)
from . import present as fmt


# ------------------------------------------------------------------ storage
def watches_file() -> Path:
    return Path(os.getenv("WATCHES_FILE", "watches.json"))


def state_file() -> Path:
    return Path(os.getenv("WATCH_STATE", "watch_state.json"))


def load_watches():
    raw = os.getenv("WATCHES")
    if raw and raw.strip():
        return json.loads(raw)
    path = watches_file()
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []


def save_watches(watches):
    watches_file().write_text(json.dumps(watches, ensure_ascii=False, indent=2), encoding="utf-8")


def load_state():
    path = state_file()
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def save_state(state):
    state_file().write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def new_watch(params, target, days=30, label=None):
    """Build a watch record from the normalized parameters of a search."""
    keep = ("origin", "dests", "region", "depart", "stay", "flex", "month", "max_stops")
    query = {k: params.get(k) for k in keep}
    wid = f"{params['origin']}-{'-'.join(params['dests'][:3])}-{params['depart']}-{int(target)}"
    return {"id": wid.lower(), "label": label or parsing.route_label(params),
            "query": query, "target": float(target),
            "until": (date.today() + timedelta(days=int(days))).isoformat()}


def add_watch(watch):
    """Save to watches.json (replaces a watch with the same id)."""
    watches = [w for w in load_watches() if w["id"] != watch["id"]] + [watch]
    save_watches(watches)
    return watches


def remove_watch(wid):
    watches = [w for w in load_watches() if w["id"] != wid]
    save_watches(watches)
    return watches


# ------------------------------------------------------------------ checking
def _offer_text(origin, o):
    return (f"<b>{html.escape(fmt.city(o['dest']))}</b> for <b>{fmt.money(o['price'])}</b>\n"
            f"📅 {fmt.trip(o)}\n"
            f"🛫 {html.escape(fmt.airline(o['airline']))} · {fmt.stops(o['stops'])}")


def check_watch(watch, provider, st, send):
    """Check one watch. `st` is its state (updated in place); `send(text, button)` delivers the
    alert. Returns one log line."""
    label, target = watch["label"], float(watch["target"])
    today = date.today().isoformat()

    if today > watch["until"]:
        if not st.get("expired"):
            seen = f"the lowest price seen was {fmt.money(st['best'])}" if st.get("best") else \
                "no price was found during that time"
            send(f"⏹️ Watch <b>{html.escape(label)}</b> ended (it ran until "
                 f"{fmt.day(watch['until'])}): {seen}. The target was {fmt.money(target)}.", None)
            st["expired"] = True
        return f"{label}: expired"

    params = parsing.normalize_params(watch["query"])
    if not search.window(params):
        return f"{label}: departure dates are in the past"
    results = search.search_grid(provider, params)
    st["checked"] = datetime.now().isoformat(timespec="minutes")
    if not results:
        return f"{label}: no offers right now"

    best = results[0]
    st["best"] = min(st.get("best") or best["price"], best["price"])
    st["last"] = best["price"]
    hit = best["price"] <= target
    already = st.get("notified")
    if hit and (already is None or best["price"] < already):
        url = fmt.booking_url(params["origin"], best)
        head = "🎯 Target price reached!" if already is None else "📉 It dropped even more!"
        send(f"{head} <b>{html.escape(label)}</b>\n\n{_offer_text(params['origin'], best)}\n\n"
             f"Your target: {fmt.money(target)} · watching until {fmt.day(watch['until'])}",
             (f"Book on {fmt.booking_site(best)} ✈️", url))
        st["notified"] = best["price"]
        return f"{label}: ALERT sent ({fmt.money(best['price'])} <= {fmt.money(target)})"
    return f"{label}: lowest now {fmt.money(best['price'])} (target {fmt.money(target)})"


def run(send=None, provider=None):
    """Check every watch and save the state. Returns the log lines."""
    if send is None:
        if not notify.telegram_enabled():
            print("[warning] TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID not set: alerts only on screen",
                  file=sys.stderr)
        send = _send_default
    provider = provider or providers.get_provider()
    state = load_state()
    log = []
    for w in load_watches():
        st = state.setdefault(w["id"], {})
        try:
            log.append(check_watch(w, provider, st, send))
        except Exception as e:  # one broken watch must not stop the others
            log.append(f"{w.get('label', w.get('id'))}: error {e}")
        for err in provider.pop_errors():
            log.append(f"  [error] {err}")
    save_state(state)
    return log


def _send_default(text, button):
    print("\n" + text + (f"\n→ {button[1]}" if button else ""))
    if notify.telegram_enabled():
        notify.send_telegram(text, button)


# ------------------------------------------------------------------ command line
def main(argv=None):
    ap = argparse.ArgumentParser(description="Price watches with Telegram alerts")
    ap.add_argument("--list", action="store_true", help="list watches and their state")
    ap.add_argument("--export", action="store_true",
                    help="print the JSON to paste into the WATCHES secret on GitHub")
    ap.add_argument("--telegram-chat-id", action="store_true",
                    help="show the chat id of whoever messaged the bot")
    ap.add_argument("--test", action="store_true", help="send a test message")
    a = ap.parse_args(argv)

    if a.telegram_chat_id:
        token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        if not token:
            sys.exit("Set TELEGRAM_BOT_TOKEN in .env first.")
        if not notify.valid_token(token):
            sys.exit("TELEGRAM_BOT_TOKEN is incomplete: the format is <digits>:<secret>, e.g. "
                     "7123456789:AAH... Copy the whole line from the @BotFather message.")
        try:
            chats = notify.telegram_chat_ids(token)
        except Exception as e:
            code = getattr(getattr(e, "response", None), "status_code", None)
            sys.exit("Telegram rejected the token (revoked or mistyped?). Create a new one with "
                     "/revoke in @BotFather." if code in (401, 404) else
                     f"Could not reach Telegram: {type(e).__name__}")
        if not chats:
            sys.exit("No messages found: send 'hi' to your bot and run this again.")
        for cid, name in chats:
            print(f"TELEGRAM_CHAT_ID={cid}   ({name})")
        return
    if a.test:
        if not notify.telegram_enabled():
            sys.exit("Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env.")
        ok = notify.send_telegram("✅ Flight Deal Agent connected. Your alerts will arrive here.")
        sys.exit(0 if ok else 1)
    if a.export:
        print(json.dumps(load_watches(), ensure_ascii=False, separators=(",", ":")))
        return
    if a.list:
        state = load_state()
        for w in load_watches():
            st = state.get(w["id"], {})
            best = fmt.money(st["best"]) if st.get("best") else "—"
            print(f"{w['label']} | target {fmt.money(w['target'])} | until {w['until']} | "
                  f"lowest seen {best} | last check {st.get('checked', '—')}")
        return
    for line in run():
        print(line)


if __name__ == "__main__":
    main()
