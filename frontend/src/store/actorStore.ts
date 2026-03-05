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
  MdoStatus,
  OodaCycle,
  KillWebMetrics,
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
  mdoStatus: MdoStatus | null;
  oodaCycle: OodaCycle | null;
  killWebMetrics: KillWebMetrics | null;
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
  fetchMdoStatus: () => Promise<void>;
  fetchOodaCycle: () => Promise<void>;
  fetchKillWebMetrics: () => Promise<void>;
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
  mdoStatus: null,
  oodaCycle: null,
  killWebMetrics: null,
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
  fetchMdoStatus: async () => {
    try {
      const mdoStatus = await apiFetch<MdoStatus>(ENDPOINTS.mdoStatus);
      set({ mdoStatus });
    } catch {}
  },

  fetchOodaCycle: async () => {
    try {
      const oodaCycle = await apiFetch<OodaCycle>(ENDPOINTS.oodaCycle);
      set({ oodaCycle });
    } catch {}
  },

  fetchKillWebMetrics: async () => {
    try {
      const killWebMetrics = await apiFetch<KillWebMetrics>(ENDPOINTS.killWeb);
      set({ killWebMetrics });
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
