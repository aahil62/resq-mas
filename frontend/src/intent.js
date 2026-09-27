// Hands a chosen scenario from one page to another (e.g. a landing-page card
// that opens the simulator with a preset already loaded). The value survives
// React's double-run of effects in development and is cleared right after.
let pending = null
export const setPendingPreset = (id) => { pending = id }
export const takePendingPreset = () => {
  const p = pending
  setTimeout(() => { if (pending === p) pending = null }, 0)
  return p
}
