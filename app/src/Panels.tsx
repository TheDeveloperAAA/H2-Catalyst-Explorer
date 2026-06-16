import { useEffect, useMemo, useState } from 'react'
import { useStore } from './store'
import { photoEntries, oerEntries, electroEntries, LEADERBOARDS, DATA, CLASS_LABEL, classColor, promisingOf } from './data'
import { exportImage, enterVR, vrSupported } from './vr'

const TOOLS: { id: any; ico: string; label: string }[] = [
  { id: 'filters', ico: '☷', label: 'Filters' },
  { id: 'leaderboards', ico: '☰', label: 'Leaders' },
  { id: 'compare', ico: '⧉', label: 'Compare' },
  { id: 'hetero', ico: '⧈', label: 'Junction' },
  { id: 'shortlist', ico: '★', label: 'Shortlist' },
]

export function ToolsBar() {
  const panel = useStore((s) => s.panel)
  const setPanel = useStore((s) => s.setPanel)
  const shortlist = useStore((s) => s.shortlist)
  const theme = useStore((s) => s.theme)
  const toggleTheme = useStore((s) => s.toggleTheme)
  const [vr, setVr] = useState(false)
  useEffect(() => { vrSupported().then(setVr) }, [])
  return (
    <div className="tools glass" role="toolbar" aria-label="Tools">
      {TOOLS.map((t) => (
        <button key={t.id} className={panel === t.id ? 'on' : ''} onClick={() => setPanel(panel === t.id ? null : t.id)} title={t.label} aria-label={t.label} aria-pressed={panel === t.id}>
          <span className="ti" aria-hidden="true">{t.ico}</span>
          {t.id === 'shortlist' && shortlist.length > 0 && <span className="badge-count">{shortlist.length}</span>}
        </button>
      ))}
      <button onClick={exportImage} title="Save image (E)" aria-label="Save image"><span className="ti" aria-hidden="true">⤓</span></button>
      {vr && <button onClick={enterVR} title="Enter VR" aria-label="Enter VR"><span className="ti" aria-hidden="true">▣</span></button>}
      <button onClick={toggleTheme} title="Theme (G)" aria-label="Toggle light or dark theme"><span className="ti" aria-hidden="true">{theme === 'dark' ? '☀' : '☾'}</span></button>
    </div>
  )
}

function Slider({ label, value, set, min, max, step, fmt }: any) {
  return (
    <div className="frow">
      <label>{label}<span>{fmt ? fmt(value) : value}</span></label>
      <input type="range" min={min} max={max} step={step} value={value} onChange={(e) => set(parseFloat(e.target.value))} />
    </div>
  )
}

function Filters() {
  const setHighlight = useStore((s) => s.setHighlight)
  const setMode = useStore((s) => s.setMode)
  const [gapMin, setGapMin] = useState(0)
  const [gapMax, setGapMax] = useState(6)
  const [minN, setMinN] = useState(0)
  const [evOnly, setEv] = useState(false)
  const [vis, setVis] = useState(false)
  const [cheap, setCheap] = useState(false)
  const [nontox, setNontox] = useState(false)
  const [fams, setFams] = useState<string[]>([])
  const allFams = [...new Set(photoEntries.map(([, m]) => m.class))]
  const matches = useMemo(() => photoEntries.filter(([, m]) => {
    if (m.band_gap_eV < gapMin || m.band_gap_eV > gapMax) return false
    if ((m.evidence?.n_papers || 0) < minN) return false
    if (evOnly && m.confidence !== 'evidence-backed') return false
    if (vis && !m.visible) return false
    if (cheap && !m.abundant) return false
    if (nontox && m.toxic) return false
    if (fams.length && !fams.includes(m.class)) return false
    return true
  }).map(([k]) => k), [gapMin, gapMax, minN, evOnly, vis, cheap, nontox, fams])
  useEffect(() => {
    setMode('universe')
    const t = setTimeout(() => setHighlight(matches.length < photoEntries.length ? matches : []), 70)
    return () => clearTimeout(t)
  }, [matches])
  const toggleFam = (f: string) => setFams((x) => x.includes(f) ? x.filter((y) => y !== f) : [...x, f])
  return (
    <div>
      <Slider label="Band gap min" value={gapMin} set={setGapMin} min={0} max={6} step={0.1} fmt={(v: number) => v.toFixed(1) + ' eV'} />
      <Slider label="Band gap max" value={gapMax} set={setGapMax} min={0} max={6} step={0.1} fmt={(v: number) => v.toFixed(1) + ' eV'} />
      <Slider label="Min studies" value={minN} set={setMinN} min={0} max={100} step={1} />
      <div className="ftoggles">
        <button className={evOnly ? 'on' : ''} onClick={() => setEv(!evOnly)}>Well-studied only</button>
        <button className={vis ? 'on' : ''} onClick={() => setVis(!vis)}>Visible-light</button>
        <button className={cheap ? 'on' : ''} onClick={() => setCheap(!cheap)}>Earth-abundant</button>
        <button className={nontox ? 'on' : ''} onClick={() => setNontox(!nontox)}>Non-toxic</button>
      </div>
      <div className="flabel">Families</div>
      <div className="ftoggles">
        {allFams.map((f) => <button key={f} className={fams.includes(f) ? 'on' : ''} onClick={() => toggleFam(f)}>{CLASS_LABEL[f] || f}</button>)}
      </div>
      <div className="fcount">{matches.length} of {photoEntries.length} materials match. They are spotlighted on the map.</div>
    </div>
  )
}

function Leaderboards() {
  const select = useStore((s) => s.select)
  const setMode = useStore((s) => s.setMode)
  const [tab, setTab] = useState('visible')
  const TABS = [['visible', 'Visible-light H2'], ['photo', 'All photocatalysts'], ['her', 'HER'], ['oer', 'OER']]
  const rows = LEADERBOARDS[tab] || []
  const open = (name: string) => { setMode(tab === 'her' ? 'her' : tab === 'oer' ? 'oer' : 'universe'); setTimeout(() => select(name), 70) }
  return (
    <div>
      <div className="ltabs">{TABS.map(([id, label]) => <button key={id} className={tab === id ? 'on' : ''} onClick={() => setTab(id)}>{label}</button>)}</div>
      <ol className="lboard">
        {rows.map((r: any, i: number) => (
          <li key={r.name} onClick={() => open(r.name)}><span className="rk">{i + 1}</span><span className="rn">{r.name}</span><span className="rv">{r.value}</span></li>
        ))}
      </ol>
    </div>
  )
}

function radarPoints(vals: number[], cx: number, cy: number, R: number) {
  const n = vals.length
  return vals.map((v, i) => {
    const a = -Math.PI / 2 + (i * 2 * Math.PI) / n
    return [cx + Math.cos(a) * R * v, cy + Math.sin(a) * R * v]
  })
}

function Compare() {
  const compare = useStore((s) => s.compare)
  const toggleCompare = useStore((s) => s.toggleCompare)
  const AX = ['Promising', 'Evidence', 'Visible', 'Abundant', 'Non-toxic']
  const norm = (m: any) => [promisingOf(m), Math.min((m.evidence?.n_papers || 0) / 150, 1), Math.min((m.solar_abs || 0) / 0.5, 1), m.abundant ? 1 : 0.3, m.toxic ? 0.2 : 1]
  const cols = ['#2dd4bf', '#60a5fa', '#fbbf24', '#f87171', '#a855f7']
  const cx = 150, cy = 140, R = 110
  if (compare.length < 2) return <div className="empty">Open a material and tap "Compare" to add 2 to 5 here, then see them side by side.</div>
  return (
    <div>
      <svg viewBox="0 0 300 280" style={{ width: '100%' }}>
        {[0.25, 0.5, 0.75, 1].map((r) => <polygon key={r} points={radarPoints(AX.map(() => r), cx, cy, R).map((p) => p.join(',')).join(' ')} fill="none" stroke="rgba(255,255,255,0.12)" />)}
        {AX.map((a, i) => { const [x, y] = radarPoints(AX.map(() => 1.12), cx, cy, R)[i]; return <text key={a} x={x} y={y} fontSize="10" fill="var(--ink3)" textAnchor="middle">{a}</text> })}
        {compare.map((k, ci) => {
          const m = DATA.photo[k]; if (!m) return null
          const pts = radarPoints(norm(m), cx, cy, R)
          return <polygon key={k} points={pts.map((p) => p.join(',')).join(' ')} fill={cols[ci] + '22'} stroke={cols[ci]} strokeWidth="1.6" />
        })}
      </svg>
      <div className="clegend">
        {compare.map((k, ci) => <div key={k} className="cl"><span className="dot" style={{ background: cols[ci] }} />{k}<button onClick={() => toggleCompare(k)} aria-label="remove">{'×'}</button></div>)}
      </div>
    </div>
  )
}

function Hetero() {
  const [a, setA] = useState('ZnO')
  const [b, setB] = useState('TiO2')
  const mats = photoEntries.filter(([, m]) => m.cb != null).map(([k]) => k)
  const ma = DATA.photo[a], mb = DATA.photo[b]
  const verdict = useMemo(() => {
    if (!ma || !mb || ma.cb == null || mb.cb == null) return { ok: false, text: 'Band edges unavailable for one of these.' }
    const stagger = (ma.cb < mb.cb && ma.vb < mb.vb) || (mb.cb < ma.cb && mb.vb < ma.vb)
    const overlap = Math.min(ma.vb, mb.vb) > Math.max(ma.cb, mb.cb)
    if (stagger && overlap) return { ok: true, text: `Type-II / Z-scheme friendly: the band edges are staggered, so electrons and holes separate across the junction. A promising pair for ${a}/${b}.` }
    return { ok: false, text: `The band edges line up (straddling), so charge separation across an ${a}/${b} junction is weaker. Less ideal as a type-II pair.` }
  }, [a, b])
  const scale = (v: number) => 170 - (v + 1) / 4 * 150
  return (
    <div>
      <div className="hsel">
        <select value={a} onChange={(e) => setA(e.target.value)}>{mats.map((k) => <option key={k}>{k}</option>)}</select>
        <span>+</span>
        <select value={b} onChange={(e) => setB(e.target.value)}>{mats.map((k) => <option key={k}>{k}</option>)}</select>
      </div>
      <svg viewBox="0 0 300 200" style={{ width: '100%' }}>
        <line x1="0" y1={scale(0)} x2="300" y2={scale(0)} stroke="#34d399" strokeDasharray="3 3" /><text x="2" y={scale(0) - 3} fontSize="9" fill="#34d399">H+/H2 (0 V)</text>
        <line x1="0" y1={scale(1.23)} x2="300" y2={scale(1.23)} stroke="#60a5fa" strokeDasharray="3 3" /><text x="2" y={scale(1.23) - 3} fontSize="9" fill="#60a5fa">O2/H2O (1.23 V)</text>
        {[[ma, a, 70, '#2dd4bf'], [mb, b, 200, '#fbbf24']].map(([m, name, x, col]: any) => m && m.cb != null && (
          <g key={name}>
            <rect x={x} y={scale(m.cb)} width="50" height={scale(m.vb) - scale(m.cb)} fill={col + '33'} stroke={col} />
            <text x={x + 25} y={scale(m.cb) - 4} fontSize="10" fill={col} textAnchor="middle">{name}</text>
            <text x={x + 25} y={scale(m.cb) + 12} fontSize="8" fill="var(--ink2)" textAnchor="middle">CB {m.cb}</text>
            <text x={x + 25} y={scale(m.vb) - 4} fontSize="8" fill="var(--ink2)" textAnchor="middle">VB {m.vb}</text>
          </g>
        ))}
      </svg>
      <div className={'hverdict ' + (verdict.ok ? 'ok' : '')}>{verdict.text}</div>
      <div className="hnote">Band edges are estimated from electronegativity (Mulliken method), shown as guidance.</div>
    </div>
  )
}

function Shortlist() {
  const shortlist = useStore((s) => s.shortlist)
  const select = useStore((s) => s.select)
  const setMode = useStore((s) => s.setMode)
  const toggleShort = useStore((s) => s.toggleShort)
  const exportReport = () => {
    const rows = shortlist.map((k) => {
      const m = DATA.photo[k]; if (!m) return ''
      const c = m.combos['methanol|true']; const ev = m.evidence
      return `<tr><td><b>${k}</b></td><td>${CLASS_LABEL[m.class] || m.class}</td><td>${m.band_gap_eV} eV</td><td>${c.tier}</td><td>${Math.round(c.promising * 100)}%</td><td>${ev ? ev.n_papers : '-'}</td><td>${m.cost}${m.toxic ? ', toxic' : ''}</td></tr>`
    }).join('')
    const html = `<html><head><title>H2 Catalyst shortlist</title><style>body{font-family:Inter,Arial,sans-serif;padding:32px;color:#111}h1{font-size:22px}table{border-collapse:collapse;width:100%;margin-top:16px;font-size:13px}th,td{border-bottom:1px solid #ddd;text-align:left;padding:8px 10px}th{color:#555;font-size:11px;text-transform:uppercase}small{color:#888}</style></head><body><h1>H2 Catalyst Explorer - candidate shortlist</h1><small>Generated from thedeveloperaaa.github.io/H2-Catalyst-Explorer</small><table><thead><tr><th>Material</th><th>Family</th><th>Band gap</th><th>Tier</th><th>Promising</th><th>Studies</th><th>Practical</th></tr></thead><tbody>${rows}</tbody></table><p style="margin-top:24px;color:#888;font-size:12px">Photocatalysis predictions are an honest screen (grouped ROC-AUC 0.65), not exact rates. Read alongside the published evidence.</p></body></html>`
    const w = window.open('', '_blank'); if (w) { w.document.write(html); w.document.close(); setTimeout(() => w.print(), 300) }
  }
  if (!shortlist.length) return <div className="empty">Star materials from their detail panel to build a synthesis shortlist, then export it as a PDF.</div>
  return (
    <div>
      <button className="export-btn" onClick={exportReport}>Export shortlist as PDF</button>
      <ul className="slist">
        {shortlist.map((k) => {
          const m = DATA.photo[k]
          return <li key={k}><span className="dot" style={{ background: m ? classColor(m.class) : '#888' }} /><span className="sn" onClick={() => { setMode('universe'); setTimeout(() => select(k), 60) }}>{k}</span><button onClick={() => toggleShort(k)} aria-label="remove">{'×'}</button></li>
        })}
      </ul>
    </div>
  )
}

const TITLES: Record<string, string> = { filters: 'Filter the universe', leaderboards: 'Leaderboards', compare: 'Compare materials', hetero: 'Heterojunction designer', shortlist: 'Synthesis shortlist' }

export function Panel() {
  const panel = useStore((s) => s.panel)
  const setPanel = useStore((s) => s.setPanel)
  if (!panel) return null
  return (
    <div className="panel-wrap glass">
      <div className="panel-head"><h3>{TITLES[panel]}</h3><button onClick={() => setPanel(null)} aria-label="close">{'×'}</button></div>
      <div className="panel-body">
        {panel === 'filters' && <Filters />}
        {panel === 'leaderboards' && <Leaderboards />}
        {panel === 'compare' && <Compare />}
        {panel === 'hetero' && <Hetero />}
        {panel === 'shortlist' && <Shortlist />}
      </div>
    </div>
  )
}
