# Flight Deal Agent ✈️

An agent that takes a trip request (free text or a form), scans dates and destinations, ranks the
offers, compares them with your price history, and alerts you on Telegram when a fare hits your
target. **Built to spend as little AI as possible**: search, ranking and alerts are plain Python;
the chat only needs AI to understand the sentence, and even that is optional (a free, offline
rules parser is included).

> **New here?** Follow the step-by-step **[setup guide](docs/SETUP.md)**. It walks you through
> creating every account, key and bot this project uses, from zero to Telegram alerts.

## What it does

- **Chat and form** web app (Streamlit): `streamlit run app.py`
- **Command line**, ready for cron: `python -m flight_agent ...`
- **Domestic (Brazil) and international flights**
- **One destination, a list, or a whole region** ("any city in Europe")
- **Flexible dates** (± days), trip length (round trip or one-way), stops filter and budget
- **Book button** on every offer: opens the itinerary on Aviasales (real prices) or the same search
  on Google Flights (simulated prices)
- Accepts **city names** ("São Paulo", "Lisbon"), **Brazilian states** ("Santa Catarina") and IATA codes
- Understands requests in **English and Portuguese**
- **Price watches**: target price + time window, checked every 4 h on GitHub Actions, Telegram alert
  with a booking link
- **History** of the lowest price per route, with drop and under-budget alerts
- **Simulated** prices by default; **real** prices via the Travelpayouts / Aviasales Data API (free)

## Quick start

```bash
git clone https://github.com/thiago88sp/flight-agent.git && cd flight-agent
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # optional: add your keys (see docs/SETUP.md)
streamlit run app.py        # opens http://localhost:8501
```

Without any key the app works with **simulated prices** (it says "Demo mode") and the **local
rules parser**, so you can try everything before creating accounts.

The web app is written for **travelers**, not developers: technical details stay hidden. Set
`DEV_MODE=true` in `.env` to see them (parser used, limits, raw errors, the JSON for GitHub).

> On recent Debian/Ubuntu the global `pip` is blocked (PEP 668), hence the `venv`.
> On WSL, if the project lives under `/mnt/c` (e.g. OneDrive), create the venv on the Linux disk,
> which is much faster: `python3 -m venv ~/.venvs/flight-agent && source ~/.venvs/flight-agent/bin/activate`.

## Usage

### Web app

```bash
streamlit run app.py
```

Type in the chat, in English or Portuguese:

- `GRU to Lisbon around Dec 10, 10 days, up to R$ 4000`
- `GRU to any city in Europe in March, 10 days, nonstop`
- `to Paris, London or Rome from CNF on Jan 5, a week`
- `Rio de Janeiro -> Miami January 15th, 12 days, ±3 days, budget of 5k`
- `São Paulo to Santa Catarina on Jan 8, 7 days` (domestic; the state maps to Florianópolis)
- `GRU para Lisboa por volta de 10/12, 10 dias, até R$ 4000`

> Numeric dates are **day/month**: `10/12` is **December 10**. To avoid ambiguity, write the month
> name (`Dec 10`) or use ISO format (`2026-12-10`).

In the sidebar form, pick **City** (name or code; several separated by commas) or **Region**.
See the [glossary](#glossary-origins-and-destinations) for what you can type.

### Command line

```bash
python -m flight_agent "GRU to any city in Europe on Dec 10, 10 days, up to R$ 3000"
python -m flight_agent --origin GRU --dest LIS,MAD --depart 2026-12-10 --stay 10 --flex 3
python -m flight_agent --origin GRU --region europe --depart 2026-12-10 --stay 10 --max-calls 120
```

Regions: `europe`, `south_america`, `usa`, `caribbean`, `brazil_northeast`
(lists in `flight_agent/geo.py`; edit freely). The older Portuguese keys (`europa`, `eua`...) still work.

### Run it every day (unattended)

Use direct parameters (0 AI tokens) and call the venv's Python, no activation needed:

```cron
0 7 * * * cd "/path/to/flight-agent" && .venv/bin/python -m flight_agent --origin GRU --region europe --depart 2026-12-10 --stay 10 --flex 1 --max-price 3500
```

## Price watches (Telegram alerts)

Turn a search into a **price watch**: the agent re-runs it every 4 hours and sends you a Telegram
message, with a booking button, when the price is **at or below your target**.

- It alerts the first time the target is hit and then **only if the price drops further** (no spam).
- When the window ends (30 days by default), it sends a summary with the lowest price seen and stops.
- It **does not buy tickets by itself**, on purpose: Aviasales only compares prices (the airline or
  agency is the seller), a cached price can be outdated, and a wrong purchase is often
  non-refundable. The alert carries the link: one tap and you check and book.

How to set it up, step by step: **[docs/SETUP.md](docs/SETUP.md)** (sections 4, 6 and 7). In short:

1. Create a Telegram bot with **@BotFather** and put `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` in `.env`.
2. In the web app, after a search, open **🔔 Watch this search**, set the target and the window.
3. On GitHub, add the secrets `TRAVELPAYOUTS_TOKEN`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` and
   `WATCHES` (`python -m flight_agent.watch --export`, or the JSON shown under **🔔 Price watches**
   when `DEV_MODE=true`), then run **Actions → price watches**.

Useful commands:

```bash
python -m flight_agent.watch --telegram-chat-id   # find your chat id
python -m flight_agent.watch --test               # send a test message
python -m flight_agent.watch                      # check every watch now
python -m flight_agent.watch --list               # watches and their state
python -m flight_agent.watch --export             # JSON for the WATCHES secret
```

- Watches live in a **secret** (the repository is public and they reveal your travel plans); the
  state (lowest price seen, last alert) lives in the **Actions cache**, not in a file in the repo.
- When you create or delete watches in the web app, update the `WATCHES` secret with the new JSON.
- GitHub **disables schedules** on public repositories with no commits for 60 days; if that
  happens, re-enable the workflow under Actions.

Local alternative (only runs while the PC/WSL is on):

```cron
17 */4 * * * cd "/path/to/flight-agent" && ~/.venvs/flight-agent/bin/python -m flight_agent.watch >> watch.log 2>&1
```

## Glossary: origins and destinations

Both **domestic (Brazil) and international** routes work. In **From** and **To** you can type a
**city name** (case and accents don't matter: `São Paulo`, `sao paulo`, `SAO PAULO`), a
**Brazilian state** or an **IATA code**.

- **City name**: accepted in the chat and in the form for the cities in the tables below, in
  English or Portuguese. Each name maps to the main airport shown.
- **Airport code** (3 letters, e.g. `CGH`): accepted everywhere, for any airport in the world,
  even outside the tables.
- **Brazilian state** (e.g. `Santa Catarina`, `Bahia`): becomes the state's main airport, see the
  [states table](#brazilian-states).
- **City code** (e.g. `SAO`, `LON`): covers every airport in the city at once. With real prices
  (Travelpayouts) it usually returns more offers, because it includes flights from or to any of them.
- With Gemini enabled in the chat, cities outside the tables are usually understood too. With the
  local rules, use the code.
- To look up a code: search "IATA code" + city, or use the
  [IATA code search](https://www.iata.org/en/publications/directories/code-search/).

### South America — Brazil

| Accepted names | Airport used | City code | Other airports in the city |
|---|---|---|---|
| São Paulo, Guarulhos | `GRU` (Guarulhos) | `SAO` | `CGH` Congonhas, `VCP` Viracopos |
| Congonhas | `CGH` | `SAO` | |
| Campinas | `VCP` (Viracopos) | | |
| Rio de Janeiro, Rio | `GIG` (Galeão) | `RIO` | `SDU` Santos Dumont |
| Brasília | `BSB` | | |
| Belo Horizonte | `CNF` (Confins) | `BHZ` | `PLU` Pampulha |
| Salvador | `SSA` | | |
| Recife | `REC` | | |
| Fortaleza | `FOR` | | |
| Natal | `NAT` | | |
| Maceió | `MCZ` | | |
| João Pessoa | `JPA` | | |
| Porto Alegre | `POA` | | |
| Curitiba | `CWB` | | |
| Florianópolis | `FLN` | | |
| Manaus | `MAO` | | |
| Belém | `BEL` | | |
| Goiânia | `GYN` | | |
| São Luís | `SLZ` | | |
| Cuiabá | `CGB` | | |
| Campo Grande | `CGR` | | |
| Teresina | `THE` | | |
| Aracaju | `AJU` | | |
| Vitória | `VIX` | | |
| Palmas | `PMW` | | |
| Porto Velho | `PVH` | | |
| Boa Vista | `BVB` | | |
| Macapá | `MCP` | | |
| Rio Branco | `RBR` | | |

### Brazilian states

Typing a state searches its main airport:

| State | Airport used | State | Airport used |
|---|---|---|---|
| Acre | `RBR` Rio Branco | Paraíba | `JPA` João Pessoa |
| Alagoas | `MCZ` Maceió | Paraná | `CWB` Curitiba |
| Amapá | `MCP` Macapá | Pernambuco | `REC` Recife |
| Amazonas | `MAO` Manaus | Piauí | `THE` Teresina |
| Bahia | `SSA` Salvador | Rio de Janeiro | `GIG` Rio de Janeiro |
| Ceará | `FOR` Fortaleza | Rio Grande do Norte | `NAT` Natal |
| Distrito Federal | `BSB` Brasília | Rio Grande do Sul | `POA` Porto Alegre |
| Espírito Santo | `VIX` Vitória | Rondônia | `PVH` Porto Velho |
| Goiás | `GYN` Goiânia | Roraima | `BVB` Boa Vista |
| Maranhão | `SLZ` São Luís | Santa Catarina | `FLN` Florianópolis |
| Mato Grosso | `CGB` Cuiabá | São Paulo | `GRU` Guarulhos |
| Mato Grosso do Sul | `CGR` Campo Grande | Sergipe | `AJU` Aracaju |
| Minas Gerais, Minas | `CNF` Belo Horizonte | Tocantins | `PMW` Palmas |
| Pará | `BEL` Belém (form only*) | | |

\* In the chat, "para" is also the Portuguese word for "to" ("GRU **para** Lisboa"), so for Pará
type `Belém` or `BEL` there. The form accepts `Pará`.

### South America — other countries

| Accepted names | Airport used | City code | Other airports in the city |
|---|---|---|---|
| Buenos Aires (Argentina) | `EZE` (Ezeiza) | `BUE` | `AEP` Aeroparque |
| Santiago (Chile) | `SCL` | | |
| Lima (Peru) | `LIM` | | |
| Bogotá (Colombia) | `BOG` | | |
| Montevideo, Montevidéu (Uruguay) | `MVD` | | |

### North America

| Accepted names | Airport used | City code | Other airports in the city |
|---|---|---|---|
| New York, Nova York | `JFK` | `NYC` | `EWR` Newark, `LGA` LaGuardia |
| Miami | `MIA` | | `FLL` Fort Lauderdale (nearby) |
| Orlando | `MCO` | `ORL` | |
| Los Angeles | `LAX` | | |

### Central America and the Caribbean

| Accepted names | Airport used | City code | Other airports in the city |
|---|---|---|---|
| Cancún (Mexico) | `CUN` | | |
| Punta Cana (Dominican Republic) | `PUJ` | | |
| Panama City, Panamá | `PTY` | | |

### Europe

| Accepted names | Airport used | City code | Other airports in the city |
|---|---|---|---|
| Lisbon, Lisboa | `LIS` | | |
| Porto, Oporto | `OPO` | | |
| Madrid, Madri | `MAD` | | |
| Barcelona | `BCN` | | |
| Paris | `CDG` (Charles de Gaulle) | `PAR` | `ORY` Orly |
| London, Londres | `LHR` (Heathrow) | `LON` | `LGW` Gatwick, `STN` Stansted |
| Rome, Roma | `FCO` (Fiumicino) | `ROM` | `CIA` Ciampino |
| Milan, Milão | `MXP` (Malpensa) | `MIL` | `LIN` Linate, `BGY` Bergamo |
| Amsterdam, Amsterdã | `AMS` | | |
| Frankfurt | `FRA` | | |
| Zurich, Zurique | `ZRH` | | |

### Asia and the Middle East

| Accepted names | Airport used | City code | Other airports in the city |
|---|---|---|---|
| Dubai (UAE) | `DXB` | | |
| Tokyo, Tóquio (Japan) | `NRT` (Narita) | `TYO` | `HND` Haneda |

### Africa and Oceania

No city names are preloaded. Use the code, e.g. `JNB` (Johannesburg), `CPT` (Cape Town),
`CMN` (Casablanca), `SYD` (Sydney), `AKL` (Auckland).

### Regions (destination only)

In the chat ("any city in Europe") or in the form, option **Region**. The search covers every
destination in the list:

| Region | How to write it in the chat | Destinations searched |
|---|---|---|
| Europe | `Europe`, `Europa` | LIS, MAD, BCN, CDG, LHR, FCO, AMS, FRA, MXP, ZRH, OPO |
| South America | `South America`, `Latin America`, `América do Sul` | EZE, SCL, LIM, BOG, MVD |
| United States | `United States`, `USA`, `EUA` | MIA, MCO, JFK, LAX |
| Caribbean / Central America | `Caribbean`, `Central America`, `Caribe` | CUN, PUJ, PTY |
| Northeast Brazil | `Northeast Brazil`, `Nordeste` | REC, SSA, FOR, NAT, MCZ, JPA |

To add cities, states or regions, edit `CITIES`, `STATES` and `REGIONS` in
[flight_agent/geo.py](flight_agent/geo.py) (and the display name in `CITY_NAMES`, in
[flight_agent/present.py](flight_agent/present.py)).

## AI cost and query limits

| Parser (`LLM_PROVIDER`) | Cost | How to enable |
|---|---|---|
| `rules` (default) | free, offline, no account | nothing to do |
| `gemini` | free with limits | key from aistudio.google.com → `GEMINI_API_KEY` ([setup](docs/SETUP.md#3-gemini-api-key-optional-smarter-chat)) |
| `ollama` | free, offline | `OLLAMA_MODEL=qwen2.5:3b` (with Ollama installed) |
| `anthropic` | paid per token | `ANTHROPIC_API_KEY` + `pip install anthropic` |

- Consumer subscriptions (Gemini, Claude plans) do **not** include an API key; the free Gemini key
  is created separately in Google AI Studio.
- On Gemini's free tier Google may use the content you send to improve its products (here, only
  the search sentence is sent).
- If the LLM fails (network, quota, bad answer), the app falls back to the local rules automatically.
- **Queries**: with simulated prices, destinations × (2×flex+1) dates; with real prices, one per
  destination and month. The default limit is `MAX_CALLS=80`; above it the search is refused with
  a message.

## Real prices (Travelpayouts)

> Amadeus' free Self-Service tier was shut down on July 17; it now serves companies under contract
> only. That is why this project uses the free Aviasales Data API.

How to get the token, step by step: [docs/SETUP.md](docs/SETUP.md#2-travelpayouts-token-real-prices).

Prices come from a **cache** of recent searches made on Aviasales, not a live query. Rarely searched
routes and dates may return nothing, and a price may be a few days old. That is enough to follow
trends and price drops; confirm the price before buying.

Because the cache rarely holds the exact pair of dates requested, the app makes **one query per
destination and month** and filters locally: departure inside the window (± flexibility) and trip
length of `days ± STAY_TOLERANCE` (default 3). So the return date shown may differ by a few days
from the request. With simulated prices the search is still a grid (one query per date).

Month-only requests ("Europe in March") accept any day of the month. When nothing fits, the app
shows the **closest dates that have a price** (for up to 3 destinations it looks at any date on the
route) and a button to check the exact dates on Google Flights. In practice the free cache has
little data more than 2–3 months ahead.

## Project layout

```
app.py                  Streamlit web app (chat + form)
flight_agent/
  parsing.py            free text -> parameters (rules EN/PT, Gemini, Ollama, Anthropic) and validation
  search.py             dates × destinations search, ranking, analysis and alerts
  providers.py          MockProvider (simulated) and TravelpayoutsProvider (real)
  present.py            friendly text: cities, airlines, dates, prices and booking link
  geo.py                known cities and regions
  history.py            price history (JSON Lines)
  notify.py             alerts: screen and Telegram
  watch.py              price watches: periodic checks and alerts
  config.py             environment variables / .env
  cli.py, __main__.py   command line
docs/SETUP.md           step-by-step setup of every account, key and bot
tests/                  pytest (parser, search, history, watches, web app)
.github/workflows/      tests.yml: pytest on every push · watch.yml: price watches every 4 h
```

## Tests

```bash
pip install -r requirements-dev.txt
pytest -q
```

They cover the rules parser (English and Portuguese, regions and lists), grid and month search,
query limits, alerts, LLM fallback, price watches and the web app (via `streamlit.testing`).
There are **no automated tests** for the real calls to Travelpayouts, Telegram, Gemini and
Ollama (they depend on network and credentials).

## Known limitations

- Simulated prices are fake; they validate the flow, not purchase decisions.
- The rules parser understands the "origin to destination, date, days, budget" shape; very free-form
  sentences work better with Gemini/Ollama. Cities not listed in `geo.py` need their IATA code.
- No "anywhere in the world" search: the destination set comes from the regions in `geo.py`.
- Prices are shown in Brazilian reais (BRL).
- The `WATCHES` secret on GitHub is updated by hand (copy and paste the JSON from the web app).

## Suggested next steps

- Create/delete watches from Telegram itself (bot commands).
- History in SQLite and a price-over-time chart per route.
- More providers (`search(...)` or `search_month(...)` interface, see `providers.py`).
