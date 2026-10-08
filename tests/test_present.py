from flight_agent import present as fmt


def _o(**kw):
    base = {"dest": "LIS", "depart": "2026-12-01", "return": "2026-12-11", "price": 5534.0,
            "airline": "TP", "stops": 1}
    return {**base, **kw}


def test_friendly_formats():
    assert fmt.city("MXP") == "Milan (MXP)" and fmt.city("XYZ") == "XYZ"
    assert fmt.airline("TP") == "TAP Air Portugal" and fmt.airline("ZZ") == "ZZ"
    assert fmt.money(5534.0) == "R$ 5,534"
    assert fmt.day("2026-12-01") == "Tue, Dec 1"
    assert fmt.month("2027-03") == "March 2027"
    assert [fmt.stops(n) for n in (0, 1, 2)] == ["nonstop", "1 stop", "2 stops"]
    assert fmt.trip(_o()) == "out Tue, Dec 1 · back Fri, Dec 11 (10 days)"
    assert fmt.trip(_o(**{"return": None})) == "one-way Tue, Dec 1"


def test_booking_link():
    real = _o(link="/search/SAO0112LIS1?t=abc")
    assert fmt.booking_url("GRU", real) == "https://www.aviasales.com/search/SAO0112LIS1?t=abc"
    assert fmt.booking_site(real) == "Aviasales"
    url = fmt.booking_url("GRU", _o())
    assert url.startswith("https://www.google.com/travel/flights?q=Flights+to+LIS+from+GRU")
    assert "2026-12-11" in url and fmt.booking_site(_o()) == "Google Flights"


def test_city_name_becomes_code():
    assert fmt.to_code("São Paulo") == "GRU"
    assert fmt.to_code(" lisbon ") == fmt.to_code("Lisboa") == "LIS"
    assert fmt.to_code("sao") == "SAO"
