const SECTION_STYLE = { padding: 14, display: 'flex', flexDirection: 'column', gap: 6 }
const PRE = { background: 'var(--panel-2)', padding: 8, borderRadius: 4, overflowX: 'auto' }

export default function Architecture() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16, maxWidth: 1100 }}>
      <Section title="The Core Idea">
        <p>
          Two rescue agents operate in the same disaster area. Several victims are attractive targets for
          <b> both</b> agents — similar priority, similar distance. <b>Without coordination</b>, both agents can
          independently pick the same victim, wasting effort. <b>With coordination</b>, the agents exchange their
          intended targets before committing, detect the duplicate, resolve it, and divide the work — rescuing
          different victims in parallel.
        </p>
      </Section>

      <div className="panel" style={{ padding: 16 }}>
        <div className="panel-title" style={{ padding: 0, border: 0, marginBottom: 12 }}>System Diagram</div>
        <ArchitectureDiagram />
      </div>

      <Section title="Agent Roles">
        <ul>
          <li><b>Medical Agent</b> — assigns each victim a priority from severity (critical=4, high=3,
            moderate=2, low=1), republished as waiting time accrues. A simple, transparent rule — no learned
            model.</li>
          <li><b>Logistics Agent</b> — sole owner of a small, finite pool of medical kits. Answers one question:
            "is this rescue feasible with what's left?" Never lets the pool go negative or double-allocate a
            kit to the same victim.</li>
          <li><b>Rescue Agent A / Rescue Agent B</b> — two instances of the same class. Each evaluates
            candidate victims, selects a target, uses BFS to reach it, and rescues it. The <i>only</i> thing
            that differs between the two simulation modes is what happens between "evaluate" and "commit."</li>
        </ul>
      </Section>

      <Section title="No Coordination vs. Multi-Agent Coordination">
        <p><b>No Coordination:</b> each rescue agent scores every victim by priority and distance, and commits
          to its best candidate immediately — without knowing what the other agent is about to choose. If both
          agents' best candidate is the same victim, both commit to it. One of them finds it already rescued
          when it arrives, and has wasted a trip.</p>
        <p><b>MAS:</b> before committing, both agents publish their intended target. If the same victim was
          proposed by both, a deterministic conflict-resolution rule (highest utility wins, ties broken by
          distance then agent id) picks one winner. The loser immediately re-evaluates and picks its next-best
          target instead — no wasted trip, and both agents make progress in parallel.</p>
        <pre style={PRE}>{`No Coordination                       MAS
----------------                      ---
A selects V1                          A proposes V1
B selects V1                          B proposes V1
(both move toward V1)                 conflict detected -> A keeps V1
duplicate detected during execution   B reassigned -> B proposes V2
                                       A -> V1,  B -> V2  (parallel)`}</pre>
      </Section>

      <Section title="Why BFS">
        <p>
          BFS and coordination answer two different questions, on purpose kept in separate modules:
        </p>
        <p><b>BFS</b> answers: <i>"How does a rescue agent reach its assigned victim?"</i> — a shortest-path
          search over a grid with uniform movement cost, re-run whenever a known route becomes blocked.</p>
        <p><b>Task allocation</b> answers: <i>"Which rescue agent should handle which victim, given what the
          other agent is doing?"</i> — this is the coordination problem the project is actually about. BFS is
          intentionally the only search algorithm in the project; the intellectual content is the coordination
          mechanism, not the pathfinding.</p>
      </Section>

      <Section title="Metrics">
        <ul>
          <li><b>Completion time (minutes)</b> — how long until every victim is rescued.</li>
          <li><b>Average waiting time (minutes)</b> — mean time victims spent waiting to be rescued.</li>
          <li><b>Duplicate / conflicting target assignments</b> — how many times two agents were genuinely,
            simultaneously committed to the same victim. This is the metric that most directly demonstrates
            the point of the project, and is expected to be at or near zero under MAS.</li>
        </ul>
        <p style={{ color: 'var(--text-dim)', fontSize: 12 }}>
          <b>Modeling assumption:</b> one simulation timestep represents one minute of simulated
          disaster-response operation (t=115 means 115 simulated minutes). These are simulated minutes
          produced by the model, not real-world measured rescue times.
        </p>
      </Section>
    </div>
  )
}

function Section({ title, children }) {
  return (
    <div className="panel" style={SECTION_STYLE}>
      <div style={{ fontWeight: 700, color: 'var(--accent)' }}>{title}</div>
      {children}
    </div>
  )
}

function ArchitectureDiagram() {
  const box = (x, y, w, h, label, sub) => {
    const cx = x + w / 2
    const cy = y + h / 2
    return (
      <g key={label}>
        <rect x={x} y={y} width={w} height={h} rx={6} fill="var(--panel-2)" stroke="var(--border)" />
        <text x={cx} y={sub ? cy - 8 : cy} textAnchor="middle" dominantBaseline="middle"
              fontFamily="var(--font-mono)" fontSize="12.5" fontWeight="600" fill="var(--text)">
          {label}
        </text>
        {sub && (
          <text x={cx} y={cy + 8} textAnchor="middle" dominantBaseline="middle"
                fontFamily="var(--font-display)" fontSize="10" fill="var(--text-dim)">
            {sub}
          </text>
        )}
      </g>
    )
  }
  const line = (x1, y1, x2, y2, dashed) => (
    <line key={`${x1}-${y1}-${x2}-${y2}`} x1={x1} y1={y1} x2={x2} y2={y2}
          stroke="var(--border)" strokeWidth="1.5" strokeDasharray={dashed ? '4 3' : undefined} />
  )

  return (
    <svg viewBox="0 0 640 560" style={{ width: '100%', maxWidth: 640, display: 'block', margin: '0 auto' }}>
      {box(210, 10, 220, 44, 'DISASTER ENVIRONMENT')}
      {line(320, 54, 320, 90)}
      {line(320, 90, 130, 90)}
      {line(320, 90, 510, 90)}
      {line(130, 90, 130, 110)}
      {line(510, 90, 510, 110)}

      {box(30, 110, 200, 54, 'Medical Agent', 'victim priority')}
      {box(410, 110, 200, 54, 'Logistics Agent', 'resource status')}

      {line(130, 164, 130, 190)}
      {line(510, 164, 510, 190)}
      {line(130, 190, 320, 190)}
      {line(510, 190, 320, 190)}
      {line(320, 190, 320, 210)}

      {box(210, 210, 220, 44, 'SHARED INFORMATION')}

      {line(320, 254, 320, 280)}
      {line(320, 280, 130, 280)}
      {line(320, 280, 510, 280)}
      {line(130, 280, 130, 300)}
      {line(510, 280, 510, 300)}

      {box(30, 300, 200, 54, 'Rescue Agent A')}
      {box(410, 300, 200, 54, 'Rescue Agent B')}

      {line(230, 327, 410, 327, true)}
      <text x="320" y="322" textAnchor="middle" fontFamily="var(--font-display)" fontSize="10" fill="var(--text-dim)">communication</text>

      {line(130, 354, 130, 390)}
      {line(510, 354, 510, 390)}
      {line(130, 390, 320, 390)}
      {line(510, 390, 320, 390)}
      {line(320, 390, 320, 410)}

      {box(210, 410, 220, 44, 'TASK ALLOCATION')}
      {line(320, 454, 320, 480)}
      {box(210, 480, 220, 40, 'BFS')}
      {line(320, 520, 320, 540)}
      <text x="320" y="555" textAnchor="middle" fontFamily="var(--font-mono)" fontSize="13" fontWeight="700" fill="var(--good)">RESCUE</text>
    </svg>
  )
}
