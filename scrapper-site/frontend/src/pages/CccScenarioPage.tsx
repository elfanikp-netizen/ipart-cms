import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import {
  createCccScenario,
  deleteCccScenario,
  errorText,
  listCccScenarios,
  updateCccScenario,
} from "../api";
import type { CccScenario, CccScenarioPage } from "../types";
import "./ccc-scenario.css";

const PAGE_SIZE = 25;
type ScenarioValues = Pick<CccScenario, "part_code" | "part_description" | "part_family" | "scenario">;
const EMPTY_VALUES: ScenarioValues = { part_code: "", part_description: "", part_family: "", scenario: "" };

export default function CccScenarioPage() {
  const [rows, setRows] = useState<CccScenario[]>([]);
  const [total, setTotal] = useState(0);
  const [pages, setPages] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [editing, setEditing] = useState<CccScenario | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [values, setValues] = useState<ScenarioValues>(EMPTY_VALUES);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const loadRows = async (targetPage = page, targetSearch = search) => {
    const result: CccScenarioPage = await listCccScenarios({
      search: targetSearch,
      page: targetPage,
      page_size: PAGE_SIZE,
    });
    setRows(result.items);
    setTotal(result.total);
    setPages(result.pages);
  };

  useEffect(() => {
    let active = true;
    const timer = window.setTimeout(() => {
      listCccScenarios({ search, page, page_size: PAGE_SIZE })
        .then((result) => {
          if (!active) return;
          setRows(result.items);
          setTotal(result.total);
          setPages(result.pages);
          setError("");
        })
        .catch((reason) => { if (active) setError(errorText(reason)); });
    }, 140);
    return () => { active = false; window.clearTimeout(timer); };
  }, [page, search]);

  const startCreate = () => {
    setEditing(null);
    setValues(EMPTY_VALUES);
    setFormOpen(true);
  };

  const startEdit = (row: CccScenario) => {
    setEditing(row);
    setValues({
      part_code: row.part_code,
      part_description: row.part_description,
      part_family: row.part_family,
      scenario: row.scenario,
    });
    setFormOpen(true);
  };

  const save = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const payload = { ...values, part_code: values.part_code.trim() };
      if (editing) await updateCccScenario(editing.id, payload);
      else await createCccScenario(payload);
      setEditing(null);
      setFormOpen(false);
      setValues(EMPTY_VALUES);
      setPage(1);
      await loadRows(1);
    } catch (reason) {
      setError(errorText(reason));
    } finally {
      setBusy(false);
    }
  };

  const remove = async (row: CccScenario) => {
    if (!window.confirm(`Delete Part Code ${row.part_code}?`)) return;
    setError("");
    try {
      await deleteCccScenario(row.id);
      const nextPage = rows.length === 1 && page > 1 ? page - 1 : page;
      setPage(nextPage);
      await loadRows(nextPage);
    } catch (reason) {
      setError(errorText(reason));
    }
  };

  const setField = (field: keyof ScenarioValues, value: string) => {
    setValues((current) => ({ ...current, [field]: value }));
  };

  return (
    <section className="card ccc-page">
      <div className="card-header">
        <div>
          <h1>CCC Scenario</h1>
          <p className="muted">Part Codes, descriptions, families, and scenarios</p>
        </div>
        <button className="primary" type="button" onClick={startCreate}>Add scenario</button>
      </div>

      {error && <p className="error" role="alert">{error}</p>}

      {formOpen && (
        <form className="ccc-edit-form" onSubmit={save}>
          <div className="ccc-form-heading">
            <h2>{editing ? "Edit scenario" : "New scenario"}</h2>
            <button type="button" className="secondary" onClick={() => { setEditing(null); setFormOpen(false); }}>Cancel</button>
          </div>
          <div className="ccc-fields">
            <label>
              <span>Part Code</span>
              <input required maxLength={150} value={values.part_code} onChange={(event) => setField("part_code", event.target.value)} />
            </label>
            <label>
              <span>Part Description</span>
              <input value={values.part_description} onChange={(event) => setField("part_description", event.target.value)} />
            </label>
            <label>
              <span>Part Family</span>
              <input value={values.part_family} onChange={(event) => setField("part_family", event.target.value)} />
            </label>
            <label>
              <span>Scenario</span>
              <input value={values.scenario} onChange={(event) => setField("scenario", event.target.value)} />
            </label>
          </div>
          <button className="primary" type="submit" disabled={busy}>{busy ? "Saving..." : editing ? "Save changes" : "Create scenario"}</button>
        </form>
      )}

      <div className="ccc-record-toolbar">
        <input
          type="search"
          value={search}
          onChange={(event) => { setSearch(event.target.value); setPage(1); }}
          placeholder="Search CCC scenarios"
          aria-label="Search CCC scenarios"
        />
        <span className="muted">{total.toLocaleString()} records</span>
      </div>

      {rows.length === 0 ? (
        <p className="muted ccc-empty">{search ? "No matching scenarios." : "No CCC scenarios yet."}</p>
      ) : (
        <div className="ccc-table-wrap">
          <table>
            <thead><tr><th>Part Code</th><th>Part Description</th><th>Part Family</th><th>Scenario</th><th className="ccc-actions-head">Actions</th></tr></thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id}>
                  <td>{row.part_code}</td>
                  <td>{row.part_description}</td>
                  <td>{row.part_family}</td>
                  <td>{row.scenario}</td>
                  <td>
                    <div className="ccc-row-actions">
                      <button type="button" onClick={() => startEdit(row)}>Edit</button>
                      <button type="button" className="danger" onClick={() => remove(row)}>Delete</button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="ccc-pagination">
        <span>{total ? `${(page - 1) * PAGE_SIZE + 1}–${Math.min(page * PAGE_SIZE, total)} of ${total}` : "0 results"}</span>
        <button type="button" disabled={page <= 1} onClick={() => setPage((value) => value - 1)}>Previous</button>
        <span>{page} / {Math.max(1, pages)}</span>
        <button type="button" disabled={page >= pages} onClick={() => setPage((value) => value + 1)}>Next</button>
      </div>
    </section>
  );
}
