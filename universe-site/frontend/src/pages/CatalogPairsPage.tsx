import { useEffect, useState } from "react";
import { downloadCatalogPairsExcel, errorText, getCatalogPairPage } from "../api";
import type { CatalogPair, Page } from "../api";
import ColumnHeader from "../components/ColumnHeader";
import type { ColumnFilterValue } from "../components/ColumnHeader";

const PAGE_SIZE = 10;
const EMPTY_PAGE: Page<CatalogPair> = { items: [], page: 1, page_size: PAGE_SIZE, total: 0, pages: 0 };

export default function CatalogPairsPage() {
  const [data, setData] = useState(EMPTY_PAGE);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [columnFilters, setColumnFilters] = useState<Record<string, ColumnFilterValue>>({});
  const [sort, setSort] = useState<{ field: string; direction: "asc" | "desc" }>({ field: "", direction: "asc" });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [exporting, setExporting] = useState(false);

  useEffect(() => {
    let current = true;
    setLoading(true);
    getCatalogPairPage({ page, page_size: PAGE_SIZE, search, filters: JSON.stringify(columnFilters), sort_by: sort.field, sort_dir: sort.direction })
      .then((result) => { if (current) { setData(result); setError(""); } })
      .catch((reason) => { if (current) setError(errorText(reason)); })
      .finally(() => { if (current) setLoading(false); });
    return () => { current = false; };
  }, [page, search, columnFilters, sort]);

  const updateColumnFilter = (field: string, value: ColumnFilterValue) => {
    setColumnFilters((current) => ({ ...current, [field]: value }));
    setPage(1);
  };

  const updateSort = (field: string) => {
    setSort((current) => ({ field, direction: current.field === field && current.direction === "asc" ? "desc" : "asc" }));
    setPage(1);
  };

  const exportRows = async () => {
    setExporting(true);
    setError("");
    try {
      await downloadCatalogPairsExcel({ search, filters: JSON.stringify(columnFilters), sort_by: sort.field, sort_dir: sort.direction });
    } catch (reason) {
      setError(errorText(reason));
    } finally {
      setExporting(false);
    }
  };

  const first = data.total ? (page - 1) * PAGE_SIZE + 1 : 0;
  const last = Math.min(page * PAGE_SIZE, data.total);

  return (
    <section className="content-wrap">
      <div className="page-heading">
        <div><p className="eyebrow">MASTER DATA / CROSS-REFERENCE</p><h1>Partslink ↔ Interchange</h1><p>Pairs derived from OEM records linked to both catalogs.</p></div>
        <div className="heading-count"><strong>{data.total.toLocaleString()}</strong><span>pairs</span></div>
      </div>
      <div className="toolbar-row">
        <label className="search-box"><span>⌕</span><input value={search} onChange={(event) => { setSearch(event.target.value); setPage(1); }} placeholder="Search Partslink or Interchange" /></label>
        <div className="toolbar-spacer" />
        <button className="outline-button" disabled={exporting} onClick={() => void exportRows()}>{exporting ? "Preparing…" : "↓ Export Excel"}</button>
      </div>
      {error && <div className="alert error-alert" role="alert">{error}</div>}
      <div className="table-frame">
        <table>
          <thead><tr>{[["partslink", "PARTSLINK"], ["interchange", "INTERCHANGE"], ["distinct_oem_count", "SHARED OEM PARTS"]].map(([field, label]) => <ColumnHeader key={field} field={field} label={label} filter={columnFilters[field] ?? { value: "", mode: "any" }} sort={sort} onFilter={updateColumnFilter} onSort={updateSort} />)}</tr></thead>
          <tbody>
            {loading ? <tr><td className="empty-state" colSpan={3}>Loading pairs…</td></tr> : data.items.length === 0 ? <tr><td className="empty-state" colSpan={3}>No shared catalog pairs found.</td></tr> : data.items.map((item) => <tr key={`${item.id_partslink}-${item.id_interchange}`}>
              <td className="vin-cell">{item.partslink}</td><td className="vin-cell">{item.interchange}</td><td><span className="count-pill">{item.distinct_oem_count}</span></td>
            </tr>)}
          </tbody>
        </table>
      </div>
      <div className="table-footer"><span>{data.total === 0 ? "0 pairs" : `${first}–${last} of ${data.total.toLocaleString()}`}</span><div><button disabled={page <= 1 || loading} onClick={() => setPage((value) => value - 1)}>← Previous</button><span>Page {page}{data.pages ? ` of ${data.pages}` : ""}</span><button disabled={page >= data.pages || loading} onClick={() => setPage((value) => value + 1)}>Next →</button></div></div>
    </section>
  );
}
