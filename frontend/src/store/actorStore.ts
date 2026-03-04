/**
 * Zustand store for HYDRA-C2 actor state management
 */

import { create } from 'zustand';
import type { Actor, HealthStatus } from '../types';

export interface DomainFilter {
  LAND: boolean;
  AIR: boolean;
  SEA: boolean;
  SUBSURFACE: boolean;
  SPACE: boolean;
  CYBER: boolean;
}

interface ActorState {
  // Data
  actors: Actor[];
  selectedActor: Actor | null;
  health: HealthStatus | null;

  // UI
  sidebarOpen: boolean;
  domainFilters: DomainFilter;

  // Actions
  setActors: (actors: Actor[]) => void;
  selectActor: (actor: Actor | null) => void;
  setHealth: (health: HealthStatus) => void;
  toggleSidebar: () => void;
  toggleDomainFilter: (domain: keyof DomainFilter) => void;
}

export const useActorStore = create<ActorState>((set) => ({
  // Initial state
  actors: [],
  selectedActor: null,
  health: null,
  sidebarOpen: true,
  domainFilters: {
    LAND: true,
    AIR: true,
    SEA: true,
    SUBSURFACE: true,
    SPACE: true,
    CYBER: true,
  },

  // Actions
  setActors: (actors) => set({ actors }),

  selectActor: (actor) => set({ selectedActor: actor }),

  setHealth: (health) => set({ health }),

  toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),

  toggleDomainFilter: (domain) =>
    set((s) => ({
      domainFilters: {
        ...s.domainFilters,
        [domain]: !s.domainFilters[domain],
      },
    })),
}));

/**
 * Selector: get actors filtered by active domain filters
 */
export function useFilteredActors(): Actor[] {
  return useActorStore((s) =>
    s.actors.filter((a) => s.domainFilters[a.domain] ?? true),
  );
}
