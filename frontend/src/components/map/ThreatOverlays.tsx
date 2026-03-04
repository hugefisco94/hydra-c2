import { Circle } from 'react-leaflet';
import type { Actor } from '../../types';

interface ThreatOverlaysProps {
  actors: Actor[];
}

interface ThreatStyle {
  radiusMeters: number;
  className: string;
  dashArray: string;
}

export function ThreatOverlays({ actors }: ThreatOverlaysProps) {
  return (
    <>
      {actors.map((actor) => {
        const style = getThreatStyle(actor);
        if (!style) return null;

        return (
          <Circle
            key={`threat-${actor.id}`}
            center={[actor.position.latitude, actor.position.longitude]}
            radius={style.radiusMeters}
            pathOptions={{
              color: '#ff4d4f',
              weight: 2,
              dashArray: style.dashArray,
              fillColor: '#ff3b30',
              fillOpacity: 0.08,
              className: style.className,
            }}
          />
        );
      })}
    </>
  );
}

function getThreatStyle(actor: Actor): ThreatStyle | null {
  if (actor.affiliation !== 'HOSTILE') return null;

  const assessedType = actor.metadata?.assessed_type;
  const isTel =
    actor.name.toUpperCase() === 'VENOM-5' ||
    (typeof assessedType === 'string' && assessedType.toUpperCase().includes('TEL'));

  if (isTel) {
    return {
      radiusMeters: 80_000,
      className: 'threat-ring threat-ring--pulse',
      dashArray: '8 6',
    };
  }

  if (actor.domain === 'AIR') {
    return {
      radiusMeters: 50_000,
      className: 'threat-ring',
      dashArray: '0',
    };
  }

  if (actor.domain === 'SEA') {
    return {
      radiusMeters: 30_000,
      className: 'threat-ring',
      dashArray: '0',
    };
  }

  if (actor.domain === 'LAND') {
    return {
      radiusMeters: 15_000,
      className: 'threat-ring',
      dashArray: '8 6',
    };
  }

  return null;
}
