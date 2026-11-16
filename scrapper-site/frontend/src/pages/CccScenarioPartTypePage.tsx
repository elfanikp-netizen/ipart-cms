import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { createCccScenarioPartType, deleteCccScenarioPartType, errorText, listCccScenarioPartTypes, updateCccScenarioPartType } from "../api";
import type { CccScenarioPartTypeValues } from "../api";
import type { CccScenarioPartType } from "../types";

const PAGE_SIZE = 25;
const FIELDS: { key: keyof CccScenarioPartTypeValues; label: string }[] = [
  { key: "part_type_code", label: "Part Type Code" },
  { key: "part_type_description", label: "Part Type Description" },
  { key: "subsystem_category", label: "Subsystem Category" },
  { key: "series_group", label: "Series Group" },
  { key: "reference_notes", label: "Reference Notes" },
  { key: "scenario", label: "Scenario" },
];
const EMPTY: CccScenarioPartTypeValues = {
  part_type_code: "", part_type_description: "", subsystem_category: "", series_group: "", reference_notes: "", scenario: "",
};

export default function CccScenarioPartTypePage() {
  const [rows, setRows] = useState<CccScenarioPartType[]>([]);
  const [total, setTotal] = useState(0);
  const [pages, setPages] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [editing, setEditing] = useState<CccScenarioPartType | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [values, setValues] = useState<CccScenarioPartTypeValues>(EMPTY);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const loadRows = async (targetPage: number, targetSearch = search) => {
    const result = await listCccScenarioPartTypes({ search: targetSearch, page: targetPage, page_size: PAGE_SIZE });
    setRows(result.items);
    setTotal(result.total);
    setPages(result.pages);
  };

  useEffect(() => {
    let active = true;
    const timer = window.setTimeout(() => {
      listCccScenarioPartTypes({ search, page, page_size: PAGE_SIZE }).then((result) => {
        if (!active) return;
        setRows(result.items);
        setTotal(result.total);
        setPages(result.pages);
        setError("");
      }).catch((reason) => { if (active) setError(errorText(reason)); });
    }, 140);
    return () => { active = false; window.clearTimeout(timer); };
  }, [page, search]);

  const save = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      if (editing) await updateCccScenarioPartType(editing.id, values);
      else await createCccScenarioPartType(values);
      setEditing(null);
      setFormOpen(false);
      setValues(EMPTY);
      setPage(1);
      await loadRows(1);
    } catch (reason) {
      setError(errorText(reason));
    } finally {
      setBusy(false);
    }
  };

  const remove = async (row: CccScenarioPartType) => {
    if (!window.confirm(`Delete Part Type Code ${row.part_type_code}?`)) return;
    setError("");
    try {
      await deleteCccScenarioPartType(row.id);
      const nextPage = rows.length === 1 && page > 1 ? page - 1 : page;
      setPage(nextPage);
      await loadRows(nextPage);
    } catch (reason) {
      setError(errorText(reason));
    }
  };

  return (
    <section className="card ccc-page">
      <div className="card-header"><div><h1>CCC Scenario</h1><p className="muted">Part Type Codes and scenarios</p></div>
        <button className="primary" type="button" onClick={() => { setEditing(null); setValues(EMPTY); setFormOpen(true); }}>Add scenario</button>
      </div>
      {error && <p className="error" role="alert">{error}</p>}
      {formOpen && <form className="ccc-edit-form" onSubmit={save}>
        <div className="ccc-form-heading"><h2>{editing ? "Edit scenario" : "New scenario"}</h2><button type="button" className="secondary" onClick={() => { setEditing(null); setFormOpen(false); }}>Cancel</button></div>
        <div className="ccc-fields">{FIELDS.map(({ key, label }) => <label key={key}><span>{label}</span>
          <input required={key === "part_type_code"} maxLength={key === "part_type_code" ? 150 : undefined} value={values[key]} onChange={(event) => setValues((current) => ({ ...current, [key]: event.target.value }))} />
        </label>)}</div>
        <button className="primary" type="submit" disabled={busy}>{busy ? "Saving..." : editing ? "Save changes" : "Create scenario"}</button>
      </form>}
      <div className="ccc-record-toolbar"><input type="search" value={search} onChange={(event) => { setSearch(event.target.value); setPage(1); }} placeholder="Search part type codes" aria-label="Search part type codes" /><span className="muted">{total.toLocaleString()} records</span></div>
      {rows.length === 0 ? <p className="muted ccc-empty">{search ? "No matching scenarios." : "No part type scenarios yet."}</p> :
        <div className="ccc-table-wrap"><table><thead><tr>{FIELDS.map((field) => <th key={field.key}>{field.label}</th>)}<th className="ccc-actions-head">Actions</th></tr></thead><tbody>
          {rows.map((row) => <tr key={row.id}>{FIELDS.map((field) => <td key={field.key}>{row[field.key]}</td>)}<td><div className="ccc-row-actions">
            <button type="button" onClick={() => { setEditing(row); setValues(Object.fromEntries(FIELDS.map(({ key }) => [key, row[key]])) as CccScenarioPartTypeValues); setFormOpen(true); }}>Edit</button>
            <button type="button" className="danger" onClick={() => void remove(row)}>Delete</button>
          </div></td></tr>)}
        </tbody></table></div>}
      <div className="ccc-pagination"><span>{total ? `${(page - 1) * PAGE_SIZE + 1}–${Math.min(page * PAGE_SIZE, total)} of ${total}` : "0 results"}</span><button type="button" disabled={page <= 1} onClick={() => setPage((value) => value - 1)}>Previous</button><span>{page} / {Math.max(1, pages)}</span><button type="button" disabled={page >= pages} onClick={() => setPage((value) => value + 1)}>Next</button></div>
    </section>
  );
}