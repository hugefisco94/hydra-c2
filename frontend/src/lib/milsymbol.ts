/**
 * MIL-STD-2525 Symbol rendering via milsymbol library
 * Generates Leaflet-compatible icons from SIDC codes
 */

import ms from 'milsymbol';
import L from 'leaflet';

export interface MilSymbolOptions {
  size?: number;
  frame?: boolean;
  fill?: boolean;
}

/**
 * Create a Leaflet icon from a MIL-STD-2525 Symbol Identification Code (SIDC)
 */
export function createMilSymbolIcon(
  sidc: string,
  options: MilSymbolOptions = {},
): L.Icon {
  const symbol = new ms.Symbol(sidc, {
    size: options.size ?? 32,
    frame: options.frame ?? true,
    fill: options.fill ?? true,
  });

  const anchor = symbol.getAnchor();
  const size = symbol.getSize();

  return L.icon({
    iconUrl: symbol.toDataURL(),
    iconSize: [size.width, size.height],
    iconAnchor: [anchor.x, anchor.y],
    popupAnchor: [0, -anchor.y],
  });
}

/**
 * Generate SVG string for inline rendering (panels, tooltips)
 */
export function createMilSymbolSvg(sidc: string, size = 64): string {
  const symbol = new ms.Symbol(sidc, { size, frame: true, fill: true });
  return symbol.asSVG();
}

/**
 * Default SIDC codes for common actor types
 * Format: S[Affiliation][Battle Dimension][Function ID]
 */
export const DEFAULT_SIDCS: Record<string, string> = {
  // Friendly
  FRIEND_LAND_UNIT: 'SFGPUCI----K',
  FRIEND_LAND_ARMOR: 'SFGPUCA----K',
  FRIEND_AIR: 'SFAPMF-----K',
  FRIEND_SEA: 'SFSPCLCC---K',
  // Hostile
  HOSTILE_LAND_UNIT: 'SHGPUCI----K',
  HOSTILE_LAND_ARMOR: 'SHGPUCA----K',
  HOSTILE_AIR: 'SHAPMF-----K',
  HOSTILE_SEA: 'SHSPCLCC---K',
  // Neutral
  NEUTRAL_LAND: 'SNGPUCI----K',
  NEUTRAL_AIR: 'SNAPMF-----K',
  // Unknown
  UNKNOWN_LAND: 'SUGPUCI----K',
  UNKNOWN_AIR: 'SUAPMF-----K',
};

/**
 * Get a fallback SIDC based on affiliation + domain
 */
export function getDefaultSidc(affiliation: string, domain: string): string {
  const key = `${affiliation}_${domain}`;
  if (key in DEFAULT_SIDCS) return DEFAULT_SIDCS[key];
  // Fallback: unknown ground unit
  return 'SUGPU------K';
}
