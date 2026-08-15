import {
  Box,
  Divider,
  List,
  ListItemButton,
  ListItemText,
  Typography,
} from "@mui/material";

import RiskBadge from "./RiskBadge";

const currency = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0,
});

export default function CaseList({ cases, selectedId, onSelect }) {
  if (!cases.length) {
    return (
      <Typography variant="body2" color="text.secondary">
        No cases.
      </Typography>
    );
  }

  return (
    <List disablePadding sx={{ width: "100%" }}>
      {cases.map((c, i) => (
        <Box key={c.case_id}>
          {i > 0 && <Divider component="li" />}
          <ListItemButton
            selected={c.case_id === selectedId}
            onClick={() => onSelect(c.case_id)}
            sx={{ borderRadius: 2, py: 1.5 }}
          >
            <ListItemText
              disableTypography
              primary={
                <Box display="flex" justifyContent="space-between" alignItems="center" gap={1}>
                  <Typography variant="subtitle2" sx={{ fontFamily: "monospace" }}>
                    {c.case_id}
                  </Typography>
                  <RiskBadge severity={c.severity} score={c.risk_score} />
                </Box>
              }
              secondary={
                <Typography variant="caption" color="text.secondary" component="div" sx={{ mt: 0.5 }}>
                  {c.transactions.length} transactions ·{" "}
                  {currency.format(c.total_amount)} ·{" "}
                  {c.customer_ids.length === 1
                    ? c.customer_ids[0]
                    : `${c.customer_ids.length} customers`}
                </Typography>
              }
            />
          </ListItemButton>
        </Box>
      ))}
    </List>
  );
}
