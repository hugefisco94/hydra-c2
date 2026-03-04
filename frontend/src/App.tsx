/**
 * HYDRA-C2 COP Dashboard — Main Application Layout
 */

import { useEffect } from 'react';
import { CopMap } from './components/map/CopMap';
import { Sidebar } from './components/layout/Sidebar';
import { ActorPanel } from './components/panels/ActorPanel';
import { SystemHealth } from './components/panels/SystemHealth';
import { useActorStore } from './store/actorStore';
import { ENDPOINTS, POLL_INTERVAL_MS } from './config/api';
import type { ActorsResponse, HealthStatus } from './types';

function App() {
  const setActors = useActorStore((s) => s.setActors);
  const setHealth = useActorStore((s) => s.setHealth);
  const toggleSidebar = useActorStore((s) => s.toggleSidebar);

  useEffect(() => {
    // Fetch system health
    const checkHealth = () => {
      fetch(ENDPOINTS.health)
        .then((r) => r.json() as Promise<HealthStatus>)
        .then(setHealth)
        .catch(() => setHealth({ status: 'error', infrastructure: 'unreachable' }));
    };

    // Fetch actors (polling for real-time updates)
    const fetchActors = () => {
      fetch(ENDPOINTS.actors)
        .then((r) => r.json() as Promise<ActorsResponse>)
        .then((data) => setActors(data.actors ?? []))
        .catch(console.error);
    };

    // Initial fetch
    checkHealth();
    fetchActors();

    // Polling intervals
    const healthInterval = setInterval(checkHealth, 10_000);
    const actorInterval = setInterval(fetchActors, POLL_INTERVAL_MS);

    return () => {
      clearInterval(healthInterval);
      clearInterval(actorInterval);
    };
  }, [setActors, setHealth]);

  return (
    <div className="h-screen flex flex-col bg-gray-950 text-white">
      {/* Header Bar */}
      <header className="h-12 flex items-center justify-between px-4 border-b border-gray-800 bg-gray-900 shrink-0">
        <div className="flex items-center gap-3">
          <button
            onClick={toggleSidebar}
            className="text-gray-400 hover:text-white transition-colors"
            title="Toggle sidebar"
          >
            ☰
          </button>
          <h1 className="text-lg font-bold tracking-tight text-white">
            HYDRA-C2
          </h1>
          <span className="text-xs text-gray-500 hidden sm:inline">
            Common Operating Picture
          </span>
        </div>
        <SystemHealth />
      </header>

      {/* Main Content */}
      <div className="flex-1 flex overflow-hidden relative">
        <Sidebar />
        <main className="flex-1 relative">
          <CopMap />
          <ActorPanel />
        </main>
      </div>
    </div>
  );
}

export default App;
