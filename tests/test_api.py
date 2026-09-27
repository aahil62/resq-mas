"""API tests for the dashboard backend: every protocol can be driven live,
the realism knobs are accepted, the study summary is served, and the
custom-experiment endpoint compares protocols on paired worlds."""

import os

import pytest

try:
    from fastapi.testclient import TestClient
except RuntimeError:  # the installed Starlette needs an HTTP client package for TestClient
    pytest.skip("FastAPI TestClient dependency not installed", allow_module_level=True)

from backend.app.main import app

client = TestClient(app)
ALL = ["no_coordination", "claim", "mas", "mas_iterative", "hungarian", "cbba"]


@pytest.mark.parametrize("policy", ALL)
def test_every_protocol_runs_live_to_completion(policy):
    s = client.post("/api/simulation/scenario", json={"policy": policy, "rescue_agent_count": 3}).json()
    assert s["policy"] == policy and len(s["units"]) == 3
    s = client.post("/api/simulation/step", json={"n": 500}).json()
    assert s["completed"] and s["metrics"]["victims_rescued"] == s["metrics"]["victims_total"]


def test_legacy_two_mode_demo_is_unchanged():
    client.post("/api/simulation/scenario", json={"policy": "no_coordination"})
    nc = client.post("/api/simulation/step", json={"n": 500}).json()
    client.post("/api/simulation/scenario", json={"policy": "mas"})
    mas = client.post("/api/simulation/step", json={"n": 500}).json()
    assert (nc["time"], nc["metrics"]["duplicate_conflicts"]) == (115, 6)
    assert (mas["time"], mas["metrics"]["duplicate_conflicts"]) == (60, 0)


def test_arrivals_hide_unreported_victims_and_loss_reports_channel_state():
    s = client.post("/api/simulation/scenario", json={
        "policy": "cbba", "victim_count": 12, "rescue_agent_count": 4, "width": 20, "height": 20,
        "arrival_window": 200, "comm_loss": 0.5, "burst_length": 5, "max_time": 2000}).json()
    assert s["metrics"]["victims_known"] < 12
    assert all("appeared" in v for v in s["victims"]) and all("channel_ok" in u for u in s["units"])
    s = client.post("/api/simulation/step", json={"n": 500}).json()
    s = client.post("/api/simulation/step", json={"n": 500}).json()
    assert s["completed"] and s["metrics"]["victims_known"] == 12


def test_unknown_protocol_and_too_many_agents_are_rejected():
    assert client.post("/api/simulation/scenario", json={"policy": "telepathy"}).status_code == 422
    assert client.post("/api/simulation/scenario", json={"policy": "mas", "rescue_agent_count": 9}).status_code == 422
    assert client.post("/api/experiments/run", json={"policies": ["telepathy"]}).status_code == 422


def test_custom_experiment_is_paired_across_protocols():
    r = client.post("/api/experiments/run", json={"n_runs": 3, "victim_count": 8, "rescue_agent_count": 3,
                                                  "policies": ["no_coordination", "mas", "cbba"]}).json()
    assert r["baseline"] == "no_coordination" and set(r["per_policy"]) == {"no_coordination", "mas", "cbba"}
    assert r["paired"]["mas"]["wins"] + r["paired"]["mas"]["ties"] + r["paired"]["mas"]["losses"] == 3
    assert r["per_policy"]["mas"]["duplicate_conflicts"]["mean"] == 0


@pytest.mark.skipif(not os.path.exists(os.path.join(os.path.dirname(__file__), "..", "results", "study", "stats.json")),
                    reason="study results not generated")
def test_study_summary_matches_paper_headlines():
    d = client.get("/api/experiments/study").json()
    e1 = {r["policy"]: r for r in d["e1"]}
    gain = 1 - e1["mas"]["completion_time"]["mean"] / e1["no_coordination"]["completion_time"]["mean"]
    assert abs(gain - 0.290) < 0.005
    three = [b for b in d["three_beats_eight"] if b["coordinated_agents"] == 3]
    assert len(three) == 3 and all(b["coordinated_T"] < b["independent8_T"] for b in three)
