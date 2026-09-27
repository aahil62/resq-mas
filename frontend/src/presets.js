// Ready-made situations that reproduce the paper's key findings.
export const BASE_CONFIG = {
  policy: 'no_coordination', seed: 11, victim_count: 6, blockage_level: 0.0, rescue_agent_count: 2,
  width: 15, arrival_window: 0, comm_loss: 0, loss_pattern: 'independent', burst_length: 5,
}

export const PRESETS = [
  {
    id: 'classic', title: 'Two teams, one critical victim',
    text: 'Both teams want the same critical casualty at the start. Compare "No talking" with "Negotiate".',
    config: { ...BASE_CONFIG },
  },
  {
    id: 'crowded', title: 'Crowded incident',
    text: 'Eight teams and twenty casualties. Without talking, teams pile onto the same victims.',
    config: { ...BASE_CONFIG, seed: 1001, victim_count: 20, rescue_agent_count: 8, width: 20 },
  },
  {
    id: 'arriving', title: 'Casualties reported over time',
    text: 'Twenty casualties are called in over 200 minutes. Every free team hears each new call at once.',
    config: { ...BASE_CONFIG, seed: 1001, victim_count: 20, rescue_agent_count: 4, width: 20, arrival_window: 200, policy: 'claim' },
  },
  {
    id: 'radio', title: 'Patchy radio',
    text: '30% of messages are lost in outages of about 5 minutes. Teams in an outage are ringed in red.',
    config: { ...BASE_CONFIG, seed: 1001, victim_count: 20, rescue_agent_count: 4, width: 20, comm_loss: 0.3, loss_pattern: 'bursty', policy: 'cbba' },
  },
]
