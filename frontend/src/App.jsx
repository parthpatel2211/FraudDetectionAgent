import { CssBaseline, Container, Typography } from "@mui/material";
import { ThemeProvider } from "@mui/material/styles";

import theme from "./theme";

export default function App() {
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Container maxWidth="xl" sx={{ mt: 4 }}>
        <Typography variant="h5">Fraud Investigation Platform</Typography>
      </Container>
    </ThemeProvider>
  );
}
