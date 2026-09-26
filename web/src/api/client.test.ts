import { ApiError, api } from "./client";

function mockFetch(status: number, body: unknown, contentType = "application/json") {
  const fn = vi.fn().mockResolvedValue(
    // 204/205/304 are null-body statuses: the Fetch spec forbids any body, even "".
    new Response([204, 205, 304].includes(status) ? null : typeof body === "string" ? body : JSON.stringify(body), {
      status,
      headers: { "content-type": contentType },
    }),
  );
  vi.stubGlobal("fetch", fn);
  return fn;
}

afterEach(() => vi.unstubAllGlobals());

test("builds URLs and parses JSON", async () => {
  const fetchFn = mockFetch(200, { kind: "text", query: "lazarus", tags: [] });
  const res = await api.search("lazarus group");
  expect(res.kind).toBe("text");
  expect(fetchFn.mock.calls[0][0]).toBe("/api/search?q=lazarus%20group");
});

test("posts JSON bodies", async () => {
  const fetchFn = mockFetch(202, { job_id: "j1" });
  await api.startTrace({ txid: "ab".repeat(32) }, { max_hops: 3 });
  const [url, init] = fetchFn.mock.calls[0];
  expect(url).toBe("/api/trace");
  expect(init.method).toBe("POST");
  expect(JSON.parse(init.body)).toEqual({ seed: { txid: "ab".repeat(32) }, policy: { max_hops: 3 } });
});

test("maps error body to ApiError with incomplete", async () => {
  mockFetch(502, { detail: "all backends failed", incomplete: true });
  const err = await api.tx("ab".repeat(32)).catch((e) => e);
  expect(err).toBeInstanceOf(ApiError);
  expect(err.status).toBe(502);
  expect(err.message).toBe("all backends failed");
  expect(err.incomplete).toBe(true);
});

test("handles 204 and text responses", async () => {
  mockFetch(204, "");
  expect(await api.deleteTag(3)).toBeUndefined();
  mockFetch(200, "title: t\ntags: []\n", "application/yaml");
  expect(await api.exportTags()).toContain("title: t");
});

test("non-JSON error bodies fall back to status text", async () => {
  mockFetch(500, "<html>oops</html>", "text/html");
  const err = await api.health().catch((e) => e);
  expect(err.status).toBe(500);
  expect(err.incomplete).toBe(false);
});
