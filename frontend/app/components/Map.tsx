"use client";

import { useEffect, useRef, useState } from "react";
import type { Map as LeafletMap, Layer } from "leaflet";
import type { Cluster, BinFeature } from "@/app/lib/api";
import { fetchClusters, fetchViewport } from "@/app/lib/api";

export interface PanTarget { lat: number; lon: number }

const SOFIA = { lat: 42.698, lng: 23.324 };
const VIEWPORT_ZOOM = 13;  // clusters → individual markers
const EXPAND_ZOOM   = 16;  // single dot → compound dots for bin_count > 1

// Actual bin colors — match the physical bin colour in Sofia
function wasteColor(wasteType: string): string {
  if (wasteType === "paper")     return "#818CF8"; // blue bin
  if (wasteType === "recycling") return "#FBBF24"; // yellow bin
  if (wasteType === "glass")     return "#34D399"; // green bin
  return "#475569";                                // grey / unknown
}

function clusterColor(count: number): string {
  if (count > 1500) return "#2563EB";
  if (count > 500)  return "#3B82F6";
  if (count > 100)  return "#60A5FA";
  return "#93C5FD";
}

function binColor(fill: number | null, wasteType?: string): string {
  if (fill === null) return wasteColor(wasteType ?? "");
  if (fill >= 100) return "#F87171";
  if (fill >= 80)  return "#FB923C";
  if (fill >= 60)  return "#FBBF24";
  return "#34D399";
}

function fillBar(fill: number | null, color: string): string {
  const pct = Math.min(fill ?? 0, 100);
  return `
    <div style="height:4px;background:rgba(255,255,255,0.07);border-radius:2px;overflow:hidden;margin-top:4px">
      <div style="height:100%;width:${pct}%;background:${color};border-radius:2px"></div>
    </div>`;
}

function wasteLabel(type: string): string {
  const map: Record<string, string> = {
    general:   "General waste",
    paper:     "Paper",
    recycling: "Recycling",
    glass:     "Glass",
    organic:   "Organic",
  };
  return map[type] ?? type;
}

function formatDate(isoStr: string | null): string {
  if (!isoStr) return "—";
  return new Intl.DateTimeFormat("en-GB", {
    timeZone: "Europe/Sofia",
    day: "numeric", month: "short", year: "numeric",
    hour: "2-digit", minute: "2-digit",
  }).format(new Date(isoStr));
}

function pill(text: string, color: string, bg: string): string {
  return `<span style="font-size:0.62rem;font-weight:700;padding:2px 6px;border-radius:4px;background:${bg};color:${color}">${text}</span>`;
}

function buildPopup(f: BinFeature): string {
  const fill     = f.properties.fill_level;
  const color    = binColor(fill, f.properties.waste_type);
  const wColor   = wasteColor(f.properties.waste_type);
  const addr     = f.properties.public_number;
  const isGrey   = f.properties.waste_type === "general";

  const extras = isGrey ? `
    <div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:8px">
      ${f.properties.bin_count > 1 ? pill(`${f.properties.bin_count} bins`, "#94A3B8", "rgba(148,163,184,0.12)") : ""}
      ${f.properties.capacity_volume != null ? pill(`${Math.round(f.properties.capacity_volume * 1000)} L`, "#94A3B8", "rgba(148,163,184,0.12)") : ""}
      ${f.properties.last_cleaned ? pill(`cleaned ${formatDate(f.properties.last_cleaned)}`, "#34D399", "rgba(52,211,153,0.10)") : ""}
    </div>` : `
    <div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:8px">
      ${f.properties.container_type ? pill(f.properties.container_type, "#94A3B8", "rgba(148,163,184,0.12)") : ""}
      ${f.properties.capacity_volume != null ? pill(`${Math.round(f.properties.capacity_volume * 1000)} L`, "#94A3B8", "rgba(148,163,184,0.12)") : ""}
      ${f.properties.bin_count > 1 ? pill(`×${f.properties.bin_count}`, "#94A3B8", "rgba(148,163,184,0.12)") : ""}
    </div>`;

  const fillSection = isGrey ? `
    <div style="background:rgba(255,255,255,0.04);border-radius:7px;padding:8px 10px;margin-bottom:8px">
      <div style="display:flex;justify-content:space-between;align-items:baseline">
        <span style="font-size:0.68rem;color:#64748B;font-weight:600">Fill level</span>
        <span style="font-size:0.85rem;font-weight:800;color:${color}">${fill !== null ? `${fill}%` : "—"}</span>
      </div>
      ${fillBar(fill, color)}
    </div>` : "";

  return `
    <div style="font-family:Manrope,system-ui,sans-serif;padding:12px 14px;min-width:200px">
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:6px">
        <span style="font-size:0.82rem;font-weight:800;color:#F0F6FF">Bin #${f.properties.id}</span>
        <span style="font-size:0.65rem;font-weight:700;padding:2px 7px;border-radius:5px;
          background:${f.properties.bin_status === "active" ? "rgba(52,211,153,0.15)" : "rgba(100,116,139,0.15)"};
          color:${f.properties.bin_status === "active" ? "#34D399" : "#64748B"}">
          ${f.properties.bin_status}
        </span>
      </div>
      ${addr ? `<div style="font-size:0.72rem;color:#F0F6FF;font-weight:600;margin-bottom:5px;line-height:1.4">${addr}</div>` : ""}
      <div style="font-size:0.7rem;color:#64748B;margin-bottom:8px;line-height:1.6">
        ${f.properties.district_name || "Unknown district"} &nbsp;·&nbsp;
        <span style="color:${wColor}">${wasteLabel(f.properties.waste_type)}</span>
      </div>
      ${extras}
      ${fillSection}
      <a href="/bin/${f.properties.id}" style="display:block;text-align:right;font-size:0.68rem;font-weight:700;color:#60A5FA;text-decoration:none">View details →</a>
    </div>`;
}

function buildGroupPopup(features: BinFeature[]): string {
  const addr = features[0].properties.public_number;
  const rows = features.map(f => {
    const wc  = wasteColor(f.properties.waste_type);
    const ct  = f.properties.container_type;
    const cap = f.properties.capacity_volume;
    const meta = [
      ct  ? ct : "",
      cap ? `${Math.round(cap * 1000)} L` : "",
      f.properties.bin_count > 1 ? `×${f.properties.bin_count}` : "",
    ].filter(Boolean).join(" · ");
    return `
      <div style="display:flex;align-items:center;gap:8px;padding:7px 0;border-bottom:1px solid rgba(255,255,255,0.05)">
        <div style="width:9px;height:9px;border-radius:50%;background:${wc};flex-shrink:0;box-shadow:0 0 4px ${wc}88"></div>
        <div style="flex:1;min-width:0">
          <div style="font-size:0.76rem;font-weight:700;color:#F0F6FF">${wasteLabel(f.properties.waste_type)}</div>
          ${meta ? `<div style="font-size:0.65rem;color:#64748B;margin-top:1px">${meta}</div>` : ""}
        </div>
        <a href="/bin/${f.properties.id}" style="font-size:0.65rem;font-weight:700;color:#60A5FA;text-decoration:none;flex-shrink:0">Details →</a>
      </div>`;
  }).join("");

  return `
    <div style="font-family:Manrope,system-ui,sans-serif;padding:10px 14px;min-width:230px">
      <div style="font-size:0.82rem;font-weight:800;color:#F0F6FF;margin-bottom:2px">
        ${features.length} bins at this location
      </div>
      ${addr ? `<div style="font-size:0.7rem;color:#64748B;margin-bottom:6px">${addr}</div>` : `<div style="margin-bottom:6px"></div>`}
      ${rows}
    </div>`;
}

export default function Map({ panTarget }: { panTarget?: PanTarget | null }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef       = useRef<LeafletMap | null>(null);
  const layersRef    = useRef<Layer[]>([]);
  const [status, setStatus]   = useState<string>("Loading…");
  const [isLoading, setLoading] = useState(false);

  useEffect(() => {
    if (mapRef.current || !containerRef.current) return;

    let L: typeof import("leaflet");

    async function init() {
      L = (await import("leaflet")).default;

      delete (L.Icon.Default.prototype as any)._getIconUrl; // eslint-disable-line
      L.Icon.Default.mergeOptions({
        iconRetinaUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
        iconUrl:       "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
        shadowUrl:     "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
      });

      const map = L.map(containerRef.current!, {
        center: [SOFIA.lat, SOFIA.lng],
        zoom: 11,
        zoomControl: true,
        attributionControl: true,
      });

      L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
        attribution: '© <a href="https://www.openstreetmap.org/copyright">OSM</a> © <a href="https://carto.com/">CARTO</a>',
        subdomains: "abcd",
        maxZoom: 19,
      }).addTo(map);

      mapRef.current = map;

      // District boundaries — static file bundled with Next.js, no API call
      fetch("/sofia-districts.json").then(r => r.json()).then((fc) => {
        L.geoJSON(fc as any, { // eslint-disable-line
          interactive: false,
          style: {
            color: "rgba(96,165,250,0.55)",
            weight: 2,
            fill: true,
            fillColor: "rgba(96,165,250,0.07)",
            fillOpacity: 1,
          },
        }).addTo(map);
      });

      let requestId = 0;

      async function refresh() {
        const myId = ++requestId;
        const zoom = map.getZoom();
        const b    = map.getBounds();
        const { _northEast: ne, _southWest: sw } = b as any; // eslint-disable-line
        const north = ne.lat, south = sw.lat, east = ne.lng, west = sw.lng;

        setLoading(true);

        try {
          const newLayers: Layer[] = [];

          if (zoom >= VIEWPORT_ZOOM) {
            const fc = await fetchViewport(north, south, east, west);
            if (myId !== requestId) return; // stale response — discard

            // Group bins by exact coordinate so co-located bins share one marker
            const groups: Record<string, BinFeature[]> = {};
            for (const f of fc.features) {
              const key = `${f.geometry.coordinates[0]},${f.geometry.coordinates[1]}`;
              (groups[key] ??= []).push(f);
            }

            for (const features of Object.values(groups)) {
              const [lng, lat] = features[0].geometry.coordinates;

              if (features.length === 1 && (features[0].properties.bin_count <= 1 || zoom < EXPAND_ZOOM)) {
                // True single bin — plain circle
                const f     = features[0];
                const fill  = f.properties.fill_level;
                const color = binColor(fill, f.properties.waste_type);
                const m = L.circleMarker([lat, lng], {
                  radius: 5,
                  fillColor: color,
                  color: "#070D1A",
                  weight: 1,
                  fillOpacity: 0.9,
                }).bindPopup(buildPopup(f), { maxWidth: 250, className: "" });
                newLayers.push(m);
              } else {
                // Compound marker — either multiple co-located features OR
                // a single record with bin_count > 1 (e.g. 3 grey bins at one spot)
                let dotColors: string[];
                let popup: string;

                if (features.length === 1) {
                  // Single record, bin_count > 1: expand into N same-colour dots
                  const f     = features[0];
                  const color = binColor(f.properties.fill_level, f.properties.waste_type);
                  const MAX   = 6;
                  const shown = Math.min(f.properties.bin_count, MAX);
                  dotColors   = Array(shown).fill(color);
                  if (f.properties.bin_count > MAX)
                    dotColors.push(`+${f.properties.bin_count - MAX}`); // sentinel for overflow label
                  popup = buildPopup(f);
                } else {
                  // Multiple co-located features (different types)
                  dotColors = features.map(f => wasteColor(f.properties.waste_type));
                  popup     = buildGroupPopup(features);
                }

                const dots = dotColors.map(c =>
                  c.startsWith("+")
                    ? `<span style="font-size:8px;color:#94A3B8;font-weight:800;font-family:Manrope,sans-serif;padding:0 1px">${c}</span>`
                    : `<div style="width:10px;height:10px;border-radius:50%;background:${c};border:1.5px solid rgba(7,13,26,0.7);box-shadow:0 0 4px ${c}66"></div>`
                ).join("");

                const w = dotColors.length * 13 + 8;
                const icon = L.divIcon({
                  html: `<div style="display:flex;gap:2px;align-items:center;cursor:pointer;
                    background:rgba(7,13,26,0.88);border-radius:9px;padding:4px 5px;
                    border:1px solid rgba(255,255,255,0.13);
                    box-shadow:0 2px 8px rgba(0,0,0,0.55)">${dots}</div>`,
                  iconSize:   [w, 22],
                  iconAnchor: [w / 2, 11],
                  className:  "",
                });

                const m = L.marker([lat, lng], { icon })
                  .bindPopup(popup, { maxWidth: 270, className: "" });
                newLayers.push(m);
              }
            }

            // Atomic swap — remove old only after new data is ready
            layersRef.current.forEach(l => l.remove());
            newLayers.forEach(l => l.addTo(map));
            layersRef.current = newLayers;
            setStatus(`${fc.features.length} bins`);

          } else {
            const clusters = await fetchClusters(zoom, north, south, east, west);
            if (myId !== requestId) return; // stale response — discard

            clusters.forEach((c: Cluster) => {
              const color = clusterColor(c.count);
              const sz    = 16;
              const svgH  = Math.round(sz * 31 / 24);
              const label = c.count >= 1000 ? `${(c.count / 1000).toFixed(1)}k` : String(c.count);

              const icon = L.divIcon({
                html: `<div style="display:flex;flex-direction:column;align-items:center;gap:2px;filter:drop-shadow(0 2px 5px rgba(0,0,0,0.55))">
                  <svg width="${sz}" height="${svgH}" viewBox="0 0 24 31" fill="none">
                    <rect x="8" y="0" width="8" height="4" rx="2" fill="${color}"/>
                    <rect x="1" y="4" width="22" height="4.5" rx="2" fill="${color}"/>
                    <path d="M4 8.5 L3.5 27 Q3.5 30 6 30 L18 30 Q20.5 30 20.5 27 L20 8.5 Z" fill="${color}"/>
                    <line x1="9" y1="12" x2="9" y2="25" stroke="rgba(255,255,255,0.22)" stroke-width="1.5" stroke-linecap="round"/>
                    <line x1="12" y1="12" x2="12" y2="25" stroke="rgba(255,255,255,0.22)" stroke-width="1.5" stroke-linecap="round"/>
                    <line x1="15" y1="12" x2="15" y2="25" stroke="rgba(255,255,255,0.22)" stroke-width="1.5" stroke-linecap="round"/>
                  </svg>
                  <span style="font-family:Manrope,system-ui,sans-serif;font-size:${sz < 27 ? 9 : 11}px;font-weight:800;color:${color};line-height:1;text-shadow:0 1px 4px rgba(0,0,0,0.9)">${label}</span>
                </div>`,
                iconSize:   [sz + 8, svgH + 16],
                iconAnchor: [(sz + 8) / 2, svgH],
                className:  "",
              });

              const m = L.marker([c.lat, c.lon], { icon })
                .on("click", () => map.setView([c.lat, c.lon], zoom + 2));
              newLayers.push(m);
            });

            // Atomic swap
            layersRef.current.forEach(l => l.remove());
            newLayers.forEach(l => l.addTo(map));
            layersRef.current = newLayers;
            setStatus(`${clusters.length} clusters`);
          }
        } finally {
          if (myId === requestId) setLoading(false);
        }
      }

      map.on("moveend", refresh);
      await refresh();
    }

    init();
    return () => { mapRef.current?.remove(); mapRef.current = null; };
  }, []);

  useEffect(() => {
    if (panTarget && mapRef.current) {
      mapRef.current.setView([panTarget.lat, panTarget.lon], Math.max(mapRef.current.getZoom(), 13));
    }
  }, [panTarget]);

  return (
    <div style={{ position: "relative", height: "100%", width: "100%" }}>
      <div ref={containerRef} style={{ height: "100%", width: "100%" }} />

      {/* Status badge */}
      <div style={{
        position: "absolute", bottom: 36, left: 10, zIndex: 500,
        background: "rgba(7,13,26,0.9)",
        color: isLoading ? "#64748B" : "#60A5FA",
        borderRadius: 7, padding: "4px 10px",
        fontSize: "0.68rem", fontWeight: 700,
        border: "1px solid rgba(96,165,250,0.15)",
        pointerEvents: "none",
        display: "flex", alignItems: "center", gap: 5,
        backdropFilter: "blur(4px)",
      }}>
        {isLoading && (
          <span style={{
            width: 6, height: 6, borderRadius: "50%",
            background: "#60A5FA", display: "inline-block",
            animation: "pulse 1s ease-in-out infinite",
          }} />
        )}
        {status}
      </div>

      {/* Legend */}
      <div style={{
        position: "absolute", bottom: 36, right: 10, zIndex: 500,
        background: "rgba(7,13,26,0.9)",
        borderRadius: 9, padding: "8px 12px",
        border: "1px solid rgba(96,165,250,0.12)",
        backdropFilter: "blur(4px)",
        display: "flex", flexDirection: "column", gap: 3,
        pointerEvents: "none",
      }}>
        {/* Coloured bins */}
        <div style={{ fontSize: "0.56rem", fontWeight: 800, color: "#475569", letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: 2 }}>Coloured bins</div>
        {[
          { color: "#818CF8", label: "Paper" },
          { color: "#FBBF24", label: "Recycling" },
          { color: "#34D399", label: "Glass" },
        ].map(({ color, label }) => (
          <div key={label} style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <div style={{ width: 9, height: 9, borderRadius: "50%", background: color, flexShrink: 0 }} />
            <span style={{ fontSize: "0.62rem", fontWeight: 600, color: "#94A3B8" }}>{label}</span>
          </div>
        ))}

        {/* Grey bins */}
        <div style={{ fontSize: "0.56rem", fontWeight: 800, color: "#475569", letterSpacing: "0.1em", textTransform: "uppercase", marginTop: 5, marginBottom: 2 }}>Grey bins</div>
        {[
          { color: "#34D399", label: "0 – 59%" },
          { color: "#FBBF24", label: "60 – 79%" },
          { color: "#FB923C", label: "80 – 99%" },
          { color: "#F87171", label: "Full / Overflow" },
          { color: "#475569", label: "No data" },
        ].map(({ color, label }) => (
          <div key={label} style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <div style={{ width: 9, height: 9, borderRadius: "50%", background: color, flexShrink: 0 }} />
            <span style={{ fontSize: "0.62rem", fontWeight: 600, color: "#94A3B8" }}>{label}</span>
          </div>
        ))}
      </div>

      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.3; }
        }
      `}</style>
    </div>
  );
}
