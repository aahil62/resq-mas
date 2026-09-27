from pydantic import BaseModel, Field

# "no_coordination" is the original name of the independent protocol; both are accepted.
POLICY_PATTERN = "^(no_coordination|independent|claim|mas|mas_iterative|hungarian|cbba)$"


class ScenarioRequest(BaseModel):
    policy: str = Field(pattern=POLICY_PATTERN)
    seed: int = 11
    victim_count: int = Field(default=6, ge=2, le=60)
    blockage_level: float = Field(default=0.0, ge=0.0, le=0.9)
    rescue_agent_count: int = Field(default=2, ge=1, le=8)
    initial_resources: int | None = Field(default=None, ge=0)
    max_time: int = Field(default=300, ge=10, le=3000)
    width: int = Field(default=15, ge=5, le=40)
    height: int = Field(default=15, ge=5, le=40)
    arrival_window: int = Field(default=0, ge=0, le=1000)
    comm_loss: float = Field(default=0.0, ge=0.0, le=1.0)
    burst_length: float | None = Field(default=None, ge=1.0, le=200.0)


class StepRequest(BaseModel):
    n: int = Field(default=1, ge=1, le=500)
