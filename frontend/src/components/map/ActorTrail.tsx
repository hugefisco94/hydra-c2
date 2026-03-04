import { useMemo } from 'react';
import { Polyline } from 'react-leaflet';
import type { Actor } from '../../types';
import { AFFILIATION_COLORS } from '../../types';

interface ActorTrailProps {
  actor: Actor;
}

interface ActorTrailsProps {
  actors: Actor[];
}

export function ActorTrail({ actor }: ActorTrailProps) {
  const points = useMemo(() => buildTrailPoints(actor), [
    actor.id,
    actor.domain,
    actor.position.latitude,
    actor.position.longitude,
    actor.last_seen,
  ]);

  const color = AFFILIATION_COLORS[actor.affiliation] ?? '#9ca3af';

  return (
    <>
      {points.slice(0, -1).map((point, index) => {
        const nextPoint = points[index + 1];
        const opacity = 0.12 + ((index + 1) / (points.length - 1)) * 0.7;

        return (
          <Polyline
            key={`trail-${actor.id}-${index}`}
            positions={[point, nextPoint]}
            pathOptions={{
              color,
              weight: actor.domain === 'AIR' ? 3 : 2,
              opacity,
              className: 'actor-trail-segment',
            }}
          />
        );
      })}
    </>
  );
}

export function ActorTrails({ actors }: ActorTrailsProps) {
  return (
    <>
      {actors.map((actor) => (
        <ActorTrail key={`trail-${actor.id}`} actor={actor} />
      ))}
    </>
  );
}

function buildTrailPoints(actor: Actor): Array<[number, number]> {
  const count = 6 + (seedFromString(actor.id) % 5);
  const current: [number, number] = [
    actor.position.latitude,
    actor.position.longitude,
  ];

  if (count < 2) {
    return [current];
  }

  const points: Array<[number, number]> = new Array(count);
  points[count - 1] = current;

  let lat = current[0];
  let lng = current[1];
  const baseSeed = seedFromString(`${actor.id}-${actor.last_seen}`);
  const bearing = (((baseSeed % 360) + 360) % 360) * (Math.PI / 180);

  for (let index = count - 2; index >= 0; index -= 1) {
    const stepSeed = baseSeed + index * 97;
    const drift = random01(stepSeed) - 0.5;

    if (actor.domain === 'AIR') {
      const distance = 0.03 + random01(stepSeed + 11) * 0.07;
      lat -= Math.cos(bearing) * distance + drift * 0.01;
      lng -= Math.sin(bearing) * distance + drift * 0.01;
    } else if (actor.domain === 'SEA') {
      const distance = 0.008 + random01(stepSeed + 23) * 0.015;
      lat -= Math.cos(bearing) * distance * 0.7 + drift * 0.003;
      lng -= Math.sin(bearing) * distance + drift * 0.004;
    } else {
      const distance = 0.002 + random01(stepSeed + 37) * 0.008;
      lat -= (random01(stepSeed + 41) - 0.5) * distance;
      lng -= (random01(stepSeed + 53) - 0.5) * distance;
    }

    points[index] = [lat, lng];
  }

  return points;
}

function seedFromString(input: string): number {
  let hash = 0;
  for (let index = 0; index < input.length; index += 1) {
    hash = (hash * 31 + input.charCodeAt(index)) | 0;
  }
  return Math.abs(hash);
}

function random01(seed: number): number {
  const x = Math.sin(seed * 12.9898) * 43758.5453;
  return x - Math.floor(x);
}
