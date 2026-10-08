import pytest


@pytest.fixture(autouse=True)
def _isolated_env(tmp_path, monkeypatch):
    """Cada teste usa histórico próprio, interpretador por regras e nenhuma credencial."""
    monkeypatch.setenv("FLIGHT_HISTORY", str(tmp_path / "history.jsonl"))
    monkeypatch.setenv("LLM_PROVIDER", "rules")
    monkeypatch.setenv("MAX_CALLS", "80")
    for key in ("TRAVELPAYOUTS_TOKEN", "GEMINI_API_KEY",
                "ANTHROPIC_API_KEY", "OLLAMA_MODEL"):
        monkeypatch.delenv(key, raising=False)
