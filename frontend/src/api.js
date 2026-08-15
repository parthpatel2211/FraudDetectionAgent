/**
 * API client.
 *
 * Always relative: the Vite proxy handles dev, and the SPA shares an origin
 * with the API in production. v1 hardcoded http://localhost:8000, which made
 * the build undeployable.
 */

const BASE = "";

class ApiError extends Error {
  constructor(message, { status, details } = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.details = details;
  }
}

async function request(path, options = {}) {
  let res;
  try {
    res = await fetch(`${BASE}${path}`, options);
  } catch (cause) {
    // Network-level failure: server down, DNS, offline. Distinct from a
    // non-2xx response, and the caller reacts differently to each.
    throw new ApiError("Could not reach the API", { status: 0, cause });
  }

  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new ApiError(data.error || `Request failed (${res.status})`, {
      status: res.status,
      details: data.details,
    });
  }
  return data;
}

function postJson(path, body) {
  return request(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export const analyze = (transactions) => postJson("/api/analyze", { transactions });

export const summarize = (caseData) => postJson("/api/summarize", caseData);

export const health = () => request("/api/health");

export async function loadDemo() {
  const { transactions } = await request("/api/demo");
  return transactions;
}

export { ApiError };
