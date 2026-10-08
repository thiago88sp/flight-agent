from flight_agent import present as fmt


def _o(**kw):
    base = {"dest": "LIS", "depart": "2026-12-01", "return": "2026-12-11", "price": 5534.0,
            "airline": "TP", "stops": 1}
    return {**base, **kw}


def test_formatos_amigaveis():
    assert fmt.city("MXP") == "Milão (MXP)" and fmt.city("XYZ") == "XYZ"
    assert fmt.airline("TP") == "TAP Air Portugal" and fmt.airline("ZZ") == "ZZ"
    assert fmt.money(5534.0) == "R$ 5.534"
    assert fmt.day("2026-12-01") == "ter, 01/12"
    assert fmt.month("2027-03") == "março/2027"
    assert [fmt.stops(n) for n in (0, 1, 2)] == ["voo direto", "1 escala", "2 escalas"]
    assert fmt.trip(_o()) == "ida ter, 01/12 · volta sex, 11/12 (10 dias)"
    assert fmt.trip(_o(**{"return": None})) == "só ida ter, 01/12"


def test_link_de_compra():
    real = _o(link="/search/SAO0112LIS1?t=abc")
    assert fmt.booking_url("GRU", real) == "https://www.aviasales.com/search/SAO0112LIS1?t=abc"
    assert fmt.booking_site(real) == "Aviasales"
    url = fmt.booking_url("GRU", _o())
    assert url.startswith("https://www.google.com/travel/flights?q=Flights+to+LIS+from+GRU")
    assert "2026-12-11" in url and fmt.booking_site(_o()) == "Google Flights"


def test_nome_de_cidade_vira_codigo():
    assert fmt.to_code("São Paulo") == "GRU"
    assert fmt.to_code(" lisboa ") == "LIS"
    assert fmt.to_code("sao") == "SAO"
