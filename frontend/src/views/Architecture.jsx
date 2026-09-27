import { PROTOCOLS } from '../protocols.js'

const SECTION_STYLE = { padding: 14, display: 'flex', flexDirection: 'column', gap: 6 }
const PRE = { background: 'var(--panel-2)', padding: 8, borderRadius: 4, overflowX: 'auto' }

export default function Architecture() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16, maxWidth: 1100 }}>
      <Section title="The Core Idea">
        <p>
          Several rescue agents serve the same disaster area. Many victims are attractive to <b>several</b> agents at
          once: similar priority, similar distance. <b>Without coordination</b>, agents independently pick the same
          victim and waste trips; with more agents, the waste grows until adding units barely helps. <b>With
          coordination</b>, agents exchange information before committing and divide the work. The question the
          paper answers is <i>how much</i> communication that takes: three coordinated agents finish faster than
          eight independent ones.
        </p>
      </Section>

      <div className="panel" style={{ padding: 16 }}>
        <div className="panel-title" style={{ padding: 0, border: 0, marginBottom: 12 }}>System Diagram</div>
        <ArchitectureDiagram />
      </div>

      <Section title="Agent Roles">
        <ul>
          <li><b>Medical Agent</b>: registers each victim when it is reported (at t=0, or over time when an arrival
            window is set) and assigns a priority from severity (critical=4, high=3, moderate=2, low=1), which rises
            by 0.1 per minute of waiting. A simple, transparent rule, not a learned model.</li>
          <li><b>Logistics Agent</b>: sole owner of the pool of medical kits. It never lets the pool go negative and
            never gives two kits for the same victim.</li>
          <li><b>Rescue Agents 1…N</b> (up to 8): identical instances of one class. Each scores reachable victims by
            <span className="mono"> utility = priority − 0.1 × BFS distance</span>, commits to a target, drives there,
            and delivers the victim to the hospital. The <i>only</i> thing that changes between protocols is what
            happens between "score" and "commit".</li>
        </ul>
      </Section>

      <Section title="The Communication Ladder: Six Protocols">
        <p style={{ margin: 0 }}>Ordered from least to most information exchanged before an agent commits. All six share the
          same environment, agents, routing and metrics, so any difference comes from the protocol alone.</p>
        <table>
          <thead><tr><th>Protocol</th><th>What is exchanged</th></tr></thead>
          <tbody>
            {PROTOCOLS.map((p) => (
              <tr key={p.id}>
                <td style={{ whiteSpace: 'nowrap' }}>
                  <span style={{ display: 'inline-block', width: 8, height: 8, borderRadius: 2, background: p.color, marginRight: 6 }} />
                  <b>{p.short}</b> <span style={{ color: 'var(--text-dim)' }}>{p.label}</span>
                </td>
                <td style={{ color: 'var(--text-dim)' }}>{p.desc}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <pre style={PRE}>{`Independent (IND)                     Propose-resolve (PR-1)
-----------------                     ----------------------
A selects V1                          A proposes V1
B selects V1                          B proposes V1
(both drive toward V1)                conflict: highest utility wins -> A keeps V1
one arrives to find nothing           B proposes V2 next minute (PR-k: same minute)
                                      A -> V1,  B -> V2  (parallel)`}</pre>
      </Section>

      <Section title="Realism Knobs">
        <ul>
          <li><b>Victims arriving over time</b>: with an arrival window, each victim appears at a random minute; nobody
            knows about it until then, and its waiting time starts at that moment.</li>
          <li><b>Unreliable radio</b>: every broadcast (proposal, bundle or claim) can be lost. <i>Independent</i> loss
            drops each message at random; <i>bursty</i> loss puts an agent's radio into outages lasting several minutes,
            during which everything it sends is lost. A lost proposal becomes a unilateral commitment, so duplicates
            return as the link degrades.</li>
          <li><b>Road blockages</b>: a share of road cells blocks and reopens mid-run, forcing BFS replanning.</li>
        </ul>
      </Section>

      <Section title="Why BFS">
        <p><b>BFS</b> answers: <i>"How does a rescue agent reach its victim?"</i> It is a shortest-path search on a grid
          with uniform movement cost, re-run whenever a known route becomes blocked.</p>
        <p><b>Task allocation</b> answers: <i>"Which agent should handle which victim, given what the others are doing?"</i>
          That is the coordination problem this project is about. The two are kept in separate modules on purpose.</p>
      </Section>

      <Section title="Metrics">
        <ul>
          <li><b>Completion time</b>: minute the last victim reaches the hospital.</li>
          <li><b>Victim wait</b> (plain, severity-weighted, and for critical victims): minutes from a victim being reported to its delivery.</li>
          <li><b>Duplicate conflicts</b>: times two agents were simultaneously committed to the same victim.</li>
          <li><b>Wasted / idle agent-minutes</b>: time spent on targets later abandoned, and time spent with nothing to do.</li>
          <li><b>Messages and data sent</b>: the communication cost of each protocol.</li>
        </ul>
        <p style={{ color: 'var(--text-dim)', fontSize: 12 }}>
          <b>Modeling assumption:</b> one simulation timestep represents one minute of simulated disaster-response
          operation. These are simulated minutes produced by the model, not real-world measured rescue times.
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

      {box(30, 300, 200, 54, 'Rescue Agent 1', 'scores victims, commits')}
      {box(410, 300, 200, 54, 'Rescue Agent N', 'up to 8 agents')}

      {line(230, 327, 410, 327, true)}
      <text x="320" y="322" textAnchor="middle" fontFamily="var(--font-display)" fontSize="10" fill="var(--text-dim)">radio (may be lossy)</text>

      {line(130, 354, 130, 390)}
      {line(510, 354, 510, 390)}
      {line(130, 390, 320, 390)}
      {line(510, 390, 320, 390)}
      {line(320, 390, 320, 410)}

      {box(170, 410, 300, 44, 'ALLOCATION PROTOCOL', 'IND · CLM · PR-1 · PR-k · HUN · CBBA')}
      {line(320, 454, 320, 480)}
      {box(210, 480, 220, 40, 'BFS')}
      {line(320, 520, 320, 540)}
      <text x="320" y="555" textAnchor="middle" fontFamily="var(--font-mono)" fontSize="13" fontWeight="700" fill="var(--good)">RESCUE</text>
    </svg>
  )
}
