from fastapi import APIRouter, HTTPException

from backend.app.schemas.simulation import ScenarioRequest, StepRequest
from backend.app.sim_session import SESSION, ScenarioParams
from experiments.configs import resources_for

router = APIRouter(prefix="/api/simulation", tags=["simulation"])


@router.post("/scenario")
def create_scenario(req: ScenarioRequest) -> dict:
    resources = req.initial_resources if req.initial_resources is not None else resources_for(req.victim_count)
    params = ScenarioParams(
        policy=req.policy, seed=req.seed, victim_count=req.victim_count, blockage_level=req.blockage_level,
        rescue_agent_count=req.rescue_agent_count, initial_resources=resources, max_time=req.max_time,
        width=req.width, height=req.height, arrival_window=req.arrival_window, comm_loss=req.comm_loss,
        burst_length=req.burst_length,
    )
    return SESSION.create(params)


@router.post("/step")
def step(req: StepRequest) -> dict:
    try:
        return SESSION.step(req.n)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/reset")
def reset() -> dict:
    try:
        return SESSION.reset()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/state")
def get_state() -> dict:
    try:
        return SESSION.state()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/events")
def get_events(since: int = 0, limit: int = 200) -> list[dict]:
    return SESSION.events(since=since, limit=limit)
