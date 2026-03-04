/**
 * ActorMarker — renders MIL-STD-2525 symbol on map via milsymbol
 */

import { useMemo } from 'react';
import { Marker, Popup } from 'react-leaflet';
import type { Actor } from '../../types';
import { AFFILIATION_COLORS, DOMAIN_LABELS } from '../../types';
import { createMilSymbolIcon } from '../../lib/milsymbol';
import { useActorStore } from '../../store/actorStore';

interface Props {
  actor: Actor;
}

export function ActorMarker({ actor }: Props) {
  const selectActor = useActorStore((s) => s.selectActor);

  const icon = useMemo(
    () => createMilSymbolIcon(actor.sidc, { size: 32 }),
    [actor.sidc],
  );

  const affiliationColor = AFFILIATION_COLORS[actor.affiliation] ?? '#888';

  return (
    <Marker
      position={[actor.position.latitude, actor.position.longitude]}
      icon={icon}
      eventHandlers={{
        click: () => selectActor(actor),
      }}
    >
      <Popup>
        <div className="min-w-[180px] text-sm font-sans">
          <div className="font-bold text-base mb-1">{actor.name}</div>
          <div className="flex items-center gap-2 mb-1">
            <span
              className="inline-block w-2 h-2 rounded-full"
              style={{ backgroundColor: affiliationColor }}
            />
            <span>{actor.affiliation}</span>
            <span className="text-gray-400">·</span>
            <span>
              {DOMAIN_LABELS[actor.domain]} {actor.domain}
            </span>
          </div>
          <div className="text-xs text-gray-500 font-mono">
            SIDC: {actor.sidc}
          </div>
          <div className="text-xs text-gray-500">
            {actor.position.latitude.toFixed(4)}°N,{' '}
            {actor.position.longitude.toFixed(4)}°E
            {actor.position.altitude != null &&
              ` · ${actor.position.altitude}m`}
          </div>
          <div className="text-xs text-gray-400 mt-1">
            Last: {new Date(actor.last_seen).toLocaleString()}
          </div>
        </div>
      </Popup>
    </Marker>
  );
}
