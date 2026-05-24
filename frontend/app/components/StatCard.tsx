interface StatCardProps {
  label: string;
  value: string | number;
  sub?: string;
  accent?: "blue" | "sky" | "danger" | "profit" | "muted" | "amber";
}

const colors: Record<string, { value: string; glow: string; badge: string }> = {
  sky:    { value: "#60A5FA", glow: "rgba(96,165,250,0.12)",  badge: "rgba(96,165,250,0.14)"  },
  blue:   { value: "#3B82F6", glow: "rgba(59,130,246,0.12)",  badge: "rgba(59,130,246,0.14)"  },
  profit: { value: "#34D399", glow: "rgba(52,211,153,0.12)",  badge: "rgba(52,211,153,0.14)"  },
  amber:  { value: "#FBBF24", glow: "rgba(251,191,36,0.12)",  badge: "rgba(251,191,36,0.14)"  },
  danger: { value: "#F87171", glow: "rgba(248,113,113,0.12)", badge: "rgba(248,113,113,0.14)" },
  muted:  { value: "#64748B", glow: "transparent",            badge: "rgba(100,116,139,0.1)"  },
};

export default function StatCard({ label, value, sub, accent = "sky" }: StatCardProps) {
  const c = colors[accent];
  return (
    <div
      style={{
        background: "#162032",
        border: `1px solid rgba(96,165,250,0.1)`,
        borderRadius: 16,
        padding: "1rem 1.25rem",
        display: "flex",
        flexDirection: "column",
        gap: "0.25rem",
        position: "relative",
        overflow: "hidden",
      }}
    >
      {/* Subtle colour wash top-right */}
      <div style={{
        position: "absolute", top: 0, right: 0,
        width: 80, height: 80,
        background: `radial-gradient(circle at top right, ${c.glow}, transparent 70%)`,
        pointerEvents: "none",
      }} />

      <div style={{
        fontSize: "clamp(1.6rem, 2.2vw, 2.4rem)",
        fontWeight: 800,
        lineHeight: 1.05,
        color: c.value,
        letterSpacing: "-0.02em",
      }}>
        {typeof value === "number" ? value.toLocaleString() : value}
      </div>

      <div style={{ fontSize: "0.78rem", fontWeight: 700, color: "#F0F6FF" }}>
        {label}
      </div>

      {sub && (
        <div style={{
          fontSize: "0.68rem", fontWeight: 600, color: "#64748B",
          display: "inline-flex", alignItems: "center", gap: "0.3rem",
        }}>
          {sub}
        </div>
      )}
    </div>
  );
}
