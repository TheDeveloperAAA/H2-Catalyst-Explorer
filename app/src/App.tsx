import { useMemo, useState } from 'react'
import Scene from './Scene'
import { useStore } from './store'
import { useEffect } from 'react'
import {
  DATA, photoEntries, electroEntries, oerEntries,
  CLASS_LABEL, CLASS_COLOR, classColor, promisingOf, tierOf, driversFor,
} from './data'
import { interpret, CHIPS } from './assistant'

function Drivers({ mode, k }: { mode: string; k: string }) {
  const d = driversFor(mode, k)
  if (!d.length) return null
  const max = Math.max(...d.map((x: any) => Math.abs(x.impact)))
  return (
    <div className="drivers">
      <div className="meta"><div className="k">Why this score (SHAP)</div></div>
      {d.map((x: any, i: number) => (
        <div className="driver" key={i}>
          <span className="dn">{x.feature}</span>
          <span className="dbar"><span className="dfill" style={{ width: `${(Math.abs(x.impact) / max) * 100}%`, background: x.dir === 'up' ? '#34d399' : '#f87171' }} /></span>
          <span className="dd" style={{ color: x.dir === 'up' ? '#34d399' : '#f87171' }}>{x.dir === 'up' ? '↑' : '↓'}</span>
        </div>
      ))}
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

function PhotoDetail({ k, m }: { k: string; m: any }) {
  const c = m.combos['methanol|true']
  const prom = c.promising
  const ev = m.evidence
  const [cc, clabel] = CONF[m.confidence] || CONF['model-estimate']
  const levers = m.recommendation?.top_levers || []
  return (
    <>
      <h2>{k}</h2>
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
      {ev ? (
        <div className="ev">
          <div className="et">Published evidence · {ev.n_papers} studies</div>
          <div className="er">Typical H2 rate: <b>{Math.round(ev.typical_low)} to {Math.round(ev.typical_high)}</b> umol/h/g (median {Math.round(ev.median_rate)})</div>
          <small>The real literature spread. The model screens within it, never pretends to one number.</small>
        </div>
      ) : (
        <div className="ev"><div className="et">Published evidence</div><div className="er">No direct corpus data; prediction from composition + experimental band gap.</div></div>
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
  const col = m.score >= 70 ? '#34d399' : m.score >= 40 ? '#fbbf24' : '#f87171'
  return (
    <>
      <h2>{k}</h2>
      <div className="gaugewrap" style={{ marginTop: 14 }}>
        <div className="gaugelabel"><span>Predicted H-binding energy</span><span className="gaugeval" style={{ color: col }}>{m.energy_eV > 0 ? '+' : ''}{m.energy_eV} eV</span></div>
        <div className="gauge"><div className="gaugefill" style={{ width: `${m.score}%`, background: col }} /></div>
      </div>
      <div style={{ fontSize: 15, color: col, fontWeight: 500, marginTop: 14 }}>{m.verdict}</div>
      <div className="metarow">
        <div className="meta"><div className="k">HER score</div><div className="v">{Math.round(m.score)} / 100</div></div>
        <div className="meta"><div className="k">Reading</div><div className="v">Sabatier volcano</div></div>
      </div>
      <div style={{ fontSize: 13, color: 'var(--ink3)', lineHeight: 1.6 }}>A binding energy near 0 eV is ideal. Trained on Catalysis-Hub DFT, grouped R2 = {M.electro_R2}.</div>
      <Drivers mode="her" k={k} />
    </>
  )
}

function OerDetail({ k, m }: { k: string; m: any }) {
  const col = m.score >= 70 ? '#34d399' : m.score >= 40 ? '#fbbf24' : '#f87171'
  return (
    <>
      <h2>{k}</h2>
      <div style={{ fontSize: 15, color: col, fontWeight: 500, marginTop: 10 }}>{m.verdict}</div>
      <div className="gaugewrap">
        <div className="gaugelabel"><span>OER activity score</span><span className="gaugeval" style={{ color: col }}>{Math.round(m.score)}/100</span></div>
        <div className="gauge"><div className="gaugefill" style={{ width: `${m.score}%`, background: col }} /></div>
      </div>
      <div className="metarow">
        <div className="meta"><div className="k">Descriptor dG(O)-dG(OH)</div><div className="v">{m.descriptor} eV</div></div>
        <div className="meta"><div className="k">Est. overpotential</div><div className="v">{m.overpotential_V} V</div></div>
        <div className="meta"><div className="k">Family</div><div className="v">{m.class}</div></div>
        {m.lit_eta_mV != null && <div className="meta"><div className="k">Literature eta</div><div className="v">{m.lit_eta_mV} mV</div></div>}
      </div>
      <div style={{ fontSize: 13, color: 'var(--ink3)', lineHeight: 1.6 }}>Trained on Catalysis-Hub O/OH/OOH energies (grouped R2 = {M.oer_cv_R2 ?? M.oer_R2}). Optimal descriptor is ~1.6 eV.</div>
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

export default function App() {
  return (
    <div className="app">
      <Scene />
      <TopBar />
      <Rail />
      <Assistant />
      <Legend />
      <Hint />
      <Drawer />
      <TourButton />
      <Tour />
      <Onboard />
    </div>
  )
}
