"""Flight deal agent: cheap request parsing, search and ranking in plain Python."""
from .parsing import (llm_provider, normalize_params, parse_request, parse_rules,
                      route_label)
from .search import analyze, plan_calls, search_grid

__version__ = "0.3.0"
__all__ = ["analyze", "llm_provider", "normalize_params", "parse_request", "parse_rules",
           "plan_calls", "route_label", "search_grid"]
