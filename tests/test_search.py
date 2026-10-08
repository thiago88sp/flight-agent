from datetime import date, timedelta

import pytest

from flight_agent import analyze, normalize_params, plan_calls, search_grid
from flight_agent.providers import MockProvider, TravelpayoutsProvider, get_provider


class FakeProvider:
    """Preço fixo por destino, para testes determinísticos."""

    def __init__(self, base=2000.0, extra=None):
        self.base, self.extra, self.calls = base, extra or {}, 0

    def search(self, origin, dest, depart, ret):
        self.calls += 1
        return [{"airline": "X", "price": self.base + self.extra.get(dest, 0),
                 "stops": 0, "currency": "BRL"}]


def params(**kw):
    base = {"origin": "GRU", "dest": "LIS,MAD", "flex": 0, "stay": 7,
            "depart": (date.today() + timedelta(days=30)).isoformat()}
    return normalize_params({**base, **kw})


def test_plano_de_consultas_e_ordenacao():
    p = params(flex=2)
    assert plan_calls(p) == 2 * 5
    fake = FakeProvider(extra={"MAD": 300})
    res = search_grid(fake, p)
    assert fake.calls == 10 and len(res) == 10
    assert res[0]["dest"] == "LIS" and res[-1]["dest"] == "MAD"
    assert [o["price"] for o in res] == sorted(o["price"] for o in res)


def test_limite_de_consultas():
    p = params(region="europa", dest="", flex=4)  # 11 destinos × 9 datas = 99 > 80
    with pytest.raises(ValueError, match="consultas"):
        search_grid(FakeProvider(), p)
    assert len(search_grid(FakeProvider(), p, max_calls=500)) == plan_calls(p)


def test_filtro_de_escalas():
    class Escalas:
        def search(self, *a):
            return [{"airline": "A", "price": 1, "stops": 0, "currency": "BRL"},
                    {"airline": "B", "price": 2, "stops": 2, "currency": "BRL"}]
    res = search_grid(Escalas(), params(max_stops=1))
    assert {o["airline"] for o in res} == {"A"}


def test_datas_passadas_sao_ignoradas():
    ontem = (date.today() - timedelta(days=1)).isoformat()
    p = params(depart=ontem, flex=2)  # datas: ontem-2 ... ontem+2; só hoje e amanhã valem
    assert plan_calls(p) == 2 * 2     # 2 datas × 2 destinos


def test_alertas_de_queda_e_teto_por_destino():
    p = params(max_price=1800)
    analyze(p, search_grid(FakeProvider(2000), p))               # 1ª execução: sem alerta de queda
    info = analyze(p, search_grid(FakeProvider(1500), p))        # preço cai 25%
    texts = " | ".join(info["alerts"])
    assert "GRU-LIS caiu 25%" in texts and "GRU-MAD caiu 25%" in texts
    assert "abaixo do seu teto" in texts
    assert info["per_dest"][0]["diff"] == pytest.approx(-25.0)


def test_primeira_execucao_nao_gera_alerta_de_queda():
    p = params()
    info = analyze(p, search_grid(FakeProvider(), p))
    assert info["alerts"] == [] and info["prev"] is None


def test_mock_provider_e_deterministico():
    d = date.today() + timedelta(days=30)
    m = MockProvider()
    assert m.search("GRU", "LIS", d, None) == m.search("GRU", "LIS", d, None)
    assert m.search("GRU", "LIS", d, None) != m.search("GRU", "CDG", d, None)


class _FakeResp:
    def __init__(self, status, body):
        self.status_code, self._body, self.text = status, body, str(body)

    def json(self):
        return self._body


class _FakeRequests:
    import requests
    RequestException = requests.RequestException

    def __init__(self, resp):
        self.resp, self.calls = resp, []

    def get(self, url, headers, params, timeout):
        self.calls.append(params)
        return self.resp


def test_travelpayouts_converte_resposta(monkeypatch):
    monkeypatch.setenv("TRAVELPAYOUTS_TOKEN", "x")
    monkeypatch.setattr(TravelpayoutsProvider, "PAUSE", 0)
    tp = TravelpayoutsProvider()
    tp.requests = _FakeRequests(_FakeResp(200, {"success": True, "currency": "brl", "data": [
        {"airline": "TP", "price": 3500, "transfers": 0, "return_transfers": 1,
         "departure_at": "2026-11-02T10:00:00-03:00", "return_at": "2026-11-17T08:00:00+00:00"}]}))
    assert tp.search_month("GRU", "LIS", "2026-11", True) == [
        {"airline": "TP", "price": 3500.0, "stops": 1, "currency": "BRL",
         "depart": "2026-11-02", "return": "2026-11-17", "link": None}]
    sent = tp.requests.calls[0]
    assert sent["one_way"] == "false" and sent["departure_at"] == "2026-11" and "return_at" not in sent


def test_travelpayouts_erro_http_devolve_vazio(monkeypatch):
    monkeypatch.setenv("TRAVELPAYOUTS_TOKEN", "x")
    monkeypatch.setattr(TravelpayoutsProvider, "PAUSE", 0)
    tp = TravelpayoutsProvider()
    tp.requests = _FakeRequests(_FakeResp(401, {}))
    assert tp.search_month("GRU", "LIS", "2026-11", False) == []
    assert tp.search_month("GRU", "CDG", "2026-11", False) == []
    errs = tp.pop_errors()
    assert len(errs) == 1 and "401" in errs[0]        # mesma falha não se repete
    assert tp.pop_errors() == []


def test_travelpayouts_falha_de_rede_vira_aviso(monkeypatch):
    import requests
    monkeypatch.setenv("TRAVELPAYOUTS_TOKEN", "x")
    monkeypatch.setattr(TravelpayoutsProvider, "PAUSE", 0)
    tp = TravelpayoutsProvider()

    class _Down(_FakeRequests):
        RequestException = requests.RequestException

        def get(self, *a, **k):
            raise requests.ConnectionError("sem rede")
    tp.requests = _Down(None)
    assert tp.search_month("GRU", "LIS", "2026-11", False) == []
    assert "inacessível" in tp.pop_errors()[0]


def test_sem_token_usa_simulado():
    assert isinstance(get_provider(), MockProvider)


class MonthProvider:
    """Provedor por mês: devolve ofertas fixas com datas próprias."""

    def __init__(self, offers):
        self.offers, self.calls = offers, []

    def search_month(self, origin, dest, month, round_trip):
        self.calls.append((dest, month, round_trip))
        return [o for o in self.offers if o["depart"].startswith(month or "")]


def _o(dep, ret, price, stops=0):
    return {"airline": "XX", "price": price, "stops": stops, "currency": "BRL",
            "depart": dep.isoformat(), "return": ret.isoformat() if ret else None}


def test_busca_mensal_filtra_janela_e_estadia(monkeypatch):
    monkeypatch.setenv("STAY_TOLERANCE", "3")
    d0 = date.today() + timedelta(days=60)
    p = normalize_params({"origin": "GRU", "dests": ["LON"], "depart": d0.isoformat(),
                          "stay": 12, "flex": 2})
    prov = MonthProvider([
        _o(d0, d0 + timedelta(days=15), 3881),                         # estadia 15: dentro de 12±3
        _o(d0 + timedelta(days=1), d0 + timedelta(days=20), 1000),     # estadia 19: fora
        _o(d0 + timedelta(days=5), d0 + timedelta(days=17), 900),      # ida fora da janela ±2
        _o(d0, None, 500),                                             # só ida: fora
        _o(d0 - timedelta(days=2), d0 + timedelta(days=9), 2500, 2),   # estadia 11, 2 escalas
    ])
    found = search_grid(prov, p)
    assert [o["price"] for o in found] == [2500, 3881]
    assert found[1]["return"] == (d0 + timedelta(days=15)).isoformat()
    assert plan_calls(p, prov) == len({c[1] for c in prov.calls}) == len(prov.calls)
    p["max_stops"] = 1
    assert [o["price"] for o in search_grid(prov, p)] == [3881]


def test_busca_mensal_so_ida_e_janela_em_dois_meses():
    d0 = date.today() + timedelta(days=60)
    d0 = d0.replace(day=1)  # janela ±3 atravessa a virada do mês
    p = normalize_params({"origin": "GRU", "dests": ["LIS"], "depart": d0.isoformat(),
                          "flex": 3})
    prov = MonthProvider([_o(d0 - timedelta(days=2), None, 700),
                          _o(d0 + timedelta(days=1), d0 + timedelta(days=8), 600)])
    assert [o["price"] for o in search_grid(prov, p)] == [700]
    assert plan_calls(p, prov) == 2 and all(rt is False for _, _, rt in prov.calls)


def test_pedido_so_com_mes_busca_o_mes_inteiro():
    first = (date.today() + timedelta(days=70)).replace(day=1)
    last = (first + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    p = normalize_params({"origin": "GRU", "dests": ["LIS"], "depart": first.replace(day=15).isoformat(),
                          "month": first.strftime("%Y-%m"), "stay": 10})
    prov = MonthProvider([_o(first, first + timedelta(days=10), 900),
                          _o(last, last + timedelta(days=11), 800)])
    assert [o["price"] for o in search_grid(prov, p)] == [800, 900]
    assert plan_calls(p, prov) == 1


def test_sem_oferta_na_janela_sugere_datas_proximas():
    from flight_agent.search import nearby
    d0 = date.today() + timedelta(days=40)
    p = normalize_params({"origin": "GRU", "dests": ["MCO"], "depart": d0.isoformat(),
                          "stay": 16})
    far = d0 + timedelta(days=200)
    prov = MonthProvider([_o(far, far + timedelta(days=16), 3000),
                          _o(far + timedelta(days=60), far + timedelta(days=76), 2000),
                          _o(far, None, 1000)])                     # só ida: não serve
    misses = []
    assert search_grid(prov, p, misses=misses) == []
    assert prov.calls[-1] == ("MCO", None, True)                    # caiu no "qualquer data"
    assert [o["price"] for o in nearby(p, misses)] == [3000, 2000]  # mais próxima primeiro


def test_fallback_qualquer_data_nao_roda_para_regioes_grandes():
    d0 = date.today() + timedelta(days=40)
    p = normalize_params({"origin": "GRU", "dests": ["LIS", "MAD", "CDG", "FCO"],
                          "depart": d0.isoformat(), "stay": 10})
    prov = MonthProvider([])
    search_grid(prov, p, misses=[])
    assert all(month is not None for _, month, _ in prov.calls)
