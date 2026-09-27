import { useEffect, useMemo, useState } from 'react'
import { api } from '../api.js'
import LineChart from '../components/LineChart.jsx'
import { PROTOCOL, PROTOCOLS } from '../protocols.js'

// Every number on this page is computed from executed runs: the paper's
// paired study (results/study/*.csv via /api/experiments/study) or runs the
// visitor launches below. Times are simulated minutes (1 tick = 1 minute).

const MSG_PROTOCOLS = PROTOCOLS.filter((p) => ['claim', 'mas', 'mas_iterative', 'cbba'].includes(p.id))
const TALKING_PROTOCOLS = PROTOCOLS.filter((p) => p.id !== 'no_coordination')

const f0 = (v) => (v == null ? '-' : v.toFixed(0))
const f1 = (v) => (v == null ? '-' : v.toFixed(1))

export default function Comparison() {
  const [study, setStudy] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    api.study().then(setStudy).catch((e) => setError(e.message))
  }, [])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16, maxWidth: 1240 }}>
      <div>
        <h2 style={{ margin: '0 0 4px 0' }}>Three Beats Eight: What Coordination Is Worth</h2>
        <div style={{ color: 'var(--text-dim)', maxWidth: 980 }}>
          Results of the paper's paired study
          {study?.meta?.runs ? ` (${study.meta.runs.toLocaleString()} simulations on randomly generated worlds; every protocol runs on the same worlds)` : ''}.
          Hover any chart for exact values and 95% confidence intervals. Times are simulated minutes, not field measurements.
        </div>
      </div>

      {error && (
        <div className="panel" style={{ padding: 16 }}>
          <p style={{ color: 'var(--bad)', margin: 0 }}>{error}</p>
          <p style={{ color: 'var(--text-dim)', marginBottom: 0 }}>
            Run <code>python -m experiments.study</code> from the project root to generate the study results.
          </p>
        </div>
      )}
      {!study && !error && <div className="panel" style={{ padding: 16, color: 'var(--text-dim)' }}>Loading study results…</div>}

      {study && (
        <>
          <Headlines study={study} />
          <TwoAgentTable study={study} />
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(520px, 1fr))', gap: 16 }}>
            <ScalingChart study={study} />
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

function Panel({ title, subtitle, controls, children }) {
  return (
    <div className="panel" style={{ padding: 14, display: 'flex', flexDirection: 'column', gap: 8, minWidth: 0 }}>
      <div style={{ display: 'flex', gap: 10, alignItems: 'start', flexWrap: 'wrap' }}>
        <div style={{ flex: 1, minWidth: 220 }}>
          <div style={{ fontWeight: 700, color: 'var(--accent)' }}>{title}</div>
          {subtitle && <div style={{ fontSize: 11.5, color: 'var(--text-dim)' }}>{subtitle}</div>}
        </div>
        {controls}
      </div>
      {children}
    </div>
  )
}

function Toggle({ options, value, onChange, label }) {
  return (
    <div role="radiogroup" aria-label={label} style={{ display: 'flex', gap: 2 }}>
      {options.map(([v, text]) => (
        <button key={String(v)} className="btn" role="radio" aria-checked={value === v} onClick={() => onChange(v)}
                style={{
                  fontSize: 11, padding: '3px 8px',
                  borderColor: value === v ? 'var(--accent)' : 'var(--border)',
                  color: value === v ? 'var(--accent)' : 'var(--text-dim)',
                }}>
          {text}
        </button>
      ))}
    </div>
  )
}

function series(rows, xKey, metric, filter = () => true, protocols = PROTOCOLS) {
  return protocols.map((p) => ({
    key: p.id, label: `${p.short} · ${p.label}`, color: p.color, marker: p.marker,
    dashed: p.id === 'claim',
    points: rows.filter((r) => r.policy === p.id && filter(r) && r[metric]?.mean != null)
      .map((r) => ({ x: r[xKey], y: r[metric].mean, ci: r[metric].ci }))
      .sort((a, b) => a.x - b.x),
  })).filter((s) => s.points.length > 0)
}

// -- headline tiles ---------------------------------------------------------------
function Headlines({ study }) {
  const e1 = Object.fromEntries(study.e1.map((r) => [r.policy, r]))
  const e1Gain = 100 * (1 - e1.mas.completion_time.mean / e1.no_coordination.completion_time.mean)

  const three = study.three_beats_eight.filter((b) => b.coordinated_agents === 3)
  const worst3 = three.reduce((a, b) => (b.wins / b.n < a.wins / a.n ? b : a))

  const e5 = study.e5.filter((r) => r.arrival_window > 0)
  const waitCut = [100, 200, 400].map((w) => {
    const ind = e5.find((r) => r.arrival_window === w && r.policy === 'no_coordination')
    const pr = e5.find((r) => r.arrival_window === w && r.policy === 'mas')
    return 100 * (1 - pr.avg_waiting_time.mean / ind.avg_waiting_time.mean)
  })

  const ratios = [10, 20, 30].flatMap((m) => [2, 3, 4, 6, 8].map((n) => {
    const get = (p) => study.e2.find((r) => r.victims === m && r.rescue_agents === n && r.policy === p)
    return get('cbba').message_payload.mean / get('mas').message_payload.mean
  }))

  const tiles = [
    { big: `${e1Gain.toFixed(0)}%`, text: 'faster missions with one negotiation round, two agents, 1,000 worlds' },
    { big: '3 > 8', text: `three coordinated agents beat eight independent ones on every workload (at least ${worst3.wins}/${worst3.n} worlds)` },
    { big: `${Math.min(...waitCut).toFixed(0)}–${Math.max(...waitCut).toFixed(0)}%`, text: 'lower victim wait when victims are reported over time' },
    { big: `${Math.min(...ratios).toFixed(0)}–${Math.max(...ratios).toFixed(0)}×`, text: 'more data sent by CBBA than one-round negotiation, for the same allocation quality' },
  ]
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 12 }}>
      {tiles.map((t) => (
        <div key={t.big} className="panel" style={{ padding: 14 }}>
          <div className="mono" style={{ fontSize: 30, fontWeight: 800, color: 'var(--text)', lineHeight: 1.1 }}>{t.big}</div>
          <div style={{ fontSize: 12, color: 'var(--text-dim)', marginTop: 6 }}>{t.text}</div>
        </div>
      ))}
    </div>
  )
}

// -- E1 table -----------------------------------------------------------------------
function TwoAgentTable({ study }) {
  const rows = PROTOCOLS.map((p) => ({ p, r: study.e1.find((x) => x.policy === p.id) })).filter((x) => x.r)
  const maxT = Math.max(...rows.map((x) => x.r.completion_time.mean))
  return (
    <Panel title="Two agents, six victims — 1,000 random worlds"
           subtitle="The original RESQ-MAS setting. Duplicates and wasted trips disappear as soon as agents negotiate; beyond one round, returns vanish.">
      <table>
        <thead>
          <tr>
            <th>Protocol</th><th style={{ width: '30%' }}>Completion time (±95% CI)</th><th>Avg wait</th>
            <th>Severity-weighted wait</th><th>Critical victims' wait</th><th>Duplicates</th><th>Wasted agent-min</th><th>Data sent</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(({ p, r }) => (
            <tr key={p.id} title={p.desc}>
              <td><span style={{ display: 'inline-block', width: 8, height: 8, borderRadius: 2, background: p.color, marginRight: 6 }} />
                <b>{p.short}</b> <span style={{ color: 'var(--text-dim)', fontSize: 11 }}>{p.label}</span></td>
              <td>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <div style={{ height: 10, width: `${(r.completion_time.mean / maxT) * 100}%`, background: p.color, borderRadius: '0 3px 3px 0' }} />
                  <span className="mono">{f1(r.completion_time.mean)} <span style={{ color: 'var(--text-dim)' }}>±{f1(r.completion_time.ci)}</span></span>
                </div>
              </td>
              <td className="mono">{f1(r.avg_waiting_time.mean)}</td>
              <td className="mono">{f1(r.weighted_wait.mean)}</td>
              <td className="mono">{f1(r.critical_wait.mean)}</td>
              <td className="mono" style={{ color: r.duplicate_conflicts.mean > 0.05 ? 'var(--bad)' : undefined }}>{r.duplicate_conflicts.mean.toFixed(2)}</td>
              <td className="mono">{f1(r.wasted_ticks.mean)}</td>
              <td className="mono">{f0(r.message_payload.mean)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Panel>
  )
}

// -- E2 scaling ------------------------------------------------------------------------
function ScalingChart({ study }) {
  const [m, setM] = useState(20)
  const [metric, setMetric] = useState('completion_time')
  const data = useMemo(() => {
    const rows = study.e2.filter((r) => r.victims === m && (metric === 'completion_time' || r.rescue_agents > 1))
    let s = series(rows, 'rescue_agents', metric)
    if (metric === 'completion_time') {
      // N=1 has nobody to coordinate with: it is the same run for every protocol.
      const one = rows.find((r) => r.rescue_agents === 1 && r.policy === 'no_coordination')
      s = s.map((x) => (x.key === 'no_coordination' ? x : { ...x, points: [{ x: 1, y: one.completion_time.mean, ci: one.completion_time.ci }, ...x.points] }))
      s.push({ key: 'ideal', label: 'Ideal: single-agent time ÷ N', color: '#7d8996', marker: 'none', dashed: true,
               points: [1, 2, 3, 4, 6, 8].map((n) => ({ x: n, y: one.completion_time.mean / n })) })
    }
    return s
  }, [study, m, metric])
  const labels = { completion_time: 'Completion time (min)', wasted_ticks: 'Wasted agent-minutes', idle_ticks: 'Idle agent-minutes' }
  return (
    <Panel title="Adding agents without coordination stops paying off"
           subtitle="Independent agents herd onto the same victims: eight are only 1.7–2.5× faster than one. Negotiating teams track the ideal curve."
           controls={<div style={{ display: 'flex', flexDirection: 'column', gap: 4, alignItems: 'end' }}>
             <Toggle label="Victims" value={m} onChange={setM} options={[[10, '10 victims'], [20, '20'], [30, '30']]} />
             <Toggle label="Metric" value={metric} onChange={setMetric}
                     options={[['completion_time', 'time'], ['wasted_ticks', 'wasted'], ['idle_ticks', 'idle']]} />
           </div>}>
      <LineChart series={data} xLabel="Rescue agents N" yLabel={labels[metric]} xTicks={metric === 'completion_time' ? [1, 2, 3, 4, 6, 8] : [2, 3, 4, 6, 8]}
                 formatY={(v) => v.toFixed(0)} />
    </Panel>
  )
}

// -- E5 arrivals -------------------------------------------------------------------------
function ArrivalsChart({ study }) {
  const [metric, setMetric] = useState('avg_waiting_time')
  const data = useMemo(() => series(study.e5, 'arrival_window', metric), [study, metric])
  const labels = { avg_waiting_time: 'Mean victim wait (min)', weighted_wait: 'Severity-weighted wait (min)', duplicate_conflicts: 'Duplicate commitments per run' }
  return (
    <Panel title="When victims are reported over time, claims are not enough"
           subtitle="Every idle agent sees a new victim in the same minute, so claim-only (dashed) collides constantly. 4 agents, 20 victims."
           controls={<Toggle label="Metric" value={metric} onChange={setMetric}
                              options={[['avg_waiting_time', 'wait'], ['weighted_wait', 'severity-weighted'], ['duplicate_conflicts', 'duplicates']]} />}>
      <LineChart series={data} xLabel="Arrival window (min; 0 = all known at start)" yLabel={labels[metric]}
                 xTicks={[0, 100, 200, 400]} formatY={(v) => (metric === 'duplicate_conflicts' ? v.toFixed(1) : v.toFixed(0))} />
    </Panel>
  )
}

// -- E3 / E6 message loss -------------------------------------------------------------------
function LossChart({ study }) {
  const [pattern, setPattern] = useState('independent')
  const [burst, setBurst] = useState(5)
  const data = useMemo(() => {
    let rows
    if (pattern === 'independent') {
      rows = study.e3
    } else {
      const lossFree = study.e3.filter((r) => r.comm_loss === 0)
      rows = [...lossFree, ...study.e6.filter((r) => r.burst_length === burst)]
    }
    const s = series(rows, 'comm_loss', 'completion_time', () => true, MSG_PROTOCOLS)
    const ind = study.e2.find((r) => r.victims === 20 && r.rescue_agents === 4 && r.policy === 'no_coordination')
    const xs = [...new Set(rows.map((r) => r.comm_loss))].sort((a, b) => a - b)
    s.push({ key: 'ind-ref', label: 'IND (no communication) reference', color: PROTOCOL.no_coordination.color, marker: 'none', dashed: true,
             points: xs.map((x) => ({ x, y: ind.completion_time.mean })) })
    return s
  }, [study, pattern, burst])
  return (
    <Panel title="Unreliable radio: repetition beats random loss, not outages"
           subtitle="CBBA's repeated consensus rounds shrug off random packet loss, but most of that edge vanishes when losses come as outages. 4 agents, 20 victims."
           controls={<div style={{ display: 'flex', flexDirection: 'column', gap: 4, alignItems: 'end' }}>
             <Toggle label="Loss pattern" value={pattern} onChange={setPattern}
                     options={[['independent', 'independent loss'], ['bursty', 'bursty outages']]} />
             {pattern === 'bursty' && (
               <Toggle label="Outage length" value={burst} onChange={setBurst}
                       options={[[1, '1-min outages'], [5, '5-min'], [20, '20-min']]} />
             )}
           </div>}>
      <LineChart series={data} xLabel="Message-loss probability p" yLabel="Completion time (min)"
                 formatX={(v) => `${Math.round(v * 100)}%`} formatY={(v) => v.toFixed(0)} />
    </Panel>
  )
}

// -- communication cost ---------------------------------------------------------------------
function DataCostChart({ study }) {
  const [m, setM] = useState(20)
  const data = useMemo(() => series(study.e2.filter((r) => r.victims === m), 'rescue_agents', 'message_payload', () => true, TALKING_PROTOCOLS), [study, m])
  return (
    <Panel title="What each protocol costs on the radio"
           subtitle="Values transmitted per mission. Iterative negotiation matches the centralized optimum at a fraction of the traffic; CBBA pays the most."
           controls={<Toggle label="Victims" value={m} onChange={setM} options={[[10, '10 victims'], [20, '20'], [30, '30']]} />}>
      <LineChart series={data} xLabel="Rescue agents N" yLabel="Data sent per mission (values)" xTicks={[2, 3, 4, 6, 8]}
                 formatY={(v) => (v >= 1000 ? `${(v / 1000).toFixed(1)}k` : v.toFixed(0))} />
    </Panel>
  )
}

// -- run your own -----------------------------------------------------------------------------
function RunYourOwn() {
  const [cfg, setCfg] = useState({
    victim_count: 12, rescue_agent_count: 4, width: 20, n_runs: 20, base_seed: 1000, blockage_level: 0,
    arrival_window: 0, comm_loss: 0, loss_pattern: 'independent', burst_length: 5,
    policies: PROTOCOLS.map((p) => p.id),
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
      const ordered = PROTOCOLS.map((p) => p.id).filter((id) => cfg.policies.includes(id))
      setRes(await api.runExperiment({
        victim_count: cfg.victim_count, rescue_agent_count: cfg.rescue_agent_count, width: cfg.width,
        n_runs: cfg.n_runs, base_seed: cfg.base_seed, blockage_level: cfg.blockage_level, max_time: 3000,
        arrival_window: cfg.arrival_window, comm_loss: cfg.comm_loss, policies: ordered,
        burst_length: cfg.comm_loss > 0 && cfg.loss_pattern === 'bursty' ? cfg.burst_length : null,
      }))
    } catch (e) {
      setErr(e.message)
    } finally {
      setBusy(false)
    }
  }

  const rows = res ? res.policies.map((id) => ({ p: PROTOCOL[id], v: res.per_policy[id], paired: res.paired[id] })) : []
  const maxT = Math.max(1, ...rows.map((r) => r.v.completion_time.mean + (r.v.completion_time.ci || 0)))
  const num = (label, key, props = {}) => (
    <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 11, color: 'var(--text-dim)' }}>
      {label}
      <input className="btn mono" type="number" style={{ width: props.width || 72 }} value={props.scale ? Math.round(cfg[key] * props.scale) : cfg[key]}
             min={props.min} max={props.max} step={props.step || 1}
             onChange={(e) => up(key, props.scale ? Number(e.target.value) / props.scale : Number(e.target.value))} />
    </label>
  )

  return (
    <Panel title="Run your own experiment"
           subtitle="Pick a scenario and protocols; each seed builds one world that every selected protocol runs on, so the comparison is paired. Runs execute live on the server.">
      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'end' }}>
        {num('Victims', 'victim_count', { min: 2, max: 60 })}
        {num('Agents', 'rescue_agent_count', { min: 1, max: 8 })}
        <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 11, color: 'var(--text-dim)' }}>
          Grid
          <select className="btn mono" value={cfg.width} onChange={(e) => up('width', Number(e.target.value))}>
            <option value={15}>15×15</option><option value={20}>20×20</option><option value={25}>25×25</option>
          </select>
        </label>
        {num('Worlds', 'n_runs', { min: 1, max: 100 })}
        {num('First seed', 'base_seed', { width: 80 })}
        {num('Arrival window (min)', 'arrival_window', { min: 0, max: 1000, step: 50, width: 96 })}
        {num('Message loss (%)', 'comm_loss', { min: 0, max: 100, step: 5, scale: 100, width: 90 })}
        {cfg.comm_loss > 0 && (
          <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 11, color: 'var(--text-dim)' }}>
            Loss pattern
            <select className="btn mono" value={cfg.loss_pattern} onChange={(e) => up('loss_pattern', e.target.value)}>
              <option value="independent">independent</option><option value="bursty">bursty outages</option>
            </select>
          </label>
        )}
        {cfg.comm_loss > 0 && cfg.loss_pattern === 'bursty' && num('Outage (min)', 'burst_length', { min: 1, max: 100 })}
      </div>
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
        {PROTOCOLS.map((p) => (
          <label key={p.id} title={p.desc} style={{
            display: 'flex', alignItems: 'center', gap: 5, fontSize: 11.5, padding: '3px 8px', borderRadius: 4,
            border: `1px solid ${cfg.policies.includes(p.id) ? p.color : 'var(--border)'}`, cursor: 'pointer',
          }}>
            <input type="checkbox" checked={cfg.policies.includes(p.id)} onChange={() => toggle(p.id)} />
            {p.short}
          </label>
        ))}
        <button className="btn primary" style={{ marginLeft: 'auto' }} disabled={busy || cfg.policies.length === 0} onClick={run}>
          {busy ? 'Running…' : `Run ${cfg.n_runs * cfg.policies.length} simulations`}
        </button>
      </div>
      {err && <div style={{ color: 'var(--bad)' }}>{err}</div>}
      {rows.length > 0 && (
        <table>
          <thead>
            <tr>
              <th>Protocol</th><th style={{ width: '34%' }}>Completion time (±95% CI)</th><th>Avg wait</th><th>Duplicates</th>
              <th>Data sent</th><th>vs {PROTOCOL[res.baseline].short}: faster in</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(({ p, v, paired }) => (
              <tr key={p.id}>
                <td><span style={{ display: 'inline-block', width: 8, height: 8, borderRadius: 2, background: p.color, marginRight: 6 }} />
                  <b>{p.short}</b></td>
                <td>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <div style={{ height: 10, width: `${(v.completion_time.mean / maxT) * 100}%`, background: p.color, borderRadius: '0 3px 3px 0' }} />
                    <span className="mono">{f1(v.completion_time.mean)} <span style={{ color: 'var(--text-dim)' }}>±{f1(v.completion_time.ci)}</span></span>
                  </div>
                </td>
                <td className="mono">{f1(v.avg_waiting_time.mean)}</td>
                <td className="mono" style={{ color: v.duplicate_conflicts.mean > 0.05 ? 'var(--bad)' : undefined }}>{v.duplicate_conflicts.mean.toFixed(2)}</td>
                <td className="mono">{f0(v.message_payload.mean)}</td>
                <td className="mono">{paired ? `${paired.wins}/${res.seeds.length} worlds (${paired.mean_reduction >= 0 ? '−' : '+'}${Math.abs(paired.mean_reduction).toFixed(1)} min)` : 'baseline'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Panel>
  )
}

// -- original curated benchmark ---------------------------------------------------------------
function OriginalBenchmark() {
  const [table, setTable] = useState(null)
  useEffect(() => { api.precomputedTable('comparison').then(setTable).catch(() => {}) }, [])
  if (!table) return null
  return (
    <details className="panel" style={{ padding: 12 }}>
      <summary style={{ cursor: 'pointer', color: 'var(--text-dim)' }}>
        Original course benchmark: 20 runs on 10 hand-picked seeds (No Coordination vs MAS)
      </summary>
      <p style={{ color: 'var(--text-dim)', fontSize: 12 }}>
        Kept for reference. On 1,000 random worlds the gain is larger (29% vs 20.9%), so the curated benchmark understated the effect.
      </p>
      <table>
        <thead><tr><th>Metric</th><th>No Coordination</th><th>MAS</th><th>Change</th></tr></thead>
        <tbody>
          {table.map((row) => (
            <tr key={row.metric}>
              <td>{row.metric.replace(/_/g, ' ')}</td>
              <td className="mono">{Number(row.no_coordination_mean).toFixed(2)}</td>
              <td className="mono">{Number(row.mas_mean).toFixed(2)}</td>
              <td className="mono">{Number(row.improvement_pct) >= 0 ? '+' : ''}{Number(row.improvement_pct).toFixed(1)}%</td>
            </tr>
          ))}
        </tbody>
      </table>
    </details>
  )
}
