import React, { useState } from "react";
import {
  Box,
  Typography,
  Button,
  Chip,
  Stack,
  Divider
} from "@mui/material";

import RiskBadge from "./RiskBadge";
import TransactionTable from "./TransactionTable";
import { summarizeCase } from "../api";

export default function CaseDetail({ selectedCase }) {
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(false);

  if (!selectedCase) {
    return <Typography>Select a case to view details.</Typography>;
  }

 const handleSummarize = async () => {
  setLoading(true);

  const payload = {
  case_id: selectedCase.case_id,
  customer_id: selectedCase.customer_id,
  primary_account_id: selectedCase.primary_account_id,
  risk_score: selectedCase.risk_score,
  signals: selectedCase.signals.map(s => ({
    name: s.name,
    score: s.score,
    explanation: s.explanation
  })),
  transactions: selectedCase.transactions.map(t => ({
    id: t.id,
    customer_id: t.customer_id,
    account_id: t.account_id,
    merchant_id: t.merchant_id,
    device_id: t.device_id,
    ip_address: t.ip_address,
    amount: t.amount,
    currency: t.currency,
    timestamp: new Date(t.timestamp).toISOString(),   // ⭐ FIXED ⭐
    channel: t.channel,
    country: t.country
  }))
};

  try {
    const res = await summarizeCase(payload);
    setSummary(res);
  } finally {
    setLoading(false);
  }
};
  return (
    <Box>
      <Box display="flex" justifyContent="space-between" mb={1}>
        <Typography variant="h5">
          Case {selectedCase.case_id.slice(0, 8)}…
        </Typography>
        <RiskBadge score={selectedCase.risk_score} />
      </Box>

      <Typography variant="body1">
        <strong>Customer:</strong> {selectedCase.customer_id}
      </Typography>
      <Typography variant="body1" mb={2}>
        <strong>Account:</strong> {selectedCase.primary_account_id}
      </Typography>

      <Divider sx={{ my: 2 }} />

      <Typography variant="h6">Signals</Typography>
      <Stack direction="column" spacing={1} sx={{ my: 1 }}>
        {selectedCase.signals.map((s) => (
          <Chip
            key={s.name}
            label={`${s.name} (${s.score.toFixed(2)})`}
            color="warning"
            variant="outlined"
          />
        ))}
      </Stack>

      <Divider sx={{ my: 2 }} />

      <Typography variant="h6">Transactions</Typography>
      <TransactionTable transactions={selectedCase.transactions} />

      <Button
        variant="contained"
        sx={{ mt: 2 }}
        onClick={handleSummarize}
        disabled={loading}
      >
        {loading ? "Summarizing…" : "Generate Summary"}
      </Button>

      {summary && (
        <Box sx={{ mt: 3 }}>
          <Typography variant="h6">Narrative</Typography>
          <Typography variant="body2" sx={{ mb: 2 }}>
            {summary.narrative}
          </Typography>

          <Typography variant="h6">Recommendation</Typography>
          <Typography variant="body2">{summary.recommendation}</Typography>
        </Box>
      )}
    </Box>
  );
}
