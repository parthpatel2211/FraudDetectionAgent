import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import RiskBadge from "../RiskBadge";

describe("RiskBadge", () => {
  it.each(["critical", "high", "medium", "low"])("renders %s", (severity) => {
    render(<RiskBadge severity={severity} score={0.5} />);
    expect(screen.getByText(new RegExp(severity, "i"))).toBeInTheDocument();
  });

  it("shows the score to two decimals", () => {
    render(<RiskBadge severity="high" score={0.7} />);
    expect(screen.getByText(/high · 0\.70/i)).toBeInTheDocument();
  });

  /**
   * 0.99945 rounded to two decimals reads as "1.00", i.e. certainty. Truncating
   * keeps two decimals without ever overstating the model's confidence.
   */
  it("never rounds a sub-1.0 score up to 1.00", () => {
    render(<RiskBadge severity="critical" score={0.99945} />);
    expect(screen.getByText(/critical · 0\.99/i)).toBeInTheDocument();
    expect(screen.queryByText(/1\.00/)).not.toBeInTheDocument();
  });

  it("renders without a score", () => {
    render(<RiskBadge severity="low" />);
    expect(screen.getByText("low")).toBeInTheDocument();
  });

  /** The backend owns the bands; the UI must not recompute and drift from it. */
  it("trusts the given severity even if it disagrees with the score", () => {
    render(<RiskBadge severity="low" score={0.99} />);
    expect(screen.getByText(/low · 0\.99/i)).toBeInTheDocument();
  });
});
