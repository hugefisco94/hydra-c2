interface LayerToggleProps {
  showThreatRings: boolean;
  showDmz: boolean;
  showTrails: boolean;
  crtMode: boolean;
  satelliteMode: boolean;
  onToggleThreatRings: () => void;
  onToggleDmz: () => void;
  onToggleTrails: () => void;
  onToggleCrt: () => void;
  onToggleSatellite: () => void;
}

export function LayerToggle({
  showThreatRings,
  showDmz,
  showTrails,
  crtMode,
  satelliteMode,
  onToggleThreatRings,
  onToggleDmz,
  onToggleTrails,
  onToggleCrt,
  onToggleSatellite,
}: LayerToggleProps) {
  return (
    <div className="hidden lg:flex items-center gap-1.5">
      <ToggleButton label="Threat Rings" active={showThreatRings} onClick={onToggleThreatRings} />
      <ToggleButton label="DMZ" active={showDmz} onClick={onToggleDmz} />
      <ToggleButton label="Trails" active={showTrails} onClick={onToggleTrails} />
      <ToggleButton label="CRT" active={crtMode} onClick={onToggleCrt} />
      <ToggleButton label="Satellite" active={satelliteMode} onClick={onToggleSatellite} />
    </div>
  );
}

function ToggleButton({
  label,
  active,
  onClick,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={`px-2.5 py-1 rounded-sm border text-[11px] font-mono tracking-wide transition-colors ${
        active
          ? 'bg-emerald-950/60 text-emerald-300 border-emerald-700'
          : 'bg-gray-800/80 text-gray-400 border-gray-700 hover:text-gray-200 hover:border-gray-500'
      }`}
    >
      {label}
    </button>
  );
}
