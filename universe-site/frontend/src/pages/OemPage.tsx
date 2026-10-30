import { useEffect, useState } from "react";
import { client, deleteOem, downloadOemsByList, downloadOemsExcel, errorText, importOemsExcel } from "../api";
import type { Oem, OemImportSummary, Page } from "../api";
import OemForm from "../components/OemForm";

const PAGE_SIZE = 10;
const EMPTY_PAGE: Page<Oem> = { items: [], page: 1, page_size: PAGE_SIZE, total: 0, pages: 0 };

export default function OemPage() {
  const [data, setData] = useState(EMPTY_PAGE);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [importing, setImporting] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState("");
  const [summary, setSummary] = useState<OemImportSummary | null>(null);
  const [showExportDialog, setShowExportDialog] = useState(false);
  const [exportFile, setExportFile] = useState<File | null>(null);
  const [modal, setModal] = useState<Oem | null | "new">(null);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [notice, setNotice] = useState("");

  const load = async () => {
    setLoading(true);
    try {
      const response = await client.get<Page<Oem>>("/api/universe/oems", {
        params: { page, page_size: PAGE_SIZE, search },
      });
      setData(response.data);
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
  }, [page, search]);

  const onImport = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    setImporting(true);
    setError("");
    setSummary(null);
    try {
      setSummary(await importOemsExcel(file));
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
      await downloadOemsExcel(search);
    } catch (reason) {
      setError(errorText(reason));
    } finally {
      setExporting(false);
    }
  };

  const exportList = async () => {
    if (!exportFile) return;
    setExporting(true);
    setError("");
    try {
      await downloadOemsByList(exportFile);
      setShowExportDialog(false);
    } catch (reason) {
      setError(errorText(reason));
    } finally {
      setExporting(false);
    }
  };

  const onSaved = async (item: Oem) => {
    setModal(null);
    setNotice(`${item.oem} ${item.id ? "saved" : "created"}.`);
    await load();
  };

  const remove = async (item: Oem) => {
    if (!window.confirm(`Delete OEM ${item.oem} linked to VIN ${item.vin}?`)) return;
    setBusyId(item.id);
    setError("");
    try {
      await deleteOem(item.id);
      setNotice(`OEM ${item.oem} deleted.`);
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
        <div><p className="eyebrow">MASTER DATA / OEM</p><h1>OEM registry</h1><p>OEM numbers linked to VINs and vehicle fitment.</p></div>
        <div className="heading-count"><strong>{data.total.toLocaleString()}</strong><span>records</span></div>
      </div>
      <div className="toolbar-row">
        <label className="search-box"><span>⌕</span><input value={search} onChange={(event) => { setSearch(event.target.value); setPage(1); }} placeholder="Search OEM, VIN, vehicle" /></label>
        <div className="toolbar-spacer" />
        <button className="primary-button" onClick={() => { setNotice(""); setModal("new"); }}>＋ Add OEM</button>
        <label className={`outline-button file-button${importing ? " disabled" : ""}`}>
          {importing ? "Importing…" : "↑ Import Excel"}
          <input type="file" accept=".xlsx,.xlsm" onChange={onImport} disabled={importing} />
        </label>
        <button className="outline-button" disabled={exporting} onClick={() => { setExportFile(null); setShowExportDialog(true); }}>↓ Export Excel</button>
      </div>
      {error && <div className="alert error-alert" role="alert">{error}</div>}
      {notice && <div className="alert success-alert" role="status">{notice}<button onClick={() => setNotice("")} aria-label="Dismiss message">×</button></div>}
      {summary && <div className="import-summary"><div><strong>Import complete</strong><span>{summary.created} created</span><span>{summary.updated} updated</span><span>{summary.skipped} unchanged/skipped</span><span>{summary.vehicles_created} vehicles added</span><span>{summary.vins_created} VINs added</span></div>{summary.errors.length > 0 && <details><summary>{summary.errors.length} row issue(s)</summary><ul>{summary.errors.map((item) => <li key={item}>{item}</li>)}</ul></details>}<button onClick={() => setSummary(null)} aria-label="Dismiss import report">×</button></div>}
      <div className="table-frame">
        <table>
          <thead><tr><th>OEM</th><th>VIN</th><th>YEAR</th><th>MAKE</th><th>MODEL</th><th>DESCRIPTION</th><th>UPDATED</th><th aria-label="Actions" /></tr></thead>
          <tbody>
            {loading ? <tr><td className="empty-state" colSpan={8}>Loading records…</td></tr> : data.items.length === 0 ? <tr><td className="empty-state" colSpan={8}>No OEM records match this search.</td></tr> : data.items.map((item) => <tr key={item.id}>
              <td className="vin-cell">{item.oem}</td><td className="vin-cell">{item.vin}</td><td className="year-cell">{item.year}</td><td>{item.make}</td><td>{item.model}</td><td>{item.description}</td><td className="updated-cell">{new Date(item.updated_at).toLocaleDateString()}</td><td className="row-actions"><button onClick={() => { setNotice(""); setModal(item); }}>Edit</button><button className="delete-action" disabled={busyId === item.id} onClick={() => void remove(item)}>Delete</button></td>
            </tr>)}
          </tbody>
        </table>
      </div>
      <div className="table-footer"><span>{data.total === 0 ? "0 records" : `${first}–${last} of ${data.total.toLocaleString()}`}</span><div><button disabled={page <= 1 || loading} onClick={() => setPage((value) => value - 1)}>← Previous</button><span>Page {page}{data.pages ? ` of ${data.pages}` : ""}</span><button disabled={page >= data.pages || loading} onClick={() => setPage((value) => value + 1)}>Next →</button></div></div>
      {modal !== null && <div className="modal-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) setModal(null); }}><section className="modal" role="dialog" aria-modal="true" aria-labelledby="oem-form-title"><header><div><p className="eyebrow">MASTER DATA / OEM</p><h2 id="oem-form-title">{modal === "new" ? "Add OEM" : "Edit OEM"}</h2></div><button className="close-button" onClick={() => setModal(null)} aria-label="Close dialog">×</button></header><OemForm value={modal === "new" ? null : modal} onSaved={onSaved} onCancel={() => setModal(null)} /></section></div>}
      {showExportDialog && <div className="modal-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) setShowExportDialog(false); }}><section className="modal" role="dialog" aria-modal="true" aria-labelledby="oem-export-title"><header><div><p className="eyebrow">MASTER DATA</p><h2 id="oem-export-title">Export OEMs</h2></div><button className="close-button" onClick={() => setShowExportDialog(false)} aria-label="Close dialog">×</button></header><div className="export-options"><button className="export-choice" disabled={exporting} onClick={() => void exportAll()}><span><strong>Current search results</strong><small>Export OEM records matching the search field.</small></span></button><label className="export-choice"><span><strong>OEM list from Excel</strong><small>Upload a workbook with an OEM column. Add VIN to narrow each OEM to a specific vehicle.</small></span><input type="file" accept=".xlsx,.xlsm" onChange={(event) => setExportFile(event.target.files?.[0] ?? null)} /><small>{exportFile ? exportFile.name : "Required column: OEM · Optional column: VIN"}</small></label></div><div className="modal-actions"><button type="button" className="outline-button" onClick={() => setShowExportDialog(false)}>Cancel</button><button type="button" className="primary-button" disabled={exporting || !exportFile} onClick={() => void exportList()}>{exporting ? "Preparing…" : "Export selected OEMs"}</button></div></section></div>}
    </section>
  );
}
