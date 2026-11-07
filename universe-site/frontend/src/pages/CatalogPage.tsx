import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { client, deleteCatalog, downloadCatalogByOem, downloadCatalogExcel, errorText, getCatalogPage, importCatalogExcel, saveCatalog } from "../api";
import type { CatalogImportSummary, CatalogKind, CatalogRecord, Page } from "../api";
import ColumnHeader from "../components/ColumnHeader";
import type { ColumnFilterValue } from "../components/ColumnHeader";

const PAGE_SIZE = 10;
const EMPTY_PAGE: Page<CatalogRecord> = { items: [], page: 1, page_size: PAGE_SIZE, total: 0, pages: 0 };

export default function CatalogPage({ kind }: { kind: CatalogKind }) {
  const isPartslink = kind === "partslinks";
  const label = isPartslink ? "Partslink" : "Interchange";
  const valueField = isPartslink ? "partslink" : "interchange";
  const [data, setData] = useState(EMPTY_PAGE);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [columnFilters, setColumnFilters] = useState<Record<string, ColumnFilterValue>>({});
  const [sort, setSort] = useState<{ field: string; direction: "asc" | "desc" }>({ field: "", direction: "asc" });
  const [loading, setLoading] = useState(true);
  const [importing, setImporting] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [summary, setSummary] = useState<CatalogImportSummary | null>(null);
  const [modal, setModal] = useState<CatalogRecord | null | "new">(null);
  const [showExport, setShowExport] = useState(false);
  const [exportFile, setExportFile] = useState<File | null>(null);
  const [exportMode, setExportMode] = useState<"all" | "oem-list">("all");
  const [busyId, setBusyId] = useState<number | null>(null);

  const load = async () => {
    setLoading(true);
    try {
      setData(await getCatalogPage(kind, {
        page, page_size: PAGE_SIZE, search, filters: JSON.stringify(columnFilters),
        sort_by: sort.field, sort_dir: sort.direction,
      }));
      setError("");
    } catch (reason) {
      setError(errorText(reason));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 180);
    return () => window.clearTimeout(timer);
  }, [kind, page, search, columnFilters, sort]);

  const updateColumnFilter = (field: string, value: ColumnFilterValue) => {
    setColumnFilters((current) => ({ ...current, [field]: value }));
    setPage(1);
  };

  const updateSort = (field: string) => {
    setSort((current) => ({ field, direction: current.field === field && current.direction === "asc" ? "desc" : "asc" }));
    setPage(1);
  };

  const onImport = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    setImporting(true);
    setError("");
    setSummary(null);
    try {
      setSummary(await importCatalogExcel(kind, file));
      setPage(1);
      await load();
    } catch (reason) {
      setError(errorText(reason));
    } finally {
      setImporting(false);
    }
  };

  const exportAll = async () => {
    setExporting(true);
    setError("");
    try {
      await downloadCatalogExcel(kind, { search, filters: JSON.stringify(columnFilters), sort_by: sort.field, sort_dir: sort.direction });
      setShowExport(false);
    } catch (reason) {
      setError(errorText(reason));
    } finally {
      setExporting(false);
    }
  };

  const exportByOem = async () => {
    if (!exportFile) return;
    setExporting(true);
    setError("");
    try {
      await downloadCatalogByOem(kind, exportFile);
      setShowExport(false);
    } catch (reason) {
      setError(errorText(reason));
    } finally {
      setExporting(false);
    }
  };

  const submitExport = () => {
    if (exportMode === "all") void exportAll();
    else void exportByOem();
  };

  const save = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const id = typeof modal === "object" && modal ? modal.id : null;
    const values = {
      [valueField]: String(form.get(valueField) || ""),
      description: String(form.get("description") || ""),
      notes: String(form.get("notes") || ""),
    };
    try {
      await saveCatalog(kind, id, values);
      setModal(null);
      setNotice(`${label} ${id === null ? "created" : "updated"}.`);
      await load();
    } catch (reason) {
      setError(errorText(reason));
    }
  };

  const remove = async (record: CatalogRecord) => {
    const number = record[valueField as "partslink" | "interchange"];
    if (!window.confirm(`Delete ${label} ${number}? OEM links to this catalog number will also be removed.`)) return;
    setBusyId(record.id);
    setError("");
    try {
      await deleteCatalog(kind, record.id);
      setNotice(`${label} ${number} deleted.`);
      await load();
    } catch (reason) {
      setError(errorText(reason));
    } finally {
      setBusyId(null);
    }
  };

  const first = data.total ? (page - 1) * PAGE_SIZE + 1 : 0;
  const last = Math.min(page * PAGE_SIZE, data.total);

  return (
    <section className="content-wrap">
      <div className="page-heading">
        <div><p className="eyebrow">MASTER DATA / {label.toUpperCase()}</p><h1>{label}</h1><p>{isPartslink ? "Partslink numbers and their OEM mappings." : "Hollander interchange groups and their OEM mappings."}</p></div>
        <div className="heading-count"><strong>{data.total.toLocaleString()}</strong><span>records</span></div>
      </div>
      <div className="toolbar-row">
        <label className="search-box"><span>⌕</span><input value={search} onChange={(event) => { setSearch(event.target.value); setPage(1); }} placeholder={`Search ${label}, OEM, description`} /></label>
        <div className="toolbar-spacer" />
        <button className="primary-button" onClick={() => { setNotice(""); setModal("new"); }}>＋ Add {label}</button>
        <label className={`outline-button file-button${importing ? " disabled" : ""}`}>
          {importing ? "Importing…" : "↑ Import Excel"}
          <input type="file" accept=".xlsx,.xlsm" onChange={onImport} disabled={importing} />
        </label>
        <button className="outline-button" disabled={exporting} onClick={() => { setExportFile(null); setExportMode("all"); setShowExport(true); }}>↓ Export Excel</button>
      </div>
      {error && <div className="alert error-alert" role="alert">{error}</div>}
      {notice && <div className="alert success-alert" role="status">{notice}<button onClick={() => setNotice("")} aria-label="Dismiss message">×</button></div>}
      {summary && <div className="import-summary"><div><strong>Import complete</strong><span>{summary.catalogs_created} catalog numbers added</span><span>{summary.oems_created} OEMs added</span><span>{summary.links_created} catalog mappings added</span><span>{summary.vehicles_created} vehicles added</span><span>{summary.vins_created} VINs added</span><span>{summary.fitments_created} OEM/VIN fitments added</span><span>{summary.updated} updated</span><span>{summary.skipped} unchanged/skipped</span></div>{summary.errors.length > 0 && <details><summary>{summary.errors.length} row issue(s)</summary><ul>{summary.errors.map((item) => <li key={item}>{item}</li>)}</ul></details>}<button onClick={() => setSummary(null)} aria-label="Dismiss import report">×</button></div>}
      <div className="table-frame">
        <table>
          <thead><tr>{[[valueField, label.toUpperCase()], ["description", "DESCRIPTION"], ["oems", "OEM MAPPINGS"], ["updated_at", "UPDATED"]].map(([field, heading]) => <ColumnHeader key={field} field={field} label={heading} filter={columnFilters[field] ?? { value: "", mode: "any" }} sort={sort} onFilter={updateColumnFilter} onSort={updateSort} />)}<th aria-label="Actions" /></tr></thead>
          <tbody>
            {loading ? <tr><td className="empty-state" colSpan={5}>Loading records…</td></tr> : data.items.length === 0 ? <tr><td className="empty-state" colSpan={5}>No {label} records match this search.</td></tr> : data.items.map((item) => <tr key={item.id}>
              <td className="vin-cell">{item[valueField as "partslink" | "interchange"]}</td><td>{item.description}</td><td>{item.oems.join(", ") || "No OEM mappings"}</td><td className="updated-cell">{new Date(item.updated_at).toLocaleDateString()}</td><td className="row-actions"><button onClick={() => { setError(""); setModal(item); }}>Edit</button><button className="delete-action" disabled={busyId === item.id} onClick={() => void remove(item)}>Delete</button></td>
            </tr>)}
          </tbody>
        </table>
      </div>
      <div className="table-footer"><span>{data.total === 0 ? "0 records" : `${first}–${last} of ${data.total.toLocaleString()}`}</span><div><button disabled={page <= 1 || loading} onClick={() => setPage((value) => value - 1)}>← Previous</button><span>Page {page}{data.pages ? ` of ${data.pages}` : ""}</span><button disabled={page >= data.pages || loading} onClick={() => setPage((value) => value + 1)}>Next →</button></div></div>
      {modal !== null && <div className="modal-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) setModal(null); }}><section className="modal" role="dialog" aria-modal="true" aria-labelledby="catalog-form-title"><header><div><p className="eyebrow">MASTER DATA / {label.toUpperCase()}</p><h2 id="catalog-form-title">{modal === "new" ? `Add ${label}` : `Edit ${label}`}</h2></div><button className="close-button" onClick={() => setModal(null)} aria-label="Close dialog">×</button></header><form className="record-form" onSubmit={save}><div className="form-grid"><label className="full-field">{label}<input name={valueField} maxLength={150} defaultValue={modal === "new" ? "" : modal[valueField as "partslink" | "interchange"] ?? ""} required /></label><label className="full-field">Description<input name="description" maxLength={4000} defaultValue={modal === "new" ? "" : modal.description} /></label><label className="full-field">Notes<textarea name="notes" rows={3} maxLength={4000} defaultValue={modal === "new" ? "" : modal.notes} /></label></div><div className="modal-actions"><button type="button" className="outline-button" onClick={() => setModal(null)}>Cancel</button><button className="primary-button">Save {label}</button></div></form></section></div>}
      {showExport && <div className="modal-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) setShowExport(false); }}><section className="modal" role="dialog" aria-modal="true" aria-labelledby="catalog-export-title"><header><div><p className="eyebrow">MASTER DATA</p><h2 id="catalog-export-title">Export {label}</h2></div><button className="close-button" onClick={() => setShowExport(false)} aria-label="Close dialog">×</button></header><div className="export-options"><label className={`export-choice${exportMode === "all" ? " selected" : ""}`}><input type="radio" name={`${kind}-export-mode`} checked={exportMode === "all"} onChange={() => setExportMode("all")} /><span><strong>Current search results</strong><small>Export {label} records matching the current search, filters, and sort order.</small></span></label><label className={`export-choice${exportMode === "oem-list" ? " selected" : ""}`}><input type="radio" name={`${kind}-export-mode`} checked={exportMode === "oem-list"} onChange={() => setExportMode("oem-list")} /><span><strong>Filter by OEM list</strong><small>Upload a workbook to export its linked {label} mappings.</small></span></label>{exportMode === "oem-list" && <label className="vehicle-list-upload">Excel file<input type="file" accept=".xlsx,.xlsm" onChange={(event) => setExportFile(event.target.files?.[0] ?? null)} /><small>Required column: OEM{exportFile ? ` · ${exportFile.name}` : ""}</small></label>}</div><div className="modal-actions"><button type="button" className="outline-button" onClick={() => setShowExport(false)}>Cancel</button><button type="button" className="primary-button" disabled={exporting || (exportMode === "oem-list" && !exportFile)} onClick={submitExport}>{exporting ? "Preparing…" : `Export ${label}`}</button></div></section></div>}
    </section>
  );
}
