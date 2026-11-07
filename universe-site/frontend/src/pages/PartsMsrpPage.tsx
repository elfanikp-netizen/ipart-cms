import { useEffect, useState } from "react";
import { errorText, exportPartsMsrpByOemList, exportPartsMsrpExcel, getPartsMsrpPage, importPartsMsrpExcel } from "../api";
import type { PartsMsrpImportSummary, PartsMsrpRecord } from "../api";
import ColumnHeader from "../components/ColumnHeader";
import type { ColumnFilterValue } from "../components/ColumnHeader";

const PAGE_SIZE = 25;
const COLUMNS = [
  ["oem", "OEM"],
  ["fitments", "FITMENTS"],
  ["msrp", "MSRP"],
  ["previous_msrp", "PREVIOUS MSRP"],
  ["ccc_price", "CCC PRICE"],
  ["previous_ccc_price", "PREVIOUS CCC PRICE"],
  ["gap_msrp", "GAP MSRP"],
  ["gap_ccc", "GAP CCC"],
  ["crawl_date", "CRAWL DATE"],
] as const;
const EMPTY_FILTER: ColumnFilterValue = { value: "", mode: "any" };

function money(value: string | null): string {
  if (value === null) return "—";
  const amount = Number(value);
  return Number.isFinite(amount)
    ? new Intl.NumberFormat(undefined, { style: "currency", currency: "USD" }).format(amount)
    : value;
}

export default function PartsMsrpPage() {
  const [items, setItems] = useState<PartsMsrpRecord[]>([]);
  const [search, setSearch] = useState("");
  const [columnFilters, setColumnFilters] = useState<Record<string, ColumnFilterValue>>({});
  const [sort, setSort] = useState<{ field: string; direction: "asc" | "desc" }>({ field: "", direction: "desc" });
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [pages, setPages] = useState(0);
  const [loading, setLoading] = useState(true);
  const [importing, setImporting] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState("");
  const [report, setReport] = useState<PartsMsrpImportSummary | null>(null);
  const [showExportDialog, setShowExportDialog] = useState(false);
  const [exportMode, setExportMode] = useState<"all" | "list">("all");
  const [exportFile, setExportFile] = useState<File | null>(null);

  useEffect(() => {
    let current = true;
    setLoading(true);
    getPartsMsrpPage({
      page,
      page_size: PAGE_SIZE,
      search,
      filters: JSON.stringify(columnFilters),
      sort_by: sort.field,
      sort_dir: sort.direction,
    })
      .then((result) => {
        if (!current) return;
        setItems(result.items);
        setTotal(result.total);
        setPages(result.pages);
        setError("");
      })
      .catch((reason) => { if (current) setError(errorText(reason)); })
      .finally(() => { if (current) setLoading(false); });
    return () => { current = false; };
  }, [page, search, columnFilters, sort]);

  const updateColumnFilter = (field: string, value: ColumnFilterValue) => {
    setColumnFilters((current) => ({ ...current, [field]: value }));
    setPage(1);
  };

  const updateSort = (field: string) => {
    setSort((current) => ({
      field,
      direction: current.field === field && current.direction === "asc" ? "desc" : "asc",
    }));
    setPage(1);
  };

  const onImport = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    setImporting(true);
    setError("");
    setReport(null);
    try {
      setReport(await importPartsMsrpExcel(file));
      setPage(1);
      const refreshed = await getPartsMsrpPage({
        page: 1,
        page_size: PAGE_SIZE,
        search,
        filters: JSON.stringify(columnFilters),
        sort_by: sort.field,
        sort_dir: sort.direction,
      });
      setItems(refreshed.items);
      setTotal(refreshed.total);
      setPages(refreshed.pages);
    } catch (reason) {
      setError(errorText(reason));
    } finally {
      setImporting(false);
    }
  };

  const exportRows = async () => {
    setExporting(true);
    setError("");
    try {
      await exportPartsMsrpExcel({
        search,
        filters: JSON.stringify(columnFilters),
        sort_by: sort.field,
        sort_dir: sort.direction,
      });
      setShowExportDialog(false);
    } catch (reason) {
      setError(errorText(reason));
    } finally {
      setExporting(false);
    }
  };

  const exportByOemList = async () => {
    if (!exportFile) return;
    setExporting(true);
    setError("");
    try {
      await exportPartsMsrpByOemList(exportFile);
      setShowExportDialog(false);
    } catch (reason) {
      setError(errorText(reason));
    } finally {
      setExporting(false);
    }
  };

  const first = total ? (page - 1) * PAGE_SIZE + 1 : 0;
  const last = Math.min(page * PAGE_SIZE, total);

  return (
    <section className="content-wrap">
      <div className="page-heading">
        <div><p className="eyebrow">MARKET / PARTS</p><h1>PARTS - MSRP</h1><p>MSRP history compared with matching CCC OEM offers.</p></div>
        <div className="heading-count"><strong>{total.toLocaleString()}</strong><span>snapshots</span></div>
      </div>
      <div className="ccc-view-tabs" role="tablist" aria-label="Parts MSRP views">
        <button role="tab" aria-selected="true" className="active">Crawl List</button>
      </div>
      <div className="toolbar-row parts-msrp-toolbar">
        <label className="search-box"><span>⌕</span><input value={search} onChange={(event) => { setSearch(event.target.value); setPage(1); }} placeholder="Search OEM" /></label>
        <div className="toolbar-spacer" />
        <label className={`outline-button file-button${importing ? " disabled" : ""}`}>
          {importing ? "Importing…" : "↑ Import Excel"}
          <input type="file" accept=".xlsx,.xlsm" onChange={onImport} disabled={importing} />
        </label>
        <button className="outline-button" disabled={exporting} onClick={() => { setExportFile(null); setExportMode("all"); setShowExportDialog(true); }}>↓ Export Excel</button>
      </div>
      <p className="parts-msrp-import-note">Import columns: OEM, MSRP, Date. OEM-list export accepts OEM or OEM Number.</p>
      {error && <div className="alert error-alert" role="alert">{error}</div>}
      {report && <div className="import-summary"><div><strong>Parts MSRP import complete</strong><span>{report.created} added</span><span>{report.updated} updated</span><span>{report.skipped} skipped</span></div>{report.errors.length > 0 && <details><summary>{report.errors.length} row issue(s)</summary><ul>{report.errors.map((issue) => <li key={issue}>{issue}</li>)}</ul></details>}<button onClick={() => setReport(null)} aria-label="Dismiss import report">×</button></div>}
      <div className="table-frame parts-msrp-table-frame">
        <table>
          <thead><tr>{COLUMNS.map(([field, label]) => <ColumnHeader
            key={field}
            field={field}
            label={label}
            filter={columnFilters[field] ?? EMPTY_FILTER}
            sort={sort}
            onFilter={updateColumnFilter}
            onSort={updateSort}
          />)}</tr></thead>
          <tbody>
            {loading ? <tr><td className="empty-state" colSpan={9}>Loading Parts MSRP…</td></tr>
              : items.length === 0 ? <tr><td className="empty-state" colSpan={9}>No Parts MSRP snapshots found. Import an Excel file to add one.</td></tr>
                : items.map((record) => <tr key={record.id}>
                  <td className="vin-cell">{record.oem}</td>
                  <td className="parts-msrp-fitments">{record.fitments.length ? record.fitments.join("; ") : "No VIN fitments"}</td>
                  <td>{money(record.msrp)}</td><td>{money(record.previous_msrp)}</td>
                  <td>{money(record.ccc_price)}</td><td>{money(record.previous_ccc_price)}</td>
                  <td>{money(record.gap_msrp)}</td><td>{money(record.gap_ccc)}</td>
                  <td className="updated-cell">{new Date(record.crawl_date).toLocaleDateString()}</td>
                </tr>)}
          </tbody>
        </table>
      </div>
      <div className="table-footer"><span>{total === 0 ? "0 snapshots" : `${first}–${last} of ${total.toLocaleString()}`}</span><div><button disabled={page <= 1 || loading} onClick={() => setPage((value) => value - 1)}>← Previous</button><span>Page {page}{pages ? ` of ${pages}` : ""}</span><button disabled={page >= pages || loading} onClick={() => setPage((value) => value + 1)}>Next →</button></div></div>
      {showExportDialog && <div className="modal-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) setShowExportDialog(false); }}>
        <section className="modal" role="dialog" aria-modal="true" aria-labelledby="parts-msrp-export-title">
          <header><div><p className="eyebrow">MARKET / PARTS - MSRP</p><h2 id="parts-msrp-export-title">Export Parts MSRP</h2></div><button className="close-button" onClick={() => setShowExportDialog(false)} aria-label="Close export dialog">×</button></header>
          <div className="export-options">
            <label className={`export-choice${exportMode === "all" ? " selected" : ""}`}>
              <input type="radio" name="parts-msrp-export-mode" checked={exportMode === "all"} onChange={() => setExportMode("all")} />
              <span><strong>Current search and filters</strong><small>Export rows matching the list search, column filters, and sort order.</small></span>
            </label>
            <label className={`export-choice${exportMode === "list" ? " selected" : ""}`}>
              <input type="radio" name="parts-msrp-export-mode" checked={exportMode === "list"} onChange={() => setExportMode("list")} />
              <span><strong>OEM list from Excel</strong><small>Export Parts MSRP history for OEM numbers in an uploaded workbook.</small></span>
            </label>
            {exportMode === "list" && <label className="vehicle-list-upload">Excel file
              <input type="file" accept=".xlsx,.xlsm" onChange={(event) => setExportFile(event.target.files?.[0] ?? null)} />
              <small>Required column: OEM or OEM Number{exportFile ? ` · ${exportFile.name}` : ""}</small>
            </label>}
          </div>
          <div className="modal-actions">
            <button type="button" className="outline-button" onClick={() => setShowExportDialog(false)}>Cancel</button>
            <button type="button" className="primary-button" disabled={exporting || (exportMode === "list" && !exportFile)} onClick={() => void (exportMode === "all" ? exportRows() : exportByOemList())}>{exporting ? "Preparing…" : "Export Excel"}</button>
          </div>
        </section>
      </div>}
    </section>
  );
}
