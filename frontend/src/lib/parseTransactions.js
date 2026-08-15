/**
 * Client-side parsing and validation for uploaded transaction files.
 *
 * Mirrors the backend's Transaction model closely enough to catch the common
 * mistakes before a request is sent. The server still validates - this is a
 * better error message, not a security boundary.
 */

const REQUIRED = ["id", "customer_id", "account_id", "merchant_id", "amount", "timestamp"];
const CHANNELS = ["WEB", "MOBILE", "POS", "ATM", "TRANSFER"];

export function parseTransactionFile(text, filename = "") {
  const isCsv = filename.toLowerCase().endsWith(".csv");
  const rows = isCsv ? parseCsv(text) : parseJson(text);
  return validateRows(rows);
}

function parseJson(text) {
  let data;
  try {
    data = JSON.parse(text);
  } catch (e) {
    throw new Error(`Not valid JSON: ${e.message}`);
  }
  if (Array.isArray(data)) return data;
  if (data && Array.isArray(data.transactions)) return data.transactions;
  throw new Error("Expected a JSON array, or an object with a 'transactions' array.");
}

/** Minimal RFC4180-ish reader: handles quoted fields and embedded commas. */
export function parseCsv(text) {
  const lines = text.replace(/\r\n/g, "\n").split("\n").filter((l) => l.trim() !== "");
  if (!lines.length) throw new Error("The file is empty.");

  const header = splitCsvLine(lines[0]).map((h) => h.trim());
  if (!header.length) throw new Error("Could not read a header row.");

  return lines.slice(1).map((line) => {
    const cells = splitCsvLine(line);
    return Object.fromEntries(header.map((h, i) => [h, (cells[i] ?? "").trim()]));
  });
}

function splitCsvLine(line) {
  const out = [];
  let cur = "";
  let quoted = false;
  for (let i = 0; i < line.length; i += 1) {
    const ch = line[i];
    if (quoted) {
      if (ch === '"' && line[i + 1] === '"') {
        cur += '"';
        i += 1;
      } else if (ch === '"') {
        quoted = false;
      } else {
        cur += ch;
      }
    } else if (ch === '"') {
      quoted = true;
    } else if (ch === ",") {
      out.push(cur);
      cur = "";
    } else {
      cur += ch;
    }
  }
  out.push(cur);
  return out;
}

function validateRows(rows) {
  const errors = [];
  const transactions = [];
  const seenIds = new Set();

  if (!rows.length) {
    return { transactions, errors: [{ row: null, message: "No transactions found." }] };
  }

  rows.forEach((raw, i) => {
    const rowNo = i + 1;
    if (typeof raw !== "object" || raw === null || Array.isArray(raw)) {
      errors.push({ row: rowNo, message: "Not an object." });
      return;
    }

    const missing = REQUIRED.filter(
      (k) => raw[k] === undefined || raw[k] === null || raw[k] === ""
    );
    if (missing.length) {
      errors.push({ row: rowNo, message: `missing ${missing.join(", ")}` });
      return;
    }

    const amount = Number(raw.amount);
    if (!Number.isFinite(amount)) {
      errors.push({ row: rowNo, message: `amount "${raw.amount}" is not a number` });
      return;
    }
    if (amount <= 0) {
      errors.push({ row: rowNo, message: `amount must be positive, got ${amount}` });
      return;
    }

    const parsedDate = new Date(raw.timestamp);
    if (Number.isNaN(parsedDate.getTime())) {
      errors.push({ row: rowNo, message: `timestamp "${raw.timestamp}" is not a date` });
      return;
    }

    const channel = (raw.channel || "WEB").toUpperCase();
    if (!CHANNELS.includes(channel)) {
      errors.push({
        row: rowNo,
        message: `channel "${raw.channel}" must be one of ${CHANNELS.join(", ")}`,
      });
      return;
    }

    const id = String(raw.id);
    if (seenIds.has(id)) {
      errors.push({ row: rowNo, message: `duplicate id "${id}"` });
      return;
    }
    seenIds.add(id);

    transactions.push({
      id,
      customer_id: String(raw.customer_id),
      account_id: String(raw.account_id),
      merchant_id: String(raw.merchant_id),
      device_id: emptyToNull(raw.device_id),
      ip_address: emptyToNull(raw.ip_address),
      amount,
      currency: raw.currency || "USD",
      timestamp: parsedDate.toISOString(),
      channel,
      country: emptyToNull(raw.country),
    });
  });

  return { transactions, errors };
}

function emptyToNull(v) {
  return v === undefined || v === null || v === "" ? null : String(v);
}
