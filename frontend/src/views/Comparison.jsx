import ProtocolChip from '../components/ProtocolChip.jsx'
import { useEffect, useMemo, useState } from 'react'
import { api, PAPER_URL } from '../api.js'
import LineChart from '../components/LineChart.jsx'
import { computeHeadlines } from '../headlines.js'
import { PROTOCOL, PROTOCOLS } from '../protocols.js'

// Every number on this page is computed from executed runs: the paper's
// paired study (results/study/*.csv via /api/experiments/study) or runs the
// visitor launches below. Times are simulated minutes (1 tick = 1 minute).

const MSG_PROTOCOLS = PROTOCOLS.filter((p) => ['claim', 'mas', 'mas_iterative', 'cbba'].includes(p.id))
const TALKING_PROTOCOLS = PROTOCOLS.filter((p) => p.id !== 'no_coordination')
const f0 = (v) => (v == null ? '–' : v.toFixed(0))
const f1 = (v) => (v == null ? '–' : v.toFixed(1))

export default function Comparison() {
  const [study, setStudy] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => { api.study().then(setStudy).catch((e) => setError(e.message)) }, [])
  const h = useMemo(() => (study ? computeHeadlines(study) : null), [study])

  return (
    <div className="page results">
      <div className="section-head">
        <div className="eyebrow">Results</div>
        <h2>What coordination is worth</h2>
        <p className="lede">
          Findings from {h?.runs ? h.runs.toLocaleString() : 'the'} simulated disasters in the paper. Every strategy ran on the
          same randomly generated cities, so each comparison is like for like. Hover a chart for exact values.
          {' '}<a href={PAPER_URL} target="_blank" rel="noreferrer">Read the full paper (PDF)</a>.
        </p>
      </div>

      {error && (
        <div className="card">
          <p className="error-box">Could not load the study results ({error}).</p>
          <p className="muted small" style={{ marginTop: 8 }}>Run <code>python -m experiments.study</code> from the project folder to generate them.</p>
        </div>
      )}
      {!study && !error && <div className="card muted">Loading results…</div>}

      {study && h && (
        <>
          <div className="findings">
            <Tile big={`${h.e1Gain.toFixed(0)}%`} label="faster missions" text="One negotiation round, two teams, 1,000 disasters." />
            <Tile big="3 > 8" label="talk beats numbers" text={`Three negotiating teams beat eight silent ones on every workload (at least ${h.three.minWins} of ${h.three.n} disasters).`} />
            <Tile big={`${h.waitCut[0].toFixed(0)}–${h.waitCut[1].toFixed(0)}%`} label="shorter waits" text="When casualties are reported over time." />
            <Tile big={`${h.cbbaRatio[0].toFixed(0)}–${h.cbbaRatio[1].toFixed(0)}×`} label="more radio traffic for CBBA" text="Than simple negotiation, for the same assignment quality." />
          </div>
          <TwoTeamTable study={study} />
          <div className="chart-grid">
            <ScalingChart study={study} h={h} />
            <ArrivalsChart study={study} />
            <LossChart study={study} />
            <DataCostChart study={study} />
          </div>
        </>
      )}

      <RunYourOwn />
      <OriginalBenchmark />
    </div>
  )
}

function Tile({ big, label, text }) {
  return (
    <div className="card finding">
      <div className="finding-big num">{big}</div>
      <div className="finding-title">{label}</div>
      <p className="muted small">{text}</p>
    </div>
  )
}

function Panel({ title, subtitle, controls, children }) {
  return (
    <section className="card chart-card">
      <div className="chart-head">
        <div style={{ flex: 1, minWidth: 220 }}>
          <h3>{title}</h3>
          {subtitle && <p className="muted small">{subtitle}</p>}
        </div>
        {controls && <div className="chart-controls">{controls}</div>}
      </div>
      {children}
    </section>
  )
}

function Seg({ options, value, onChange, label }) {
  return (
    <div className="seg" role="radiogroup" aria-label={label}>
      {options.map(([v, text]) => (
        <button key={String(v)} role="radio" aria-checked={value === v} onClick={() => onChange(v)}>{text}</button>
      ))}
    </div>
  )
}

function series(rows, xKey, metric, protocols = PROTOCOLS) {
  return protocols.map((p) => ({
    key: p.id, label: p.name.includes(p.short) ? p.name : `${p.name} (${p.short})`, color: p.color, marker: p.marker, dashed: p.id === 'claim',
    points: rows.filter((r) => r.policy === p.id && r[metric]?.mean != null)
      .map((r) => ({ x: r[xKey], y: r[metric].mean, ci: r[metric].ci }))
      .sort((a, b) => a.x - b.x),
  })).filter((s) => s.points.length > 0)
}

function TwoTeamTable({ study }) {
  const rows = PROTOCOLS.map((p) => ({ p, r: study.e1.find((x) => x.policy === p.id) })).filter((x) => x.r)
  const maxT = Math.max(...rows.map((x) => x.r.completion_time.mean))
  return (
    <Panel title="Two teams, six casualties, 1,000 random disasters"
           subtitle="The original RESQ-MAS setting. Duplicate chases disappear as soon as teams negotiate, and extra rounds add almost nothing.">
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Strategy</th><th style={{ width: '32%' }}>Time to rescue everyone (±95% CI)</th><th>Average wait</th>
              <th>Critical casualties' wait</th><th>Duplicate chases</th><th>Wasted team-min</th><th>Data sent</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(({ p, r }) => (
              <tr key={p.id} title={p.desc}>
                <td><ProtocolChip id={p.id} /></td>
                <td>
                  <div className="bar-cell">
                    <div className="bar" style={{ width: `${(r.completion_time.mean / maxT) * 70}%`, background: p.color }} />
                    <span className="num">{f1(r.completion_time.mean)} <span className="muted">±{f1(r.completion_time.ci)}</span></span>
                  </div>
                </td>
                <td className="num">{f1(r.avg_waiting_time.mean)} min</td>
                <td className="num">{f1(r.critical_wait.mean)} min</td>
                <td className="num" style={{ color: r.duplicate_conflicts.mean > 0.05 ? 'var(--bad)' : undefined }}>{r.duplicate_conflicts.mean.toFixed(2)}</td>
                <td className="num">{f1(r.wasted_ticks.mean)}</td>
                <td className="num">{f0(r.message_payload.mean)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Panel>
  )
}

function ScalingChart({ study, h }) {
  const [m, setM] = useState(20)
  const [metric, setMetric] = useState('completion_time')
  const data = useMemo(() => {
    const rows = study.e2.filter((r) => r.victims === m && (metric === 'completion_time' || r.rescue_agents > 1))
    let s = series(rows, 'rescue_agents', metric)
    if (metric === 'completion_time') {
      const one = rows.find((r) => r.rescue_agents === 1 && r.policy === 'no_coordination')
      s = s.map((x) => (x.key === 'no_coordination' ? x : { ...x, points: [{ x: 1, y: one.completion_time.mean, ci: one.completion_time.ci }, ...x.points] }))
      s.push({ key: 'ideal', label: 'Perfect sharing (one team’s time ÷ N)', color: 'var(--text-dim)', marker: 'none', dashed: true,
               points: [1, 2, 3, 4, 6, 8].map((n) => ({ x: n, y: one.completion_time.mean / n })) })
    }
    return s
  }, [study, m, metric])
  const labels = { completion_time: 'Time to rescue everyone (min)', wasted_ticks: 'Wasted team-minutes', idle_ticks: 'Idle team-minutes' }
  return (
    <Panel title="More teams only help if they talk"
           subtitle={`Silent teams crowd the same casualties: eight are only ${h.speedupInd[0].toFixed(1)}–${h.speedupInd[1].toFixed(1)}× faster than one. Negotiating teams get ${h.speedupPr[0].toFixed(1)}–${h.speedupPr[1].toFixed(1)}×.`}
           controls={<>
             <Seg label="Casualties" value={m} onChange={setM} options={[[10, '10 casualties'], [20, '20'], [30, '30']]} />
             <Seg label="Measure" value={metric} onChange={setMetric} options={[['completion_time', 'Time'], ['wasted_ticks', 'Wasted'], ['idle_ticks', 'Idle']]} />
           </>}>
      <LineChart series={data} xLabel="Number of rescue teams" yLabel={labels[metric]}
                 xTicks={metric === 'completion_time' ? [1, 2, 3, 4, 6, 8] : [2, 3, 4, 6, 8]} formatY={(v) => v.toFixed(0)} />
    </Panel>
  )
}

function ArrivalsChart({ study }) {
  const [metric, setMetric] = useState('avg_waiting_time')
  const data = useMemo(() => series(study.e5, 'arrival_window', metric), [study, metric])
  const labels = { avg_waiting_time: 'Average wait (min)', weighted_wait: 'Severity-weighted wait (min)', duplicate_conflicts: 'Duplicate chases per mission' }
  return (
    <Panel title="When calls keep coming in, announcing claims is not enough"
           subtitle="Every free team hears a new call at the same moment, so teams that only announce claims (dashed) keep colliding. 4 teams, 20 casualties."
           controls={<Seg label="Measure" value={metric} onChange={setMetric}
                          options={[['avg_waiting_time', 'Wait'], ['weighted_wait', 'By severity'], ['duplicate_conflicts', 'Duplicates']]} />}>
      <LineChart series={data} xLabel="Casualties reported over (min); 0 = all known at the start" yLabel={labels[metric]}
                 xTicks={[0, 100, 200, 400]} formatY={(v) => (metric === 'duplicate_conflicts' ? v.toFixed(1) : v.toFixed(0))} />
    </Panel>
  )
}

function LossChart({ study }) {
  const [pattern, setPattern] = useState('independent')
  const [burst, setBurst] = useState(5)
  const data = useMemo(() => {
    const rows = pattern === 'independent'
      ? study.e3
      : [...study.e3.filter((r) => r.comm_loss === 0), ...study.e6.filter((r) => r.burst_length === burst)]
    const s = series(rows, 'comm_loss', 'completion_time', MSG_PROTOCOLS)
    const ind = study.e2.find((r) => r.victims === 20 && r.rescue_agents === 4 && r.policy === 'no_coordination')
    const xs = [...new Set(rows.map((r) => r.comm_loss))].sort((a, b) => a - b)
    s.push({ key: 'ind-ref', label: `${PROTOCOL.no_coordination.name} (IND), for reference`, color: PROTOCOL.no_coordination.color,
             marker: 'none', dashed: true, points: xs.map((x) => ({ x, y: ind.completion_time.mean })) })
    return s
  }, [study, pattern, burst])
  return (
    <Panel title="Patchy radio: repetition helps with random drops, not with outages"
           subtitle="The auction method (CBBA) repeats its messages, which rides out random losses. When a team's radio goes dark for minutes at a time, most of that advantage disappears."
           controls={<>
             <Seg label="Loss pattern" value={pattern} onChange={setPattern} options={[['independent', 'Random drops'], ['bursty', 'Outages']]} />
             {pattern === 'bursty' && <Seg label="Outage length" value={burst} onChange={setBurst} options={[[1, '1 min'], [5, '5 min'], [20, '20 min']]} />}
           </>}>
      <LineChart series={data} xLabel="Share of messages lost" yLabel="Time to rescue everyone (min)"
                 formatX={(v) => `${Math.round(v * 100)}%`} formatY={(v) => v.toFixed(0)} />
    </Panel>
  )
}

function DataCostChart({ study }) {
  const [m, setM] = useState(20)
  const data = useMemo(() => series(study.e2.filter((r) => r.victims === m), 'rescue_agents', 'message_payload', TALKING_PROTOCOLS), [study, m])
  return (
    <Panel title="What each strategy costs on the radio"
           subtitle="Values sent per mission. Negotiating to agreement matches the central dispatcher with far less traffic; the auction method sends the most."
           controls={<Seg label="Casualties" value={m} onChange={setM} options={[[10, '10 casualties'], [20, '20'], [30, '30']]} />}>
      <LineChart series={data} xLabel="Number of rescue teams" yLabel="Values sent per mission" xTicks={[2, 3, 4, 6, 8]}
                 formatY={(v) => (v >= 1000 ? `${(v / 1000).toFixed(1)}k` : v.toFixed(0))} />
    </Panel>
  )
}

function RunYourOwn() {
  const [cfg, setCfg] = useState({
    victim_count: 12, rescue_agent_count: 4, width: 20, n_runs: 20, base_seed: 1000, blockage_level: 0,
    arrival_window: 0, comm_loss: 0, loss_pattern: 'independent', burst_length: 5, policies: PROTOCOLS.map((p) => p.id),
  })
  const [res, setRes] = useState(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState(null)
  const up = (k, v) => setCfg((c) => ({ ...c, [k]: v }))
  const toggle = (id) => up('policies', cfg.policies.includes(id) ? cfg.policies.filter((x) => x !== id) : [...cfg.policies, id])

  const run = async () => {
    setBusy(true)
    setErr(null)
    try {
      setRes(await api.runExperiment({
        victim_count: cfg.victim_count, rescue_agent_count: cfg.rescue_agent_count, width: cfg.width,
        n_runs: cfg.n_runs, base_seed: cfg.base_seed, blockage_level: cfg.blockage_level, max_time: 3000,
        arrival_window: cfg.arrival_window, comm_loss: cfg.comm_loss,
        policies: PROTOCOLS.map((p) => p.id).filter((id) => cfg.policies.includes(id)),
        burst_length: cfg.comm_loss > 0 && cfg.loss_pattern === 'bursty' ? cfg.burst_length : null,
      }))
    } catch (e) {
      setErr(`The run failed: ${e.message}. Check that the server is running and the settings are in range.`)
    } finally {
      setBusy(false)
    }
  }

  const rows = res ? res.policies.map((id) => ({ p: PROTOCOL[id], v: res.per_policy[id], paired: res.paired[id] })) : []
  const maxT = Math.max(1, ...rows.map((r) => r.v.completion_time.mean))
  const num = (id, label, key, props = {}) => (
    <label className="field-label" htmlFor={id}>
      {label}
      <input id={id} className="field num" type="number" style={{ width: 110 }} value={props.scale ? Math.round(cfg[key] * props.scale) : cfg[key]}
             min={props.min} max={props.max} step={props.step || 1}
             onChange={(e) => up(key, props.scale ? Number(e.target.value) / props.scale : Number(e.target.value))} />
    </label>
  )

  return (
    <Panel title="Run your own experiment"
           subtitle="Set up a situation, pick strategies, and run fresh simulations on the server. Each disaster is played once by every strategy you pick, so the comparison is fair.">
      <div className="settings-grid">
        {num('own-victims', 'Casualties', 'victim_count', { min: 2, max: 60 })}
        {num('own-teams', 'Rescue teams', 'rescue_agent_count', { min: 1, max: 8 })}
        <label className="field-label" htmlFor="own-grid">City size
          <select id="own-grid" className="field" value={cfg.width} onChange={(e) => up('width', Number(e.target.value))}>
            <option value={15}>Small (15×15)</option><option value={20}>Medium (20×20)</option><option value={25}>Large (25×25)</option>
          </select>
        </label>
        {num('own-runs', 'Disasters to run', 'n_runs', { min: 1, max: 100 })}
        {num('own-arrival', 'Reported over (min)', 'arrival_window', { min: 0, max: 1000, step: 50 })}
        {num('own-loss', 'Messages lost (%)', 'comm_loss', { min: 0, max: 100, step: 5, scale: 100 })}
        {cfg.comm_loss > 0 && (
          <label className="field-label" htmlFor="own-pattern">Loss pattern
            <select id="own-pattern" className="field" value={cfg.loss_pattern} onChange={(e) => up('loss_pattern', e.target.value)}>
              <option value="independent">Random drops</option><option value="bursty">Radio outages</option>
            </select>
          </label>
        )}
        {cfg.comm_loss > 0 && cfg.loss_pattern === 'bursty' && num('own-burst', 'Outage length (min)', 'burst_length', { min: 1, max: 100 })}
      </div>
      <div className="own-picks">
        {PROTOCOLS.map((p) => (
          <label key={p.id} className="pick" title={p.desc} style={{ '--pc': p.color }}>
            <input type="checkbox" checked={cfg.policies.includes(p.id)} onChange={() => toggle(p.id)} />
            {p.name} <span className="code" style={{ color: 'var(--text-dim)' }}>{p.short}</span>
          </label>
        ))}
        <button className="btn primary" style={{ marginLeft: 'auto' }} disabled={busy || cfg.policies.length === 0} onClick={run}>
          {busy ? 'Running…' : `Run ${cfg.n_runs * cfg.policies.length} simulations`}
        </button>
      </div>
      {err && <div className="error-box">{err}</div>}
      {rows.length > 0 && (
        <div className="table-wrap">
          <table>
            <thead>
              <tr><th>Strategy</th><th style={{ width: '34%' }}>Time to rescue everyone (±95% CI)</th><th>Average wait</th><th>Duplicate chases</th>
                <th>Data sent</th><th>Faster than {PROTOCOL[res.baseline].name} in</th></tr>
            </thead>
            <tbody>
              {rows.map(({ p, v, paired }) => (
                <tr key={p.id}>
                  <td><ProtocolChip id={p.id} /></td>
                  <td>
                    <div className="bar-cell">
                      <div className="bar" style={{ width: `${(v.completion_time.mean / maxT) * 70}%`, background: p.color }} />
                      <span className="num">{f1(v.completion_time.mean)} <span className="muted">±{f1(v.completion_time.ci)}</span></span>
                    </div>
                  </td>
                  <td className="num">{f1(v.avg_waiting_time.mean)} min</td>
                  <td className="num" style={{ color: v.duplicate_conflicts.mean > 0.05 ? 'var(--bad)' : undefined }}>{v.duplicate_conflicts.mean.toFixed(2)}</td>
                  <td className="num">{f0(v.message_payload.mean)}</td>
                  <td className="num">{paired ? `${paired.wins} of ${res.seeds.length} disasters` : 'baseline'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Panel>
  )
}

function OriginalBenchmark() {
  const [table, setTable] = useState(null)
  useEffect(() => { api.precomputedTable('comparison').then(setTable).catch(() => {}) }, [])
  if (!table) return null
  return (
    <details className="card">
      <summary className="muted">Original course benchmark: 20 runs on hand-picked disasters</summary>
      <p className="muted small" style={{ margin: '10px 0' }}>
        Kept for reference. On 1,000 random disasters the gain is larger (29% instead of 20.9%), so the hand-picked benchmark understated the effect.
      </p>
      <div className="table-wrap">
        <table>
          <thead><tr><th>Measure</th><th>No talking</th><th>Negotiate</th><th>Change</th></tr></thead>
          <tbody>
            {table.map((row) => (
              <tr key={row.metric}>
                <td>{row.metric.replace(/_/g, ' ')}</td>
                <td className="num">{Number(row.no_coordination_mean).toFixed(2)}</td>
                <td className="num">{Number(row.mas_mean).toFixed(2)}</td>
                <td className="num">{Number(row.improvement_pct) >= 0 ? '+' : ''}{Number(row.improvement_pct).toFixed(1)}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  )
}
