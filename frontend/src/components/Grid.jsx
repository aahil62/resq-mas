import { unitLetter } from '../protocols.js'

// The city map as a scalable SVG: roads, buildings, hospital, bases, blocked
// roads, casualties in triage-tag colours, and rescue teams with their planned
// routes. A casualty chased by two teams at once gets a red ring.
const C = 20

export default function Grid({ state }) {
  if (!state) return <div className="map-empty muted">Loading the city…</div>
  const { width, height, cells } = state.grid
  const blocked = new Set(state.blocked_cells.map(([r, c]) => `${r},${c}`))
  const showRadio = state.policy !== 'no_coordination' && state.settings?.comm_loss > 0

  const chasers = {}
  for (const u of state.units) if (u.target && u.status !== 'idle') chasers[u.target] = (chasers[u.target] || 0) + 1

  const tiles = []
  for (let r = 0; r < height; r++) {
    for (let c = 0; c < width; c++) {
      const type = cells[r][c]
      const isBlocked = blocked.has(`${r},${c}`)
      if (type === 'road' && !isBlocked) continue
      const fill = isBlocked ? 'var(--c-blocked)' : type === 'building' ? 'var(--c-building)' : type === 'hospital' ? 'var(--c-hospital)' : 'var(--c-depot)'
      tiles.push(<rect key={`${r},${c}`} x={c * C + 1} y={r * C + 1} width={C - 2} height={C - 2} rx="3" fill={fill} />)
    }
  }
  const [hr, hc] = state.hospital

  return (
    <svg viewBox={`0 0 ${width * C} ${height * C}`} className="city-map" role="img"
         aria-label={`City map at minute ${state.time}: ${state.metrics.victims_rescued} of ${state.metrics.victims_total} casualties at hospital`}>
      <rect width={width * C} height={height * C} fill="var(--c-road)" />
      {Array.from({ length: width + 1 }, (_, i) => (
        <line key={`v${i}`} x1={i * C} x2={i * C} y1={0} y2={height * C} stroke="var(--c-grid-line)" strokeWidth="1" />
      ))}
      {Array.from({ length: height + 1 }, (_, i) => (
        <line key={`h${i}`} y1={i * C} y2={i * C} x1={0} x2={width * C} stroke="var(--c-grid-line)" strokeWidth="1" />
      ))}
      {tiles}
      <path d={`M${hc * C + C / 2} ${hr * C + 5}V${hr * C + C - 5}M${hc * C + 5} ${hr * C + C / 2}H${hc * C + C - 5}`}
            stroke="#fff" strokeWidth="3" strokeLinecap="round" />

      {state.units.map((u) => u.path.length > 0 && (
        <polyline key={`p-${u.id}`} fill="none" stroke="var(--unit)" strokeOpacity="0.45" strokeWidth="2" strokeDasharray="3 4"
                  strokeLinecap="round" points={[u.position, ...u.path].map(([r, c]) => `${c * C + C / 2},${r * C + C / 2}`).join(' ')} />
      ))}

      {state.victims.filter((v) => v.status !== 'rescued' && v.appeared !== false).map((v) => {
        const [r, c] = v.position
        const dup = (chasers[v.id] || 0) > 1
        return (
          <g key={v.id}>
            <title>{`${v.id}: ${v.severity}, waiting ${v.waiting_time} min`}</title>
            {dup && <circle cx={c * C + C / 2} cy={r * C + C / 2} r={C / 2 + 1} fill="none" stroke="var(--bad)" strokeWidth="2.5" className="dup-ring" />}
            <circle cx={c * C + C / 2} cy={r * C + C / 2} r={C / 2 - 3} fill={`var(--sev-${v.severity})`} stroke="var(--panel)" strokeWidth="1.5" />
            <text x={c * C + C / 2} y={r * C + C / 2 + 3.5} textAnchor="middle" fontSize="9" fontWeight="700" fill="#fff"
                  fontFamily="var(--font-mono)">{v.id.replace('V', '')}</text>
          </g>
        )
      })}

      {state.units.map((u, i) => {
        const [r, c] = u.position
        const stack = state.units.slice(0, i).filter((o) => o.position[0] === r && o.position[1] === c).length
        const outage = showRadio && !u.channel_ok
        return (
          <g key={u.id} transform={`translate(${c * C + stack * 3} ${r * C - stack * 3})`}>
            <title>{`Team ${unitLetter(u.id)}: ${u.status.replace(/_/g, ' ')}${u.target ? ` to ${u.target}` : ''}${outage ? ' (radio outage)' : ''}`}</title>
            {outage && <rect x="0" y="0" width={C} height={C} rx="5" fill="none" stroke="var(--bad)" strokeWidth="2.5" />}
            <rect x="2" y="2" width={C - 4} height={C - 4} rx="4" fill="var(--unit)" stroke="var(--panel)" strokeWidth="1" />
            <text x={C / 2} y={C / 2 + 4} textAnchor="middle" fontSize="11" fontWeight="700" fill="var(--unit-ink)"
                  fontFamily="var(--font-display)">{unitLetter(u.id)}</text>
          </g>
        )
      })}
    </svg>
  )
}
