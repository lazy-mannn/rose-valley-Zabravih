"use client";

import { useEffect, useRef, useState } from "react";
import type { Map as LeafletMap, CircleMarker, Marker } from "leaflet";
import type { Cluster, BinFeature } from "@/app/lib/api";
import { fetchClusters, fetchViewport } from "@/app/lib/api";

// Leaflet is browser-only — imported inside useEffect to avoid SSR issues
const SOFIA = { lat: 42.698, lng: 23.324 };
const VIEWPORT_ZOOM = 15;

function clusterColor(count: number): string {
  if (count > 300) return "#2563EB";
  if (count > 100) return "#3B82F6";
  if (count > 30)  return "#60A5FA";
  return "#93C5FD";
}

function binColor(fillLevel: number | null): string {
  if (fillLevel === null) return "#60A5FA";
  if (fillLevel >= 100)   return "#F87171";
  if (fillLevel >= 80)    return "#FB923C";
  if (fillLevel >= 60)    return "#FBBF24";
  return "#34D399";
}

export default function Map() {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef       = useRef<LeafletMap | null>(null);
  const layersRef    = useRef<(CircleMarker | Marker)[]>([]);
  const [status, setStatus] = useState("Loading map…");

  useEffect(() => {
    if (mapRef.current || !containerRef.current) return;

    let L: typeof import("leaflet");

    async function init() {
      L = (await import("leaflet")).default;

      // Fix default marker icons (webpack strips asset URLs)
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      delete (L.Icon.Default.prototype as any)._getIconUrl;
      L.Icon.Default.mergeOptions({
        iconRetinaUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
        iconUrl:       "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
        shadowUrl:     "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
      });

      const map = L.map(containerRef.current!, {
        center: [SOFIA.lat, SOFIA.lng],
        zoom: 12,
        zoomControl: true,
      });

      L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
        attribution: '© <a href="https://www.openstreetmap.org/copyright">OSM</a> © <a href="https://carto.com/">CARTO</a>',
        subdomains: "abcd",
        maxZoom: 19,
      }).addTo(map);

      mapRef.current = map;

      async function refresh() {
        const zoom = map.getZoom();
        const b = map.getBounds();
        const north = b.getNorth(), south = b.getSouth();
        const east  = b.getEast(),  west  = b.getWest();

        // Clear old layers
        layersRef.current.forEach(l => l.remove());
        layersRef.current = [];

        if (zoom >= VIEWPORT_ZOOM) {
          setStatus("Loading bins…");
          const fc = await fetchViewport(north, south, east, west);
          fc.features.forEach((f: BinFeature) => {
            const [lng, lat] = f.geometry.coordinates;
            const fill = f.properties.fill_level;
            const m = L.circleMarker([lat, lng], {
              radius: 6,
              fillColor: binColor(fill),
              color: "#0F172A",
              weight: 1,
              fillOpacity: 0.9,
            }).bindPopup(
              `<div style="font-family:Manrope,sans-serif;min-width:160px;">
                <b>Bin #${f.properties.id}</b><br>
                ${f.properties.district_name} · ${f.properties.waste_type}<br>
                Status: ${f.properties.bin_status}<br>
                Fill: ${fill !== null ? fill + "%" : "no data"}
              </div>`
            );
            m.addTo(map);
            layersRef.current.push(m);
          });
          setStatus(`${fc.features.length} bins`);
        } else {
          setStatus("Loading clusters…");
          const clusters = await fetchClusters(zoom, north, south, east, west);
          clusters.forEach((c: Cluster) => {
            const radius = Math.min(8 + Math.sqrt(c.count) * 1.4, 38);
            const m = L.circleMarker([c.lat, c.lon], {
              radius,
              fillColor: clusterColor(c.count),
              color: "#0F172A",
              weight: 1.5,
              fillOpacity: 0.82,
            })
              .bindTooltip(String(c.count), {
                permanent: true,
                direction: "center",
                className: "cluster-label",
              })
              .on("click", () => map.setView([c.lat, c.lon], zoom + 2));
            m.addTo(map);
            layersRef.current.push(m);
          });
          setStatus(`${clusters.length} clusters`);
        }
      }

      map.on("moveend", refresh);
      await refresh();
    }

    init();
    return () => { mapRef.current?.remove(); mapRef.current = null; };
  }, []);

  return (
    <div style={{ position: "relative", height: "100%", width: "100%" }}>
      <div ref={containerRef} style={{ height: "100%", width: "100%" }} />
      <div style={{
        position: "absolute", bottom: 36, left: 8, zIndex: 500,
        background: "rgba(7,13,26,0.85)", color: "#60A5FA",
        borderRadius: 8, padding: "3px 10px",
        fontSize: "0.72rem", fontWeight: 700,
        border: "1px solid rgba(96,165,250,0.18)",
        pointerEvents: "none",
      }}>
        {status}
      </div>
      <style>{`
        .cluster-label {
          background: transparent !important;
          border: none !important;
          box-shadow: none !important;
          color: #fff;
          font-weight: 800;
          font-size: 0.72rem;
          font-family: Manrope, sans-serif;
          text-shadow: 0 1px 3px rgba(0,0,0,0.9);
        }
      `}</style>
    </div>
  );
}
