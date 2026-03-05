/**
 * HYDRA-C2 API Configuration
 *
 * Production: DO GPU via Caddy HTTPS reverse proxy (sslip.io)
 * Development: proxied via Vite dev server
 */

/** HTTPS-enabled API base URL — resolves mixed-content issue on GitHub Pages */
export const API_BASE_URL: string =
  import.meta.env.VITE_API_BASE_URL ?? 'https://134-199-207-172.sslip.io';

export const ENDPOINTS = {
  health: `${API_BASE_URL}/health`,
  actors: `${API_BASE_URL}/api/v1/actors`,
  actorById: (id: string) => `${API_BASE_URL}/api/v1/actors/${id}`,
  actorNetwork: (id: string) => `${API_BASE_URL}/api/v1/actors/${id}/network`,
  threatAssessment: `${API_BASE_URL}/api/v1/threat-assessment`,
  analyticsOverview: `${API_BASE_URL}/api/v1/analytics/overview`,
  cotIngest: `${API_BASE_URL}/api/v1/cot/ingest`,
  sdrDetections: `${API_BASE_URL}/api/v1/sdr/detections`,
  geofences: `${API_BASE_URL}/api/v1/geofences`,
  geofenceCheck: `${API_BASE_URL}/api/v1/geofences/check`,
  sdrReference: `${API_BASE_URL}/api/v1/sdr/reference`,
  adsbStateModel: `${API_BASE_URL}/api/v1/adsb/state-model`,
  aisVesselModel: `${API_BASE_URL}/api/v1/ais/vessel-model`,
  signalChain: `${API_BASE_URL}/api/v1/signals/processing-chain`,
  osintFeeds: `${API_BASE_URL}/api/v1/osint/feeds`,
  osintThreatAssessment: `${API_BASE_URL}/api/v1/osint/threat-assessment`,
} as const;

/** Polling interval in milliseconds for real-time updates */
export const POLL_INTERVAL_MS = 5_000;

/** Connection timeout in milliseconds */
export const FETCH_TIMEOUT_MS = 8_000;

/** Helper: fetch with timeout + abort */
export async function apiFetch<T>(url: string, init?: RequestInit): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);

  try {
    const res = await fetch(url, { ...init, signal: controller.signal });
    if (!res.ok) throw new Error(`API ${res.status}: ${res.statusText}`);
    return (await res.json()) as T;
  } finally {
    clearTimeout(timeout);
  }
}
