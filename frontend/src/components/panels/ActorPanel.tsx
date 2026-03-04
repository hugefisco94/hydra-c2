/**
 * ActorPanel — slide-out detail panel for selected actor
 */

import { useActorStore } from '../../store/actorStore';
import { createMilSymbolSvg } from '../../lib/milsymbol';
import { AFFILIATION_COLORS, DOMAIN_LABELS } from '../../types';

export function ActorPanel() {
  const selectedActor = useActorStore((s) => s.selectedActor);
  const selectActor = useActorStore((s) => s.selectActor);

  if (!selectedActor) return null;

  const svgString = createMilSymbolSvg(selectedActor.sidc, 80);
  const color = AFFILIATION_COLORS[selectedActor.affiliation] ?? '#888';

  return (
    <div className="absolute right-0 top-0 h-full w-80 bg-gray-900/95 backdrop-blur-sm border-l border-gray-700 shadow-2xl z-[1000] overflow-y-auto">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-gray-700">
        <h2 className="text-lg font-bold text-white truncate pr-2">
          {selectedActor.name}
        </h2>
        <button
          onClick={() => selectActor(null)}
          className="text-gray-400 hover:text-white transition-colors text-xl leading-none"
        >
          ✕
        </button>
      </div>

      {/* Symbol Preview */}
      <div className="flex justify-center p-6 bg-gray-800/50">
        <div dangerouslySetInnerHTML={{ __html: svgString }} />
      </div>

      {/* Details */}
      <div className="p-4 space-y-4">
        {/* Affiliation Badge */}
        <div className="flex items-center gap-2">
          <span
            className="w-3 h-3 rounded-full"
            style={{ backgroundColor: color }}
          />
          <span className="text-sm font-semibold" style={{ color }}>
            {selectedActor.affiliation}
          </span>
          <span className="text-gray-500">·</span>
          <span className="text-sm text-gray-300">
            {DOMAIN_LABELS[selectedActor.domain]} {selectedActor.domain}
          </span>
        </div>

        {/* Info Grid */}
        <div className="grid grid-cols-2 gap-3 text-sm">
          <InfoField label="ID" value={selectedActor.id} mono />
          <InfoField label="SIDC" value={selectedActor.sidc} mono />
          <InfoField
            label="Latitude"
            value={selectedActor.position.latitude.toFixed(6)}
          />
          <InfoField
            label="Longitude"
            value={selectedActor.position.longitude.toFixed(6)}
          />
          {selectedActor.position.altitude != null && (
            <InfoField
              label="Altitude"
              value={`${selectedActor.position.altitude}m`}
            />
          )}
          <InfoField
            label="Last Seen"
            value={new Date(selectedActor.last_seen).toLocaleString()}
          />
        </div>

        {/* Metadata */}
        {selectedActor.metadata &&
          Object.keys(selectedActor.metadata).length > 0 && (
            <div>
              <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
                Metadata
              </h3>
              <div className="bg-gray-800 rounded-lg p-3 text-xs font-mono text-gray-300 whitespace-pre-wrap">
                {JSON.stringify(selectedActor.metadata, null, 2)}
              </div>
            </div>
          )}
      </div>
    </div>
  );
}

function InfoField({
  label,
  value,
  mono = false,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div>
      <div className="text-xs text-gray-500 uppercase tracking-wider">
        {label}
      </div>
      <div
        className={`text-sm text-gray-200 truncate ${mono ? 'font-mono' : ''}`}
        title={value}
      >
        {value}
      </div>
    </div>
  );
}
