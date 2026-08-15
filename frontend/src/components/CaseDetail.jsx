import { lazy, Suspense, useState } from "react";
import { Box, Divider, Skeleton, Stack, Tab, Tabs, Typography } from "@mui/material";

import NarrativePanel from "./NarrativePanel";
import RiskBadge from "./RiskBadge";
import SignalPanel from "./SignalPanel";
import TransactionTable from "./TransactionTable";

// The force-graph library is the single biggest dependency and lives behind a
// tab most visitors never open, so keep it out of the initial bundle.
const GraphView = lazy(() => import("./GraphView"));

const currency = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
});

function Meta({ label, children }) {
  return (
    <Box>
      <Typography variant="overline" color="text.secondary" display="block">
        {label}
      </Typography>
      <Typography variant="body2" sx={{ fontFamily: "monospace" }}>
        {children}
      </Typography>
    </Box>
  );
}

export default function CaseDetail({
  selectedCase,
  summary,
  summarizing,
  onGenerateSummary,
  model,
}) {
  const [tab, setTab] = useState(0);
  const [highlightedTx, setHighlightedTx] = useState(null);

  if (!selectedCase) {
    return (
      <Typography variant="body2" color="text.secondary">
        Select a case to view its evidence.
      </Typography>
    );
  }

  // Jumping to a cited transaction should land on the table showing it.
  const focusTransaction = (id) => {
    setHighlightedTx(id);
    setTab(2);
  };

  return (
    <Box>
      <Stack
        direction={{ xs: "column", sm: "row" }}
        justifyContent="space-between"
        alignItems={{ sm: "center" }}
        gap={1}
        sx={{ mb: 2 }}
      >
        <Typography variant="h6" sx={{ fontFamily: "monospace" }}>
          {selectedCase.case_id}
        </Typography>
        <RiskBadge
          severity={selectedCase.severity}
          score={selectedCase.risk_score}
          size="medium"
        />
      </Stack>

      <Stack direction="row" spacing={4} flexWrap="wrap" useFlexGap sx={{ mb: 2 }}>
        <Meta label="Customers">{selectedCase.customer_ids.join(", ")}</Meta>
        <Meta label="Accounts">{selectedCase.account_ids.join(", ")}</Meta>
        <Meta label="Transactions">{selectedCase.transactions.length}</Meta>
        <Meta label="Total">{currency.format(selectedCase.total_amount)}</Meta>
      </Stack>

      <Divider />

      <Tabs
        value={tab}
        onChange={(_, v) => setTab(v)}
        sx={{ mb: 2 }}
        variant="scrollable"
        allowScrollButtonsMobile
      >
        <Tab label={`Signals (${selectedCase.signals.length})`} />
        <Tab label="Graph" />
        <Tab label={`Transactions (${selectedCase.transactions.length})`} />
        <Tab label="Narrative" />
      </Tabs>

      {tab === 0 && (
        <SignalPanel
          signals={selectedCase.signals}
          onSelectTransaction={focusTransaction}
        />
      )}
      {tab === 1 && (
        <Suspense fallback={<Skeleton variant="rounded" height={460} />}>
          <GraphView graph={selectedCase.graph} onSelectTransaction={focusTransaction} />
        </Suspense>
      )}
      {tab === 2 && (
        <TransactionTable
          transactions={selectedCase.transactions}
          highlightedId={highlightedTx}
        />
      )}
      {tab === 3 && (
        <NarrativePanel
          summary={summary}
          loading={summarizing}
          model={model}
          onGenerate={() => onGenerateSummary(selectedCase)}
        />
      )}
    </Box>
  );
}
