import ProtocolChip from '../components/ProtocolChip.jsx'
import { PROTOCOLS } from '../protocols.js'

export default function Architecture({ go }) {
  return (
    <div className="page how">
      <div className="section-head">
        <div className="eyebrow">How it works</div>
        <h2>Agents that share one picture of the disaster</h2>
        <p className="lede">
          RESQ-MAS is a multi-agent system. Each agent has one job and they cooperate through a shared board. The only
          thing we change between experiments is how the rescue teams agree on who goes where.
        </p>
      </div>

      <section className="card how-diagram">
        <FlowDiagram />
      </section>

      <section className="band">
        <h3>What happens in one simulated minute</h3>
        <ol className="minute-steps">
          <li><b>New reports and road changes</b> arrive. Blocked and reopened roads are known to everyone immediately.</li>
          <li><b>The medical agent</b> registers new casualties and raises the priority of everyone still waiting.</li>
          <li><b>The logistics agent</b> answers requests for medical kits.</li>
          <li><b>Every free rescue team</b> scores the casualties it can reach: urgency minus distance.</li>
          <li><b>The coordination strategy decides</b> which team commits to which casualty. This is the step under study.</li>
          <li><b>Teams move one block</b> along the shortest open route, pick up casualties and deliver them to hospital.</li>
        </ol>
      </section>

      <section className="band">
        <h3>Six coordination strategies</h3>
        <p className="muted">Listed from least to most information shared before a team commits. The codes match the research paper.</p>
        <div className="card" style={{ padding: 0 }}>
          <div className="table-wrap">
            <table>
              <thead><tr><th>Strategy</th><th>Name in the paper</th><th>What the teams share</th></tr></thead>
              <tbody>
                {PROTOCOLS.map((p) => (
                  <tr key={p.id}>
                    <td><ProtocolChip id={p.id} /></td>
                    <td className="muted">{p.paper}</td>
                    <td style={{ whiteSpace: 'normal', minWidth: 320 }}>{p.desc}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
        <div className="compare-example">
          <div className="card">
            <h3 style={{ fontSize: 18 }}>No talking</h3>
            <ol className="mini-seq">
              <li>Team A picks casualty V1</li>
              <li>Team B also picks V1</li>
              <li>Both drive to V1</li>
              <li className="bad">One arrives to find nobody left</li>
            </ol>
          </div>
          <div className="card">
            <h3 style={{ fontSize: 18 }}>Negotiate</h3>
            <ol className="mini-seq">
              <li>A proposes V1, B proposes V1</li>
              <li>The closer, higher-priority bid wins: A keeps V1</li>
              <li>B picks its next best, V2</li>
              <li className="good">Both casualties are served in parallel</li>
            </ol>
          </div>
        </div>
      </section>

      <section className="band">
        <h3>Real-world complications you can switch on</h3>
        <div className="agents">
          <div className="card agent-card">
            <b>Casualties reported over time</b>
            <p className="muted">Instead of everyone being known at the start, calls arrive at random minutes. Nobody knows about a casualty until the call comes in.</p>
          </div>
          <div className="card agent-card">
            <b>Patchy radio</b>
            <p className="muted">Messages can be lost at random, or a team's radio can go dark for several minutes. A team that is not heard acts on its own, so duplicate chases come back.</p>
          </div>
          <div className="card agent-card">
            <b>Blocked roads</b>
            <p className="muted">Some roads close and reopen during the mission. Teams find a new shortest route with breadth-first search.</p>
          </div>
        </div>
      </section>

      <section className="band">
        <h3>The rules of the model</h3>
        <div className="rules">
          <div className="card">
            <div className="eyebrow">Priority</div>
            <p className="formula num">priority = severity + 0.1 × minutes waiting</p>
            <p className="muted small">Severity: critical 4, high 3, moderate 2, low 1. Long waits slowly raise anyone's priority.</p>
          </div>
          <div className="card">
            <div className="eyebrow">Choosing a target</div>
            <p className="formula num">score = priority − 0.1 × distance</p>
            <p className="muted small">Distance is the number of blocks on the shortest open route.</p>
          </div>
          <div className="card">
            <div className="eyebrow">Time</div>
            <p className="formula num">1 step = 1 simulated minute</p>
            <p className="muted small">All times are produced by the model, not measured in the field.</p>
          </div>
        </div>
        <div><button className="btn primary big" onClick={() => go?.('simulator')}>Try it in the simulator</button></div>
      </section>
    </div>
  )
}

function FlowDiagram() {
  const node = (x, y, w, h, title, sub, tone) => (
    <g key={title}>
      <rect x={x} y={y} width={w} height={h} rx="10"
            fill={tone === 'accent' ? 'var(--accent-soft)' : 'var(--panel-2)'}
            stroke={tone === 'accent' ? 'var(--accent)' : 'var(--border-strong)'} strokeWidth={tone === 'accent' ? 2 : 1} />
      <text x={x + w / 2} y={y + h / 2 - (sub ? 7 : -5)} textAnchor="middle" fontFamily="var(--font-display)" fontSize="19" fontWeight="700" fill="var(--text)">{title}</text>
      {sub && <text x={x + w / 2} y={y + h / 2 + 15} textAnchor="middle" fontFamily="var(--font-body)" fontSize="12.5" fill="var(--text-dim)">{sub}</text>}
    </g>
  )
  const arrow = (d, dashed) => <path d={d} fill="none" stroke="var(--text-dim)" strokeWidth="1.6" strokeDasharray={dashed ? '5 4' : undefined} markerEnd="url(#arr)" />
  return (
    <svg viewBox="0 0 900 300" className="flow" role="img" aria-label="How the agents connect: disaster to medical and logistics agents, a shared board, rescue teams, the coordination strategy, and routing">
      <defs>
        <marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
          <path d="M0 0L10 5L0 10z" fill="var(--text-dim)" />
        </marker>
      </defs>
      {node(10, 20, 170, 64, 'Disaster', 'city, casualties, roads')}
      {node(10, 118, 170, 64, 'Medical agent', 'triage and priority')}
      {node(10, 216, 170, 64, 'Logistics agent', 'medical kits')}
      {node(250, 110, 180, 80, 'Shared board', 'casualties, claims, roads')}
      {node(500, 110, 170, 80, 'Rescue teams', 'up to 8, score targets')}
      {node(730, 20, 160, 110, 'Coordination', 'one of six strategies', 'accent')}
      {node(730, 170, 160, 110, 'Route and rescue', 'shortest open path')}
      {arrow('M95 84V116')}
      {arrow('M180 150H248')}
      {arrow('M180 248C215 248 215 180 248 175')}
      {arrow('M430 150H498')}
      {arrow('M670 135C700 120 700 80 728 75')}
      {arrow('M810 130V168')}
      {arrow('M730 75C580 55 400 60 340 108', true)}
      <text x="540" y="40" textAnchor="middle" fontFamily="var(--font-body)" fontSize="12.5" fill="var(--text-dim)">claims and proposals over the radio</text>
    </svg>
  )
}
