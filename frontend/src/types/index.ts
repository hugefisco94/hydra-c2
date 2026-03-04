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
