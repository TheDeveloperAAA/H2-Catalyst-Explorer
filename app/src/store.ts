import { create } from 'zustand'

export type Mode = 'universe' | 'her' | 'oer'

interface S {
  mode: Mode
  selected: string | null
  hovered: string | null
  search: string
  onboarded: boolean
  tour: number
  setMode: (m: Mode) => void
  select: (s: string | null) => void
  setHovered: (s: string | null) => void
  setSearch: (q: string) => void
  dismissOnboard: () => void
  startTour: () => void
  nextTour: () => void
  endTour: () => void
}

export const useStore = create<S>((set) => ({
  mode: 'universe',
  selected: null,
  hovered: null,
  search: '',
  onboarded: false,
  tour: -1,
  setMode: (mode) => set({ mode, selected: null, search: '' }),
  select: (selected) => set({ selected }),
  setHovered: (hovered) => set({ hovered }),
  setSearch: (search) => set({ search }),
  dismissOnboard: () => set({ onboarded: true }),
  startTour: () => set({ onboarded: true, tour: 0 }),
  nextTour: () => set((s) => ({ tour: s.tour + 1 })),
  endTour: () => set({ tour: -1, selected: null }),
}))
