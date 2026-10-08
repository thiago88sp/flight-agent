"""Interpretação do pedido em texto livre -> parâmetros de busca.

Interpretadores (LLM_PROVIDER): rules (padrão, grátis, offline) | gemini | ollama | anthropic.
Se um LLM falhar, cai automaticamente nas regras.

Parâmetros normalizados:
  origin (IATA), dests (lista IATA), dest (IATA se for um só, senão None), region (chave ou None),
  depart (YYYY-MM-DD), stay (dias ou None), flex (± dias), max_stops (int/None), max_price (BRL/None)
"""
import json
import os
import re
import sys
import unicodedata
from datetime import date, timedelta

from . import config
from .geo import CITIES, REGION_ALIASES, REGION_PATTERNS, REGIONS

MONTHS = {"janeiro": 1, "fevereiro": 2, "marco": 3, "abril": 4, "maio": 5, "junho": 6,
          "julho": 7, "agosto": 8, "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12}
_IATA_STOP = {"ATE", "DIA", "MAX", "MIN", "IDA", "RIO", "EUA", "USA"}

PARSE_PROMPT = """Extraia os parâmetros da busca de passagem. Hoje é {today}.
Responda SOMENTE um JSON com as chaves:
origin (IATA), dest (IATA ou null), region (uma de {regions}, ou null; use quando o pedido for "qualquer cidade de <região>"),
depart (YYYY-MM-DD), stay (dias de estadia, int ou null), flex (± dias, int, padrão 0),
month ("YYYY-MM" quando o pedido cita só o mês, sem dia — ex.: "em março"; nesse caso depart = dia 15
desse mês; senão null), max_stops (int ou null), max_price (número em BRL ou null).

Pedido: {text}"""

HINT = ("Tente algo como: 'GRU para Lisboa em 10/12, 10 dias, até R$ 4000' ou "
        "'GRU para qualquer cidade da Europa em março, 10 dias'. "
        "Regiões: Europa, América do Sul, EUA, Caribe, Nordeste.")


# ------------------------------------------------------------------ LLMs (opcionais)
def _json_from(raw):
    raw = raw.strip()
    return json.loads(raw[raw.find("{"): raw.rfind("}") + 1])


def _prompt(text):
    return PARSE_PROMPT.format(today=date.today().isoformat(), text=text,
                               regions=", ".join(REGIONS))


def parse_gemini(text):
    """API do Gemini via REST (chave gratuita do Google AI Studio, sem SDK)."""
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
    """Modelo local via Ollama: grátis, offline, sem chave."""
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
    import anthropic  # opcional: pip install anthropic
    resp = anthropic.Anthropic().messages.create(
        model=config.ANTHROPIC_MODEL, max_tokens=200,
        messages=[{"role": "user", "content": _prompt(text)}])
    return _json_from(resp.content[0].text)


# ------------------------------------------------------------------ regras locais
def _fold(s):
    """Remove acentos preservando maiúsculas/minúsculas e o tamanho do texto."""
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def _next_date(day, month, year=None):
    today = date.today()
    if year:
        year = year + 2000 if year < 100 else year
        return date(year, month, day)
    d = date(today.year, month, day)
    return d if d >= today else date(today.year + 1, month, day)


def _money(num, mil):
    thousands_dots = re.fullmatch(r"\d{1,3}(\.\d{3})+", num) or num.count(".") > 1
    n = num.replace(".", "").replace(",", ".") if ("," in num or thousands_dots) else num
    v = float(n)
    return v * 1000 if mil else v


def _blank(low, m):
    return low[:m.start()] + " " * (m.end() - m.start()) + low[m.end():]


def parse_rules(text):
    norm = _fold(text)
    low = norm.lower()
    p = {"origin": None, "dests": [], "region": None, "depart": None, "stay": None,
         "flex": 0, "month": None, "max_stops": None, "max_price": None}

    # --- região ("qualquer cidade da Europa") ---
    for rx, key in REGION_PATTERNS:
        if re.search(rx, low):
            p["region"] = key
            break

    # --- locais: cidades conhecidas + códigos IATA em maiúsculas ---
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
        if re.search(r"(\b(para|pra|ate|a|destino|rumo a)|->|→)\s*$", before):
            roles[i] = "dest"
        elif re.search(r"\b(de|do|da|origem|from)\s*$", before):
            roles[i] = "origin"
        elif i > 0 and roles.get(i - 1) == "dest" and re.search(r"(,|\bou\b|\be\b)\s*$", before):
            roles[i] = "dest"  # lista: "para Paris, Londres ou Roma"
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

    # --- flexibilidade (antes da estadia, para não confundir "±3 dias" com estadia) ---
    flex = re.search(r"(?:[±]|\+/-|\bmais ou menos\b)\s*(\d+)\s*dias?|"
                     r"flexibilidade\s*(?:de\s*)?(\d+)|(\d+)\s*dias?\s*de\s*flexibilidade", low)
    if flex:
        p["flex"] = int(next(g for g in flex.groups() if g))
        low = _blank(low, flex)

    # --- datas ---
    iso = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", low)
    dm = re.search(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b", low)
    dn = re.search(r"\b(\d{1,2})\s*(?:de\s*)?(" + "|".join(MONTHS) + r")\b", low)
    mo = re.search(r"\b(" + "|".join(MONTHS) + r")\b", low)
    try:
        if iso:
            p["depart"] = date(int(iso[1]), int(iso[2]), int(iso[3])).isoformat()
        elif dm:
            p["depart"] = _next_date(int(dm[1]), int(dm[2]),
                                     int(dm[3]) if dm[3] else None).isoformat()
        elif dn:
            p["depart"] = _next_date(int(dn[1]), MONTHS[dn[2]]).isoformat()
        elif mo:  # só o mês: usa o dia 15 e a maior flexibilidade que cabe no limite de consultas
            p["depart"] = _next_date(15, MONTHS[mo[1]]).isoformat()
            p["month"] = p["depart"][:7]
            if not p["flex"]:
                n = len(p["dests"]) or len(REGIONS.get(p["region"], [])) or 1
                p["flex"] = min(7, max(0, (config.max_calls() // n - 1) // 2))
    except ValueError:
        pass
    if dm:
        low = _blank(low, dm)

    # --- estadia ---
    if re.search(r"\b(so ida|somente ida|apenas ida|sem volta|one.?way)\b", low):
        p["stay"] = None
    elif m := re.search(r"\b(\d+)\s*(?:dias?|noites?|diarias?)\b", low):
        p["stay"] = int(m[1])
    elif re.search(r"\buma semana\b", low):
        p["stay"] = 7
    elif m := re.search(r"\b(\d+)\s*semanas?\b", low):
        p["stay"] = int(m[1]) * 7

    # --- escalas ---
    if re.search(r"\b(direto|sem escalas?|nonstop)\b", low):
        p["max_stops"] = 0
    elif m := re.search(r"\b(\d)\s*escalas?\b", low):
        p["max_stops"] = int(m[1])

    # --- preço máximo ---
    m = re.search(r"(?:r\$|\bate\b|\bmax\w*|\bteto\b|\bno maximo\b)\s*(?:de\s*)?(?:r\$)?\s*"
                  r"(\d[\d.]*(?:,\d+)?)(?![\d/.,])(?!\s*(?:escalas?|dias?|noites?|semanas?))"
                  r"(\s*mil\b)?", low)
    if m:
        p["max_price"] = _money(m[1], m[2])
    return p


# ------------------------------------------------------------------ normalização
def normalize_params(p):
    """Valida/normaliza o resultado de qualquer interpretador (ou do formulário/CLI)."""
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

    dests = [d for d in dict.fromkeys(dests) if d != origin]  # sem repetidos e sem a origem
    missing = [k for k, v in (("origem", origin), ("destino", dests), ("data de ida", p.get("depart")))
               if not v]
    if missing:
        raise ValueError(f"não entendi: {', '.join(missing)}. {HINT}")
    for code in [origin] + dests:
        if not re.fullmatch(r"[A-Z]{3}", code):
            raise ValueError(f"código de aeroporto inválido: {code!r}")
    depart = date.fromisoformat(p["depart"])
    flex = timedelta(days=int(p.get("flex") or 0))
    while depart + flex < date.today():  # janela toda no passado (LLM errou o ano): próxima ocorrência
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
        "month": month,  # "YYYY-MM": qualquer dia do mês (usado pela busca mensal)
        "max_stops": None if p.get("max_stops") in (None, "") else int(p["max_stops"]),
        "max_price": float(p["max_price"]) if p.get("max_price") else None,
    }


def route_label(p):
    """Texto curto para títulos: 'GRU → LIS' ou 'GRU → Europa (11 destinos)'."""
    if len(p["dests"]) == 1:
        return f"{p['origin']} → {p['dests'][0]}"
    from .geo import REGION_LABELS
    if p.get("region") in REGION_LABELS:
        return f"{p['origin']} → {REGION_LABELS[p['region']]} ({len(p['dests'])} destinos)"
    if len(p["dests"]) <= 4:
        return f"{p['origin']} → {', '.join(p['dests'])}"
    return f"{p['origin']} → {len(p['dests'])} destinos"


# ------------------------------------------------------------------ escolha do interpretador
def llm_provider():
    """LLM_PROVIDER=rules|gemini|ollama|anthropic (padrão: auto, do mais barato ao mais caro)."""
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
    """Texto livre -> (parâmetros normalizados, rótulo de quem interpretou)."""
    prov = llm_provider()
    fn = {"gemini": parse_gemini, "ollama": parse_ollama, "anthropic": parse_anthropic}.get(prov)
    if fn:
        try:
            return normalize_params(fn(text)), prov
        except Exception as e:  # rede, cota, JSON ruim... não derruba o app
            print(f"[aviso] {prov} falhou ({e}); usando regras locais", file=sys.stderr)
            return normalize_params(parse_rules(text)), f"regras (fallback: {prov} falhou)"
    return normalize_params(parse_rules(text)), "regras"
