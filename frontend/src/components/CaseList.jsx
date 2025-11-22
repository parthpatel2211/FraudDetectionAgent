import React from "react";
import {
  List,
  ListItemButton,
  ListItemText,
  Divider,
  Box,
  Typography
} from "@mui/material";
import RiskBadge from "./RiskBadge";

export default function CaseList({ cases, selectedId, onSelect }) {
  if (!cases.length) {
    return (
      <Typography variant="body2" sx={{ opacity: 0.7 }}>
        No cases detected.
      </Typography>
    );
  }

  return (
    <List sx={{ width: "100%" }}>
      {cases.map((c) => (
        <React.Fragment key={c.case_id}>
          <ListItemButton
            selected={c.case_id === selectedId}
            onClick={() => onSelect(c)}
            sx={{ borderRadius: 2 }}
          >
            <ListItemText
              primary={
                <Box display="flex" justifyContent="space-between">
                  <span>Case {c.case_id.slice(0, 8)}…</span>
                  <RiskBadge score={c.risk_score} />
                </Box>
              }
              secondary={
                <>
                  Customer <strong>{c.customer_id}</strong> — Account{" "}
                  <strong>{c.primary_account_id}</strong>
                </>
              }
            />
          </ListItemButton>
          <Divider />
        </React.Fragment>
      ))}
    </List>
  );
}
