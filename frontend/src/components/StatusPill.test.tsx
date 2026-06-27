import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { StatusPill } from "./StatusPill";

describe("StatusPill", () => {
  it.each(["Pending", "Provisioning", "Running", "Stopping", "Error"] as const)(
    "renders the %s label",
    (phase) => {
      render(<StatusPill phase={phase} />);
      expect(screen.getByText(phase)).toBeInTheDocument();
    }
  );

  it("pulses the dot for in-progress phases but not for Running", () => {
    const { container: prov } = render(<StatusPill phase="Provisioning" />);
    expect(prov.querySelector(".dot-pulse")).not.toBeNull();

    const { container: run } = render(<StatusPill phase="Running" />);
    expect(run.querySelector(".dot-pulse")).toBeNull();
  });
});
