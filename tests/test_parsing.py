import pytest

from flight_agent import normalize_params, parse_request, parse_rules
from flight_agent.geo import REGIONS
from flight_agent import parsing


def parse(text):
    return parse_request(text)[0]


def test_codigos_iata_data_estadia_e_teto():
    p = parse("GRU para Lisboa por volta de 10/12, 10 dias, até R$ 4000")
    assert (p["origin"], p["dests"], p["dest"]) == ("GRU", ["LIS"], "LIS")
    assert p["depart"].endswith("-12-10")
    assert p["stay"] == 10 and p["max_price"] == 4000.0 and p["flex"] == 0


def test_cidades_por_extenso_mes_e_semana():
    p = parse("quero ir de São Paulo para Paris em dezembro, uma semana, direto, até 6.500")
    assert (p["origin"], p["dests"]) == ("GRU", ["CDG"])
    assert p["stay"] == 7 and p["max_stops"] == 0 and p["max_price"] == 6500.0
    assert p["depart"].endswith("-12-15") and p["flex"] > 0  # só o mês -> flex automática
    assert p["month"] == p["depart"][:7]                     # e busca mensal no mês inteiro


def test_flexibilidade_nao_vira_estadia_e_mil():
    p = parse("Rio de Janeiro -> Miami 15 de janeiro, 12 dias, ±3 dias, máximo 5 mil")
    assert (p["origin"], p["dests"]) == ("GIG", ["MIA"])
    assert p["stay"] == 12 and p["flex"] == 3 and p["max_price"] == 5000.0


def test_so_ida_origem_padrao_e_escalas():
    p = parse("passagem para Buenos Aires dia 20/11 só ida até 1 escala")
    assert p["origin"] == "GRU" and p["dests"] == ["EZE"]
    assert p["stay"] is None and p["max_stops"] == 1 and p["max_price"] is None


def test_data_iso_e_flexibilidade_por_extenso():
    p = parse("saindo de CNF para Madri em 2026-12-05, 14 noites, flexibilidade de 2")
    assert (p["origin"], p["dests"], p["depart"]) == ("CNF", ["MAD"], "2026-12-05")
    assert p["stay"] == 14 and p["flex"] == 2


def test_regiao_qualquer_cidade_da_europa():
    p = parse("GRU para qualquer cidade da Europa em 10/12, 10 dias")
    assert p["region"] == "europa" and p["dest"] is None
    assert p["dests"] == REGIONS["europa"]


def test_regiao_com_so_o_mes_respeita_limite_de_consultas(monkeypatch):
    monkeypatch.setenv("MAX_CALLS", "80")
    p = parse("de Curitiba para a Europa em março, 10 dias")
    assert p["origin"] == "CWB" and p["region"] == "europa"
    assert len(p["dests"]) * (2 * p["flex"] + 1) <= 80


def test_lista_de_destinos():
    p = parse("para Paris, Londres ou Roma saindo de CNF em 05/01, 7 dias")
    assert p["origin"] == "CNF" and p["dests"] == ["CDG", "LHR", "FCO"]


def test_origem_removida_dos_destinos():
    p = normalize_params({"origin": "GRU", "region": "europa", "depart": "2030-01-10"})
    assert "GRU" not in p["dests"]
    p = normalize_params({"origin": "FOR", "region": "nordeste", "depart": "2030-01-10"})
    assert "FOR" not in p["dests"]


def test_normalize_aceita_lista_por_virgula_e_alias_de_regiao():
    p = normalize_params({"origin": "gru", "dest": "lis, mad", "depart": "2030-01-10"})
    assert p["dests"] == ["LIS", "MAD"]
    p = normalize_params({"origin": "GRU", "region": "América do Sul", "depart": "2030-01-10"})
    assert p["region"] == "america_do_sul"


@pytest.mark.parametrize("texto", ["Orlando", "quero viajar", "10/12 por 5 dias"])
def test_pedido_incompleto_gera_erro_claro(texto):
    with pytest.raises(ValueError, match="não entendi"):
        parse(texto)


def test_codigo_invalido():
    with pytest.raises(ValueError, match="inválido"):
        normalize_params({"origin": "GRU", "dest": "LISBOA", "depart": "2030-01-10"})


def test_llm_que_falha_cai_nas_regras(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "x")

    def boom(_):
        raise RuntimeError("sem rede")

    monkeypatch.setattr(parsing, "parse_gemini", boom)
    p, how = parse_request("GRU para Lisboa em 10/12, 10 dias")
    assert p["dests"] == ["LIS"] and "fallback" in how


def test_llm_ok_e_normalizado(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setattr(parsing, "parse_gemini", lambda t: {
        "origin": "gru", "dest": None, "region": "europa", "depart": "2030-05-10",
        "stay": 8, "flex": 1, "max_stops": None, "max_price": 3500})
    p, how = parse_request("qualquer coisa")
    assert how == "gemini" and p["dests"] == REGIONS["europa"] and p["max_price"] == 3500.0


def test_parse_rules_nao_valida_apenas_extrai():
    assert parse_rules("Orlando")["dests"] == ["MCO"]


def test_data_com_dia_nao_marca_mes_inteiro():
    assert parse("GRU para Lisboa em 10/12, 10 dias")["month"] is None


def test_mes_invalido_do_llm_e_ignorado():
    p = normalize_params({"origin": "GRU", "dest": "LIS", "depart": "2026-12-15",
                          "month": "dezembro"})
    assert p["month"] is None


def test_data_passada_do_llm_vai_para_o_proximo_ano():
    from datetime import date, timedelta
    past = date.today() - timedelta(days=30)
    p = normalize_params({"origin": "GRU", "dest": "LIS", "depart": past.isoformat(),
                          "month": past.strftime("%Y-%m")})
    d = date.fromisoformat(p["depart"])
    assert d >= date.today() and (d.month, d.year) == (past.month, past.year + 1)
    assert p["month"] == p["depart"][:7]
