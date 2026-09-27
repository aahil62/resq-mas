from typing import Annotated

from pydantic import BaseModel, Field

from backend.app.schemas.simulation import POLICY_PATTERN


class ExperimentRunRequest(BaseModel):
    victim_count: int = Field(default=6, ge=2, le=60)
    blockage_level: float = Field(default=0.0, ge=0.0, le=0.9)
    base_seed: int = Field(default=1, ge=0)
    n_runs: int = Field(default=10, ge=1, le=100)
    rescue_agent_count: int = Field(default=2, ge=1, le=8)
    max_time: int = Field(default=300, ge=10, le=3000)
    width: int = Field(default=15, ge=5, le=40)
    policies: list[Annotated[str, Field(pattern=POLICY_PATTERN)]] = Field(
        default_factory=lambda: ["no_coordination", "mas"], min_length=1, max_length=6)
    arrival_window: int = Field(default=0, ge=0, le=1000)
    comm_loss: float = Field(default=0.0, ge=0.0, le=1.0)
    burst_length: float | None = Field(default=None, ge=1.0, le=200.0)
