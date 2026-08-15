import DarkModeIcon from "@mui/icons-material/DarkMode";
import GitHubIcon from "@mui/icons-material/GitHub";
import LightModeIcon from "@mui/icons-material/LightMode";
import {
  AppBar,
  Box,
  Button,
  IconButton,
  Toolbar,
  Tooltip,
  Typography,
} from "@mui/material";

const REPO = "https://github.com/parthpatel2211/FraudDetectionAgent";

export default function AppHeader({ mode, onToggleMode, onRunDemo, loading }) {
  return (
    <AppBar position="sticky" color="default" elevation={0} sx={{ borderBottom: 1, borderColor: "divider" }}>
      <Toolbar sx={{ gap: 1 }}>
        <Typography variant="h6" sx={{ flexGrow: 1 }}>
          Fraud Investigation Platform
        </Typography>

        <Button variant="contained" onClick={onRunDemo} disabled={loading}>
          {loading ? "Analyzing…" : "Load demo dataset"}
        </Button>

        <Tooltip title={mode === "dark" ? "Switch to light" : "Switch to dark"}>
          <IconButton onClick={onToggleMode} aria-label="Toggle colour mode">
            {mode === "dark" ? <LightModeIcon /> : <DarkModeIcon />}
          </IconButton>
        </Tooltip>

        <Tooltip title="Source on GitHub">
          <IconButton component="a" href={REPO} target="_blank" rel="noreferrer" aria-label="GitHub">
            <GitHubIcon />
          </IconButton>
        </Tooltip>
      </Toolbar>
      <Box />
    </AppBar>
  );
}
