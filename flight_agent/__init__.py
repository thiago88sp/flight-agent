"""Agente de busca de passagens: interpretação barata, busca e ranking em Python puro."""
from .parsing import (llm_provider, normalize_params, parse_request, parse_rules,
                      route_label)
from .search import analyze, plan_calls, search_grid

__version__ = "0.2.0"
__all__ = ["analyze", "llm_provider", "normalize_params", "parse_request", "parse_rules",
           "plan_calls", "route_label", "search_grid"]
