"use client";

import { useState } from "react";
import dynamic from "next/dynamic";
import DistrictList from "./DistrictList";
import type { District } from "@/app/lib/api";
import type { PanTarget } from "./Map";

const Map = dynamic(() => import("./Map"), { ssr: false });

export default function DashboardClient({ districts }: { districts: District[] }) {
  const [panTarget, setPanTarget] = useState<PanTarget | null>(null);

  function handleDistrictClick(d: District) {
    if (d.center_lat != null && d.center_lon != null) {
      setPanTarget({ lat: d.center_lat, lon: d.center_lon });
    }
  }

  return (
    <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>
      {/* Sidebar */}
      <aside style={{
        width: 272, flexShrink: 0,
        background: "#090F1C",
        borderRight: "1px solid rgba(96,165,250,0.07)",
        display: "flex", flexDirection: "column",
        padding: "0.9rem 0.85rem",
        overflow: "hidden",
        gap: "0.1rem",
      }}>
        <div style={{
          fontSize: "0.62rem", fontWeight: 800,
          color: "#60A5FA", letterSpacing: "0.16em",
          textTransform: "uppercase", marginBottom: "0.6rem",
          paddingBottom: "0.6rem",
          borderBottom: "1px solid rgba(96,165,250,0.08)",
        }}>
          Districts
        </div>
        <DistrictList districts={districts} onDistrictClick={handleDistrictClick} />
      </aside>

      {/* Map */}
      <main style={{ flex: 1, position: "relative", overflow: "hidden" }}>
        <Map panTarget={panTarget} />
      </main>
    </div>
  );
}
