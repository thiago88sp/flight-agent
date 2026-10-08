from datetime import date, timedelta

import pytest

from flight_agent import analyze, normalize_params, plan_calls, search_grid
from flight_agent.providers import MockProvider, TravelpayoutsProvider, get_provider


class FakeProvider:
    """Fixed price per destination, for deterministic tests."""

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


def test_query_plan_and_sorting():
    p = params(flex=2)
    assert plan_calls(p) == 2 * 5
    fake = FakeProvider(extra={"MAD": 300})
    res = search_grid(fake, p)
    assert fake.calls == 10 and len(res) == 10
    assert res[0]["dest"] == "LIS" and res[-1]["dest"] == "MAD"
    assert [o["price"] for o in res] == sorted(o["price"] for o in res)


def test_query_limit():
    p = params(region="europe", dest="", flex=4)  # 11 destinations × 9 dates = 99 > 80
    with pytest.raises(ValueError, match="queries"):
        search_grid(FakeProvider(), p)
    assert len(search_grid(FakeProvider(), p, max_calls=500)) == plan_calls(p)


def test_stops_filter():
    class Stops:
        def search(self, *a):
            return [{"airline": "A", "price": 1, "stops": 0, "currency": "BRL"},
                    {"airline": "B", "price": 2, "stops": 2, "currency": "BRL"}]
    res = search_grid(Stops(), params(max_stops=1))
    assert {o["airline"] for o in res} == {"A"}


def test_past_dates_are_skipped():
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    p = params(depart=yesterday, flex=2)  # yesterday-2 ... yesterday+2: only today and tomorrow count
    assert plan_calls(p) == 2 * 2         # 2 dates × 2 destinations


def test_drop_and_budget_alerts_per_destination():
    p = params(max_price=1800)
    analyze(p, search_grid(FakeProvider(2000), p))               # 1st run: no drop alert
    info = analyze(p, search_grid(FakeProvider(1500), p))        # price drops 25%
    texts = " | ".join(info["alerts"])
    assert "GRU-LIS dropped 25%" in texts and "GRU-MAD dropped 25%" in texts
    assert "under your budget" in texts
    assert info["per_dest"][0]["diff"] == pytest.approx(-25.0)


def test_first_run_has_no_drop_alert():
    p = params()
    info = analyze(p, search_grid(FakeProvider(), p))
    assert info["alerts"] == [] and info["prev"] is None


def test_mock_provider_is_deterministic():
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


def test_travelpayouts_converts_response(monkeypatch):
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


def test_travelpayouts_http_error_returns_empty(monkeypatch):
    monkeypatch.setenv("TRAVELPAYOUTS_TOKEN", "x")
    monkeypatch.setattr(TravelpayoutsProvider, "PAUSE", 0)
    tp = TravelpayoutsProvider()
    tp.requests = _FakeRequests(_FakeResp(401, {}))
    assert tp.search_month("GRU", "LIS", "2026-11", False) == []
    assert tp.search_month("GRU", "CDG", "2026-11", False) == []
    errs = tp.pop_errors()
    assert len(errs) == 1 and "401" in errs[0]        # the same failure is reported once
    assert tp.pop_errors() == []


def test_travelpayouts_network_failure_becomes_warning(monkeypatch):
    import requests
    monkeypatch.setenv("TRAVELPAYOUTS_TOKEN", "x")
    monkeypatch.setattr(TravelpayoutsProvider, "PAUSE", 0)
    tp = TravelpayoutsProvider()

    class _Down(_FakeRequests):
        RequestException = requests.RequestException

        def get(self, *a, **k):
            raise requests.ConnectionError("no network")
    tp.requests = _Down(None)
    assert tp.search_month("GRU", "LIS", "2026-11", False) == []
    assert "unreachable" in tp.pop_errors()[0]


def test_without_token_uses_simulated_prices():
    assert isinstance(get_provider(), MockProvider)


class MonthProvider:
    """Month provider: returns fixed offers with their own dates."""

    def __init__(self, offers):
        self.offers, self.calls = offers, []

    def search_month(self, origin, dest, month, round_trip):
        self.calls.append((dest, month, round_trip))
        return [o for o in self.offers if o["depart"].startswith(month or "")]


def _o(dep, ret, price, stops=0):
    return {"airline": "XX", "price": price, "stops": stops, "currency": "BRL",
            "depart": dep.isoformat(), "return": ret.isoformat() if ret else None}


def test_month_search_filters_window_and_trip_length(monkeypatch):
    monkeypatch.setenv("STAY_TOLERANCE", "3")
    d0 = date.today() + timedelta(days=60)
    p = normalize_params({"origin": "GRU", "dests": ["LON"], "depart": d0.isoformat(),
                          "stay": 12, "flex": 2})
    prov = MonthProvider([
        _o(d0, d0 + timedelta(days=15), 3881),                         # 15-day trip: within 12±3
        _o(d0 + timedelta(days=1), d0 + timedelta(days=20), 1000),     # 19-day trip: out
        _o(d0 + timedelta(days=5), d0 + timedelta(days=17), 900),      # departure outside the ±2 window
        _o(d0, None, 500),                                             # one-way: out
        _o(d0 - timedelta(days=2), d0 + timedelta(days=9), 2500, 2),   # 11-day trip, 2 stops
    ])
    found = search_grid(prov, p)
    assert [o["price"] for o in found] == [2500, 3881]
    assert found[1]["return"] == (d0 + timedelta(days=15)).isoformat()
    assert plan_calls(p, prov) == len({c[1] for c in prov.calls}) == len(prov.calls)
    p["max_stops"] = 1
    assert [o["price"] for o in search_grid(prov, p)] == [3881]


def test_month_search_one_way_and_window_across_two_months():
    d0 = date.today() + timedelta(days=60)
    d0 = d0.replace(day=1)  # the ±3 window crosses the month boundary
    p = normalize_params({"origin": "GRU", "dests": ["LIS"], "depart": d0.isoformat(),
                          "flex": 3})
    prov = MonthProvider([_o(d0 - timedelta(days=2), None, 700),
                          _o(d0 + timedelta(days=1), d0 + timedelta(days=8), 600)])
    assert [o["price"] for o in search_grid(prov, p)] == [700]
    assert plan_calls(p, prov) == 2 and all(rt is False for _, _, rt in prov.calls)


def test_month_only_request_searches_the_whole_month():
    first = (date.today() + timedelta(days=70)).replace(day=1)
    last = (first + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    p = normalize_params({"origin": "GRU", "dests": ["LIS"], "depart": first.replace(day=15).isoformat(),
                          "month": first.strftime("%Y-%m"), "stay": 10})
    prov = MonthProvider([_o(first, first + timedelta(days=10), 900),
                          _o(last, last + timedelta(days=11), 800)])
    assert [o["price"] for o in search_grid(prov, p)] == [800, 900]
    assert plan_calls(p, prov) == 1


def test_no_offer_in_window_suggests_nearby_dates():
    from flight_agent.search import nearby
    d0 = date.today() + timedelta(days=40)
    p = normalize_params({"origin": "GRU", "dests": ["MCO"], "depart": d0.isoformat(),
                          "stay": 16})
    far = d0 + timedelta(days=200)
    prov = MonthProvider([_o(far, far + timedelta(days=16), 3000),
                          _o(far + timedelta(days=60), far + timedelta(days=76), 2000),
                          _o(far, None, 1000)])                     # one-way: not usable
    misses = []
    assert search_grid(prov, p, misses=misses) == []
    assert prov.calls[-1] == ("MCO", None, True)                    # fell back to "any date"
    assert [o["price"] for o in nearby(p, misses)] == [3000, 2000]  # closest first


def test_any_date_fallback_skipped_for_large_regions():
    d0 = date.today() + timedelta(days=40)
    p = normalize_params({"origin": "GRU", "dests": ["LIS", "MAD", "CDG", "FCO"],
                          "depart": d0.isoformat(), "stay": 10})
    prov = MonthProvider([])
    search_grid(prov, p, misses=[])
    assert all(month is not None for _, month, _ in prov.calls)
