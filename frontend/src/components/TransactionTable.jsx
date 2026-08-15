import { useEffect, useRef } from "react";
import {
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
} from "@mui/material";

const currency = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
});

export default function TransactionTable({ transactions, highlightedId }) {
  const rowRefs = useRef({});

  // Scroll the cited transaction into view when a signal chip is clicked.
  useEffect(() => {
    if (highlightedId && rowRefs.current[highlightedId]) {
      rowRefs.current[highlightedId].scrollIntoView({
        behavior: "smooth",
        block: "center",
      });
    }
  }, [highlightedId]);

  return (
    <TableContainer component={Paper} variant="outlined" sx={{ maxHeight: 420 }}>
      <Table size="small" stickyHeader>
        <TableHead>
          <TableRow>
            {["ID", "Time (UTC)", "Amount", "Merchant", "Channel", "Country", "Device", "IP"].map(
              (h) => (
                <TableCell key={h}>{h}</TableCell>
              )
            )}
          </TableRow>
        </TableHead>
        <TableBody>
          {transactions.map((t) => (
            <TableRow
              key={t.id}
              ref={(el) => {
                rowRefs.current[t.id] = el;
              }}
              selected={t.id === highlightedId}
              hover
            >
              <TableCell sx={{ fontFamily: "monospace", fontSize: 11 }}>{t.id}</TableCell>
              <TableCell>
                {new Date(t.timestamp).toISOString().replace("T", " ").slice(0, 16)}
              </TableCell>
              <TableCell align="right">{currency.format(t.amount)}</TableCell>
              <TableCell>{t.merchant_id}</TableCell>
              <TableCell>{t.channel}</TableCell>
              <TableCell>{t.country || "—"}</TableCell>
              <TableCell sx={{ fontFamily: "monospace", fontSize: 11 }}>
                {t.device_id || "—"}
              </TableCell>
              <TableCell sx={{ fontFamily: "monospace", fontSize: 11 }}>
                {t.ip_address || "—"}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );
}
