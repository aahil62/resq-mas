const BASE = 'http://127.0.0.1:8000'

async function request(method, path, body) {
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(detail.detail || `${method} ${path} failed (${res.status})`)
  }
  return res.json()
}

export const api = {
  health: () => request('GET', '/api/health'),
  createScenario: (params) => request('POST', '/api/simulation/scenario', params),
  step: (n = 1) => request('POST', '/api/simulation/step', { n }),
  reset: () => request('POST', '/api/simulation/reset'),
  getState: () => request('GET', '/api/simulation/state'),
  getEvents: (since = 0, limit = 200) => request('GET', `/api/simulation/events?since=${since}&limit=${limit}`),
  runExperiment: (params) => request('POST', '/api/experiments/run', params),
  study: () => request('GET', '/api/experiments/study'),
  replay: (policy, seed = 11) => request('GET', `/api/simulation/replay?policy=${policy}&seed=${seed}`),
  precomputedMeta: () => request('GET', '/api/experiments/precomputed/meta'),
  precomputedSummary: () => request('GET', '/api/experiments/precomputed/summary'),
  precomputedTable: (name) => request('GET', `/api/experiments/precomputed/${name}`),
}

export const RESULTS_BASE = `${BASE}/results`
