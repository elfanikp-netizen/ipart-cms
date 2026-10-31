import { useEffect, useState } from "react";
import { client, errorText, getPage, saveOem } from "../api";
import type { FormEvent } from "react";
import type { Oem, OemValues, Page, Vin } from "../api";
import SearchSelect from "./SearchSelect";

export default function OemForm({ value, onSaved, onCancel }: {
  value: Oem | null;
  onSaved: (item: Oem) => void;
  onCancel: () => void;
}) {
  const [vinSearch, setVinSearch] = useState(value ? `${value.vin} · ${value.year} ${value.make} ${value.model}` : "");
  const [selectedVin, setSelectedVin] = useState(value ? String(value.id_vin) : "");
  const [vins, setVins] = useState<Vin[]>([]);
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
      <div className="full-field">
        <SearchSelect
          label="VIN and vehicle"
          value={selectedVin}
          selectedLabel={vinSearch}
          options={vins.map((vin) => ({ label: `${vin.vin} · ${vin.vehicle.year} ${vin.vehicle.make} ${vin.vehicle.model}`, value: String(vin.id) }))}
          placeholder="Search VIN, year, make, or model"
          onSearch={(query) => { setVinSearch(query); setSelectedVin(""); }}
          loading={loading}
          emptyMessage={error || "No matching VINs"}
          onChange={(vinId) => {
            const vin = vins.find((item) => String(item.id) === vinId);
            setSelectedVin(vinId);
            if (vin) setVinSearch(`${vin.vin} · ${vin.vehicle.year} ${vin.vehicle.make} ${vin.vehicle.model}`);
          }}
        />
        <input type="hidden" name="id_vin" value={selectedVin} />
        {!selectedVin && <small className="field-error">Select an existing VIN.</small>}
      </div>
      <label className="full-field">OEM<input name="oem" maxLength={150} defaultValue={value?.oem ?? ""} required /></label>
      <label className="full-field">Description<input name="description" maxLength={4000} defaultValue={value?.description ?? ""} /></label>
      <label className="full-field">Notes<textarea name="notes" rows={3} maxLength={4000} defaultValue={value?.notes ?? ""} /></label>
    </div>
    {error && <p className="field-error" role="alert">{error}</p>}
    <div className="modal-actions"><button type="button" className="outline-button" onClick={onCancel}>Cancel</button><button className="primary-button" disabled={saving}>{saving ? "Saving…" : "Save OEM"}</button></div>
  </form>;
}
