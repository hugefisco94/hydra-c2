import { useActorStore, useFilteredActors } from '../../store/actorStore';
import type { DomainFilter } from '../../store/actorStore';
import { AFFILIATION_COLORS, DOMAIN_LABELS, THREAT_LEVEL_COLORS } from '../../types';
import type { Affiliation, Domain } from '../../types';

const DOMAINS: Domain[] = ['LAND', 'AIR', 'SEA', 'SUBSURFACE', 'SPACE', 'CYBER'];
const AFFILIATIONS: Affiliation[] = ['HOSTILE', 'FRIEND', 'NEUTRAL', 'UNKNOWN'];

export function Sidebar() {
  const sidebarOpen = useActorStore((s) => s.sidebarOpen);
  const allActors = useActorStore((s) => s.actors);
  const analyticsOverview = useActorStore((s) => s.analyticsOverview);
  const threatAssessment = useActorStore((s) => s.threatAssessment);
  const osintFeeds = useActorStore((s) => s.osintFeeds);
  const causalAssessment = useActorStore((s) => s.causalAssessment);
  const selectedActor = useActorStore((s) => s.selectedActor);
  const selectActor = useActorStore((s) => s.selectActor);
  const domainFilters = useActorStore((s) => s.domainFilters);
  const toggleDomainFilter = useActorStore((s) => s.toggleDomainFilter);
  const actors = useFilteredActors();

  const byAffiliation = analyticsOverview?.by_affiliation ?? {};
  const byDomain = analyticsOverview?.by_domain ?? {};
  const forceRatio = analyticsOverview?.force_ratio?.ratio ?? 0;
  const formattedRatio = Number.isFinite(forceRatio) && forceRatio > 0
    ? `${forceRatio.toFixed(2)}:1`
    : 'N/A';

  const topThreats = [...(threatAssessment?.assessments ?? [])]
    .sort((a, b) => b.composite_score - a.composite_score)
    .slice(0, 5);

  const threatBadges = {
    critical: threatAssessment?.critical_count ?? 0,
    high: threatAssessment?.high_count ?? 0,
  };

  if (!sidebarOpen) return null;

  return (
    <div className="w-72 bg-gray-900 border-r border-gray-700 flex flex-col shrink-0">
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

      <div className="p-3 border-b border-gray-800 space-y-3 bg-gray-950/60">
        <div className="flex items-center justify-between">
          <h3 className="text-[11px] font-semibold text-gray-400 uppercase tracking-[0.18em]">
            Force Status
          </h3>
          <span className="text-[10px] text-emerald-300 font-mono flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 live-blink" />
            LIVE
          </span>
        </div>

        <div className="flex items-end justify-between">
          <div>
            <div className="text-[10px] text-gray-500 uppercase tracking-[0.16em]">Tracks</div>
            <div className="text-xl font-mono text-gray-100 font-semibold leading-none">
              {analyticsOverview?.total_tracks ?? allActors.length}
            </div>
          </div>
          <div className="force-ratio-box">
            <div className="text-[10px] text-gray-500 uppercase tracking-[0.16em]">Force Ratio</div>
            <div className="force-ratio-value">{formattedRatio}</div>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-1.5 text-[11px] font-mono">
          {AFFILIATIONS.map((affiliation) => (
            <div key={affiliation} className="flex items-center justify-between px-2 py-1 rounded bg-gray-900/70 border border-gray-800">
              <span style={{ color: AFFILIATION_COLORS[affiliation] }}>{affiliation}</span>
              <span className="text-gray-200">{byAffiliation[affiliation] ?? 0}</span>
            </div>
          ))}
        </div>

        <div className="grid grid-cols-2 gap-1.5 text-[11px]">
          {['LAND', 'AIR', 'SEA', 'CYBER'].map((domain) => (
            <div key={domain} className="flex items-center justify-between px-2 py-1 rounded border border-gray-800 bg-gray-900/40">
              <span className="text-gray-400 font-mono">{domain}</span>
              <span className="text-gray-200 font-mono">{byDomain[domain] ?? 0}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="p-3 border-b border-gray-800 space-y-2.5 bg-gray-950/70">
        <div className="flex items-center justify-between">
          <h3 className="text-[11px] font-semibold text-gray-400 uppercase tracking-[0.18em]">
            Threat Board
          </h3>
          <div className="flex items-center gap-1.5 text-[10px] font-mono">
            <span className="px-1.5 py-0.5 rounded bg-red-950/50 border border-red-700/40 threat-critical">
              CRIT {threatBadges.critical}
            </span>
            <span className="px-1.5 py-0.5 rounded bg-orange-950/50 border border-orange-700/40 threat-high">
              HIGH {threatBadges.high}
            </span>
          </div>
        </div>

        {topThreats.length === 0 ? (
          <div className="text-xs text-gray-600 font-mono py-2">No threat tracks</div>
        ) : (
          <div className="space-y-2">
            {topThreats.map((threat) => {
              const classificationClass = `threat-${threat.classification.toLowerCase()}`;
              const scoreWidth = `${Math.max(0, Math.min(1, threat.composite_score)) * 100}%`;
              const domainLabel = threat.domain as Domain;
              const domainIcon = DOMAIN_LABELS[domainLabel] ?? '•';

              return (
                <div key={threat.actor_id} className="rounded border border-gray-800 bg-gray-900/50 px-2 py-1.5">
                  <div className="flex items-center justify-between gap-2">
                    <span className={`text-xs font-semibold truncate ${classificationClass}`}>{threat.name}</span>
                    <span className="text-[10px] text-gray-400 font-mono">
                      {domainIcon} {threat.domain}
                    </span>
                  </div>
                  <div className="threat-score-track mt-1">
                    <div className={`threat-score-fill ${classificationClass}`} style={{ width: scoreWidth }} />
                  </div>
                  <div className="mt-1 text-[10px] text-gray-500 font-mono flex items-center justify-between">
                    <span>SCORE {(threat.composite_score ?? 0).toFixed(3)}</span>
                    <span>TEHRAN {(threat.distance_to_tehran_km ?? 0).toFixed(1)}km</span>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
      {/* OSINT Intelligence Panel */}
      <div className="p-3 border-b border-gray-800 space-y-2.5 bg-gray-950/80">
        <div className="flex items-center justify-between">
          <h3 className="text-[11px] font-semibold text-gray-400 uppercase tracking-[0.18em]">
            OSINT Intel
          </h3>
          {causalAssessment && (
            <span
              className="text-[10px] font-mono px-1.5 py-0.5 rounded border"
              style={{
                color: THREAT_LEVEL_COLORS[causalAssessment.threat_level] ?? '#6b7280',
                borderColor: `${THREAT_LEVEL_COLORS[causalAssessment.threat_level] ?? '#6b7280'}66`,
                backgroundColor: `${THREAT_LEVEL_COLORS[causalAssessment.threat_level] ?? '#6b7280'}1a`,
              }}
            >
              {causalAssessment.threat_level}
            </span>
          )}
        </div>

        {/* Bayesian Composite Score */}
        {causalAssessment && (
          <div className="space-y-1.5">
            <div className="flex items-center justify-between text-[10px] font-mono">
              <span className="text-gray-500">COMPOSITE</span>
              <span className="text-gray-200 font-semibold">{(causalAssessment.composite_score ?? 0).toFixed(3)}</span>
            </div>
            <div className="h-1.5 bg-gray-800 rounded-full overflow-hidden">
              <div
                className="h-full rounded-full transition-all"
                style={{
                  width: `${Math.min(100, causalAssessment.composite_score * 100)}%`,
                  backgroundColor: THREAT_LEVEL_COLORS[causalAssessment.threat_level] ?? '#6b7280',
                }}
              />
            </div>

            {/* Causal Factors */}
            <div className="grid grid-cols-2 gap-1 text-[10px] font-mono">
              <div className="px-1.5 py-1 rounded bg-gray-900/60 border border-gray-800">
                <div className="text-gray-500">ESCALATION</div>
                <div className="text-amber-300 font-semibold">{((causalAssessment.escalation_probability ?? 0) * 100).toFixed(0)}%</div>
              </div>
              <div className="px-1.5 py-1 rounded bg-gray-900/60 border border-gray-800">
                <div className="text-gray-500">MIL POSTURE</div>
                <div className="text-blue-300 font-semibold">{((causalAssessment.military_posture_index ?? 0) * 100).toFixed(0)}%</div>
              </div>
              <div className="px-1.5 py-1 rounded bg-gray-900/60 border border-gray-800">
                <div className="text-gray-500">GDELT TONE</div>
                <div className="text-gray-200">{(causalAssessment.causal_factors?.gdelt_tone_avg ?? 0).toFixed(2)}</div>
              </div>
              <div className="px-1.5 py-1 rounded bg-gray-900/60 border border-gray-800">
                <div className="text-gray-500">AIR DENSITY</div>
                <div className="text-gray-200">{(causalAssessment.causal_factors?.aircraft_density ?? 0).toFixed(1)}</div>
              </div>
            </div>

            {/* Evidence Summary */}
            <div className="flex items-center justify-between text-[10px] font-mono">
              <span className="text-gray-500">GDELT</span>
              <span className="text-gray-300">{causalAssessment.evidence_summary?.gdelt_articles ?? 0} articles</span>
            </div>
            <div className="flex items-center justify-between text-[10px] font-mono">
              <span className="text-gray-500">OPENSKY</span>
              <span className="text-gray-300">{causalAssessment.evidence_summary?.military_flights ?? 0} mil flights</span>
            </div>
          </div>
        )}

        {/* OSINT Feed Breakdown */}
        {osintFeeds && (
          <div className="space-y-1">
            <div className="text-[10px] text-gray-500 uppercase tracking-[0.14em]">Feed Activity</div>
            <div className="flex gap-1 text-[10px] font-mono">
              {Object.entries(osintFeeds.breakdown).map(([key, count]) => (
                <div key={key} className="flex-1 text-center py-1 rounded border border-gray-800 bg-gray-900/40">
                  <div className="text-gray-400">{key}</div>
                  <div className="text-gray-200 font-semibold">{count}</div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

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
