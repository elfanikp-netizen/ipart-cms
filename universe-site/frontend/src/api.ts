import axios from "axios";
import { beginOperation, finishOperation, updateOperation } from "./components/operation-progress-store";

export interface Vehicle {
  id: number;
  year: number;
  make: string;
  model: string;
  notes: string;
  created_at: string;
  updated_at: string;
  vin_count: number;
}

export interface Vin {
  id: number;
  id_vehicle: number;
  vin: string;
  notes: string;
  created_at: string;
  updated_at: string;
  vehicle: Pick<Vehicle, "id" | "year" | "make" | "model">;
}

export interface Page<T> {
  items: T[];
  page: number;
  page_size: number;
  total: number;
  pages: number;
}

export interface ImportSummary {
  vehicles_created: number;
  vehicles_updated: number;
  created: number;
  updated: number;
  skipped: number;
  errors: string[];
}

export interface VehicleOption {
  id: number;
  year: number;
  make: string;
  model: string;
  label: string;
}

export interface FilterOptions {
  years: number[];
  makes: string[];
  models: string[];
}

export interface CccMarketRecord {
  id: number;
  oem: string;
  vin: string;
  crawl_date: string;
  description: string;
  vendor: string;
  market_data: Record<string, unknown> | unknown[];
  created_at: string;
  updated_at: string;
}

export interface PartsMsrpRecord {
  id: number;
  oem: string;
  fitments: string[];
  msrp: string;
  previous_msrp: string | null;
  ccc_price: string | null;
  previous_ccc_price: string | null;
  gap_msrp: string | null;
  gap_ccc: string | null;
  crawl_date: string;
}

export interface PartsMsrpPage {
  items: PartsMsrpRecord[];
  page: number;
  page_size: number;
  total: number;
  pages: number;
}

export interface PartsMsrpImportSummary {
  created: number;
  updated: number;
  skipped: number;
  errors: string[];
}

export interface CccMarketPage {
  items: Pick<CccMarketRecord, "oem" | "vin" | "crawl_date">[];
  page: number;
  page_size: number;
  total: number;
  pages: number;
}

export interface CccMarketOffer {
  market_index: number;
  market_data: Record<string, unknown>;
}

export interface CccPriceObservation {
  crawl_date: string;
  price: string;
  previous_price: string | null;
  change: string | null;
}

export interface CccVendorPriceHistory {
  vendor: string;
  observations: CccPriceObservation[];
}

export interface CccPriceHistory {
  oem: string;
  vin: string;
  description: string;
  vendors: CccVendorPriceHistory[];
}

export interface CccVendorDashboard {
  vendor: string;
  from_date: string | null;
  to_date: string | null;
  priced_offers: number;
  wins: number;
  losses: number;
  win_rate: number;
  crawl_wins: number;
  crawl_losses: number;
  crawl_win_rate: number;
  average_gap: string;
  average_vendor_price: string;
  average_market_low: string;
  oem_count: number;
  vin_count: number;
  crawl_count: number;
  opportunity_count: number;
  trend: { date: string; average_price: string; average_lowest_price: string; offers: number }[];
  trend_oem: { date: string; average_price: string; average_lowest_price: string; oems: number }[];
  descriptions: {
    description: string;
    wins: number;
    losses: number;
    opportunities: number;
    win_rate: number;
    won_oem_count: number;
    lost_oem_count: number;
    crawl_wins: number;
    crawl_losses: number;
    oem_opportunities: number;
    oem_win_rate: number;
    crawl_opportunities: number;
    crawl_win_rate: number;
  }[];
  details: {
      vendor: string;
    oem: string;
    vin: string;
    description: string;
    crawl_date: string;
    price: string;
    gap_price: string;
    previous_price: string | null;
    lowest_price: string;
    lowest_vendors: string;
    gap: string;
    outcome: "won" | "lost";
    previous_crawl_date: string | null;
    previous_vendor_price: string | null;
    previous_lowest_vendors: string;
    previous_lowest_price: string | null;
  }[];
  details_total: number;
}

export interface CccMarketFilters {
  oems: string[];
  vins: string[];
  descriptions: string[];
  vendors: string[];
}

export interface CccVehicleOptions {
  oems: string[];
  vins: string[];
}

export interface CccLowestPriceSummary {
  from_date: string | null;
  to_date: string | null;
  vendor_count: number;
  oem_count: number;
  lowest_count: number;
  lost_count: number;
  vendors: {
    vendor: string;
    oem_count: number;
    won_oem_count: number;
    lost_oem_count: number;
    lowest_count: number;
    lost_count: number;
    descriptions: {
      description: string;
      won_oem_count: number;
      won_count: number;
      lost_oem_count: number;
      lost_count: number;
    }[];
  }[];
}

export interface CccLowestPriceDetail {
  oem: string;
  vin: string;
  crawl_date: string;
  previous_crawl_date: string | null;
  previous_lowest_vendors: string;
  previous_lowest_price: string | null;
  vendor: string;
  description: string;
  price: string;
  gap_price: string;
  previous_price: string | null;
  gap_previous_price: string | null;
  lowest_price: string;
  lowest_vendors: string;
  second_lowest_price: string | null;
  second_lowest_vendors: string;
  outcome: "won" | "lost";
  crawl_count?: number;
}

export interface CccMarketImportSummary {
  created: number;
  updated: number;
  skipped: number;
  errors: string[];
}

export const client = axios.create({ withCredentials: true });

const trackedOperations = new WeakMap<object, number>();

function operationDetails(url = "", method = "get") {
  const path = url.split("?")[0].toLocaleLowerCase();
  const kind = /\/import\/?$/.test(path) ? "import" : /\/export(?:-[^/]+)?\/?$/.test(path) ? "export" : null;
  if (!kind) return null;

  const route = path.replace(/^.*\/api\/universe\//, "").replace(/\/(?:import|export(?:-[^/]+)?)\/?$/, "");
  const labels: Record<string, string> = {
    vehicles: "Vehicles", vins: "VINs", oems: "OEMs", oem: "OEMs",
    partslinks: "Partslink", interchanges: "Interchanges",
    "partslink-interchange": "Cross-reference", "market/ccc": "CCC market",
    "market/parts-msrp": "Parts MSRP",
  };
  const routeParts = route.split("/");
  const label = labels[route] ?? routeParts[routeParts.length - 1]?.replace(/-/g, " ") ?? "data";
  const hasUpload = method.toLocaleLowerCase() === "post";
  return { kind, label, phase: hasUpload ? "uploading" : "processing" } as const;
}

client.interceptors.request.use((config) => {
  const details = operationDetails(config.url, config.method);
  if (!details) return config;

  const id = beginOperation(details.kind, details.label, details.phase);
  trackedOperations.set(config, id);
  if (details.phase === "uploading") {
    config.onUploadProgress = (event) => {
      if (event.total && event.total > 0) {
        const percent = Math.min(100, Math.round((event.loaded / event.total) * 100));
        updateOperation(id, percent >= 100
          ? { phase: "processing", percent: null }
          : { phase: "uploading", percent });
      }
    };
  }
  if (details.kind === "export") {
    config.onDownloadProgress = (event) => {
      const percent = event.total && event.total > 0
        ? Math.min(100, Math.round((event.loaded / event.total) * 100))
        : null;
      updateOperation(id, { phase: "downloading", percent });
    };
  }
  return config;
});

client.interceptors.response.use(
  (response) => {
    const id = trackedOperations.get(response.config);
    if (id !== undefined) finishOperation(id);
    return response;
  },
  (error: unknown) => {
    if (axios.isAxiosError(error) && error.config) {
      const id = trackedOperations.get(error.config);
      if (id !== undefined) {
        const detail = (error.response?.data as { detail?: string } | undefined)?.detail;
        finishOperation(id, detail ?? error.message ?? "The operation failed.");
      }
    }
    return Promise.reject(error);
  },
);

export function errorText(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const detail = (error.response?.data as { detail?: string } | undefined)?.detail;
    return detail ?? error.message;
  }
  return String(error);
}

export async function getPage<T>(path: string, params: Record<string, string | number | undefined>) {
  return (await client.get<Page<T>>(path, { params })).data;
}

export async function getVehicleOptions(search = "", limit = 100) {
  return (await client.get<VehicleOption[]>("/api/universe/vehicles/options", { params: { search, limit } })).data;
}

export async function getFilterOptions() {
  return (await client.get<FilterOptions>("/api/universe/filters")).data;
}

export async function getCccMarketPage(params: {
  page: number;
  page_size: number;
  search: string;
  oem: string;
  vin: string;
  description: string;
  vendor: string;
}) {
  return (await client.get<CccMarketPage>("/api/universe/market/ccc", { params })).data;
}

export async function exportCccMarketCrawls(params: {
  search: string;
  oem: string;
  vin: string;
  description: string;
  vendor: string;
}) {
  const response = await client.get<Blob>("/api/universe/market/ccc/export", {
    params,
    responseType: "blob",
  });
  saveBlob(response.data, "ccc-crawls.xlsx");
}

export async function exportCccOemListPrices(file: File, options: {
  vendors: string[];
  descriptions: string[];
  price_direction: "lowest" | "highest";
  price_field: "ext-price" | "total";
}) {
  const form = new FormData();
  form.append("file", file);
  options.vendors.forEach((vendor) => form.append("vendors", vendor));
  options.descriptions.forEach((description) => form.append("descriptions", description));
  form.append("price_direction", options.price_direction);
  form.append("price_field", options.price_field);
  const response = await client.post<Blob>("/api/universe/market/ccc/export-by-oem-list", form, {
    responseType: "blob",
  });
  saveBlob(response.data, `ccc-oem-won-${options.price_direction}.xlsx`);
}

export async function getCccMarketFilters() {
  return (await client.get<CccMarketFilters>("/api/universe/market/ccc/filters")).data;
}

export async function getCccVehicleOptions(oem = "", vin = "") {
  return (await client.get<CccVehicleOptions>("/api/universe/market/ccc/vehicle-options", {
    params: { oem: oem || undefined, vin: vin || undefined },
  })).data;
}

export async function getCccMarketOffers(group: Pick<CccMarketRecord, "oem" | "vin" | "crawl_date">) {
  return (await client.get<CccMarketOffer[]>("/api/universe/market/ccc/offers", { params: group })).data;
}

export async function getCccPriceHistory(params: {
  oem: string;
  vin: string;
  description: string;
  from_date: string;
  to_date: string;
}) {
  return (await client.get<CccPriceHistory>("/api/universe/market/ccc/price-history", { params })).data;
}

export async function getCccVendorDashboard(params: {
  vendor: string;
  from_date: string;
  to_date: string;
  description: string;
}) {
  return (await client.get<CccVendorDashboard>("/api/universe/market/ccc/vendor-dashboard", { params })).data;
}

export async function getCccLowestPriceSummary(fromDate = "", toDate = "") {
  return (await client.get<CccLowestPriceSummary>("/api/universe/market/ccc/lowest-price", {
    params: { from_date: fromDate || undefined, to_date: toDate || undefined },
  })).data;
}

export async function getCccLowestPriceDetails(params: {
  vendor: string;
  description: string;
  outcome: "won" | "lost";
  metric: "oem" | "crawl";
  from_date: string;
  to_date: string;
}) {
  return (await client.get<CccLowestPriceDetail[]>("/api/universe/market/ccc/lowest-price/details", { params })).data;
}

export async function exportCccLowestPriceDetails(params: {
  vendor: string;
  description: string;
  outcome: "won" | "lost";
  metric: "oem" | "crawl";
  from_date: string;
  to_date: string;
}) {
  const response = await client.get<Blob>("/api/universe/market/ccc/lowest-price/export", { params, responseType: "blob" });
  const url = URL.createObjectURL(response.data);
  const link = document.createElement("a");
  link.href = url;
  link.download = `ccc-${params.outcome}-${params.metric}-details.xlsx`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export async function importCccMarketExcel(file: File) {
  const form = new FormData();
  form.append("file", file);
  return (await client.post<CccMarketImportSummary>("/api/universe/market/ccc/import", form)).data;
}

export async function getPartsMsrpPage(params: {
  page: number;
  page_size: number;
  search: string;
  filters: string;
  sort_by: string;
  sort_dir: "asc" | "desc";
  from_date: string;
  to_date: string;
}) {
  return (await client.get<PartsMsrpPage>("/api/universe/market/parts-msrp", { params })).data;
}

export async function importPartsMsrpExcel(file: File) {
  const form = new FormData();
  form.append("file", file);
  return (await client.post<PartsMsrpImportSummary>("/api/universe/market/parts-msrp/import", form)).data;
}

export async function exportPartsMsrpExcel(params: {
  search: string;
  filters: string;
  sort_by: string;
  sort_dir: "asc" | "desc";
  from_date: string;
  to_date: string;
  group_by_oem: boolean;
}) {
  const response = await client.get<Blob>("/api/universe/market/parts-msrp/export", {
    params: { ...params, search: params.search || undefined },
    responseType: "blob",
  });
  saveBlob(response.data, "parts-msrp.xlsx");
}

export async function exportPartsMsrpByOemList(file: File, fromDate: string, toDate: string, groupByOem: boolean) {
  const form = new FormData();
  form.append("file", file);
  const response = await client.post<Blob>("/api/universe/market/parts-msrp/export-by-list", form, {
    params: { from_date: fromDate || undefined, to_date: toDate || undefined, group_by_oem: groupByOem },
    responseType: "blob",
  });
  saveBlob(response.data, "parts-msrp-by-oem.xlsx");
}

export async function saveVehicle(id: number | null, values: Pick<Vehicle, "year" | "make" | "model" | "notes">) {
  const response = id === null
    ? await client.post<Vehicle>("/api/universe/vehicles", values)
    : await client.put<Vehicle>(`/api/universe/vehicles/${id}`, values);
  return response.data;
}

export async function saveVin(id: number | null, values: Pick<Vin, "id_vehicle" | "vin" | "notes">) {
  const response = id === null
    ? await client.post<Vin>("/api/universe/vins", values)
    : await client.put<Vin>(`/api/universe/vins/${id}`, values);
  return response.data;
}

export async function deleteRecord(type: "vehicles" | "vins", id: number) {
  await client.delete(`/api/universe/${type}/${id}`);
}

export async function importExcel(type: "vehicles" | "vins", file: File) {
  const form = new FormData();
  form.append("file", file);
  return (await client.post<ImportSummary>(`/api/universe/${type}/import`, form)).data;
}

export async function downloadExcel(type: "vehicles" | "vins", filters: Record<string, string | number | undefined>) {
  const response = await client.get(`/api/universe/${type}/export`, { params: filters, responseType: "blob" });
  saveBlob(response.data as Blob, `${type}.xlsx`);
}

function saveBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export async function downloadVinExportByVehicleList(file: File) {
  const form = new FormData();
  form.append("file", file);
  let response;
  try {
    response = await client.post<Blob>("/api/universe/vins/export-by-vehicle-list", form, { responseType: "blob" });
  } catch (error) {
    if (axios.isAxiosError(error) && error.response?.data instanceof Blob) {
      const body = await error.response.data.text();
      let detail: string | undefined;
      try {
        detail = (JSON.parse(body) as { detail?: string }).detail;
      } catch {
        detail = undefined;
      }
      if (detail) throw new Error(detail);
    }
    throw error;
  }
  saveBlob(response.data, "vins-by-vehicle-list.xlsx");
}

export interface Activity {
  id: number;
  user_id: number | null;
  username: string;
  action: string;
  detail: string;
  created_at: string;
}

export interface ActivityPage {
  items: Activity[];
  page: number;
  page_size: number;
  total: number;
  pages: number;
}

export async function getUniverseActivity(params: { page: number; page_size: number; search: string; username?: string }) {
  return (await client.get<ActivityPage>("/api/universe/activity", { params })).data;
}

export interface Oem {
  id: number;
  oem: string;
  description: string;
  notes: string;
  vins: { id: number; vin: string; is_valid: boolean; year: number; make: string; model: string }[];
  partslinks: string[];
  interchanges: string[];
  created_at: string;
  updated_at: string;
}

export interface OemImportSummary {
  vehicles_created: number;
  vins_created: number;
  created: number;
  updated: number;
  skipped: number;
  errors: string[];
}

export async function importOemsExcel(file: File) {
  const form = new FormData();
  form.append("file", file);
  return (await client.post<OemImportSummary>("/api/universe/oems/import", form)).data;
}

export async function downloadOemsExcel(params: { search: string; filters: string; sort_by: string; sort_dir: "asc" | "desc"; group_by_type: boolean }) {
  const response = await client.get<Blob>("/api/universe/oems/export", {
    params: { ...params, search: params.search || undefined },
    responseType: "blob",
  });
  saveBlob(response.data, "oems.xlsx");
}

export type ExportListType = "oem" | "partslink" | "interchange";

export async function downloadOemsByList(file: File, listType: ExportListType = "oem", groupByType = true) {
  const form = new FormData();
  form.append("file", file);
  form.append("list_type", listType);
  form.append("group_by_type", String(groupByType));
  let response;
  try {
    response = await client.post<Blob>("/api/universe/oems/export-by-list", form, { responseType: "blob" });
  } catch (error) {
    if (axios.isAxiosError(error) && error.response?.data instanceof Blob) {
      const body = await error.response.data.text();
      let detail: string | undefined;
      try {
        detail = (JSON.parse(body) as { detail?: string }).detail;
      } catch {
        detail = undefined;
      }
      if (detail) throw new Error(detail);
    }
    throw error;
  }
  saveBlob(response.data, `oems-by-${listType}.xlsx`);
}

export type OemValues = { id_vin: number | null; oem: string; description: string; notes: string; source_id_vin?: number | null };

export async function saveOem(id: number | null, values: OemValues) {
  const response = id === null
    ? await client.post<Oem>("/api/universe/oems", values)
    : await client.put<Oem>(`/api/universe/oems/${id}`, values);
  return response.data;
}

export async function deleteOem(id: number, vinId?: number | null) {
  const suffix = vinId == null ? "" : `/vins/${vinId}`;
  await client.delete(`/api/universe/oems/${id}${suffix}`);
}

export type CatalogKind = "partslinks" | "interchanges";

export interface CatalogRecord {
  id: number;
  partslink?: string;
  interchange?: string;
  description: string;
  notes: string;
  oems: string[];
  created_at: string;
  updated_at: string;
}

export interface CatalogImportSummary {
  catalogs_created: number;
  oems_created: number;
  links_created: number;
  vehicles_created: number;
  vins_created: number;
  fitments_created: number;
  updated: number;
  skipped: number;
  errors: string[];
}

export interface CatalogPair {
  id_partslink: number;
  partslink: string;
  id_interchange: number;
  interchange: string;
  distinct_oem_count: number;
}

export async function getCatalogPage(kind: CatalogKind, params: {
  page: number;
  page_size: number;
  search: string;
  filters?: string;
  sort_by?: string;
  sort_dir?: "asc" | "desc";
}) {
  return (await client.get<Page<CatalogRecord>>(`/api/universe/${kind}`, { params })).data;
}

export async function getCatalogPairPage(params: {
  page: number;
  page_size: number;
  search: string;
  filters?: string;
  sort_by?: string;
  sort_dir?: "asc" | "desc";
}) {
  return (await client.get<Page<CatalogPair>>("/api/universe/partslink-interchange", { params })).data;
}

export async function importCatalogExcel(kind: CatalogKind, file: File) {
  const form = new FormData();
  form.append("file", file);
  return (await client.post<CatalogImportSummary>(`/api/universe/${kind}/import`, form)).data;
}

export async function downloadCatalogExcel(kind: CatalogKind, params: { search: string; filters: string; sort_by: string; sort_dir: "asc" | "desc"; group_by_type: boolean }) {
  const response = await client.get<Blob>(`/api/universe/${kind}/export`, { params, responseType: "blob" });
  saveBlob(response.data, `${kind}.xlsx`);
}

export async function downloadCatalogPairsExcel(params: { search: string; filters: string; sort_by: string; sort_dir: "asc" | "desc" }) {
  const response = await client.get<Blob>("/api/universe/partslink-interchange/export", { params, responseType: "blob" });
  saveBlob(response.data, "partslink-interchange.xlsx");
}

export async function downloadCatalogByList(kind: CatalogKind, file: File, listType: ExportListType = "oem", groupByType = true) {
  const form = new FormData();
  form.append("file", file);
  form.append("list_type", listType);
  form.append("group_by_type", String(groupByType));
  const response = await client.post<Blob>(`/api/universe/${kind}/export-by-list`, form, { responseType: "blob" });
  saveBlob(response.data, `${kind}-by-${listType}.xlsx`);
}

export async function saveCatalog(kind: CatalogKind, id: number | null, values: { partslink?: string; interchange?: string; description: string; notes: string }) {
  const url = `/api/universe/${kind}`;
  const response = id === null
    ? await client.post<CatalogRecord>(url, values)
    : await client.put<CatalogRecord>(`${url}/${id}`, values);
  return response.data;
}

export async function deleteCatalog(kind: CatalogKind, id: number) {
  await client.delete(`/api/universe/${kind}/${id}`);
}

export async function exportCccVendorDashboard(params: {
  vendor: string;
  from_date: string;
  to_date: string;
  description: string;
}) {
  const response = await client.get<Blob>("/api/universe/market/ccc/vendor-dashboard/export", { params, responseType: "blob" });
  saveBlob(response.data, `ccc-dashboard-${params.vendor.trim().replace(/[^A-Za-z0-9_-]+/g, "-").replace(/^-|-$/g, "") || "vendor"}.xlsx`);
}