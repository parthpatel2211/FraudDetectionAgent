import { Chip } from "@mui/material";

import { SEVERITY_CHIP_COLOR } from "../theme";

/**
 * Reads `severity` from the case rather than recomputing it from the score.
 *
 * v1 recomputed the bands here in the frontend, so the UI and the engine could
 * drift apart silently. The backend already decided; this just renders it.
 */
export default function RiskBadge({ severity, score, size = "small" }) {
  // Truncate rather than round: 0.99945 shown as "1.00" reads as certainty the
  // model does not have. Flooring keeps two decimals without ever overstating.
  const label =
    typeof score === "number"
      ? `${severity} · ${(Math.floor(score * 100) / 100).toFixed(2)}`
      : severity;

  return (
    <Chip
      label={label}
      color={SEVERITY_CHIP_COLOR[severity] ?? "default"}
      size={size}
      sx={{ fontWeight: 600, textTransform: "capitalize" }}
    />
  );
}
