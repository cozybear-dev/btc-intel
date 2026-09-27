import { btcToSats, formatBtc, formatDuration, formatPct, formatTime, shortAddr, shortTxid } from "./format";

test("formatBtc trims trailing zeros and stays finite", () => {
  expect(formatBtc(0)).toBe("0 BTC");
  expect(formatBtc(150_000_000)).toBe("1.5 BTC");
  expect(formatBtc(100_000_000)).toBe("1 BTC");
  expect(formatBtc(10)).toBe("0.0000001 BTC");
  expect(formatBtc(2_100_000_000_000_000)).toBe("21000000 BTC");
});

test("short identifiers", () => {
  expect(shortAddr("bc1qntndgqfx46wks63jep34cjk3pw63es86kp45c6")).toBe("bc1qntnd…45c6");
  expect(shortAddr("1short")).toBe("1short");
  expect(shortTxid("c5908e04daea83ec38101692a0663130bcafa7d0ddaef1fd8821d179d1db1c8c")).toBe("c5908e04…1c8c");
});

test("formatTime", () => {
  expect(formatTime(null)).toBe("unconfirmed");
  expect(formatTime(1749188499)).toBe("2025-06-06 05:41 UTC");
});

test("btcToSats", () => {
  expect(btcToSats("0.001")).toBe(100_000);
  expect(btcToSats("1.23456789")).toBe(123_456_789);
  expect(btcToSats("-1")).toBeNull();
  expect(btcToSats("abc")).toBeNull();
});

test("formatPct matches the backend report", () => {
  expect(formatPct(0.6667)).toBe("67%");
  expect(formatPct(0.04)).toBe("4.0%");
  expect(formatPct(1)).toBe("100%");
});

test("formatDuration", () => {
  expect(formatDuration(0)).toBe("0s");
  expect(formatDuration(45_900)).toBe("45s");
  expect(formatDuration(134_000)).toBe("2m 14s");
  expect(formatDuration(3_780_000)).toBe("1h 3m");
  expect(formatDuration(-5)).toBe("0s");
});
