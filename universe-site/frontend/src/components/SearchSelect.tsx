import { useEffect, useId, useRef, useState } from "react";

export interface SearchSelectOption {
  label: string;
  value: string;
}

interface SearchSelectProps {
  label: string;
  value: string;
  options: SearchSelectOption[];
  placeholder?: string;
  allowCustom?: boolean;
  className?: string;
  onSearch?: (query: string) => void;
  selectedLabel?: string;
  loading?: boolean;
  emptyMessage?: string;
  onChange: (value: string) => void;
}

export default function SearchSelect({
  label,
  value,
  options,
  placeholder,
  allowCustom = false,
  className = "",
  onSearch,
  selectedLabel: selectedLabelOverride,
  loading = false,
  emptyMessage,
  onChange,
}: SearchSelectProps) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(0);
  const rootRef = useRef<HTMLDivElement>(null);
  const pickerId = useId();
  const selectedLabel = selectedLabelOverride ?? options.find((option) => option.value === value)?.label ?? value;
  const filtered = options.filter((option) => option.label.toLocaleLowerCase().includes(query.trim().toLocaleLowerCase()));

  useEffect(() => {
    const closeOutside = (event: PointerEvent) => {
      if (rootRef.current && !rootRef.current.contains(event.target as Node)) {
        setOpen(false);
        setQuery("");
      }
    };
    document.addEventListener("pointerdown", closeOutside);
    return () => document.removeEventListener("pointerdown", closeOutside);
  }, []);

  const choose = (option: SearchSelectOption) => {
    onChange(option.value);
    setQuery("");
    setActiveIndex(0);
    setOpen(false);
  };

  return <div className={`search-select${className ? ` ${className}` : ""}`} ref={rootRef}>
    <label htmlFor={pickerId}>{label}</label>
    <input
      id={pickerId}
      type="search"
      role="combobox"
      aria-autocomplete="list"
      aria-expanded={open}
      aria-controls={`${pickerId}-options`}
      aria-activedescendant={open && filtered[activeIndex] ? `${pickerId}-${activeIndex}` : undefined}
      value={open ? query : selectedLabel}
      placeholder={placeholder ?? `Search ${label.toLocaleLowerCase()}`}
      autoComplete="off"
      onFocus={() => { setQuery(""); setOpen(true); setActiveIndex(0); }}
      onClick={() => { if (!open) { setQuery(""); setOpen(true); setActiveIndex(0); } }}
      onChange={(event) => {
        const nextQuery = event.target.value;
        setQuery(nextQuery);
        setActiveIndex(0);
        setOpen(true);
        onSearch?.(nextQuery);
        if (allowCustom) onChange(nextQuery);
      }}
      onKeyDown={(event) => {
        if (event.key === "ArrowDown") {
          event.preventDefault();
          setOpen(true);
          setActiveIndex((index) => Math.min(index + 1, Math.max(filtered.length - 1, 0)));
        } else if (event.key === "ArrowUp") {
          event.preventDefault();
          setOpen(true);
          setActiveIndex((index) => Math.max(index - 1, 0));
        } else if (event.key === "Enter" && open) {
          event.preventDefault();
          if (filtered[activeIndex]) choose(filtered[activeIndex]);
          else if (allowCustom) setOpen(false);
        } else if (event.key === "Escape") {
          setOpen(false);
          setQuery("");
        }
      }}
    />
    {open && <div className="search-select-options" id={`${pickerId}-options`} role="listbox" aria-label={`${label} options`}>
      {filtered.length ? filtered.slice(0, 100).map((option, index) => <button
        id={`${pickerId}-${index}`}
        key={`${option.value}-${index}`}
        type="button"
        role="option"
        aria-selected={option.value === value}
        className={index === activeIndex ? "active" : ""}
        onMouseDown={(event) => event.preventDefault()}
        onMouseEnter={() => setActiveIndex(index)}
        onClick={() => choose(option)}
      >{option.label}</button>) : <span className="search-select-empty">{loading ? `Searching ${label.toLocaleLowerCase()}s…` : emptyMessage ?? `No matching ${label.toLocaleLowerCase()}s`}</span>}
    </div>}
  </div>;
}