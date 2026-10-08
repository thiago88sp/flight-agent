"""Free-text request -> search parameters.

Parsers (LLM_PROVIDER): rules (default, free, offline) | gemini | ollama | anthropic.
If an LLM fails, it falls back to the rules automatically. The rules understand English and
Portuguese; numeric dates are day/month (10/12 = December 10).

Normalized parameters:
  origin (IATA), dests (IATA list), dest (IATA if only one, else None), region (key or None),
  depart (YYYY-MM-DD), stay (days or None), flex (± days), month ("YYYY-MM" or None),
  max_stops (int/None), max_price (BRL/None)
"""
import json
import os
import re
import sys
import unicodedata
from datetime import date, timedelta

from . import config
from .geo import CITIES, REGION_ALIASES, REGION_PATTERNS, REGIONS

MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6, "july": 7,
    "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7, "aug": 8, "sep": 9, "sept": 9,
    "oct": 10, "nov": 11, "dec": 12,
    "janeiro": 1, "fevereiro": 2, "marco": 3, "abril": 4, "maio": 5, "junho": 6, "julho": 7,
    "agosto": 8, "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12,
}
_MONTH_RX = "|".join(sorted(MONTHS, key=len, reverse=True))
# Numbers written as words, before a unit ("two weeks", "one stop", "duas semanas", "uma escala")
NUMBER_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
                "eight": 8, "nine": 9, "ten": 10, "um": 1, "uma": 1, "dois": 2, "duas": 2,
                "tres": 3, "quatro": 4, "cinco": 5, "seis": 6, "sete": 7, "oito": 8, "nove": 9,
                "dez": 10}
_UNITS = r"(?=\s+(?:weeks?|days?|nights?|stops?|semanas?|dias?|noites?|escalas?)\b)"
# Uppercase 3-letter words that are not airport codes
_IATA_STOP = {"ATE", "DIA", "MAX", "MIN", "IDA", "RIO", "EUA", "USA", "THE", "AND", "ANY",
              "ONE", "TWO", "DAY", "BRL", "USD"}

PARSE_PROMPT = """Extract the flight search parameters. Today is {today}.
The request may be in English or Portuguese; numeric dates like 10/12 are day/month.
Reply ONLY with a JSON object with the keys:
origin (IATA), dest (IATA or null), region (one of {regions}, or null; use it when the request is "any city in <region>"),
depart (YYYY-MM-DD), stay (trip length in days, int or null), flex (± days, int, default 0),
month ("YYYY-MM" when the request names only a month, no day — e.g. "in March"; then depart = the 15th
of that month; otherwise null), max_stops (int or null), max_price (number in BRL or null).

Request: {text}"""

HINT = ("Try something like: 'São Paulo to Lisbon on Dec 10, 10 days, up to R$ 4000' or "
        "'GRU to any city in Europe in March, 10 days'. "
        "Regions: Europe, South America, USA, Caribbean, Northeast Brazil.")


# ------------------------------------------------------------------ LLMs (optional)
def _json_from(raw):
    raw = raw.strip()
    return json.loads(raw[raw.find("{"): raw.rfind("}") + 1])


def _prompt(text):
    return PARSE_PROMPT.format(today=date.today().isoformat(), text=text,
                               regions=", ".join(REGIONS))


def parse_gemini(text):
    """Gemini API over REST (free key from Google AI Studio, no SDK)."""
    import requests
    resp = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{config.GEMINI_MODEL}:generateContent",
        headers={"x-goog-api-key": os.environ["GEMINI_API_KEY"]},
        json={"contents": [{"parts": [{"text": _prompt(text)}]}],
              "generationConfig": {"responseMimeType": "application/json",
                                   "maxOutputTokens": 400, "temperature": 0}},
        timeout=30,
    )
    resp.raise_for_status()
    return _json_from(resp.json()["candidates"][0]["content"]["parts"][0]["text"])


def parse_ollama(text):
    """Local model via Ollama: free, offline, no key."""
    import requests
    resp = requests.post(
        f"{config.OLLAMA_URL}/api/chat",
        json={"model": config.OLLAMA_MODEL, "stream": False, "format": "json",
              "options": {"temperature": 0},
              "messages": [{"role": "user", "content": _prompt(text)}]},
        timeout=120,
    )
    resp.raise_for_status()
    return _json_from(resp.json()["message"]["content"])


def parse_anthropic(text):
    import anthropic  # optional: pip install anthropic
    resp = anthropic.Anthropic().messages.create(
        model=config.ANTHROPIC_MODEL, max_tokens=200,
        messages=[{"role": "user", "content": _prompt(text)}])
    return _json_from(resp.content[0].text)


# ------------------------------------------------------------------ local rules
def _fold(s):
    """Strip accents while keeping case and text length."""
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def _next_date(day, month, year=None):
    today = date.today()
    if year:
        year = year + 2000 if year < 100 else year
        return date(year, month, day)
    d = date(today.year, month, day)
    return d if d >= today else date(today.year + 1, month, day)


def _money(num, mil):
    if re.fullmatch(r"\d{1,3}(,\d{3})+(\.\d+)?", num):  # English thousands: 4,000 / 4,000.50
        num = num.replace(",", "")
    thousands_dots = re.fullmatch(r"\d{1,3}(\.\d{3})+", num) or num.count(".") > 1
    n = num.replace(".", "").replace(",", ".") if ("," in num or thousands_dots) else num
    v = float(n)
    return v * 1000 if mil else v


def _blank(low, m):
    return low[:m.start()] + " " * (m.end() - m.start()) + low[m.end():]


def parse_rules(text):
    norm = _fold(text)
    low = norm.lower()
    # "two weeks" -> "2 weeks" (padded so positions still line up with `norm`)
    low = re.sub(r"\b(" + "|".join(NUMBER_WORDS) + r")\b" + _UNITS,
                 lambda m: str(NUMBER_WORDS[m[1]]).ljust(len(m[1])), low)
    p = {"origin": None, "dests": [], "region": None, "depart": None, "stay": None,
         "flex": 0, "month": None, "max_stops": None, "max_price": None}

    # --- region ("any city in Europe" / "qualquer cidade da Europa") ---
    for rx, key in REGION_PATTERNS:
        if re.search(rx, low):
            p["region"] = key
            break

    # --- places: known cities + uppercase IATA codes ---
    mentions, used = [], []

    def free(s, e):
        return all(e <= a or s >= b for a, b in used)

    for city in sorted(CITIES, key=len, reverse=True):
        for m in re.finditer(r"\b" + re.escape(city) + r"\b", low):
            if free(m.start(), m.end()):
                mentions.append((m.start(), m.end(), CITIES[city]))
                used.append((m.start(), m.end()))
    for m in re.finditer(r"\b[A-Z]{3}\b", norm):
        if m.group() not in _IATA_STOP and free(m.start(), m.end()):
            mentions.append((m.start(), m.end(), m.group()))
            used.append((m.start(), m.end()))
    mentions.sort()

    roles = {}
    for i, (s, _e, _c) in enumerate(mentions):
        before = low[max(0, s - 16):s]
        if re.search(r"(\b(to|para|pra|ate|a|destino|rumo a)|->|→)\s*$", before):
            roles[i] = "dest"
        elif re.search(r"\b(from|leaving|departing|de|do|da|origem)\s*$", before):
            roles[i] = "origin"
        elif i > 0 and roles.get(i - 1) == "dest" and \
                re.search(r"(,|\b(or|and|ou|e)\b)\s*$", before):
            roles[i] = "dest"  # list: "to Paris, London or Rome"
    for i in range(len(mentions)):
        if i in roles:
            continue
        have = set(roles.values())
        have_dest = "dest" in have or p["region"] is not None
        if "origin" not in have and (len(mentions) > 1 or have_dest):
            roles[i] = "origin"
        else:
            roles[i] = "dest"
    for i, role in sorted(roles.items()):
        code = mentions[i][2]
        if role == "origin":
            p["origin"] = p["origin"] or code
        elif code not in p["dests"]:
            p["dests"].append(code)
    if (p["dests"] or p["region"]) and not p["origin"]:
        p["origin"] = config.default_origin()

    # --- flexibility (before trip length, so "±3 days" is not read as the trip length) ---
    flex = re.search(r"(?:[±]|\+/-|\bplus or minus\b|\bgive or take\b|\bmais ou menos\b)\s*"
                     r"(\d+)\s*(?:days?|dias?)|"
                     r"(?:flexibility|flexibilidade|flex)\s*(?:of|de)?\s*(\d+)|"
                     r"(\d+)\s*(?:days?\s*(?:of\s*)?flexibility|flexible days?|"
                     r"dias?\s*de\s*flexibilidade)", low)
    if flex:
        p["flex"] = int(next(g for g in flex.groups() if g))
        low = _blank(low, flex)

    # --- dates ---
    iso = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", low)
    dm = re.search(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b", low)
    # "15 january", "15th of january", "15 de janeiro"
    dn = re.search(r"\b(\d{1,2})(?:st|nd|rd|th)?\s*(?:de\s+|of\s+)?(" + _MONTH_RX + r")\b", low)
    # "january 15", "jan 15th"
    nd = re.search(r"\b(" + _MONTH_RX + r")\.?\s+(\d{1,2})(?:st|nd|rd|th)?\b(?!\s*(?:days?|dias?))",
                   low)
    mo = re.search(r"\b(" + _MONTH_RX + r")\b", low)
    try:
        if iso:
            p["depart"] = date(int(iso[1]), int(iso[2]), int(iso[3])).isoformat()
        elif dm:
            p["depart"] = _next_date(int(dm[1]), int(dm[2]),
                                     int(dm[3]) if dm[3] else None).isoformat()
        elif dn:
            p["depart"] = _next_date(int(dn[1]), MONTHS[dn[2]]).isoformat()
        elif nd:
            p["depart"] = _next_date(int(nd[2]), MONTHS[nd[1]]).isoformat()
        elif mo:  # month only: the 15th, with the widest flexibility that fits the query limit
            p["depart"] = _next_date(15, MONTHS[mo[1]]).isoformat()
            p["month"] = p["depart"][:7]
            if not p["flex"]:
                n = len(p["dests"]) or len(REGIONS.get(p["region"], [])) or 1
                p["flex"] = min(7, max(0, (config.max_calls() // n - 1) // 2))
    except ValueError:
        pass
    for found in (dm, dn, nd):
        if found:
            low = _blank(low, found)

    # --- trip length ---
    if re.search(r"\b(one.?way|so ida|somente ida|apenas ida|sem volta)\b", low):
        p["stay"] = None
    elif m := re.search(r"\b(\d+)\s*(?:days?|nights?|dias?|noites?|diarias?)\b", low):
        p["stay"] = int(m[1])
    elif re.search(r"\b(a|one|uma) (week|semana)\b", low):
        p["stay"] = 7
    elif m := re.search(r"\b(\d+)\s*(?:weeks?|semanas?)\b", low):
        p["stay"] = int(m[1]) * 7

    # --- stops ---
    if re.search(r"\b(nonstop|non-stop|direct|no stops|direto|sem escalas?)\b", low):
        p["max_stops"] = 0
    elif m := re.search(r"\b(\d)\s*(?:stops?|escalas?)\b", low):
        p["max_stops"] = int(m[1])

    # --- maximum price ---
    m = re.search(r"(?:r\$|\bbrl\b|\bup to\b|\bunder\b|\bbelow\b|\bless than\b|\bbudget\b|"
                  r"\bate\b|\bmax\w*|\bteto\b|\bno maximo\b)\s*(?:de\s*|of\s*)?(?:r\$|\$|brl)?\s*"
                  r"(\d[\d.,]*)(?![\d/])"
                  r"(?!\s*(?:stops?|days?|nights?|weeks?|escalas?|dias?|noites?|semanas?))"
                  r"(\s*(?:mil|thousand|k)\b)?", low)
    if m:
        p["max_price"] = _money(m[1], m[2])
    return p


# ------------------------------------------------------------------ normalization
def normalize_params(p):
    """Validate/normalize the output of any parser (or of the form/CLI)."""
    p = dict(p)
    origin = (p.get("origin") or "").strip().upper()

    dests = [str(x).strip().upper() for x in (p.get("dests") or []) if str(x).strip()]
    single = [x.strip().upper() for x in str(p.get("dest") or "").split(",") if x.strip()]
    dests = single + [d for d in dests if d not in single]

    region = p.get("region")
    region_key = None
    if region:
        r = str(region)
        region_key = r if r in REGIONS else REGION_ALIASES.get(_fold(r).lower())
    if not dests and region_key:
        dests = list(REGIONS[region_key])

    dests = [d for d in dict.fromkeys(dests) if d != origin]  # no duplicates, never the origin
    missing = [k for k, v in (("origin", origin), ("destination", dests),
                              ("departure date", p.get("depart"))) if not v]
    if missing:
        raise ValueError(f"I couldn't understand the {', '.join(missing)}. {HINT}")
    for code in [origin] + dests:
        if not re.fullmatch(r"[A-Z]{3}", code):
            raise ValueError(f"invalid airport code: {code!r}")
    depart = date.fromisoformat(p["depart"])
    flex = timedelta(days=int(p.get("flex") or 0))
    while depart + flex < date.today():  # whole window in the past (LLM got the year wrong): roll forward
        depart = depart.replace(year=depart.year + 1, day=min(depart.day, 28)
                                if depart.month == 2 else depart.day)
    month = p.get("month")
    if month and not re.fullmatch(r"\d{4}-\d{2}", str(month)):
        month = None
    if month:
        month = depart.isoformat()[:7]

    return {
        "origin": origin, "dests": dests, "dest": dests[0] if len(dests) == 1 else None,
        "region": region_key, "depart": depart.isoformat(),
        "stay": int(p["stay"]) if p.get("stay") else None,
        "flex": int(p.get("flex") or 0),
        "month": month,  # "YYYY-MM": any day of the month (used by the month search)
        "max_stops": None if p.get("max_stops") in (None, "") else int(p["max_stops"]),
        "max_price": float(p["max_price"]) if p.get("max_price") else None,
    }


def route_label(p):
    """Short text for titles: 'GRU → LIS' or 'GRU → Europe (11 destinations)'."""
    if len(p["dests"]) == 1:
        return f"{p['origin']} → {p['dests'][0]}"
    from .geo import REGION_LABELS
    if p.get("region") in REGION_LABELS:
        return f"{p['origin']} → {REGION_LABELS[p['region']]} ({len(p['dests'])} destinations)"
    if len(p["dests"]) <= 4:
        return f"{p['origin']} → {', '.join(p['dests'])}"
    return f"{p['origin']} → {len(p['dests'])} destinations"


# ------------------------------------------------------------------ parser selection
def llm_provider():
    """LLM_PROVIDER=rules|gemini|ollama|anthropic (default: auto, cheapest first)."""
    forced = os.getenv("LLM_PROVIDER", "auto").lower()
    if forced != "auto":
        return forced
    if os.getenv("GEMINI_API_KEY"):
        return "gemini"
    if config.OLLAMA_MODEL:
        return "ollama"
    if os.getenv("ANTHROPIC_API_KEY"):
        return "anthropic"
    return "rules"


def parse_request(text):
    """Free text -> (normalized parameters, label of the parser that handled it)."""
    prov = llm_provider()
    fn = {"gemini": parse_gemini, "ollama": parse_ollama, "anthropic": parse_anthropic}.get(prov)
    if fn:
        try:
            return normalize_params(fn(text)), prov
        except Exception as e:  # network, quota, bad JSON... never crash the app
            print(f"[warning] {prov} failed ({e}); using local rules", file=sys.stderr)
            return normalize_params(parse_rules(text)), f"rules (fallback: {prov} failed)"
    return normalize_params(parse_rules(text)), "rules"
