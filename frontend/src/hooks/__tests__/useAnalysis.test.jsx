import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import useAnalysis from "../useAnalysis";

const CASE = {
  case_id: "CASE-1",
  customer_ids: ["C1"],
  account_ids: ["A1"],
  transactions: [],
  risk_score: 0.9,
  severity: "critical",
  total_amount: 100,
  signals: [],
  graph: { nodes: [], edges: [] },
};

const okResult = (cases) => ({
  cases,
  transactions_analyzed: 10,
  transactions_flagged: cases.length,
  threshold: 0.5,
});

function mockFetch(handler) {
  global.fetch = vi.fn(handler);
}

const jsonResponse = (body, ok = true, status = 200) =>
  Promise.resolve({ ok, status, json: () => Promise.resolve(body) });

beforeEach(() => {
  vi.restoreAllMocks();
});

afterEach(() => {
  delete global.fetch;
});

describe("useAnalysis — terminal states", () => {
  it("starts idle", () => {
    const { result } = renderHook(() => useAnalysis());
    expect(result.current.status).toBe("idle");
    expect(result.current.isLoading).toBe(false);
  });

  it("reaches ready on a successful demo run", async () => {
    mockFetch((url) =>
      url.includes("/api/demo")
        ? jsonResponse({ transactions: [] })
        : jsonResponse(okResult([CASE]))
    );
    const { result } = renderHook(() => useAnalysis());
    await act(async () => { await result.current.runDemo(); });
    await waitFor(() => expect(result.current.status).toBe("ready"));
    expect(result.current.cases).toHaveLength(1);
    expect(result.current.selectedCaseId).toBe("CASE-1");
  });

  it("reaches empty when nothing crosses the threshold", async () => {
    mockFetch((url) =>
      url.includes("/api/demo")
        ? jsonResponse({ transactions: [] })
        : jsonResponse(okResult([]))
    );
    const { result } = renderHook(() => useAnalysis());
    await act(async () => { await result.current.runDemo(); });
    await waitFor(() => expect(result.current.status).toBe("empty"));
  });

  /**
   * The v1 regression: a rejected fetch threw past the `setLoading(false)` that
   * followed it, leaving the spinner running and the button disabled forever.
   */
  it("never gets stuck loading when the network fails", async () => {
    mockFetch(() => Promise.reject(new TypeError("Failed to fetch")));
    const { result } = renderHook(() => useAnalysis());
    await act(async () => { await result.current.runDemo(); });
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.status).not.toBe("loading");
  });

  it("falls back to bundled results when the demo API is unreachable", async () => {
    mockFetch(() => Promise.reject(new TypeError("Failed to fetch")));
    const { result } = renderHook(() => useAnalysis());
    await act(async () => { await result.current.runDemo(); });
    await waitFor(() => expect(result.current.status).toBe("offline"));
    expect(result.current.cases.length).toBeGreaterThan(0);
    expect(result.current.error).toBeTruthy();
  });

  it("falls back when the demo API returns an error status", async () => {
    mockFetch(() => jsonResponse({ error: "boom" }, false, 500));
    const { result } = renderHook(() => useAnalysis());
    await act(async () => { await result.current.runDemo(); });
    await waitFor(() => expect(result.current.status).toBe("offline"));
  });

  it("preseeds narratives in offline mode so the demo is self-contained", async () => {
    mockFetch(() => Promise.reject(new TypeError("Failed to fetch")));
    const { result } = renderHook(() => useAnalysis());
    await act(async () => { await result.current.runDemo(); });
    await waitFor(() => expect(result.current.status).toBe("offline"));
    expect(Object.keys(result.current.summaries).length).toBeGreaterThan(0);
  });
});

describe("useAnalysis — custom uploads are never faked", () => {
  it("surfaces the real error instead of substituting demo data", async () => {
    mockFetch(() => Promise.reject(new TypeError("Failed to fetch")));
    const { result } = renderHook(() => useAnalysis());
    await act(async () => { await result.current.runCustom([{ id: "x" }]); });
    await waitFor(() => expect(result.current.status).toBe("error"));
    expect(result.current.result).toBeNull();
    expect(result.current.cases).toEqual([]);
  });

  it("reports a validation error from the API", async () => {
    mockFetch(() =>
      jsonResponse({ error: "Invalid transaction payload", details: [] }, false, 400)
    );
    const { result } = renderHook(() => useAnalysis());
    await act(async () => { await result.current.runCustom([{ id: "x" }]); });
    await waitFor(() => expect(result.current.status).toBe("error"));
    expect(result.current.error).toMatch(/Invalid transaction payload/);
  });

  it("reaches ready on a successful upload", async () => {
    mockFetch(() => jsonResponse(okResult([CASE])));
    const { result } = renderHook(() => useAnalysis());
    await act(async () => { await result.current.runCustom([{ id: "x" }]); });
    await waitFor(() => expect(result.current.status).toBe("ready"));
  });
});

describe("useAnalysis — summaries", () => {
  it("stores a generated summary against its case", async () => {
    mockFetch(() =>
      jsonResponse({
        case_id: "CASE-1", narrative: "n", recommendation: "r",
        next_steps: ["s"], source: "template",
      })
    );
    const { result } = renderHook(() => useAnalysis());
    await act(async () => { await result.current.generateSummary(CASE); });
    await waitFor(() =>
      expect(result.current.summaries["CASE-1"].narrative).toBe("n")
    );
    expect(result.current.summarizing).toBe(false);
  });

  it("records an error against the case rather than throwing", async () => {
    mockFetch(() => Promise.reject(new TypeError("Failed to fetch")));
    const { result } = renderHook(() => useAnalysis());
    await act(async () => { await result.current.generateSummary(CASE); });
    await waitFor(() => expect(result.current.summaries["CASE-1"].error).toBeTruthy());
    expect(result.current.summarizing).toBe(false);
  });

  it("strips UI-only fields before sending the case back", async () => {
    const seen = [];
    mockFetch((url, opts) => {
      seen.push(JSON.parse(opts.body));
      return jsonResponse({
        case_id: "CASE-1", narrative: "n", recommendation: "r",
        next_steps: ["s"], source: "template",
      });
    });
    const { result } = renderHook(() => useAnalysis());
    await act(async () => {
      await result.current.generateSummary({ ...CASE, _summary: { narrative: "old" } });
    });
    expect(seen[0]).not.toHaveProperty("_summary");
  });
});

describe("useAnalysis — selection and reset", () => {
  it("selects a case by id", async () => {
    const second = { ...CASE, case_id: "CASE-2" };
    mockFetch(() => jsonResponse(okResult([CASE, second])));
    const { result } = renderHook(() => useAnalysis());
    await act(async () => { await result.current.runCustom([]); });
    act(() => result.current.select("CASE-2"));
    await waitFor(() => expect(result.current.selectedCase.case_id).toBe("CASE-2"));
  });

  it("reset returns to idle", async () => {
    mockFetch(() => jsonResponse(okResult([CASE])));
    const { result } = renderHook(() => useAnalysis());
    await act(async () => { await result.current.runCustom([]); });
    act(() => result.current.reset());
    expect(result.current.status).toBe("idle");
    expect(result.current.result).toBeNull();
  });
});
