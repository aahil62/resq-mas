from pydantic import BaseModel, Field


class ExperimentRunRequest(BaseModel):
    victim_count: int = Field(default=6, ge=2, le=60)
    blockage_level: float = Field(default=0.0, ge=0.0, le=0.9)
    base_seed: int = Field(default=1, ge=0)
    n_runs: int = Field(default=10, ge=1, le=100)
    rescue_agent_count: int = Field(default=2, ge=1, le=6)
    max_time: int = Field(default=300, ge=10, le=2000)
