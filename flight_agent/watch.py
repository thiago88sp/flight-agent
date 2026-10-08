"""Monitoramento de preços: refaz buscas salvas e avisa (Telegram) quando o preço-alvo é atingido.

Feito para rodar sozinho (GitHub Actions ou cron):

  python -m flight_agent.watch                 # verifica todos os monitoramentos ativos
  python -m flight_agent.watch --list          # mostra os monitoramentos e o estado
  python -m flight_agent.watch --telegram-chat-id   # descobre o seu chat id
  python -m flight_agent.watch --test          # manda uma mensagem de teste no Telegram

Monitoramentos: variável WATCHES (JSON, usada no GitHub Actions) ou o arquivo WATCHES_FILE
(padrão watches.json, criado pelo botão "Monitorar" da interface).
Estado (menor preço visto, último aviso): arquivo WATCH_STATE (padrão watch_state.json).

Regras de aviso: avisa quando o menor preço fica <= alvo; depois só avisa de novo se cair
abaixo do último preço avisado. Ao passar da data-limite, manda um resumo e para.
"""
import argparse
import html
import json
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

from . import config, notify, parsing, providers, search  # noqa: F401 (config lê o .env)
from . import present as fmt


# ------------------------------------------------------------------ armazenamento
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
    """Cria o registro de um monitoramento a partir dos parâmetros normalizados de uma busca."""
    keep = ("origin", "dests", "region", "depart", "stay", "flex", "month", "max_stops")
    query = {k: params.get(k) for k in keep}
    wid = f"{params['origin']}-{'-'.join(params['dests'][:3])}-{params['depart']}-{int(target)}"
    return {"id": wid.lower(), "label": label or parsing.route_label(params),
            "query": query, "target": float(target),
            "until": (date.today() + timedelta(days=int(days))).isoformat()}


def add_watch(watch):
    """Grava em watches.json (substitui um monitoramento com o mesmo id)."""
    watches = [w for w in load_watches() if w["id"] != watch["id"]] + [watch]
    save_watches(watches)
    return watches


def remove_watch(wid):
    watches = [w for w in load_watches() if w["id"] != wid]
    save_watches(watches)
    return watches


# ------------------------------------------------------------------ verificação
def _offer_text(origin, o):
    return (f"<b>{html.escape(fmt.city(o['dest']))}</b> por <b>{fmt.money(o['price'])}</b>\n"
            f"📅 {fmt.trip(o)}\n"
            f"🛫 {html.escape(fmt.airline(o['airline']))} · {fmt.stops(o['stops'])}")


def check_watch(watch, provider, st, send):
    """Verifica um monitoramento. `st` é o estado dele (alterado no lugar); `send(text, button)`
    entrega o aviso. Devolve uma linha de log."""
    label, target = watch["label"], float(watch["target"])
    today = date.today().isoformat()

    if today > watch["until"]:
        if not st.get("expired"):
            seen = f"o menor preço visto foi {fmt.money(st['best'])}" if st.get("best") else \
                "não encontrei nenhum preço no período"
            send(f"⏹️ Monitoramento <b>{html.escape(label)}</b> encerrado (prazo até "
                 f"{fmt.day(watch['until'])}): {seen}. Alvo era {fmt.money(target)}.", None)
            st["expired"] = True
        return f"{label}: expirado"

    params = parsing.normalize_params(watch["query"])
    if not search.window(params):
        return f"{label}: datas de ida já passaram"
    results = search.search_grid(provider, params)
    st["checked"] = datetime.now().isoformat(timespec="minutes")
    if not results:
        return f"{label}: nenhuma oferta agora"

    best = results[0]
    st["best"] = min(st.get("best") or best["price"], best["price"])
    st["last"] = best["price"]
    hit = best["price"] <= target
    already = st.get("notified")
    if hit and (already is None or best["price"] < already):
        url = fmt.booking_url(params["origin"], best)
        head = "🎯 Preço-alvo atingido!" if already is None else "📉 Caiu ainda mais!"
        send(f"{head} <b>{html.escape(label)}</b>\n\n{_offer_text(params['origin'], best)}\n\n"
             f"Seu alvo: {fmt.money(target)} · monitorando até {fmt.day(watch['until'])}",
             (f"Comprar no {fmt.booking_site(best)} ✈️", url))
        st["notified"] = best["price"]
        return f"{label}: AVISO enviado ({fmt.money(best['price'])} <= {fmt.money(target)})"
    return f"{label}: menor agora {fmt.money(best['price'])} (alvo {fmt.money(target)})"


def run(send=None, provider=None):
    """Verifica todos os monitoramentos e grava o estado. Devolve as linhas de log."""
    if send is None:
        if not notify.telegram_enabled():
            print("[aviso] TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID ausentes: avisos só na tela",
                  file=sys.stderr)
        send = _send_default
    provider = provider or providers.get_provider()
    state = load_state()
    log = []
    for w in load_watches():
        st = state.setdefault(w["id"], {})
        try:
            log.append(check_watch(w, provider, st, send))
        except Exception as e:  # um monitoramento com problema não derruba os outros
            log.append(f"{w.get('label', w.get('id'))}: erro {e}")
        for err in provider.pop_errors():
            log.append(f"  [erro] {err}")
    save_state(state)
    return log


def _send_default(text, button):
    print("\n" + text + (f"\n→ {button[1]}" if button else ""))
    if notify.telegram_enabled():
        notify.send_telegram(text, button)


# ------------------------------------------------------------------ linha de comando
def main(argv=None):
    ap = argparse.ArgumentParser(description="Monitoramento de preços com aviso no Telegram")
    ap.add_argument("--list", action="store_true", help="lista monitoramentos e estado")
    ap.add_argument("--export", action="store_true",
                    help="imprime o JSON para colar no secret WATCHES do GitHub")
    ap.add_argument("--telegram-chat-id", action="store_true",
                    help="mostra o chat id de quem mandou mensagem ao bot")
    ap.add_argument("--test", action="store_true", help="envia uma mensagem de teste")
    a = ap.parse_args(argv)

    if a.telegram_chat_id:
        token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        if not token:
            sys.exit("Defina TELEGRAM_BOT_TOKEN no .env primeiro.")
        if not notify.valid_token(token):
            sys.exit("TELEGRAM_BOT_TOKEN incompleto: o formato é <números>:<segredo>, ex.: "
                     "7123456789:AAH... Copie a linha inteira da mensagem do @BotFather.")
        try:
            chats = notify.telegram_chat_ids(token)
        except Exception as e:
            code = getattr(getattr(e, "response", None), "status_code", None)
            sys.exit("O Telegram recusou o token (revogado ou digitado errado?). Gere outro com "
                     "/revoke no @BotFather." if code in (401, 404) else
                     f"Não consegui falar com o Telegram: {type(e).__name__}")
        if not chats:
            sys.exit("Nenhuma mensagem encontrada: mande um 'oi' para o seu bot e rode de novo.")
        for cid, name in chats:
            print(f"TELEGRAM_CHAT_ID={cid}   ({name})")
        return
    if a.test:
        if not notify.telegram_enabled():
            sys.exit("Defina TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID no .env.")
        ok = notify.send_telegram("✅ Agente de Passagens conectado. Os alertas chegarão aqui.")
        sys.exit(0 if ok else 1)
    if a.export:
        print(json.dumps(load_watches(), ensure_ascii=False, separators=(",", ":")))
        return
    if a.list:
        state = load_state()
        for w in load_watches():
            st = state.get(w["id"], {})
            best = fmt.money(st["best"]) if st.get("best") else "—"
            print(f"{w['label']} | alvo {fmt.money(w['target'])} | até {w['until']} | "
                  f"menor visto {best} | última verificação {st.get('checked', '—')}")
        return
    for line in run():
        print(line)


if __name__ == "__main__":
    main()
