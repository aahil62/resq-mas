import ProtocolChip from '../components/ProtocolChip.jsx'
import { useEffect, useRef, useState } from 'react'
import { api } from '../api.js'
import Grid from '../components/Grid.jsx'
import { takePendingPreset } from '../intent.js'
import { BASE_CONFIG, PRESETS } from '../presets.js'
import { PROTOCOL, PROTOCOLS, SEVERITIES, teamName } from '../protocols.js'

const SPEEDS = [
  { label: 'Slow', ms: 450 },
  { label: 'Normal', ms: 220 },
  { label: 'Fast', ms: 90 },
  { label: 'Fastest', ms: 35 },
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
  const [presetId, setPresetId] = useState('classic')
  const [state, setState] = useState(null)
  const [events, setEvents] = useState([])
  const [running, setRunning] = useState(false)
  const [speedIdx, setSpeedIdx] = useState(1)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)
  const [compare, setCompare] = useState(null)
  const timerRef = useRef(null)

  const load = async (cfg) => {
    setLoading(true)
    setError(null)
    setRunning(false)
    setCompare(null)
    try {
      setState(await api.createScenario(toRequest(cfg)))
      setEvents([])
    } catch (e) {
      setError(`Could not reach the simulator (${e.message}). Is the server running on port 8000?`)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    const pending = PRESETS.find((p) => p.id === takePendingPreset())
    const start = pending || PRESETS[0]
    setPresetId(start.id)
    setConfig(start.config)
    load(start.config)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const doStep = async (n = 1) => {
    try {
      const s = await api.step(n)
      setState(s)
      try { setEvents(await api.getEvents(0, 800)) } catch { /* keep the previous log on a transient error */ }
      if (s.completed) setRunning(false)
    } catch (e) {
      setError(e.message)
      setRunning(false)
    }
  }

  useEffect(() => {
    if (running) timerRef.current = setInterval(() => doStep(1), SPEEDS[speedIdx].ms)
    return () => clearInterval(timerRef.current)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [running, speedIdx])

  const choosePreset = (p) => { setPresetId(p.id); setConfig(p.config); load(p.config) }
  const chooseProtocol = (id) => { const cfg = { ...config, policy: id }; setConfig(cfg); load(cfg) }
  const restart = () => load(config)

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

  const showRadio = state && state.policy !== 'no_coordination' && state.settings.comm_loss > 0

  return (
    <div className="page sim">
      <div className="section-head">
        <div className="eyebrow">Simulator</div>
        <h2>Run a disaster and watch the teams decide</h2>
        <p className="lede">Pick a situation, choose how the rescue teams coordinate, and press Play. Switch strategy at any time to replay the same disaster.</p>
      </div>

      <div className="sim-setup card">
        <div className="setup-row">
          <div className="setup-label">1 · Situation</div>
          <div className="preset-pills" role="radiogroup" aria-label="Situation">
            {PRESETS.map((p) => (
              <button key={p.id} role="radio" aria-checked={presetId === p.id} className="pill" title={p.text}
                      onClick={() => choosePreset(p)} disabled={loading}>{p.title}</button>
            ))}
          </div>
        </div>
        <div className="setup-row">
          <div className="setup-label">2 · How teams coordinate</div>
          <div className="proto-picker" role="radiogroup" aria-label="Coordination strategy">
            {PROTOCOLS.map((p) => (
              <button key={p.id} role="radio" aria-checked={config.policy === p.id} className="proto-btn"
                      style={{ '--pc': p.color }} onClick={() => chooseProtocol(p.id)} disabled={loading} title={p.desc}>
                <span className="proto-name">{p.name}</span>
                <span className="code">{p.short}</span>
              </button>
            ))}
          </div>
        </div>
        <p className="proto-desc small"><b>{PROTOCOL[config.policy].name}.</b> {PROTOCOL[config.policy].desc}</p>
        <details className="more-settings">
          <summary>More settings</summary>
          <SettingsForm config={config} setConfig={setConfig} onApply={() => { setPresetId(null); load(config) }} disabled={loading} />
        </details>
      </div>

      <div className="sim-main">
        <div className="card map-card">
          <div className="map-toolbar">
            <button className="btn primary" disabled={!state || state.completed} onClick={() => setRunning((r) => !r)}>
              {running ? <><PauseIcon /> Pause</> : <><PlayIcon /> Play</>}
            </button>
            <button className="btn" disabled={!state || running || state.completed} onClick={() => doStep(1)}>Step 1 min</button>
            <button className="btn" disabled={!state || running || state.completed} onClick={() => doStep(500)}>Skip to end</button>
            <button className="btn quiet" onClick={restart}>Restart</button>
            <div className="seg" role="radiogroup" aria-label="Speed">
              {SPEEDS.map((s, i) => (
                <button key={s.label} role="radio" aria-checked={speedIdx === i} onClick={() => setSpeedIdx(i)}>{s.label}</button>
              ))}
            </div>
            {state && (
              <div className="clock">
                {running && <span className="live-dot" aria-hidden="true" />}
                <span className="num clock-time">{state.time}</span><span className="muted small">min</span>
                {state.completed && <span className="done-badge">All rescued</span>}
              </div>
            )}
          </div>
          {error && <div className="error-box">{error}</div>}
          <div className="map-wrap"><Grid state={state} /></div>
          <MapLegend showRadio={showRadio} />
        </div>

        <aside className="sim-side">
          <StatusPanel state={state} />
          <TeamsPanel state={state} showRadio={showRadio} />
          <RadioLog events={events} />
        </aside>
      </div>

      <ComparePanel compare={compare} onRun={runComparison} config={config} />
    </div>
  )
}

function SettingsForm({ config, setConfig, onApply, disabled }) {
  const up = (k, v) => setConfig((c) => ({ ...c, [k]: v }))
  return (
    <div className="settings-grid">
      <Num id="set-victims" label="Casualties" value={config.victim_count} min={2} max={60} onChange={(v) => up('victim_count', v)} />
      <Num id="set-teams" label="Rescue teams" value={config.rescue_agent_count} min={1} max={8} onChange={(v) => up('rescue_agent_count', v)} />
      <label className="field-label" htmlFor="set-grid">City size
        <select id="set-grid" className="field" value={config.width} onChange={(e) => up('width', Number(e.target.value))}>
          <option value={15}>Small (15×15)</option><option value={20}>Medium (20×20)</option><option value={25}>Large (25×25)</option>
        </select>
      </label>
      <Num id="set-arrival" label="Reported over (min)" hint="0 = all known at the start" value={config.arrival_window} min={0} max={1000} step={50}
           onChange={(v) => up('arrival_window', v)} />
      <Num id="set-loss" label="Messages lost (%)" value={Math.round(config.comm_loss * 100)} min={0} max={100} step={5}
           onChange={(v) => up('comm_loss', v / 100)} />
      {config.comm_loss > 0 && (
        <label className="field-label" htmlFor="set-pattern">Loss pattern
          <select id="set-pattern" className="field" value={config.loss_pattern} onChange={(e) => up('loss_pattern', e.target.value)}>
            <option value="independent">Random drops</option><option value="bursty">Radio outages</option>
          </select>
        </label>
      )}
      {config.comm_loss > 0 && config.loss_pattern === 'bursty' && (
        <Num id="set-burst" label="Outage length (min)" value={config.burst_length} min={1} max={100} onChange={(v) => up('burst_length', v)} />
      )}
      <Num id="set-block" label="Roads blocked (%)" value={Math.round(config.blockage_level * 100)} min={0} max={90} step={5}
           onChange={(v) => up('blockage_level', v / 100)} />
      <Num id="set-seed" label="Disaster number" hint="same number = same city and casualties" value={config.seed} onChange={(v) => up('seed', v)} />
      <button className="btn primary" disabled={disabled} onClick={onApply} style={{ alignSelf: 'end' }}>Apply settings</button>
    </div>
  )
}

function Num({ id, label, hint, value, onChange, min, max, step = 1 }) {
  return (
    <label className="field-label" htmlFor={id} title={hint}>
      {label}
      <input id={id} className="field num" type="number" min={min} max={max} step={step} value={value}
             onChange={(e) => onChange(Number(e.target.value))} />
    </label>
  )
}

function MapLegend({ showRadio }) {
  return (
    <div className="map-legend small">
      {SEVERITIES.map((s) => (
        <span key={s.id}><i className="lg-dot" style={{ background: `var(--sev-${s.id})` }} />{s.label}</span>
      ))}
      <span><i className="lg-unit">A</i>Rescue team</span>
      <span><i className="lg-sq" style={{ background: 'var(--c-hospital)' }} />Hospital</span>
      <span><i className="lg-sq" style={{ background: 'var(--c-depot)' }} />Base</span>
      <span><i className="lg-sq" style={{ background: 'var(--c-building)' }} />Building</span>
      <span><i className="lg-sq" style={{ background: 'var(--c-blocked)' }} />Blocked road</span>
      <span><i className="lg-ring" />Two teams on one casualty</span>
      {showRadio && <span><i className="lg-unit" style={{ boxShadow: '0 0 0 2px var(--bad)' }}>B</i>Radio outage</span>}
    </div>
  )
}

function StatusPanel({ state }) {
  const m = state?.metrics
  const waiting = m ? m.victims_known - m.victims_rescued : 0
  const incoming = m ? m.victims_total - m.victims_known : 0
  return (
    <div className="card status-card">
      <div className="status-top">
        <div>
          <div className="status-big num">{m ? m.victims_rescued : '–'}<span className="muted">/{m ? m.victims_total : '–'}</span></div>
          <div className="muted small">casualties at hospital</div>
        </div>
        {state && <ProtocolChip id={state.policy} />}
      </div>
      <Progress value={m ? m.victims_rescued / m.victims_total : 0} />
      <div className="status-grid">
        <Stat label="Still waiting" value={m ? waiting : '–'} />
        <Stat label="Not yet reported" value={m ? incoming : '–'} />
        <Stat label="Average wait" value={m?.avg_waiting_time != null ? `${m.avg_waiting_time.toFixed(0)} min` : '–'} />
        <Stat label="Duplicate chases" value={m ? m.duplicate_conflicts : '–'} bad={m && m.duplicate_conflicts > 0} />
        <Stat label="Wasted team-minutes" value={m ? m.wasted_ticks : '–'} bad={m && m.wasted_ticks > 0} />
        <Stat label="Messages sent" value={m ? m.messages : '–'} />
      </div>
    </div>
  )
}

function Progress({ value }) {
  return (
    <div className="progress" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(value * 100)}>
      <div style={{ width: `${value * 100}%` }} />
    </div>
  )
}

function Stat({ label, value, bad }) {
  return (
    <div className="stat">
      <div className="value" style={{ color: bad ? 'var(--bad)' : undefined }}>{value}</div>
      <div className="label">{label}</div>
    </div>
  )
}

const STATUS = { idle: 'Waiting', moving_to_victim: 'Heading to casualty', moving_to_hospital: 'Driving to hospital' }

function TeamsPanel({ state, showRadio }) {
  return (
    <div className="card">
      <div className="panel-title">Rescue teams</div>
      <div className="table-wrap">
        <table>
          <tbody>
            {(state?.units || []).map((u) => (
              <tr key={u.id}>
                <td><span className="lg-unit" style={{ marginRight: 8 }}>{u.id.slice(-1).toUpperCase()}</span>{teamName(u.id)}</td>
                <td className="muted">{STATUS[u.status] || u.status}{u.target ? ` · ${u.target}` : ''}</td>
                {showRadio && (
                  <td style={{ color: u.channel_ok ? 'var(--good)' : 'var(--bad)', fontWeight: 600 }}>{u.channel_ok ? 'Radio ok' : 'Outage'}</td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function listTeams(ids) {
  const letters = ids.map((id) => id.slice(-1).toUpperCase())
  if (letters.length <= 1) return `Team ${letters[0] || ''}`
  return `Teams ${letters.slice(0, -1).join(', ')} and ${letters[letters.length - 1]}`
}

// Plain-language radio log: the engine's event stream, rewritten for people.
function describe(e) {
  const p = e.payload || {}
  const who = e.source.startsWith('rescue_') ? teamName(e.source) : e.source === 'medical' ? 'Medical' : e.source === 'logistics' ? 'Logistics' : 'Dispatch'
  switch (e.type) {
    case 'VICTIM_DETECTED': return { who, text: `New casualty ${p.victim_id} reported (${p.severity}).` }
    case 'TARGET_SELECTED': return { who, text: `Heads for ${p.victim_id} without telling anyone.` }
    case 'TASK_PROPOSED': return { who, text: `Proposes to take ${p.victim_id}.` }
    case 'TASK_CONFLICT': return { who, text: `Two teams want ${p.victim_id}. ${teamName(p.winner)} gets it.`, alert: true }
    case 'TASK_ASSIGNED': return { who, text: `Confirmed on ${p.victim_id}.` }
    case 'TASK_REASSIGNED': return { who, text: `Gives up ${p.victim_id}${p.reason === 'victim_already_rescued' ? ': another team already took them' : ''}.`, alert: true }
    case 'DUPLICATE_DETECTED': return { who, text: `${listTeams(p.agents || [])} are all chasing ${p.victim_id}.`.replace(' are all chasing', (p.agents || []).length === 2 ? ' are both chasing' : ' are all chasing'), alert: true }
    case 'VICTIM_RESCUED': return { who, text: `Delivered ${p.victim_id} to hospital after ${p.waiting_time} min.`, good: true }
    case 'ROAD_BLOCKED': return { who: 'Roads', text: 'A road is now blocked.' }
    case 'ROAD_OPENED': return { who: 'Roads', text: 'A road has reopened.' }
    case 'ROUTE_REPLANNED': return { who, text: 'Found a new route around a blockage.' }
    default: return null
  }
}

function RadioLog({ events }) {
  const lines = [...events].reverse().map((e) => ({ e, d: describe(e) })).filter((x) => x.d).slice(0, 80)
  return (
    <div className="card log-card">
      <div className="panel-title">Radio log</div>
      <div className="log-body">
        {lines.length === 0 && <div className="muted small">Press Play to start. Decisions appear here as they happen.</div>}
        {lines.map(({ e, d }, i) => (
          <div key={i} className={`log-line${d.alert ? ' alert' : ''}${d.good ? ' good' : ''}`}>
            <span className="num log-t">{e.timestamp}′</span>
            <span><b>{d.who}</b> {d.text}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

function ComparePanel({ compare, onRun, config }) {
  const rows = compare?.result ? PROTOCOLS.map((p) => ({ p, v: compare.result.per_policy[p.id] })).filter((r) => r.v) : []
  const maxT = Math.max(1, ...rows.map((r) => r.v.completion_time.mean))
  const best = rows.length ? Math.min(...rows.map((r) => r.v.completion_time.mean)) : null
  return (
    <div className="card compare-card">
      <div className="compare-head">
        <div>
          <h3>Same disaster, every strategy</h3>
          <p className="muted small">Runs all six strategies on disaster #{config.seed} with your current settings and lines them up.</p>
        </div>
        <button className="btn primary" disabled={compare?.loading} onClick={onRun}>
          {compare?.loading ? 'Running…' : 'Compare all six'}
        </button>
      </div>
      {compare?.error && <div className="error-box">{compare.error}</div>}
      {rows.length > 0 && (
        <div className="table-wrap">
          <table>
            <thead><tr><th>Strategy</th><th style={{ width: '40%' }}>Time to rescue everyone</th><th>Average wait</th><th>Duplicate chases</th><th>Messages</th></tr></thead>
            <tbody>
              {rows.map(({ p, v }) => (
                <tr key={p.id}>
                  <td><ProtocolChip id={p.id} /></td>
                  <td>
                    <div className="bar-cell">
                      <div className="bar" style={{ width: `${(v.completion_time.mean / maxT) * 100}%`, background: p.color }} />
                      <span className="num">{v.completion_time.mean.toFixed(0)} min</span>
                      {v.completion_time.mean === best && <span className="best">fastest</span>}
                    </div>
                  </td>
                  <td className="num">{v.avg_waiting_time.mean.toFixed(0)} min</td>
                  <td className="num" style={{ color: v.duplicate_conflicts.mean > 0 ? 'var(--bad)' : undefined }}>{v.duplicate_conflicts.mean.toFixed(0)}</td>
                  <td className="num">{v.messages.mean.toFixed(0)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

const PlayIcon = () => (<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M7 4v16l13-8z" /></svg>)
const PauseIcon = () => (<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M6 4h4v16H6zM14 4h4v16h-4z" /></svg>)
