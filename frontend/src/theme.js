import { createTheme } from "@mui/material/styles";

const theme = createTheme({
  palette: {
    mode: "light",
    primary: {
      main: "#1E88E5"
    },
    secondary: {
      main: "#1565C0"
    },
    background: {
      default: "#F5F7FA"
    }
  },
  shape: {
    borderRadius: 10
  }
});

export default theme;
