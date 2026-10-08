"""Configuração por variáveis de ambiente (com .env opcional, sem dependências extras)."""
import os
from pathlib import Path


def load_dotenv(path=".env"):
    """Lê KEY=VALUE de um .env sem sobrescrever variáveis já definidas no ambiente."""
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_dotenv()

# Modelos usados só se o interpretador correspondente for escolhido
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
ANTHROPIC_MODEL = os.getenv("PARSER_MODEL", "claude-haiku-5-5")


# Lidos a cada chamada (facilita testes e mudanças sem reiniciar)
def history_file() -> Path:
    return Path(os.getenv("FLIGHT_HISTORY", "price_history.jsonl"))


def max_calls() -> int:
    return int(os.getenv("MAX_CALLS", "80"))


def stay_tolerance() -> int:
    """± dias aceitos na estadia quando o provedor busca por mês (cache esparso)."""
    return int(os.getenv("STAY_TOLERANCE", "3"))


def default_origin() -> str:
    return os.getenv("DEFAULT_ORIGIN", "GRU").upper()


def drop_alert_pct() -> float:
    return float(os.getenv("DROP_ALERT_PCT", "10"))
