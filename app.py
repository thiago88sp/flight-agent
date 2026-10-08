"""
Interface web (chat + formulário) para o agente de passagens.

Rodar:  streamlit run app.py

O formulário lateral não usa IA. O chat usa o interpretador configurado em LLM_PROVIDER
(padrão: regras locais, grátis). Busca, ranking e alertas são Python puro.
"""
import json
from datetime import date, timedelta

import pandas as pd
import streamlit as st

import flight_agent as fa
from flight_agent.search import nearby
from flight_agent import config, notify, providers
from flight_agent import watch as watches
from flight_agent import present as fmt
from flight_agent.geo import REGION_LABELS, REGIONS

st.set_page_config(page_title="Agente de Passagens", page_icon="✈️", layout="wide")

PARSER = fa.llm_provider()
IS_MOCK = providers.using_mock()

EXAMPLES = [
    "São Paulo para Lisboa por volta de 10/12, 10 dias",
    "GRU para qualquer cidade da Europa em março, 12 dias, até R$ 5000",
    "Rio para Buenos Aires em 15/11, 5 dias, voo direto",
]
STOPS = {"Tanto faz": None, "Só voo direto": 0, "Até 1 escala": 1, "Até 2 escalas": 2}


@st.cache_resource
def provider():
    return providers.get_provider()


def run_search(params):
    """Busca + análise; devolve um dict pronto para renderizar."""
    prov = provider()
    misses = []
    results = fa.search_grid(prov, params, misses=misses)
    errors = prov.pop_errors()
    if not results:
        return {"params": params, "empty": True, "errors": errors,
                "nearby": nearby(params, misses)}
    return {"params": params, "empty": False, "errors": errors,
            "info": fa.analyze(params, results), "results": results}


# ---------------------------------------------------------------- textos
def dest_label(p):
    if p.get("region") in REGION_LABELS and len(p["dests"]) > 1:
        return f"{REGION_LABELS[p['region']]} ({len(p['dests'])} destinos)"
    if len(p["dests"]) <= 4:
        return ", ".join(fmt.city(d) for d in p["dests"])
    return f"{len(p['dests'])} destinos"


def describe(params):
    """Frase curta confirmando o que foi entendido do pedido."""
    text = f"Procurando voos de **{fmt.city(params['origin'])}** para **{dest_label(params)}**, "
    if params.get("month") and not IS_MOCK:
        text += f"ida em **qualquer dia de {fmt.month(params['month'])}**"
    else:
        text += f"ida por volta de **{fmt.day(params['depart'])}**"
        if params.get("flex"):
            text += f" (± {params['flex']} dias)"
    text += f", **{params['stay']} dias** de viagem" if params.get("stay") else ", **só ida**"
    if params.get("max_stops") is not None:
        text += ", " + ("só voo direto" if params["max_stops"] == 0
                        else f"até {fmt.stops(params['max_stops'])}")
    if params.get("max_price"):
        text += f", até {fmt.money(params['max_price'])}"
    return text + "."


def buy_button(origin, offer, key, primary=False):
    st.link_button(f"Comprar no {fmt.booking_site(offer)}" if primary else "Comprar",
                   fmt.booking_url(origin, offer), icon=":material/open_in_new:",
                   type="primary" if primary else "secondary", width="stretch", key=key)


def best_card(origin, offer, entry, key):
    with st.container(border=True):
        st.caption("🏆 MAIS BARATA")
        left, right = st.columns([3, 1.4], vertical_alignment="center")
        with left:
            st.markdown(f"### {fmt.city(offer['dest'])}")
            st.markdown(f"📅 {fmt.trip(offer)}  \n"
                        f"🛫 {fmt.airline(offer['airline'])} · {fmt.stops(offer['stops'])}")
            if entry["prev"] is not None:
                trend = "📉 mais barato" if entry["diff"] < 0 else "📈 mais caro"
                st.caption(f"{trend} que na última busca ({fmt.money(entry['prev'])}, "
                           f"{entry['diff']:+.0f}%)")
        with right:
            st.markdown(f"## {fmt.money(offer['price'])}")
            st.caption("ida e volta, por pessoa" if offer.get("return") else "só ida, por pessoa")
            buy_button(origin, offer, f"{key}-best", primary=True)


def offer_row(origin, offer, key):
    with st.container(border=True):
        c1, c2, c3, c4 = st.columns([3, 2, 1.2, 1.2], vertical_alignment="center")
        c1.markdown(f"**{fmt.city(offer['dest'])}**  \n{fmt.trip(offer)}")
        c2.markdown(f"{fmt.airline(offer['airline'])}  \n{fmt.stops(offer['stops'])}")
        c3.markdown(f"**{fmt.money(offer['price'])}**")
        with c4:
            buy_button(origin, offer, key)


def all_offers_table(origin, results):
    df = pd.DataFrame([{
        "Destino": fmt.city(o["dest"]), "Ida": fmt.day(o["depart"]),
        "Volta": fmt.day(o["return"]) if o.get("return") else "—",
        "Dias": fmt.nights(o), "Companhia": fmt.airline(o["airline"]),
        "Escalas": fmt.stops(o["stops"]), "Preço (R$)": o["price"],
        "Comprar": fmt.booking_url(origin, o)} for o in results])
    st.dataframe(df, hide_index=True, width="stretch", column_config={
        "Preço (R$)": st.column_config.NumberColumn(format="R$ %.0f"),
        "Comprar": st.column_config.LinkColumn(display_text="Abrir ↗")})


def empty_state(res, key):
    p, near = res["params"], res.get("nearby") or []
    st.warning("😕 Não encontrei voos exatamente com esses filtros.")
    if not IS_MOCK:
        st.markdown("Os preços gratuitos vêm do que outros viajantes pesquisaram recentemente no "
                    "Aviasales, então datas pouco procuradas (sobretudo a mais de 2–3 meses) "
                    "costumam não ter preço guardado.")
    if near:
        st.markdown("##### 📅 Datas mais próximas com preço disponível")
        for i, o in enumerate(near):
            offer_row(p["origin"], o, f"{key}-near{i}")
    if len(p["dests"]) == 1:
        wanted = {"dest": p["dests"][0], "depart": p["depart"], "return": None}
        if p.get("stay"):
            back = date.fromisoformat(p["depart"]) + timedelta(days=int(p["stay"]))
            wanted["return"] = back.isoformat()
        st.link_button("Ver as datas exatas no Google Flights", fmt.booking_url(p["origin"], wanted),
                       icon=":material/open_in_new:", key=f"{key}-gf")
    st.caption("Dicas: aumente a flexibilidade de datas, aceite escalas ou tente outro mês ou "
               "outro destino da mesma região.")
    ref = min((o["price"] for o in near), default=3000)
    watch_box(p, int(ref // 100 * 100) or 100, key)


REPO_SECRETS = "https://github.com/thiago88sp/flight-agent/settings/secrets/actions"


def watch_box(params, suggested, key):
    """Caixa para transformar a busca num monitoramento com preço-alvo."""
    with st.expander("🔔 Monitorar esta busca e me avisar quando baixar"):
        with st.form(f"{key}-watch", border=False):
            c1, c2 = st.columns(2)
            target = c1.number_input("Avise quando custar até (R$)", 100, 100000,
                                     int(suggested), step=100, key=f"{key}-target")
            days = c2.number_input("Monitorar por (dias)", 1, 90, 30, key=f"{key}-days")
            if st.form_submit_button("Criar monitoramento", icon=":material/notifications:"):
                w = watches.new_watch(params, target, days)
                watches.add_watch(w)
                # recarrega para a barra lateral (já desenhada) mostrar o novo monitoramento
                st.session_state.flash = (
                    f"🔔 Monitorando **{w['label']}** até {fmt.day(w['until'])}: aviso no Telegram "
                    f"quando custar até **{fmt.money(target)}**. Veja em **Monitoramentos**, na "
                    "barra lateral, como ativar no GitHub.")
                st.rerun()


def render(res, key):
    for e in res.get("errors", []):
        st.error(f"⚠️ {e}")
    if res["empty"]:
        if not res.get("errors"):
            empty_state(res, key)
        return

    p, info, results = res["params"], res["info"], res["results"]
    origin, per_dest = p["origin"], info["per_dest"]
    multi = len(per_dest) > 1

    head = f"🎉 Achei **{len(results)} oferta{'s' if len(results) > 1 else ''}**"
    st.markdown(head + (f" em **{len(per_dest)} destinos**." if multi else "."))
    for a in info["alerts"]:
        st.success(f"🔔 {a}")

    best_card(origin, info["best"], per_dest[0], key)
    watch_box(p, int(info["best"]["price"] * 0.9 // 100 * 100) or 100, key)

    # Mais opções: com vários destinos, o melhor de cada um; senão, as próximas mais baratas
    others = [e["best"] for e in per_dest[1:6]] if multi else results[1:6]
    if others:
        st.markdown("##### " + ("Outros destinos" if multi else "Outras opções"))
        for i, o in enumerate(others):
            offer_row(origin, o, f"{key}-{i}")

    if multi and len(per_dest) >= 3:
        st.markdown("##### Menor preço por destino")
        chart = pd.DataFrame({"Destino": [fmt.city(e["dest"]) for e in per_dest],
                              "Preço (R$)": [e["best"]["price"] for e in per_dest]})
        st.bar_chart(chart, x="Destino", y="Preço (R$)", horizontal=True, sort="Preço (R$)")
    elif not multi:
        by_day = {}
        for o in results:
            by_day[o["depart"]] = min(by_day.get(o["depart"], o["price"]), o["price"])
        if len(by_day) >= 3:
            st.markdown("##### Menor preço por data de ida")
            st.bar_chart(pd.DataFrame({"Ida": [fmt.day(d) for d in sorted(by_day)],
                                       "Preço (R$)": [by_day[d] for d in sorted(by_day)]}),
                         x="Ida", y="Preço (R$)", sort=False)

    with st.expander(f"📋 Ver todas as {len(results)} ofertas"):
        all_offers_table(origin, results)

    if IS_MOCK:
        st.caption("⚠️ Preços **simulados** para teste. O botão abre o Google Flights com a mesma "
                   "rota e datas para você ver o preço real.")
    else:
        st.caption("Preços do cache do Aviasales (buscas recentes de outros viajantes). "
                   "O valor final é confirmado no site antes de pagar.")


# ---------------------------------------------------------------- barra lateral
def watch_panel():
    items = watches.load_watches()
    state = watches.load_state()
    with st.expander(f"🔔 Monitoramentos ({len(items)})"):
        if not items:
            st.caption("Nenhum ainda. Faça uma busca e use **Monitorar esta busca**.")
        for w in items:
            stt = state.get(w["id"], {})
            seen = f" · menor visto {fmt.money(stt['best'])}" if stt.get("best") else ""
            c1, c2 = st.columns([5, 1], vertical_alignment="center")
            c1.markdown(f"**{w['label']}**  \nalvo {fmt.money(w['target'])} · até "
                        f"{fmt.day(w['until'])}{seen}")
            if c2.button("", icon=":material/delete:", key=f"del-{w['id']}", help="Excluir"):
                watches.remove_watch(w["id"])
                st.rerun()
        st.markdown("**Telegram:** " + ("✅ configurado" if notify.telegram_enabled()
                                         else "⚠️ falta TELEGRAM_BOT_TOKEN/CHAT_ID no .env"))
        if notify.telegram_enabled() and st.button("Enviar mensagem de teste"):
            ok = notify.send_telegram("✅ Teste do Agente de Passagens: os alertas chegarão aqui.")
            (st.success if ok else st.error)("Enviado!" if ok else "Falhou; veja o terminal.")
        if items:
            st.markdown(f"**Ativar no GitHub:** copie o JSON abaixo para o secret `WATCHES` em "
                        f"[Settings → Secrets → Actions]({REPO_SECRETS}). Repita ao criar ou "
                        "excluir monitoramentos.")
            st.code(json.dumps(items, ensure_ascii=False, separators=(",", ":")), language="json",
                    wrap_lines=True)


with st.sidebar:
    st.header("🔎 Nova busca")
    mode = st.radio("Para onde?", ["Cidade", "Região"], horizontal=True)
    with st.form("form"):
        origin_txt = st.text_input("Saindo de", "São Paulo",
                                   help="Nome da cidade ou código do aeroporto. "
                                        "SAO = todos os aeroportos de São Paulo.")
        if mode == "Região":
            region = st.selectbox("Região", list(REGIONS), format_func=REGION_LABELS.get)
            dest_txt = ""
        else:
            region = None
            dest_txt = st.text_input("Indo para", "Lisboa",
                                     help="Uma ou mais cidades separadas por vírgula "
                                          "(ex.: Lisboa, Madri, CDG).")
        depart = st.date_input("Data de ida (aproximada)", date.today() + timedelta(days=60),
                               format="DD/MM/YYYY")
        stay = st.number_input("Dias de viagem (0 = só ida)", 0, 60, 10)
        flex = st.slider("Datas flexíveis (± dias)", 0, 7, 3 if mode != "Região" else 1)
        max_stops = st.selectbox("Escalas", list(STOPS))
        max_price = st.number_input("Quero pagar até (R$, 0 = sem limite)", 0, 100000, 0, step=100)
        go = st.form_submit_button("Buscar voos", type="primary", width="stretch",
                                   icon=":material/search:")

    with st.expander("ℹ️ Como funciona"):
        st.markdown(
            "- O formulário não usa IA (0 tokens). O chat usa o interpretador abaixo.\n"
            + ("- Consultas = destinos × datas (± flexibilidade).\n" if IS_MOCK else
               "- Uma consulta por destino e mês; a volta pode variar "
               f"±{config.stay_tolerance()} dias (STAY_TOLERANCE).\n")
            + f"- Limite por busca: {config.max_calls()} consultas (MAX_CALLS).\n"
            "- Cada busca guarda o menor preço por rota e avisa quando cai.")
    watch_panel()
    st.caption(f"Preços: {'⚠️ simulados' if IS_MOCK else '✅ reais (Aviasales)'}  \n"
               "Chat: " + ("regras locais" if PARSER == "rules" else f"✅ {PARSER}"))

# ---------------------------------------------------------------- conversa
st.title("✈️ Agente de Passagens")
st.caption("Diga para onde quer ir e quando. Eu comparo as datas e destinos e mostro onde comprar "
           "a passagem mais barata.")

if "history" not in st.session_state:
    st.session_state.history = []
if flash := st.session_state.pop("flash", None):
    st.success(flash)

example = None
if not st.session_state.history:
    with st.container(border=True):
        st.markdown("**👋 Comece por aqui.** Escreva no chat abaixo, use o formulário ao lado "
                    "ou toque em um exemplo:")
        for col, ex in zip(st.columns(len(EXAMPLES)), EXAMPLES):
            if col.button(ex, width="stretch"):
                example = ex

for i, msg in enumerate(st.session_state.history):
    with st.chat_message(msg["role"]):
        if msg.get("text"):
            st.markdown(msg["text"])
        if msg.get("note"):
            st.caption(msg["note"])
        if msg.get("result"):
            render(msg["result"], key=f"m{i}")


def handle(user_text, params_fn, info=None):
    hist = st.session_state.history
    key = f"m{len(hist) + 1}"  # índice que a resposta terá no histórico
    with st.chat_message("user"):
        st.markdown(user_text)
    with st.chat_message("assistant"):
        try:
            with st.spinner("Procurando as melhores tarifas..."):
                params = params_fn()
                summary = describe(params)
                res = run_search(params)
            note = f"interpretado por: {info['how']}" if info and info.get("how") else None
            st.markdown(summary)
            if note:
                st.caption(note)
            render(res, key)
            answer = {"role": "assistant", "text": summary, "note": note, "result": res}
        except Exception as e:  # mostra o erro sem derrubar o app
            text = f"Não consegui entender ou processar o pedido: {e}"
            st.error(text)
            answer = {"role": "assistant", "text": text}
    # pergunta e resposta entram juntas: uma busca interrompida não deixa pergunta órfã
    hist += [{"role": "user", "text": user_text}, answer]


if go:
    dests = ",".join(fmt.to_code(d) for d in dest_txt.split(",") if d.strip())
    origin = fmt.to_code(origin_txt)
    raw = {"origin": origin, "dest": dests, "region": region, "depart": depart.isoformat(),
           "stay": int(stay) or None, "flex": int(flex), "max_stops": STOPS[max_stops],
           "max_price": float(max_price) or None}
    label = REGION_LABELS[region] if region else dest_txt
    handle(f"{origin_txt} → {label}, ida {depart:%d/%m/%Y}", lambda: fa.normalize_params(raw))

prompt = st.chat_input("Para onde você quer ir? Ex.: Lisboa em dezembro, 10 dias, até R$ 4000")
prompt = prompt or example
if prompt:
    chat_info = {}

    def _parse():
        params, chat_info["how"] = fa.parse_request(prompt)
        return params

    handle(prompt, _parse, chat_info)
