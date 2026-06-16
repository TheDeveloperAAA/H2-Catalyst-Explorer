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
