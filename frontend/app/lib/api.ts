export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "https://kazan.zabravih.org";

export const API_INTERNAL =
  process.env.API_INTERNAL_URL ?? "http://127.0.0.1:8000";

export interface District {
  district_id: number;
  district_name: string;
  bin_count: number;
  active_count: number;
  monitored_count: number;
  center_lat: number | null;
  center_lon: number | null;
}

export interface Totals {
  grey_bins: number;
  coloured_bins: number;
  active_bins: number;
  monitored_bins: number;
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
    public_number: string;
    capacity_volume: number | null;
    bin_count: number;
    last_cleaned: string | null;
    container_type: string;
  };
}

export interface FeatureCollection {
  type: "FeatureCollection";
  features: BinFeature[];
}

export interface FillRecord {
  timestamp: string;
  fill_level: number;
  source: string;
}

export interface BinDetail {
  id: number;
  latitude: number;
  longitude: number;
  waste_type: string;
  bin_status: string;
  public_number: string;
  district_id: number | null;
  district_name: string;
  capacity_volume: number | null;
  bin_count: number;
  last_cleaned: string | null;
  container_type: string;
  fill_history: FillRecord[];
}

const EMPTY_RESPONSE = {
  districts: [] as District[],
  totals: { grey_bins: 0, coloured_bins: 0, active_bins: 0, monitored_bins: 0 } as Totals,
};

export async function fetchDistricts(): Promise<{ districts: District[]; totals: Totals }> {
  const res = await fetch(`${API_INTERNAL}/api/districts/`, {
    next: { revalidate: 3600 },
  });
  if (!res.ok) throw new Error("districts fetch failed");
  const data = await res.json();
  return {
    districts: data.districts ?? [],
    totals: data.totals ?? EMPTY_RESPONSE.totals,
  };
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
  return data.clusters ?? [];
}

export async function fetchBinDetail(id: number): Promise<BinDetail | null> {
  const res = await fetch(`${API_INTERNAL}/api/bins/${id}/`, { cache: "no-store" });
  if (!res.ok) return null;
  return res.json();
}

export async function fetchDistrictBoundaries(): Promise<FeatureCollection> {
  const res = await fetch(`${API_INTERNAL}/api/districts/boundaries/`, {
    next: { revalidate: 86400 },
  });
  if (!res.ok) return { type: "FeatureCollection", features: [] };
  return res.json();
}

// Client-safe version — uses public base URL, called from browser
export async function fetchDistrictBoundariesClient(): Promise<FeatureCollection> {
  const res = await fetch(`${API_BASE}/api/districts/boundaries/`, { cache: "force-cache" });
  if (!res.ok) return { type: "FeatureCollection", features: [] };
  return res.json();
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
