import React, { useState } from "react";
import { ThemeProvider } from "@mui/material/styles";
import {
  AppBar,
  Toolbar,
  Typography,
  CssBaseline,
  Box,
  Container,
  Button,
  Grid,
  Card,
  CardContent
} from "@mui/material";

import theme from "./theme";
import { sampleTransactions } from "./sampleData";
import { analyzeTransactions } from "./api";
import CaseList from "./components/CaseList";
import CaseDetail from "./components/CaseDetail";

export default function App() {
  const [cases, setCases] = useState([]);
  const [selectedCase, setSelectedCase] = useState(null);
  const [loading, setLoading] = useState(false);

  const runSample = async () => {
    setLoading(true);
    const detected = await analyzeTransactions(sampleTransactions);
    setCases(detected);
    setSelectedCase(detected[0]);
    setLoading(false);
  };

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />

      {/* TOP NAV */}
      <AppBar position="sticky" elevation={0}>
        <Toolbar>
          <Typography variant="h6" sx={{ flexGrow: 1 }}>
            Fraud Investigation Platform
          </Typography>

          <Button
            color="inherit"
            variant="outlined"
            onClick={runSample}
            disabled={loading}
          >
            {loading ? "Analyzing..." : "Load Sample Data"}
          </Button>
        </Toolbar>
      </AppBar>

      {/* MAIN CONTENT */}
      <Container maxWidth="xl" sx={{ mt: 4 }}>
        <Grid container spacing={3}>
          {/* CASE LIST */}
          <Grid item xs={12} md={4}>
            <Card elevation={1} sx={{ height: "100%" }}>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Fraud Cases
                </Typography>
                <CaseList
                  cases={cases}
                  selectedId={selectedCase?.case_id}
                  onSelect={(c) => setSelectedCase(c)}
                />
              </CardContent>
            </Card>
          </Grid>

          {/* CASE DETAIL */}
          <Grid item xs={12} md={8}>
            <Card elevation={1}>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Case Details
                </Typography>
                <CaseDetail selectedCase={selectedCase} />
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      </Container>
    </ThemeProvider>
  );
}
