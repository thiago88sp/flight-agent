"""Grid/month search (dates × destinations), ranking and comparison with history. No LLM."""
from datetime import date, timedelta

from . import config, history


def date_pairs(p):
    """(departure, return) pairs within the flexibility window, skipping past dates."""
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


FALLBACK_DESTS = 3  # up to how many destinations we search "any date" when nothing fits


def by_month(provider):
    return hasattr(provider, "search_month")


def window(p):
    """Departure days accepted by the month search: the whole month when the request named only
    a month (p["month"]), otherwise the date ± flexibility. Past dates are dropped."""
    if p.get("month"):
        first = date.fromisoformat(p["month"] + "-01")
        nxt = (first + timedelta(days=32)).replace(day=1)
        days = [first + timedelta(days=i) for i in range((nxt - first).days)]
        return [d for d in days if d >= date.today()]
    return [d for d, _ in date_pairs(p)]


def months(p):
    """Months ("YYYY-MM") covered by the departure window."""
    return sorted({d.strftime("%Y-%m") for d in window(p)})


def plan_calls(p, provider=None):
    """How many provider queries the search will make."""
    per_dest = len(months(p)) if by_month(provider) else len(date_pairs(p))
    return len(p["dests"]) * per_dest


def nearby(p, misses, top=5):
    """Offers the cache has but that missed the filters, closest dates to the request first
    (ties broken by price)."""
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
    """Is a month-search offer inside the departure window and trip length (± STAY_TOLERANCE)?"""
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
    """Query every combination and return the offers sorted by price.

    In month search, if `misses` is a list it receives the offers dropped by the date/trip-length
    filter (used to suggest alternatives when nothing fits)."""
    limit = max_calls or config.max_calls()
    n = plan_calls(p, provider)
    if n > limit:
        raise ValueError(f"That would take {n} queries (limit {limit}). Reduce the flexibility, "
                         f"pick fewer destinations or raise MAX_CALLS.")
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
    # Nothing in the requested month(s): fetch any date on the route to suggest alternatives
    # (only for a few destinations, so the number of queries stays small)
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
    """Best offer per destination, comparison with history, saving and alerts."""
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
            alerts.append(f"{route} dropped {abs(diff):.0f}% to R$ {best['price']:,.0f}")
        per_dest.append({"dest": dest, "route": route, "best": best, "prev": prev, "diff": diff})
        history.save(route, best)

    if p.get("max_price"):
        for e in per_dest[:3]:  # up to the 3 cheapest destinations under the budget
            if e["best"]["price"] <= float(p["max_price"]):
                alerts.append(f"{e['route']} is under your budget: R$ {e['best']['price']:,.0f} "
                              f"(limit R$ {float(p['max_price']):,.0f})")

    top = per_dest[0]
    return {"best": top["best"], "route": top["route"], "prev": top["prev"],
            "diff": top["diff"], "per_dest": per_dest, "alerts": alerts}
