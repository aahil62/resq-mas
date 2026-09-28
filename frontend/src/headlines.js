// Headline figures, computed from the study summary served by the API so the
// landing page and the Results page always agree.
export function computeHeadlines(study) {
  const e1 = Object.fromEntries(study.e1.map((r) => [r.policy, r]))
  const e1Gain = 100 * (1 - e1.mas.completion_time.mean / e1.no_coordination.completion_time.mean)

  const three = study.coordination_beats_scale.filter((b) => b.coordinated_agents === 3)
  const minWins = Math.min(...three.map((b) => b.wins))
  const n = three[0]?.n ?? 150

  const waitCut = [100, 200, 400].map((w) => {
    const ind = study.e5.find((r) => r.arrival_window === w && r.policy === 'no_coordination')
    const pr = study.e5.find((r) => r.arrival_window === w && r.policy === 'mas')
    return 100 * (1 - pr.avg_waiting_time.mean / ind.avg_waiting_time.mean)
  })

  const ratios = [10, 20, 30].flatMap((m) => [2, 3, 4, 6, 8].map((k) => {
    const get = (p) => study.e2.find((r) => r.victims === m && r.rescue_agents === k && r.policy === p)
    return get('cbba').message_payload.mean / get('mas').message_payload.mean
  }))

  const speedup = (p) => [10, 20, 30].map((m) => {
    const one = study.e2.find((r) => r.victims === m && r.rescue_agents === 1 && r.policy === 'no_coordination')
    const eight = study.e2.find((r) => r.victims === m && r.rescue_agents === 8 && r.policy === p)
    return one.completion_time.mean / eight.completion_time.mean
  })

  return {
    e1Gain,
    three: { minWins, n, rows: three },
    waitCut: [Math.min(...waitCut), Math.max(...waitCut)],
    cbbaRatio: [Math.min(...ratios), Math.max(...ratios)],
    speedupInd: [Math.min(...speedup('no_coordination')), Math.max(...speedup('no_coordination'))],
    speedupPr: [Math.min(...speedup('mas')), Math.max(...speedup('mas'))],
    runs: study.meta?.runs,
  }
}
