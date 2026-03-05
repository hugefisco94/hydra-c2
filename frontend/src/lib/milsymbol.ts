/**
 * MIL-STD-2525 Symbol rendering via milsymbol library
 * Generates Leaflet-compatible icons from SIDC codes
 */

import ms from 'milsymbol';
import L from 'leaflet';
import type { Actor } from '../types';

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
  TYPE_FRIEND_AIR_AIRCRAFT: 'SFAPMF-----K',
  TYPE_FRIEND_AIR_UAV: 'SFAPMFQ----K',
  TYPE_FRIEND_LAND_VEHICLE: 'SFGPUCA----K',
  TYPE_FRIEND_SEA_VESSEL: 'SFSPCLCC---K',
  TYPE_HOSTILE_LAND_UNIT: 'SHGPUCI----K',
  TYPE_HOSTILE_AIR_AIRCRAFT: 'SHAPMF-----K',
  TYPE_NEUTRAL_AIR_AIRCRAFT: 'SNAPMF-----K',
  TYPE_UNKNOWN_LAND_UNIT: 'SUGPUCI----K',
  CYBER: 'SFGPEWRH---K',
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
export function getDefaultSidc(
  affiliation: string,
  domain: string,
  actorType?: string,
): string {
  const normalizedAffiliation = normalizeAffiliation(affiliation);
  const normalizedDomain = domain.toUpperCase();
  const normalizedActorType = actorType?.toUpperCase();

  if (normalizedDomain === 'CYBER') {
    return DEFAULT_SIDCS.CYBER;
  }

  if (normalizedActorType) {
    const typedKey = `TYPE_${normalizedAffiliation}_${normalizedDomain}_${normalizedActorType}`;
    if (typedKey in DEFAULT_SIDCS) return DEFAULT_SIDCS[typedKey];
  }

  const key = `${normalizedAffiliation}_${normalizedDomain}`;
  if (key in DEFAULT_SIDCS) return DEFAULT_SIDCS[key];

  if (normalizedAffiliation === 'UNKNOWN' && normalizedDomain === 'LAND') {
    return DEFAULT_SIDCS.UNKNOWN_LAND_UNIT;
  }

  // Fallback: unknown ground unit
  return 'SUGPU------K';
}

export function isGenericSidc(sidc: string): boolean {
  const normalized = sidc.trim().toUpperCase();
  return [
    'SFGP------',
    'SHGP------',
    'SNGP------',
    'SUGP------',
    'SFGP------K',
    'SHGP------K',
    'SNGP------K',
    'SUGP------K',
  ].includes(normalized);
}

export function resolveActorSidc(actor: Actor): string {
  const incomingSidc = actor.sidc?.trim() ?? '';
  if (incomingSidc && !isGenericSidc(incomingSidc)) {
    return incomingSidc;
  }

  const actorType = extractActorType(actor);
  return getDefaultSidc(actor.affiliation, actor.domain, actorType);
}

function extractActorType(actor: Actor): string | undefined {
  const metadataActorType = actor.metadata?.actor_type;
  if (typeof metadataActorType === 'string' && metadataActorType.length > 0) {
    return metadataActorType;
  }
  return undefined;
}

function normalizeAffiliation(affiliation: string): string {
  const normalized = affiliation.trim().toUpperCase();
  if (normalized === 'FRIENDLY') return 'FRIEND';
  if (normalized === 'HOSTILE') return 'HOSTILE';
  if (normalized === 'NEUTRAL') return 'NEUTRAL';
  if (normalized === 'UNKNOWN') return 'UNKNOWN';
  return normalized;
}
