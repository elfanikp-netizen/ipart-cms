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