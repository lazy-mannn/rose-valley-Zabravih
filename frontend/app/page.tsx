import { fetchDistricts } from "@/app/lib/api";
import StatCard from "./components/StatCard";
import DashboardClient from "./components/DashboardClient";

export default async function DashboardPage() {
  const { districts, totals } = await fetchDistricts().catch(() => ({
    districts: [],
    totals: { grey_bins: 0, coloured_bins: 0, active_bins: 0, monitored_bins: 0 },
  }));

  const totalBins = totals.grey_bins + totals.coloured_bins;

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh", overflow: "hidden", background: "#070D1A" }}>

      {/* ── Header ── */}
      <header style={{
        height: 52, flexShrink: 0,
        display: "flex", alignItems: "center", justifyContent: "space-between",
        padding: "0 clamp(1rem,2.5vw,1.75rem)",
        background: "rgba(7,13,26,0.98)",
        borderBottom: "1px solid rgba(96,165,250,0.1)",
        backdropFilter: "blur(12px)",
        gap: "1rem",
      }}>
        {/* Logo */}
        <div style={{ display: "flex", alignItems: "center", gap: "0.65rem" }}>
          <div style={{
            width: 28, height: 28, borderRadius: 8,
            background: "linear-gradient(135deg, #2563EB, #60A5FA)",
            display: "flex", alignItems: "center", justifyContent: "center",
            fontSize: "0.7rem", fontWeight: 900, color: "#fff",
            flexShrink: 0,
          }}>K</div>
          <span style={{ fontWeight: 800, fontSize: "0.9rem", color: "#F0F6FF", letterSpacing: "-0.01em" }}>
            Smart <span style={{ color: "#60A5FA" }}>Kazan</span> Collector
          </span>
          <span style={{ fontSize: "0.72rem", color: "#475569", fontWeight: 600, display: "none" }}>
            Sofia, Bulgaria
          </span>
        </div>

        {/* Nav */}
        <nav style={{ display: "flex", alignItems: "center", gap: "clamp(0.5rem,1.5vw,1.25rem)" }}>
          {/* Live indicator */}
          <div style={{ display: "flex", alignItems: "center", gap: "0.35rem" }}>
            <div style={{
              width: 6, height: 6, borderRadius: "50%",
              background: "#34D399",
              boxShadow: "0 0 0 2px rgba(52,211,153,0.25)",
            }} />
            <span style={{ fontSize: "0.68rem", fontWeight: 700, color: "#475569" }}>Live</span>
          </div>

          <a href="/" style={{
            fontSize: "0.78rem", fontWeight: 700, color: "#60A5FA",
            borderBottom: "2px solid #60A5FA", paddingBottom: 1,
            textDecoration: "none",
          }}>
            Dashboard
          </a>
          <a href="/pitch/" style={{
            fontSize: "0.78rem", fontWeight: 700,
            color: "#fff", background: "#2563EB",
            padding: "0.3rem 0.85rem", borderRadius: 8,
            textDecoration: "none",
          }}>
            Pitch Deck →
          </a>
        </nav>
      </header>

      {/* ── Stat strip ── */}
      <div style={{
        flexShrink: 0,
        padding: "0.65rem clamp(1rem,2.5vw,1.75rem)",
        display: "grid",
        gridTemplateColumns: "repeat(4, 1fr)",
        gap: "0.6rem",
        borderBottom: "1px solid rgba(96,165,250,0.07)",
        background: "#0A1120",
      }}>
        <StatCard
          label="Total Bins"
          value={totalBins}
          accent="sky"
          sub={`Sofia municipality`}
        />
        <StatCard
          label="Grey Waste"
          value={totals.grey_bins}
          accent="blue"
          sub="General collection"
        />
        <StatCard
          label="Coloured Bins"
          value={totals.coloured_bins}
          accent="profit"
          sub="Separate collection"
        />
        <StatCard
          label="Districts"
          value={districts.length || 24}
          accent="sky"
          sub={`${totals.active_bins.toLocaleString()} bins active`}
        />
      </div>

      {/* ── Main: sidebar + map (client component handles pan state) ── */}
      <DashboardClient districts={districts} />
    </div>
  );
}
