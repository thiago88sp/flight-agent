from datetime import date, timedelta

import pytest

from flight_agent import normalize_params, parse_request, parse_rules
from flight_agent.geo import REGIONS
from flight_agent import parsing


def parse(text):
    return parse_request(text)[0]


# ------------------------------------------------------------------ English
def test_en_iata_date_trip_length_and_budget():
    p = parse("GRU to Lisbon around Dec 10, 10 days, up to R$ 4,000")
    assert (p["origin"], p["dests"], p["dest"]) == ("GRU", ["LIS"], "LIS")
    assert p["depart"].endswith("-12-10")
    assert p["stay"] == 10 and p["max_price"] == 4000.0 and p["flex"] == 0


def test_en_city_names_month_week_and_nonstop():
    p = parse("from São Paulo to Paris in December, a week, nonstop, under 6,500")
    assert (p["origin"], p["dests"]) == ("GRU", ["CDG"])
    assert p["stay"] == 7 and p["max_stops"] == 0 and p["max_price"] == 6500.0
    assert p["depart"].endswith("-12-15") and p["flex"] > 0  # month only -> automatic flex
    assert p["month"] == p["depart"][:7]                     # and whole-month search


def test_en_flexibility_is_not_trip_length_and_k():
    p = parse("Rio de Janeiro -> Miami January 15th, 12 days, ±3 days, budget of 5k")
    assert (p["origin"], p["dests"]) == ("GIG", ["MIA"])
    assert p["stay"] == 12 and p["flex"] == 3 and p["max_price"] == 5000.0


def test_en_one_way_default_origin_and_stops():
    p = parse("flight to Buenos Aires on 20/11 one-way up to 1 stop")
    assert p["origin"] == "GRU" and p["dests"] == ["EZE"]
    assert p["stay"] is None and p["max_stops"] == 1 and p["max_price"] is None


def test_en_iso_date_nights_and_flexibility_in_words():
    p = parse("from CNF to Madrid on 2026-12-05, 14 nights, flexibility of 2")
    assert (p["origin"], p["dests"], p["depart"]) == ("CNF", ["MAD"], "2026-12-05")
    assert p["stay"] == 14 and p["flex"] == 2


def test_en_region_any_city_in_europe():
    p = parse("GRU to any city in Europe on 10/12, 10 days")
    assert p["region"] == "europe" and p["dest"] is None
    assert p["dests"] == REGIONS["europe"]


def test_en_list_of_destinations():
    p = parse("to Paris, London or Rome from CNF on 05/01, 7 days")
    assert p["origin"] == "CNF" and p["dests"] == ["CDG", "LHR", "FCO"]


def test_numbers_written_as_words():
    p = parse("from Rio to Rome in March for about two weeks, max one stop")
    assert (p["origin"], p["dests"], p["stay"], p["max_stops"]) == ("GIG", ["FCO"], 14, 1)
    p = parse("de Recife para Lisboa em março, duas semanas, uma escala")
    assert (p["origin"], p["stay"], p["max_stops"]) == ("REC", 14, 1)


def test_en_day_before_month():
    assert parse("GRU to Lisbon on the 3rd of March, 10 days")["depart"].endswith("-03-03")


# ------------------------------------------------------------------ Portuguese
def test_pt_iata_date_trip_length_and_budget():
    p = parse("GRU para Lisboa por volta de 10/12, 10 dias, até R$ 4000")
    assert (p["origin"], p["dests"], p["dest"]) == ("GRU", ["LIS"], "LIS")
    assert p["depart"].endswith("-12-10")
    assert p["stay"] == 10 and p["max_price"] == 4000.0 and p["flex"] == 0


def test_pt_city_names_month_week_and_direct():
    p = parse("quero ir de São Paulo para Paris em dezembro, uma semana, direto, até 6.500")
    assert (p["origin"], p["dests"]) == ("GRU", ["CDG"])
    assert p["stay"] == 7 and p["max_stops"] == 0 and p["max_price"] == 6500.0
    assert p["depart"].endswith("-12-15") and p["flex"] > 0
    assert p["month"] == p["depart"][:7]


def test_pt_flexibility_is_not_trip_length_and_mil():
    p = parse("Rio de Janeiro -> Miami 15 de janeiro, 12 dias, ±3 dias, máximo 5 mil")
    assert (p["origin"], p["dests"]) == ("GIG", ["MIA"])
    assert p["stay"] == 12 and p["flex"] == 3 and p["max_price"] == 5000.0


def test_pt_one_way_default_origin_and_stops():
    p = parse("passagem para Buenos Aires dia 20/11 só ida até 1 escala")
    assert p["origin"] == "GRU" and p["dests"] == ["EZE"]
    assert p["stay"] is None and p["max_stops"] == 1 and p["max_price"] is None


def test_pt_iso_date_and_flexibility_in_words():
    p = parse("saindo de CNF para Madri em 2026-12-05, 14 noites, flexibilidade de 2")
    assert (p["origin"], p["dests"], p["depart"]) == ("CNF", ["MAD"], "2026-12-05")
    assert p["stay"] == 14 and p["flex"] == 2


def test_pt_region_any_city_in_europe():
    p = parse("GRU para qualquer cidade da Europa em 10/12, 10 dias")
    assert p["region"] == "europe" and p["dests"] == REGIONS["europe"]


def test_pt_list_of_destinations():
    p = parse("para Paris, Londres ou Roma saindo de CNF em 05/01, 7 dias")
    assert p["origin"] == "CNF" and p["dests"] == ["CDG", "LHR", "FCO"]


# ------------------------------------------------------------------ shared behavior
def test_region_with_month_only_respects_query_limit(monkeypatch):
    monkeypatch.setenv("MAX_CALLS", "80")
    p = parse("from Curitiba to Europe in March, 10 days")
    assert p["origin"] == "CWB" and p["region"] == "europe"
    assert len(p["dests"]) * (2 * p["flex"] + 1) <= 80


def test_origin_removed_from_destinations():
    p = normalize_params({"origin": "GRU", "region": "europe", "depart": "2030-01-10"})
    assert "GRU" not in p["dests"]
    p = normalize_params({"origin": "FOR", "region": "brazil_northeast", "depart": "2030-01-10"})
    assert "FOR" not in p["dests"]


def test_normalize_accepts_comma_list_and_region_aliases():
    p = normalize_params({"origin": "gru", "dest": "lis, mad", "depart": "2030-01-10"})
    assert p["dests"] == ["LIS", "MAD"]
    for alias in ("South America", "América do Sul", "america_do_sul"):
        p = normalize_params({"origin": "GRU", "region": alias, "depart": "2030-01-10"})
        assert p["region"] == "south_america"
    # older Portuguese keys (CLI, saved watches) keep working
    assert normalize_params({"origin": "GRU", "region": "europa",
                             "depart": "2030-01-10"})["region"] == "europe"


@pytest.mark.parametrize("text", ["Orlando", "I want to travel", "quero viajar",
                                  "10/12 for 5 days"])
def test_incomplete_request_gives_clear_error(text):
    with pytest.raises(ValueError, match="couldn't understand"):
        parse(text)


def test_unknown_place_gives_friendly_error():
    with pytest.raises(ValueError, match="I don't know the place 'Lisboa City'"):
        normalize_params({"origin": "GRU", "dest": "LISBOA CITY", "depart": "2030-01-10"})


def test_brazilian_states_map_to_main_airport():
    p = parse("São Paulo to Santa Catarina on Jan 8, 7 days")
    assert (p["origin"], p["dests"]) == ("GRU", ["FLN"])
    p = parse("de Minas Gerais para Bahia em 10/01, 5 dias")
    assert (p["origin"], p["dests"]) == ("CNF", ["SSA"])
    # "para" is the preposition, not the state of Pará
    assert parse("GRU para Lisboa em 10/12, 10 dias")["dests"] == ["LIS"]


def test_domestic_capitals():
    p = parse("from Goiânia to São Luís on Feb 2, one-way")
    assert (p["origin"], p["dests"]) == ("GYN", ["SLZ"])


def test_failing_llm_falls_back_to_rules(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "x")

    def boom(_):
        raise RuntimeError("no network")

    monkeypatch.setattr(parsing, "parse_gemini", boom)
    p, how = parse_request("GRU to Lisbon on 10/12, 10 days")
    assert p["dests"] == ["LIS"] and "fallback" in how


def test_llm_output_is_normalized(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setattr(parsing, "parse_gemini", lambda t: {
        "origin": "gru", "dest": None, "region": "Europe", "depart": "2030-05-10",
        "stay": 8, "flex": 1, "max_stops": None, "max_price": 3500})
    p, how = parse_request("anything")
    assert how == "gemini" and p["dests"] == REGIONS["europe"] and p["max_price"] == 3500.0


def test_parse_rules_only_extracts_without_validating():
    assert parse_rules("Orlando")["dests"] == ["MCO"]


def test_date_with_day_is_not_whole_month():
    assert parse("GRU to Lisbon on 10/12, 10 days")["month"] is None


def test_invalid_month_from_llm_is_ignored():
    p = normalize_params({"origin": "GRU", "dest": "LIS", "depart": "2026-12-15",
                          "month": "december"})
    assert p["month"] is None


def test_past_date_from_llm_rolls_to_next_year():
    past = date.today() - timedelta(days=30)
    p = normalize_params({"origin": "GRU", "dest": "LIS", "depart": past.isoformat(),
                          "month": past.strftime("%Y-%m")})
    d = date.fromisoformat(p["depart"])
    assert d >= date.today() and (d.month, d.year) == (past.month, past.year + 1)
    assert p["month"] == p["depart"][:7]
