import { useMemo, useRef } from 'react'
import { Canvas, useFrame } from '@react-three/fiber'
import { OrbitControls, Stars, Html } from '@react-three/drei'
import * as THREE from 'three'
import { photoEntries, electroEntries, oerEntries, classColor, promisingOf } from './data'
import { useStore } from './store'
import type { Mode } from './store'

type Node = { key: string; m: any; pos: [number, number, number]; color: string; scale: number; sub: string }

function layout(mode: Mode): Node[] {
  if (mode === 'universe') {
    return photoEntries.map(([k, m]) => {
      const gap = m.band_gap_eV ?? 2.7
      const prom = promisingOf(m)
      const rate = m.evidence?.median_rate ?? 1
      const n = m.evidence?.n_papers ?? 0
      return {
        key: k, m,
        pos: [(gap - 2.6) * 2.1, (prom - 0.5) * 15, (Math.log10(Math.max(rate, 1)) - 2) * 2.3],
        color: classColor(m.class),
        scale: 0.16 + Math.min(n, 200) / 200 * 0.4 + prom * 0.22,
        sub: `${m.band_gap_eV} eV · ${Math.round(prom * 100)}% promising`,
      }
    })
  }
  if (mode === 'her') {
    return electroEntries.map(([k, m], i) => ({
      key: k, m,
      pos: [m.energy_eV * 5, m.score / 9 - 4, ((i % 6) - 2.5) * 1.3],
      color: m.score >= 70 ? '#34d399' : m.score >= 40 ? '#fbbf24' : '#f87171',
      scale: 0.32 + m.score / 200,
      sub: `${m.energy_eV > 0 ? '+' : ''}${m.energy_eV} eV · score ${Math.round(m.score)}`,
    }))
  }
  return oerEntries.map(([k, m], i) => ({
    key: k, m,
    pos: [(m.descriptor - 1.6) * 4, m.score / 9 - 4, ((i % 9) - 4) * 1.1],
    color: m.score >= 70 ? '#34d399' : m.score >= 40 ? '#fbbf24' : '#f87171',
    scale: 0.22 + m.score / 260,
    sub: `descriptor ${m.descriptor} eV · score ${Math.round(m.score)}`,
  }))
}

function Node3D({ n }: { n: Node }) {
  const selected = useStore((s) => s.selected)
  const hovered = useStore((s) => s.hovered)
  const select = useStore((s) => s.select)
  const setHovered = useStore((s) => s.setHovered)
  const ref = useRef<THREE.Mesh>(null!)
  const isSel = selected === n.key
  const isHov = hovered === n.key
  useFrame(() => {
    const t = (isSel ? 1.8 : isHov ? 1.4 : 1) * n.scale
    if (ref.current) ref.current.scale.lerp(new THREE.Vector3(t, t, t), 0.18)
  })
  return (
    <mesh
      ref={ref}
      position={n.pos}
      onPointerOver={(e) => { e.stopPropagation(); setHovered(n.key); document.body.style.cursor = 'pointer' }}
      onPointerOut={() => { setHovered(null); document.body.style.cursor = 'default' }}
      onClick={(e) => { e.stopPropagation(); select(n.key) }}
    >
      <sphereGeometry args={[1, 22, 22]} />
      <meshStandardMaterial color={n.color} emissive={n.color} emissiveIntensity={isSel || isHov ? 1.2 : 0.5} roughness={0.35} metalness={0.15} />
      {(isHov || isSel) && (
        <Html center distanceFactor={16} zIndexRange={[20, 0]}>
          <div className="tooltip3d"><div className="tn">{n.key}</div><div className="ts">{n.sub}</div></div>
        </Html>
      )}
    </mesh>
  )
}

function Rig({ nodes }: { nodes: Node[] }) {
  const selected = useStore((s) => s.selected)
  const controls = useRef<any>(null)
  useFrame(() => {
    if (!controls.current) return
    const sel = nodes.find((n) => n.key === selected)
    const dest = sel ? new THREE.Vector3(...sel.pos) : new THREE.Vector3(0, 0, 0)
    controls.current.target.lerp(dest, 0.05)
    controls.current.update()
  })
  return <OrbitControls ref={controls} enableDamping dampingFactor={0.12} rotateSpeed={0.6} minDistance={4} maxDistance={70} />
}

export default function Scene() {
  const mode = useStore((s) => s.mode)
  const select = useStore((s) => s.select)
  const nodes = useMemo(() => layout(mode), [mode])
  return (
    <div className="canvas-wrap">
      <Canvas camera={{ position: [11, 7, 19], fov: 50 }} onPointerMissed={() => select(null)} dpr={[1, 2]}>
        <color attach="background" args={['#060a12']} />
        <ambientLight intensity={0.6} />
        <pointLight position={[20, 20, 20]} intensity={1.3} />
        <pointLight position={[-20, -10, -20]} intensity={0.4} color="#60a5fa" />
        <Stars radius={140} depth={70} count={2200} factor={4} saturation={0} fade speed={0.4} />
        {nodes.map((n) => <Node3D key={n.key} n={n} />)}
        <Rig nodes={nodes} />
      </Canvas>
    </div>
  )
}
