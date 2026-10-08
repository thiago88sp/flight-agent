"""Histórico de menores preços por rota (arquivo JSON Lines)."""
import json
from datetime import date

from . import config


def last_min(route):
    """Menor preço já registrado para a rota (ex.: 'GRU-LIS') ou None."""
    path = config.history_file()
    if not path.exists():
        return None
    prices = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line:
            rec = json.loads(line)
            if rec["route"] == route:
                prices.append(rec["price"])
    return min(prices) if prices else None


def save(route, best):
    with config.history_file().open("a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": date.today().isoformat(), "route": route,
                            "price": best["price"], "depart": best["depart"]}) + "\n")
