// The six task-allocation protocols studied in the paper, in ladder order
// (least to most information exchanged before an agent commits). Colours are
// a fixed categorical order validated for colour-vision deficiency against
// the dark panel surface -- a protocol keeps its colour everywhere.
export const PROTOCOLS = [
  {
    id: 'no_coordination', short: 'IND', label: 'Independent', color: '#3987e5', marker: 'circle',
    desc: 'No communication. Each agent commits to its own best victim, so agents can pile onto the same one.',
  },
  {
    id: 'claim', short: 'CLM', label: 'Claim-only', color: '#d95926', marker: 'square',
    desc: 'Agents announce what they committed to; others skip claimed victims. Choices made in the same minute still collide.',
  },
  {
    id: 'mas', short: 'PR-1', label: 'Propose-resolve (1 round)', color: '#199e70', marker: 'triangle',
    desc: 'Agents propose first; the highest-utility proposal wins each victim. Losers wait one minute and try again.',
  },
  {
    id: 'mas_iterative', short: 'PR-k', label: 'Iterative propose-resolve', color: '#c98500', marker: 'diamond',
    desc: 'Like PR-1, but losers re-propose immediately in the same minute until everyone has a target.',
  },
  {
    id: 'hungarian', short: 'HUN', label: 'Centralized Hungarian', color: '#d55181', marker: 'triangleDown',
    desc: 'A coordinator collects every utility and computes the optimal matching. Reference only: it needs a working central link.',
  },
  {
    id: 'cbba', short: 'CBBA', label: 'CBBA (bundle consensus)', color: '#008300', marker: 'plus',
    desc: 'The standard consensus-based bundle algorithm: agents bid on bundles of future victims and repeat consensus rounds.',
  },
]

export const PROTOCOL = Object.fromEntries(PROTOCOLS.map((p) => [p.id, p]))

// Rescue units on the grid (identity, not protocol).
export const UNIT_COLORS = ['#e0af68', '#bb9af7', '#7dcfff', '#9aa5ce', '#73daca', '#e6e6e6', '#2ac3de', '#cfc9c2']
export const unitColor = (id) => UNIT_COLORS[(id.charCodeAt(id.length - 1) - 97) % UNIT_COLORS.length] || UNIT_COLORS[0]
export const unitLetter = (id) => id.slice(-1).toUpperCase()
