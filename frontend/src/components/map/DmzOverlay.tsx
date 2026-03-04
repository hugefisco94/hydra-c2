import { CircleMarker, Polygon, Polyline, Tooltip } from 'react-leaflet';

const DMZ_POLYGON: Array<[number, number]> = [
  [38.62, 124.6],
  [38.62, 128.35],
  [37.73, 128.35],
  [37.73, 124.6],
];

const MDL_LINE: Array<[number, number]> = [
  [38.175, 124.6],
  [38.175, 128.35],
];

const PANMUNJOM: [number, number] = [37.9567, 126.6775];

export function DmzOverlay() {
  return (
    <>
      <Polygon
        positions={DMZ_POLYGON}
        pathOptions={{
          color: '#ff7849',
          weight: 1,
          fillColor: '#ff4d2e',
          fillOpacity: 0.14,
          className: 'dmz-zone',
        }}
      />
      <Polyline
        positions={MDL_LINE}
        pathOptions={{
          color: '#ff3b30',
          weight: 2,
          dashArray: '10 8',
          className: 'dmz-mdl',
        }}
      />
      <CircleMarker
        center={PANMUNJOM}
        radius={6}
        pathOptions={{
          color: '#ffd166',
          weight: 2,
          fillColor: '#f59e0b',
          fillOpacity: 0.9,
        }}
      >
        <Tooltip direction="top" offset={[0, -4]} opacity={0.95}>
          Panmunjom
        </Tooltip>
      </CircleMarker>
    </>
  );
}
