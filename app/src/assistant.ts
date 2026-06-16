import { photoEntries, electroEntries, oerEntries, CLASS_LABEL, promisingOf } from './data'
import type { Mode } from './store'

export type Resp = {
  text: string
  mode?: Mode
  select?: string | null
  highlight?: string[]
  results?: string[]
  chips?: string[]
}

const FAMILY_WORDS: Record<string, string> = {
  oxides: 'oxide', oxide: 'oxide', sulfides: 'sulfide', sulfide: 'sulfide', sulphides: 'sulfide', sulphide: 'sulfide',
  selenides: 'selenide', selenide: 'selenide', tellurides: 'telluride', telluride: 'telluride',
  perovskites: 'perovskite', perovskite: 'perovskite', pyrochlores: 'pyrochlore', pyrochlore: 'pyrochlore',
  nitrides: 'nitride', nitride: 'nitride', 'carbon nitride': 'carbon_nitride', mxene: 'mxene',
}
const EXPENSIVE = ['Pt', 'Au', 'Ag', 'Pd', 'Ir', 'Ru', 'Rh', 'Re', 'Os', 'In', 'Ga', 'Te', 'Cd']
function elements(f: string) { return f.match(/[A-Z][a-z]?/g) || [] }
function isCheap(f: string) { return !elements(f).some((e) => EXPENSIVE.includes(e)) }

function findMaterial(t: string): string | null {
  let best = ''
  const all = [...photoEntries, ...electroEntries, ...oerEntries]
  for (const [k] of all) {
    const kl = k.toLowerCase()
    if (kl.length >= 2 && t.includes(' ' + kl) && k.length > best.length) best = k
  }
  return best || null
}

export const CHIPS = [
  'Best photocatalysts',
  'Cheap visible-light oxides',
  'Top HER catalysts',
  'Best for oxygen evolution',
  'Well-studied sulfides',
  'What should I try for CdS',
]

export function interpret(query: string): Resp {
  const t = ' ' + query.toLowerCase().replace(/[?.,!]/g, ' ').replace(/\s+/g, ' ').trim() + ' '
  if (!query.trim()) return { text: 'Ask me anything grounded in the data: "best photocatalysts", "cheap visible-light oxides", "top HER catalysts", or "what should I try for CdS".', chips: CHIPS }

  const wantsOER = /\boer\b|oxygen evol/.test(t)
  const wantsHER = /\bher\b|hydrogen evolution|h-binding|binding energy|electrocataly/.test(t) && !/photocataly|photo /.test(t)
  const wantsRecommend = /what should i|try next|improve|recommend|optimi/.test(t)
  const wantsCompare = /\bcompare\b|\bvs\b|versus| or /.test(t) && /\band\b|\bvs\b|versus/.test(t)
  const mat = findMaterial(t)

  if (mat && wantsRecommend) {
    const pm = photoEntries.find(([k]) => k === mat)
    if (pm && pm[1].recommendation?.top_levers?.length) {
      const top = pm[1].recommendation.top_levers[0]
      return { text: `For ${mat}, the single change that most improves its hydrogen output is to ${top.change} (${top.delta > 0 ? '+' : ''}${Math.round(top.delta * 100)} pts). Opening ${mat} now.`, mode: 'universe', select: mat, chips: CHIPS }
    }
  }

  if (wantsOER && /best|top|good|strong|highest|leading/.test(t)) {
    const top = [...oerEntries].sort((a, b) => b[1].score - a[1].score).slice(0, 12)
    return { text: `The trained OER model ranks these earth-abundant catalysts highest for oxygen evolution: ${top.slice(0, 5).map(([k]) => k).join(', ')}. Highlighting the top ${top.length} on the OER volcano.`, mode: 'oer', highlight: top.map(([k]) => k), results: top.slice(0, 6).map(([k]) => k), chips: CHIPS }
  }
  if (wantsHER && /best|top|good|strong|highest|leading/.test(t)) {
    const top = [...electroEntries].sort((a, b) => b[1].score - a[1].score).slice(0, 8)
    return { text: `For hydrogen evolution (HER), the model rates these highest: ${top.slice(0, 4).map(([k]) => k).join(', ')}. MoS2 sits at the volcano peak. Highlighting them now.`, mode: 'her', highlight: top.map(([k]) => k), results: top.slice(0, 6).map(([k]) => k), chips: CHIPS }
  }

  if (mat && !/best|top|all|list|every|show me .*(oxide|sulfide|perovskite|selenide)/.test(t)) {
    const pm = photoEntries.find(([k]) => k === mat)
    if (pm) {
      const m = pm[1], c = m.combos['methanol|true'], ev = m.evidence
      return { text: `${mat} is a ${CLASS_LABEL[m.class] || m.class} with a ${m.band_gap_eV} eV band gap. The model rates it ${c.tier} tier, ${Math.round(c.promising * 100)}% worth synthesizing${ev ? `, backed by ${ev.n_papers} published studies (median ${Math.round(ev.median_rate)} umol/h/g)` : ''}. Opening it.`, mode: 'universe', select: mat, chips: CHIPS }
    }
    const em = electroEntries.find(([k]) => k === mat) || oerEntries.find(([k]) => k === mat)
    if (em) {
      const isOer = !!oerEntries.find(([k]) => k === mat)
      return { text: `${mat} is an electrocatalyst. ${isOer ? `Its OER activity score is ${Math.round(em[1].score)}/100 (${em[1].verdict}).` : `Its predicted H-binding energy is ${em[1].energy_eV} eV, score ${Math.round(em[1].score)}/100 (${em[1].verdict}).`} Opening it.`, mode: isOer ? 'oer' : 'her', select: mat, chips: CHIPS }
    }
  }

  let pool = [...photoEntries]
  const desc: string[] = []
  for (const w in FAMILY_WORDS) {
    if (t.includes(' ' + w + ' ') || t.includes(' ' + w + 's ')) { const f = FAMILY_WORDS[w]; pool = pool.filter(([, m]) => m.class === f); desc.push((CLASS_LABEL[f] || f).toLowerCase()); break }
  }
  if (/visible/.test(t)) { pool = pool.filter(([, m]) => m.band_gap_eV < 3.0); desc.push('visible-light') }
  else if (/\buv\b|ultraviolet|wide.?gap/.test(t)) { pool = pool.filter(([, m]) => m.band_gap_eV >= 3.0); desc.push('wide-gap') }
  if (/narrow.?gap|low.?gap|small.?gap/.test(t)) { pool = pool.filter(([, m]) => m.band_gap_eV < 2.0); desc.push('narrow-gap') }
  const ng = t.match(/(below|under|less than|above|over|greater than)\s*([\d.]+)\s*ev/)
  if (ng) { const v = parseFloat(ng[2]); const below = /below|under|less/.test(ng[1]); pool = pool.filter(([, m]) => (below ? m.band_gap_eV < v : m.band_gap_eV > v)); desc.push(`gap ${below ? 'below' : 'above'} ${v} eV`) }
  if (/well.?stud|proven|strong evidence|reliable|evidence.?backed|established/.test(t)) { pool = pool.filter(([, m]) => m.confidence === 'evidence-backed'); desc.push('well-studied') }
  if (/cheap|earth.?abundant|abundant|low.?cost|inexpensive|non.?precious/.test(t)) { pool = pool.filter(([k]) => isCheap(k)); desc.push('earth-abundant') }

  pool.sort((a, b) => promisingOf(b[1]) - promisingOf(a[1]))
  const label = desc.length ? desc.join(', ') + ' photocatalysts' : 'photocatalysts'
  if (pool.length === 0) return { text: `I could not find any ${label} in the set. Try loosening the filter, for example "visible-light oxides" or "well-studied sulfides".`, chips: CHIPS }
  const top = pool.slice(0, 12)
  const note = desc.includes('earth-abundant') ? ' (earth-abundant is a heuristic that excludes precious and rare elements)' : ''
  return {
    text: `Top ${label} by predicted promise: ${top.slice(0, 5).map(([k]) => k).join(', ')}. Highlighting ${pool.length} ${pool.length === 1 ? 'match' : 'matches'} on the map, brightest first${note}.`,
    mode: 'universe', highlight: pool.map(([k]) => k), results: top.slice(0, 6).map(([k]) => k), chips: CHIPS,
  }
}
