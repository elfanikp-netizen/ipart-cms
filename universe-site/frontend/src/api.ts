import axios from "axios";

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

export interface CccMarketFilters {
  oems: string[];
  vins: string[];
  descriptions: string[];
  vendors: string[];
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
  vendor: string;
  description: string;
  price: string;
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

export async function getCccMarketFilters() {
  return (await client.get<CccMarketFilters>("/api/universe/market/ccc/filters")).data;
}

export async function getCccMarketOffers(group: Pick<CccMarketRecord, "oem" | "vin" | "crawl_date">) {
  return (await client.get<CccMarketOffer[]>("/api/universe/market/ccc/offers", { params: group })).data;
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
  const response = await client.post<Blob>("/api/universe/vins/export-by-vehicle-list", form, { responseType: "blob" });
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