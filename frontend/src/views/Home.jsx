import { useEffect, useState } from 'react'
import { api, PAPER_URL } from '../api.js'
import RaceReplay from '../components/RaceReplay.jsx'
import { computeHeadlines } from '../headlines.js'
import { setPendingPreset } from '../intent.js'
import { PRESETS } from '../presets.js'
import { PROTOCOLS } from '../protocols.js'

export default function Home({ go }) {
  const [h, setH] = useState(null)
  useEffect(() => { api.study().then((s) => setH(computeHeadlines(s))).catch(() => {}) }, [])

  const openPreset = (id) => { setPendingPreset(id); go('simulator') }

  return (
    <div className="page home">
      <section className="hero">
        <div className="hero-copy">
          <div className="eyebrow">Multi-agent disaster rescue</div>
          <h1>Three rescue teams that talk beat eight that don't.</h1>
          <p className="lede">
            When ambulances, robots or drones answer the same disaster, the easiest way to lose time is for two of them
            to chase the same casualty. RESQ-MAS is a simulator of cooperating rescue agents that measures how much
            coordination a team actually needs.
          </p>
          <div className="hero-cta">
            <button className="btn primary big" onClick={() => go('simulator')}>Try the simulator</button>
            <button className="btn big" onClick={() => go('results')}>See the results</button>
            <a className="btn big quiet" href={PAPER_URL} target="_blank" rel="noreferrer">Read the paper (PDF)</a>
          </div>
        </div>
        <RaceReplay />
      </section>

      <section className="band">
        <div className="section-head">
          <div className="eyebrow">The problem</div>
          <h2>How a dispatch goes wrong</h2>
        </div>
        <ol className="steps">
          <li>
            <b>Casualties are reported.</b>
            <span className="muted">A medical agent triages each one: critical, high, moderate or low.</span>
          </li>
          <li>
            <b>Every free team picks its best target.</b>
            <span className="muted">Each team weighs how urgent a casualty is against how far away it is.</span>
          </li>
          <li>
            <b>Without talking, teams collide.</b>
            <span className="muted">Two teams drive to the same casualty. One arrives to find nothing to do while others keep waiting.</span>
          </li>
        </ol>
      </section>

      <section className="band">
        <div className="section-head">
          <div className="eyebrow">What we found</div>
          <h2>{h?.runs ? `${h.runs.toLocaleString()} simulated disasters, four findings` : 'Four findings'}</h2>
        </div>
        <div className="findings">
          <Finding big={h ? `${h.e1Gain.toFixed(0)}%` : '…'} title="faster missions"
                   text="with a single round of negotiation between two teams, across 1,000 random disasters." />
          <Finding big="3 > 8" title="talk beats numbers"
                   text={h ? `Three negotiating teams finish before eight silent ones on every workload tested (at least ${h.three.minWins} of ${h.three.n} disasters).` : 'Three negotiating teams finish before eight silent ones.'} />
          <Finding big={h ? `${h.waitCut[0].toFixed(0)}–${h.waitCut[1].toFixed(0)}%` : '…'} title="shorter waits"
                   text="for casualties when they are reported over time, the situation where coordination matters most." />
          <Finding big={h ? `${h.cbbaRatio[0].toFixed(0)}–${h.cbbaRatio[1].toFixed(0)}×` : '…'} title="less radio traffic"
                   text="for simple negotiation than for the standard auction method (CBBA), with the same quality of assignment." />
        </div>
      </section>

      <section className="band">
        <div className="section-head">
          <div className="eyebrow">The agents</div>
          <h2>Three kinds of agent share one picture of the disaster</h2>
        </div>
        <div className="agents">
          <AgentCard icon={<TriageIcon />} title="Medical agent"
                     text="Registers each casualty as it is reported and sets its priority from severity. Priority rises the longer someone waits." />
          <AgentCard icon={<KitIcon />} title="Logistics agent"
                     text="Owns the medical kits. Never hands out two kits for the same casualty and never runs the stock below zero." />
          <AgentCard icon={<TeamIcon />} title="Rescue teams (up to 8)"
                     text="Pick a casualty, find the shortest open route, carry them to hospital, and pick again. How they choose is what we study." />
        </div>
      </section>

      <section className="band">
        <div className="section-head">
          <div className="eyebrow">Six ways to coordinate</div>
          <h2>From saying nothing to a central control room</h2>
          <p className="lede">Each strategy shares a little more before a team commits. The simulator lets you switch between them on the same disaster.</p>
        </div>
        <div className="ladder">
          {PROTOCOLS.map((p, i) => (
            <div key={p.id} className="rung" style={{ '--rung': p.color }}>
              <div className="rung-top">
                <span className="rung-step num">{i + 1}</span>
                <b>{p.name}</b>
                <span className="code" style={{ color: 'var(--text-dim)' }}>{p.short}</span>
              </div>
              <p className="muted small">{p.desc}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="band">
        <div className="section-head">
          <div className="eyebrow">Try it</div>
          <h2>Open a scenario in the simulator</h2>
        </div>
        <div className="scenarios">
          {PRESETS.map((p) => (
            <button key={p.id} className="scenario-card" onClick={() => openPreset(p.id)}>
              <b>{p.title}</b>
              <span className="muted small">{p.text}</span>
              <span className="scenario-go">Open in simulator →</span>
            </button>
          ))}
        </div>
      </section>
    </div>
  )
}

function Finding({ big, title, text }) {
  return (
    <div className="card finding">
      <div className="finding-big num">{big}</div>
      <div className="finding-title">{title}</div>
      <p className="muted small">{text}</p>
    </div>
  )
}

function AgentCard({ icon, title, text }) {
  return (
    <div className="card agent-card">
      <div className="agent-icon" aria-hidden="true">{icon}</div>
      <h3>{title}</h3>
      <p className="muted">{text}</p>
    </div>
  )
}

const iconProps = { width: 26, height: 26, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 2, strokeLinecap: 'round', strokeLinejoin: 'round' }
const TriageIcon = () => (<svg {...iconProps}><path d="M8 3h8l2 3v15H6V6z" /><path d="M12 9v6M9 12h6" /></svg>)
const KitIcon = () => (<svg {...iconProps}><rect x="3" y="7" width="18" height="13" rx="2" /><path d="M9 7V5h6v2M12 11v5M9.5 13.5h5" /></svg>)
const TeamIcon = () => (<svg {...iconProps}><path d="M3 16V9h11v7M14 11h4l3 3v2h-7" /><circle cx="7" cy="17" r="2" /><circle cx="17" cy="17" r="2" /></svg>)
