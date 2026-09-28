// The six task-allocation protocols, in ladder order (least to most
// information exchanged before a team commits). `name` is the plain label
// used across the site; `formal` is the technical/textbook name and `short`
// its code. Colours come from theme tokens (see index.css), validated for
// colour-vision deficiency; a protocol keeps its colour everywhere.
export const PROTOCOLS = [
  {
    id: 'no_coordination', short: 'IND', name: 'No talking', formal: 'Independent', color: 'var(--p-ind)', marker: 'circle',
    desc: 'Each team heads for the victim that looks best to it, without telling anyone. Teams often chase the same victim.',
  },
  {
    id: 'claim', short: 'CLM', name: 'Announce claims', formal: 'Claim broadcasting', color: 'var(--p-clm)', marker: 'square',
    desc: 'Teams announce the victim they took, and others skip it. Two teams choosing in the same minute can still collide.',
  },
  {
    id: 'mas', short: 'PR-1', name: 'Negotiate', formal: 'One-round propose–resolve', color: 'var(--p-pr1)', marker: 'triangle',
    desc: 'Teams propose a victim first. If two want the same one, the better-placed team gets it and the other picks again next minute.',
  },
  {
    id: 'mas_iterative', short: 'PR-k', name: 'Negotiate to agreement', formal: 'Iterative propose–resolve', color: 'var(--p-prk)', marker: 'diamond',
    desc: 'Like Negotiate, but a team that loses picks again straight away, so every free team leaves with a target.',
  },
  {
    id: 'hungarian', short: 'HUN', name: 'Central dispatcher', formal: 'Centralized Hungarian', color: 'var(--p-hun)', marker: 'triangleDown',
    desc: 'A control room collects every option and computes the best assignment. Needs a working link to the centre.',
  },
  {
    id: 'cbba', short: 'CBBA', name: 'Auction (CBBA)', formal: 'Consensus-based bundle algorithm', color: 'var(--p-cbba)', marker: 'plus',
    desc: 'The standard auction method from robotics: teams bid on several future victims and repeat rounds until the bids agree.',
  },
]

export const PROTOCOL = Object.fromEntries(PROTOCOLS.map((p) => [p.id, p]))

export const SEVERITIES = [
  { id: 'critical', label: 'Critical', tag: 'red tag' },
  { id: 'high', label: 'High', tag: 'orange tag' },
  { id: 'moderate', label: 'Moderate', tag: 'yellow tag' },
  { id: 'low', label: 'Low', tag: 'green tag' },
]

export const unitLetter = (id) => id.slice(-1).toUpperCase()
export const teamName = (id) => `Team ${unitLetter(id)}`
