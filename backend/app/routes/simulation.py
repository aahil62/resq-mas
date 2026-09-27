from fastapi import APIRouter, HTTPException, Query

from backend.app.schemas.simulation import ScenarioRequest, StepRequest
from backend.app.sim_session import SESSION, ScenarioParams
from experiments.configs import DEFAULT_SEVERITY_SEQUENCE, resources_for
from simulation.environment import ScenarioConfig, VictimStatus
from simulation.simulation import Simulation

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


@router.get("/replay")
def replay(policy: str = Query(pattern="^(no_coordination|claim|mas|mas_iterative|hungarian|cbba)$"),
           seed: int = 11, victim_count: int = Query(default=6, ge=2, le=30),
           rescue_agent_count: int = Query(default=2, ge=1, le=8), width: int = Query(default=15, ge=5, le=30)) -> dict:
    """A complete run recorded frame by frame, for side-by-side playback on
    the landing page. Runs independently of the live session."""
    cfg = ScenarioConfig(seed=seed, width=width, height=width, victim_count=victim_count,
                         severity_sequence=DEFAULT_SEVERITY_SEQUENCE if victim_count == 6 else None,
                         initial_resources=resources_for(victim_count), max_time=1500)
    sim = Simulation(cfg, policy="independent" if policy == "no_coordination" else policy,
                     rescue_agent_count=rescue_agent_count)
    env = sim.environment
    frames = []

    def snap():
        frames.append({
            "t": env.time,
            "units": [[ra.position[0], ra.position[1], ra.current_target or ""] for ra in sim.rescue_agents],
            "rescued": [v.victim_id for v in env.victims.values() if v.status == VictimStatus.RESCUED],
            "duplicates": sim.duplicate_conflicts,
        })

    snap()
    while not env.is_complete() and not sim._is_stalled():
        sim.tick()
        snap()
    return {
        "policy": policy,
        "grid": [[c.value for c in row] for row in env.grid],
        "hospital": list(env.hospital),
        "victims": [{"id": v.victim_id, "position": list(v.position), "severity": v.severity.value}
                    for v in env.victims.values()],
        "frames": frames,
    }
