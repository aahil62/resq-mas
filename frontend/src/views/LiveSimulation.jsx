import { useEffect, useRef, useState } from 'react'
import { api } from '../api.js'
import Grid from '../components/Grid.jsx'

const SPEEDS = [
  { label: '1x', ms: 500 },
  { label: '2x', ms: 250 },
  { label: '4x', ms: 100 },
  { label: '8x', ms: 40 },
]

const SEVERITY_LIST = ['critical', 'high', 'moderate', 'low']

export default function LiveSimulation() {
  const [config, setConfig] = useState({
    policy: 'no_coordination', seed: 11, victim_count: 6, blockage_level: 0.0, rescue_agent_count: 2,
  })
  const [state, setState] = useState(null)
  const [events, setEvents] = useState([])
  const [running, setRunning] = useState(false)
  const [speedIdx, setSpeedIdx] = useState(1)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)
  const timerRef = useRef(null)

  const createScenario = async (overrideConfig) => {
    setLoading(true)
    setError(null)
    setRunning(false)
    try {
      const cfg = overrideConfig || config
      const s = await api.createScenario(cfg)
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
      const newEvents = await api.getEvents(0, 500)
      setEvents(newEvents)
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
      const s = await api.reset()
      setState(s)
      setEvents([])
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 340px', gap: 16, alignItems: 'start' }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <ScenarioForm config={config} setConfig={setConfig} onApply={createScenario} disabled={loading} />

        <div className="panel" style={{ padding: 12 }}>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 10, flexWrap: 'wrap' }}>
            <button className="btn primary" disabled={!state || state.completed} onClick={() => setRunning((r) => !r)}>
              {running ? 'Pause' : 'Run'}
            </button>
            <button className="btn" disabled={!state || running || state.completed} onClick={() => doStep(1)}>Step</button>
            <button className="btn" onClick={handleReset}>Reset</button>
            <span style={{ color: 'var(--text-dim)' }}>Speed</span>
            <select value={speedIdx} onChange={(e) => setSpeedIdx(Number(e.target.value))} className="btn">
              {SPEEDS.map((s, i) => <option key={s.label} value={i}>{s.label}</option>)}
            </select>
            {state && (
              <span style={{ marginLeft: 'auto', color: 'var(--text-dim)' }}>
                Simulation Time: <span className="mono" style={{ color: 'var(--text)' }}>{state.time} min</span>{' '}
                <span className="mono" style={{ opacity: 0.6 }}>/ {state.max_time} min max</span>{' '}
                {state.completed && <b style={{ color: 'var(--good)' }}>COMPLETE</b>}
              </span>
            )}
          </div>
          {error && <div style={{ color: 'var(--bad)', marginBottom: 8 }}>{error}</div>}
          <div style={{ overflow: 'auto' }}>
            <Grid state={state} />
          </div>
          <Legend />
        </div>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <MetricsPanel state={state} />
        <AgentStatusPanel state={state} />
        <EventLog events={events} />
      </div>
    </div>
  )
}

function ScenarioForm({ config, setConfig, onApply, disabled }) {
  const update = (k, v) => setConfig((c) => ({ ...c, [k]: v }))
  return (
    <div className="panel" style={{ padding: 12, display: 'flex', flexDirection: 'column', gap: 10 }}>
      <div style={{ display: 'flex', gap: 4 }}>
        <ModeButton active={config.policy === 'no_coordination'} onClick={() => update('policy', 'no_coordination')}>
          NO COORDINATION
        </ModeButton>
        <ModeButton active={config.policy === 'mas'} onClick={() => update('policy', 'mas')}>
          MULTI-AGENT
        </ModeButton>
      </div>
      <div style={{ display: 'flex', gap: 12, alignItems: 'end', flexWrap: 'wrap' }}>
        <Field label="Seed">
          <input className="btn mono" style={{ width: 70 }} type="number" value={config.seed}
                 onChange={(e) => update('seed', Number(e.target.value))} />
        </Field>
        <Field label="Victims">
          <input className="btn mono" style={{ width: 70 }} type="number" value={config.victim_count}
                 onChange={(e) => update('victim_count', Number(e.target.value))} />
        </Field>
        <Field label="Blockage">
          <input className="btn mono" style={{ width: 70 }} type="number" step="0.05" min="0" max="0.9"
                 value={config.blockage_level} onChange={(e) => update('blockage_level', Number(e.target.value))} />
        </Field>
        <Field label="Rescue agents">
          <input className="btn mono" style={{ width: 70 }} type="number" min="1" max="6" value={config.rescue_agent_count}
                 onChange={(e) => update('rescue_agent_count', Number(e.target.value))} />
        </Field>
        <button className="btn primary" disabled={disabled} onClick={() => onApply()}>Load Scenario</button>
      </div>
    </div>
  )
}

function ModeButton({ active, onClick, children }) {
  return (
    <button
      className="btn"
      style={{
        flex: 1, fontWeight: 700, letterSpacing: '0.04em',
        borderColor: active ? 'var(--accent)' : 'var(--border)',
        color: active ? 'var(--accent)' : 'var(--text-dim)',
        background: active ? 'rgba(41,224,201,0.12)' : 'var(--panel-2)',
      }}
      onClick={onClick}
    >
      {children}
    </button>
  )
}

function Field({ label, children }) {
  return (
    <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 11, color: 'var(--text-dim)' }}>
      {label}
      {children}
    </label>
  )
}

function Legend() {
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
      <span style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
        <span style={{ width: 10, height: 10, background: '#e0af68', display: 'inline-block', borderRadius: 2 }} /> Rescue A
      </span>
      <span style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
        <span style={{ width: 10, height: 10, background: '#bb9af7', display: 'inline-block', borderRadius: 2 }} /> Rescue B
      </span>
    </div>
  )
}

function MetricsPanel({ state }) {
  const m = state?.metrics
  const r = state?.resources
  const activeConflict = m && m.duplicate_conflicts > 0
  return (
    <div className="panel">
      <div className="panel-title">Metrics</div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 2 }}>
        <Stat label="Rescued" value={m ? `${m.victims_rescued}/${m.victims_total}` : '-'} />
        <Stat label="Duplicate Conflicts" value={m ? m.duplicate_conflicts : '-'} highlight={activeConflict} pulse={activeConflict} />
        <Stat label="Medical Kits" value={r ? `${r.medical_kits}/${r.available}` : '-'} />
        <Stat label="Denied Requests" value={r ? r.denied_count : '-'} />
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

function AgentStatusPanel({ state }) {
  return (
    <div className="panel">
      <div className="panel-title">Agent Status</div>
      <table>
        <thead><tr><th>Agent</th><th>Status</th><th>Target</th><th>Pos</th></tr></thead>
        <tbody>
          {(state?.units || []).map((u) => (
            <tr key={u.id}>
              <td>{u.id}</td>
              <td>{u.status}</td>
              <td className="mono">{u.target || '-'}</td>
              <td className="mono">({u.position[0]},{u.position[1]})</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

const HIGHLIGHT_EVENT_TYPES = new Set(['TASK_CONFLICT', 'DUPLICATE_DETECTED', 'TASK_REASSIGNED'])

function EventLog({ events }) {
  const recent = [...events].reverse().slice(0, 80)
  return (
    <div className="panel" style={{ display: 'flex', flexDirection: 'column', height: 360 }}>
      <div className="panel-title">Event Log</div>
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

function formatPayload(payload) {
  if (!payload) return ''
  return Object.entries(payload).map(([k, v]) => `${k}=${JSON.stringify(v)}`).join(' ')
}
