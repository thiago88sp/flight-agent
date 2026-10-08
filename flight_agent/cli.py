"""Command line.

Examples:
  python -m flight_agent "GRU to Lisbon around Dec 10, 10 days, up to R$ 4000"
  python -m flight_agent "GRU to any city in Europe in March, 10 days, nonstop"
  python -m flight_agent --origin GRU --dest LIS,MAD --depart 2026-12-10 --stay 10 --flex 3
  python -m flight_agent --origin GRU --region europe --depart 2026-12-10 --stay 10
"""
import argparse
import sys

from . import parsing, providers, search
from . import present as fmt
from .geo import REGIONS
from .notify import notify


def report(p, results, top=5):
    if not results:
        return ("No offers found. Try more date flexibility, allowing stops or a whole-city "
                "code (e.g. SAO, LON)."), []
    info = search.analyze(p, results)
    multi = len(info["per_dest"]) > 1
    best = info["best"]
    lines = [f"{parsing.route_label(p)} | {len(results)} offer(s)", "",
             f"Cheapest: {fmt.city(best['dest'])} for {fmt.money(best['price'])}",
             f"  {fmt.trip(best)} | {fmt.airline(best['airline'])}, {fmt.stops(best['stops'])}",
             f"  Book: {fmt.booking_url(p['origin'], best)}", ""]
    others = [e["best"] for e in info["per_dest"][1:top]] if multi else results[1:top]
    if others:
        lines.append("Other destinations:" if multi else "Other options:")
    for o in others:
        lines.append(f"  {fmt.money(o['price']):>10} | {fmt.city(o['dest'])} | {fmt.trip(o)} | "
                     f"{fmt.airline(o['airline'])}, {fmt.stops(o['stops'])}")
    if info["prev"] is not None:
        lines.append(f"\nPrevious lowest price on {info['route']}: {fmt.money(info['prev'])} "
                     f"({info['diff']:+.1f}% today)")
    return "\n".join(lines), info["alerts"]


def main(argv=None):
    ap = argparse.ArgumentParser(prog="flight_agent", description="Flight deal search agent")
    ap.add_argument("text", nargs="?", help="request in natural language (English or Portuguese)")
    ap.add_argument("--origin", help="IATA code (e.g. GRU, or SAO for every São Paulo airport)")
    ap.add_argument("--dest", help="IATA code; several separated by commas (e.g. LIS,MAD)")
    ap.add_argument("--region", help="search every destination in the region: "
                                     + ", ".join(sorted(REGIONS)))
    ap.add_argument("--depart", help="YYYY-MM-DD")
    ap.add_argument("--stay", type=int, help="trip length in days (omit = one-way)")
    ap.add_argument("--flex", type=int, default=0, help="± days of flexibility")
    ap.add_argument("--max-stops", type=int, dest="max_stops")
    ap.add_argument("--max-price", type=float, dest="max_price", help="budget in BRL")
    ap.add_argument("--max-calls", type=int, dest="max_calls", help="query limit")
    a = ap.parse_args(argv)

    try:
        if a.text:
            params, how = parsing.parse_request(a.text)
            print(f"[parsed by: {how}]", file=sys.stderr)
        elif a.origin and (a.dest or a.region) and a.depart:
            params = parsing.normalize_params({k: v for k, v in vars(a).items()
                                               if k not in ("text", "max_calls")})
        else:
            ap.error("give a free-text request OR --origin, (--dest or --region) and --depart")
        prov = providers.get_provider()
        print(f"Search: {parsing.route_label(params)} | departing {params['depart']} "
              f"| {search.plan_calls(params, prov)} query(ies)")
        results = search.search_grid(prov, params, a.max_calls)
    except ValueError as e:
        sys.exit(f"Error: {e}")

    text, alerts = report(params, results)
    for msg in alerts:
        notify(msg)
    print(text)


if __name__ == "__main__":
    main()
