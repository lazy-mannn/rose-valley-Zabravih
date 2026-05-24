"use client";

import type { FillRecord } from "@/app/lib/api";

function formatDate(iso: string): string {
  return new Intl.DateTimeFormat("en-GB", {
    timeZone: "Europe/Sofia",
    day: "numeric", month: "short",
    hour: "2-digit", minute: "2-digit",
  }).format(new Date(iso));
}

function fillColor(level: number): string {
  if (level >= 100) return "#F87171";
  if (level >= 80) return "#FB923C";
  if (level >= 60) return "#FBBF24";
  return "#34D399";
}

export default function FillChart({ history }: { history: FillRecord[] }) {
  if (history.length === 0) {
    return (
      <div style={{
        background: "rgba(255,255,255,0.03)",
        border: "1px solid rgba(96,165,250,0.1)",
        borderRadius: 12,
        padding: "2rem",
        textAlign: "center",
        color: "#475569",
        fontSize: "0.82rem",
        fontWeight: 600,
      }}>
        No monitoring data yet
        <div style={{ fontSize: "0.72rem", marginTop: 6, color: "#334155" }}>
          Fill records appear once a truck RPi scans this bin
        </div>
      </div>
    );
  }

  const W = 520;
  const H = 160;
  const PAD = { top: 12, right: 12, bottom: 32, left: 36 };
  const cW = W - PAD.left - PAD.right;
  const cH = H - PAD.top - PAD.bottom;

  const times = history.map(r => new Date(r.timestamp).getTime());
  const minT = Math.min(...times);
  const maxT = Math.max(...times);
  const tRange = maxT - minT || 1;

  const xOf = (t: number) => (t - minT) / tRange * cW;
  const yOf = (v: number) => cH - Math.min(v, 100) / 100 * cH;

  const pts = history.map(r => ({
    x: xOf(new Date(r.timestamp).getTime()),
    y: yOf(r.fill_level),
    fill: r.fill_level,
  }));

  const pathD = pts.map((p, i) => `${i === 0 ? "M" : "L"}${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(" ");

  // Y-axis gridlines at 0, 25, 50, 75, 100
  const yTicks = [0, 25, 50, 75, 100];

  // X-axis: pick up to 4 evenly spaced labels
  const xTickIdxs = history.length <= 4
    ? history.map((_, i) => i)
    : [0, Math.floor(history.length / 3), Math.floor(history.length * 2 / 3), history.length - 1];

  const lastFill = history[history.length - 1].fill_level;
  const lineColor = fillColor(lastFill);

  return (
    <div style={{
      background: "rgba(255,255,255,0.02)",
      border: "1px solid rgba(96,165,250,0.1)",
      borderRadius: 12,
      padding: "1rem 1.25rem",
    }}>
      <div style={{ fontSize: "0.68rem", fontWeight: 800, color: "#60A5FA", letterSpacing: "0.14em", textTransform: "uppercase", marginBottom: "0.75rem" }}>
        Fill history · last {history.length} records
      </div>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        style={{ width: "100%", display: "block", overflow: "visible" }}
      >
        <g transform={`translate(${PAD.left},${PAD.top})`}>
          {/* Gridlines */}
          {yTicks.map(v => (
            <g key={v}>
              <line
                x1={0} y1={yOf(v)} x2={cW} y2={yOf(v)}
                stroke="rgba(255,255,255,0.05)" strokeWidth={1}
              />
              <text
                x={-6} y={yOf(v)} textAnchor="end" dominantBaseline="middle"
                fill="#475569" fontSize={9} fontFamily="Manrope,system-ui,sans-serif" fontWeight={600}
              >
                {v}%
              </text>
            </g>
          ))}

          {/* Area fill */}
          <defs>
            <linearGradient id="chartFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={lineColor} stopOpacity={0.18} />
              <stop offset="100%" stopColor={lineColor} stopOpacity={0} />
            </linearGradient>
          </defs>
          <path
            d={`${pathD} L${pts[pts.length - 1].x.toFixed(1)},${cH} L0,${cH} Z`}
            fill="url(#chartFill)"
          />

          {/* Line */}
          <path d={pathD} fill="none" stroke={lineColor} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />

          {/* Dots */}
          {pts.map((p, i) => (
            <circle key={i} cx={p.x} cy={p.y} r={3} fill={fillColor(p.fill)} stroke="#070D1A" strokeWidth={1.5} />
          ))}

          {/* X-axis labels */}
          {xTickIdxs.map(idx => (
            <text
              key={idx}
              x={pts[idx].x} y={cH + 14}
              textAnchor="middle"
              fill="#475569" fontSize={8.5} fontFamily="Manrope,system-ui,sans-serif" fontWeight={600}
            >
              {formatDate(history[idx].timestamp)}
            </text>
          ))}
        </g>
      </svg>
    </div>
  );
}
