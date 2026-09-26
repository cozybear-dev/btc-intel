import { useState } from "react";
import type { Tag } from "../api/types";
import { shortAddr } from "../lib/format";
import { openAddress, search } from "../state/actions";

export default function SearchBar() {
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<Tag[]>([]);
  return (
    <div className="relative flex-1 max-w-2xl">
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          if (!query.trim()) return;
          const res = await search(query.trim());
          setHits(res?.kind === "text" ? res.tags ?? [] : []);
        }}
      >
        <input
          type="search"
          role="searchbox"
          className="input w-full mono"
          placeholder="txid, txid:vout, address, or tag / entity name"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </form>
      {hits.length > 0 && (
        <ul className="absolute z-20 mt-1 w-full panel max-h-80 overflow-auto text-sm">
          {hits.map((t) => (
            <li key={`${t.address}-${t.pack}-${t.label}`}>
              <button
                className="w-full text-left px-3 py-1 hover:bg-[var(--panel-2)]"
                onClick={() => {
                  setHits([]);
                  void openAddress(t.address);
                }}
              >
                {t.label} <span className="muted mono">{shortAddr(t.address)} · {t.category}{t.abuse ? ` / ${t.abuse}` : ""} · {t.pack}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
