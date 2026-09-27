import { useEffect, useRef, useState } from 'react'
import { api } from '../api.js'
import Grid from '../components/Grid.jsx'
import { PROTOCOL, PROTOCOLS, unitColor, unitLetter } from '../protocols.js'

const SPEEDS = [
  { label: '1x', ms: 500 },
  { label: '2x', ms: 250 },
  { label: '4x', ms: 100 },
  { label: '8x', ms: 40 },
]

const SEVERITY_LIST = ['critical', 'high', 'moderate', 'low']

const BASE_CONFIG = {
  policy: 'no_coordination', seed: 11, victim_count: 6, blockage_level: 0.0, rescue_agent_count: 2,
  width: 15, arrival_window: 0, comm_loss: 0, loss_pattern: 'independent', burst_length: 5,
}

// One-click scenarios that reproduce the paper's key situations.
const PRESETS = [
  {
    label: 'Classic duplicate', hint: 'Seed 11: both agents want the same critical victim at t=0.',
    config: { ...BASE_CONFIG },
  },
  {
    label: 'Crowded incident', hint: '8 agents, 20 victims: independent agents herd onto the same victims.',
    config: { ...BASE_CONFIG, seed: 1001, victim_count: 20, rescue_agent_count: 8, width: 20 },
  },
  {
    label: 'Victims arriving', hint: '20 victims reported over 200 minutes: same-minute collisions become the norm.',
    config: { ...BASE_CONFIG, seed: 1001, victim_count: 20, rescue_agent_count: 4, width: 20, arrival_window: 200, policy: 'claim' },
  },
  {
    label: 'Bad radio', hint: '30% of messages lost in 5-minute outages: watch agents drop off the network.',
    config: { ...BASE_CONFIG, seed: 1001, victim_count: 20, rescue_agent_count: 4, width: 20, comm_loss: 0.3, loss_pattern: 'bursty', policy: 'cbba' },
  },
]

function toRequest(cfg) {
  return {
    policy: cfg.policy, seed: cfg.seed, victim_count: cfg.victim_count, blockage_level: cfg.blockage_level,
    rescue_agent_count: cfg.rescue_agent_count, width: cfg.width, height: cfg.width,
    arrival_window: cfg.arrival_window, comm_loss: cfg.comm_loss,
    burst_length: cfg.comm_loss > 0 && cfg.loss_pattern === 'bursty' ? cfg.burst_length : null,
    max_time: 3000,
  }
}

export default function LiveSimulation() {
  const [config, setConfig] = useState(BASE_CONFIG)
  const [state, setState] = useState(null)
  const [events, setEvents] = useState([])
  const [running, setRunning] = useState(false)
  const [speedIdx, setSpeedIdx] = useState(1)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)
  const [compare, setCompare] = useState(null)
  const timerRef = useRef(null)

  const createScenario = async (overrideConfig) => {
    setLoading(true)
    setError(null)
    setRunning(false)
    try {
      const cfg = overrideConfig || config
      const s = await api.createScenario(toRequest(cfg))
      setState(s)
      setEvents([])
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { createScenario() }, [])

  const refreshEvents = async () => {
    try {
      setEvents(await api.getEvents(0, 800))
    } catch { /* ignore transient errors while polling */ }
  }

  const doStep = async (n = 1) => {
    try {
      const s = await api.step(n)
      setState(s)
      await refreshEvents()
      if (s.completed) setRunning(false)
    } catch (e) {
      setError(e.message)
      setRunning(false)
    }
  }

  useEffect(() => {
    if (running) {
      timerRef.current = setInterval(() => doStep(1), SPEEDS[speedIdx].ms)
    }
    return () => clearInterval(timerRef.current)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [running, speedIdx])

  const handleReset = async () => {
    setRunning(false)
    setLoading(true)
    try {
      setState(await api.reset())
      setEvents([])
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const applyPreset = (preset) => {
    setConfig(preset.config)
    setCompare(null)
    createScenario(preset.config)
  }

  const runComparison = async () => {
    setCompare({ loading: true })
    try {
      const req = toRequest(config)
      const res = await api.runExperiment({
        victim_count: req.victim_count, blockage_level: req.blockage_level, base_seed: req.seed, n_runs: 1,
        rescue_agent_count: req.rescue_agent_count, max_time: req.max_time, width: req.width,
        policies: PROTOCOLS.map((p) => p.id), arrival_window: req.arrival_window, comm_loss: req.comm_loss,
        burst_length: req.burst_length,
      })
      setCompare({ result: res })
    } catch (e) {
      setCompare({ error: e.message })
    }
  }

  const communicates = state && state.policy !== 'no_coordination' && state.settings.comm_loss > 0

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) 360px', gap: 16, alignItems: 'start' }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12, minWidth: 0 }}>
        <ScenarioForm config={config} setConfig={setConfig} onApply={() => { setCompare(null); createScenario() }}
                      onPreset={applyPreset} disabled={loading} />

        <div className="panel" style={{ padding: 12 }}>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 10, flexWrap: 'wrap' }}>
            <button className="btn primary" disabled={!state || state.completed} onClick={() => setRunning((r) => !r)}>
              {running ? 'Pause' : 'Run'}
            </button>
            <button className="btn" disabled={!state || running || state.completed} onClick={() => doStep(1)}>Step</button>
            <button className="btn" disabled={!state || running || state.completed} onClick={() => doStep(500)}
                    title="Run to completion instantly">Finish</button>
            <button className="btn" onClick={handleReset}>Reset</button>
            <span style={{ color: 'var(--text-dim)' }}>Speed</span>
            <select value={speedIdx} onChange={(e) => setSpeedIdx(Number(e.target.value))} className="btn">
              {SPEEDS.map((s, i) => <option key={s.label} value={i}>{s.label}</option>)}
            </select>
            {state && (
              <span style={{ marginLeft: 'auto', color: 'var(--text-dim)' }}>
                <ProtocolBadge id={state.policy} />{' '}
                Time: <span className="mono" style={{ color: 'var(--text)' }}>{state.time} min</span>{' '}
                {state.completed && <b style={{ color: 'var(--good)' }}>COMPLETE</b>}
              </span>
            )}
          </div>
          {error && <div style={{ color: 'var(--bad)', marginBottom: 8 }}>{error}</div>}
          <div style={{ overflow: 'auto' }}>
            <Grid state={state} />
          </div>
          <Legend units={state?.units || []} showRadio={communicates} />
        </div>

        <ComparePanel compare={compare} onRun={runComparison} config={config} />
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <MetricsPanel state={state} />
        <AgentStatusPanel state={state} showRadio={communicates} />
        <EventLog events={events} />
      </div>
    </div>
  )
}

function ScenarioForm({ config, setConfig, onApply, onPreset, disabled }) {
  const update = (k, v) => setConfig((c) => ({ ...c, [k]: v }))
  const selected = PROTOCOL[config.policy]
  return (
    <div className="panel" style={{ padding: 12, display: 'flex', flexDirection: 'column', gap: 10 }}>
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
        <span style={{ fontSize: 11, color: 'var(--text-dim)', marginRight: 4 }}>PRESETS</span>
        {PRESETS.map((p) => (
          <button key={p.label} className="btn" title={p.hint} disabled={disabled} onClick={() => onPreset(p)}
                  style={{ fontSize: 11, padding: '3px 9px' }}>
            {p.label}
          </button>
        ))}
      </div>
      <div role="radiogroup" aria-label="Allocation protocol"
           style={{ display: 'grid', gridTemplateColumns: 'repeat(6, minmax(0, 1fr))', gap: 4 }}>
        {PROTOCOLS.map((p) => (
          <ModeButton key={p.id} active={config.policy === p.id} color={p.color} onClick={() => update('policy', p.id)}
                      title={p.desc}>
            <span style={{ display: 'block', fontSize: 12 }}>{p.short}</span>
            <span style={{ display: 'block', fontSize: 9, fontWeight: 400, opacity: 0.85, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
              {p.label}
            </span>
          </ModeButton>
        ))}
      </div>
      <div style={{ fontSize: 11.5, color: 'var(--text-dim)', minHeight: 18 }}>
        <b style={{ color: 'var(--text)' }}>{selected.label}:</b> {selected.desc}
      </div>
      <div style={{ display: 'flex', gap: 12, alignItems: 'end', flexWrap: 'wrap' }}>
        <NumField label="Seed" value={config.seed} onChange={(v) => update('seed', v)} />
        <NumField label="Victims" value={config.victim_count} min={2} max={60} onChange={(v) => update('victim_count', v)} />
        <NumField label="Rescue agents" value={config.rescue_agent_count} min={1} max={8} onChange={(v) => update('rescue_agent_count', v)} />
        <Field label="Grid">
          <select className="btn mono" value={config.width} onChange={(e) => update('width', Number(e.target.value))}>
            <option value={15}>15×15</option>
            <option value={20}>20×20</option>
            <option value={25}>25×25</option>
          </select>
        </Field>
        <NumField label="Blockage" value={config.blockage_level} step={0.05} min={0} max={0.9}
                  onChange={(v) => update('blockage_level', v)} />
        <NumField label="Arrival window (min)" value={config.arrival_window} step={50} min={0} max={1000}
                  width={96} onChange={(v) => update('arrival_window', v)}
                  title="0 = all victims known at the start; otherwise victims appear at random times in this window" />
        <NumField label="Message loss (%)" value={Math.round(config.comm_loss * 100)} step={5} min={0} max={100}
                  width={90} onChange={(v) => update('comm_loss', v / 100)} />
        {config.comm_loss > 0 && (
          <Field label="Loss pattern">
            <select className="btn mono" value={config.loss_pattern} onChange={(e) => update('loss_pattern', e.target.value)}>
              <option value="independent">independent</option>
              <option value="bursty">bursty outages</option>
            </select>
          </Field>
        )}
        {config.comm_loss > 0 && config.loss_pattern === 'bursty' && (
          <NumField label="Outage length (min)" value={config.burst_length} min={1} max={100} width={90}
                    onChange={(v) => update('burst_length', v)} />
        )}
        <button className="btn primary" disabled={disabled} onClick={() => onApply()}>Load Scenario</button>
      </div>
    </div>
  )
}

function ModeButton({ active, onClick, children, color, title }) {
  return (
    <button
      className="btn"
      role="radio"
      aria-checked={active}
      title={title}
      style={{
        fontWeight: 700, letterSpacing: '0.03em', textAlign: 'center', minWidth: 0, padding: '5px 4px',
        borderColor: active ? color : 'var(--border)',
        color: active ? 'var(--text)' : 'var(--text-dim)',
        background: active ? `${color}33` : 'var(--panel-2)',
        boxShadow: active ? `inset 0 -3px 0 ${color}` : 'none',
      }}
      onClick={onClick}
    >
      {children}
    </button>
  )
}

function ProtocolBadge({ id }) {
  const p = PROTOCOL[id]
  if (!p) return null
  return (
    <span style={{ border: `1px solid ${p.color}`, borderRadius: 4, padding: '1px 6px', color: 'var(--text)', fontSize: 11 }}>
      <span style={{ display: 'inline-block', width: 7, height: 7, borderRadius: 2, background: p.color, marginRight: 5 }} />
      {p.short}
    </span>
  )
}

function Field({ label, children, title }) {
  return (
    <label title={title} style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 11, color: 'var(--text-dim)' }}>
      {label}
      {children}
    </label>
  )
}

function NumField({ label, value, onChange, min, max, step = 1, width = 70, title }) {
  return (
    <Field label={label} title={title}>
      <input className="btn mono" style={{ width }} type="number" min={min} max={max} step={step} value={value}
             onChange={(e) => onChange(Number(e.target.value))} />
    </Field>
  )
}

function Legend({ units, showRadio }) {
  const items = [
    ['road', 'var(--c-road)'], ['building', 'var(--c-building)'], ['hospital', 'var(--c-hospital)'],
    ['depot', 'var(--c-depot)'], ['blocked', 'var(--c-blocked)'],
  ]
  return (
    <div style={{ display: 'flex', gap: 14, marginTop: 10, flexWrap: 'wrap', fontSize: 11, color: 'var(--text-dim)' }}>
      {items.map(([label, color]) => (
        <span key={label} style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
          <span style={{ width: 10, height: 10, background: color, display: 'inline-block', borderRadius: 2 }} />
          {label}
        </span>
      ))}
      {SEVERITY_LIST.map((sev) => (
        <span key={sev} style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
          <span style={{ width: 10, height: 10, background: `var(--sev-${sev})`, display: 'inline-block', borderRadius: '50%' }} />
          victim: {sev}
        </span>
      ))}
      {units.map((u) => (
        <span key={u.id} style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
          <span style={{ width: 10, height: 10, background: unitColor(u.id), display: 'inline-block', borderRadius: 2 }} />
          Rescue {unitLetter(u.id)}
        </span>
      ))}
      {showRadio && (
        <span style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
          <span style={{ width: 10, height: 10, border: '2px solid var(--bad)', display: 'inline-block', borderRadius: 2 }} />
          radio outage
        </span>
      )}
    </div>
  )
}

function MetricsPanel({ state }) {
  const m = state?.metrics
  const r = state?.resources
  const activeConflict = m && m.duplicate_conflicts > 0
  const incoming = m ? m.victims_total - m.victims_known : 0
  return (
    <div className="panel">
      <div className="panel-title">Metrics</div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 2 }}>
        <Stat label={incoming > 0 ? `Rescued (${incoming} not yet reported)` : 'Rescued'}
              value={m ? `${m.victims_rescued}/${m.victims_total}` : '-'} />
        <Stat label="Duplicate Conflicts" value={m ? m.duplicate_conflicts : '-'} highlight={activeConflict} pulse={activeConflict} />
        <Stat label="Avg Victim Wait" value={m?.avg_waiting_time != null ? `${m.avg_waiting_time.toFixed(1)} min` : '-'} />
        <Stat label="Wasted Agent-min" value={m ? m.wasted_ticks : '-'} highlight={m && m.wasted_ticks > 0} />
        <Stat label="Messages Sent" value={m ? m.messages : '-'} />
        <Stat label="Data Sent (values)" value={m ? m.message_payload : '-'} />
        <Stat label="Medical Kits" value={r ? `${r.medical_kits}/${r.available}` : '-'} />
        {m && m.consensus_rounds > 0
          ? <Stat label="CBBA Consensus Rounds" value={m.consensus_rounds} />
          : <Stat label="Denied Kit Requests" value={r ? r.denied_count : '-'} />}
      </div>
    </div>
  )
}

function Stat({ label, value, highlight, pulse }) {
  return (
    <div className="stat">
      <div className="value" style={{
        color: highlight ? 'var(--bad)' : undefined,
        animation: pulse ? 'pulse-alert 1.6s var(--ease-out) infinite' : undefined,
      }}>
        {value}
      </div>
      <div className="label">{label}</div>
    </div>
  )
}

function AgentStatusPanel({ state, showRadio }) {
  return (
    <div className="panel">
      <div className="panel-title">Agent Status</div>
      <table>
        <thead>
          <tr><th>Agent</th><th>Status</th><th>Target</th>{showRadio && <th>Radio</th>}<th>Pos</th></tr>
        </thead>
        <tbody>
          {(state?.units || []).map((u) => (
            <tr key={u.id}>
              <td>
                <span style={{ display: 'inline-block', width: 8, height: 8, borderRadius: 2, background: unitColor(u.id), marginRight: 6 }} />
                {u.id}
              </td>
              <td>{STATUS_LABEL[u.status] || u.status}</td>
              <td className="mono">{u.target || '-'}</td>
              {showRadio && (
                <td className="mono" style={{ color: u.channel_ok ? 'var(--good)' : 'var(--bad)' }}>
                  {u.channel_ok ? 'ok' : 'OUTAGE'}
                </td>
              )}
              <td className="mono">({u.position[0]},{u.position[1]})</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

const STATUS_LABEL = { idle: 'idle', moving_to_victim: '→ victim', moving_to_hospital: '→ hospital' }

const HIGHLIGHT_EVENT_TYPES = new Set(['TASK_CONFLICT', 'DUPLICATE_DETECTED', 'TASK_REASSIGNED'])
const NOISY_EVENT_TYPES = new Set(['PRIORITY_UPDATED'])

function EventLog({ events }) {
  const [showNoisy, setShowNoisy] = useState(false)
  const recent = [...events].reverse().filter((e) => showNoisy || !NOISY_EVENT_TYPES.has(e.type)).slice(0, 120)
  return (
    <div className="panel" style={{ display: 'flex', flexDirection: 'column', height: 380 }}>
      <div className="panel-title" style={{ display: 'flex', alignItems: 'center' }}>
        Event Log
        <label style={{ marginLeft: 'auto', fontSize: 10, textTransform: 'none', letterSpacing: 0, display: 'flex', gap: 4, alignItems: 'center' }}>
          <input type="checkbox" checked={showNoisy} onChange={(e) => setShowNoisy(e.target.checked)} />
          show priority updates
        </label>
      </div>
      <div className="mono" style={{ overflowY: 'auto', padding: '6px 10px', fontSize: 11, flex: 1 }}>
        {recent.length === 0 && <div style={{ color: 'var(--text-dim)', fontFamily: 'var(--font-display)' }}>No events yet.</div>}
        {recent.map((e, i) => (
          <div key={i} style={{ marginBottom: 3, color: HIGHLIGHT_EVENT_TYPES.has(e.type) ? 'var(--bad)' : 'var(--text-dim)' }}>
            <span style={{ color: 'var(--accent)' }}>[{e.timestamp} min]</span> {e.source}: <b style={{ color: HIGHLIGHT_EVENT_TYPES.has(e.type) ? 'var(--bad)' : 'var(--text)' }}>{e.type}</b> {formatPayload(e.payload)}
          </div>
        ))}
      </div>
    </div>
  )
}

function formatValue(v) {
  if (typeof v === 'number') return Number.isInteger(v) ? String(v) : v.toFixed(2)
  if (Array.isArray(v)) return `[${v.map(formatValue).join(', ')}]`
  if (v && typeof v === 'object') return JSON.stringify(v)
  return JSON.stringify(v)
}

function formatPayload(payload) {
  if (!payload) return ''
  return Object.entries(payload).map(([k, v]) => `${k}=${formatValue(v)}`).join(' ')
}

function ComparePanel({ compare, onRun, config }) {
  const rows = compare?.result
    ? PROTOCOLS.map((p) => ({ p, v: compare.result.per_policy[p.id] })).filter((r) => r.v)
    : []
  const maxT = Math.max(1, ...rows.map((r) => r.v.completion_time.mean))
  return (
    <div className="panel" style={{ padding: 12 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
        <div>
          <div style={{ fontWeight: 700, color: 'var(--accent)' }}>Same world, every protocol</div>
          <div style={{ fontSize: 11.5, color: 'var(--text-dim)' }}>
            Runs all six protocols on seed {config.seed} with the settings above and compares them side by side.
          </div>
        </div>
        <button className="btn primary" style={{ marginLeft: 'auto' }} disabled={compare?.loading} onClick={onRun}>
          {compare?.loading ? 'Running…' : 'Compare all protocols'}
        </button>
      </div>
      {compare?.error && <div style={{ color: 'var(--bad)', marginTop: 8 }}>{compare.error}</div>}
      {rows.length > 0 && (
        <table style={{ marginTop: 10 }}>
          <thead>
            <tr><th>Protocol</th><th style={{ width: '38%' }}>Completion time</th><th>Avg wait</th><th>Duplicates</th><th>Data sent</th></tr>
          </thead>
          <tbody>
            {rows.map(({ p, v }) => (
              <tr key={p.id}>
                <td><ProtocolBadge id={p.id} /> <span style={{ color: 'var(--text-dim)', fontSize: 11 }}>{p.label}</span></td>
                <td>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <div style={{ height: 10, width: `${(v.completion_time.mean / maxT) * 100}%`, background: p.color, borderRadius: '0 3px 3px 0', minWidth: 2 }} />
                    <span className="mono">{v.completion_time.mean.toFixed(0)} min</span>
                  </div>
                </td>
                <td className="mono">{v.avg_waiting_time.mean.toFixed(1)} min</td>
                <td className="mono" style={{ color: v.duplicate_conflicts.mean > 0 ? 'var(--bad)' : undefined }}>
                  {v.duplicate_conflicts.mean.toFixed(0)}
                </td>
                <td className="mono">{v.message_payload.mean.toFixed(0)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
