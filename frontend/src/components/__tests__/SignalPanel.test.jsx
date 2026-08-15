import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import SignalPanel from "../SignalPanel";

const SIGNALS = [
  {
    rule: "shared_device_ring",
    label: "Shared device across customers",
    score: 1.0,
    weight: 0.85,
    contribution: 0.85,
    explanation: "Device DEV-SHARED-01 was used by 3 distinct customers.",
    tx_ids: ["TX-D000", "TX-D001"],
  },
  {
    rule: "off_hours",
    label: "Off-hours activity",
    score: 1.0,
    weight: 0.25,
    contribution: 0.25,
    explanation: "Transaction posted at 03:14 UTC.",
    tx_ids: ["TX-D000"],
  },
];

describe("SignalPanel", () => {
  it("renders every signal's explanation verbatim", () => {
    render(<SignalPanel signals={SIGNALS} />);
    for (const s of SIGNALS) {
      expect(screen.getByText(s.explanation)).toBeInTheDocument();
    }
  });

  it("shows each signal's contribution", () => {
    render(<SignalPanel signals={SIGNALS} />);
    expect(screen.getByText(/contributes 0\.85/)).toBeInTheDocument();
    expect(screen.getByText(/contributes 0\.25/)).toBeInTheDocument();
  });

  it("renders the evidence transaction chips", () => {
    render(<SignalPanel signals={SIGNALS} />);
    expect(screen.getAllByText("TX-D000")).toHaveLength(2);
    expect(screen.getByText("TX-D001")).toBeInTheDocument();
  });

  it("reports the clicked transaction id", async () => {
    const onSelect = vi.fn();
    render(<SignalPanel signals={SIGNALS} onSelectTransaction={onSelect} />);
    await userEvent.click(screen.getByText("TX-D001"));
    expect(onSelect).toHaveBeenCalledWith("TX-D001");
  });

  it("handles an empty signal list", () => {
    render(<SignalPanel signals={[]} />);
    expect(screen.getByText(/No signals recorded/i)).toBeInTheDocument();
  });

  it("handles a signal with no evidence ids", () => {
    render(<SignalPanel signals={[{ ...SIGNALS[0], tx_ids: [] }]} />);
    expect(screen.getByText(SIGNALS[0].explanation)).toBeInTheDocument();
  });
});
