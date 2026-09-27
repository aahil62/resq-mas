import { useEffect, useMemo, useRef, useState } from 'react'
import { api } from '../api.js'
import { PROTOCOL } from '../protocols.js'

// Same disaster, two strategies, played side by side from recorded engine runs.
const LANES = ['no_coordination', 'mas']
const FRAME_MS = 140

export default function RaceReplay() {
  const [runs, setRuns] = useState(null)
  const [error, setError] = useState(null)
  const [t, setT] = useState(0)
  const [playing, setPlaying] = useState(false)
  const timer = useRef(null)

  useEffect(() => {
    Promise.all(LANES.map((p) => api.replay(p))).then((rs) => {
      setRuns(rs)
      const reduce = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
      if (reduce) setT(Math.max(...rs.map((r) => r.frames.length - 1)))
      else setPlaying(true)
    }).catch((e) => setError(e.message))
  }, [])

  const maxT = runs ? Math.max(...runs.map((r) => r.frames.length - 1)) : 0
  useEffect(() => {
    if (!playing) return undefined
    timer.current = setInterval(() => {
      setT((x) => {
        if (x >= maxT) { setPlaying(false); return x }
        return x + 1
      })
    }, FRAME_MS)
    return () => clearInterval(timer.current)
  }, [playing, maxT])

  const replay = () => { setT(0); setPlaying(true) }

  if (error) {
    return (
      <div className="card race">
        <p className="muted">The live demo needs the simulator server. Start it with <code>uvicorn backend.app.main:app --port 8000</code>.</p>
      </div>
    )
  }
  return (
    <div className="card race" aria-label="Side-by-side replay of the same disaster under two strategies">
      <div className="race-head">
        <span className="live-dot" aria-hidden="true" />
        <b>Same disaster, two strategies</b>
        <span className="muted small">2 rescue teams · 6 casualties</span>
        <button className="btn" style={{ marginLeft: 'auto' }} onClick={playing ? () => setPlaying(false) : replay} disabled={!runs}>
          {playing ? 'Pause' : t >= maxT && runs ? 'Replay' : 'Play'}
        </button>
      </div>
      <div className="race-lanes">
        {LANES.map((id, i) => <Lane key={id} id={id} run={runs?.[i]} t={t} />)}
      </div>
    </div>
  )
}

function Lane({ id, run, t }) {
  const p = PROTOCOL[id]
  const frame = run ? run.frames[Math.min(t, run.frames.length - 1)] : null
  const done = run && t >= run.frames.length - 1
  const rescued = new Set(frame?.rescued || [])
  const dupTargets = useMemo(() => {
    if (!frame) return new Set()
    const count = {}
    frame.units.forEach(([, , tgt]) => { if (tgt) count[tgt] = (count[tgt] || 0) + 1 })
    return new Set(Object.keys(count).filter((k) => count[k] > 1))
  }, [frame])

  return (
    <div className="lane">
      <div className="lane-head">
        <span className="chip"><span className="dot" style={{ background: p.color }} />{p.name}</span>
        <span className="num lane-clock">{frame ? frame.t : 0}<span className="muted small"> min</span></span>
      </div>
      <div className="lane-map">
        {run ? <MiniMap run={run} frame={frame} rescued={rescued} dupTargets={dupTargets} /> : <div className="muted small">Loading…</div>}
      </div>
      <div className="lane-foot small">
        <span>Rescued <b className="num">{rescued.size}/{run?.victims.length ?? 6}</b></span>
        <span style={{ color: frame?.duplicates ? 'var(--bad)' : undefined }}>
          Duplicate chases <b className="num">{frame?.duplicates ?? 0}</b>
        </span>
        {done && <span className="done-badge">Done in {frame.t} min</span>}
      </div>
    </div>
  )
}

function MiniMap({ run, frame, rescued, dupTargets }) {
  const n = run.grid.length
  const C = 10
  const victimPos = Object.fromEntries(run.victims.map((v) => [v.id, v.position]))
  return (
    <svg viewBox={`0 0 ${n * C} ${n * C}`} style={{ width: '100%', display: 'block' }} role="img" aria-label="City grid">
      <rect width={n * C} height={n * C} fill="var(--c-road)" />
      {run.grid.flatMap((row, r) => row.map((cell, c) => (cell === 'building' || cell === 'hospital' || cell === 'depot') ? (
        <rect key={`${r}-${c}`} x={c * C + 0.5} y={r * C + 0.5} width={C - 1} height={C - 1} rx="1.5"
              fill={cell === 'building' ? 'var(--c-building)' : cell === 'hospital' ? 'var(--c-hospital)' : 'var(--c-depot)'} />
      ) : null))}
      <text x={run.hospital[1] * C + C / 2} y={run.hospital[0] * C + C / 2 + 3} textAnchor="middle" fontSize="8" fontWeight="700" fill="#fff">+</text>
      {frame.units.map(([r, c, tgt], i) => tgt && victimPos[tgt] && !rescued.has(tgt) ? (
        <line key={`l${i}`} x1={c * C + C / 2} y1={r * C + C / 2} x2={victimPos[tgt][1] * C + C / 2} y2={victimPos[tgt][0] * C + C / 2}
              stroke={dupTargets.has(tgt) ? 'var(--bad)' : 'var(--unit)'} strokeWidth="1" strokeDasharray="2 2" opacity="0.7" />
      ) : null)}
      {run.victims.map((v) => (
        <circle key={v.id} cx={v.position[1] * C + C / 2} cy={v.position[0] * C + C / 2} r={rescued.has(v.id) ? 2 : 3.6}
                fill={`var(--sev-${v.severity})`} opacity={rescued.has(v.id) ? 0.25 : 1}
                stroke={dupTargets.has(v.id) ? 'var(--bad)' : 'none'} strokeWidth="1.5" />
      ))}
      {frame.units.map(([r, c], i) => (
        <g key={`u${i}`}>
          <rect x={c * C + 1} y={r * C + 1} width={C - 2} height={C - 2} rx="2" fill="var(--unit)" />
          <text x={c * C + C / 2} y={r * C + C / 2 + 2.6} textAnchor="middle" fontSize="7" fontWeight="700" fill="var(--unit-ink)">
            {String.fromCharCode(65 + i)}
          </text>
        </g>
      ))}
    </svg>
  )
}
