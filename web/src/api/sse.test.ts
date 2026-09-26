import { subscribeJob } from "./sse";
import type { JobEvent } from "./types";

class FakeEventSource {
  static last: FakeEventSource;
  onmessage: ((m: MessageEvent) => void) | null = null;
  onerror: (() => void) | null = null;
  closed = false;
  constructor(public url: string) { FakeEventSource.last = this; }
  close() { this.closed = true; }
  emit(data: unknown) { this.onmessage?.({ data: JSON.stringify(data) } as MessageEvent); }
}

test("forwards events and closes after status", () => {
  const events: JobEvent[] = [];
  subscribeJob("j1", (e) => events.push(e), { EventSourceImpl: FakeEventSource as unknown as typeof EventSource });
  const es = FakeEventSource.last;
  expect(es.url).toBe("/api/jobs/j1/events");
  es.emit({ seq: 0, type: "stop", item: { node: "addr:x", reason: "unspent", taint: 1, detail: "" } });
  es.emit({ seq: 1, type: "status", status: "done", error: null });
  expect(events.map((e) => e.type)).toEqual(["stop", "status"]);
  expect(es.closed).toBe(true);
});

test("transport errors become a synthetic error status", () => {
  const events: JobEvent[] = [];
  subscribeJob("j2", (e) => events.push(e), { EventSourceImpl: FakeEventSource as unknown as typeof EventSource });
  FakeEventSource.last.onerror?.();
  expect(events).toEqual([{ seq: -1, type: "status", status: "error", error: "event stream disconnected" }]);
  expect(FakeEventSource.last.closed).toBe(true);
});

test("unsubscribe closes the stream", () => {
  const stop = subscribeJob("j3", () => {}, { EventSourceImpl: FakeEventSource as unknown as typeof EventSource });
  stop();
  expect(FakeEventSource.last.closed).toBe(true);
});
