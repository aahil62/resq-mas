import { PROTOCOL } from '../protocols.js'

// A strategy's colour, plain name and short code, used everywhere a strategy is named.
export default function ProtocolChip({ id, withName = true }) {
  const p = PROTOCOL[id]
  if (!p) return null
  return (
    <span className="chip" title={p.desc}>
      <span className="dot" style={{ background: p.color }} />
      {withName && p.name}
      <span className="code" style={{ color: 'var(--text-dim)' }}>{p.short}</span>
    </span>
  )
}
