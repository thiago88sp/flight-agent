"""Dados geográficos: cidades conhecidas e regiões (listas de aeroportos de destino)."""

# Nomes sem acento e em minúsculas -> código IATA
CITIES = {
    "sao paulo": "GRU", "guarulhos": "GRU", "congonhas": "CGH", "campinas": "VCP",
    "rio de janeiro": "GIG", "rio": "GIG", "brasilia": "BSB", "belo horizonte": "CNF",
    "salvador": "SSA", "recife": "REC", "fortaleza": "FOR", "porto alegre": "POA",
    "curitiba": "CWB", "florianopolis": "FLN", "natal": "NAT", "manaus": "MAO",
    "maceio": "MCZ", "joao pessoa": "JPA",
    "lisboa": "LIS", "porto": "OPO", "madri": "MAD", "madrid": "MAD",
    "barcelona": "BCN", "paris": "CDG", "londres": "LHR", "roma": "FCO",
    "amsterda": "AMS", "frankfurt": "FRA", "milao": "MXP", "zurique": "ZRH",
    "nova york": "JFK", "new york": "JFK", "miami": "MIA", "orlando": "MCO",
    "los angeles": "LAX", "buenos aires": "EZE", "santiago": "SCL", "lima": "LIM",
    "bogota": "BOG", "montevideu": "MVD", "cancun": "CUN", "punta cana": "PUJ",
    "panama": "PTY", "dubai": "DXB", "toquio": "NRT", "tokyo": "NRT",
}

# Chave interna -> aeroportos consultados quando o pedido é "qualquer cidade de <região>"
REGIONS = {
    "europa": ["LIS", "MAD", "BCN", "CDG", "LHR", "FCO", "AMS", "FRA", "MXP", "ZRH", "OPO"],
    "america_do_sul": ["EZE", "SCL", "LIM", "BOG", "MVD"],
    "eua": ["MIA", "MCO", "JFK", "LAX"],
    "caribe": ["CUN", "PUJ", "PTY"],
    "nordeste": ["REC", "SSA", "FOR", "NAT", "MCZ", "JPA"],
}

REGION_LABELS = {
    "europa": "Europa", "america_do_sul": "América do Sul", "eua": "Estados Unidos",
    "caribe": "Caribe / América Central", "nordeste": "Nordeste do Brasil",
}

# Padrões (sobre texto sem acento, minúsculo) que indicam cada região
REGION_PATTERNS = [
    (r"\beuropa\b", "europa"),
    (r"\bamerica do sul\b|\bamerica latina\b|\bsul.americ", "america_do_sul"),
    (r"\bestados unidos\b|\beua\b|\busa\b", "eua"),
    (r"\bcaribe\b|\bamerica central\b", "caribe"),
    (r"\bnordeste\b", "nordeste"),
]

# Apelidos aceitos quando um LLM devolve o nome da região em vez da chave interna
REGION_ALIASES = {
    "europa": "europa", "america do sul": "america_do_sul", "america latina": "america_do_sul",
    "estados unidos": "eua", "eua": "eua", "usa": "eua", "caribe": "caribe",
    "america central": "caribe", "nordeste": "nordeste",
}
