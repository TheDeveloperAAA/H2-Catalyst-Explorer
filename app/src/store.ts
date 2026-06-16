import { create } from 'zustand'

export type Mode = 'universe' | 'her' | 'oer'

interface S {
  mode: Mode
  selected: string | null
  hovered: string | null
  search: string
  onboarded: boolean
  setMode: (m: Mode) => void
  select: (s: string | null) => void
  setHovered: (s: string | null) => void
  setSearch: (q: string) => void
  dismissOnboard: () => void
}

export const useStore = create<S>((set) => ({
  mode: 'universe',
  selected: null,
  hovered: null,
  search: '',
  onboarded: false,
  setMode: (mode) => set({ mode, selected: null, search: '' }),
  select: (selected) => set({ selected }),
  setHovered: (hovered) => set({ hovered }),
  setSearch: (search) => set({ search }),
  dismissOnboard: () => set({ onboarded: true }),
}))
