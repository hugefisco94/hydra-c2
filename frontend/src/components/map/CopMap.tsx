/**
 * COP (Common Operating Picture) Map Component
 * Leaflet map with OSM/CartoDB dark tiles displaying MIL-STD-2525 actors
 */

import {
  LayerGroup,
  LayersControl,
  MapContainer,
  TileLayer,
  ZoomControl,
} from 'react-leaflet';
import { ActorMarker } from './ActorMarker';
import { useFilteredActors } from '../../store/actorStore';
import { ThreatOverlays } from './ThreatOverlays';
import { DmzOverlay } from './DmzOverlay';
import { ActorTrails } from './ActorTrail';
import { ScanlineOverlay } from './ScanlineOverlay';

/** Default center: Korean Peninsula */
const DEFAULT_CENTER: [number, number] = [36.5, 127.5];
const DEFAULT_ZOOM = 7;

/** CartoDB Dark Matter tiles — optimized for C2 dark theme */
const TILE_URL =
  'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png';
const TILE_ATTRIBUTION =
  '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> &copy; <a href="https://carto.com/">CARTO</a>';
const SATELLITE_TILE_URL =
  'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}';
const SATELLITE_ATTRIBUTION =
  'Tiles &copy; Esri &mdash; Source: Esri, Maxar, Earthstar Geographics';

interface CopMapProps {
  showThreatRings: boolean;
  showDmz: boolean;
  showTrails: boolean;
  crtMode: boolean;
  satelliteMode: boolean;
  onToggleThreatRings: (next: boolean) => void;
  onToggleDmz: (next: boolean) => void;
  onToggleTrails: (next: boolean) => void;
  onToggleSatellite: (next: boolean) => void;
}

export function CopMap({
  showThreatRings,
  showDmz,
  showTrails,
  crtMode,
  satelliteMode,
  onToggleThreatRings,
  onToggleDmz,
  onToggleTrails,
  onToggleSatellite,
}: CopMapProps) {
  const actors = useFilteredActors();

  return (
    <div className="h-full w-full relative">
      <MapContainer
        center={DEFAULT_CENTER}
        zoom={DEFAULT_ZOOM}
        className="h-full w-full"
        zoomControl={false}
        attributionControl={true}
      >
        <ZoomControl position="bottomright" />
        <LayersControl position="topright">
          <LayersControl.BaseLayer checked={!satelliteMode} name="Dark Tactical">
            <TileLayer
              attribution={TILE_ATTRIBUTION}
              url={TILE_URL}
              eventHandlers={{ add: () => onToggleSatellite(false) }}
            />
          </LayersControl.BaseLayer>
          <LayersControl.BaseLayer checked={satelliteMode} name="Satellite">
            <TileLayer
              attribution={SATELLITE_ATTRIBUTION}
              url={SATELLITE_TILE_URL}
              eventHandlers={{ add: () => onToggleSatellite(true) }}
            />
          </LayersControl.BaseLayer>

          <LayersControl.Overlay checked={showThreatRings} name="Threat Rings">
            <LayerGroup
              eventHandlers={{
                add: () => onToggleThreatRings(true),
                remove: () => onToggleThreatRings(false),
              }}
            >
              <ThreatOverlays actors={actors} />
            </LayerGroup>
          </LayersControl.Overlay>

          <LayersControl.Overlay checked={showDmz} name="DMZ Geofence">
            <LayerGroup
              eventHandlers={{
                add: () => onToggleDmz(true),
                remove: () => onToggleDmz(false),
              }}
            >
              <DmzOverlay />
            </LayerGroup>
          </LayersControl.Overlay>

          <LayersControl.Overlay checked={showTrails} name="Actor Trails">
            <LayerGroup
              eventHandlers={{
                add: () => onToggleTrails(true),
                remove: () => onToggleTrails(false),
              }}
            >
              <ActorTrails actors={actors} />
            </LayerGroup>
          </LayersControl.Overlay>
        </LayersControl>

        {actors.map((actor) => (
          <ActorMarker key={actor.id} actor={actor} />
        ))}
      </MapContainer>
      <ScanlineOverlay enabled={crtMode} />
    </div>
  );
}
