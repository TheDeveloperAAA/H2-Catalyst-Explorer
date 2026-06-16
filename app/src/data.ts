import raw from './data.json'

export const DATA: any = raw

export const photoEntries = Object.entries(DATA.photo) as [string, any][]
export const electroEntries = Object.entries(DATA.electro) as [string, any][]
export const oerEntries = Object.entries(DATA.oer || {}) as [string, any][]

export const CLASS_LABEL: Record<string, string> = {
  oxide: 'Oxides', sulfide: 'Sulfides', selenide: 'Selenides', telluride: 'Tellurides',
  perovskite: 'Perovskites', halide_perovskite: 'Halide perovskites', pyrochlore: 'Pyrochlores',
  layered: 'Layered', carbon_nitride: 'Carbon nitrides', nitride: 'Nitrides',
  carbon: 'Carbon / GO', framework: 'MOF / COF', mxene: 'MXene', other: 'Other',
}

export const CLASS_COLOR: Record<string, string> = {
  oxide: '#3b82f6', sulfide: '#f59e0b', selenide: '#a855f7', telluride: '#ec4899',
  perovskite: '#10b981', halide_perovskite: '#14b8a6', pyrochlore: '#ef4444', layered: '#8b5cf6',
  carbon_nitride: '#22c55e', nitride: '#0ea5e9', carbon: '#94a3b8', framework: '#eab308',
  mxene: '#f43f5e', other: '#64748b',
}

export function promisingOf(m: any): number {
  return (m?.combos?.['methanol|true']?.promising) ?? 0
}
export function tierOf(m: any): string {
  return (m?.combos?.['methanol|true']?.tier) ?? 'low'
}
export function rateOf(m: any): number {
  return m?.evidence?.median_rate ?? 0
}
export function classColor(cls: string): string {
  return CLASS_COLOR[cls] || CLASS_COLOR.other
}

export function driversFor(mode: string, key: string): any[] {
  const block = mode === 'her' ? DATA.shap?.her : DATA.shap?.photo
  return (block && block[key]) || []
}

export const LEADERBOARDS: any = DATA.leaderboards || {}

export function plainSummary(k: string, m: any): string {
  const c = m.combos['methanol|true']
  const fam = (CLASS_LABEL[m.class] || m.class).toLowerCase()
  const ev = m.evidence
  const cost = m.cost === 'precious' ? 'expensive' : m.cost === 'moderate' ? 'moderately priced' : 'cheap and earth-abundant'
  const tox = m.toxic ? ', though it contains a toxic element' : ''
  const vis = m.visible ? 'can use visible sunlight' : 'mostly needs UV light'
  const water = m.splits_water ? 'Its energy levels line up to split water on their own.' : 'On its own its energy levels may not fully line up to split water, so it often needs help.'
  return `${k} is a ${fam} that ${vis}. The tool rates it a ${c.tier} performer, about ${Math.round(c.promising * 100)} percent worth synthesizing${ev ? `, and ${ev.n_papers} real studies report a typical rate near ${Math.round(ev.median_rate)} units` : ''}. It is ${cost}${tox}. ${water}`
}
