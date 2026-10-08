from datetime import date, timedelta

from flight_agent import normalize_params
from flight_agent import watch as w


class Fixed:
    """Provedor em grade com preço ajustável; conta as consultas."""

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


def test_avisa_ao_atingir_alvo_e_so_de_novo_se_cair():
    w.add_watch(_watch(target=3000))
    sent, _ = _run(Fixed(3500))
    assert sent == []                                       # acima do alvo: silêncio
    sent, _ = _run(Fixed(2900))
    assert len(sent) == 1 and "Preço-alvo atingido" in sent[0][0]
    assert sent[0][1][0].startswith("Comprar no Google Flights")
    assert _run(Fixed(2900))[0] == []                       # mesmo preço: não repete
    sent, _ = _run(Fixed(2700))
    assert len(sent) == 1 and "Caiu ainda mais" in sent[0][0]
    st = w.load_state()[_watch(target=3000)["id"]]
    assert st["best"] == 2700 and st["notified"] == 2700


def test_expirado_manda_resumo_uma_vez_e_nao_busca():
    watch = _watch()
    watch["until"] = (date.today() - timedelta(days=1)).isoformat()
    w.add_watch(watch)
    prov = Fixed(100)
    sent, _ = _run(prov)
    assert len(sent) == 1 and "encerrado" in sent[0][0] and prov.calls == 0
    assert _run(prov)[0] == []


def test_watches_do_secret_tem_prioridade(monkeypatch):
    import json
    w.add_watch(_watch(target=1))                           # arquivo local: alvo inatingível
    monkeypatch.setenv("WATCHES", json.dumps([_watch(target=5000)]))
    sent, _ = _run(Fixed(4000))
    assert len(sent) == 1


def test_remover_e_substituir_por_id():
    a = _watch(target=3000)
    w.add_watch(a)
    w.add_watch(a)                                          # mesmo id: não duplica
    assert len(w.load_watches()) == 1
    assert w.remove_watch(a["id"]) == []


def test_erro_em_um_monitoramento_nao_para_os_outros():
    bad = _watch(target=3000)
    bad["id"], bad["query"]["origin"] = "ruim", "1"         # origem inválida
    w.add_watch(bad)
    w.add_watch(_watch(target=5000))
    sent, log = _run(Fixed(4000))
    assert len(sent) == 1 and any("erro" in line for line in log)
