"use client";

import { useState } from "react";
import type { District } from "@/app/lib/api";

export default function DistrictList({
  districts,
  onDistrictClick,
}: {
  districts: District[];
  onDistrictClick?: (d: District) => void;
}) {
  const [search, setSearch] = useState("");

  const filtered = search
    ? districts.filter(d =>
        d.district_name.toLowerCase().includes(search.toLowerCase())
      )
    : districts;

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", overflow: "hidden" }}>
      {/* Search */}
      <div style={{ position: "relative", marginBottom: "0.75rem" }}>
        <svg
          style={{
            position: "absolute", left: 10, top: "50%", transform: "translateY(-50%)",
            width: 13, height: 13, color: "#64748B", pointerEvents: "none",
          }}
          viewBox="0 0 20 20" fill="currentColor"
        >
          <path fillRule="evenodd" d="M9 3a6 6 0 100 12A6 6 0 009 3zM2 9a7 7 0 1112.32 4.906l3.387 3.387a1 1 0 01-1.414 1.414l-3.387-3.387A7 7 0 012 9z" clipRule="evenodd" />
        </svg>
        <input
          type="text"
          placeholder="Search districts…"
          value={search}
          onChange={e => setSearch(e.target.value)}
          style={{
            width: "100%",
            background: "#0d1829",
            border: "1px solid rgba(96,165,250,0.15)",
            borderRadius: 9,
            color: "#F0F6FF",
            padding: "0.5rem 0.75rem 0.5rem 2rem",
            fontSize: "0.78rem",
            fontWeight: 600,
            outline: "none",
            fontFamily: "inherit",
            boxSizing: "border-box",
          }}
        />
      </div>

      {/* Count */}
      <div style={{
        fontSize: "0.65rem", fontWeight: 800, color: "#64748B",
        letterSpacing: "0.12em", textTransform: "uppercase",
        marginBottom: "0.5rem",
      }}>
        {filtered.length} {filtered.length === 1 ? "district" : "districts"}
      </div>

      {/* List */}
      <div
        className="district-scroll"
        style={{ flex: 1, overflowY: "auto", display: "flex", flexDirection: "column", gap: "0.35rem" }}
      >
        {filtered.map(d => {
          const activePct = d.bin_count > 0 ? (d.active_count / d.bin_count) * 100 : 0;
          const hasMonitored = d.monitored_count > 0;
          return (
            <div
              key={d.district_id}
              style={{
                background: "#111827",
                border: "1px solid rgba(96,165,250,0.07)",
                borderRadius: 10,
                padding: "0.6rem 0.75rem",
                transition: "background 0.15s, border-color 0.15s",
                cursor: onDistrictClick ? "pointer" : "default",
              }}
              onClick={() => onDistrictClick?.(d)}
              onMouseEnter={e => {
                (e.currentTarget as HTMLDivElement).style.background = "#162032";
                (e.currentTarget as HTMLDivElement).style.borderColor = "rgba(96,165,250,0.18)";
              }}
              onMouseLeave={e => {
                (e.currentTarget as HTMLDivElement).style.background = "#111827";
                (e.currentTarget as HTMLDivElement).style.borderColor = "rgba(96,165,250,0.07)";
              }}
            >
              {/* Name + count */}
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.45rem" }}>
                <span style={{ fontSize: "0.8rem", fontWeight: 700, color: "#F0F6FF", lineHeight: 1.2 }}>
                  {d.district_name}
                </span>
                <span style={{
                  fontSize: "0.68rem", fontWeight: 800, color: "#60A5FA",
                  background: "rgba(96,165,250,0.1)",
                  borderRadius: 5, padding: "1px 6px",
                  flexShrink: 0, marginLeft: "0.4rem",
                }}>
                  {d.bin_count.toLocaleString()}
                </span>
              </div>

              {/* Active bar */}
              <div style={{
                height: 3, borderRadius: 2,
                background: "rgba(255,255,255,0.05)",
                overflow: "hidden", marginBottom: "0.35rem",
              }}>
                <div style={{
                  height: "100%", borderRadius: 2,
                  width: `${activePct}%`,
                  background: activePct > 80 ? "#34D399" : activePct > 40 ? "#60A5FA" : "#3B82F6",
                  transition: "width 0.4s ease",
                }} />
              </div>

              {/* Sub-line */}
              <div style={{ fontSize: "0.66rem", fontWeight: 600, color: "#475569", display: "flex", gap: "0.5rem" }}>
                <span>{d.active_count > 0 ? `${d.active_count.toLocaleString()} active` : "pending"}</span>
                {hasMonitored && (
                  <>
                    <span style={{ color: "#1e2d40" }}>·</span>
                    <span style={{ color: "#34D399" }}>{d.monitored_count} monitored</span>
                  </>
                )}
              </div>
            </div>
          );
        })}

        {filtered.length === 0 && (
          <div style={{ fontSize: "0.78rem", color: "#475569", textAlign: "center", marginTop: "2rem" }}>
            No results
          </div>
        )}
      </div>
    </div>
  );
}
