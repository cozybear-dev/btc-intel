import type { JobEvent } from "./types";

export function subscribeJob(
  jobId: string,
  onEvent: (event: JobEvent) => void,
  opts: { EventSourceImpl?: typeof EventSource } = {},
): () => void {
  const Impl = opts.EventSourceImpl ?? EventSource;
  const source = new Impl(`/api/jobs/${jobId}/events`);
  let finished = false;
  source.onmessage = (message: MessageEvent) => {
    const event = JSON.parse(message.data) as JobEvent;
    onEvent(event);
    if (event.type === "status") {
      finished = true;
      source.close();
    }
  };
  source.onerror = () => {
    source.close();
    if (!finished) {
      finished = true;
      onEvent({ seq: -1, type: "status", status: "error", error: "event stream disconnected" });
    }
  };
  return () => {
    finished = true;
    source.close();
  };
}
