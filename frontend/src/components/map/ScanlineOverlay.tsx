interface ScanlineOverlayProps {
  enabled: boolean;
}

export function ScanlineOverlay({ enabled }: ScanlineOverlayProps) {
  if (!enabled) return null;

  return (
    <div className="scanline-overlay" aria-hidden>
      <div className="scanline-sweep" />
    </div>
  );
}
