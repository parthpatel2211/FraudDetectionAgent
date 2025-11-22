import React from "react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Paper,
  TableContainer
} from "@mui/material";

export default function TransactionTable({ transactions }) {
  return (
    <TableContainer component={Paper} elevation={0} sx={{ my: 1 }}>
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell>Time</TableCell>
            <TableCell>Amount</TableCell>
            <TableCell>Merchant</TableCell>
            <TableCell>Channel</TableCell>
            <TableCell>Country</TableCell>
            <TableCell>Device</TableCell>
            <TableCell>IP</TableCell>
          </TableRow>
        </TableHead>

        <TableBody>
          {transactions.map((t) => (
            <TableRow key={t.id}>
              <TableCell>{new Date(t.timestamp).toLocaleString()}</TableCell>
              <TableCell>{t.amount} {t.currency}</TableCell>
              <TableCell>{t.merchant_id}</TableCell>
              <TableCell>{t.channel}</TableCell>
              <TableCell>{t.country || "—"}</TableCell>
              <TableCell>{t.device_id || "—"}</TableCell>
              <TableCell>{t.ip_address || "—"}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );
}
