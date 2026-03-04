/**
 * SystemHealth — compact health indicator in header
 */

import { useActorStore } from '../../store/actorStore';

export function SystemHealth() {
  const health = useActorStore((s) => s.health);
  const actorCount = useActorStore((s) => s.actors.length);

  const isOperational = health?.status === 'operational';
  const statusColor = isOperational
    ? 'bg-green-500'
    : health
      ? 'bg-red-500'
      : 'bg-yellow-500 animate-pulse';

  return (
    <div className="flex items-center gap-4 text-xs">
      {/* Actor count */}
      <div className="flex items-center gap-1.5 text-gray-400">
        <span className="font-mono font-bold text-gray-200">{actorCount}</span>
        <span>actors</span>
      </div>

      {/* Divider */}
      <div className="w-px h-4 bg-gray-700" />

      {/* API status */}
      <div className="flex items-center gap-1.5">
        <div className={`w-2 h-2 rounded-full ${statusColor}`} />
        <span className="text-gray-400">
          {health?.status ?? 'connecting...'}
        </span>
      </div>

      {/* Infrastructure */}
      {health?.infrastructure && (
        <>
          <div className="w-px h-4 bg-gray-700" />
          <span className="text-gray-500">{health.infrastructure}</span>
        </>
      )}
    </div>
  );
}
