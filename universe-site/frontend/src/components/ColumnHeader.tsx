import "./ColumnHeader.css";

export interface ColumnFilterValue {
  value: string;
  mode: "any" | "empty" | "nonempty";
}

export default function ColumnHeader({
  label,
  field,
  filter,
  sort,
  onFilter,
  onSort,
}: {
  label: string;
  field: string;
  filter: ColumnFilterValue;
  sort: { field: string; direction: "asc" | "desc" };
  onFilter: (field: string, value: ColumnFilterValue) => void;
  onSort: (field: string) => void;
}) {
  const marker = sort.field === field ? (sort.direction === "asc" ? "↑" : "↓") : "↕";
  return (
    <th className="filterable-header">
      <button className="column-sort" type="button" onClick={() => onSort(field)} aria-label={`Sort by ${label} ${sort.field === field ? (sort.direction === "asc" ? "descending" : "ascending") : "ascending"}`}>
        <span>{label}</span><span className="sort-marker" aria-hidden="true">{marker}</span>
      </button>
      <div className="column-filter">
        <input aria-label={`Filter ${label}`} value={filter.value} placeholder="Filter" onChange={(event) => onFilter(field, { ...filter, value: event.target.value })} />
        <select aria-label={`Empty values for ${label}`} value={filter.mode} onChange={(event) => onFilter(field, { ...filter, mode: event.target.value as ColumnFilterValue["mode"] })}>
          <option value="any">Any</option>
          <option value="empty">Empty</option>
          <option value="nonempty">Not empty</option>
        </select>
      </div>
    </th>
  );
}
