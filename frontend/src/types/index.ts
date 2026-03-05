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
  distance_to_tehran_km: number;
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
/** OSINT event from GDELT or OpenSky feeds */
export interface OsintEvent {
  id: string;
  source: 'GDELT' | 'OPENSKY';
  event_type: string;
  title: string;
  timestamp: string;
  location?: { lat: number; lon: number };
  relevance_score: number;
  metadata?: Record<string, unknown>;
}

/** Aggregated OSINT feed response */
export interface OsintFeedsResponse {
  source: string;
  events: OsintEvent[];
  breakdown: Record<string, number>;
  timestamp: string;
}

/** Bayesian causal DAG threat assessment */
export interface CausalAssessment {
  threat_level: 'CRITICAL' | 'HIGH' | 'ELEVATED' | 'LOW' | 'MINIMAL';
  composite_score: number;
  escalation_probability: number;
  military_posture_index: number;
  causal_factors: {
    gdelt_tone_avg: number;
    aircraft_density: number;
    escalation_node: number;
    posture_node: number;
  };
  evidence_summary: {
    gdelt_articles: number;
    military_flights: number;
    assessment_basis: string;
  };
  timestamp: string;
}

export type ThreatLevel = CausalAssessment['threat_level'];

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

/** Threat level color mapping for Bayesian assessment UI */
export const THREAT_LEVEL_COLORS: Record<string, string> = {
  CRITICAL: '#ef4444',
  HIGH: '#f97316',
  ELEVATED: '#eab308',
  LOW: '#22c55e',
  MINIMAL: '#6b7280',
};
