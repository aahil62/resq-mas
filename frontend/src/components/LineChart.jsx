import { useMemo, useRef, useState } from 'react'

// Small dependency-free SVG line chart: 2px lines, >=8px markers, optional
// 95% CI whiskers, recessive grid, a legend, and a hover crosshair with a
// tooltip listing every series at the nearest x.
//   series: [{ key, label, color, marker, dashed, points: [{ x, y, ci }] }]
export default function LineChart({
  series, xLabel, yLabel, xTicks, height = 260, yMin, yMax, formatY = (v) => v.toFixed(1),
  formatX = (v) => v, logX = false,
}) {
  const [hoverX, setHoverX] = useState(null)
  const ref = useRef(null)
  const W = 560
  const H = height
  const M = { l: 52, r: 14, t: 10, b: 38 }
  const iw = W - M.l - M.r
  const ih = H - M.t - M.b

  const xs = useMemo(() => [...new Set(series.flatMap((s) => s.points.map((p) => p.x)))].sort((a, b) => a - b), [series])
  const allY = series.flatMap((s) => s.points.flatMap((p) => [p.y - (p.ci || 0), p.y + (p.ci || 0)]))
  const lo = yMin ?? Math.min(0, ...allY)
  const hiRaw = yMax ?? Math.max(...allY)
  const hi = hiRaw + (hiRaw - lo) * 0.06
  const fx = (x) => (logX ? Math.log(x) : x)
  const xMin = fx(Math.min(...xs))
  const xMax = fx(Math.max(...xs))
  const sx = (x) => M.l + (xMax === xMin ? iw / 2 : ((fx(x) - xMin) / (xMax - xMin)) * iw)
  const sy = (y) => M.t + ih - ((y - lo) / (hi - lo)) * ih
  const yTicks = niceTicks(lo, hi, 5)

  const onMove = (e) => {
    const rect = ref.current.getBoundingClientRect()
    const px = ((e.clientX - rect.left) / rect.width) * W
    let best = xs[0]
    for (const x of xs) if (Math.abs(sx(x) - px) < Math.abs(sx(best) - px)) best = x
    setHoverX(best)
  }

  const hoverRows = hoverX == null ? [] : series
    .map((s) => ({ s, p: s.points.find((p) => p.x === hoverX) }))
    .filter((r) => r.p)
    .sort((a, b) => a.p.y - b.p.y)

  return (
    <div style={{ position: 'relative' }}>
      <svg ref={ref} viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', display: 'block' }}
           onMouseMove={onMove} onMouseLeave={() => setHoverX(null)} role="img" aria-label={`${yLabel} by ${xLabel}`}>
        {yTicks.map((t) => (
          <g key={t}>
            <line x1={M.l} x2={W - M.r} y1={sy(t)} y2={sy(t)} stroke="var(--border)" strokeWidth="1" />
            <text x={M.l - 6} y={sy(t)} textAnchor="end" dominantBaseline="middle" fontSize="10" fill="var(--text-dim)">
              {formatY(t)}
            </text>
          </g>
        ))}
        {(xTicks || xs).map((t) => (
          <text key={t} x={sx(t)} y={H - M.b + 14} textAnchor="middle" fontSize="10" fill="var(--text-dim)">{formatX(t)}</text>
        ))}
        <text x={M.l + iw / 2} y={H - 4} textAnchor="middle" fontSize="10.5" fill="var(--text-dim)">{xLabel}</text>
        <text x={12} y={M.t + ih / 2} textAnchor="middle" fontSize="10.5" fill="var(--text-dim)"
              transform={`rotate(-90 12 ${M.t + ih / 2})`}>{yLabel}</text>
        {hoverX != null && (
          <line x1={sx(hoverX)} x2={sx(hoverX)} y1={M.t} y2={M.t + ih} stroke="var(--text-dim)" strokeWidth="1" strokeDasharray="3 3" />
        )}
        {series.map((s) => {
          const pts = s.points.filter((p) => p.y != null)
          const d = pts.map((p, i) => `${i ? 'L' : 'M'}${sx(p.x)},${sy(p.y)}`).join(' ')
          return (
            <g key={s.key}>
              {pts.map((p) => p.ci ? (
                <line key={`ci${p.x}`} x1={sx(p.x)} x2={sx(p.x)} y1={sy(p.y - p.ci)} y2={sy(p.y + p.ci)}
                      stroke={s.color} strokeWidth="1" opacity="0.7" />
              ) : null)}
              <path d={d} fill="none" stroke={s.color} strokeWidth="2" strokeDasharray={s.dashed ? '5 4' : undefined}
                    strokeLinejoin="round" />
              {pts.map((p) => <Marker key={p.x} type={s.marker} x={sx(p.x)} y={sy(p.y)} color={s.color}
                                      big={p.x === hoverX} />)}
            </g>
          )
        })}
      </svg>
      {hoverRows.length > 0 && (
        <div className="chart-tip" style={{
          left: `${(sx(hoverX) / W) * 100}%`,
          transform: sx(hoverX) > W * 0.6 ? 'translateX(calc(-100% - 12px))' : 'translateX(12px)',
        }}>
          <div style={{ color: 'var(--text)', marginBottom: 4 }}>{xLabel}: <b>{formatX(hoverX)}</b></div>
          {hoverRows.map(({ s, p }) => (
            <div key={s.key} style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
              <span style={{ width: 8, height: 8, borderRadius: 2, background: s.color, flexShrink: 0 }} />
              <span style={{ color: 'var(--text-dim)', flex: 1 }}>{s.label}</span>
              <span className="mono" style={{ color: 'var(--text)' }}>{formatY(p.y)}{p.ci ? ` ±${formatY(p.ci)}` : ''}</span>
            </div>
          ))}
        </div>
      )}
      <Legend series={series} />
    </div>
  )
}

export function Legend({ series }) {
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px 14px', marginTop: 6, fontSize: 11, color: 'var(--text-dim)' }}>
      {series.map((s) => (
        <span key={s.key} style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
          <svg width="22" height="10" aria-hidden="true">
            <line x1="0" x2="22" y1="5" y2="5" stroke={s.color} strokeWidth="2" strokeDasharray={s.dashed ? '5 4' : undefined} />
            <Marker type={s.marker} x={11} y={5} color={s.color} small />
          </svg>
          {s.label}
        </span>
      ))}
    </div>
  )
}

function Marker({ type, x, y, color, big, small }) {
  const r = small ? 3 : big ? 5.5 : 4
  const common = { fill: color, stroke: 'var(--panel)', strokeWidth: small ? 0 : 1.5 }
  switch (type) {
    case 'square': return <rect x={x - r} y={y - r} width={2 * r} height={2 * r} {...common} />
    case 'triangle': return <polygon points={`${x},${y - r * 1.2} ${x - r * 1.1},${y + r * 0.8} ${x + r * 1.1},${y + r * 0.8}`} {...common} />
    case 'triangleDown': return <polygon points={`${x},${y + r * 1.2} ${x - r * 1.1},${y - r * 0.8} ${x + r * 1.1},${y - r * 0.8}`} {...common} />
    case 'diamond': return <polygon points={`${x},${y - r * 1.3} ${x + r * 1.1},${y} ${x},${y + r * 1.3} ${x - r * 1.1},${y}`} {...common} />
    case 'plus': return <path d={`M${x - r},${y}H${x + r}M${x},${y - r}V${y + r}`} stroke={color} strokeWidth={small ? 2 : 3} />
    case 'none': return null
    default: return <circle cx={x} cy={y} r={r} {...common} />
  }
}

function niceTicks(lo, hi, n) {
  const span = hi - lo || 1
  const step0 = span / n
  const mag = 10 ** Math.floor(Math.log10(step0))
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= step0) || step0
  const out = []
  for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step) out.push(+v.toFixed(6))
  return out
}
