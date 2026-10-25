import { useEffect, useMemo, useState } from "react";

export const TABLE_PAGE_SIZE = 10;

export function useTableSearch<T>(rows: T[], getSearchText: (row: T) => string) {
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);

  const filteredRows = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase();
    if (!needle) return rows;
    return rows.filter((row) => getSearchText(row).toLocaleLowerCase().includes(needle));
  }, [getSearchText, query, rows]);

  const pageCount = Math.max(1, Math.ceil(filteredRows.length / TABLE_PAGE_SIZE));
  const currentPage = Math.min(page, pageCount);
  const startIndex = filteredRows.length === 0 ? 0 : (currentPage - 1) * TABLE_PAGE_SIZE;
  const pageRows = filteredRows.slice(startIndex, startIndex + TABLE_PAGE_SIZE);

  useEffect(() => {
    if (page !== currentPage) setPage(currentPage);
  }, [currentPage, page]);

  const updateQuery = (value: string) => {
    setQuery(value);
    setPage(1);
  };

  return {
    query,
    setQuery: updateQuery,
    pageRows,
    filteredCount: filteredRows.length,
    page: currentPage,
    pageCount,
    start: startIndex + 1,
    end: Math.min(startIndex + TABLE_PAGE_SIZE, filteredRows.length),
    setPage,
    resetPage: () => setPage(1),
  };
}

interface TableSearchPaginationProps {
  query: string;
  onQueryChange: (query: string) => void;
  page: number;
  pageCount: number;
  filteredCount: number;
  start: number;
  end: number;
  onPageChange: (page: number) => void;
  placeholder?: string;
}

export default function TableSearchPagination({
  query,
  onQueryChange,
  page,
  pageCount,
  filteredCount,
  start,
  end,
  onPageChange,
  placeholder = "Search this table…",
}: TableSearchPaginationProps) {
  return (
    <div className="table-tools">
      <input
        className="table-search"
        type="search"
        aria-label={placeholder}
        placeholder={placeholder}
        value={query}
        onChange={(event) => onQueryChange(event.target.value)}
      />
      <div className="table-pagination" aria-label="Table pagination">
        <span className="table-range">
          {filteredCount === 0 ? "0 results" : `${start}–${end} of ${filteredCount}`}
        </span>
        <button type="button" className="small" onClick={() => onPageChange(page - 1)} disabled={page <= 1} aria-label="Previous page">
          Previous
        </button>
        <span className="table-page-number">{page} / {pageCount}</span>
        <button type="button" className="small" onClick={() => onPageChange(page + 1)} disabled={page >= pageCount} aria-label="Next page">
          Next
        </button>
      </div>
    </div>
  );
}
