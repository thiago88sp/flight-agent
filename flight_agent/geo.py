"""Geographic data: known cities and regions (lists of destination airports).

City names are accepted in English and Portuguese, lowercase and without accents.
"""

# City name (lowercase, no accents) -> IATA airport code
CITIES = {
    # Brazil
    "sao paulo": "GRU", "guarulhos": "GRU", "congonhas": "CGH", "campinas": "VCP",
    "rio de janeiro": "GIG", "rio": "GIG", "brasilia": "BSB", "belo horizonte": "CNF",
    "salvador": "SSA", "recife": "REC", "fortaleza": "FOR", "porto alegre": "POA",
    "curitiba": "CWB", "florianopolis": "FLN", "natal": "NAT", "manaus": "MAO",
    "maceio": "MCZ", "joao pessoa": "JPA", "belem": "BEL", "goiania": "GYN",
    "sao luis": "SLZ", "cuiaba": "CGB", "campo grande": "CGR", "teresina": "THE",
    "porto velho": "PVH", "boa vista": "BVB", "aracaju": "AJU", "palmas": "PMW",
    "vitoria": "VIX", "macapa": "MCP", "rio branco": "RBR",
    # Europe
    "lisbon": "LIS", "lisboa": "LIS", "porto": "OPO", "oporto": "OPO",
    "madrid": "MAD", "madri": "MAD", "barcelona": "BCN", "paris": "CDG",
    "london": "LHR", "londres": "LHR", "rome": "FCO", "roma": "FCO",
    "amsterdam": "AMS", "amsterda": "AMS", "frankfurt": "FRA", "milan": "MXP", "milao": "MXP",
    "zurich": "ZRH", "zurique": "ZRH",
    # North America
    "new york": "JFK", "nova york": "JFK", "miami": "MIA", "orlando": "MCO",
    "los angeles": "LAX",
    # South America
    "buenos aires": "EZE", "santiago": "SCL", "lima": "LIM", "bogota": "BOG",
    "montevideo": "MVD", "montevideu": "MVD",
    # Central America and Caribbean
    "cancun": "CUN", "punta cana": "PUJ", "panama city": "PTY", "panama": "PTY",
    # Asia and Middle East
    "dubai": "DXB", "tokyo": "NRT", "toquio": "NRT",
}

# Brazilian state (lowercase, no accents) -> main airport, so "São Paulo to Santa Catarina" works.
# "São Paulo" and "Rio de Janeiro" are already cities above.
STATES = {
    "acre": "RBR", "alagoas": "MCZ", "amapa": "MCP", "amazonas": "MAO", "bahia": "SSA",
    "ceara": "FOR", "distrito federal": "BSB", "espirito santo": "VIX", "goias": "GYN",
    "maranhao": "SLZ", "mato grosso": "CGB", "mato grosso do sul": "CGR",
    "minas gerais": "CNF", "minas": "CNF", "para": "BEL", "paraiba": "JPA", "parana": "CWB",
    "pernambuco": "REC", "piaui": "THE", "rio grande do norte": "NAT",
    "rio grande do sul": "POA", "rondonia": "PVH", "roraima": "BVB",
    "santa catarina": "FLN", "sergipe": "AJU", "tocantins": "PMW",
}
# "para" is also the Portuguese word for "to", so the chat only accepts it in the form
CHAT_STATES = {k: v for k, v in STATES.items() if k != "para"}

# Internal key -> airports searched when the request is "any city in <region>"
REGIONS = {
    "europe": ["LIS", "MAD", "BCN", "CDG", "LHR", "FCO", "AMS", "FRA", "MXP", "ZRH", "OPO"],
    "south_america": ["EZE", "SCL", "LIM", "BOG", "MVD"],
    "usa": ["MIA", "MCO", "JFK", "LAX"],
    "caribbean": ["CUN", "PUJ", "PTY"],
    "brazil_northeast": ["REC", "SSA", "FOR", "NAT", "MCZ", "JPA"],
}

REGION_LABELS = {
    "europe": "Europe", "south_america": "South America", "usa": "United States",
    "caribbean": "Caribbean / Central America", "brazil_northeast": "Northeast Brazil",
}

# Patterns (over lowercase text without accents) that point to each region, EN and PT
REGION_PATTERNS = [
    (r"\beurope\b|\beuropa\b", "europe"),
    (r"\bsouth america\b|\blatin america\b|\bamerica do sul\b|\bamerica latina\b|\bsul.americ",
     "south_america"),
    (r"\bunited states\b|\bthe us\b|\busa\b|\bestados unidos\b|\beua\b", "usa"),
    (r"\bcaribbean\b|\bcentral america\b|\bcaribe\b|\bamerica central\b", "caribbean"),
    (r"\bnortheast brazil\b|\bbrazil(?:ian)? northeast\b|\bnordeste\b", "brazil_northeast"),
]

# Names accepted when an LLM, the CLI or an older watch uses a label or the old Portuguese key
REGION_ALIASES = {
    "europe": "europe", "europa": "europe",
    "south america": "south_america", "latin america": "south_america",
    "america do sul": "south_america", "america latina": "south_america",
    "america_do_sul": "south_america",
    "united states": "usa", "us": "usa", "estados unidos": "usa", "eua": "usa",
    "caribbean": "caribbean", "central america": "caribbean", "caribe": "caribbean",
    "america central": "caribbean", "caribbean / central america": "caribbean",
    "northeast brazil": "brazil_northeast", "brazil northeast": "brazil_northeast",
    "nordeste": "brazil_northeast",
}
