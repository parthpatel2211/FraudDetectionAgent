import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import App from "../App";

describe("toolchain", () => {
  it("renders the app without crashing", () => {
    render(<App />);
    expect(screen.getByText(/Fraud Investigation Platform/i)).toBeInTheDocument();
  });
});
