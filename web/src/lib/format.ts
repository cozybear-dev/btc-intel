export const SATS_PER_BTC = 100_000_000;

export function formatBtc(sats: number): string {
  const btc = (Number.isFinite(sats) ? sats : 0) / SATS_PER_BTC;
  return `${btc.toFixed(8).replace(/\.?0+$/, "")} BTC`;
}

export function shortAddr(a: string): string {
  return a.length <= 14 ? a : `${a.slice(0, 8)}…${a.slice(-4)}`;
}

export function shortTxid(t: string): string {
  return `${t.slice(0, 8)}…${t.slice(-4)}`;
}

export function formatTime(ts: number | null | undefined): string {
  if (!ts) return "unconfirmed";
  return `${new Date(ts * 1000).toISOString().replace("T", " ").slice(0, 16)} UTC`;
}

export function btcToSats(btc: string): number | null {
  const n = Number(btc);
  if (btc.trim() === "" || !Number.isFinite(n) || n < 0) return null;
  return Math.round(n * SATS_PER_BTC);
}

/** Share (0–1) as a percentage, like the backend report: one decimal below 10%, none above. */
export function formatPct(share: number): string {
  const p = (Number.isFinite(share) ? share : 0) * 100;
  return `${p < 10 ? p.toFixed(1) : p.toFixed(0)}%`;
}

/** Elapsed time, coarse: "45s", "2m 14s", "1h 3m". */
export function formatDuration(ms: number): string {
  const s = Math.max(0, Math.floor(ms / 1000));
  if (s < 60) return `${s}s`;
  if (s < 3600) return `${Math.floor(s / 60)}m ${s % 60}s`;
  return `${Math.floor(s / 3600)}h ${Math.floor((s % 3600) / 60)}m`;
}
