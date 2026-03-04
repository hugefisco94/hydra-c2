/**
 * HYDRA-C2 API Configuration
 *
 * Production: DO GPU at 134.199.207.172:8080
 * Development: proxied via Vite dev server
 */

export const API_BASE_URL: string =
  import.meta.env.VITE_API_BASE_URL ?? 'http://134.199.207.172:8080';

export const ENDPOINTS = {
  health: `${API_BASE_URL}/health`,
  actors: `${API_BASE_URL}/api/v1/actors`,
  actorById: (id: string) => `${API_BASE_URL}/api/v1/actors/${id}`,
  cotIngest: `${API_BASE_URL}/api/v1/cot/ingest`,
  sdrDetections: `${API_BASE_URL}/api/v1/sdr/detections`,
  geofences: `${API_BASE_URL}/api/v1/geofence/check`,
  networkQuery: `${API_BASE_URL}/api/v1/network/query`,
} as const;

/** Polling interval in milliseconds for real-time updates */
export const POLL_INTERVAL_MS = 3000;
