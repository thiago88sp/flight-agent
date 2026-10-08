"""Provedores de preço. Cada um expõe UMA destas formas de busca:

- search(origin, dest, depart, ret) -> ofertas para um par exato de datas (busca em grade);
- search_month(origin, dest, month, round_trip) -> todas as ofertas do mês, cada uma com
  "depart"/"return" (ISO); a busca filtra localmente a janela de datas e a estadia.

Oferta = {"airline": str, "price": float, "stops": int, "currency": str}
"""
import hashlib
import os
import sys
import time


class MockProvider:
    """Preços determinísticos e FICTÍCIOS, só para testar o fluxo sem credenciais."""

    name = "simulado"

    def pop_errors(self):
        return []

    def search(self, origin, dest, depart, ret):
        offers = []
        for airline, base in (("LATAM", 1.0), ("TAP", 0.93), ("Azul", 1.08)):
            seed = f"{origin}{dest}{depart}{ret}{airline}".encode()
            h = int(hashlib.md5(seed).hexdigest(), 16)
            dest_factor = 0.7 + (int(hashlib.md5(dest.encode()).hexdigest(), 16) % 90) / 100
            price = 2200 * base * dest_factor * (0.8 + (h % 700) / 1000)
            if depart.weekday() in (1, 2):  # ter/qua costumam ser mais baratos
                price *= 0.9
            offers.append({"airline": airline, "price": round(price, 2),
                           "stops": h % 3, "currency": "BRL"})
        return offers


class TravelpayoutsProvider:
    """Preços reais (grátis) da Aviasales Data API via Travelpayouts: travelpayouts.com.

    Os preços vêm do cache de buscas recentes de usuários do Aviasales, não de consulta em
    tempo real: rotas/datas pouco buscadas podem voltar vazias e o valor pode estar defasado.
    """

    name = "Travelpayouts"
    URL = "https://api.travelpayouts.com/aviasales/v3/prices_for_dates"
    PAUSE = 0.1  # evita estourar o limite de requisições por segundo

    HINTS = {401: "token inválido? confira TRAVELPAYOUTS_TOKEN no .env",
             429: "limite de requisições atingido; reduza MAX_CALLS ou tente mais tarde"}

    def __init__(self):
        import requests
        self.requests = requests
        self.headers = {"X-Access-Token": os.environ["TRAVELPAYOUTS_TOKEN"]}
        self.errors = []  # mensagens distintas desde a última pop_errors()

    def _error(self, msg):
        if msg not in self.errors:
            self.errors.append(msg)
            print(f"[erro] {msg}", file=sys.stderr)

    def pop_errors(self):
        errs, self.errors = self.errors, []
        return errs

    def search_month(self, origin, dest, month, round_trip):
        """Uma consulta por mês: o cache raramente tem o par exato de datas pedido, então
        trazemos tudo e deixamos search.py filtrar. Sem return_at a volta pode cair em
        qualquer data (inclusive no mês seguinte). month=None traz qualquer data de ida."""
        params = {"origin": origin, "destination": dest,
                  "currency": "brl", "sorting": "price", "limit": 100,
                  "one_way": "false" if round_trip else "true"}
        if month:
            params["departure_at"] = month
        time.sleep(self.PAUSE)
        try:
            resp = self.requests.get(self.URL, headers=self.headers, params=params, timeout=30)
        except self.requests.RequestException as e:
            self._error(f"Travelpayouts inacessível: {type(e).__name__}")
            return []
        if resp.status_code != 200:
            hint = self.HINTS.get(resp.status_code) or resp.text[:120].strip()
            self._error(f"Travelpayouts HTTP {resp.status_code}: {hint}")
            return []
        body = resp.json()
        currency = body.get("currency", "brl").upper()
        out = []
        for o in body.get("data", []):
            ret = o.get("return_at") if round_trip else None
            out.append({"airline": o.get("airline", "?"),
                        "price": float(o["price"]),
                        "stops": max(o.get("transfers", 0), o.get("return_transfers", 0)),
                        "currency": currency,
                        "depart": o["departure_at"][:10],
                        "return": ret[:10] if ret else None,
                        "link": o.get("link")})  # caminho no aviasales.com para fechar a compra
        return out


def using_mock() -> bool:
    return not os.getenv("TRAVELPAYOUTS_TOKEN")


def get_provider():
    if using_mock():
        print("[aviso] sem TRAVELPAYOUTS_TOKEN -> usando preços SIMULADOS", file=sys.stderr)
        return MockProvider()
    return TravelpayoutsProvider()
