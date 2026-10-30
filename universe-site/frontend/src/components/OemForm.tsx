import { useEffect, useState } from "react";
import { client, errorText, getPage, saveOem } from "../api";
import type { FormEvent } from "react";
import type { Oem, OemValues, Page, Vin } from "../api";

export default function OemForm({ value, onSaved, onCancel }: {
  value: Oem | null;
  onSaved: (item: Oem) => void;
  onCancel: () => void;
}) {
  const [vinSearch, setVinSearch] = useState(value ? `${value.vin} · ${value.year} ${value.make} ${value.model}` : "");
  const [selectedVin, setSelectedVin] = useState(value ? String(value.id_vin) : "");
  const [vins, setVins] = useState<Vin[]>([]);
  const [listOpen, setListOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const timer = window.setTimeout(async () => {
      setLoading(true);
      try {
        const result: Page<Vin> = await getPage<Vin>("/api/universe/vins", {
          page: 1,
          page_size: 100,
          search: vinSearch,
        });
        setVins(result.items);
        setError("");
      } catch (reason) {
        setError(errorText(reason));
      } finally {
        setLoading(false);
      }
    }, 200);
    return () => window.clearTimeout(timer);
  }, [vinSearch]);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedVin) {
      setError("Select a VIN from the search results.");
      setListOpen(true);
      return;
    }
    const form = new FormData(event.currentTarget);
    const values: OemValues = {
      id_vin: Number(selectedVin),
      oem: String(form.get("oem") || ""),
      description: String(form.get("description") || ""),
      notes: String(form.get("notes") || ""),
    };
    setSaving(true);
    setError("");
    try {
      onSaved(await saveOem(value?.id ?? null, values));
    } catch (reason) {
      setError(errorText(reason));
    } finally {
      setSaving(false);
    }
  };

  return <form className="record-form" onSubmit={submit}>
    <div className="form-grid">
      <label className="full-field vehicle-picker">VIN and vehicle
        <input
          name="vin_search"
          role="combobox"
          aria-autocomplete="list"
          aria-expanded={listOpen}
          aria-controls="oem-vin-options"
          value={vinSearch}
          onFocus={() => setListOpen(true)}
          onBlur={() => window.setTimeout(() => setListOpen(false), 120)}
          onChange={(event) => { setVinSearch(event.target.value); setSelectedVin(""); setListOpen(true); }}
          placeholder="Search VIN, year, make, or model"
          autoComplete="off"
          required
        />
        <input type="hidden" name="id_vin" value={selectedVin} />
        {listOpen && <div id="oem-vin-options" className="vehicle-picker-options" role="listbox">
          {vins.length ? vins.map((vin) => <button
            key={vin.id}
            type="button"
            role="option"
            aria-selected={selectedVin === String(vin.id)}
            onMouseDown={(event) => event.preventDefault()}
            onClick={() => {
              setSelectedVin(String(vin.id));
              setVinSearch(`${vin.vin} · ${vin.vehicle.year} ${vin.vehicle.make} ${vin.vehicle.model}`);
              setListOpen(false);
            }}
          >{vin.vin} · {vin.vehicle.year} {vin.vehicle.make} {vin.vehicle.model}</button>) : <span className="vehicle-picker-empty">{loading ? "Searching…" : error || "No matching VINs"}</span>}
        </div>}
        {!selectedVin && <small className="field-error">Select an existing VIN.</small>}
      </label>
      <label className="full-field">OEM<input name="oem" maxLength={150} defaultValue={value?.oem ?? ""} required /></label>
      <label className="full-field">Description<input name="description" maxLength={4000} defaultValue={value?.description ?? ""} /></label>
      <label className="full-field">Notes<textarea name="notes" rows={3} maxLength={4000} defaultValue={value?.notes ?? ""} /></label>
    </div>
    {error && <p className="field-error" role="alert">{error}</p>}
    <div className="modal-actions"><button type="button" className="outline-button" onClick={onCancel}>Cancel</button><button className="primary-button" disabled={saving}>{saving ? "Saving…" : "Save OEM"}</button></div>
  </form>;
}
