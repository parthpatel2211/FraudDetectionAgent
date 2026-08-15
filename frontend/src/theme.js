import { createTheme } from "@mui/material/styles";

/**
 * Severity colours live here and nowhere else. RiskBadge, StatsStrip and the
 * graph all read from this map, so a badge and its graph node can never
 * disagree about what "critical" looks like.
 *
 * Keys match the backend's severity bands exactly (see engine/scoring.py).
 */
export const SEVERITY_COLORS = {
  critical: { light: "#b3261e", dark: "#f2b8b5" },
  high: { light: "#b45309", dark: "#fcd34d" },
  medium: { light: "#1e6091", dark: "#7dd3fc" },
  low: { light: "#2e7d32", dark: "#86efac" },
};

export const SEVERITY_ORDER = ["critical", "high", "medium", "low"];

/** MUI Chip colours, used where a full palette entry is expected. */
export const SEVERITY_CHIP_COLOR = {
  critical: "error",
  high: "warning",
  medium: "info",
  low: "success",
};

export function severityColor(severity, mode) {
  return (SEVERITY_COLORS[severity] ?? SEVERITY_COLORS.low)[mode] ?? "#888";
}

export function buildTheme(mode) {
  const isDark = mode === "dark";
  return createTheme({
    palette: {
      mode,
      primary: { main: isDark ? "#7dd3fc" : "#0b5394" },
      secondary: { main: isDark ? "#c4b5fd" : "#5b21b6" },
      background: {
        default: isDark ? "#0f1419" : "#f5f7fa",
        paper: isDark ? "#161b22" : "#ffffff",
      },
    },
    shape: { borderRadius: 10 },
    typography: {
      fontFamily: '"Inter", "Segoe UI", system-ui, sans-serif',
      h6: { fontWeight: 600 },
      // Identifiers are compared by eye constantly in this UI, so give them a
      // monospace face wherever they appear.
      body2: { fontVariantNumeric: "tabular-nums" },
    },
    components: {
      MuiCard: { defaultProps: { elevation: 0 }, styleOverrides: {
        root: { border: `1px solid ${isDark ? "#30363d" : "#e2e8f0"}` },
      } },
      MuiTableCell: { styleOverrides: { root: { fontVariantNumeric: "tabular-nums" } } },
    },
  });
}

export default buildTheme("light");
