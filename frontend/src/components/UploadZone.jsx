import { useRef, useState } from "react";
import {
  Alert,
  AlertTitle,
  Box,
  Button,
  Card,
  CardContent,
  Stack,
  Typography,
} from "@mui/material";

import { parseTransactionFile } from "../lib/parseTransactions";

/**
 * Drag-and-drop JSON/CSV upload.
 *
 * Validates client-side and reports row-level problems before anything is
 * sent. Posting a batch we already know is bad, just to render the 400, wastes
 * a round trip and gives a worse error than we can produce here.
 */
export default function UploadZone({ onSubmit, disabled }) {
  const inputRef = useRef(null);
  const [dragging, setDragging] = useState(false);
  const [errors, setErrors] = useState([]);
  const [notice, setNotice] = useState(null);

  const handleFile = async (file) => {
    if (!file) return;
    setErrors([]);
    setNotice(null);
    try {
      const { transactions, errors: rowErrors } = parseTransactionFile(
        await file.text(),
        file.name
      );
      if (rowErrors.length) {
        setErrors(rowErrors);
        return;
      }
      setNotice(`${transactions.length} transactions from ${file.name}`);
      onSubmit(transactions);
    } catch (e) {
      setErrors([{ row: null, message: e.message }]);
    }
  };

  return (
    <Card>
      <CardContent>
        <Typography variant="h6" gutterBottom>
          Analyze your own data
        </Typography>

        <Box
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragging(false);
            handleFile(e.dataTransfer.files?.[0]);
          }}
          onClick={() => inputRef.current?.click()}
          sx={{
            border: 2,
            borderStyle: "dashed",
            borderColor: dragging ? "primary.main" : "divider",
            bgcolor: dragging ? "action.hover" : "transparent",
            borderRadius: 2,
            p: 3,
            textAlign: "center",
            cursor: disabled ? "not-allowed" : "pointer",
            opacity: disabled ? 0.6 : 1,
            transition: "border-color 120ms, background-color 120ms",
          }}
        >
          <Typography variant="body2" color="text.secondary">
            Drop a <strong>.json</strong> or <strong>.csv</strong> file here, or click to
            choose one.
          </Typography>
          <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 1 }}>
            Required columns: id, customer_id, account_id, merchant_id, amount, timestamp
          </Typography>
          <input
            ref={inputRef}
            type="file"
            accept=".json,.csv,application/json,text/csv"
            hidden
            disabled={disabled}
            onChange={(e) => {
              handleFile(e.target.files?.[0]);
              e.target.value = "";
            }}
          />
        </Box>

        {notice && (
          <Alert severity="success" sx={{ mt: 2 }}>
            {notice}
          </Alert>
        )}

        {errors.length > 0 && (
          <Alert severity="error" sx={{ mt: 2 }}>
            <AlertTitle>
              {errors.length} problem{errors.length > 1 ? "s" : ""} in this file
            </AlertTitle>
            <Stack component="ul" sx={{ pl: 2, m: 0 }} spacing={0.25}>
              {errors.slice(0, 8).map((e, i) => (
                <Typography key={i} component="li" variant="caption">
                  {e.row != null ? `Row ${e.row}: ` : ""}
                  {e.message}
                </Typography>
              ))}
            </Stack>
            {errors.length > 8 && (
              <Typography variant="caption">…and {errors.length - 8} more.</Typography>
            )}
            <Button size="small" sx={{ mt: 1 }} onClick={() => setErrors([])}>
              Dismiss
            </Button>
          </Alert>
        )}
      </CardContent>
    </Card>
  );
}
