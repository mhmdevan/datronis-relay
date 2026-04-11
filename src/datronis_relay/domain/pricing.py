from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ModelPricing:
    """Per-million-token pricing for one Claude model.

    Kept in the domain layer (not config) so `CostTracker` doesn't depend on
    pydantic. The config loader converts its validated pydantic shape into
    this plain dataclass at composition time.
    """

    input_usd_per_mtok: float
    output_usd_per_mtok: float

    def cost(self, tokens_in: int, tokens_out: int) -> float:
        return (
            (tokens_in / 1_000_000.0) * self.input_usd_per_mtok
            + (tokens_out / 1_000_000.0) * self.output_usd_per_mtok
        )
