/**
 * Sidebar — actor list + domain filters
 */

import { useActorStore, useFilteredActors } from '../../store/actorStore';
import type { DomainFilter } from '../../store/actorStore';
import { AFFILIATION_COLORS, DOMAIN_LABELS } from '../../types';
import type { Domain } from '../../types';

const DOMAINS: Domain[] = ['LAND', 'AIR', 'SEA', 'SUBSURFACE', 'SPACE', 'CYBER'];

export function Sidebar() {
  const sidebarOpen = useActorStore((s) => s.sidebarOpen);
  const selectedActor = useActorStore((s) => s.selectedActor);
  const selectActor = useActorStore((s) => s.selectActor);
  const domainFilters = useActorStore((s) => s.domainFilters);
  const toggleDomainFilter = useActorStore((s) => s.toggleDomainFilter);
  const actors = useFilteredActors();

  if (!sidebarOpen) return null;

  return (
    <div className="w-72 bg-gray-900 border-r border-gray-700 flex flex-col shrink-0">
      {/* Domain Filters */}
      <div className="p-3 border-b border-gray-700">
        <h2 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
          Domain Filter
        </h2>
        <div className="flex flex-wrap gap-1">
          {DOMAINS.map((domain) => (
            <DomainChip
              key={domain}
              domain={domain}
              active={domainFilters[domain as keyof DomainFilter]}
              onClick={() => toggleDomainFilter(domain as keyof DomainFilter)}
            />
          ))}
        </div>
      </div>

      {/* Actor Count */}
      <div className="px-3 py-2 border-b border-gray-800 flex items-center justify-between">
        <span className="text-xs text-gray-500 uppercase tracking-wider">
          Actors
        </span>
        <span className="text-xs font-mono font-bold text-gray-300">
          {actors.length}
        </span>
      </div>

      {/* Actor List */}
      <div className="flex-1 overflow-y-auto">
        {actors.length === 0 ? (
          <div className="p-4 text-center text-sm text-gray-600">
            No actors in view
          </div>
        ) : (
          actors.map((actor) => {
            const isSelected = selectedActor?.id === actor.id;
            const color = AFFILIATION_COLORS[actor.affiliation] ?? '#888';

            return (
              <button
                key={actor.id}
                onClick={() => selectActor(isSelected ? null : actor)}
                className={`w-full text-left px-3 py-2.5 border-b border-gray-800 transition-colors hover:bg-gray-800/60 ${
                  isSelected ? 'bg-gray-800 border-l-2 border-l-blue-500' : ''
                }`}
              >
                <div className="flex items-center gap-2">
                  <span
                    className="w-2 h-2 rounded-full shrink-0"
                    style={{ backgroundColor: color }}
                  />
                  <span className="text-sm font-medium text-gray-200 truncate">
                    {actor.name}
                  </span>
                </div>
                <div className="flex items-center gap-1.5 mt-0.5 ml-4 text-xs text-gray-500">
                  <span>{DOMAIN_LABELS[actor.domain]}</span>
                  <span>{actor.domain}</span>
                  <span className="text-gray-700">·</span>
                  <span className="font-mono text-gray-600 truncate">
                    {actor.sidc}
                  </span>
                </div>
              </button>
            );
          })
        )}
      </div>
    </div>
  );
}

function DomainChip({
  domain,
  active,
  onClick,
}: {
  domain: Domain;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={`px-2 py-0.5 rounded text-xs font-medium transition-colors ${
        active
          ? 'bg-blue-900/60 text-blue-300 border border-blue-700'
          : 'bg-gray-800 text-gray-600 border border-gray-700'
      }`}
    >
      {DOMAIN_LABELS[domain]} {domain}
    </button>
  );
}
