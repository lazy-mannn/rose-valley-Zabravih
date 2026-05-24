import { fetchDistricts } from "@/app/lib/api";
import StatCard from "./components/StatCard";
import DistrictList from "./components/DistrictList";
import MapWrapper from "./components/MapWrapper";

export default async function DashboardPage() {
  let districts = await fetchDistricts().catch(() => []);

  const totalBins   = districts.reduce((s, d) => s + d.bin_count, 0);
  const activeBins  = districts.reduce((s, d) => s + d.active_count, 0);
  const monitored   = districts.reduce((s, d) => s + d.monitored_count, 0);

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh", overflow: "hidden" }}>

      {/* ── Top bar ── */}
      <header style={{
        height: 60, flexShrink: 0,
        background: "rgba(7,13,26,0.97)",
        borderBottom: "1px solid rgba(96,165,250,0.14)",
        display: "flex", alignItems: "center", justifyContent: "space-between",
        padding: "0 clamp(1rem,3vw,2rem)", gap: "1rem",
        backdropFilter: "blur(12px)",
      }}>
        <span style={{ fontWeight: 800, fontSize: "clamp(0.9rem,1.2vw,1.1rem)", color: "#F0F6FF" }}>
          Smart <span style={{ color: "#60A5FA" }}>Kazan</span> Collector
        </span>
        <nav style={{ display: "flex", gap: "clamp(0.5rem,1.5vw,1.25rem)", alignItems: "center" }}>
          <a href="/" style={{ fontSize: "0.82rem", fontWeight: 700, color: "#60A5FA",
            borderBottom: "2px solid #60A5FA", paddingBottom: 2, textDecoration: "none" }}>
            Dashboard
          </a>
          <a href="/pitch/" style={{
            fontSize: "0.82rem", fontWeight: 700,
            color: "#fff", background: "#2563EB",
            padding: "0.35rem 0.9rem", borderRadius: 8,
            textDecoration: "none",
          }}>
            Pitch Deck →
          </a>
        </nav>
      </header>

      {/* ── Stat strip ── */}
      <div style={{
        flexShrink: 0, padding: "0.85rem clamp(1rem,2.5vw,1.75rem)",
        display: "grid",
        gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
        gap: "0.75rem",
        borderBottom: "1px solid rgba(96,165,250,0.08)",
        background: "#0F172A",
      }}>
        <StatCard label="Total Bins"   value={totalBins.toLocaleString()}   accent="sky"    sub="Sofia municipality" />
        <StatCard label="Active Bins"  value={activeBins.toLocaleString()}  accent="blue"   sub="confirmed by Sofia API" />
        <StatCard label="Monitored"    value={monitored.toLocaleString()}    accent="profit" sub="have fill records" />
        <StatCard label="Districts"    value={districts.length}              accent="sky"    sub="24 total" />
      </div>

      {/* ── Main content: sidebar + map ── */}
      <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>

        {/* Sidebar */}
        <aside style={{
          width: 260, flexShrink: 0,
          background: "#0F172A",
          borderRight: "1px solid rgba(96,165,250,0.08)",
          display: "flex", flexDirection: "column",
          padding: "1rem",
          overflow: "hidden",
        }}>
          <div style={{
            fontSize: "0.7rem", fontWeight: 800,
            color: "#60A5FA", letterSpacing: "0.18em",
            textTransform: "uppercase", marginBottom: "0.75rem",
          }}>
            Districts
          </div>
          <DistrictList districts={districts} />
        </aside>

        {/* Map */}
        <main style={{ flex: 1, position: "relative", overflow: "hidden" }}>
          <MapWrapper />
        </main>
      </div>
    </div>
  );
}
