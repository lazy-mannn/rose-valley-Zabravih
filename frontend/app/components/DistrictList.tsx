"use client";

import { useState } from "react";
import type { District } from "@/app/lib/api";

export default function DistrictList({ districts }: { districts: District[] }) {
  const [search, setSearch] = useState("");

  const filtered = districts.filter(d =>
    d.district_name.toLowerCase().includes(search.toLowerCase()) ||
    String(d.district_id).includes(search)
  );

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", overflow: "hidden" }}>
      <input
        type="text"
        placeholder="Filter districts…"
        value={search}
        onChange={e => setSearch(e.target.value)}
        style={{
          background: "#162032",
          border: "1px solid rgba(96,165,250,0.18)",
          borderRadius: 10,
          color: "#F0F6FF",
          padding: "0.55rem 0.85rem",
          fontSize: "0.82rem",
          fontWeight: 600,
          outline: "none",
          marginBottom: "0.75rem",
          fontFamily: "inherit",
        }}
      />
      <div style={{ flex: 1, overflowY: "auto", display: "flex", flexDirection: "column", gap: "0.45rem" }}>
        {filtered.map(d => (
          <div
            key={d.district_id}
            style={{
              background: "#162032",
              border: "1px solid rgba(96,165,250,0.08)",
              borderRadius: 12,
              padding: "0.65rem 0.85rem",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span style={{ fontSize: "0.85rem", fontWeight: 700, color: "#F0F6FF" }}>
                {d.district_name}
              </span>
              <span style={{
                fontSize: "0.72rem", fontWeight: 800,
                color: "#60A5FA",
                background: "rgba(96,165,250,0.12)",
                borderRadius: 6, padding: "1px 7px",
              }}>
                {d.bin_count.toLocaleString()}
              </span>
            </div>
            {d.active_count > 0 && (
              <div style={{ fontSize: "0.7rem", fontWeight: 600, color: "#64748B", marginTop: "0.2rem" }}>
                {d.active_count.toLocaleString()} active
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
