export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "https://kazan.zabravih.org";

// Server-side calls go direct to gunicorn to skip the nginx round-trip
export const API_INTERNAL =
  process.env.API_INTERNAL_URL ?? "http://127.0.0.1:8000";

export interface District {
  district_id: number;
  district_name: string;
  bin_count: number;
  active_count: number;
  monitored_count: number;
}

export interface Cluster {
  lat: number;
  lon: number;
  count: number;
  district_id: number;
}

export interface BinFeature {
  type: "Feature";
  geometry: { type: "Point"; coordinates: [number, number] };
  properties: {
    id: number;
    fill_level: number | null;
    district_id: number;
    district_name: string;
    waste_type: string;
    bin_status: string;
  };
}

export interface FeatureCollection {
  type: "FeatureCollection";
  features: BinFeature[];
}

export async function fetchDistricts(): Promise<District[]> {
  const res = await fetch(`${API_INTERNAL}/api/districts/`, {
    next: { revalidate: 3600 },
  });
  if (!res.ok) throw new Error("districts fetch failed");
  const data = await res.json();
  return data.districts;
}

export async function fetchClusters(
  zoom: number,
  north: number,
  south: number,
  east: number,
  west: number
): Promise<Cluster[]> {
  const url = `${API_BASE}/api/bins/clusters/?zoom=${zoom}&north=${north}&south=${south}&east=${east}&west=${west}`;
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) return [];
  const data = await res.json();
  return data.clusters;
}

export async function fetchViewport(
  north: number,
  south: number,
  east: number,
  west: number
): Promise<FeatureCollection> {
  const url = `${API_BASE}/api/bins/viewport/?north=${north}&south=${south}&east=${east}&west=${west}`;
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) return { type: "FeatureCollection", features: [] };
  return res.json();
}
