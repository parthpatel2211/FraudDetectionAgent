import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { Box, Button, Chip, Stack, Typography } from "@mui/material";
import { useTheme } from "@mui/material/styles";
import ForceGraph2D from "react-force-graph-2d";

import { severityColor } from "../theme";

/**
 * The fraud ring, drawn.
 *
 * The backend has always built this graph; v1 never rendered it. Transactions
 * are tinted by their own risk and sized by amount; entity nodes show what
 * binds them. Solid links are similarity edges that actually cleared the
 * backend's 0.60 threshold; dashed links are the weaker
 * transaction-to-entity relationships.
 */

const ENTITY_COLORS = {
  customer: { light: "#5b21b6", dark: "#c4b5fd" },
  account: { light: "#0f766e", dark: "#5eead4" },
  device: { light: "#b45309", dark: "#fcd34d" },
  ip: { light: "#9d174d", dark: "#f9a8d4" },
  merchant: { light: "#475569", dark: "#94a3b8" },
};

const LINK_THRESHOLD = 0.6;
const RENDER_WARN_NODES = 400;

export default function GraphView({ graph, onSelectTransaction }) {
  const theme = useTheme();
  const mode = theme.palette.mode;
  const containerRef = useRef(null);
  const fgRef = useRef(null);
  const [size, setSize] = useState({ width: 0, height: 460 });
  const [forceRender, setForceRender] = useState(false);

  // Measure synchronously before paint. ResizeObserver's *initial* observation
  // is not delivered in every environment - in at least one embedded browser it
  // never fires at all - and gating the canvas on it left the graph
  // permanently blank. clientWidth is always available once mounted.
  useLayoutEffect(() => {
    const el = containerRef.current;
    if (el && el.clientWidth > 0) {
      setSize((s) => (s.width === el.clientWidth ? s : { ...s, width: el.clientWidth }));
    }
  });

  // ResizeObserver handles container-only resizes (sidebar collapse, layout
  // shift) that no window event would report.
  useEffect(() => {
    const el = containerRef.current;
    if (!el || typeof ResizeObserver === "undefined") return undefined;
    const ro = new ResizeObserver(([entry]) => {
      const width = entry.contentRect.width;
      setSize((s) => (s.width === width ? s : { ...s, width }));
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // Window resize as the backstop. Where ResizeObserver does not fire, this is
  // what keeps the canvas from staying stuck at its first measured width.
  useEffect(() => {
    const onResize = () => {
      const el = containerRef.current;
      if (el) setSize((s) => (s.width === el.clientWidth ? s : { ...s, width: el.clientWidth }));
    };
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  // react-force-graph mutates the objects it is given, so hand it copies.
  const data = useMemo(() => {
    if (!graph) return { nodes: [], links: [] };
    return {
      nodes: graph.nodes.map((n) => ({ ...n })),
      links: graph.edges.map((e) => ({ ...e })),
    };
  }, [graph]);

  const nodeColor = useCallback(
    (n) =>
      n.kind === "transaction"
        ? severityColor(severityOf(n.risk), mode)
        : (ENTITY_COLORS[n.kind] ?? ENTITY_COLORS.merchant)[mode],
    [mode]
  );

  const drawNode = useCallback(
    (node, ctx, globalScale) => {
      const r =
        node.kind === "transaction"
          ? Math.max(3, Math.min(11, Math.sqrt(node.amount ?? 1) / 4))
          : 5;

      ctx.beginPath();
      ctx.arc(node.x, node.y, r, 0, 2 * Math.PI);
      ctx.fillStyle = nodeColor(node);
      ctx.fill();

      if (node.kind !== "transaction") {
        ctx.strokeStyle = mode === "dark" ? "#0f1419" : "#ffffff";
        ctx.lineWidth = 1.5;
        ctx.stroke();
      }

      if (globalScale > 1.4) {
        const label = node.kind === "transaction" ? node.label : `${node.kind}: ${node.label}`;
        ctx.font = `${10 / globalScale}px monospace`;
        ctx.fillStyle = theme.palette.text.secondary;
        ctx.textAlign = "center";
        ctx.fillText(label, node.x, node.y + r + 9 / globalScale);
      }
    },
    [nodeColor, mode, theme.palette.text.secondary]
  );

  if (!graph || !data.nodes.length) {
    return (
      <Typography variant="body2" color="text.secondary">
        No graph for this case.
      </Typography>
    );
  }

  if (data.nodes.length > RENDER_WARN_NODES && !forceRender) {
    return (
      <Stack spacing={2} alignItems="flex-start">
        <Typography variant="body2" color="text.secondary">
          This case has {data.nodes.length} nodes. Rendering it may be slow.
        </Typography>
        <Button variant="outlined" onClick={() => setForceRender(true)}>
          Render anyway
        </Button>
      </Stack>
    );
  }

  return (
    <Box>
      <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap sx={{ mb: 1.5 }}>
        <Chip size="small" label="transaction (tinted by risk)" variant="outlined" />
        {Object.keys(ENTITY_COLORS).map((kind) => (
          <Chip
            key={kind}
            size="small"
            label={kind}
            variant="outlined"
            sx={{ borderColor: ENTITY_COLORS[kind][mode], color: ENTITY_COLORS[kind][mode] }}
          />
        ))}
      </Stack>

      <Box
        ref={containerRef}
        sx={{
          border: 1,
          borderColor: "divider",
          borderRadius: 2,
          overflow: "hidden",
          height: size.height,
        }}
      >
        {size.width > 0 && (
          <ForceGraph2D
            ref={fgRef}
            width={size.width}
            height={size.height}
            graphData={data}
            backgroundColor={theme.palette.background.paper}
            nodeCanvasObject={drawNode}
            nodePointerAreaPaint={(node, color, ctx) => {
              ctx.fillStyle = color;
              ctx.beginPath();
              ctx.arc(node.x, node.y, 8, 0, 2 * Math.PI);
              ctx.fill();
            }}
            nodeLabel={(n) =>
              n.kind === "transaction"
                ? `${n.label} — risk ${n.risk.toFixed(2)}, ${n.amount?.toFixed(2)} USD`
                : `${n.kind}: ${n.label}`
            }
            linkLabel={(l) => (l.reasons?.length ? l.reasons.join(", ") : "")}
            linkColor={() => (mode === "dark" ? "#3f4854" : "#cbd5e1")}
            linkWidth={(l) => (l.weight >= LINK_THRESHOLD ? 1 + l.weight * 2 : 0.6)}
            linkLineDash={(l) => (l.weight >= LINK_THRESHOLD ? null : [3, 3])}
            cooldownTicks={90}
            onNodeClick={(n) => n.kind === "transaction" && onSelectTransaction?.(n.id)}
          />
        )}
      </Box>

      <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: "block" }}>
        Solid links share enough attributes to cross the {LINK_THRESHOLD} similarity
        threshold. Hover a link to see why. Click a transaction to highlight it in the
        table.
      </Typography>
    </Box>
  );
}

function severityOf(risk) {
  if (risk >= 0.85) return "critical";
  if (risk >= 0.65) return "high";
  if (risk >= 0.4) return "medium";
  return "low";
}
