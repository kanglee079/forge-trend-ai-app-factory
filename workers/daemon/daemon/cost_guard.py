from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class CostDecision:
    allowed: bool
    reason: str


def check_cost_limit(provider: str, estimated_cost_usd: Decimal = Decimal("0")) -> CostDecision:
    if estimated_cost_usd < 0:
        return CostDecision(False, "Estimated cost cannot be negative.")
    # MVP agents are deterministic and do not spend provider credits.
    # Real LLM adapters should replace this with API key budget lookups.
    return CostDecision(True, f"{provider} allowed by MVP cost guard.")
