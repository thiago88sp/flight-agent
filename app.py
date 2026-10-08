"""
Web app (chat + form) for the flight deal agent.

Run:  streamlit run app.py

The sidebar form uses no AI. The chat uses the parser set in LLM_PROVIDER
(default: local rules, free). Search, ranking and alerts are plain Python.
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

st.set_page_config(page_title="Flight Deal Agent", page_icon="✈️", layout="wide")

PARSER = fa.llm_provider()
IS_MOCK = providers.using_mock()

EXAMPLES = [
    "São Paulo to Lisbon around Dec 10, 10 days",
    "GRU to any city in Europe in March, 12 days, up to R$ 5000",
    "Rio to Buenos Aires on Nov 15, 5 days, nonstop",
]
STOPS = {"Any": None, "Nonstop only": 0, "Up to 1 stop": 1, "Up to 2 stops": 2}
REPO_SECRETS = "https://github.com/thiago88sp/flight-agent/settings/secrets/actions"


@st.cache_resource
def provider():
    return providers.get_provider()


def run_search(params):
    """Search + analysis; returns a dict ready to render."""
    prov = provider()
    misses = []
    results = fa.search_grid(prov, params, misses=misses)
    errors = prov.pop_errors()
    if not results:
        return {"params": params, "empty": True, "errors": errors,
                "nearby": nearby(params, misses)}
    return {"params": params, "empty": False, "errors": errors,
            "info": fa.analyze(params, results), "results": results}


# ---------------------------------------------------------------- text
def dest_label(p):
    if p.get("region") in REGION_LABELS and len(p["dests"]) > 1:
        return f"{REGION_LABELS[p['region']]} ({len(p['dests'])} destinations)"
    if len(p["dests"]) <= 4:
        return ", ".join(fmt.city(d) for d in p["dests"])
    return f"{len(p['dests'])} destinations"


def describe(params):
    """Short sentence confirming what was understood from the request."""
    text = f"Searching flights from **{fmt.city(params['origin'])}** to **{dest_label(params)}**, "
    if params.get("month") and not IS_MOCK:
        text += f"departing **any day in {fmt.month(params['month'])}**"
    else:
        text += f"departing around **{fmt.day(params['depart'])}**"
        if params.get("flex"):
            text += f" (± {params['flex']} days)"
    text += f", **{params['stay']}-day** trip" if params.get("stay") else ", **one-way**"
    if params.get("max_stops") is not None:
        text += ", " + ("nonstop only" if params["max_stops"] == 0
                        else f"up to {fmt.stops(params['max_stops'])}")
    if params.get("max_price"):
        text += f", up to {fmt.money(params['max_price'])}"
    return text + "."


def buy_button(origin, offer, key, primary=False):
    st.link_button(f"Book on {fmt.booking_site(offer)}" if primary else "Book",
                   fmt.booking_url(origin, offer), icon=":material/open_in_new:",
                   type="primary" if primary else "secondary", width="stretch", key=key)


def best_card(origin, offer, entry, key):
    with st.container(border=True):
        st.caption("🏆 CHEAPEST")
        left, right = st.columns([3, 1.4], vertical_alignment="center")
        with left:
            st.markdown(f"### {fmt.city(offer['dest'])}")
            st.markdown(f"📅 {fmt.trip(offer)}  \n"
                        f"🛫 {fmt.airline(offer['airline'])} · {fmt.stops(offer['stops'])}")
            if entry["prev"] is not None:
                trend = "📉 cheaper" if entry["diff"] < 0 else "📈 more expensive"
                st.caption(f"{trend} than your last search ({fmt.money(entry['prev'])}, "
                           f"{entry['diff']:+.0f}%)")
        with right:
            st.markdown(f"## {fmt.money(offer['price'])}")
            st.caption("round trip, per person" if offer.get("return") else "one-way, per person")
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
        "Destination": fmt.city(o["dest"]), "Out": fmt.day(o["depart"]),
        "Back": fmt.day(o["return"]) if o.get("return") else "—",
        "Days": fmt.nights(o), "Airline": fmt.airline(o["airline"]),
        "Stops": fmt.stops(o["stops"]), "Price (R$)": o["price"],
        "Book": fmt.booking_url(origin, o)} for o in results])
    st.dataframe(df, hide_index=True, width="stretch", column_config={
        "Price (R$)": st.column_config.NumberColumn(format="R$ %.0f"),
        "Book": st.column_config.LinkColumn(display_text="Open ↗")})


def empty_state(res, key):
    p, near = res["params"], res.get("nearby") or []
    st.warning("😕 I couldn't find flights matching exactly these filters.")
    if not IS_MOCK:
        st.markdown("The free prices come from what other travelers searched recently on "
                    "Aviasales, so rarely searched dates (especially more than 2–3 months ahead) "
                    "often have no cached price.")
    if near:
        st.markdown("##### 📅 Closest dates with a price available")
        for i, o in enumerate(near):
            offer_row(p["origin"], o, f"{key}-near{i}")
    if len(p["dests"]) == 1:
        wanted = {"dest": p["dests"][0], "depart": p["depart"], "return": None}
        if p.get("stay"):
            back = date.fromisoformat(p["depart"]) + timedelta(days=int(p["stay"]))
            wanted["return"] = back.isoformat()
        st.link_button("Check the exact dates on Google Flights",
                       fmt.booking_url(p["origin"], wanted), icon=":material/open_in_new:",
                       key=f"{key}-gf")
    st.caption("Tips: widen the date flexibility, allow stops, or try another month or another "
               "destination in the same region.")
    ref = min((o["price"] for o in near), default=3000)
    watch_box(p, int(ref // 100 * 100) or 100, key)


def watch_box(params, suggested, key):
    """Box that turns the search into a price watch with a target."""
    with st.expander("🔔 Watch this search and alert me when it drops"):
        with st.form(f"{key}-watch", border=False):
            c1, c2 = st.columns(2)
            target = c1.number_input("Alert me at or below (R$)", 100, 100000,
                                     int(suggested), step=100, key=f"{key}-target")
            days = c2.number_input("Watch for (days)", 1, 90, 30, key=f"{key}-days")
            if st.form_submit_button("Create watch", icon=":material/notifications:"):
                w = watches.new_watch(params, target, days)
                watches.add_watch(w)
                # rerun so the sidebar (already drawn) shows the new watch
                st.session_state.flash = (
                    f"🔔 Watching **{w['label']}** until {fmt.day(w['until'])}: Telegram alert at "
                    f"or below **{fmt.money(target)}**. See **Price watches** in the sidebar for "
                    "how to enable it on GitHub.")
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

    head = f"🎉 Found **{len(results)} offer{'s' if len(results) > 1 else ''}**"
    st.markdown(head + (f" across **{len(per_dest)} destinations**." if multi else "."))
    for a in info["alerts"]:
        st.success(f"🔔 {a}")

    best_card(origin, info["best"], per_dest[0], key)
    watch_box(p, int(info["best"]["price"] * 0.9 // 100 * 100) or 100, key)

    # More options: with several destinations, the best of each; otherwise the next cheapest
    others = [e["best"] for e in per_dest[1:6]] if multi else results[1:6]
    if others:
        st.markdown("##### " + ("Other destinations" if multi else "Other options"))
        for i, o in enumerate(others):
            offer_row(origin, o, f"{key}-{i}")

    if multi and len(per_dest) >= 3:
        st.markdown("##### Lowest price per destination")
        chart = pd.DataFrame({"Destination": [fmt.city(e["dest"]) for e in per_dest],
                              "Price (R$)": [e["best"]["price"] for e in per_dest]})
        st.bar_chart(chart, x="Destination", y="Price (R$)", horizontal=True, sort="Price (R$)")
    elif not multi:
        by_day = {}
        for o in results:
            by_day[o["depart"]] = min(by_day.get(o["depart"], o["price"]), o["price"])
        if len(by_day) >= 3:
            st.markdown("##### Lowest price per departure date")
            st.bar_chart(pd.DataFrame({"Out": [fmt.day(d) for d in sorted(by_day)],
                                       "Price (R$)": [by_day[d] for d in sorted(by_day)]}),
                         x="Out", y="Price (R$)", sort=False)

    with st.expander(f"📋 See all {len(results)} offers"):
        all_offers_table(origin, results)

    if IS_MOCK:
        st.caption("⚠️ **Simulated** prices for testing. The button opens Google Flights with the "
                   "same route and dates so you can see the real price.")
    else:
        st.caption("Prices from the Aviasales cache (recent searches by other travelers). "
                   "The final price is confirmed on the seller's site before you pay.")


# ---------------------------------------------------------------- sidebar
def watch_panel():
    items = watches.load_watches()
    state = watches.load_state()
    with st.expander(f"🔔 Price watches ({len(items)})"):
        if not items:
            st.caption("None yet. Run a search and use **Watch this search**.")
        for w in items:
            stt = state.get(w["id"], {})
            seen = f" · lowest seen {fmt.money(stt['best'])}" if stt.get("best") else ""
            c1, c2 = st.columns([5, 1], vertical_alignment="center")
            c1.markdown(f"**{w['label']}**  \ntarget {fmt.money(w['target'])} · until "
                        f"{fmt.day(w['until'])}{seen}")
            if c2.button("", icon=":material/delete:", key=f"del-{w['id']}", help="Delete"):
                watches.remove_watch(w["id"])
                st.rerun()
        st.markdown("**Telegram:** " + ("✅ configured" if notify.telegram_enabled()
                                         else "⚠️ set TELEGRAM_BOT_TOKEN/CHAT_ID in .env"))
        if notify.telegram_enabled() and st.button("Send a test message"):
            ok = notify.send_telegram("✅ Flight Deal Agent test: your alerts will arrive here.")
            (st.success if ok else st.error)("Sent!" if ok else "Failed; check the terminal.")
        if items:
            st.markdown(f"**Enable on GitHub:** copy the JSON below into the `WATCHES` secret at "
                        f"[Settings → Secrets → Actions]({REPO_SECRETS}). Repeat whenever you "
                        "create or delete a watch.")
            st.code(json.dumps(items, ensure_ascii=False, separators=(",", ":")), language="json",
                    wrap_lines=True)


with st.sidebar:
    st.header("🔎 New search")
    mode = st.radio("Where to?", ["City", "Region"], horizontal=True)
    with st.form("form"):
        origin_txt = st.text_input("From", "São Paulo",
                                   help="City name or airport code. "
                                        "SAO = every São Paulo airport.")
        if mode == "Region":
            region = st.selectbox("Region", list(REGIONS), format_func=REGION_LABELS.get)
            dest_txt = ""
        else:
            region = None
            dest_txt = st.text_input("To", "Lisbon",
                                     help="One or more cities separated by commas "
                                          "(e.g. Lisbon, Madrid, CDG).")
        depart = st.date_input("Departure date (approximate)", date.today() + timedelta(days=60),
                               format="YYYY-MM-DD")
        stay = st.number_input("Trip length in days (0 = one-way)", 0, 60, 10)
        flex = st.slider("Flexible dates (± days)", 0, 7, 3 if mode != "Region" else 1)
        max_stops = st.selectbox("Stops", list(STOPS))
        max_price = st.number_input("Budget (R$, 0 = no limit)", 0, 100000, 0, step=100)
        go = st.form_submit_button("Search flights", type="primary", width="stretch",
                                   icon=":material/search:")

    with st.expander("ℹ️ How it works"):
        st.markdown(
            "- The form uses no AI (0 tokens). The chat uses the parser shown below.\n"
            + ("- Queries = destinations × dates (± flexibility).\n" if IS_MOCK else
               "- One query per destination and month; the return may vary by "
               f"±{config.stay_tolerance()} days (STAY_TOLERANCE).\n")
            + f"- Limit per search: {config.max_calls()} queries (MAX_CALLS).\n"
            "- Every search stores the lowest price per route and tells you when it drops.")
    watch_panel()
    st.caption(f"Prices: {'⚠️ simulated' if IS_MOCK else '✅ real (Aviasales)'}  \n"
               "Chat: " + ("local rules" if PARSER == "rules" else f"✅ {PARSER}"))

# ---------------------------------------------------------------- conversation
st.title("✈️ Flight Deal Agent")
st.caption("Tell me where and when you want to go. I compare dates and destinations and show "
           "you where to book the cheapest ticket. English or Portuguese both work.")

if "history" not in st.session_state:
    st.session_state.history = []
if flash := st.session_state.pop("flash", None):
    st.success(flash)

example = None
if not st.session_state.history:
    with st.container(border=True):
        st.markdown("**👋 Start here.** Type in the chat below, use the form on the left, "
                    "or tap an example:")
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
    key = f"m{len(hist) + 1}"  # index the answer will have in the history
    with st.chat_message("user"):
        st.markdown(user_text)
    with st.chat_message("assistant"):
        try:
            with st.spinner("Looking for the best fares..."):
                params = params_fn()
                summary = describe(params)
                res = run_search(params)
            note = f"parsed by: {info['how']}" if info and info.get("how") else None
            st.markdown(summary)
            if note:
                st.caption(note)
            render(res, key)
            answer = {"role": "assistant", "text": summary, "note": note, "result": res}
        except Exception as e:  # show the error without crashing the app
            text = f"I couldn't understand or process that request: {e}"
            st.error(text)
            answer = {"role": "assistant", "text": text}
    # question and answer are stored together: an interrupted search leaves no orphan question
    hist += [{"role": "user", "text": user_text}, answer]


if go:
    dests = ",".join(fmt.to_code(d) for d in dest_txt.split(",") if d.strip())
    origin = fmt.to_code(origin_txt)
    raw = {"origin": origin, "dest": dests, "region": region, "depart": depart.isoformat(),
           "stay": int(stay) or None, "flex": int(flex), "max_stops": STOPS[max_stops],
           "max_price": float(max_price) or None}
    label = REGION_LABELS[region] if region else dest_txt
    handle(f"{origin_txt} → {label}, departing {fmt.day(depart.isoformat())}",
           lambda: fa.normalize_params(raw))

prompt = st.chat_input("Where do you want to go? e.g. Lisbon in December, 10 days, up to R$ 4000")
prompt = prompt or example
if prompt:
    chat_info = {}

    def _parse():
        params, chat_info["how"] = fa.parse_request(prompt)
        return params

    handle(prompt, _parse, chat_info)
