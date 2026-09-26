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
