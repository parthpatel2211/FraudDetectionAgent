import { useCallback, useMemo, useState } from "react";

import { analyze, loadDemo, summarize } from "../api";
import { STATIC_DEMO } from "../config";

/**
 * The single owner of analysis state.
 *
 * v1 set `loading` true, awaited a bare fetch with no try/catch, and set it
 * false on the line after. Any network failure threw past the reset and left
 * the button disabled and the spinner running forever. Here every path is
 * terminal: `status` always ends at "ready", "offline", "empty" or "error".
 *
 * status:
 *   idle    - nothing run yet
 *   loading - request in flight
 *   ready   - cases returned
 *   empty   - analysed successfully, nothing crossed the threshold
 *   offline - the API did not answer the demo request; showing bundled results
 *   error   - a custom upload failed (never faked, unlike the demo path)
 */
export default function useAnalysis() {
  const [status, setStatus] = useState("idle");
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [selectedCaseId, setSelectedCaseId] = useState(null);
  const [summaries, setSummaries] = useState({});
  const [summarizing, setSummarizing] = useState(false);

  const settle = useCallback((data) => {
    setResult(data);
    setSelectedCaseId(data.cases[0]?.case_id ?? null);
    setStatus(data.cases.length ? "ready" : "empty");
  }, []);

  /** Load the analysis bundled at build time and seed its narratives. */
  const loadBundled = useCallback(async () => {
    const { default: bundled } = await import("../data/fallbackCases.json");
    setSummaries(
      Object.fromEntries(
        bundled.cases.filter((c) => c._summary).map((c) => [c.case_id, c._summary])
      )
    );
    setResult(bundled);
    setSelectedCaseId(bundled.cases[0]?.case_id ?? null);
    return bundled;
  }, []);

  const runDemo = useCallback(async () => {
    setStatus("loading");
    setError(null);

    // Static hosting (GitHub Pages) has no API to call. This is the expected
    // path there, not a failure, so it gets its own status and no error.
    if (STATIC_DEMO) {
      await loadBundled();
      setStatus("static");
      return;
    }

    try {
      settle(await analyze(await loadDemo()));
    } catch (e) {
      // The demo path must never look broken to someone clicking a portfolio
      // link, so fall back to a precomputed run and say so plainly.
      // Imported dynamically so the 96 kB fixture stays out of the initial
      // bundle - it is only needed when the API is unreachable.
      try {
        await loadBundled();
        setError(e.message);
        setStatus("offline");
      } catch {
        // Even the fallback failed. Surface the original problem.
        setError(e.message);
        setResult(null);
        setStatus("error");
      }
    }
  }, [settle, loadBundled]);

  const runCustom = useCallback(
    async (transactions) => {
      setStatus("loading");
      setError(null);
      try {
        settle(await analyze(transactions));
      } catch (e) {
        // A user's own upload gets the real error. Silently showing them demo
        // data in place of their file would be a lie.
        setError(e.message);
        setResult(null);
        setStatus("error");
      }
    },
    [settle]
  );

  const generateSummary = useCallback(
    async (caseObj) => {
      if (!caseObj) return;
      // Nothing to call on a static host; the bundled summary is already shown.
      if (STATIC_DEMO) return;
      setSummarizing(true);
      try {
        const summary = await summarize(stripLocalFields(caseObj));
        setSummaries((prev) => ({ ...prev, [caseObj.case_id]: summary }));
      } catch (e) {
        setSummaries((prev) => ({
          ...prev,
          [caseObj.case_id]: { error: e.message },
        }));
      } finally {
        setSummarizing(false);
      }
    },
    []
  );

  const reset = useCallback(() => {
    setStatus("idle");
    setResult(null);
    setError(null);
    setSelectedCaseId(null);
    setSummaries({});
  }, []);

  const cases = result?.cases ?? [];
  const selectedCase = useMemo(
    () => cases.find((c) => c.case_id === selectedCaseId) ?? null,
    [cases, selectedCaseId]
  );

  return {
    status,
    error,
    result,
    cases,
    selectedCase,
    selectedCaseId,
    select: setSelectedCaseId,
    summaries,
    summarizing,
    runDemo,
    runCustom,
    generateSummary,
    reset,
    isLoading: status === "loading",
  };
}

/** Drop UI-only keys before sending a case back to the API. */
function stripLocalFields(caseObj) {
  const clean = { ...caseObj };
  delete clean._summary;
  return clean;
}
