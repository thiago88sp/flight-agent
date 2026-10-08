"""Human-friendly text: city and airline names, dates, prices and the booking link."""
import unicodedata
from datetime import date
from urllib.parse import quote_plus

from .geo import CITIES

# IATA code (airport or city) -> display name
CITY_NAMES = {
    "GRU": "São Paulo", "CGH": "São Paulo", "VCP": "Campinas", "SAO": "São Paulo",
    "GIG": "Rio de Janeiro", "SDU": "Rio de Janeiro", "RIO": "Rio de Janeiro",
    "BSB": "Brasília", "CNF": "Belo Horizonte", "BHZ": "Belo Horizonte", "SSA": "Salvador",
    "REC": "Recife", "FOR": "Fortaleza", "POA": "Porto Alegre", "CWB": "Curitiba",
    "FLN": "Florianópolis", "NAT": "Natal", "MAO": "Manaus", "MCZ": "Maceió",
    "JPA": "João Pessoa",
    "LIS": "Lisbon", "OPO": "Porto", "MAD": "Madrid", "BCN": "Barcelona",
    "CDG": "Paris", "ORY": "Paris", "PAR": "Paris", "LHR": "London", "LGW": "London",
    "LON": "London", "FCO": "Rome", "ROM": "Rome", "AMS": "Amsterdam", "FRA": "Frankfurt",
    "MXP": "Milan", "MIL": "Milan", "ZRH": "Zurich",
    "JFK": "New York", "EWR": "New York", "NYC": "New York", "MIA": "Miami",
    "MCO": "Orlando", "LAX": "Los Angeles", "EZE": "Buenos Aires", "BUE": "Buenos Aires",
    "SCL": "Santiago", "LIM": "Lima", "BOG": "Bogotá", "MVD": "Montevideo",
    "CUN": "Cancún", "PUJ": "Punta Cana", "PTY": "Panama City", "DXB": "Dubai",
    "NRT": "Tokyo", "TYO": "Tokyo",
}

AIRLINES = {
    "LA": "LATAM", "JJ": "LATAM", "G3": "GOL", "AD": "Azul", "TP": "TAP Air Portugal",
    "UX": "Air Europa", "IB": "Iberia", "AF": "Air France", "KL": "KLM",
    "LH": "Lufthansa", "LX": "Swiss", "BA": "British Airways", "AZ": "ITA Airways",
    "TK": "Turkish Airlines", "EK": "Emirates", "QR": "Qatar Airways", "ET": "Ethiopian",
    "AT": "Royal Air Maroc", "DT": "TAAG Angola", "AA": "American Airlines",
    "UA": "United", "DL": "Delta", "CM": "Copa Airlines", "AV": "Avianca",
    "AR": "Aerolíneas Argentinas", "H2": "Sky Airline", "JA": "JetSMART",
    "AC": "Air Canada", "AM": "Aeroméxico", "VY": "Vueling", "FR": "Ryanair",
    "U2": "easyJet", "LO": "LOT", "OS": "Austrian", "SN": "Brussels Airlines",
    "CA": "Air China", "MS": "EgyptAir", "SA": "South African", "TA": "TACA",
}

WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
MONTH_ABBR = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
MONTH_NAMES = ["January", "February", "March", "April", "May", "June", "July", "August",
               "September", "October", "November", "December"]


def city(code):
    """'MXP' -> 'Milan (MXP)'; unknown codes are returned as they are."""
    name = CITY_NAMES.get(code)
    return f"{name} ({code})" if name else code


def airline(code):
    return AIRLINES.get(code, code)


def money(value):
    """5534.0 -> 'R$ 5,534' (prices are in Brazilian reais, no cents)."""
    return f"R$ {value:,.0f}"


def day(iso):
    """'2026-12-01' -> 'Tue, Dec 1'."""
    d = date.fromisoformat(iso)
    return f"{WEEKDAYS[d.weekday()]}, {MONTH_ABBR[d.month - 1]} {d.day}"


def month(ym):
    """'2027-03' -> 'March 2027'."""
    return f"{MONTH_NAMES[int(ym[5:7]) - 1]} {ym[:4]}"


def stops(n):
    return "nonstop" if n == 0 else f"{n} stop" + ("s" if n > 1 else "")


def nights(offer):
    if not offer.get("return"):
        return None
    return (date.fromisoformat(offer["return"]) - date.fromisoformat(offer["depart"])).days


def trip(offer):
    """'out Tue, Dec 1 · back Fri, Dec 11 (10 days)' or 'one-way Tue, Dec 1'."""
    if not offer.get("return"):
        return f"one-way {day(offer['depart'])}"
    return f"out {day(offer['depart'])} · back {day(offer['return'])} ({nights(offer)} days)"


def booking_url(origin, offer):
    """Where to buy: the exact Aviasales itinerary (real prices) or the same search on Google
    Flights (simulated prices have no real offer behind them)."""
    if offer.get("link"):
        return "https://www.aviasales.com" + offer["link"]
    q = f"Flights to {offer['dest']} from {origin} on {offer['depart']}"
    if offer.get("return"):
        q += f" through {offer['return']}"
    return f"https://www.google.com/travel/flights?q={quote_plus(q)}&curr=BRL&hl=en"


def booking_site(offer):
    return "Aviasales" if offer.get("link") else "Google Flights"


def to_code(text):
    """Accept a code ('lis') or a city name ('Lisbon', 'são paulo') and return the IATA code."""
    t = text.strip()
    folded = "".join(c for c in unicodedata.normalize("NFKD", t.lower())
                     if not unicodedata.combining(c))
    return CITIES.get(folded, t.upper())
