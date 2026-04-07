interface ScoreGaugeProps {
  score: number; // 0–100
  size?: number;
}

function scoreColor(score: number): string {
  if (score <= 40) return "#ef4444";
  if (score <= 70) return "#eab308";
  return "#22c55e";
}

export default function ScoreGauge({ score, size = 120 }: ScoreGaugeProps) {
  const radius = (size - 16) / 2;
  const cx = size / 2;
  const cy = size / 2;

  // Arc spans 240° (from 150° to 390°, i.e. -210° to 30° in standard coords)
  const startAngle = 150;
  const totalAngle = 240;
  const fillAngle = (score / 100) * totalAngle;

  function polarToCartesian(angleDeg: number) {
    const rad = ((angleDeg - 90) * Math.PI) / 180;
    return {
      x: cx + radius * Math.cos(rad),
      y: cy + radius * Math.sin(rad),
    };
  }

  function arcPath(start: number, end: number) {
    const s = polarToCartesian(start);
    const e = polarToCartesian(end);
    const large = end - start > 180 ? 1 : 0;
    return `M ${s.x} ${s.y} A ${radius} ${radius} 0 ${large} 1 ${e.x} ${e.y}`;
  }

  const trackPath = arcPath(startAngle, startAngle + totalAngle);
  const fillPath =
    fillAngle > 0 ? arcPath(startAngle, startAngle + fillAngle) : null;
  const color = scoreColor(score);

  return (
    <div className="flex flex-col items-center">
      <svg width={size} height={size}>
        <path
          d={trackPath}
          fill="none"
          stroke="#e5e7eb"
          strokeWidth={10}
          strokeLinecap="round"
        />
        {fillPath && (
          <path
            d={fillPath}
            fill="none"
            stroke={color}
            strokeWidth={10}
            strokeLinecap="round"
          />
        )}
        <text
          x={cx}
          y={cy + 6}
          textAnchor="middle"
          fontSize={size * 0.22}
          fontWeight="bold"
          fill={color}
        >
          {score}
        </text>
      </svg>
    </div>
  );
}
