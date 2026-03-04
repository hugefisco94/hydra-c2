/**
 * HYDRA-C2 COP Dashboard — Main Application Layout
 *
 * Multi-domain Command & Control Common Operating Picture.
 * Connects to cloud backend via HTTPS for real-time actor tracking.
 */

import { useEffect, useCallback, useState } from 'react';
import { CopMap } from './components/map/CopMap';
import { Sidebar } from './components/layout/Sidebar';
import { ActorPanel } from './components/panels/ActorPanel';
import { SystemHealth } from './components/panels/SystemHealth';
import { ConnectionBanner } from './components/layout/ConnectionBanner';
import { LayerToggle } from './components/layout/LayerToggle';
import { useActorStore } from './store/actorStore';
import { ENDPOINTS, POLL_INTERVAL_MS, apiFetch } from './config/api';
import type { ActorsResponse, HealthStatus } from './types';

function App() {
  const setActors = useActorStore((s) => s.setActors);
  const setHealth = useActorStore((s) => s.setHealth);
  const setConnectionState = useActorStore((s) => s.setConnectionState);
  const toggleSidebar = useActorStore((s) => s.toggleSidebar);

  const [showThreatRings, setShowThreatRings] = useState(true);
  const [showDmz, setShowDmz] = useState(true);
  const [showTrails, setShowTrails] = useState(true);
  const [crtMode, setCrtMode] = useState(false);
  const [satelliteMode, setSatelliteMode] = useState(false);

  const checkHealth = useCallback(() => {
    apiFetch<HealthStatus>(ENDPOINTS.health)
      .then((data) => {
        setHealth(data);
        setConnectionState('connected');
      })
      .catch(() => {
        setHealth({ status: 'error', infrastructure: 'unreachable' });
        setConnectionState('disconnected');
      });
  }, [setHealth, setConnectionState]);

  const fetchActors = useCallback(() => {
    apiFetch<ActorsResponse>(ENDPOINTS.actors)
      .then((data) => {
        setActors(data.actors ?? []);
        setConnectionState('connected');
      })
      .catch(() => {
        // Keep existing actors on transient failures
        setConnectionState('disconnected');
      });
  }, [setActors, setConnectionState]);

  useEffect(() => {
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
  }, [checkHealth, fetchActors]);

  return (
    <div className="h-screen flex flex-col bg-gray-950 text-white">
      {/* Connection Status Banner */}
      <ConnectionBanner />

      {/* Header Bar */}
      <header className="h-12 flex items-center justify-between px-4 border-b border-gray-800 bg-gray-900/95 backdrop-blur-sm shrink-0 z-50">
        <div className="flex items-center gap-3">
          <button
            onClick={toggleSidebar}
            className="text-gray-400 hover:text-white transition-colors text-lg"
            title="Toggle sidebar"
          >
            ☰
          </button>
          <h1 className="text-lg font-bold tracking-tight">
            <span style={{ color: '#39ff14' }}>HYDRA</span>
            <span className="text-white">-C2</span>
          </h1>
          <span className="text-xs text-gray-500 hidden sm:inline font-mono tracking-widest">
            MULTI-DOMAIN C2 // COP
          </span>
        </div>
        <div className="flex items-center gap-3">
          <LayerToggle
            showThreatRings={showThreatRings}
            showDmz={showDmz}
            showTrails={showTrails}
            crtMode={crtMode}
            satelliteMode={satelliteMode}
            onToggleThreatRings={() => setShowThreatRings((prev) => !prev)}
            onToggleDmz={() => setShowDmz((prev) => !prev)}
            onToggleTrails={() => setShowTrails((prev) => !prev)}
            onToggleCrt={() => setCrtMode((prev) => !prev)}
            onToggleSatellite={() => setSatelliteMode((prev) => !prev)}
          />
          <SystemHealth />
        </div>
      </header>

      {/* Main Content */}
      <div className="flex-1 flex overflow-hidden relative">
        <Sidebar />
        <main className="flex-1 relative">
          <CopMap
            showThreatRings={showThreatRings}
            showDmz={showDmz}
            showTrails={showTrails}
            crtMode={crtMode}
            satelliteMode={satelliteMode}
            onToggleThreatRings={setShowThreatRings}
            onToggleDmz={setShowDmz}
            onToggleTrails={setShowTrails}
            onToggleSatellite={setSatelliteMode}
          />
          <ActorPanel />
        </main>
      </div>
    </div>
  );
}

export default App;
