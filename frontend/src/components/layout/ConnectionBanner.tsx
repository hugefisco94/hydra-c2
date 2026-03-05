/**
 * ConnectionBanner — shows connection status when backend is unreachable
 */

import { useActorStore } from '../../store/actorStore';
import { API_BASE_URL } from '../../config/api';

export function ConnectionBanner() {
  const connectionState = useActorStore((s) => s.connectionState);

  if (connectionState === 'connected') return null;

  const isConnecting = connectionState === 'connecting';

  return (
    <div
      className={`px-4 py-2 text-xs font-mono text-center shrink-0 ${
        isConnecting
          ? 'bg-yellow-900/60 text-yellow-300 border-b border-yellow-800'
          : 'bg-red-900/60 text-red-300 border-b border-red-800'
      }`}
    >
      <span className={isConnecting ? 'animate-pulse' : ''}>
        {isConnecting ? '⟳' : '⚠'}{' '}
        {isConnecting
          ? `CONNECTING TO C2 BACKEND: ${API_BASE_URL} ...`
          : `C2 BACKEND UNREACHABLE: ${API_BASE_URL} — retrying every 10s`}
      </span>
    </div>
  );
}
