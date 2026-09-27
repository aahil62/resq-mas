import { useEffect, useState } from 'react'
import Home from './views/Home.jsx'
import LiveSimulation from './views/LiveSimulation.jsx'
import Comparison from './views/Comparison.jsx'
import Architecture from './views/Architecture.jsx'

const TABS = [
  { id: 'home', label: 'Home', view: Home },
  { id: 'simulator', label: 'Simulator', view: LiveSimulation },
  { id: 'results', label: 'Results', view: Comparison },
  { id: 'how', label: 'How it works', view: Architecture },
]

const fromHash = () => {
  const h = window.location.hash.replace('#', '')
  return TABS.some((t) => t.id === h) ? h : 'home'
}

export default function App() {
  const [tab, setTab] = useState(fromHash)
  const [theme, setTheme] = useState(() => document.documentElement.dataset.theme || '')

  useEffect(() => {
    const onHash = () => { setTab(fromHash()); window.scrollTo(0, 0) }
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])

  const go = (id) => { window.location.hash = id }

  const isDark = theme === 'dark' || (!theme && window.matchMedia?.('(prefers-color-scheme: dark)').matches)
  const toggleTheme = () => {
    const next = isDark ? 'light' : 'dark'
    document.documentElement.dataset.theme = next
    try { localStorage.setItem('resq-theme', next) } catch { /* storage unavailable */ }
    setTheme(next)
  }

  const Active = TABS.find((t) => t.id === tab).view

  return (
    <div style={{ minHeight: '100%', display: 'flex', flexDirection: 'column' }}>
      <header className="site-header">
        <div className="site-header-inner">
          <a href="#home" className="brand" aria-label="RESQ-MAS home">
            <BrandMark />
            <span>
              <span className="brand-name">RESQ-MAS</span>
              <span className="brand-sub">Rescue team coordination</span>
            </span>
          </a>
          <nav aria-label="Sections" className="site-nav">
            {TABS.map((t) => (
              <a key={t.id} href={`#${t.id}`} aria-current={tab === t.id ? 'page' : undefined}>{t.label}</a>
            ))}
          </nav>
          <button className="btn quiet theme-toggle" onClick={toggleTheme} aria-label={`Switch to ${isDark ? 'light' : 'dark'} theme`}
                  title={`Switch to ${isDark ? 'light' : 'dark'} theme`}>
            {isDark ? <SunIcon /> : <MoonIcon />}
          </button>
        </div>
      </header>
      <main style={{ flex: 1 }}>
        <Active go={go} />
      </main>
      <footer className="site-footer">
        <div>
          <b>RESQ-MAS</b> · Aahil Sayed, Prachi Pawar, Purva Chaudhari, Sakshi Maher · Department of Computer Engineering, PCCOE, Pune
        </div>
        <div className="muted small">All numbers come from executed simulations. Times are simulated minutes, not field measurements.</div>
      </footer>
    </div>
  )
}

function BrandMark() {
  // A rescue beacon: a cross inside a grid cell, the unit of the simulator's map.
  return (
    <svg width="34" height="34" viewBox="0 0 34 34" aria-hidden="true">
      <rect x="1" y="1" width="32" height="32" rx="8" fill="var(--brand)" />
      <path d="M1 12H33M1 22H33M12 1V33M22 1V33" stroke="var(--brand-ink)" strokeOpacity="0.14" strokeWidth="1" />
      <rect x="14" y="8" width="6" height="18" rx="1.5" fill="var(--brand-ink)" />
      <rect x="8" y="14" width="18" height="6" rx="1.5" fill="var(--brand-ink)" />
      <circle cx="27" cy="7" r="3" fill="var(--signal)" />
    </svg>
  )
}

const SunIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
    <circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
  </svg>
)
const MoonIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
    <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z" />
  </svg>
)
