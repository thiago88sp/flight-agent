"""Texto amigável para humanos: nomes de cidades e companhias, datas, preços e link de compra."""
import unicodedata
from datetime import date
from urllib.parse import quote_plus

from .geo import CITIES

# Código IATA (aeroporto ou cidade) -> nome para exibir
CITY_NAMES = {
    "GRU": "São Paulo", "CGH": "São Paulo", "VCP": "Campinas", "SAO": "São Paulo",
    "GIG": "Rio de Janeiro", "SDU": "Rio de Janeiro", "RIO": "Rio de Janeiro",
    "BSB": "Brasília", "CNF": "Belo Horizonte", "BHZ": "Belo Horizonte", "SSA": "Salvador",
    "REC": "Recife", "FOR": "Fortaleza", "POA": "Porto Alegre", "CWB": "Curitiba",
    "FLN": "Florianópolis", "NAT": "Natal", "MAO": "Manaus", "MCZ": "Maceió",
    "JPA": "João Pessoa",
    "LIS": "Lisboa", "OPO": "Porto", "MAD": "Madri", "BCN": "Barcelona",
    "CDG": "Paris", "ORY": "Paris", "PAR": "Paris", "LHR": "Londres", "LGW": "Londres",
    "LON": "Londres", "FCO": "Roma", "ROM": "Roma", "AMS": "Amsterdã", "FRA": "Frankfurt",
    "MXP": "Milão", "MIL": "Milão", "ZRH": "Zurique",
    "JFK": "Nova York", "EWR": "Nova York", "NYC": "Nova York", "MIA": "Miami",
    "MCO": "Orlando", "LAX": "Los Angeles", "EZE": "Buenos Aires", "BUE": "Buenos Aires",
    "SCL": "Santiago", "LIM": "Lima", "BOG": "Bogotá", "MVD": "Montevidéu",
    "CUN": "Cancún", "PUJ": "Punta Cana", "PTY": "Cidade do Panamá", "DXB": "Dubai",
    "NRT": "Tóquio", "TYO": "Tóquio",
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

WEEKDAYS = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"]
MONTH_NAMES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto",
               "setembro", "outubro", "novembro", "dezembro"]


def city(code):
    """'MXP' -> 'Milão (MXP)'; códigos desconhecidos ficam como estão."""
    name = CITY_NAMES.get(code)
    return f"{name} ({code})" if name else code


def airline(code):
    return AIRLINES.get(code, code)


def money(value):
    """5534.0 -> 'R$ 5.534' (formato brasileiro, sem centavos)."""
    return "R$ " + f"{value:,.0f}".replace(",", ".")


def day(iso):
    """'2026-12-01' -> 'ter, 01/12'."""
    d = date.fromisoformat(iso)
    return f"{WEEKDAYS[d.weekday()]}, {d:%d/%m}"


def month(ym):
    """'2027-03' -> 'março/2027'."""
    return f"{MONTH_NAMES[int(ym[5:7]) - 1]}/{ym[:4]}"


def stops(n):
    return "voo direto" if n == 0 else f"{n} escala" + ("s" if n > 1 else "")


def nights(offer):
    if not offer.get("return"):
        return None
    return (date.fromisoformat(offer["return"]) - date.fromisoformat(offer["depart"])).days


def trip(offer):
    """'ida ter, 01/12 · volta sex, 11/12 (10 dias)' ou 'só ida ter, 01/12'."""
    if not offer.get("return"):
        return f"só ida {day(offer['depart'])}"
    return f"ida {day(offer['depart'])} · volta {day(offer['return'])} ({nights(offer)} dias)"


def booking_url(origin, offer):
    """Onde fechar a compra: o link exato do Aviasales (preços reais) ou uma busca
    equivalente no Google Flights (preços simulados não têm oferta de verdade)."""
    if offer.get("link"):
        return "https://www.aviasales.com" + offer["link"]
    q = f"Flights to {offer['dest']} from {origin} on {offer['depart']}"
    if offer.get("return"):
        q += f" through {offer['return']}"
    return f"https://www.google.com/travel/flights?q={quote_plus(q)}&curr=BRL&hl=pt-BR"


def booking_site(offer):
    return "Aviasales" if offer.get("link") else "Google Flights"


def to_code(text):
    """Aceita código ('lis') ou nome de cidade ('Lisboa', 'são paulo') e devolve o IATA."""
    t = text.strip()
    folded = "".join(c for c in unicodedata.normalize("NFKD", t.lower())
                     if not unicodedata.combining(c))
    return CITIES.get(folded, t.upper())
