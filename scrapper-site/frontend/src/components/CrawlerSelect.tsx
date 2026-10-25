import { useEffect, useMemo, useRef, useState } from "react";
import type { Crawler } from "../types";

interface Props {
  crawlers: Crawler[];
  value: string;
  onChange: (id: string) => void;
}

export default function CrawlerSelect({ crawlers, value, onChange }: Props) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [activeIndex, setActiveIndex] = useState(0);
  const rootRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const selected = crawlers.find((crawler) => crawler.id === value) ?? null;
  const filtered = useMemo(() => {
    const search = query.trim().toLocaleLowerCase();
    if (!search) return crawlers;
    return crawlers.filter((crawler) =>
      `${crawler.name} ${crawler.group} ${crawler.id}`.toLocaleLowerCase().includes(search)
    );
  }, [crawlers, query]);

  const groups = useMemo(() => {
    const map = new Map<string, Crawler[]>();
    for (const crawler of filtered) {
      const items = map.get(crawler.group) ?? [];
      items.push(crawler);
      map.set(crawler.group, items);
    }
    return [...map.entries()];
  }, [filtered]);

  useEffect(() => {
    if (activeIndex >= filtered.length) setActiveIndex(Math.max(0, filtered.length - 1));
  }, [activeIndex, filtered.length]);

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

  const choose = (crawler: Crawler) => {
    if (!crawler.available) return;
    onChange(crawler.id);
    setOpen(false);
    setQuery("");
  };

  const handleKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
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
      const crawler = filtered[activeIndex];
      if (crawler?.available) choose(crawler);
    } else if (event.key === "Escape" && open) {
      event.preventDefault();
      setOpen(false);
      setQuery("");
    }
  };

  let flatIndex = -1;

  return (
    <div className="crawler-picker" ref={rootRef}>
      <label htmlFor="crawler-search">Crawler</label>
      <input
        ref={inputRef}
        id="crawler-search"
        type="search"
        role="combobox"
        aria-autocomplete="list"
        aria-expanded={open}
        aria-controls="crawler-options"
        aria-activedescendant={open && filtered[activeIndex] ? `crawler-option-${filtered[activeIndex].id}` : undefined}
        placeholder={selected ? selected.name : "Search crawlers…"}
        value={open ? query : selected?.name ?? ""}
        onFocus={() => setOpen(true)}
        onClick={() => setOpen(true)}
        onChange={(event) => {
          setQuery(event.target.value);
          setActiveIndex(0);
          setOpen(true);
        }}
        onKeyDown={handleKeyDown}
        autoComplete="off"
      />
      {open && (
        <div className="crawler-options" id="crawler-options" role="listbox" aria-label="Crawlers">
          {groups.length === 0 ? (
            <div className="crawler-empty">No crawlers match “{query}”</div>
          ) : groups.map(([group, items]) => (
            <div className="crawler-group" key={group}>
              <div className="crawler-group-label">{group}</div>
              {items.map((crawler) => {
                flatIndex += 1;
                const index = flatIndex;
                return (
                  <button
                    id={`crawler-option-${crawler.id}`}
                    key={crawler.id}
                    type="button"
                    role="option"
                    aria-selected={crawler.id === value}
                    disabled={!crawler.available}
                    className={`crawler-option${crawler.id === value ? " selected" : ""}${index === activeIndex ? " focused" : ""}`}
                    onMouseEnter={() => setActiveIndex(index)}
                    onClick={() => choose(crawler)}
                  >
                    <span>{crawler.name}</span>
                    {!crawler.available && <span className="crawler-unavailable">not found</span>}
                  </button>
                );
              })}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
