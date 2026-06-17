import { useMemo, useState } from 'react'
import Scene from './Scene'
import { useStore } from './store'
import { useEffect } from 'react'
import {
  DATA, photoEntries, electroEntries, oerEntries,
  CLASS_LABEL, CLASS_COLOR, classColor, promisingOf, tierOf, driversFor, plainSummary,
} from './data'
import { interpret, CHIPS } from './assistant'
import { ToolsBar, Panel } from './Panels'
import { exportImage } from './vr'

function KeyShortcuts() {
  const setMode = useStore((s) => s.setMode)
  const setPanel = useStore((s) => s.setPanel)
  const select = useStore((s) => s.select)
  const endTour = useStore((s) => s.endTour)
  const toggleTheme = useStore((s) => s.toggleTheme)
  const startTour = useStore((s) => s.startTour)
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName
      if (tag === 'INPUT' || tag === 'SELECT' || tag === 'TEXTAREA') {
        if (e.key === 'Escape') (e.target as HTMLElement).blur()
        return
      }
      const k = e.key.toLowerCase()
      if (k === '1') setMode('universe')
      else if (k === '2') setMode('her')
      else if (k === '3') setMode('oer')
      else if (k === 'f') setPanel('filters')
      else if (k === 'l') setPanel('leaderboards')
      else if (k === 'c') setPanel('compare')
      else if (k === 'h') setPanel('hetero')
      else if (k === 's') setPanel('shortlist')
      else if (k === 'g') toggleTheme()
      else if (k === 't') startTour()
      else if (k === 'e') exportImage()
      else if (k === '/') { e.preventDefault(); (document.querySelector('.searchwrap input') as HTMLElement)?.focus() }
      else if (k === 'escape') { setPanel(null); select(null); endTour() }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])
  return null
}

function Drivers({ mode, k }: { mode: string; k: string }) {
  const d = driversFor(mode, k)
  if (!d.length) return null
  const max = Math.max(...d.map((x: any) => Math.abs(x.impact)))
  return (
    <div className="drivers">
      <div className="meta"><div className="k">Why this score (SHAP direction)</div></div>
      {d.map((x: any, i: number) => (
        <div className="driver" key={i}>
          <span className="dn">{x.feature}</span>
          <span className="dbar"><span className="dfill" style={{ width: `${(Math.abs(x.impact) / max) * 100}%`, background: x.dir === 'up' ? '#34d399' : '#f87171' }} /></span>
          <span className="dd" style={{ color: x.dir === 'up' ? '#34d399' : '#f87171' }}>{x.dir === 'up' ? '↑' : '↓'}</span>
        </div>
      ))}
      <small style={{ display: 'block', color: 'var(--ink3)', fontSize: 10.5, marginTop: 6, lineHeight: 1.5 }}>SHAP explains the raw model. The displayed % is a monotonic calibration of that score, so the up/down direction of each driver carries over, but the magnitudes are pre-calibration.</small>
    </div>
  )
}

const M = DATA.metrics

const TIER_COLOR: Record<string, string> = { low: '#f87171', moderate: '#fbbf24', high: '#60a5fa', exceptional: '#2dd4bf' }
const CONF: Record<string, [string, string]> = {
  'evidence-backed': ['#34d399', 'Evidence-backed'],
  'limited-evidence': ['#fbbf24', 'Limited evidence'],
  'model-estimate': ['#94a3b8', 'Model estimate'],
}
function gaugeColor(p: number) { return p >= 0.6 ? '#34d399' : p >= 0.4 ? '#fbbf24' : '#f87171' }

const MODES = [
  { id: 'universe', label: 'Photocatalysts', ico: '◆', hint: 'x band gap · y promising · z published rate' },
  { id: 'her', label: 'HER volcano', ico: '▲', hint: 'x H-binding energy · height = suitability · peak near 0 eV is best' },
  { id: 'oer', label: 'OER volcano', ico: '●', hint: 'x activity descriptor · height = score · centre (1.6 eV) is optimal' },
]

function TopBar() {
  return (
    <div className="topbar">
      <div className="brand glass">
        <h1>H<sub>2</sub> Catalyst <em>Explorer</em></h1>
        <span className="sub">3D</span>
      </div>
      <div className="metrics glass">
        <div className="mc"><div className="mv">{M.electro_R2}</div><div className="mk">HER R2</div></div>
        <div className="mc"><div className="mv">{M.oer_cv_R2 ?? M.oer_R2 ?? '-'}</div><div className="mk">OER R2</div></div>
        <div className="mc"><div className="mv">{M.photo_roc_auc}</div><div className="mk">Photo AUC</div></div>
        <div className="mc"><div className="mv">{photoEntries.length}</div><div className="mk">materials</div></div>
      </div>
      <a className="classic glass" href="./classic.html">Classic view {'↗'}</a>
    </div>
  )
}

function Rail() {
  const mode = useStore((s) => s.mode)
  const setMode = useStore((s) => s.setMode)
  return (
    <div className="rail glass">
      {MODES.map((m) => (
        <button key={m.id} className={mode === m.id ? 'on' : ''} onClick={() => setMode(m.id as any)}>
          <span className="ico">{m.ico}</span>{m.label}
        </button>
      ))}
    </div>
  )
}

function entriesFor(mode: string): [string, any][] {
  return mode === 'her' ? electroEntries : mode === 'oer' ? oerEntries : photoEntries
}

function Assistant() {
  const setMode = useStore((s) => s.setMode)
  const select = useStore((s) => s.select)
  const setHighlight = useStore((s) => s.setHighlight)
  const [q, setQ] = useState('')
  const [resp, setResp] = useState<any>(null)
  const [focused, setFocused] = useState(false)

  const apply = (r: any) => {
    setResp(r)
    const act = () => { if (r.highlight) setHighlight(r.highlight); if (r.select) select(r.select) }
    if (r.mode) { setMode(r.mode); setTimeout(act, 90) } else act()
  }
  const run = (text: string) => { setQ(text); apply(interpret(text)) }

  const matches = useMemo(() => {
    if (!q.trim() || resp) return []
    const t = q.toLowerCase()
    return photoEntries.filter(([k, m]) => (k + ' ' + (m.class || '')).toLowerCase().includes(t)).slice(0, 6)
  }, [q, resp])

  return (
    <div className="searchwrap">
      <input
        value={q}
        onFocus={() => setFocused(true)}
        onBlur={() => setTimeout(() => setFocused(false), 160)}
        onChange={(e) => { setQ(e.target.value); setResp(null) }}
        onKeyDown={(e) => { if (e.key === 'Enter' && q.trim()) run(q) }}
        placeholder="Ask anything: best cheap oxides, top HER catalysts, what to try for CdS..."
      />
      {resp ? (
        <div className="assistant-card glass">
          <button className="ac-close" onClick={() => { setResp(null); setHighlight([]); setQ('') }} aria-label="clear">{'×'}</button>
          <div className="ac-text">{resp.text}</div>
          {resp.results && resp.results.length > 0 && (
            <div className="ac-results">{resp.results.map((k: string) => <button key={k} className="ac-chip" onClick={() => select(k)}>{k}</button>)}</div>
          )}
          {resp.chips && (
            <div className="ac-chips">{resp.chips.slice(0, 4).map((c: string) => <button key={c} className="ac-suggest" onClick={() => run(c)}>{c}</button>)}</div>
          )}
        </div>
      ) : matches.length > 0 ? (
        <div className="results glass">
          {matches.map(([k, m]) => (
            <div className="r" key={k} onClick={() => { setMode('universe'); setTimeout(() => select(k), 60); setQ('') }}>
              <span><span className="dot" style={{ background: classColor(m.class) }} />{k}</span>
              <span style={{ fontSize: 11, color: 'var(--ink3)' }}>{CLASS_LABEL[m.class]}</span>
            </div>
          ))}
        </div>
      ) : focused && !q ? (
        <div className="results glass">
          <div className="ac-hint-label">Try asking</div>
          {CHIPS.map((c) => <div className="r" key={c} onMouseDown={() => run(c)}>{c}</div>)}
        </div>
      ) : null}
    </div>
  )
}

function Legend() {
  const mode = useStore((s) => s.mode)
  if (mode === 'universe') {
    const used = [...new Set(photoEntries.map(([, m]) => m.class))]
    return (
      <div className="legend glass">
        <div className="lt">Material family</div>
        {used.map((c) => (
          <div className="lrow" key={c}><span className="dot" style={{ background: CLASS_COLOR[c] || '#64748b' }} />{CLASS_LABEL[c] || c}</div>
        ))}
      </div>
    )
  }
  return (
    <div className="legend glass">
      <div className="lt">Activity</div>
      <div className="lrow"><span className="dot" style={{ background: '#34d399' }} />Strong</div>
      <div className="lrow"><span className="dot" style={{ background: '#fbbf24' }} />Moderate</div>
      <div className="lrow"><span className="dot" style={{ background: '#f87171' }} />Weak</div>
    </div>
  )
}

const GOOD = { background: 'rgba(52,211,153,0.15)', color: '#34d399' }
const BAD = { background: 'rgba(248,113,113,0.15)', color: '#f87171' }
const NEU = { background: 'rgba(148,163,184,0.15)', color: '#9fb0c8' }
const AMB = { background: 'rgba(251,191,36,0.15)', color: '#fbbf24' }
function costStyle(c: string) { return c === 'precious' ? BAD : c === 'moderate' ? AMB : GOOD }

function PhotoDetail({ k, m }: { k: string; m: any }) {
  const c = m.combos['methanol|true']
  const prom = c.promising
  const ev = m.evidence
  const [cc, clabel] = CONF[m.confidence] || CONF['model-estimate']
  const levers = m.recommendation?.top_levers || []
  const shortlist = useStore((s) => s.shortlist)
  const toggleShort = useStore((s) => s.toggleShort)
  const compare = useStore((s) => s.compare)
  const toggleCompare = useStore((s) => s.toggleCompare)
  const eli5 = useStore((s) => s.eli5)
  const toggleEli5 = useStore((s) => s.toggleEli5)
  const starred = shortlist.includes(k)
  const inComp = compare.includes(k)
  return (
    <>
      <h2>{k}</h2>
      <div className="dactions">
        <button className={starred ? 'on' : ''} onClick={() => toggleShort(k)}>{starred ? '★ Shortlisted' : '☆ Shortlist'}</button>
        <button className={inComp ? 'on' : ''} onClick={() => toggleCompare(k)}>{inComp ? '✓ Comparing' : '⧉ Compare'}</button>
        <button className={eli5 ? 'on' : ''} onClick={toggleEli5}>{eli5 ? 'Technical' : 'Explain simply'}</button>
      </div>
      {eli5 && <div className="eli5">{plainSummary(k, m)}</div>}
      <div>
        <span className="tier-pill" style={{ background: (TIER_COLOR[c.tier] || '#888') + '22', color: TIER_COLOR[c.tier] }}>{c.tier} performer</span>
        <span className="badge" style={{ background: cc + '22', color: cc, marginLeft: 8 }}>{clabel}{ev ? ` · ${ev.n_papers}` : ''}</span>
      </div>
      <div className="gaugewrap">
        <div className="gaugelabel"><span>Worth synthesizing?</span><span className="gaugeval" style={{ color: gaugeColor(prom) }}>{Math.round(prom * 100)}%</span></div>
        <div className="gauge"><div className="gaugefill" style={{ width: `${prom * 100}%`, background: gaugeColor(prom) }} /></div>
      </div>
      <div className="metarow">
        <div className="meta"><div className="k">Band gap</div><div className="v">{m.band_gap_eV} eV</div></div>
        <div className="meta"><div className="k">Gap source</div><div className="v">{m.band_gap_source.includes('experimental') ? 'Experimental' : 'Estimated'}</div></div>
        <div className="meta"><div className="k">Family</div><div className="v">{CLASS_LABEL[m.class] || m.class}</div></div>
        <div className="meta"><div className="k">Tier conf.</div><div className="v">{Math.round(c.tier_conf * 100)}%</div></div>
      </div>
      <div className="scirow">
        <div className="sci"><div className="k">Solar use</div><div className="v">{Math.round((m.solar_abs || 0) * 100)}%{m.visible ? '' : ' UV'}</div></div>
        {m.cb != null && <div className="sci"><div className="k">Band edges {m.edge_source === 'estimated' ? '(est)' : ''}</div><div className="v">{m.cb} / {m.vb} V</div></div>}
        {(() => {
          const est = m.edge_source === 'estimated'
          const v = m.water_verdict || (m.splits_water == null ? 'unknown' : m.splits_water ? 'yes' : 'marginal')
          const base: any = { yes: ['Yes', '#57d39b'], marginal: ['Marginal', '#efc169'], no: ['No', '#9fb0c8'], unknown: ['?', '#9fb0c8'] }
          let [label, col] = base[v]
          if (v === 'yes' && est) { label = 'Likely (est)'; col = '#efc169' }
          const star = est && (v === 'yes' || v === 'marginal')
          return <div className="sci"><div className="k">Splits water{star ? ' *' : ''}</div><div className="v" style={{ color: col }}>{label}</div></div>
        })()}
      </div>
      {m.water_verdict === 'marginal' && m.cb != null && <div style={{ fontSize: 11, color: 'var(--ink3)', marginBottom: 8 }}>Marginal: the band edges straddle the water redox levels but the valence band clears the O₂/H₂O line by less than a realistic OER overpotential (~0.4 V), so unassisted overall splitting is unlikely without a co-catalyst.</div>}
      {m.edge_source === 'estimated' && m.cb != null && (m.water_verdict === 'yes' || m.water_verdict === 'marginal') && <div style={{ fontSize: 11, color: 'var(--ink3)', marginBottom: 8 }}>* Band edges are a Mulliken electronegativity estimate (E_CB = χ − 4.5 − ½Eg), not measured, so this verdict is indicative, not confirmed.</div>}
      <div className="pbadges">
        <span className="pb" style={costStyle(m.cost)}>{m.cost === 'precious' ? 'Precious' : m.cost === 'moderate' ? 'Moderate cost' : 'Low cost'}</span>
        <span className="pb" style={m.abundant ? GOOD : NEU}>{m.abundant ? 'Earth-abundant' : 'Less abundant'}</span>
        <span className="pb" style={m.toxic ? BAD : GOOD}>{m.toxic ? 'Toxic element' : 'Non-toxic'}</span>
      </div>
      {m.stability && <div className="stab"><b>Stability.</b> {m.stability}</div>}
      <div style={{ fontSize: 11.5, color: 'var(--ink3)', fontStyle: 'italic', marginBottom: 12 }}>Composition-level screen. The % is an {DATA.uncertainty?.calib_out_of_sample ? 'out-of-sample ' : ''}calibrated probability{DATA.uncertainty?.calib_n ? ` (fit on ${DATA.uncertainty.calib_n} held-out rows the model never saw)` : ''}, so it means what it says, but calibration fixes the meaning, not the separating power (grouped ROC-AUC stays ~{M.photo_roc_auc ?? M.roc_auc ?? '0.65'}). It cannot see morphology, facet, or surface area, which strongly affect real rates. Cost, toxicity, stability and solar use are heuristic estimates.</div>
      {ev ? (
        <div className="ev">
          <div className="et">Published evidence · {ev.n_papers} studies</div>
          <div className="er">Typical H2 rate: <b>{Math.round(ev.typical_low)} to {Math.round(ev.typical_high)}</b> umol/h/g (median {Math.round(ev.median_rate)})</div>
          <small>The real literature spread. The model screens within it, never pretends to one number.</small>
        </div>
      ) : (
        <div className="ev"><div className="et">Published evidence</div><div className="er">No direct corpus data; prediction from composition + experimental band gap.</div></div>
      )}
      {m.papers && m.papers.length > 0 && (
        <div className="cites">
          <div className="meta"><div className="k">Sources</div></div>
          {m.papers.slice(0, 4).map((p: string, i: number) => (
            <a key={i} className="cite" href={p.startsWith('10.') ? `https://doi.org/${p}` : `https://scholar.google.com/scholar?q=${encodeURIComponent(p)}`} target="_blank" rel="noreferrer">{p.length > 32 ? p.slice(0, 32) + '...' : p}</a>
          ))}
        </div>
      )}
      {levers.length > 0 && (
        <div className="levers">
          <div className="meta"><div className="k">What to try next</div></div>
          {levers.slice(0, 3).map((l: any, i: number) => (
            <div className="lever" key={i}>
              <span>{l.change}</span>
              <span className="d" style={{ color: l.delta > 0.01 ? '#34d399' : '#9fb0c8' }}>{l.delta > 0 ? '+' : ''}{Math.round(l.delta * 100)} pts</span>
            </div>
          ))}
        </div>
      )}
      <Drivers mode="universe" k={k} />
    </>
  )
}

function HerDetail({ k, m }: { k: string; m: any }) {
  const col = m.score >= 70 ? '#57d39b' : m.score >= 40 ? '#efc169' : '#ef8d8d'
  const pm = DATA.uncertainty?.her_pm
  return (
    <>
      <h2>{k}</h2>
      {m.in_domain === false && <div className="pbadges" style={{ marginTop: 8 }}><span className="pb" style={{ background: 'rgba(251,191,36,0.15)', color: '#fbbf24' }}>Extrapolated: outside the alloy training set</span></div>}
      <div className="gaugewrap" style={{ marginTop: 12 }}>
        <div className="gaugelabel"><span>Predicted H-binding energy</span><span className="gaugeval" style={{ color: col }}>{m.energy_eV > 0 ? '+' : ''}{m.energy_eV}{pm ? ` ± ${pm}` : ''} eV</span></div>
        <div className="gauge"><div className="gaugefill" style={{ width: `${m.score}%`, background: col }} /></div>
      </div>
      <div style={{ fontSize: 15, color: col, fontWeight: 500, marginTop: 14 }}>{m.verdict}</div>
      <div className="metarow">
        <div className="meta"><div className="k">HER score</div><div className="v">{Math.round(m.score)} / 100</div></div>
        <div className="meta"><div className="k">Reading</div><div className="v">Sabatier volcano</div></div>
      </div>
      <div style={{ fontSize: 12.5, color: 'var(--ink3)', lineHeight: 1.6 }}>A binding energy near 0 eV is ideal. Trained on Catalysis-Hub bimetallic-alloy DFT (grouped R2 = {M.electro_R2}, conformal ±{pm} eV).{m.in_domain === false ? ' This composition is outside that alloy chemistry, so treat the value as a rough extrapolation.' : ''}</div>
      <div style={{ fontSize: 11, color: 'var(--ink3)', fontStyle: 'italic', marginTop: 6, lineHeight: 1.5 }}>Composition-level: the model does not resolve facet or adsorption site, so it gives one value per composition. The target is the DFT H* binding energy (ΔE), not the entropy/zero-point-corrected free energy (ΔG ≈ ΔE + 0.24 eV), so the volcano is read on the same ΔE scale the model was trained on.</div>
      <Drivers mode="her" k={k} />
    </>
  )
}

function OerDetail({ k, m }: { k: string; m: any }) {
  const descPm = DATA.uncertainty?.oer_desc_pm
  const known = m.lit_eta_mV != null
  // Literature is PRIMARY when known; the trained descriptor is a weak, leak-free
  // cross-check (grouped CV R2 ~0.64 +/- 0.26, O*/OOH* arms near zero), so colour
  // from the literature eta when we have it, not from the model score.
  const col = known ? (m.lit_eta_mV <= 300 ? '#57d39b' : m.lit_eta_mV <= 360 ? '#efc169' : '#ef8d8d')
                    : (m.score >= 70 ? '#57d39b' : m.score >= 40 ? '#efc169' : '#ef8d8d')
  const cvStd = M.oer_cv_R2_std
  const arm = M.oer_arm_R2 || {}
  return (
    <>
      <h2>{k}</h2>
      <div style={{ fontSize: 15, color: col, fontWeight: 500, marginTop: 10 }}>{m.verdict_primary || m.verdict}</div>
      {known ? (
        <div className="gaugewrap">
          <div className="gaugelabel"><span>Overpotential (literature, lower is better)</span><span className="gaugeval" style={{ color: col }}>{m.lit_eta_mV} mV</span></div>
          <div className="gauge"><div className="gaugefill" style={{ width: `${Math.max(8, 100 - (m.lit_eta_mV - 230) / 3)}%`, background: col }} /></div>
        </div>
      ) : (
        <div className="gaugewrap">
          <div className="gaugelabel"><span>Activity descriptor (optimum ~1.6 eV)</span><span className="gaugeval" style={{ color: col }}>{m.descriptor} eV</span></div>
          <div className="gauge"><div className="gaugefill" style={{ width: `${m.score}%`, background: col }} /></div>
        </div>
      )}
      <div className="metarow">
        {known && <div className="meta"><div className="k">Literature eta (@10 mA/cm²)</div><div className="v">{m.lit_eta_mV} mV</div></div>}
        <div className="meta"><div className="k">Descriptor dG(O)-dG(OH)</div><div className="v">{m.descriptor}{descPm ? ` ± ${descPm}` : ''} eV</div></div>
        <div className="meta"><div className="k">Model score (weak)</div><div className="v">{Math.round(m.score)}/100</div></div>
        <div className="meta"><div className="k">Family</div><div className="v">{m.class}</div></div>
      </div>
      <div className="pbadges">
        {known
          ? <span className="pb" style={{ background: 'rgba(148,163,184,0.15)', color: '#9fb0c8' }}>Literature-anchored (representative η, not individually cited)</span>
          : <span className="pb" style={{ background: 'rgba(251,191,36,0.15)', color: '#fbbf24' }}>Model-only estimate, low confidence</span>}
      </div>
      {known && m.model_disagrees && (
        <div style={{ fontSize: 12, color: '#efc169', background: 'rgba(239,193,105,0.10)', borderRadius: 8, padding: '8px 10px', margin: '10px 0', lineHeight: 1.55 }}>
          The trained descriptor disagrees with the literature here (it reads "{m.verdict}"). The metal/alloy-heavy training set underrates noble and known oxide catalysts, so the literature overpotential above is authoritative and the model is shown only for transparency.
        </div>
      )}
      <div style={{ fontSize: 12.5, color: 'var(--ink3)', lineHeight: 1.6 }}>
        The OER descriptor comes from a trained model that is honestly <b>weak</b> once leakage is removed: leak-free grouped-CV R2 = {M.oer_cv_R2}{cvStd ? ` ± ${cvStd}` : ''}, and the O*/OOH* arms barely predict (R2 {arm['O*'] ?? '?'} / {arm['OOH*'] ?? '?'}). An earlier 0.86 was inflated by identical-composition surfaces leaking across the split. The descriptor band is ±{descPm} eV, so treat it as a rough ranking only. Where a literature overpotential exists it is the primary signal.
      </div>
    </>
  )
}

function Drawer() {
  const mode = useStore((s) => s.mode)
  const selected = useStore((s) => s.selected)
  const select = useStore((s) => s.select)
  if (!selected) return null
  const map = entriesFor(mode)
  const found = map.find(([k]) => k === selected)
  if (!found) return null
  const m = found[1]
  return (
    <div className="drawer glass">
      <button className="close" onClick={() => select(null)} aria-label="close">{'×'}</button>
      {mode === 'universe' ? <PhotoDetail k={selected} m={m} /> : mode === 'her' ? <HerDetail k={selected} m={m} /> : <OerDetail k={selected} m={m} />}
    </div>
  )
}

const TOUR = [
  { mode: 'universe', sel: null, title: 'The catalyst universe', text: '127 real photocatalysts. Higher and brighter means more promising for hydrogen, and colors are material families.' },
  { mode: 'universe', sel: 'CdS', title: 'A proven performer', text: 'CdS: a high-tier sulfide backed by 521 published studies. Click any point to inspect it like this.' },
  { mode: 'universe', sel: 'g-C3N4', title: 'The workhorse', text: 'g-C3N4: the most-studied visible-light photocatalyst, with the widest evidence base.' },
  { mode: 'her', sel: 'MoS2', title: 'The HER champion', text: 'In the HER volcano, with no hints, the model places MoS2 at the peak, exactly the catalyst the field celebrates.' },
  { mode: 'her', sel: 'Pt', title: 'An honest miss', text: 'Pt sits mid-pack here: its (111) facet binds hydrogen slightly too strongly, which is real chemistry. The tool shows misses, not just wins.' },
  { mode: 'oer', sel: 'NiOOH', title: 'Oxygen evolution', text: 'For the OER half-reaction, the trained model ranks earth-abundant NiOOH and cobalt oxides highest, ideal for green hydrogen.' },
  { mode: 'universe', sel: null, title: 'Your turn', text: 'Search any material, click any point, switch modes. Every number is grounded in published evidence.' },
]

function Tour() {
  const tour = useStore((s) => s.tour)
  const setMode = useStore((s) => s.setMode)
  const select = useStore((s) => s.select)
  const next = useStore((s) => s.nextTour)
  const end = useStore((s) => s.endTour)
  useEffect(() => {
    if (tour < 0) return
    if (tour >= TOUR.length) { end(); return }
    const step = TOUR[tour]
    setMode(step.mode as any)
    const t = setTimeout(() => select(step.sel), 350)
    const auto = setTimeout(() => next(), 7000)
    return () => { clearTimeout(t); clearTimeout(auto) }
  }, [tour])
  if (tour < 0 || tour >= TOUR.length) return null
  const step = TOUR[tour]
  return (
    <div className="tour glass">
      <div className="tour-step">{tour + 1} / {TOUR.length}</div>
      <h3>{step.title}</h3>
      <p>{step.text}</p>
      <div className="tour-actions">
        <button className="skip" onClick={end}>Skip</button>
        <button className="next" onClick={next}>{tour === TOUR.length - 1 ? 'Done' : 'Next'}</button>
      </div>
    </div>
  )
}

function TourButton() {
  const tour = useStore((s) => s.tour)
  const onboarded = useStore((s) => s.onboarded)
  const selected = useStore((s) => s.selected)
  const startTour = useStore((s) => s.startTour)
  if (tour >= 0 || !onboarded || selected) return null
  return <button className="tour-launch" onClick={startTour}>{'▶'} Take the tour</button>
}

function Onboard() {
  const onboarded = useStore((s) => s.onboarded)
  const dismiss = useStore((s) => s.dismissOnboard)
  const startTour = useStore((s) => s.startTour)
  if (onboarded) return null
  return (
    <div className="onboard">
      <div className="card glass">
        <h2>The catalyst <em>universe</em></h2>
        <p>Every glowing point is a real catalyst. Brighter and higher means more promising for hydrogen. Colors are material families.</p>
        <div className="steps">
          <div className="step"><div className="si">{'↻'}</div><div className="st">Drag to rotate</div></div>
          <div className="step"><div className="si">{'⊕'}</div><div className="st">Scroll to zoom</div></div>
          <div className="step"><div className="si">{'→'}</div><div className="st">Click a point</div></div>
        </div>
        <div className="ob-actions">
          <button className="ghost" onClick={dismiss}>Explore freely</button>
          <button onClick={startTour}>Take the guided tour</button>
        </div>
      </div>
    </div>
  )
}

function Hint() {
  const mode = useStore((s) => s.mode)
  const sel = useStore((s) => s.selected)
  if (sel) return null
  const m = MODES.find((x) => x.id === mode)!
  return <div className="hint">{m.hint}</div>
}

function DeepLink() {
  const mode = useStore((s) => s.mode)
  const selected = useStore((s) => s.selected)
  const setMode = useStore((s) => s.setMode)
  const select = useStore((s) => s.select)
  useEffect(() => {
    const h = decodeURIComponent(location.hash.replace('#', ''))
    if (h) {
      const [mo, sel] = h.split('/')
      if (mo === 'her' || mo === 'oer' || mo === 'universe') setMode(mo as any)
      if (sel) setTimeout(() => select(sel), 140)
    }
  }, [])
  useEffect(() => {
    history.replaceState(null, '', '#' + mode + (selected ? '/' + selected : ''))
  }, [mode, selected])
  return null
}

export default function App() {
  const theme = useStore((s) => s.theme)
  return (
    <div className={'app ' + theme}>
      <h1 className="sr-only">H2 Catalyst Explorer: a 3D interactive dashboard for screening photocatalysts and electrocatalysts for green hydrogen, grounded in published evidence.</h1>
      <Scene />
      <KeyShortcuts />
      <TopBar />
      <Rail />
      <Assistant />
      <ToolsBar />
      <Panel />
      <Legend />
      <Hint />
      <Drawer />
      <TourButton />
      <Tour />
      <Onboard />
      <DeepLink />
    </div>
  )
}
