import axios from "axios";

const API = "http://localhost:8000"

export async function analyzeTransactions(txs) {
  const res = await axios.post(API+ "/api/transactions/analyze", txs);
  return res.data;
}

export async function summarizeCase(caseData) {
  const res = await axios.post(API + "/api/cases/summary", caseData);
  return res.data;
}
