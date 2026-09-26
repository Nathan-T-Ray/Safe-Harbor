// Decorative DNA double helix in the sage palette. Presentation only: aria-hidden, no data.
type HelixProps = {
  length: number;
  thickness: number;
  turns?: number;
  vertical?: boolean;
  drift?: boolean;
  className?: string;
};

const PALETTE = { back: '#cad2c5', mid: '#84a98c', front: '#52796f', rung: '#cad2c5' };

function strand(length: number, thickness: number, turns: number, phase: number, steps = 160) {
  const amplitude = thickness / 2 - 2;
  const points: string[] = [];
  for (let i = 0; i <= steps; i++) {
    const t = i / steps;
    const along = t * length;
    const across = thickness / 2 + amplitude * Math.sin(t * turns * 2 * Math.PI + phase);
    points.push(`${along.toFixed(1)},${across.toFixed(1)}`);
  }
  return `M${points.join(' L')}`;
}

export function Helix({ length, thickness, turns = 3, vertical = false, drift = false, className = '' }: HelixProps) {
  // Draw one extra turn so a drifting helix can loop seamlessly.
  const period = length / turns;
  const drawn = drift ? length + period : length;
  const drawnTurns = drift ? turns + 1 : turns;
  const amplitude = thickness / 2 - 2;
  const rungs = Math.round(drawnTurns * 10);
  const rungLines = Array.from({ length: rungs }, (_, index) => {
    const t = (index + 0.5) / rungs;
    const along = t * drawn;
    const angle = t * drawnTurns * 2 * Math.PI;
    const a = thickness / 2 + amplitude * Math.sin(angle);
    const b = thickness / 2 + amplitude * Math.sin(angle + Math.PI);
    const depth = Math.abs(Math.cos(angle));
    return <line key={index} x1={along} y1={a} x2={along} y2={b} stroke={PALETTE.rung} strokeWidth={1.4} strokeLinecap="round" opacity={0.35 + 0.5 * depth} />;
  });
  const width = vertical ? thickness : length;
  const height = vertical ? length : thickness;
  const body = <g className={drift ? 'helix-drift' : undefined} style={drift ? { ['--helix-period' as string]: `${period}px` } : undefined}>
    {rungLines}
    <path d={strand(drawn, thickness, drawnTurns, Math.PI)} fill="none" stroke={PALETTE.mid} strokeWidth={1.8} strokeLinecap="round" opacity={0.75} />
    <path d={strand(drawn, thickness, drawnTurns, 0)} fill="none" stroke={PALETTE.front} strokeWidth={2.2} strokeLinecap="round" />
  </g>;
  return <svg className={`helix ${className}`} width={width} height={height} viewBox={`0 0 ${width} ${height}`} aria-hidden="true" focusable="false">
    <defs><clipPath id={`helix-clip-${length}-${thickness}`}><rect width={width} height={height} /></clipPath></defs>
    <g clipPath={`url(#helix-clip-${length}-${thickness})`}>
      {vertical ? <g transform={`translate(${thickness},0) rotate(90)`}>{body}</g> : body}
    </g>
  </svg>;
}
