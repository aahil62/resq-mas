from pydantic import BaseModel, Field


class ScenarioRequest(BaseModel):
    policy: str = Field(pattern="^(mas|no_coordination)$")
    seed: int = 11
    victim_count: int = Field(default=6, ge=2, le=60)
    blockage_level: float = Field(default=0.0, ge=0.0, le=0.9)
    rescue_agent_count: int = Field(default=2, ge=1, le=6)
    initial_resources: int | None = Field(default=None, ge=0)
    max_time: int = Field(default=300, ge=10, le=2000)
    width: int = Field(default=15, ge=5, le=40)
    height: int = Field(default=15, ge=5, le=40)


class StepRequest(BaseModel):
    n: int = Field(default=1, ge=1, le=500)
