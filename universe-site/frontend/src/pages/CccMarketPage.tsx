import { useEffect, useState } from "react";
import "./lowest-price.css";
import { errorText, exportCccLowestPriceDetails, exportCccMarketCrawls, getCccLowestPriceDetails, getCccLowestPriceSummary, getCccMarketFilters, getCccMarketOffers, getCccMarketPage, getCccPriceHistory, getCccVendorDashboard, getCccVehicleOptions, importCccMarketExcel } from "../api";
import type { CccLowestPriceDetail, CccLowestPriceSummary, CccMarketFilters, CccMarketImportSummary, CccMarketOffer, CccMarketRecord, CccPriceHistory, CccVendorDashboard } from "../api";
import SearchSelect from "../components/SearchSelect";

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
  const [activeView, setActiveView] = useState<"dashboard" | "crawls" | "lowest" | "history">("dashboard");
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
  const [exportingCrawls, setExportingCrawls] = useState(false);
  const [error, setError] = useState("");
  const [report, setReport] = useState<CccMarketImportSummary | null>(null);
  const [fromDate, setFromDate] = useState(previousMonthDate);
  const [toDate, setToDate] = useState(() => localDateString(new Date()));
  const [lowestSummary, setLowestSummary] = useState<CccLowestPriceSummary | null>(null);
  const [lowestLoading, setLowestLoading] = useState(false);
  const [lowestError, setLowestError] = useState("");
  const [historyOem, setHistoryOem] = useState("");
  const [historyVin, setHistoryVin] = useState("");
  const [historyOemOptions, setHistoryOemOptions] = useState<string[]>([]);
  const [historyVinOptions, setHistoryVinOptions] = useState<string[]>([]);
  const [historyOptionsLoading, setHistoryOptionsLoading] = useState(false);
  const [historyDescription, setHistoryDescription] = useState("");
  const [priceHistory, setPriceHistory] = useState<CccPriceHistory | null>(null);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState("");
  const [dashboardVendor, setDashboardVendor] = useState("");
  const [dashboardDescription, setDashboardDescription] = useState("");
  const [dashboardData, setDashboardData] = useState<CccVendorDashboard | null>(null);
  const [dashboardLoading, setDashboardLoading] = useState(false);
  const [dashboardError, setDashboardError] = useState("");
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
    if (activeView !== "history") return;
    let current = true;
    setHistoryOptionsLoading(true);
    Promise.all([
      getCccVehicleOptions(historyOem, ""),
      getCccVehicleOptions("", historyVin),
    ])
      .then(([vinResult, oemResult]) => {
        if (!current) return;
        setHistoryVinOptions(vinResult.vins);
        setHistoryOemOptions(oemResult.oems);
        if (historyOem && !oemResult.oems.includes(historyOem)) setHistoryOem("");
        if (historyVin && !vinResult.vins.includes(historyVin)) setHistoryVin("");
      })
      .catch((reason) => { if (current) setHistoryError(errorText(reason)); })
      .finally(() => { if (current) setHistoryOptionsLoading(false); });
    return () => { current = false; };
  }, [activeView, historyOem, historyVin]);

  useEffect(() => {
    if (!dashboardVendor && filters.vendors.length) {
      setDashboardVendor(filters.vendors.find((item) => item.toLocaleLowerCase().includes("ipart")) ?? filters.vendors[0]);
    }
  }, [dashboardVendor, filters.vendors]);

  useEffect(() => {
    if (activeView !== "dashboard" || !dashboardVendor) return;
    let current = true;
    setDashboardData(null);
    setDashboardLoading(true);
    setDashboardError("");
    getCccVendorDashboard({ vendor: dashboardVendor, from_date: fromDate, to_date: toDate, description: dashboardDescription })
      .then((result) => { if (current) setDashboardData(result); })
      .catch((reason) => { if (current) setDashboardError(errorText(reason)); })
      .finally(() => { if (current) setDashboardLoading(false); });
    return () => { current = false; };
  }, [activeView, dashboardVendor, dashboardDescription, fromDate, toDate]);

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
    if (activeView !== "history" || !historyOem.trim() || !historyVin.trim() || !historyDescription.trim()) {
      setPriceHistory(null);
      setHistoryLoading(false);
      return;
    }
    let current = true;
    setPriceHistory(null);
    setHistoryLoading(true);
    setHistoryError("");
    getCccPriceHistory({
      oem: historyOem,
      vin: historyVin,
      description: historyDescription,
      from_date: fromDate,
      to_date: toDate,
    })
      .then((result) => { if (current) setPriceHistory(result); })
      .catch((reason) => { if (current) setHistoryError(errorText(reason)); })
      .finally(() => { if (current) setHistoryLoading(false); });
    return () => { current = false; };
  }, [activeView, historyOem, historyVin, historyDescription, fromDate, toDate]);

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

  const exportCrawls = async () => {
    setExportingCrawls(true);
    setError("");
    try {
      await exportCccMarketCrawls({ search, oem, vin, description, vendor });
    } catch (reason) {
      setError(errorText(reason));
    } finally {
      setExportingCrawls(false);
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
        <div><p className="eyebrow">MARKET / CCC</p><h1>{activeView === "dashboard" ? "Dashboard" : activeView === "crawls" ? "CCC Market" : activeView === "lowest" ? "Lowest Price" : "Price History"}</h1><p>{activeView === "dashboard" ? "Vendor competitiveness across CCC crawls." : activeView === "crawls" ? "Crawls grouped by OEM, VIN, and crawl date; newest first." : activeView === "lowest" ? "Compare lowest and lost prices for each vendor and description." : "Track vendor prices for an OEM across CCC crawls."}</p></div>
        <div className="heading-count"><strong>{activeView === "dashboard" ? (dashboardData?.priced_offers ?? 0).toLocaleString() : activeView === "crawls" ? total.toLocaleString() : activeView === "lowest" ? (lowestSummary?.oem_count ?? 0).toLocaleString() : (priceHistory?.vendors.length ?? 0).toLocaleString()}</strong><span>{activeView === "dashboard" ? "priced offers" : activeView === "crawls" ? "crawls" : activeView === "lowest" ? "OEMs analyzed" : "vendors tracked"}</span></div>
      </div>
      <div className="ccc-view-tabs" role="tablist" aria-label="CCC views">
        <button role="tab" aria-selected={activeView === "dashboard"} className={activeView === "dashboard" ? "active" : ""} onClick={() => setActiveView("dashboard")}>Dashboard</button>
        <button role="tab" aria-selected={activeView === "crawls"} className={activeView === "crawls" ? "active" : ""} onClick={() => setActiveView("crawls")}>Crawl list</button>
        <button role="tab" aria-selected={activeView === "lowest"} className={activeView === "lowest" ? "active" : ""} onClick={() => setActiveView("lowest")}>Lowest Price</button>
        <button role="tab" aria-selected={activeView === "history"} className={activeView === "history" ? "active" : ""} onClick={() => setActiveView("history")}>Price History</button>
      </div>
      {activeView === "dashboard" ? <div className="ccc-toolbar ccc-date-toolbar">
        <SearchSelect label="Vendor" value={dashboardVendor} options={filters.vendors.map((item) => ({ label: item, value: item }))} placeholder="Search vendors" onChange={setDashboardVendor} className="ccc-filter" />
        <SearchSelect label="Description" value={dashboardDescription} options={[{ label: "All descriptions", value: "" }, ...filters.descriptions.map((item) => ({ label: item, value: item }))]} placeholder="Search descriptions" onChange={setDashboardDescription} className="ccc-filter" />
        <label className="ccc-filter">From date<input type="date" value={fromDate} max={toDate || undefined} onChange={(event) => setFromDate(event.target.value)} /></label>
        <label className="ccc-filter">To date<input type="date" value={toDate} min={fromDate || undefined} onChange={(event) => setToDate(event.target.value)} /></label>
        <button className="text-button" onClick={() => { setFromDate(previousMonthDate()); setToDate(localDateString(new Date())); }}>Reset dates</button>
      </div> : activeView === "crawls" ? <div className="ccc-toolbar">
        <label className="search-box"><span>⌕</span><input value={search} onChange={(event) => updateFilter(setSearch, event.target.value)} placeholder="Search all CCC data" /></label>
        <SearchSelect label="OEM" value={oem} options={filters.oems.map((item) => ({ label: item, value: item }))} placeholder="Any OEM" allowCustom onChange={(value) => updateFilter(setOem, value)} className="ccc-filter" />
        <SearchSelect label="VIN" value={vin} options={filters.vins.map((item) => ({ label: item, value: item }))} placeholder="Any VIN" allowCustom onChange={(value) => updateFilter(setVin, value)} className="ccc-filter" />
        <SearchSelect label="Description" value={description} options={filters.descriptions.map((item) => ({ label: item, value: item }))} placeholder="Any description" allowCustom onChange={(value) => updateFilter(setDescription, value)} className="ccc-filter" />
        <SearchSelect label="Vendor" value={vendor} options={filters.vendors.map((item) => ({ label: item, value: item }))} placeholder="Any vendor" allowCustom onChange={(value) => updateFilter(setVendor, value)} className="ccc-filter" />
        <button className="text-button" onClick={clearFilters}>Clear</button>
        <label className={`outline-button file-button${importing ? " disabled" : ""}`}>
          {importing ? "Importing…" : "↑ Import Excel"}
          <input type="file" accept=".xlsx,.xlsm" onChange={onImport} disabled={importing} />
        </label>
        <button className="outline-button" disabled={exportingCrawls} onClick={() => void exportCrawls()}>{exportingCrawls ? "Exporting…" : "↓ Export Excel"}</button>
      </div> : <div className="ccc-toolbar ccc-date-toolbar">
        {activeView === "history" && <>
          <SearchSelect label="OEM" value={historyOem} options={historyOemOptions.map((item) => ({ label: item, value: item }))} placeholder="Search OEM" loading={historyOptionsLoading} emptyMessage="No matching OEMs" clearable onChange={setHistoryOem} className="ccc-filter" />
          <SearchSelect label="VIN" value={historyVin} options={historyVinOptions.map((item) => ({ label: item, value: item }))} placeholder={historyOem ? "VINs for selected OEM" : "Search VIN"} loading={historyOptionsLoading} emptyMessage="No matching VINs" clearable onChange={setHistoryVin} className="ccc-filter" />
          <SearchSelect label="Description" value={historyDescription} options={filters.descriptions.map((item) => ({ label: item, value: item }))} placeholder="Select description" onChange={setHistoryDescription} className="ccc-filter" />
        </>}
        <label className="ccc-filter">From date<input type="date" value={fromDate} max={toDate || undefined} onChange={(event) => setFromDate(event.target.value)} /></label>
        <label className="ccc-filter">To date<input type="date" value={toDate} min={fromDate || undefined} onChange={(event) => setToDate(event.target.value)} /></label>
        <button className="text-button" onClick={() => { setFromDate(previousMonthDate()); setToDate(localDateString(new Date())); }}>Reset to last month</button>
        {activeView === "lowest" && <span className="ccc-date-note">Inclusive range · defaults to the last month</span>}
      </div>}
      {activeView === "dashboard" && <>
        {dashboardError && <div className="alert error-alert" role="alert">{dashboardError}</div>}
        {dashboardLoading ? <p className="empty-state price-history-empty">Loading vendor performance…</p>
          : !dashboardVendor ? <p className="empty-state price-history-empty">No vendors are available in the CCC market data.</p>
            : !dashboardData?.priced_offers ? <p className="empty-state price-history-empty">No priced offers found for this vendor and date range.</p>
              : <div className="vendor-dashboard-content">
                <div className="vendor-dashboard-kpis">
                  <div><span>PRICED OFFERS</span><strong>{dashboardData.priced_offers.toLocaleString()}</strong></div>
                  <div><span>LOWEST-PRICE WINS</span><strong>{dashboardData.wins.toLocaleString()}</strong></div>
                  <div><span>LOSSES</span><strong>{dashboardData.losses.toLocaleString()}</strong></div>
                  <div><span>WIN RATE</span><strong>{dashboardData.win_rate.toFixed(1)}%</strong></div>
                  <div><span>AVG. GAP FROM LOWEST</span><strong>{formatPrice(dashboardData.average_gap)}</strong></div>
                </div>
                <section className="vendor-dashboard-section">
                  <header><div><h2>Price competitiveness</h2><p>Average vendor price versus average lowest market price by crawl date.</p></div><div className="vendor-dashboard-legend"><span><i className="vendor-price-key" />{dashboardData.vendor}</span><span><i className="market-price-key" />Market low</span></div></header>
                  {dashboardData.trend.length < 2 ? <p className="vendor-dashboard-empty">At least two crawl dates are needed to draw a trend. Current average: {formatPrice(dashboardData.trend[0]?.average_price ?? "0")}</p>
                    : <div className="vendor-trend-chart"><svg viewBox="0 0 760 220" role="img" aria-label="Vendor and market-low average prices by crawl date" preserveAspectRatio="none">
                      {[0, 1, 2, 3].map((line) => <line key={line} x1="48" x2="748" y1={25 + line * 52} y2={25 + line * 52} className="vendor-chart-grid" />)}
                      <polyline points={trendPoints(dashboardData.trend.map((item) => Number(item.average_lowest_price)), dashboardData.trend)} className="vendor-chart-market" />
                      <polyline points={trendPoints(dashboardData.trend.map((item) => Number(item.average_price)), dashboardData.trend)} className="vendor-chart-price" />
                      {dashboardData.trend.map((item, index) => <g key={item.date}>
                        <circle cx={trendX(index, dashboardData.trend.length)} cy={trendY(Number(item.average_lowest_price), dashboardData.trend)} r="3" className="vendor-chart-market-dot" />
                        <circle cx={trendX(index, dashboardData.trend.length)} cy={trendY(Number(item.average_price), dashboardData.trend)} r="3" className="vendor-chart-price-dot" />
                      </g>)}
                    </svg><div className="vendor-chart-dates"><span>{dashboardData.trend[0].date}</span><span>{dashboardData.trend[dashboardData.trend.length - 1].date}</span></div></div>}
                </section>
                <section className="vendor-dashboard-section">
                  <header><div><h2>Description performance</h2><p>Wins and losses for this vendor in the selected date range.</p></div></header>
                  <div className="vendor-dashboard-table-scroll"><table><thead><tr><th>DESCRIPTION</th><th>WINS</th><th>LOSSES</th><th>OPPORTUNITIES</th><th>WIN RATE</th></tr></thead><tbody>{dashboardData.descriptions.map((item) => <tr key={item.description}><td>{item.description}</td><td className="dashboard-win">{item.wins.toLocaleString()}</td><td className="dashboard-loss">{item.losses.toLocaleString()}</td><td>{item.opportunities.toLocaleString()}</td><td>{item.win_rate.toFixed(1)}%</td></tr>)}</tbody></table></div>
                </section>
                <section className="vendor-dashboard-section">
                  <header><div><h2>Recent crawl details</h2><p>{dashboardData.details.length.toLocaleString()} shown of {dashboardData.details_total.toLocaleString()} priced offers</p></div></header>
                  <div className="vendor-dashboard-table-scroll vendor-dashboard-details"><table><thead><tr><th>CRAWL DATE</th><th>OEM</th><th>VIN</th><th>DESCRIPTION</th><th>VENDOR PRICE</th><th>LOWEST VENDOR</th><th>LOWEST PRICE</th><th>PREVIOUS CRAWL</th><th>PREVIOUS LOWEST VENDOR</th><th>PREVIOUS LOWEST PRICE</th><th>RESULT</th></tr></thead><tbody>{dashboardData.details.map((item, index) => <tr key={`${item.oem}-${item.vin}-${item.description}-${item.crawl_date}-${index}`}><td>{new Date(item.crawl_date).toLocaleString()}</td><td>{item.oem}</td><td className="vin-cell">{item.vin}</td><td>{item.description}</td><td>{formatPrice(item.price)}</td><td>{item.lowest_vendors}</td><td>{formatPrice(item.lowest_price)}</td><td>{item.previous_crawl_date ? new Date(item.previous_crawl_date).toLocaleString() : "—"}</td><td>{item.previous_lowest_vendors || "—"}</td><td>{item.previous_lowest_price ? formatPrice(item.previous_lowest_price) : "—"}</td><td className={item.outcome === "won" ? "dashboard-win" : "dashboard-loss"}>{item.outcome === "won" ? "Won" : "Lost"}</td></tr>)}</tbody></table></div>
                </section>
              </div>}
      </>}
      {activeView === "history" && <>
        {historyError && <div className="alert error-alert" role="alert">{historyError}</div>}
        {!historyOem.trim() || !historyVin.trim() || !historyDescription.trim()
          ? <p className="empty-state price-history-empty">Select an OEM, VIN, and description to view vendor price history.</p>
          : historyLoading ? <p className="empty-state price-history-empty">Loading price history…</p>
            : !priceHistory?.vendors.length ? <p className="empty-state price-history-empty">No priced offers found for this OEM, VIN, description, and date range.</p>
              : <div className="price-history-content">
                <div className="price-history-summary">
                  <span>{priceHistory.oem} · {priceHistory.vin}</span>
                  <strong>{priceHistory.description}</strong>
                  <small>{priceHistory.vendors.length} vendors · {fromDate} to {toDate}</small>
                </div>
                {priceHistory.vendors.map((entry) => {
                  const latest = entry.observations[entry.observations.length - 1];
                  const previous = entry.observations[entry.observations.length - 2];
                  return <section className="price-history-vendor" key={entry.vendor}>
                    <header><h2>{entry.vendor}</h2><div><span>Latest <strong>{latest ? formatPrice(latest.price) : "—"}</strong></span><span>Change <strong className={latest?.change && Number(latest.change) > 0 ? "price-up" : latest?.change && Number(latest.change) < 0 ? "price-down" : ""}>{latest?.change ? formatPriceChange(latest.change) : "No previous crawl"}</strong></span><span>Previous → latest <strong>{previous ? formatPrice(previous.price) : "No previous crawl"} → {latest ? formatPrice(latest.price) : "—"}</strong></span></div></header>
                    <div className="price-history-table-frame"><table><thead><tr><th>CRAWL DATE</th><th>PRICE</th><th>PREVIOUS</th><th>CHANGE</th></tr></thead><tbody>{[...entry.observations].reverse().map((observation) => <tr key={observation.crawl_date}><td>{new Date(observation.crawl_date).toLocaleString()}</td><td>{formatPrice(observation.price)}</td><td>{observation.previous_price ? formatPrice(observation.previous_price) : "—"}</td><td className={observation.change && Number(observation.change) > 0 ? "price-up" : observation.change && Number(observation.change) < 0 ? "price-down" : ""}>{observation.change ? formatPriceChange(observation.change) : "—"}</td></tr>)}</tbody></table></div>
                  </section>;
                })}
              </div>}
      </>}
      {activeView === "lowest" && <>
        {lowestError && <div className="alert error-alert" role="alert">{lowestError}</div>}
        <div className="lowest-summary-strip">
          <div><strong>{lowestSummary?.vendor_count ?? 0}</strong><span>vendors with priced offers</span></div>
          <div><strong>{lowestSummary?.lowest_count ?? 0}</strong><span>lowest-price crawl wins</span></div>
          <div><strong>{lowestSummary?.lost_count ?? 0}</strong><span>vendor crawl losses</span></div>
        </div>
        <div className="lowest-vendor-list">
          {lowestLoading ? <p className="empty-state lowest-empty">Calculating lowest offers…</p>
            : !lowestSummary?.vendors.length ? <p className="empty-state lowest-empty">No priced offers found in this date range.</p>
              : lowestSummary.vendors.map((item) => <section className="lowest-vendor-panel" key={item.vendor}>
                <header className="lowest-vendor-panel-header"><h2>{item.vendor}</h2><div><span>OEMs won <strong>{item.won_oem_count.toLocaleString()}</strong></span><span>Crawl wins <strong>{item.lowest_count.toLocaleString()}</strong></span><span>OEMs lost <strong>{item.lost_oem_count.toLocaleString()}</strong></span><span>Crawl losses <strong>{item.lost_count.toLocaleString()}</strong></span></div></header>
                <div className="lowest-vendor-description-scroll"><table className="lowest-vendor-description-table"><thead><tr><th>DESCRIPTION</th><th>OEMs WON</th><th>CRAWL WINS</th><th>OEMs LOST</th><th>CRAWL LOSSES</th></tr></thead><tbody>{item.descriptions.map((entry) => <tr key={`${item.vendor}-${entry.description}`}><td>{entry.description}</td><td><button className="lowest-count-button won-count" onClick={() => showLowestDetails(item.vendor, entry.description, "won", "oem")}>{entry.won_oem_count.toLocaleString()}</button></td><td><button className="lowest-count-button won-count" onClick={() => showLowestDetails(item.vendor, entry.description, "won", "crawl")}>{entry.won_count.toLocaleString()}</button></td><td><button className="lowest-count-button lost-count" onClick={() => showLowestDetails(item.vendor, entry.description, "lost", "oem")}>{entry.lost_oem_count.toLocaleString()}</button></td><td><button className="lowest-count-button lost-count" onClick={() => showLowestDetails(item.vendor, entry.description, "lost", "crawl")}>{entry.lost_count.toLocaleString()}</button></td></tr>)}</tbody></table></div>
              </section>)}
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
          <div className="ccc-offers-table-frame"><table><thead><tr><th>OEM PART</th><th>VIN</th><th>CRAWL DATE</th><th>VENDOR</th><th>PRICE</th><th>{detailSelection.outcome === "won" ? "SECOND-LOWEST VENDOR" : "LOWEST VENDOR"}</th><th>{detailSelection.outcome === "won" ? "SECOND-LOWEST PRICE" : "LOWEST PRICE"}</th><th>PREVIOUS CRAWL</th><th>PREVIOUS LOWEST VENDOR</th><th>PREVIOUS LOWEST PRICE</th><th>RESULT</th>{detailSelection.metric === "oem" && <th>CRAWLS</th>}</tr></thead><tbody>{lowestDetails.map((row, index) => <tr key={`${row.oem}-${row.vin}-${row.crawl_date}-${index}`}><td>{row.oem}</td><td className="vin-cell">{row.vin}</td><td>{new Date(row.crawl_date).toLocaleString()}</td><td>{row.vendor}</td><td>{formatPrice(row.price)}</td><td>{detailSelection.outcome === "won" ? row.second_lowest_vendors || "No higher-priced vendor" : row.lowest_vendors}</td><td>{detailSelection.outcome === "won" ? row.second_lowest_price ? formatPrice(row.second_lowest_price) : "N/A" : formatPrice(row.lowest_price)}</td><td>{row.previous_crawl_date ? new Date(row.previous_crawl_date).toLocaleString() : "No previous crawl"}</td><td>{row.previous_lowest_vendors || "—"}</td><td>{row.previous_lowest_price ? formatPrice(row.previous_lowest_price) : "—"}</td><td>{row.outcome === "won" ? "Lowest" : "Higher"}</td>{detailSelection.metric === "oem" && <td>{row.crawl_count ?? 1}</td>}</tr>)}{!detailsLoading && !lowestDetails.length && <tr><td className="empty-state" colSpan={detailSelection.metric === "oem" ? 12 : 11}>No related OEM records.</td></tr>}</tbody></table></div>
        </section>
      </div>}
    </section>
  );
}

function displayOfferValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "";
  return typeof value === "object" ? JSON.stringify(value) : String(value);
}

function formatPrice(value: string): string {
  const amount = Number(value);
  return Number.isFinite(amount) ? amount.toLocaleString(undefined, { style: "currency", currency: "USD" }) : value;
}

function formatPriceChange(value: string): string {
  const amount = Number(value);
  if (!Number.isFinite(amount)) return value;
  return `${amount > 0 ? "+" : ""}${amount.toLocaleString(undefined, { style: "currency", currency: "USD" })}`;
}

function trendX(index: number, count: number): number {
  return count < 2 ? 398 : 48 + index * 700 / (count - 1);
}

function trendY(value: number, trend: CccVendorDashboard["trend"]): number {
  const prices = trend.flatMap((item) => [Number(item.average_price), Number(item.average_lowest_price)]);
  const minimum = Math.min(...prices);
  const maximum = Math.max(...prices);
  return maximum === minimum ? 105 : 185 - (value - minimum) / (maximum - minimum) * 160;
}

function trendPoints(values: number[], trend: CccVendorDashboard["trend"]): string {
  return values.map((value, index) => `${trendX(index, values.length)},${trendY(value, trend)}`).join(" ");
}

function sortableOfferValue(value: unknown): number | string {
  const rendered = displayOfferValue(value).replace(/[$,]/g, "").trim();
  if (rendered && /^[-+]?(?:\d+\.?\d*|\.\d+)$/.test(rendered)) return Number(rendered);
  return rendered;
}
