import { notFound } from "next/navigation";
import { fetchBinDetail } from "@/app/lib/api";
import FillChart from "./FillChart";

function formatDate(isoStr: string | null): string {
  if (!isoStr) return "—";
  return new Intl.DateTimeFormat("en-GB", {
    timeZone: "Europe/Sofia",
    day: "numeric", month: "short", year: "numeric",
    hour: "2-digit", minute: "2-digit",
  }).format(new Date(isoStr));
}

function wasteLabel(type: string): { text: string; color: string; bg: string } {
  const map: Record<string, { text: string; color: string; bg: string }> = {
    general:   { text: "General waste",  color: "#94A3B8", bg: "rgba(148,163,184,0.12)" },
    recycling: { text: "Recycling",       color: "#34D399", bg: "rgba(52,211,153,0.12)" },
    glass:     { text: "Glass",           color: "#FBBF24", bg: "rgba(251,191,36,0.12)" },
    organic:   { text: "Organic",         color: "#86EFAC", bg: "rgba(134,239,172,0.12)" },
  };
  return map[type] ?? { text: type, color: "#94A3B8", bg: "rgba(148,163,184,0.12)" };
}

export default async function BinDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id: idStr } = await params;
  const id = parseInt(idStr, 10);
  if (isNaN(id)) notFound();

  const bin = await fetchBinDetail(id);
  if (!bin) notFound();

  const isGrey = bin.waste_type === "general";
  const wl = wasteLabel(bin.waste_type);
  const isActive = bin.bin_status === "active";

  return (
    <div style={{ minHeight: "100vh", background: "#070D1A", fontFamily: "Manrope, system-ui, sans-serif" }}>

      {/* Header */}
      <header style={{
        height: 52, display: "flex", alignItems: "center", justifyContent: "space-between",
        padding: "0 clamp(1rem,2.5vw,1.75rem)",
        background: "rgba(7,13,26,0.98)",
        borderBottom: "1px solid rgba(96,165,250,0.1)",
        backdropFilter: "blur(12px)",
        position: "sticky", top: 0, zIndex: 50,
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: "0.65rem" }}>
          <a href="/" style={{ textDecoration: "none", display: "flex", alignItems: "center", gap: "0.65rem" }}>
            <div style={{
              width: 28, height: 28, borderRadius: 8,
              background: "linear-gradient(135deg, #2563EB, #60A5FA)",
              display: "flex", alignItems: "center", justifyContent: "center",
              fontSize: "0.7rem", fontWeight: 900, color: "#fff",
            }}>K</div>
            <span style={{ fontWeight: 800, fontSize: "0.9rem", color: "#F0F6FF", letterSpacing: "-0.01em" }}>
              Smart <span style={{ color: "#60A5FA" }}>Kazan</span> Collector
            </span>
          </a>
        </div>
        <a href="/" style={{
          fontSize: "0.78rem", fontWeight: 700, color: "#60A5FA",
          textDecoration: "none", display: "flex", alignItems: "center", gap: 4,
        }}>
          ← Back to map
        </a>
      </header>

      {/* Content */}
      <main style={{ maxWidth: 640, margin: "0 auto", padding: "2rem 1.25rem" }}>

        {/* ID + badges */}
        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: "1.25rem", gap: "1rem" }}>
          <div>
            <div style={{ fontSize: "0.65rem", fontWeight: 800, color: "#60A5FA", letterSpacing: "0.16em", textTransform: "uppercase", marginBottom: 4 }}>
              Bin details
            </div>
            <h1 style={{ margin: 0, fontSize: "1.6rem", fontWeight: 800, color: "#F0F6FF", letterSpacing: "-0.02em" }}>
              Bin #{bin.id}
            </h1>
          </div>
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap", justifyContent: "flex-end", paddingTop: 4 }}>
            <span style={{ fontSize: "0.7rem", fontWeight: 700, padding: "3px 10px", borderRadius: 6, background: wl.bg, color: wl.color }}>
              {wl.text}
            </span>
            <span style={{
              fontSize: "0.7rem", fontWeight: 700, padding: "3px 10px", borderRadius: 6,
              background: isActive ? "rgba(52,211,153,0.12)" : "rgba(100,116,139,0.12)",
              color: isActive ? "#34D399" : "#64748B",
            }}>
              {bin.bin_status}
            </span>
          </div>
        </div>

        {/* Location card */}
        <div style={{
          background: "rgba(255,255,255,0.03)",
          border: "1px solid rgba(96,165,250,0.1)",
          borderRadius: 12,
          padding: "1rem 1.25rem",
          marginBottom: "1rem",
        }}>
          <div style={{ fontSize: "0.62rem", fontWeight: 800, color: "#60A5FA", letterSpacing: "0.14em", textTransform: "uppercase", marginBottom: "0.65rem" }}>
            Location
          </div>
          {bin.public_number && (
            <div style={{ fontSize: "0.88rem", fontWeight: 700, color: "#F0F6FF", marginBottom: 4 }}>
              {bin.public_number}
            </div>
          )}
          <div style={{ fontSize: "0.78rem", color: "#94A3B8", fontWeight: 600, marginBottom: 8 }}>
            {bin.district_name || "Unknown district"}
          </div>
          <div style={{ fontSize: "0.7rem", color: "#475569", fontWeight: 600, fontVariantNumeric: "tabular-nums" }}>
            {bin.latitude.toFixed(5)}, {bin.longitude.toFixed(5)}
            <a
              href={`https://www.google.com/maps?q=${bin.latitude},${bin.longitude}`}
              target="_blank"
              rel="noopener noreferrer"
              style={{ marginLeft: 10, color: "#60A5FA", textDecoration: "none" }}
            >
              Open in Maps ↗
            </a>
          </div>
        </div>

        {/* Grey bin details */}
        {isGrey && (
          <div style={{
            background: "rgba(255,255,255,0.03)",
            border: "1px solid rgba(96,165,250,0.1)",
            borderRadius: 12,
            padding: "1rem 1.25rem",
            marginBottom: "1rem",
          }}>
            <div style={{ fontSize: "0.62rem", fontWeight: 800, color: "#60A5FA", letterSpacing: "0.14em", textTransform: "uppercase", marginBottom: "0.65rem" }}>
              Container info
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "0.75rem" }}>
              {bin.capacity_volume != null && (
                <div>
                  <div style={{ fontSize: "0.65rem", fontWeight: 700, color: "#475569", marginBottom: 2 }}>Capacity</div>
                  <div style={{ fontSize: "0.95rem", fontWeight: 800, color: "#F0F6FF" }}>
                    {Math.round(bin.capacity_volume * 1000)} L
                  </div>
                </div>
              )}
              <div>
                <div style={{ fontSize: "0.65rem", fontWeight: 700, color: "#475569", marginBottom: 2 }}>Bins here</div>
                <div style={{ fontSize: "0.95rem", fontWeight: 800, color: "#F0F6FF" }}>{bin.bin_count}</div>
              </div>
              {bin.last_cleaned && (
                <div>
                  <div style={{ fontSize: "0.65rem", fontWeight: 700, color: "#475569", marginBottom: 2 }}>Last cleaned</div>
                  <div style={{ fontSize: "0.95rem", fontWeight: 800, color: "#34D399" }}>
                    {formatDate(bin.last_cleaned)}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Fill chart */}
        <FillChart history={bin.fill_history} />

      </main>
    </div>
  );
}
