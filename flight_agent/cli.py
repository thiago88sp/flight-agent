"""Linha de comando.

Exemplos:
  python -m flight_agent "GRU para Lisboa por volta de 10/12, 10 dias, até R$ 4000"
  python -m flight_agent "GRU para qualquer cidade da Europa em março, 10 dias, direto"
  python -m flight_agent --origin GRU --dest LIS,MAD --depart 2026-12-10 --stay 10 --flex 3
  python -m flight_agent --origin GRU --region europa --depart 2026-12-10 --stay 10
"""
import argparse
import sys

from . import parsing, providers, search
from . import present as fmt
from .geo import REGIONS
from .notify import notify


def report(p, results, top=5):
    if not results:
        return ("Nenhuma oferta encontrada. Tente mais flexibilidade de datas, aceitar escalas "
                "ou o código da cidade inteira (ex.: SAO, LON)."), []
    info = search.analyze(p, results)
    multi = len(info["per_dest"]) > 1
    best = info["best"]
    lines = [f"{parsing.route_label(p)} | {len(results)} oferta(s)", "",
             f"Mais barata: {fmt.city(best['dest'])} por {fmt.money(best['price'])}",
             f"  {fmt.trip(best)} | {fmt.airline(best['airline'])}, {fmt.stops(best['stops'])}",
             f"  Comprar: {fmt.booking_url(p['origin'], best)}", ""]
    others = [e["best"] for e in info["per_dest"][1:top]] if multi else results[1:top]
    if others:
        lines.append("Outros destinos:" if multi else "Outras opções:")
    for o in others:
        lines.append(f"  {fmt.money(o['price']):>10} | {fmt.city(o['dest'])} | {fmt.trip(o)} | "
                     f"{fmt.airline(o['airline'])}, {fmt.stops(o['stops'])}")
    if info["prev"] is not None:
        lines.append(f"\nMenor preço anterior em {info['route']}: {fmt.money(info['prev'])} "
                     f"({info['diff']:+.1f}% hoje)")
    return "\n".join(lines), info["alerts"]


def main(argv=None):
    ap = argparse.ArgumentParser(prog="flight_agent", description="Agente de busca de passagens")
    ap.add_argument("text", nargs="?", help="pedido em linguagem natural")
    ap.add_argument("--origin")
    ap.add_argument("--dest", help="IATA; vários separados por vírgula (ex.: LIS,MAD)")
    ap.add_argument("--region", choices=sorted(REGIONS), help="busca em todos os destinos da região")
    ap.add_argument("--depart", help="YYYY-MM-DD")
    ap.add_argument("--stay", type=int, help="dias de estadia (omitir = só ida)")
    ap.add_argument("--flex", type=int, default=0, help="± dias de flexibilidade")
    ap.add_argument("--max-stops", type=int, dest="max_stops")
    ap.add_argument("--max-price", type=float, dest="max_price")
    ap.add_argument("--max-calls", type=int, dest="max_calls", help="limite de consultas")
    a = ap.parse_args(argv)

    try:
        if a.text:
            params, how = parsing.parse_request(a.text)
            print(f"[interpretado por: {how}]", file=sys.stderr)
        elif a.origin and (a.dest or a.region) and a.depart:
            params = parsing.normalize_params({k: v for k, v in vars(a).items()
                                               if k not in ("text", "max_calls")})
        else:
            ap.error("informe um texto livre OU --origin, (--dest ou --region) e --depart")
        prov = providers.get_provider()
        print(f"Busca: {parsing.route_label(params)} | ida {params['depart']} "
              f"| {search.plan_calls(params, prov)} consulta(s)")
        results = search.search_grid(prov, params, a.max_calls)
    except ValueError as e:
        sys.exit(f"Erro: {e}")

    text, alerts = report(params, results)
    for msg in alerts:
        notify(msg)
    print(text)


if __name__ == "__main__":
    main()
