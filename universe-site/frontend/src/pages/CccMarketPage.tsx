import { Fragment, useEffect, useState } from "react";
import "./lowest-price.css";
import { errorText, exportCccLowestPriceDetails, getCccLowestPriceDetails, getCccLowestPriceSummary, getCccMarketFilters, getCccMarketOffers, getCccMarketPage, importCccMarketExcel } from "../api";
import type { CccLowestPriceDetail, CccLowestPriceSummary, CccMarketFilters, CccMarketImportSummary, CccMarketOffer, CccMarketRecord } from "../api";

const EMPTY_FILTERS: CccMarketFilters = { oems: [], vins: [], descriptions: [], vendors: [] };
const PAGE_SIZE = 25;

function localDateString(value: Date): string {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, "0");
  const day = String(value.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function previousMonthDate(): string {
  const today = new Date();
  const day = today.getDate();
  today.setDate(1);
  today.setMonth(today.getMonth() - 1);
  const lastDay = new Date(today.getFullYear(), today.getMonth() + 1, 0).getDate();
  today.setDate(Math.min(day, lastDay));
  return localDateString(today);
}

export default function CccMarketPage() {
  const [activeView, setActiveView] = useState<"crawls" | "lowest">("crawls");
  const [items, setItems] = useState<Pick<CccMarketRecord, "oem" | "vin" | "crawl_date">[]>([]);
  const [filters, setFilters] = useState<CccMarketFilters>(EMPTY_FILTERS);
  const [search, setSearch] = useState("");
  const [oem, setOem] = useState("");
  const [vin, setVin] = useState("");
  const [description, setDescription] = useState("");
  const [vendor, setVendor] = useState("");
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [pages, setPages] = useState(0);
  const [loading, setLoading] = useState(true);
  const [importing, setImporting] = useState(false);
  const [error, setError] = useState("");
  const [report, setReport] = useState<CccMarketImportSummary | null>(null);
  const [fromDate, setFromDate] = useState(previousMonthDate);
  const [toDate, setToDate] = useState(() => localDateString(new Date()));
  const [lowestSummary, setLowestSummary] = useState<CccLowestPriceSummary | null>(null);
  const [lowestLoading, setLowestLoading] = useState(false);
  const [lowestError, setLowestError] = useState("");
  const [detailSelection, setDetailSelection] = useState<{ vendor: string; description: string; outcome: "won" | "lost"; metric: "oem" | "crawl" } | null>(null);
  const [lowestDetails, setLowestDetails] = useState<CccLowestPriceDetail[]>([]);
  const [detailsLoading, setDetailsLoading] = useState(false);
  const [detailsError, setDetailsError] = useState("");
  const [exportingDetails, setExportingDetails] = useState(false);
  const [selectedGroup, setSelectedGroup] = useState<Pick<CccMarketRecord, "oem" | "vin" | "crawl_date"> | null>(null);
  const [offers, setOffers] = useState<CccMarketOffer[]>([]);
  const [offersLoading, setOffersLoading] = useState(false);
  const [offersError, setOffersError] = useState("");
  const [columnSearch, setColumnSearch] = useState<Record<string, string>>({});
  const [sortColumn, setSortColumn] = useState("");
  const [sortDirection, setSortDirection] = useState<"asc" | "desc">("asc");

  useEffect(() => {
    getCccMarketFilters().then(setFilters).catch((reason) => setError(errorText(reason)));
  }, []);

  useEffect(() => {
    if (activeView !== "lowest") return;
    let current = true;
    setLowestLoading(true);
    getCccLowestPriceSummary(fromDate, toDate)
      .then((result) => { if (current) { setLowestSummary(result); setLowestError(""); } })
      .catch((reason) => { if (current) setLowestError(errorText(reason)); })
      .finally(() => { if (current) setLowestLoading(false); });
    return () => { current = false; };
  }, [activeView, fromDate, toDate]);

  useEffect(() => {
    if (!detailSelection) return;
    let current = true;
    setDetailsLoading(true);
    setDetailsError("");
    getCccLowestPriceDetails({ ...detailSelection, from_date: fromDate, to_date: toDate })
      .then((rows) => { if (current) setLowestDetails(rows); })
      .catch((reason) => { if (current) setDetailsError(errorText(reason)); })
      .finally(() => { if (current) setDetailsLoading(false); });
    return () => { current = false; };
  }, [detailSelection, fromDate, toDate]);

  useEffect(() => {
    let current = true;
    setLoading(true);
    getCccMarketPage({ page, page_size: PAGE_SIZE, search, oem, vin, description, vendor })
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
  }, [page, search, oem, vin, description, vendor]);

  const updateFilter = (setter: (value: string) => void, value: string) => {
    setter(value);
    setPage(1);
  };

  const clearFilters = () => {
    setSearch("");
    setOem("");
    setVin("");
    setDescription("");
    setVendor("");
    setPage(1);
  };

  const showPrices = async (group: Pick<CccMarketRecord, "oem" | "vin" | "crawl_date">) => {
    setSelectedGroup(group);
    setOffers([]);
    setColumnSearch({});
    setSortColumn("");
    setSortDirection("asc");
    setOffersLoading(true);
    setOffersError("");
    try {
      setOffers(await getCccMarketOffers(group));
    } catch (reason) {
      setOffersError(errorText(reason));
    } finally {
      setOffersLoading(false);
    }
  };

  const showLowestDetails = (vendor: string, description: string, outcome: "won" | "lost", metric: "oem" | "crawl") => {
    setLowestDetails([]);
    setDetailsError("");
    setDetailSelection({ vendor, description, outcome, metric });
  };

  const exportLowestDetails = async () => {
    if (!detailSelection) return;
    setExportingDetails(true);
    setDetailsError("");
    try {
      await exportCccLowestPriceDetails({ ...detailSelection, from_date: fromDate, to_date: toDate });
    } catch (reason) {
      setDetailsError(errorText(reason));
    } finally {
      setExportingDetails(false);
    }
  };

  const offerColumns = [...new Set(offers.flatMap((offer) => Object.keys(offer.market_data)))];
  const visibleOffers = offers.filter((offer) => offerColumns.every((column) => {
    const filter = (columnSearch[column] ?? "").trim().toLocaleLowerCase();
    return !filter || displayOfferValue(offer.market_data[column]).toLocaleLowerCase().includes(filter);
  }));
  if (sortColumn) {
    visibleOffers.sort((left, right) => {
      const leftValue = sortableOfferValue(left.market_data[sortColumn]);
      const rightValue = sortableOfferValue(right.market_data[sortColumn]);
      const comparison = typeof leftValue === "number" && typeof rightValue === "number"
        ? leftValue - rightValue
        : String(leftValue).localeCompare(String(rightValue), undefined, { numeric: true, sensitivity: "base" });
      return sortDirection === "asc" ? comparison : -comparison;
    });
  }

  const onImport = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    setImporting(true);
    setError("");
    setReport(null);
    try {
      const result = await importCccMarketExcel(file);
      setReport(result);
      setPage(1);
      setFilters(await getCccMarketFilters());
      const refreshed = await getCccMarketPage({ page: 1, page_size: PAGE_SIZE, search, oem, vin, description, vendor });
      setItems(refreshed.items);
      setTotal(refreshed.total);
      setPages(refreshed.pages);
    } catch (reason) {
      setError(errorText(reason));
    } finally {
      setImporting(false);
    }
  };

  const start = total ? (page - 1) * PAGE_SIZE + 1 : 0;
  const end = Math.min(page * PAGE_SIZE, total);

  return (
    <section className="content-wrap">
      <div className="page-heading">
        <div><p className="eyebrow">MARKET / CCC</p><h1>{activeView === "crawls" ? "CCC Market" : "Lowest Price"}</h1><p>{activeView === "crawls" ? "Crawls grouped by OEM, VIN, and crawl date; newest first." : "Compare lowest and lost prices for each vendor and description."}</p></div>
        <div className="heading-count"><strong>{activeView === "crawls" ? total.toLocaleString() : (lowestSummary?.oem_count ?? 0).toLocaleString()}</strong><span>{activeView === "crawls" ? "crawls" : "OEMs analyzed"}</span></div>
      </div>
      <div className="ccc-view-tabs" role="tablist" aria-label="CCC views">
        <button role="tab" aria-selected={activeView === "crawls"} className={activeView === "crawls" ? "active" : ""} onClick={() => setActiveView("crawls")}>Crawl list</button>
        <button role="tab" aria-selected={activeView === "lowest"} className={activeView === "lowest" ? "active" : ""} onClick={() => setActiveView("lowest")}>Lowest Price</button>
      </div>
      {activeView === "crawls" ? <div className="ccc-toolbar">
        <label className="search-box"><span>⌕</span><input value={search} onChange={(event) => updateFilter(setSearch, event.target.value)} placeholder="Search all CCC data" /></label>
        <label className="ccc-filter">OEM<input list="ccc-oem-options" value={oem} onChange={(event) => updateFilter(setOem, event.target.value)} placeholder="Any OEM" /><datalist id="ccc-oem-options">{filters.oems.map((option) => <option key={option} value={option} />)}</datalist></label>
        <label className="ccc-filter">VIN<input list="ccc-vin-options" value={vin} onChange={(event) => updateFilter(setVin, event.target.value)} placeholder="Any VIN" /><datalist id="ccc-vin-options">{filters.vins.map((option) => <option key={option} value={option} />)}</datalist></label>
        <label className="ccc-filter">Description<input list="ccc-description-options" value={description} onChange={(event) => updateFilter(setDescription, event.target.value)} placeholder="Any description" /><datalist id="ccc-description-options">{filters.descriptions.map((option) => <option key={option} value={option} />)}</datalist></label>
        <label className="ccc-filter">Vendor<input list="ccc-vendor-options" value={vendor} onChange={(event) => updateFilter(setVendor, event.target.value)} placeholder="Any vendor" /><datalist id="ccc-vendor-options">{filters.vendors.map((option) => <option key={option} value={option} />)}</datalist></label>
        <button className="text-button" onClick={clearFilters}>Clear</button>
        <label className={`outline-button file-button${importing ? " disabled" : ""}`}>
          {importing ? "Importing…" : "↑ Import Excel"}
          <input type="file" accept=".xlsx,.xlsm" onChange={onImport} disabled={importing} />
        </label>
      </div> : <div className="ccc-toolbar ccc-date-toolbar">
        <label className="ccc-filter">From date<input type="date" value={fromDate} max={toDate || undefined} onChange={(event) => setFromDate(event.target.value)} /></label>
        <label className="ccc-filter">To date<input type="date" value={toDate} min={fromDate || undefined} onChange={(event) => setToDate(event.target.value)} /></label>
        <button className="text-button" onClick={() => { setFromDate(previousMonthDate()); setToDate(localDateString(new Date())); }}>Reset to last month</button>
        <span className="ccc-date-note">Inclusive range · defaults to the last month</span>
      </div>}
      {activeView === "lowest" && <>
        {lowestError && <div className="alert error-alert" role="alert">{lowestError}</div>}
        <div className="lowest-summary-strip">
          <div><strong>{lowestSummary?.vendor_count ?? 0}</strong><span>vendors with priced offers</span></div>
          <div><strong>{lowestSummary?.lowest_count ?? 0}</strong><span>lowest-price crawl wins</span></div>
          <div><strong>{lowestSummary?.lost_count ?? 0}</strong><span>vendor crawl losses</span></div>
        </div>
        <div className="lowest-price-table-wrap">
          {lowestLoading ? <p className="empty-state lowest-empty">Calculating lowest offers…</p>
            : !lowestSummary?.vendors.length ? <p className="empty-state lowest-empty">No priced offers found in this date range.</p>
              : <table className="lowest-price-table"><colgroup><col className="lowest-label-column" /><col /><col /><col /><col /></colgroup><thead><tr><th>VENDOR / DESCRIPTION</th><th>OEMs WON</th><th>CRAWL WINS</th><th>OEMs LOST</th><th>CRAWL LOSSES</th></tr></thead><tbody>{lowestSummary.vendors.map((item) => <Fragment key={item.vendor}><tr className="lowest-vendor-row"><th>{item.vendor}</th><td><span className="lowest-metric-value">{item.won_oem_count.toLocaleString()}</span></td><td><span className="lowest-metric-value">{item.lowest_count.toLocaleString()}</span></td><td><span className="lowest-metric-value lost-count">{item.lost_oem_count.toLocaleString()}</span></td><td><span className="lowest-metric-value lost-count">{item.lost_count.toLocaleString()}</span></td></tr>{item.descriptions.map((entry) => <tr className="lowest-description-row" key={`${item.vendor}-${entry.description}`}><td><span>{entry.description}</span></td><td><button className="lowest-count-button won-count" onClick={() => showLowestDetails(item.vendor, entry.description, "won", "oem")}>{entry.won_oem_count.toLocaleString()}</button></td><td><button className="lowest-count-button won-count" onClick={() => showLowestDetails(item.vendor, entry.description, "won", "crawl")}>{entry.won_count.toLocaleString()}</button></td><td><button className="lowest-count-button lost-count" onClick={() => showLowestDetails(item.vendor, entry.description, "lost", "oem")}>{entry.lost_oem_count.toLocaleString()}</button></td><td><button className="lowest-count-button lost-count" onClick={() => showLowestDetails(item.vendor, entry.description, "lost", "crawl")}>{entry.lost_count.toLocaleString()}</button></td></tr>)}</Fragment>)}</tbody></table>}
        </div>
      </>}
      {error && <div className="alert error-alert" role="alert">{error}</div>}
      {activeView === "crawls" && report && <div className="import-summary"><div><strong>CCC import complete</strong><span>{report.created} created</span><span>{report.updated} replaced</span><span>{report.skipped} skipped</span></div>{report.errors.length > 0 && <details><summary>{report.errors.length} row issue(s)</summary><ul>{report.errors.map((issue) => <li key={issue}>{issue}</li>)}</ul></details>}<button onClick={() => setReport(null)} aria-label="Dismiss import report">×</button></div>}
      {activeView === "crawls" && <><div className="table-frame ccc-table-frame">
        <table>
          <thead><tr><th>OEM</th><th>VIN</th><th>CRAWL DATE</th><th>PRICES</th></tr></thead>
          <tbody>
            {loading ? <tr><td className="empty-state" colSpan={4}>Loading CCC market data…</td></tr>
              : items.length === 0 ? <tr><td className="empty-state" colSpan={4}>No CCC records match these filters.</td></tr>
                : items.map((record) => <tr key={`${record.oem}-${record.vin}-${record.crawl_date}`}>
                  <td>{record.oem}</td><td className="vin-cell">{record.vin}</td><td className="updated-cell">{new Date(record.crawl_date).toLocaleString()}</td><td><button className="ccc-price-button" onClick={() => void showPrices(record)}>View prices</button></td>
                </tr>)}
          </tbody>
        </table>
      </div>
      <div className="table-footer"><span>{start === 0 ? "0 records" : `${start}–${end} of ${total.toLocaleString()}`}</span><div><button disabled={page <= 1 || loading} onClick={() => setPage((value) => value - 1)}>← Previous</button><span>Page {page}{pages ? ` of ${pages}` : ""}</span><button disabled={page >= pages || loading} onClick={() => setPage((value) => value + 1)}>Next →</button></div></div></>}
      {selectedGroup && <div className="ccc-offers-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) setSelectedGroup(null); }}>
        <section className="ccc-offers-dialog" role="dialog" aria-modal="true" aria-labelledby="ccc-offers-title">
          <header><div><p className="eyebrow">CCC MARKET / PRICES</p><h2 id="ccc-offers-title">Market offers</h2><p>{selectedGroup.oem} · {selectedGroup.vin} · {new Date(selectedGroup.crawl_date).toLocaleString()}</p></div><button className="close-button" onClick={() => setSelectedGroup(null)} aria-label="Close prices">×</button></header>
          {offersError && <div className="alert error-alert" role="alert">{offersError}</div>}
          <div className="ccc-offers-table-frame">
            {offersLoading ? <p className="ccc-offers-empty">Loading market offers…</p>
              : offers.length === 0 ? <p className="ccc-offers-empty">No market offers were found for this crawl.</p>
                : <table><thead><tr>{offerColumns.map((column) => <th key={column}><button className="ccc-sort-button" onClick={() => { if (sortColumn === column) setSortDirection((direction) => direction === "asc" ? "desc" : "asc"); else { setSortColumn(column); setSortDirection("asc"); } }}>{column.replace(/[-_]/g, " ").toUpperCase()}{sortColumn === column ? (sortDirection === "asc" ? " ↑" : " ↓") : " ↕"}</button><input aria-label={`Search ${column}`} value={columnSearch[column] ?? ""} onChange={(event) => setColumnSearch((current) => ({ ...current, [column]: event.target.value }))} placeholder={`Search ${column}`} /></th>)}</tr></thead><tbody>{visibleOffers.map((offer) => <tr key={offer.market_index}>{offerColumns.map((column) => <td key={column}>{displayOfferValue(offer.market_data[column])}</td>)}</tr>)}{visibleOffers.length === 0 && <tr><td className="empty-state" colSpan={offerColumns.length}>No offers match these column searches.</td></tr>}</tbody></table>}
          </div>
          {!offersLoading && offers.length > 0 && <footer>{visibleOffers.length} of {offers.length} offers</footer>}
        </section>
      </div>}
      {detailSelection && <div className="ccc-offers-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) setDetailSelection(null); }}>
        <section className="ccc-offers-dialog lowest-detail-dialog" role="dialog" aria-modal="true" aria-labelledby="lowest-detail-title">
          <header><div><p className="eyebrow">LOWEST PRICE / OEM DETAILS</p><h2 id="lowest-detail-title">{detailSelection.outcome === "won" ? "Won lowest price" : "Lost lowest price"}</h2><p>{detailSelection.vendor} · {detailSelection.description} · {fromDate} to {toDate}</p></div><button className="close-button" onClick={() => setDetailSelection(null)} aria-label="Close OEM details">×</button></header>
          <div className="lowest-detail-actions"><span>{detailsLoading ? "Loading OEM records…" : `${lowestDetails.length} related record${lowestDetails.length === 1 ? "" : "s"}`}</span><button className="outline-button" disabled={detailsLoading || lowestDetails.length === 0 || exportingDetails} onClick={() => void exportLowestDetails()}>{exportingDetails ? "Exporting…" : "↓ Export Excel"}</button></div>
          {detailsError && <div className="alert error-alert" role="alert">{detailsError}</div>}
          <div className="ccc-offers-table-frame"><table><thead><tr><th>OEM PART</th><th>VIN</th><th>CRAWL DATE</th><th>VENDOR</th><th>PRICE</th><th>{detailSelection.outcome === "won" ? "SECOND-LOWEST VENDOR" : "LOWEST VENDOR"}</th><th>{detailSelection.outcome === "won" ? "SECOND-LOWEST PRICE" : "LOWEST PRICE"}</th><th>RESULT</th>{detailSelection.metric === "oem" && <th>CRAWLS</th>}</tr></thead><tbody>{lowestDetails.map((row, index) => <tr key={`${row.oem}-${row.vin}-${row.crawl_date}-${index}`}><td>{row.oem}</td><td className="vin-cell">{row.vin}</td><td>{new Date(row.crawl_date).toLocaleString()}</td><td>{row.vendor}</td><td>{row.price}</td><td>{detailSelection.outcome === "won" ? row.second_lowest_vendors || "No higher-priced vendor" : row.lowest_vendors}</td><td>{detailSelection.outcome === "won" ? row.second_lowest_price ?? "N/A" : row.lowest_price}</td><td>{row.outcome === "won" ? "Lowest" : "Higher"}</td>{detailSelection.metric === "oem" && <td>{row.crawl_count ?? 1}</td>}</tr>)}{!detailsLoading && !lowestDetails.length && <tr><td className="empty-state" colSpan={detailSelection.metric === "oem" ? 9 : 8}>No related OEM records.</td></tr>}</tbody></table></div>
        </section>
      </div>}
    </section>
  );
}

function displayOfferValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "";
  return typeof value === "object" ? JSON.stringify(value) : String(value);
}

function sortableOfferValue(value: unknown): number | string {
  const rendered = displayOfferValue(value).replace(/[$,]/g, "").trim();
  if (rendered && /^[-+]?(?:\d+\.?\d*|\.\d+)$/.test(rendered)) return Number(rendered);
  return rendered;
}
