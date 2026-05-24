interface StatCardProps {
  label: string;
  value: string | number;
  sub?: string;
  accent?: "blue" | "sky" | "danger" | "profit" | "muted";
}

const accentColor: Record<string, string> = {
  blue:   "#3B82F6",
  sky:    "#60A5FA",
  danger: "#F87171",
  profit: "#34D399",
  muted:  "#64748B",
};

export default function StatCard({ label, value, sub, accent = "sky" }: StatCardProps) {
  return (
    <div
      style={{
        background: "#162032",
        border: "1px solid rgba(96,165,250,0.1)",
        borderRadius: 16,
        padding: "1.1rem 1.35rem",
      }}
    >
      <div
        style={{
          fontSize: "clamp(1.7rem, 2.5vw, 2.6rem)",
          fontWeight: 800,
          lineHeight: 1,
          color: accentColor[accent],
          marginBottom: "0.3rem",
        }}
      >
        {value}
      </div>
      <div style={{ fontSize: "0.8rem", fontWeight: 700, color: "#F0F6FF", marginBottom: sub ? "0.15rem" : 0 }}>
        {label}
      </div>
      {sub && (
        <div style={{ fontSize: "0.72rem", fontWeight: 600, color: "#64748B" }}>
          {sub}
        </div>
      )}
    </div>
  );
}
