let renderer: any = null
let scene: any = null
let camera: any = null

export function setXR(r: any, s: any, c: any) { renderer = r; scene = s; camera = c }

export async function vrSupported(): Promise<boolean> {
  try {
    const xr = (navigator as any).xr
    return !!(xr && (await xr.isSessionSupported('immersive-vr')))
  } catch {
    return false
  }
}

export async function enterVR() {
  const xr = (navigator as any).xr
  if (!renderer || !xr) return
  try {
    const session = await xr.requestSession('immersive-vr', { optionalFeatures: ['local-floor', 'bounded-floor'] })
    renderer.xr.enabled = true
    await renderer.xr.setSession(session)
    renderer.setAnimationLoop(() => renderer.render(scene, camera))
    session.addEventListener('end', () => { renderer.setAnimationLoop(null); renderer.xr.enabled = false })
  } catch (e) {
    /* ignore: best-effort VR */
  }
}

export function exportImage() {
  const c = document.querySelector('canvas') as HTMLCanvasElement
  if (!c) return
  const url = c.toDataURL('image/png')
  const a = document.createElement('a')
  a.href = url
  a.download = 'h2-catalyst-explorer.png'
  a.click()
}
