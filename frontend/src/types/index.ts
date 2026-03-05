/**
 * HYDRA-C2 Domain Types — matches backend entity schema
 */

export type Affiliation = 'FRIEND' | 'HOSTILE' | 'NEUTRAL' | 'UNKNOWN';

export type Domain = 'LAND' | 'AIR' | 'SEA' | 'SUBSURFACE' | 'SPACE' | 'CYBER';

export interface GeoPosition {
  latitude: number;
  longitude: number;
  altitude?: number;
}

export interface Actor {
  id: string;
  name: string;
  sidc: string;
  affiliation: Affiliation;
  domain: Domain;
  position: GeoPosition;
  last_seen: string;
  metadata?: Record<string, unknown>;
}

export interface SdrDetection {
  id: string;
  frequency_hz: number;
  signal_strength_dbm: number;
  modulation?: string;
  position?: GeoPosition;
  timestamp: string;
}

export interface HealthStatus {
  status: string;
  infrastructure: string;
}

export interface ActorsResponse {
  actors: Actor[];
  total: number;
}

export interface ThreatAssessmentItem {
  actor_id: string;
  name: string;
  affiliation: string;
  domain: string;
  composite_score: number;
  classification: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
  distance_to_seoul_km: number;
  closest_critical_asset: string;
}

export interface ThreatAssessment {
  assessments: ThreatAssessmentItem[];
  total: number;
  critical_count: number;
  high_count: number;
  timestamp: string;
}

export interface AnalyticsOverview {
  total_tracks: number;
  by_affiliation: Record<string, number>;
  by_domain: Record<string, number>;
  force_ratio: { friendly: number; hostile: number; ratio: number };
  top_threats: Array<{ name: string; classification: string; composite_score: number }>;
  timestamp: string;
}
export interface MdoDomainStatus {
  total_tracks: number;
  friendly: number;
  hostile: number;
  coverage_pct: number;
  status: 'PERMISSIVE' | 'CONTESTED' | 'DENIED' | 'UNKNOWN';
}

export interface MdoStatus {
  doctrine: string;
  current_phase: string;
  phases: string[];
  domains: Record<string, MdoDomainStatus>;
  convergence_readiness: number;
  cross_domain_synergy: {
    contested_domains: number;
    permissive_domains: number;
    denied_domains: number;
    total_friendly: number;
    total_hostile: number;
  };
  timestamp: string;
}

export interface OodaPhase {
  score: number;
  status: 'GREEN' | 'AMBER' | 'RED';
  [key: string]: unknown;
}

export interface OodaCycle {
  doctrine: string;
  ooda_phases: {
    OBSERVE: OodaPhase;
    ORIENT: OodaPhase;
    DECIDE: OodaPhase;
    ACT: OodaPhase;
  };
  composite_score: number;
  cycle_assessment: string;
  ncw_principles: {
    information_superiority: number;
    shared_awareness: number;
    self_synchronization: number;
  };
  timestamp: string;
}

export interface KillWebMetrics {
  doctrine: string;
  nodes: { sensors: unknown[]; shooters: unknown[]; c2: unknown[]; total: number };
  total_edges: number;
  kill_web_metrics: {
    connectivity: number;
    redundancy: number;
    cross_domain_links: number;
    same_domain_links: number;
    avg_paths_per_shooter: number;
  };
  force_packages: Array<{ name: string; composition: string; mission: string }>;
  timestamp: string;
}

/** Affiliation color mapping for UI */
export const AFFILIATION_COLORS: Record<Affiliation, string> = {
  FRIEND: '#3b82f6',
  HOSTILE: '#ef4444',
  NEUTRAL: '#22c55e',
  UNKNOWN: '#eab308',
};

/** Domain icon labels */
export const DOMAIN_LABELS: Record<Domain, string> = {
  LAND: '🏔️',
  AIR: '✈️',
  SEA: '🚢',
  SUBSURFACE: '🔽',
  SPACE: '🛰️',
  CYBER: '💻',
};
