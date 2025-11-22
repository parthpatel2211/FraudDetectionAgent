import React from "react";
import { Chip } from "@mui/material";

export default function RiskBadge({ score }) {
  let label = "Low";
  let color = "success";

  if (score >= 0.8) {
    label = "Critical";
    color = "error";
  } else if (score >= 0.6) {
    label = "High";
    color = "warning";
  } else if (score >= 0.4) {
    label = "Medium";
    color = "info";
  }

  return (
    <Chip
      label={`${label} (${score.toFixed(2)})`}
      color={color}
      size="small"
      sx={{ fontWeight: "bold" }}
    />
  );
}
