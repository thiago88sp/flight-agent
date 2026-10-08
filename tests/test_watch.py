from datetime import date, timedelta

from flight_agent import normalize_params
from flight_agent import watch as w


class Fixed:
    """Grid provider with an adjustable price; counts the queries."""

    def __init__(self, price):
        self.price, self.calls = price, 0

    def search(self, origin, dest, depart, ret):
        self.calls += 1
        return [{"airline": "TP", "price": self.price, "stops": 0, "currency": "BRL"}]

    def pop_errors(self):
        return []


def _watch(target=3000, days=30, **kw):
    d0 = (date.today() + timedelta(days=40)).isoformat()
    p = normalize_params({"origin": "GRU", "dest": "LIS", "depart": d0, "stay": 10, **kw})
    return w.new_watch(p, target, days)


def _run(prov):
    sent = []
    log = w.run(send=lambda text, button: sent.append((text, button)), provider=prov)
    return sent, log


def test_alerts_on_target_and_again_only_if_it_drops():
    w.add_watch(_watch(target=3000))
    sent, _ = _run(Fixed(3500))
    assert sent == []                                       # above target: silence
    sent, _ = _run(Fixed(2900))
    assert len(sent) == 1 and "Target price reached" in sent[0][0]
    assert sent[0][1][0].startswith("Book on Google Flights")
    assert _run(Fixed(2900))[0] == []                       # same price: no repeat
    sent, _ = _run(Fixed(2700))
    assert len(sent) == 1 and "dropped even more" in sent[0][0]
    st = w.load_state()[_watch(target=3000)["id"]]
    assert st["best"] == 2700 and st["notified"] == 2700


def test_expired_sends_summary_once_and_does_not_search():
    watch = _watch()
    watch["until"] = (date.today() - timedelta(days=1)).isoformat()
    w.add_watch(watch)
    prov = Fixed(100)
    sent, _ = _run(prov)
    assert len(sent) == 1 and "ended" in sent[0][0] and prov.calls == 0
    assert _run(prov)[0] == []


def test_watches_secret_takes_priority(monkeypatch):
    import json
    w.add_watch(_watch(target=1))                           # local file: unreachable target
    monkeypatch.setenv("WATCHES", json.dumps([_watch(target=5000)]))
    sent, _ = _run(Fixed(4000))
    assert len(sent) == 1


def test_remove_and_replace_by_id():
    a = _watch(target=3000)
    w.add_watch(a)
    w.add_watch(a)                                          # same id: no duplicate
    assert len(w.load_watches()) == 1
    assert w.remove_watch(a["id"]) == []


def test_error_in_one_watch_does_not_stop_the_others():
    bad = _watch(target=3000)
    bad["id"], bad["query"]["origin"] = "bad", "1"          # invalid origin
    w.add_watch(bad)
    w.add_watch(_watch(target=5000))
    sent, log = _run(Fixed(4000))
    assert len(sent) == 1 and any("error" in line for line in log)
