import pytest

import flight_agent.config  # noqa: F401  lê o .env já aqui, para o fixture limpar as chaves depois


@pytest.fixture(autouse=True)
def _isolated_env(tmp_path, monkeypatch):
    """Cada teste usa histórico e monitoramentos próprios, regras locais e nenhuma credencial."""
    monkeypatch.setenv("FLIGHT_HISTORY", str(tmp_path / "history.jsonl"))
    monkeypatch.setenv("LLM_PROVIDER", "rules")
    monkeypatch.setenv("MAX_CALLS", "80")
    monkeypatch.setenv("WATCHES_FILE", str(tmp_path / "watches.json"))
    monkeypatch.setenv("WATCH_STATE", str(tmp_path / "watch_state.json"))
    for key in ("TRAVELPAYOUTS_TOKEN", "GEMINI_API_KEY", "ANTHROPIC_API_KEY", "OLLAMA_MODEL",
                "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "WATCHES"):
        monkeypatch.delenv(key, raising=False)
