"""Busca em grade (datas × destinos), ranking e análise contra o histórico. Sem LLM."""
from datetime import date, timedelta

from . import config, history


def date_pairs(p):
    """Pares (ida, volta) dentro da flexibilidade, ignorando datas passadas."""
    d0 = date.fromisoformat(p["depart"])
    flex = int(p.get("flex") or 0)
    stay = p.get("stay")
    pairs = []
    for delta in range(-flex, flex + 1):
        d = d0 + timedelta(days=delta)
        if d < date.today():
            continue
        pairs.append((d, d + timedelta(days=int(stay)) if stay else None))
    return pairs


FALLBACK_DESTS = 3  # até quantos destinos vale buscar "qualquer data" quando nada se encaixa


def by_month(provider):
    return hasattr(provider, "search_month")


def window(p):
    """Dias de ida aceitos na busca mensal: o mês inteiro quando o pedido citou só o mês
    (p["month"]), senão a data ± flexibilidade. Datas passadas ficam de fora."""
    if p.get("month"):
        first = date.fromisoformat(p["month"] + "-01")
        nxt = (first + timedelta(days=32)).replace(day=1)
        days = [first + timedelta(days=i) for i in range((nxt - first).days)]
        return [d for d in days if d >= date.today()]
    return [d for d, _ in date_pairs(p)]


def months(p):
    """Meses ("YYYY-MM") cobertos pela janela de ida."""
    return sorted({d.strftime("%Y-%m") for d in window(p)})


def plan_calls(p, provider=None):
    """Quantas consultas ao provedor a busca vai fazer."""
    per_dest = len(months(p)) if by_month(provider) else len(date_pairs(p))
    return len(p["dests"]) * per_dest


def nearby(p, misses, top=5):
    """Ofertas que o cache tem mas ficaram fora dos filtros, das datas mais próximas do
    pedido para as mais distantes (desempate pelo preço)."""
    target = date.fromisoformat(p["depart"])
    stay = int(p.get("stay") or 0)

    def distance(o):
        d = abs((date.fromisoformat(o["depart"]) - target).days)
        if stay and o["return"]:
            real = (date.fromisoformat(o["return"]) - date.fromisoformat(o["depart"])).days
            d += abs(real - stay)
        return d, o["price"]
    return sorted(misses, key=distance)[:top]


def _fits(p, offer, window):
    """Oferta de busca mensal dentro da janela de ida e da estadia (± STAY_TOLERANCE)?"""
    d = offer["depart"]
    if d not in window:
        return False
    stay = int(p.get("stay") or 0)
    if not stay:
        return offer["return"] is None
    if offer["return"] is None:
        return False
    real = (date.fromisoformat(offer["return"]) - date.fromisoformat(d)).days
    return abs(real - stay) <= config.stay_tolerance()


def search_grid(provider, p, max_calls=None, misses=None):
    """Consulta todas as combinações e devolve as ofertas ordenadas por preço.

    Na busca mensal, se `misses` for uma lista, recebe as ofertas descartadas pelo filtro de
    datas/estadia (úteis para sugerir alternativas quando nada se encaixa)."""
    limit = max_calls or config.max_calls()
    n = plan_calls(p, provider)
    if n > limit:
        raise ValueError(f"Seriam {n} consultas (limite {limit}). Reduza a flexibilidade, "
                         f"escolha menos destinos ou aumente MAX_CALLS.")
    found = []
    for dest in p["dests"]:
        if by_month(provider):
            days = {d.isoformat() for d in window(p)}
            for month in months(p):
                for offer in provider.search_month(p["origin"], dest, month, bool(p.get("stay"))):
                    if _fits(p, offer, days):
                        found.append({**offer, "dest": dest})
                    elif misses is not None and bool(offer["return"]) == bool(p.get("stay")):
                        misses.append({**offer, "dest": dest})
        else:
            for d, r in date_pairs(p):
                for offer in provider.search(p["origin"], dest, d, r):
                    found.append({**offer, "dest": dest, "depart": d.isoformat(),
                                  "return": r.isoformat() if r else None})
    # Nada no(s) mês(es) pedido(s): busca qualquer data da rota para sugerir alternativas
    # (só com poucos destinos, para não multiplicar as consultas)
    if by_month(provider) and misses is not None and not found and not misses \
            and len(p["dests"]) <= FALLBACK_DESTS:
        for dest in p["dests"]:
            for offer in provider.search_month(p["origin"], dest, None, bool(p.get("stay"))):
                if bool(offer["return"]) == bool(p.get("stay")) \
                        and date.fromisoformat(offer["depart"]) >= date.today():
                    misses.append({**offer, "dest": dest})
    if p.get("max_stops") is not None:
        found = [o for o in found if o["stops"] <= int(p["max_stops"])]
        if misses is not None:
            misses[:] = [o for o in misses if o["stops"] <= int(p["max_stops"])]
    return sorted(found, key=lambda x: x["price"])


def analyze(p, results):
    """Melhor oferta por destino, comparação com o histórico, gravação e alertas."""
    best_by_dest = {}
    for o in results:
        cur = best_by_dest.get(o["dest"])
        if cur is None or o["price"] < cur["price"]:
            best_by_dest[o["dest"]] = o

    per_dest, alerts = [], []
    for dest, best in sorted(best_by_dest.items(), key=lambda kv: kv[1]["price"]):
        route = f"{p['origin']}-{dest}"
        prev = history.last_min(route)
        diff = (best["price"] - prev) / prev * 100 if prev else None
        if diff is not None and diff <= -config.drop_alert_pct():
            alerts.append(f"{route} caiu {abs(diff):.0f}% para R$ {best['price']:.2f}")
        per_dest.append({"dest": dest, "route": route, "best": best, "prev": prev, "diff": diff})
        history.save(route, best)

    if p.get("max_price"):
        for e in per_dest[:3]:  # até 3 destinos mais baratos abaixo do teto
            if e["best"]["price"] <= float(p["max_price"]):
                alerts.append(f"{e['route']} abaixo do seu teto: R$ {e['best']['price']:.2f} "
                              f"(limite R$ {float(p['max_price']):.2f})")

    top = per_dest[0]
    return {"best": top["best"], "route": top["route"], "prev": top["prev"],
            "diff": top["diff"], "per_dest": per_dest, "alerts": alerts}
