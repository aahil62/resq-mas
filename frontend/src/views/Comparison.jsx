import { useEffect, useState } from 'react'
import { api, RESULTS_BASE } from '../api.js'

const CHARTS = [
  ['chart_1_completion_time.png', 'Completion Time (Minutes)'],
  ['chart_2_avg_waiting_time.png', 'Average Waiting Time (Minutes)'],
  ['chart_3_conflicts.png', 'Duplicate / Conflicting Target Assignments'],
]

const METRIC_LABELS = {
  completion_time: 'Completion Time (minutes)',
  avg_waiting_time: 'Average Waiting Time (minutes)',
  duplicate_conflicts: 'Duplicate / Conflicting Assignments',
  victims_rescued: 'Victims Rescued',
}

// Modeling assumption: 1 simulation timestep = 1 simulated minute (see
// README.md / docs/methodology.md). These are simulated minutes produced
// by the model, not real-world measured rescue times.
const MINUTE_METRICS = new Set(['completion_time', 'avg_waiting_time'])

function formatMetricValue(metric, value) {
  const formatted = Number(value).toFixed(2)
  return MINUTE_METRICS.has(metric) ? `${formatted} min` : formatted
}

export default function Comparison() {
  const [table, setTable] = useState(null)
  const [meta, setMeta] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    api.precomputedTable('comparison').then(setTable).catch((e) => setError(e.message))
    api.precomputedMeta().then(setMeta).catch(() => {})
  }, [])

  if (error) {
    return (
      <div className="panel" style={{ padding: 16, maxWidth: 700 }}>
        <p style={{ color: 'var(--bad)' }}>{error}</p>
        <p style={{ color: 'var(--text-dim)' }}>
          Run <code>python -m experiments.runner</code> from the project root to generate results.
        </p>
      </div>
    )
  }

  const scenarioCount = meta ? Object.keys(meta.scenarios).length : null

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16, maxWidth: 1100 }}>
      <div>
        <h2 style={{ margin: '0 0 4px 0' }}>Effect of Multi-Agent Coordination</h2>
        {meta && (
          <div style={{ color: 'var(--text-dim)' }}>
            {meta.total_runs} simulation runs across {scenarioCount} controlled scenarios
            ({meta.elapsed_seconds.toFixed(2)}s to execute). Every number below comes from those executed runs --
            nothing is hardcoded. Time metrics are simulated minutes (1 simulation timestep = 1 simulated
            minute), not real-world measured rescue times.
          </div>
        )}
      </div>

      {table && (
        <div className="panel">
          <div className="panel-title">No Coordination vs Multi-Agent — Mean Across All Scenarios</div>
          <table>
            <thead><tr><th>Metric</th><th>No Coordination</th><th>MAS</th><th>MAS vs No Coordination</th></tr></thead>
            <tbody>
              {table.map((row) => {
                const improvement = Number(row.improvement_pct)
                const good = improvement > 0.5
                const bad = improvement < -0.5
                return (
                  <tr key={row.metric}>
                    <td>{METRIC_LABELS[row.metric] || row.metric}</td>
                    <td className="mono">{formatMetricValue(row.metric, row.no_coordination_mean)}</td>
                    <td className="mono">{formatMetricValue(row.metric, row.mas_mean)}</td>
                    <td className="mono" style={{ color: good ? 'var(--good)' : bad ? 'var(--bad)' : 'var(--text-dim)' }}>
                      {improvement >= 0 ? '+' : ''}{improvement.toFixed(1)}%
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))', gap: 12 }}>
        {CHARTS.map(([file, title]) => (
          <div key={file} className="panel" style={{ padding: 8 }}>
            <div style={{ fontSize: 11, color: 'var(--text-dim)', marginBottom: 6 }}>{title}</div>
            <img src={`${RESULTS_BASE}/${file}`} alt={title} style={{ width: '100%', borderRadius: 4 }} />
          </div>
        ))}
      </div>

      {meta && (
        <div className="panel" style={{ padding: 12 }}>
          <div style={{ fontSize: 11, color: 'var(--text-dim)', marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
            Scenarios run (each under both modes)
          </div>
          <ul style={{ margin: 0, paddingLeft: 18 }}>
            {Object.entries(meta.scenarios).map(([name, seeds]) => (
              <li key={name} style={{ marginBottom: 2 }}>
                <b>{name.replace(/_/g, ' ')}</b> — seeds {seeds.join(', ')}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
