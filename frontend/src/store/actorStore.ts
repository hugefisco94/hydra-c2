/**
 * Zustand store for HYDRA-C2 actor state management
 */

import { useMemo } from 'react';
import { create } from 'zustand';
import { ENDPOINTS, apiFetch } from '../config/api';
import type {
  Actor,
  AnalyticsOverview,
  HealthStatus,
  ThreatAssessment,
  OsintFeedsResponse,
  CausalAssessment,
} from '../types';

export type ConnectionState = 'connecting' | 'connected' | 'disconnected';

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
  threatAssessment: ThreatAssessment | null;
  analyticsOverview: AnalyticsOverview | null;
  osintFeeds: OsintFeedsResponse | null;
  causalAssessment: CausalAssessment | null;
  connectionState: ConnectionState;

  // UI
  sidebarOpen: boolean;
  domainFilters: DomainFilter;

  // Actions
  setActors: (actors: Actor[]) => void;
  selectActor: (actor: Actor | null) => void;
  setHealth: (health: HealthStatus) => void;
  setConnectionState: (state: ConnectionState) => void;
  fetchThreatAssessment: () => Promise<void>;
  fetchAnalyticsOverview: () => Promise<void>;
  fetchOsintFeeds: () => Promise<void>;
  fetchCausalAssessment: () => Promise<void>;
  toggleSidebar: () => void;
  toggleDomainFilter: (domain: keyof DomainFilter) => void;
}

export const useActorStore = create<ActorState>((set) => ({
  // Initial state
  actors: [],
  selectedActor: null,
  health: null,
  threatAssessment: null,
  analyticsOverview: null,
  osintFeeds: null,
  causalAssessment: null,
  connectionState: 'connecting',
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

  setConnectionState: (connectionState) => set({ connectionState }),

  fetchThreatAssessment: async () => {
    try {
      const threatAssessment = await apiFetch<ThreatAssessment>(ENDPOINTS.threatAssessment);
      set({ threatAssessment });
    } catch {}
  },

  fetchAnalyticsOverview: async () => {
    try {
      const analyticsOverview = await apiFetch<AnalyticsOverview>(ENDPOINTS.analyticsOverview);
      set({ analyticsOverview });
    } catch {}
  },
  fetchOsintFeeds: async () => {
    try {
      const osintFeeds = await apiFetch<OsintFeedsResponse>(ENDPOINTS.osintFeeds);
      set({ osintFeeds });
    } catch {}
  },

  fetchCausalAssessment: async () => {
    try {
      const causalAssessment = await apiFetch<CausalAssessment>(ENDPOINTS.osintThreatAssessment);
      set({ causalAssessment });
    } catch {}
  },

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
 * Selector: get actors filtered by active domain filters.
 * Uses separate selectors + useMemo to return stable references
 * and avoid infinite re-render loops from .filter() creating new arrays.
 */
export function useFilteredActors(): Actor[] {
  const actors = useActorStore((s) => s.actors);
  const domainFilters = useActorStore((s) => s.domainFilters);
  return useMemo(
    () => actors.filter((a) => domainFilters[a.domain] ?? true),
    [actors, domainFilters],
  );
}
