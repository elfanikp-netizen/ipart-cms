import { useEffect, useState } from "react";
import type { FormEvent, ReactNode } from "react";
import { Link, Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { client, deleteRecord, downloadExcel, downloadVinExportByVehicleList, errorText, getFilterOptions, getPage, getVehicleOptions, importExcel, saveVehicle, saveVin } from "./api";
import type { FilterOptions, ImportSummary, Page, Vehicle, VehicleOption, Vin } from "./api";
import CccMarketPage from "./pages/CccMarketPage";
import ActivityPage from "./pages/ActivityPage";
import OemPage from "./pages/OemPage";

type Dataset = "vehicles" | "vins" | "oem" | "ccc";
type MasterDataset = "vehicles" | "vins";
type VehicleDraft = { year: string; make: string; model: string; notes: string };
type VinDraft = { id_vehicle: string; vin: string; notes: string };

interface PortalUser { id: number; username: string; display_name: string; role: string; }

function App() {
  const [user, setUser] = useState<PortalUser | null>(null);
  const [checking, setChecking] = useState(true);
  const location = useLocation();
  const navigate = useNavigate();
  const activeDataset: Dataset = location.pathname === "/market/ccc"
    ? "ccc"
    : location.pathname === "/vins" ? "vins" : location.pathname === "/oem" ? "oem" : "vehicles";
  const activityActive = location.pathname === "/activity";

  useEffect(() => {
    client.get<PortalUser>("/api/auth/me")
      .then((response) => setUser(response.data))
      .catch(() => setUser(null))
      .finally(() => setChecking(false));
  }, []);

  if (checking) return <main className="boot-screen">Checking portal session</main>;
  if (!user) {
    window.location.replace("/login");
    return <main className="boot-screen">Opening Portal sign in</main>;
  }

  return (
    <div className="universe-shell">
      <aside className="sidebar">
        <Link to="/" className="brand-mark"><span className="brand-icon">U</span><span>UNIVERSE<small>MASTER DATA</small></span></Link>
        <div className="side-label">WORKSPACE</div>
        <div className="menu-parent"><span className="menu-parent-icon">▦</span>MASTER DATA</div>
        <nav className="subnav" aria-label="Master data">
          <button className={activeDataset === "vehicles" ? "active" : ""} onClick={() => navigate("/vehicles")}><span>01</span>Vehicle</button>
          <button className={activeDataset === "vins" ? "active" : ""} onClick={() => navigate("/vins")}><span>02</span>VIN</button>
          <button className={activeDataset === "oem" ? "active" : ""} onClick={() => navigate("/oem")}><span>03</span>OEM</button>
          <button className={activityActive ? "active" : ""} onClick={() => navigate("/activity")}><span>04</span>Activity</button>
        </nav>
        <div className="menu-parent market-menu-parent"><span className="menu-parent-icon">▤</span>MARKET</div>
        <nav className="subnav" aria-label="Market">
          <button className={activeDataset === "ccc" ? "active" : ""} onClick={() => navigate("/market/ccc")}><span>01</span>CCC</button>
        </nav>
        <div className="sidebar-bottom"><a href="/">← Portal home</a><span>IPART · DATA SERVICES</span></div>
      </aside>
      <main className="main-area">
        <header className="topbar"><div><span className="crumb">{activityActive ? "AUDIT" : activeDataset === "ccc" ? "MARKET" : "MASTER DATA"}</span><span className="crumb-divider">/</span><strong>{activityActive ? "Activity" : activeDataset === "vehicles" ? "Vehicle" : activeDataset === "vins" ? "VIN" : activeDataset === "oem" ? "OEM" : "CCC"}</strong></div><div className="top-user"><span className="user-avatar">{(user.display_name || user.username).slice(0, 1).toUpperCase()}</span><span>{user.display_name || user.username}</span><a href="/">Portal</a></div></header>
        <Routes>
          <Route path="/" element={<Navigate to="/vehicles" replace />} />
          <Route path="/vehicles" element={<MasterDataPage dataset="vehicles" />} />
          <Route path="/vins" element={<MasterDataPage dataset="vins" />} />
          <Route path="/oem" element={<OemPage />} />
          <Route path="/market/ccc" element={<CccMarketPage />} />
          <Route path="/activity" element={<ActivityPage isAdmin={user.role === "superadmin"} />} />
          <Route path="*" element={<Navigate to="/vehicles" replace />} />
        </Routes>
      </main>
    </div>
  );
}

function MasterDataPage({ dataset }: { dataset: MasterDataset }) {
  const [vehicles, setVehicles] = useState<Page<Vehicle>>({ items: [], page: 1, page_size: 10, total: 0, pages: 0 });
  const [vins, setVins] = useState<Page<Vin>>({ items: [], page: 1, page_size: 10, total: 0, pages: 0 });
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [year, setYear] = useState("");
  const [make, setMake] = useState("");
  const [model, setModel] = useState("");
  const [vehicleFilter, setVehicleFilter] = useState("");
  const [vehicleFilterId, setVehicleFilterId] = useState<number | undefined>();
  const [vehicleOptions, setVehicleOptions] = useState<VehicleOption[]>([]);
  const [filterOptions, setFilterOptions] = useState<FilterOptions>({ years: [], makes: [], models: [] });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [modal, setModal] = useState<Vehicle | Vin | null | "new">(null);
  const [importSummary, setImportSummary] = useState<ImportSummary | null>(null);
  const [importing, setImporting] = useState(false);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [showExportDialog, setShowExportDialog] = useState(false);
  const [exportMode, setExportMode] = useState<"all" | "list">("all");
  const [exportFile, setExportFile] = useState<File | null>(null);
  const [exportBusy, setExportBusy] = useState(false);

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const params = { page, page_size: 10, search, year: year ? Number(year) : undefined, make, model, vehicle_id: vehicleFilterId };
      if (dataset === "vehicles") setVehicles(await getPage<Vehicle>("/api/universe/vehicles", params));
      else setVins(await getPage<Vin>("/api/universe/vins", params));
    } catch (reason) {
      setError(errorText(reason));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 180);
    return () => window.clearTimeout(timer);
  }, [dataset, page, search, year, make, model, vehicleFilterId]);

  useEffect(() => {
    if (dataset !== "vins") return;
    getFilterOptions().then(setFilterOptions).catch((reason) => setError(errorText(reason)));
  }, [dataset]);

  useEffect(() => {
    if (dataset !== "vins") return;
    const timer = window.setTimeout(() => {
      getVehicleOptions(vehicleFilter, 50).then(setVehicleOptions).catch((reason) => setError(errorText(reason)));
    }, 180);
    return () => window.clearTimeout(timer);
  }, [dataset, vehicleFilter]);

  useEffect(() => {
    if (dataset !== "vins" || !vehicleFilter) return;
    const match = vehicleOptions.find((option) => option.label === vehicleFilter);
    if (match) setVehicleFilterId(match.id);
  }, [dataset, vehicleFilter, vehicleOptions]);

  const current = dataset === "vehicles" ? vehicles : vins;
  const clearFilters = () => { setSearch(""); setYear(""); setMake(""); setModel(""); setVehicleFilter(""); setVehicleFilterId(undefined); setPage(1); };

  const remove = async (id: number) => {
    const label = dataset === "vehicles" ? "vehicle and all linked VINs" : "VIN";
    if (!window.confirm(`Delete this ${label}?`)) return;
    setBusyId(id);
    setError("");
    try {
      await deleteRecord(dataset, id);
      setNotice(dataset === "vehicles" ? "Vehicle and linked VINs deleted." : "VIN deleted.");
      await load();
    } catch (reason) {
      setError(errorText(reason));
    } finally {
      setBusyId(null);
    }
  };

  const exportData = async () => {
    if (dataset === "vins") {
      setExportFile(null);
      setExportMode("all");
      setShowExportDialog(true);
      return;
    }
    try {
      await downloadExcel(dataset, { search, year: year || undefined, make, model });
    } catch (reason) {
      setError(errorText(reason));
    }
  };

  const submitVinExport = async () => {
    setExportBusy(true);
    setError("");
    try {
      if (exportMode === "all") {
        await downloadExcel("vins", {});
      } else if (exportFile) {
        await downloadVinExportByVehicleList(exportFile);
      } else {
        setError("Choose an Excel file containing Year, Make, and Model columns.");
        return;
      }
      setShowExportDialog(false);
    } catch (reason) {
      setError(errorText(reason));
    } finally {
      setExportBusy(false);
    }
  };

  const onImport = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    setImporting(true);
    setError("");
    setImportSummary(null);
    try {
      setImportSummary(await importExcel(dataset, file));
      setPage(1);
      await load();
    } catch (reason) {
      setError(errorText(reason));
    } finally {
      setImporting(false);
    }
  };

  const editVehicle = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const id = typeof modal === "object" && modal ? modal.id : null;
    try {
      await saveVehicle(id, {
        year: Number(form.get("year")),
        make: String(form.get("make") || ""),
        model: String(form.get("model") || ""),
        notes: String(form.get("notes") || ""),
      });
      setModal(null);
      setNotice(id === null ? "Vehicle created." : "Vehicle updated.");
      await load();
    } catch (reason) { setError(errorText(reason)); }
  };

  const editVin = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const id = typeof modal === "object" && modal ? modal.id : null;
    try {
      await saveVin(id, {
        id_vehicle: Number(form.get("id_vehicle")),
        vin: String(form.get("vin") || ""),
        notes: String(form.get("notes") || ""),
      });
      setModal(null);
      setNotice(id === null ? "VIN created." : "VIN updated.");
      await load();
    } catch (reason) { setError(errorText(reason)); }
  };

  const title = dataset === "vehicles" ? "Vehicles" : "VIN registry";
  const subtitle = dataset === "vehicles"
    ? "Maintain canonical vehicle fitment records."
    : "Manage VINs linked to year, make, and model.";

  return (
    <section className="content-wrap">
      <div className="page-heading"><div><p className="eyebrow">MASTER DATA / {dataset.toUpperCase()}</p><h1>{title}</h1><p>{subtitle}</p></div><div className="heading-count"><strong>{current.total.toLocaleString()}</strong><span>records</span></div></div>
      <div className="toolbar-row">
        <label className="search-box"><span>⌕</span><input value={search} onChange={(event) => { setSearch(event.target.value); setPage(1); }} placeholder={dataset === "vehicles" ? "Search year, make, model" : "Search VIN or vehicle"} /></label>
        {dataset === "vehicles" ? <input className="filter-input year-filter" inputMode="numeric" placeholder="Year" value={year} onChange={(event) => { setYear(event.target.value.replace(/\D/g, "").slice(0, 4)); setPage(1); }} /> : <><input className="filter-input year-filter" list="vin-years" inputMode="numeric" placeholder="Year" value={year} onChange={(event) => { setYear(event.target.value.replace(/\D/g, "").slice(0, 4)); setPage(1); }} /><datalist id="vin-years">{filterOptions.years.map((item) => <option key={item} value={item} />)}</datalist></>}
        {dataset === "vehicles" ? <input className="filter-input" placeholder="Make" value={make} onChange={(event) => { setMake(event.target.value); setPage(1); }} /> : <><input className="filter-input" list="vin-makes" placeholder="Make" value={make} onChange={(event) => { setMake(event.target.value); setPage(1); }} /><datalist id="vin-makes">{filterOptions.makes.map((item) => <option key={item} value={item} />)}</datalist></>}
        {dataset === "vins" && <>
          <input className="filter-input" list="vin-models" placeholder="Model" value={model} onChange={(event) => { setModel(event.target.value); setPage(1); }} /><datalist id="vin-models">{filterOptions.models.map((item) => <option key={item} value={item} />)}</datalist>
          <input className="filter-input vehicle-filter" list="vin-vehicles" placeholder="Vehicle" value={vehicleFilter} onChange={(event) => { const value = event.target.value; setVehicleFilter(value); const match = vehicleOptions.find((option) => option.label === value); setVehicleFilterId(match?.id); setPage(1); }} /><datalist id="vin-vehicles">{vehicleOptions.map((option) => <option key={option.id} value={option.label} />)}</datalist>
        </>}
        <button className="text-button" onClick={clearFilters}>Clear</button>
        <div className="toolbar-spacer" />
        <label className={`outline-button file-button${importing ? " disabled" : ""}`}>
          {importing ? "Importing…" : "↑ Import Excel"}
          <input type="file" accept=".xlsx,.xlsm" onChange={onImport} disabled={importing} />
        </label>
        <button className="outline-button" onClick={() => void exportData()}>↓ Export Excel</button>
        <button className="primary-button" onClick={() => setModal("new")}>＋ Add {dataset === "vehicles" ? "vehicle" : "VIN"}</button>
      </div>
      {error && <div className="alert error-alert" role="alert">{error}</div>}
      {notice && <div className="alert success-alert" role="status">{notice}<button onClick={() => setNotice("")} aria-label="Dismiss message">×</button></div>}
      {importSummary && <div className="import-summary"><div><strong>Import complete</strong><span>{importSummary.created} created</span><span>{importSummary.updated} updated</span><span>{importSummary.skipped} unchanged/skipped</span>{dataset === "vins" && <span>{importSummary.vehicles_created} vehicles added</span>}</div>{importSummary.errors.length > 0 && <details><summary>{importSummary.errors.length} row issue(s)</summary><ul>{importSummary.errors.map((item) => <li key={item}>{item}</li>)}</ul></details>}<button onClick={() => setImportSummary(null)} aria-label="Dismiss import report">×</button></div>}
      <div className="table-frame">
        <table>
          <thead><tr>{dataset === "vehicles" ? <><th>YEAR</th><th>MAKE</th><th>MODEL</th><th>VINS</th><th>UPDATED</th></> : <><th>YEAR</th><th>MAKE</th><th>MODEL</th><th>VIN</th><th>UPDATED</th></>}<th aria-label="Actions" /></tr></thead>
          <tbody>
            {loading ? <tr><td className="empty-state" colSpan={6}>Loading records…</td></tr> : current.items.length === 0 ? <tr><td className="empty-state" colSpan={6}>No records match these filters.</td></tr> : dataset === "vehicles" ? (vehicles.items as Vehicle[]).map((vehicle) => <tr key={vehicle.id}>
              <td className="year-cell">{vehicle.year}</td><td>{vehicle.make}</td><td>{vehicle.model}</td><td><span className="count-pill">{vehicle.vin_count}</span></td><td className="updated-cell">{new Date(vehicle.updated_at).toLocaleDateString()}</td><td className="row-actions"><button onClick={() => { setModal(vehicle); setNotice(""); }}>Edit</button><button className="delete-action" disabled={busyId === vehicle.id} onClick={() => void remove(vehicle.id)}>Delete</button></td>
            </tr>) : (vins.items as Vin[]).map((item) => <tr key={item.id}>
              <td className="year-cell">{item.vehicle.year}</td><td>{item.vehicle.make}</td><td>{item.vehicle.model}</td><td className="vin-cell">{item.vin}</td><td className="updated-cell">{new Date(item.updated_at).toLocaleDateString()}</td><td className="row-actions"><button onClick={() => { setModal(item); setNotice(""); }}>Edit</button><button className="delete-action" disabled={busyId === item.id} onClick={() => void remove(item.id)}>Delete</button></td>
            </tr>)}
          </tbody>
        </table>
      </div>
      <div className="table-footer"><span>{current.total === 0 ? "0 records" : `${((page - 1) * 10) + 1}–${Math.min(page * 10, current.total)} of ${current.total.toLocaleString()}`}</span><div><button disabled={page <= 1 || loading} onClick={() => setPage((value) => value - 1)}>← Previous</button><span>Page {page}{current.pages ? ` of ${current.pages}` : ""}</span><button disabled={page >= current.pages || loading} onClick={() => setPage((value) => value + 1)}>Next →</button></div></div>
      {modal !== null && <Modal title={`${modal === "new" ? "Add" : "Edit"} ${dataset === "vehicles" ? "vehicle" : "VIN"}`} onClose={() => setModal(null)}>
        {dataset === "vehicles" ? <VehicleForm value={modal === "new" ? null : modal as Vehicle} onSubmit={editVehicle} onCancel={() => setModal(null)} /> : <VinForm value={modal === "new" ? null : modal as Vin} onSubmit={editVin} onCancel={() => setModal(null)} />}
      </Modal>}
      {showExportDialog && <Modal title="Export VINs" onClose={() => setShowExportDialog(false)}><div className="export-options"><label className={`export-choice${exportMode === "all" ? " selected" : ""}`}><input type="radio" name="vin-export-mode" checked={exportMode === "all"} onChange={() => setExportMode("all")} /><span><strong>All VIN records</strong><small>Export every VIN and its related vehicle.</small></span></label><label className={`export-choice${exportMode === "list" ? " selected" : ""}`}><input type="radio" name="vin-export-mode" checked={exportMode === "list"} onChange={() => setExportMode("list")} /><span><strong>Vehicle list from Excel</strong><small>Export VINs for Year/Make/Model rows in a workbook.</small></span></label>{exportMode === "list" && <label className="vehicle-list-upload">Excel file<input type="file" accept=".xlsx,.xlsm" onChange={(event) => setExportFile(event.target.files?.[0] ?? null)} /><small>Required columns: Year, Make, Model{exportFile ? ` · ${exportFile.name}` : ""}</small></label>}</div><div className="modal-actions"><button type="button" className="outline-button" onClick={() => setShowExportDialog(false)}>Cancel</button><button type="button" className="primary-button" disabled={exportBusy || (exportMode === "list" && !exportFile)} onClick={() => void submitVinExport()}>{exportBusy ? "Preparing…" : "Export VINs"}</button></div></Modal>}
    </section>
  );
}

function Modal({ title, children, onClose }: { title: string; children: ReactNode; onClose: () => void }) {
  return <div className="modal-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}><section className="modal" role="dialog" aria-modal="true" aria-labelledby="modal-title"><header><div><p className="eyebrow">MASTER DATA</p><h2 id="modal-title">{title}</h2></div><button className="close-button" onClick={onClose} aria-label="Close dialog">×</button></header>{children}</section></div>;
}

function VehicleForm({ value, onSubmit, onCancel }: { value: Vehicle | null; onSubmit: (event: FormEvent<HTMLFormElement>) => void; onCancel: () => void }) {
  return <form className="record-form" onSubmit={onSubmit}><div className="form-grid"><label>Year<input name="year" type="number" min="1886" max="2100" defaultValue={value?.year ?? ""} required /></label><label>Make<input name="make" maxLength={100} defaultValue={value?.make ?? ""} required /></label><label className="full-field">Model<input name="model" maxLength={150} defaultValue={value?.model ?? ""} required /></label><label className="full-field">Notes<textarea name="notes" rows={3} defaultValue={value?.notes ?? ""} /></label></div><div className="modal-actions"><button type="button" className="outline-button" onClick={onCancel}>Cancel</button><button className="primary-button">Save vehicle</button></div></form>;
}

function VinForm({ value, onSubmit, onCancel }: { value: Vin | null; onSubmit: (event: FormEvent<HTMLFormElement>) => void; onCancel: () => void }) {
  const [vehicleSearch, setVehicleSearch] = useState(value ? `${value.vehicle.year} ${value.vehicle.make} ${value.vehicle.model}` : "");
  const [selectedVehicle, setSelectedVehicle] = useState(value ? String(value.id_vehicle) : "");
  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [vehicleListOpen, setVehicleListOpen] = useState(false);
  const [loadError, setLoadError] = useState("");
  useEffect(() => {
    const timer = window.setTimeout(() => {
      getPage<Vehicle>("/api/universe/vehicles", { page: 1, page_size: 100, search: vehicleSearch })
        .then((result) => { setVehicles(result.items); setLoadError(""); })
        .catch((reason) => setLoadError(errorText(reason)));
    }, 200);
    return () => window.clearTimeout(timer);
  }, [vehicleSearch]);
  return <form className="record-form" onSubmit={(event) => { if (!selectedVehicle) { event.preventDefault(); setVehicleListOpen(true); return; } onSubmit(event); }}><div className="form-grid"><label className="full-field vehicle-picker">Vehicle<input name="vehicle_search" role="combobox" aria-autocomplete="list" aria-expanded={vehicleListOpen} aria-controls="vin-vehicle-options" value={vehicleSearch} onFocus={() => setVehicleListOpen(true)} onBlur={() => window.setTimeout(() => setVehicleListOpen(false), 120)} onChange={(event) => { setVehicleSearch(event.target.value); setSelectedVehicle(""); setVehicleListOpen(true); }} placeholder="Search year, make, or model" autoComplete="off" required /><input type="hidden" name="id_vehicle" value={selectedVehicle} />{vehicleListOpen && <div id="vin-vehicle-options" className="vehicle-picker-options" role="listbox">{vehicles.length ? vehicles.map((vehicle) => <button key={vehicle.id} type="button" role="option" aria-selected={selectedVehicle === String(vehicle.id)} onMouseDown={(event) => event.preventDefault()} onClick={() => { setSelectedVehicle(String(vehicle.id)); setVehicleSearch(`${vehicle.year} ${vehicle.make} ${vehicle.model}`); setVehicleListOpen(false); }}>{vehicle.year} {vehicle.make} {vehicle.model}</button>) : <span className="vehicle-picker-empty">{loadError || "No matching vehicles"}</span>}</div>}{loadError && <small className="field-error">{loadError}</small>}{!selectedVehicle && <small className="field-error">Select a vehicle from the search results.</small>}</label><label className="full-field">VIN<input name="vin" maxLength={32} minLength={5} pattern="[A-Za-z0-9]{5,32}" defaultValue={value?.vin ?? ""} required /></label><label className="full-field">Notes<textarea name="notes" rows={3} defaultValue={value?.notes ?? ""} /></label></div><div className="modal-actions"><button type="button" className="outline-button" onClick={onCancel}>Cancel</button><button className="primary-button">Save VIN</button></div></form>;
}

export default App;