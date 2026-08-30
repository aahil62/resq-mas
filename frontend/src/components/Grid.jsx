const CELL = 32

const CELL_COLOR = {
  road: 'var(--c-road)',
  building: 'var(--c-building)',
  hospital: 'var(--c-hospital)',
  depot: 'var(--c-depot)',
}

const SEV_COLOR = {
  critical: 'var(--sev-critical)',
  high: 'var(--sev-high)',
  moderate: 'var(--sev-moderate)',
  low: 'var(--sev-low)',
}

const UNIT_COLOR = {
  rescue_a: '#e0af68',
  rescue_b: '#bb9af7',
}

export default function Grid({ state }) {
  if (!state) return null
  const { width, height, cells } = state.grid
  const blocked = new Set(state.blocked_cells.map(([r, c]) => `${r},${c}`))

  const victimsByCell = new Map()
  for (const v of state.victims) {
    if (v.status === 'rescued') continue
    victimsByCell.set(`${v.position[0]},${v.position[1]}`, v)
  }

  const unitsByCell = new Map()
  for (const u of state.units) {
    const key = `${u.position[0]},${u.position[1]}`
    if (!unitsByCell.has(key)) unitsByCell.set(key, [])
    unitsByCell.get(key).push(u)
  }

  const pathCells = new Set()
  for (const u of state.units) {
    for (const p of u.path) pathCells.add(`${p[0]},${p[1]}`)
  }

  const rows = []
  for (let r = 0; r < height; r++) {
    for (let c = 0; c < width; c++) {
      const key = `${r},${c}`
      const type = cells[r][c]
      const isBlocked = blocked.has(key)
      const isPath = pathCells.has(key)
      const victim = victimsByCell.get(key)
      const units = unitsByCell.get(key)

      rows.push(
        <div
          key={key}
          title={`(${r},${c}) ${type}${isBlocked ? ' [blocked]' : ''}`}
          style={{
            gridColumn: c + 1,
            gridRow: r + 1,
            width: CELL,
            height: CELL,
            background: isBlocked ? 'var(--c-blocked)' : CELL_COLOR[type] || 'var(--c-road)',
            border: '1px solid rgba(255,255,255,0.04)',
            outline: isPath ? '1px dashed rgba(255,255,255,0.25)' : 'none',
            outlineOffset: -2,
            position: 'relative',
          }}
        >
          {victim && (
            <div
              title={`${victim.id} severity=${victim.severity} priority=${victim.priority.toFixed(1)} waiting=${victim.waiting_time} min status=${victim.status}`}
              style={{
                position: 'absolute', inset: 4, borderRadius: '50%',
                background: SEV_COLOR[victim.severity],
                boxShadow: victim.severity === 'critical' ? '0 0 5px var(--sev-critical)' : 'none',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontFamily: 'var(--font-mono)', fontSize: 9, fontWeight: 700, color: 'var(--bg)',
              }}
            >
              {victim.id.replace('V', '')}
            </div>
          )}
          {units && units.map((u, i) => (
            <div
              key={u.id}
              title={`${u.id} ${u.status}${u.target ? ' -> ' + u.target : ''}`}
              style={{
                position: 'absolute',
                inset: 2,
                transform: units.length > 1 ? `translate(${i * 5 - 2.5}px, ${i * -5 + 2.5}px)` : undefined,
                background: UNIT_COLOR[u.id] || '#e0af68',
                borderRadius: 4,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontFamily: 'var(--font-mono)', fontSize: 11, fontWeight: 700, color: 'var(--bg)',
                zIndex: 2,
              }}
            >
              {u.id === 'rescue_a' ? 'A' : u.id === 'rescue_b' ? 'B' : u.id.slice(-1).toUpperCase()}
            </div>
          ))}
        </div>,
      )
    }
  }

  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: `repeat(${width}, ${CELL}px)`,
        gridTemplateRows: `repeat(${height}, ${CELL}px)`,
        width: 'fit-content',
      }}
    >
      {rows}
    </div>
  )
}
