import { describe, expect, it } from "vitest";

import { parseCsv, parseTransactionFile } from "../parseTransactions";

const HEADER = "id,customer_id,account_id,merchant_id,amount,timestamp,channel";
const GOOD = "t1,C1,A1,M1,100.50,2026-03-14T09:00:00Z,WEB";

const csv = (...rows) => [HEADER, ...rows].join("\n");

describe("parseCsv", () => {
  it("reads a header and rows", () => {
    const rows = parseCsv(csv(GOOD));
    expect(rows).toHaveLength(1);
    expect(rows[0].id).toBe("t1");
  });

  it("handles quoted fields containing commas", () => {
    const rows = parseCsv(csv('t1,C1,A1,"Shop, Inc",100,2026-03-14T09:00:00Z,WEB'));
    expect(rows[0].merchant_id).toBe("Shop, Inc");
  });

  it("handles escaped double quotes", () => {
    const rows = parseCsv(csv('t1,C1,A1,"He said ""hi""",100,2026-03-14T09:00:00Z,WEB'));
    expect(rows[0].merchant_id).toBe('He said "hi"');
  });

  it("tolerates CRLF line endings", () => {
    const rows = parseCsv(`${HEADER}\r\n${GOOD}\r\n`);
    expect(rows).toHaveLength(1);
  });
});

describe("parseTransactionFile — valid input", () => {
  it("parses a good CSV row into the API shape", () => {
    const { transactions, errors } = parseTransactionFile(csv(GOOD), "f.csv");
    expect(errors).toEqual([]);
    expect(transactions[0]).toMatchObject({
      id: "t1",
      customer_id: "C1",
      amount: 100.5,
      channel: "WEB",
      currency: "USD",
    });
    expect(transactions[0].timestamp).toBe("2026-03-14T09:00:00.000Z");
  });

  it("accepts a bare JSON array", () => {
    const json = JSON.stringify([
      {
        id: "t1", customer_id: "C1", account_id: "A1", merchant_id: "M1",
        amount: 10, timestamp: "2026-03-14T09:00:00Z",
      },
    ]);
    const { transactions, errors } = parseTransactionFile(json, "f.json");
    expect(errors).toEqual([]);
    expect(transactions).toHaveLength(1);
  });

  it("accepts a wrapped transactions object", () => {
    const json = JSON.stringify({
      transactions: [
        {
          id: "t1", customer_id: "C1", account_id: "A1", merchant_id: "M1",
          amount: 10, timestamp: "2026-03-14T09:00:00Z",
        },
      ],
    });
    expect(parseTransactionFile(json, "f.json").transactions).toHaveLength(1);
  });

  it("defaults channel to WEB and uppercases it", () => {
    const { transactions } = parseTransactionFile(
      csv("t1,C1,A1,M1,10,2026-03-14T09:00:00Z,pos"),
      "f.csv"
    );
    expect(transactions[0].channel).toBe("POS");
  });

  it("normalises blank optional fields to null", () => {
    const { transactions } = parseTransactionFile(csv(GOOD), "f.csv");
    expect(transactions[0].device_id).toBeNull();
    expect(transactions[0].country).toBeNull();
  });
});

describe("parseTransactionFile — rejects bad rows before any request", () => {
  const cases = [
    ["non-numeric amount", "t1,C1,A1,M1,abc,2026-03-14T09:00:00Z,WEB", /not a number/],
    ["negative amount", "t1,C1,A1,M1,-5,2026-03-14T09:00:00Z,WEB", /must be positive/],
    ["zero amount", "t1,C1,A1,M1,0,2026-03-14T09:00:00Z,WEB", /missing amount|must be positive/],
    ["missing merchant", "t1,C1,A1,,10,2026-03-14T09:00:00Z,WEB", /missing merchant_id/],
    ["bad timestamp", "t1,C1,A1,M1,10,nope,WEB", /not a date/],
    ["bad channel", "t1,C1,A1,M1,10,2026-03-14T09:00:00Z,PIGEON", /must be one of/],
  ];

  it.each(cases)("reports %s", (_name, row, pattern) => {
    const { transactions, errors } = parseTransactionFile(csv(row), "f.csv");
    expect(transactions).toHaveLength(0);
    expect(errors).toHaveLength(1);
    expect(errors[0].message).toMatch(pattern);
    expect(errors[0].row).toBe(1);
  });

  it("reports duplicate ids", () => {
    const { errors } = parseTransactionFile(csv(GOOD, GOOD), "f.csv");
    expect(errors[0].message).toMatch(/duplicate id/);
    expect(errors[0].row).toBe(2);
  });

  it("numbers rows so a user can find them in the file", () => {
    const { errors } = parseTransactionFile(
      csv(GOOD, "t2,C1,A1,M1,abc,2026-03-14T09:00:00Z,WEB"),
      "f.csv"
    );
    expect(errors[0].row).toBe(2);
  });

  it("throws a readable error for malformed JSON", () => {
    expect(() => parseTransactionFile("{not json", "f.json")).toThrow(/Not valid JSON/);
  });

  it("rejects a JSON object that is not a transaction list", () => {
    expect(() => parseTransactionFile('{"foo":1}', "f.json")).toThrow(/Expected a JSON array/);
  });

  it("reports an empty file rather than submitting nothing", () => {
    const { errors } = parseTransactionFile(csv(), "f.csv");
    expect(errors[0].message).toMatch(/No transactions/);
  });
});
