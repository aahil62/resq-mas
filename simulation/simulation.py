"""The simulation loop: instantiates Medical, Logistics, Rescue A, Rescue B
around a SharedState blackboard and steps them through an Environment.

One class, `Simulation`, drives both modes -- `coordinate=True` (MAS) and
`coordinate=False` (No Coordination) -- because they are the same system
with exactly one behavioural difference (see agents/rescue.py and the
`tick()` method below): whether conflicting proposals are resolved before
either rescue agent commits to a target, or each commits unconditionally.
Everything else -- the environment, the agents, BFS routing, resource
handling -- is identical code for both modes, which is what makes the
comparison fair.

Per tick:
 1. apply scheduled blockage events
 2. Medical Agent registers victims (once) and republishes priority
 3. Logistics Agent resolves last tick's resource requests
 4. rescue agents evaluate candidates and propose/select a target
 5. MAS only: conflicts among this tick's proposals are resolved
 6. targets are committed (resolved winners for MAS; unconditionally for
    No Coordination) and BFS routes are planned
 7. routes are re-validated / replanned if a known blockage now blocks them
 8. actions are executed (movement, resource requests, pickup, delivery)
 9. a tick-level check logs any victim two agents are simultaneously,
    genuinely committed to (the "duplicate_conflicts" metric)
 10. victim waiting times are updated
 11. repeat until every victim is rescued or max_time is reached
"""

from __future__ import annotations

import random

from simulation.agents.logistics import LogisticsAgent
from simulation.agents.medical import MedicalTriageAgent
from simulation.agents.rescue import RescueAgent, WorldMap
from simulation.coordination.messages import Event, EventType
from simulation.coordination.shared_state import SharedState
from simulation.coordination.task_allocation import (
    Proposal, UtilityWeights, optimal_assignment, resolve_conflicts,
)
from simulation.environment import CellType, Environment, ScenarioConfig, VictimStatus
from simulation.metrics.metrics import RunResult
from simulation.search.bfs import bfs_distances

# Task-allocation protocols, weakest to strongest information sharing.
#   independent   -- no communication: commit to own best target (the
#                    original "No Coordination" mode)
#   claim         -- broadcast a claim after committing; others skip claimed
#                    victims, but same-tick choices are not negotiated
#   mas           -- claim + one round of propose/resolve per tick; a
#                    loser idles until the next tick (the original MAS mode)
#   mas_iterative -- claim + repeated propose/resolve rounds within the
#                    tick until every idle agent holds a target or none is
#                    left (a sequential single-item auction)
#   hungarian     -- centralized reference: each tick, idle agents are
#                    matched to unclaimed victims by maximum total utility
#   cbba          -- consensus-based bundle algorithm (Choi et al.; Buckman
#                    et al.): every agent, busy or idle, bids on a bundle of up
#                    to `cbba_bundle` future victims; bids are reconciled by
#                    max-consensus rounds and idle agents commit to the head
#                    of their converged bundle
POLICIES = ("independent", "claim", "mas", "mas_iterative", "hungarian", "cbba")


def _build_world_map(environment: Environment) -> WorldMap:
    static_blocked = frozenset(
        (r, c)
        for r in range(environment.config.height)
        for c in range(environment.config.width)
        if environment.grid[r][c] == CellType.BUILDING
    )
    return WorldMap(
        width=environment.config.width, height=environment.config.height,
        static_blocked=static_blocked, hospital=environment.hospital, depots=list(environment.depots),
    )


class Simulation:
    def __init__(self, config: ScenarioConfig, coordinate: bool | None = None, rescue_agent_count: int = 2,
                 weights: UtilityWeights | None = None, scenario_name: str = "default",
                 policy: str | None = None, comm_loss: float = 0.0, burst_length: float | None = None,
                 cbba_bundle: int = 3):
        if policy is None:
            policy = "mas" if coordinate else "independent"
        if policy not in POLICIES:
            raise ValueError(f"unknown policy {policy!r}; expected one of {POLICIES}")
        self.policy = policy
        self.coordinate = policy != "independent"
        self.comm_loss = comm_loss
        # Loss model. burst_length=None: every broadcast is lost independently
        # with probability comm_loss (Bernoulli erasure). Otherwise each
        # agent's uplink is a two-state Gilbert-Elliott channel stepped once
        # per tick: in the Bad state all of that agent's broadcasts are lost,
        # in the Good state none are. Transition probabilities are set so the
        # long-run loss rate equals comm_loss and Bad spells last burst_length
        # ticks on average.
        self.burst_length = burst_length
        self._channel_bad: dict[str, bool] = {}
        self.cbba_bundle = cbba_bundle
        # Separate stream from the scenario RNG so lossy runs share the
        # exact same world as loss-free ones.
        self._loss_rng = random.Random(config.seed * 7919 + 17)
        self.scenario_name = scenario_name
        self.environment = Environment(config)
        self.shared_state = SharedState()
        self.medical = MedicalTriageAgent("medical")
        self.logistics = LogisticsAgent("logistics")

        world_map = _build_world_map(self.environment)
        names = self._agent_names(rescue_agent_count)
        starts = self.environment.depots or [(0, 0)]
        self.rescue_agents = [
            RescueAgent(name, world_map, coordinate=self.coordinate, weights=weights,
                        start_position=starts[i % len(starts)])
            for i, name in enumerate(names)
        ]
        for ra in self.rescue_agents:
            self.environment.units[ra.agent_id] = ra.position
            self._channel_bad[ra.agent_id] = (burst_length is not None and comm_loss > 0
                                              and self._loss_rng.random() < comm_loss)

        self.duplicate_conflicts = 0
        self._logged_duplicate_victims: set[str] = set()
        self.messages = 0         # coordination broadcasts (proposals, claims, bids, conflict notices)
        self.message_payload = 0  # scalar values carried by those broadcasts
        self.idle_ticks = 0       # agent-ticks spent idle while unrescued victims remained
        self.consensus_rounds = 0  # CBBA only: build/broadcast rounds summed over all auctions

    @staticmethod
    def _agent_names(n: int) -> list[str]:
        if n <= 2:
            return ["rescue_a", "rescue_b"][:max(n, 1)]
        return [f"rescue_{chr(ord('a') + i)}" for i in range(n)]

    def tick(self) -> None:
        t = self.environment.time
        self._step_channels()
        for e in self.environment.apply_scheduled_events():
            self.environment.event_history.append({"timestamp": t, **e})
            # Blockages are ground truth known to both modes immediately --
            # there is no sensor agent in this project (the point under
            # study is coordination, not information latency).
            self.shared_state.publish(Event(timestamp=t, source="system", type=EventType(e["type"]),
                                             payload=e["payload"]))

        self.medical.step(self.environment, self.shared_state, t)
        self.logistics.step(self.environment, self.shared_state, t)

        for ra in self.rescue_agents:
            ra.timestamp = t
            ra.observe(self.environment)
            ra.update_state(None)
            ra.communicate(self.shared_state)

        getattr(self, f"_allocate_{self.policy}")(t)

        for ra in self.rescue_agents:
            ra.decide(self.shared_state)
        for ra in self.rescue_agents:
            ra.act(self.environment, self.shared_state)

        self._check_duplicate_targets(t)
        if any(v.status != VictimStatus.RESCUED for v in self.environment.victims.values()):
            self.idle_ticks += sum(ra.status == "idle" for ra in self.rescue_agents)
        self.environment.tick_waiting_times()
        self.environment.advance_time()

    # -- task-allocation protocols ------------------------------------------
    def _step_channels(self) -> None:
        if self.burst_length is None or self.comm_loss <= 0:
            return
        p_bg = 1.0 / self.burst_length
        p_gb = min(1.0, self.comm_loss * p_bg / (1.0 - self.comm_loss)) if self.comm_loss < 1 else 1.0
        for aid, bad in self._channel_bad.items():
            self._channel_bad[aid] = (self._loss_rng.random() >= p_bg) if bad else (self._loss_rng.random() < p_gb)

    def _lost(self, agent_id: str) -> bool:
        if self.comm_loss <= 0:
            return False
        if self.burst_length is not None:
            return self._channel_bad[agent_id]
        return self._loss_rng.random() < self.comm_loss

    def _commit(self, ra: RescueAgent, victim_id: str | None) -> None:
        ra.receive_assignment(self.shared_state, victim_id, self.environment)
        if victim_id is None or not self.coordinate:
            return
        self.messages += 1
        self.message_payload += 1
        if self._lost(ra.agent_id):
            self.shared_state.hidden_claims.add(victim_id)
        else:
            self.shared_state.hidden_claims.discard(victim_id)

    def _allocate_independent(self, t: int) -> None:
        # No communication: every selection is committed unconditionally.
        # If two agents' best candidate is the same victim, both commit.
        for ra in self.rescue_agents:
            if ra.pending_proposal is not None:
                self._commit(ra, ra.pending_proposal.victim_id)

    def _allocate_claim(self, t: int) -> None:
        # Agents skip victims already claimed on the blackboard, but choices
        # made in the same tick are committed without any exchange.
        self._allocate_independent(t)

    def _exchange(self, t: int, proposals: list[tuple[RescueAgent, Proposal]]) -> dict[str, str]:
        """One propose/resolve round. A proposal whose broadcast is lost
        never reaches the resolver, so its sender -- hearing no objection --
        commits to it unilaterally. Returns victim_id -> winning agent_id."""
        delivered, unheard = [], []
        for ra, p in proposals:
            self.messages += 1
            self.message_payload += 2  # (victim_id, utility)
            (unheard if self._lost(ra.agent_id) else delivered).append((ra, p))
        resolution = resolve_conflicts([p for _, p in delivered])
        for c in resolution.conflicts:
            self.messages += 1
            self.message_payload += 1
            self.shared_state.publish(Event(timestamp=t, source="coordinator",
                                             type=EventType.TASK_CONFLICT, payload=c))
        for ra, p in unheard:
            self._commit(ra, p.victim_id)
        return resolution.assignments

    def _allocate_mas(self, t: int) -> None:
        # One round: resolve conflicts BEFORE anyone commits; a loser stays
        # idle this tick and proposes its next-best candidate next tick.
        proposals = [(ra, ra.pending_proposal) for ra in self.rescue_agents if ra.pending_proposal]
        winners = self._exchange(t, proposals)
        for ra, p in proposals:
            if winners.get(p.victim_id) == ra.agent_id:
                self._commit(ra, p.victim_id)
            elif ra.status == "idle":
                self._commit(ra, None)

    def _allocate_mas_iterative(self, t: int) -> None:
        # Repeat propose/resolve within the tick: losers immediately
        # re-propose their best remaining victim, excluding ones already
        # won this tick, until nobody is left without a target.
        proposals = [(ra, ra.pending_proposal) for ra in self.rescue_agents if ra.pending_proposal]
        taken: set[str] = set()
        while proposals:
            winners = self._exchange(t, proposals)
            losers = []
            for ra, p in proposals:
                if ra.status != "idle":
                    continue  # committed unilaterally after a lost proposal
                if winners.get(p.victim_id) == ra.agent_id:
                    self._commit(ra, p.victim_id)
                    taken.add(p.victim_id)
                else:
                    losers.append(ra)
            taken |= {ra.current_target for ra in self.rescue_agents if ra.current_target}
            proposals = []
            for ra in losers:
                ranked = ra.rank_candidates(self.shared_state, exclude=taken)
                if not ranked:
                    continue
                kv, dist, util = ranked[0]
                proposals.append((ra, Proposal(agent_id=ra.agent_id, victim_id=kv.victim_id, utility=util,
                                                travel_distance=dist, timestamp=t)))
                self.shared_state.publish(Event(
                    timestamp=t, source=ra.agent_id, type=EventType.TASK_PROPOSED,
                    payload={"victim_id": kv.victim_id, "utility": util, "travel_distance": dist, "round": "retry"},
                ))

    def _allocate_hungarian(self, t: int) -> None:
        # Centralized reference: every idle agent reports its full utility
        # row; a coordinator returns the max-total-utility matching.
        idle = [ra for ra in self.rescue_agents if ra.pending_proposal is not None]
        if not idle:
            return
        rows = {ra.agent_id: {kv.victim_id: (u, d) for kv, d, u in ra.rank_candidates(self.shared_state)}
                for ra in idle}
        for ra in idle:
            self.messages += 2  # utility report up, assignment down
            self.message_payload += 2 * len(rows[ra.agent_id]) + 1
        matching = optimal_assignment(rows)
        for ra in idle:
            self._commit(ra, matching.get(ra.agent_id))

    def _allocate_cbba(self, t: int) -> None:
        """Consensus-based bundle algorithm, re-run each tick in which some
        agent is idle (replanning in the spirit of Buckman et al.).

        Bundle construction: an agent appends, one at a time, the victim
        with the highest score it can still outbid, where the score of a
        victim at bundle position k is  priority - beta * (pickup time) and
        pickup times chain through the hospital (capacity one). Busy agents
        bid from the moment and place they become free, so a unit about to
        drop off at the hospital can out-bid an idle but distant one.

        Consensus: agents broadcast their bundle bids; each receiver keeps
        the most recent bundle it has heard from every other agent and
        treats the highest bid (ties to the lower agent id) as the winner.
        An agent outbid on a bundle item releases it and every later item.
        Lost broadcasts leave receivers with stale bids, which is how
        message loss degrades CBBA in practice.
        """
        idle = [ra for ra in self.rescue_agents if ra.status == "idle"]
        if not idle or not any(ra.pending_proposal for ra in idle):
            return
        known = self.shared_state
        grid = self.rescue_agents[0]._grid_spec(known)
        hospital = self.rescue_agents[0].world_map.hospital
        from_h = bfs_distances(grid, hospital)
        beta = self.rescue_agents[0].weights.distance_weight
        order = {ra.agent_id: i for i, ra in enumerate(self.rescue_agents)}

        # When and where each agent next becomes free.
        free = {}
        for ra in self.rescue_agents:
            if ra.status == "idle":
                free[ra.agent_id] = (0, bfs_distances(grid, ra.position))
            elif ra.status == "moving_to_victim":
                v_pos = known.known_victims[ra.current_target].position
                free[ra.agent_id] = (len(ra.path) + from_h.get(tuple(v_pos), 0), from_h)
            else:
                free[ra.agent_id] = (len(ra.path), from_h)
        cands = {ra.agent_id: {kv.victim_id: kv for kv in known.unassigned_known_victims(viewer=ra.agent_id)}
                 for ra in self.rescue_agents}

        def pickup_score(aid, bundle, kv):
            t0, d0 = free[aid]
            if not bundle:
                d = d0.get(tuple(kv.position))
                tau = None if d is None else t0 + d
            else:
                prev_tau, prev = bundle[-1][2], known.known_victims[bundle[-1][0]]
                back = from_h.get(tuple(prev.position))
                d = from_h.get(tuple(kv.position))
                tau = None if (d is None or back is None) else prev_tau + back + d
            return None if tau is None else (kv.priority - beta * tau, tau)

        def beats(a_bid, a_id, b_bid, b_id):
            return a_bid > b_bid + 1e-12 or (abs(a_bid - b_bid) <= 1e-12 and order[a_id] < order[b_id])

        bundles = {ra.agent_id: [] for ra in self.rescue_agents}   # [(victim_id, bid, pickup_tau)]
        heard = {ra.agent_id: {} for ra in self.rescue_agents}     # receiver -> sender -> bundle snapshot

        def winners_seen_by(aid):
            best = {}
            views = dict(heard[aid])
            views[aid] = bundles[aid]
            for sender, b in views.items():
                for vid, bid, _ in b:
                    cur = best.get(vid)
                    if cur is None or beats(bid, sender, cur[0], cur[1]):
                        best[vid] = (bid, sender)
            return best

        max_rounds = 2 * len(self.rescue_agents) * self.cbba_bundle + 2
        for _ in range(max_rounds):
            self.consensus_rounds += 1
            changed = False
            # Phase 1: bundle construction against each agent's current view.
            for ra in self.rescue_agents:
                aid = ra.agent_id
                best = winners_seen_by(aid)
                b = bundles[aid]
                while len(b) < self.cbba_bundle:
                    pick = None
                    for vid, kv in cands[aid].items():
                        if any(x[0] == vid for x in b):
                            continue
                        sc = pickup_score(aid, b, kv)
                        if sc is None:
                            continue
                        cur = best.get(vid)
                        if cur is not None and cur[1] != aid and not beats(sc[0], aid, cur[0], cur[1]):
                            continue
                        if pick is None or sc[0] > pick[1] + 1e-12:
                            pick = (vid, sc[0], sc[1])
                    if pick is None:
                        break
                    b.append(pick)
                    changed = True
            # Phase 2: broadcast bundles (each subject to loss), then resolve.
            for ra in self.rescue_agents:
                self.messages += 1
                self.message_payload += 2 * len(bundles[ra.agent_id])
                if self._lost(ra.agent_id):
                    continue
                snap = list(bundles[ra.agent_id])
                for other in self.rescue_agents:
                    if other is not ra:
                        heard[other.agent_id][ra.agent_id] = snap
            for ra in self.rescue_agents:
                aid = ra.agent_id
                best = winners_seen_by(aid)
                b = bundles[aid]
                for k, (vid, _, _) in enumerate(b):
                    if best[vid][1] != aid:
                        del b[k:]  # outbid: release this item and everything after it
                        changed = True
                        break
            if not changed:
                break

        for ra in idle:
            b = bundles[ra.agent_id]
            self._commit(ra, b[0][0] if b else None)

    def _check_duplicate_targets(self, t: int) -> None:
        """Detects victims two rescue agents are simultaneously, genuinely
        committed to (both `status != "idle"` and pointed at the same
        target). Runs identically in both modes; under MAS it should
        essentially never find anything, since resolve_conflicts() already
        prevented it before either agent committed."""
        targets: dict[str, list[str]] = {}
        for ra in self.rescue_agents:
            if ra.status != "idle" and ra.current_target:
                targets.setdefault(ra.current_target, []).append(ra.agent_id)

        for victim_id, agent_ids in targets.items():
            if len(agent_ids) > 1 and victim_id not in self._logged_duplicate_victims:
                self._logged_duplicate_victims.add(victim_id)
                self.duplicate_conflicts += 1
                self.shared_state.event_log.append(Event(
                    timestamp=t, source="system", type=EventType.DUPLICATE_DETECTED,
                    payload={"victim_id": victim_id, "agents": agent_ids},
                ))

    def run(self) -> RunResult:
        while not self.environment.is_complete() and not self._is_stalled():
            self.tick()
        return self._collect_result()

    def _is_stalled(self) -> bool:
        """True once resources are permanently exhausted and every rescue
        agent is idle: no further rescue can ever happen, so continuing to
        tick until max_time would only waste simulated time."""
        if self.environment.resources.medical_kits > 0:
            return False
        return all(ra.status == "idle" for ra in self.rescue_agents)

    def _collect_result(self) -> RunResult:
        victims = list(self.environment.victims.values())
        rescued = [v for v in victims if v.status == VictimStatus.RESCUED]

        policy_label = {"independent": "no_coordination"}.get(self.policy, self.policy)
        return RunResult(
            policy=policy_label,
            seed=self.environment.config.seed,
            scenario=self.scenario_name,
            completion_time=self.environment.time,
            victims_total=len(victims),
            victims_rescued=len(rescued),
            waiting_times=[float(v.waiting_time) for v in rescued],
            duplicate_conflicts=self.duplicate_conflicts,
            event_log=[e.to_dict() for e in self.shared_state.event_log],
            severity_waits=[(v.severity.value, float(v.waiting_time)) for v in rescued],
            wasted_ticks=sum(ra.wasted_ticks for ra in self.rescue_agents),
            idle_ticks=self.idle_ticks,
            messages=self.messages,
            message_payload=self.message_payload,
            rescue_agents=len(self.rescue_agents),
            consensus_rounds=self.consensus_rounds,
        )


def run_mas(config: ScenarioConfig, rescue_agent_count: int = 2, weights: UtilityWeights | None = None,
            scenario_name: str = "default") -> RunResult:
    sim = Simulation(config, policy="mas", rescue_agent_count=rescue_agent_count, weights=weights,
                      scenario_name=scenario_name)
    return sim.run()


def run_policy(config: ScenarioConfig, policy: str, rescue_agent_count: int = 2,
               weights: UtilityWeights | None = None, scenario_name: str = "default",
               comm_loss: float = 0.0, burst_length: float | None = None, cbba_bundle: int = 3) -> RunResult:
    sim = Simulation(config, policy=policy, rescue_agent_count=rescue_agent_count, weights=weights,
                      scenario_name=scenario_name, comm_loss=comm_loss, burst_length=burst_length,
                      cbba_bundle=cbba_bundle)
    return sim.run()


def run_no_coordination(config: ScenarioConfig, rescue_agent_count: int = 2, weights: UtilityWeights | None = None,
                         scenario_name: str = "default") -> RunResult:
    sim = Simulation(config, policy="independent", rescue_agent_count=rescue_agent_count, weights=weights,
                      scenario_name=scenario_name)
    return sim.run()


SCENARIO_PRESETS = {
    "small": {"victim_count": 6, "blockage_level": 0.0},
    "medium": {"victim_count": 6, "blockage_level": 0.1},
    "large": {"victim_count": 10, "blockage_level": 0.15},
}


def _cli() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Run one RESQ-MAS simulation.")
    parser.add_argument("--mode", choices=["mas", "no_coordination"], default="mas")
    parser.add_argument("--scenario", choices=sorted(SCENARIO_PRESETS), default="medium")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--victim-count", type=int, default=None)
    parser.add_argument("--blockage-level", type=float, default=None)
    parser.add_argument("--rescue-agents", type=int, default=2)
    parser.add_argument("--max-time", type=int, default=300)
    args = parser.parse_args()

    preset = SCENARIO_PRESETS[args.scenario]
    victim_count = args.victim_count if args.victim_count is not None else preset["victim_count"]
    blockage_level = args.blockage_level if args.blockage_level is not None else preset["blockage_level"]

    config = ScenarioConfig(seed=args.seed, victim_count=victim_count, blockage_level=blockage_level,
                             initial_resources=victim_count, max_time=args.max_time)
    runner = run_mas if args.mode == "mas" else run_no_coordination
    result = runner(config, rescue_agent_count=args.rescue_agents, scenario_name=args.scenario)

    print(f"RESQ-MAS -- mode={args.mode} scenario={args.scenario} seed={args.seed} victims={victim_count} "
          f"blockage={blockage_level} rescue_agents={args.rescue_agents}")
    for k, v in result.to_row().items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    _cli()
