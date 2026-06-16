import { create } from 'zustand'

export type Mode = 'universe' | 'her' | 'oer'
export type Panel = null | 'filters' | 'shortlist' | 'leaderboards' | 'compare' | 'hetero'

interface S {
  mode: Mode
  selected: string | null
  hovered: string | null
  search: string
  onboarded: boolean
  tour: number
  highlight: string[]
  panel: Panel
  shortlist: string[]
  compare: string[]
  theme: 'dark' | 'light'
  eli5: boolean
  setMode: (m: Mode) => void
  select: (s: string | null) => void
  setHovered: (s: string | null) => void
  setSearch: (q: string) => void
  setHighlight: (h: string[]) => void
  dismissOnboard: () => void
  startTour: () => void
  nextTour: () => void
  endTour: () => void
  setPanel: (p: Panel) => void
  toggleShort: (k: string) => void
  toggleCompare: (k: string) => void
  toggleTheme: () => void
  toggleEli5: () => void
}

export const useStore = create<S>((set) => ({
  mode: 'universe',
  selected: null,
  hovered: null,
  search: '',
  onboarded: false,
  tour: -1,
  highlight: [],
  panel: null,
  shortlist: [],
  compare: [],
  theme: 'dark',
  eli5: false,
  setMode: (mode) => set({ mode, selected: null, search: '', highlight: [] }),
  setHighlight: (highlight) => set({ highlight }),
  select: (selected) => set((s) => ({ selected, panel: selected ? null : s.panel })),
  setHovered: (hovered) => set({ hovered }),
  setSearch: (search) => set({ search }),
  dismissOnboard: () => set({ onboarded: true }),
  startTour: () => set({ onboarded: true, tour: 0 }),
  nextTour: () => set((s) => ({ tour: s.tour + 1 })),
  endTour: () => set({ tour: -1, selected: null }),
  setPanel: (panel) => set((s) => ({ panel, selected: panel ? null : s.selected })),
  toggleShort: (k) => set((s) => ({ shortlist: s.shortlist.includes(k) ? s.shortlist.filter((x) => x !== k) : [...s.shortlist, k] })),
  toggleCompare: (k) => set((s) => ({ compare: s.compare.includes(k) ? s.compare.filter((x) => x !== k) : s.compare.length >= 5 ? s.compare : [...s.compare, k] })),
  toggleTheme: () => set((s) => ({ theme: s.theme === 'dark' ? 'light' : 'dark' })),
  toggleEli5: () => set((s) => ({ eli5: !s.eli5 })),
}))
