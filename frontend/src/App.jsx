import { useEffect, useMemo, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Container,
  CssBaseline,
  Grid,
  Skeleton,
  Stack,
  Typography,
} from "@mui/material";
import { ThemeProvider } from "@mui/material/styles";

import AppHeader from "./components/AppHeader";
import CaseDetail from "./components/CaseDetail";
import CaseList from "./components/CaseList";
import StatsStrip from "./components/StatsStrip";
import UploadZone from "./components/UploadZone";
import { health } from "./api";
import useAnalysis from "./hooks/useAnalysis";
import { buildTheme } from "./theme";

export default function App() {
  const [mode, setMode] = useState(
    () => window.localStorage?.getItem("fraud-agent-mode") ?? "light"
  );
  const [model, setModel] = useState(null);
  const theme = useMemo(() => buildTheme(mode), [mode]);
  const a = useAnalysis();

  useEffect(() => {
    window.localStorage?.setItem("fraud-agent-mode", mode);
  }, [mode]);

  // Tells the narrative panel which model to name. Never blocks the UI.
  useEffect(() => {
    health()
      .then((h) => setModel(h.model))
      .catch(() => setModel(null));
  }, []);

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <AppHeader
        mode={mode}
        onToggleMode={() => setMode((m) => (m === "dark" ? "light" : "dark"))}
        onRunDemo={a.runDemo}
        loading={a.isLoading}
      />

      <Container maxWidth="xl" sx={{ py: 4 }}>
        {a.status === "offline" && (
          <Alert severity="info" sx={{ mb: 3 }} onClose={a.reset}>
            Showing a precomputed analysis — the API did not respond
            {a.error ? ` (${a.error})` : ""}. Everything below is real output from
            this engine, generated ahead of time.
          </Alert>
        )}

        {a.status === "error" && (
          <Alert
            severity="error"
            sx={{ mb: 3 }}
            action={
              <Button size="small" onClick={a.reset}>
                Dismiss
              </Button>
            }
          >
            {a.error}
          </Alert>
        )}

        {a.status === "idle" && (
          <Box sx={{ mb: 3 }}>
            <Typography variant="h5" gutterBottom>
              Detect fraud rings, and show your work
            </Typography>
            <Typography variant="body1" color="text.secondary" sx={{ maxWidth: 720, mb: 3 }}>
              Ten explainable rules score every transaction, a similarity graph groups
              the flagged ones into cases, and every score comes with the evidence
              behind it. Load the demo dataset or bring your own.
            </Typography>
            <Stack direction="row" spacing={2} flexWrap="wrap" useFlexGap>
              <Button variant="contained" size="large" onClick={a.runDemo}>
                Load demo dataset
              </Button>
            </Stack>
          </Box>
        )}

        {a.isLoading && (
          <Grid container spacing={2} sx={{ mb: 3 }}>
            {[0, 1, 2, 3].map((i) => (
              <Grid key={i} size={{ xs: 6, md: 3 }}>
                <Skeleton variant="rounded" height={104} />
              </Grid>
            ))}
          </Grid>
        )}

        <StatsStrip result={a.result} />

        {a.status === "empty" && (
          <Alert severity="success" sx={{ mb: 3 }}>
            No cases above the {a.result.threshold} risk threshold — this batch looks
            clean. {a.result.transactions_analyzed.toLocaleString()} transactions
            analyzed.
          </Alert>
        )}

        <Grid container spacing={3}>
          <Grid size={{ xs: 12, md: 4 }}>
            <Stack spacing={3}>
              <Card sx={{ height: "fit-content" }}>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    Cases
                  </Typography>
                  {a.isLoading ? (
                    <Stack spacing={1}>
                      {[0, 1, 2].map((i) => (
                        <Skeleton key={i} variant="rounded" height={64} />
                      ))}
                    </Stack>
                  ) : (
                    <CaseList
                      cases={a.cases}
                      selectedId={a.selectedCaseId}
                      onSelect={a.select}
                    />
                  )}
                </CardContent>
              </Card>

              <UploadZone onSubmit={a.runCustom} disabled={a.isLoading} />
            </Stack>
          </Grid>

          <Grid size={{ xs: 12, md: 8 }}>
            <Card>
              <CardContent>
                {a.isLoading ? (
                  <Stack spacing={1}>
                    <Skeleton height={36} width="35%" />
                    <Skeleton height={20} />
                    <Skeleton height={20} />
                    <Skeleton variant="rounded" height={260} />
                  </Stack>
                ) : (
                  <CaseDetail
                    selectedCase={a.selectedCase}
                    summary={a.summaries[a.selectedCaseId]}
                    summarizing={a.summarizing}
                    onGenerateSummary={a.generateSummary}
                    model={model}
                  />
                )}
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      </Container>
    </ThemeProvider>
  );
}
