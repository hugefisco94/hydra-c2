import { CircleMarker, Polygon, Polyline, Tooltip } from 'react-leaflet';

/**
 * Strategic Zones Overlay — Iran / Persian Gulf Theater
 * Replaces DMZ overlay with ME-relevant strategic geography
 */

/** Strait of Hormuz chokepoint zone */
const HORMUZ_STRAIT: Array<[number, number]> = [
  [26.90, 56.00],
  [26.90, 56.60],
  [26.20, 56.60],
  [26.20, 56.00],
];

/** Persian Gulf shipping lane (approximate centerline) */
const SHIPPING_LANE: Array<[number, number]> = [
  [29.40, 48.80],
  [28.50, 49.80],
  [27.50, 51.50],
  [26.70, 53.50],
  [26.55, 56.30],
  [25.50, 57.50],
];

/** Key strategic locations */
const STRATEGIC_POINTS: Array<{
  position: [number, number];
  label: string;
  color: string;
  fillColor: string;
}> = [
  { position: [27.1865, 56.2808], label: 'Bandar Abbas (IRIN HQ)', color: '#ff3b30', fillColor: '#ef4444' },
  { position: [25.1174, 51.3150], label: 'Al Udeid AB (CENTCOM)', color: '#3b82f6', fillColor: '#2563eb' },
  { position: [24.2481, 54.5472], label: 'Al Dhafra AB (USAF)', color: '#3b82f6', fillColor: '#2563eb' },
  { position: [33.7225, 51.7275], label: 'Natanz (Nuclear)', color: '#f59e0b', fillColor: '#d97706' },
  { position: [28.9234, 50.8203], label: 'Bushehr (NPP)', color: '#f59e0b', fillColor: '#d97706' },
  { position: [34.7081, 51.2403], label: 'Fordow (UGF)', color: '#f59e0b', fillColor: '#d97706' },
  { position: [32.6546, 51.6680], label: 'Isfahan (UCF)', color: '#f59e0b', fillColor: '#d97706' },
  { position: [29.1500, 47.9250], label: 'Camp Arifjan (USA)', color: '#3b82f6', fillColor: '#2563eb' },
];

export function StrategicZonesOverlay() {
  return (
    <>
      {/* Strait of Hormuz chokepoint */}
      <Polygon
        positions={HORMUZ_STRAIT}
        pathOptions={{
          color: '#ff7849',
          weight: 1,
          fillColor: '#ff4d2e',
          fillOpacity: 0.14,
          className: 'strategic-zone',
        }}
      />
      {/* Persian Gulf shipping lane */}
      <Polyline
        positions={SHIPPING_LANE}
        pathOptions={{
          color: '#38bdf8',
          weight: 2,
          dashArray: '10 8',
          opacity: 0.6,
          className: 'shipping-lane',
        }}
      />
      {/* Strategic location markers */}
      {STRATEGIC_POINTS.map((pt) => (
        <CircleMarker
          key={pt.label}
          center={pt.position}
          radius={5}
          pathOptions={{
            color: pt.color,
            weight: 2,
            fillColor: pt.fillColor,
            fillOpacity: 0.9,
          }}
        >
          <Tooltip direction="top" offset={[0, -4]} opacity={0.95}>
            {pt.label}
          </Tooltip>
        </CircleMarker>
      ))}
    </>
  );
}
