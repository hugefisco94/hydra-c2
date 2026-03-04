/**
 * COP (Common Operating Picture) Map Component
 * Leaflet map with OSM/CartoDB dark tiles displaying MIL-STD-2525 actors
 */

import { MapContainer, TileLayer, ZoomControl } from 'react-leaflet';
import { ActorMarker } from './ActorMarker';
import { useFilteredActors } from '../../store/actorStore';

/** Default center: Korean Peninsula */
const DEFAULT_CENTER: [number, number] = [36.5, 127.5];
const DEFAULT_ZOOM = 7;

/** CartoDB Dark Matter tiles — optimized for C2 dark theme */
const TILE_URL =
  'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png';
const TILE_ATTRIBUTION =
  '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> &copy; <a href="https://carto.com/">CARTO</a>';

export function CopMap() {
  const actors = useFilteredActors();

  return (
    <MapContainer
      center={DEFAULT_CENTER}
      zoom={DEFAULT_ZOOM}
      className="h-full w-full"
      zoomControl={false}
      attributionControl={true}
    >
      <ZoomControl position="bottomright" />
      <TileLayer attribution={TILE_ATTRIBUTION} url={TILE_URL} />
      {actors.map((actor) => (
        <ActorMarker key={actor.id} actor={actor} />
      ))}
    </MapContainer>
  );
}
