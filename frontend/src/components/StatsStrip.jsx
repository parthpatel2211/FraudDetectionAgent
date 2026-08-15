import { Card, CardContent, Grid, Typography } from "@mui/material";

const currency = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0,
});

function Tile({ label, value, hint }) {
  return (
    <Grid size={{ xs: 6, md: 3 }}>
      <Card>
        <CardContent>
          <Typography variant="overline" color="text.secondary">
            {label}
          </Typography>
          <Typography variant="h5" sx={{ fontVariantNumeric: "tabular-nums" }}>
            {value}
          </Typography>
          {hint && (
            <Typography variant="caption" color="text.secondary">
              {hint}
            </Typography>
          )}
        </CardContent>
      </Card>
    </Grid>
  );
}

export default function StatsStrip({ result }) {
  if (!result) return null;

  const exposure = result.cases.reduce((sum, c) => sum + c.total_amount, 0);
  const flagRate = result.transactions_analyzed
    ? (result.transactions_flagged / result.transactions_analyzed) * 100
    : 0;

  return (
    <Grid container spacing={2} sx={{ mb: 3 }}>
      <Tile
        label="Analyzed"
        value={result.transactions_analyzed.toLocaleString()}
        hint="transactions"
      />
      <Tile
        label="Flagged"
        value={result.transactions_flagged.toLocaleString()}
        hint={`${flagRate.toFixed(1)}% at threshold ${result.threshold}`}
      />
      <Tile label="Cases" value={result.cases.length} hint="clustered rings" />
      <Tile label="Exposure" value={currency.format(exposure)} hint="total flagged value" />
    </Grid>
  );
}
