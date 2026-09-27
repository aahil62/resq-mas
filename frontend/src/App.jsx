import { useState } from 'react'
import LiveSimulation from './views/LiveSimulation.jsx'
import Comparison from './views/Comparison.jsx'
import Architecture from './views/Architecture.jsx'

const TABS = [
  { id: 'live', label: 'Live Simulation', view: LiveSimulation },
  { id: 'comparison', label: 'Results', view: Comparison },
  { id: 'architecture', label: 'Architecture', view: Architecture },
]

export default function App() {
  const [tab, setTab] = useState('live')
  const Active = TABS.find((t) => t.id === tab).view

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>
      <header style={{
        display: 'flex', alignItems: 'center', gap: 28, padding: '11px 18px',
        borderBottom: '1px solid var(--border)', background: 'var(--panel-2)', flexShrink: 0,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span
            aria-hidden="true"
            style={{
              width: 8, height: 8, borderRadius: '50%', background: 'var(--accent)', flexShrink: 0,
              animation: 'pulse-live 2.2s var(--ease-out) infinite',
            }}
          />
          <span style={{ fontWeight: 800, fontSize: 16, letterSpacing: '0.06em', color: 'var(--text)', whiteSpace: 'nowrap' }}>
            RESQ-MAS
          </span>
          <span style={{ color: 'var(--text-dim)', fontSize: 12, letterSpacing: '0.03em', borderLeft: '1px solid var(--border-strong)', paddingLeft: 12 }}>
            MULTI-AGENT TASK COORDINATION &middot; DISASTER RESCUE
          </span>
        </div>
        <nav style={{ display: 'flex', gap: 4, marginLeft: 'auto' }} aria-label="Views">
          {TABS.map((t) => (
            <button
              key={t.id}
              className="btn"
              aria-current={tab === t.id ? 'page' : undefined}
              style={tab === t.id ? { borderColor: 'var(--accent)', color: 'var(--accent)', background: 'var(--panel)' } : {}}
              onClick={() => setTab(t.id)}
            >
              {t.label}
            </button>
          ))}
        </nav>
      </header>
      <main style={{ flex: 1, overflow: 'auto', padding: 16 }}>
        <Active />
      </main>
    </div>
  )
}
