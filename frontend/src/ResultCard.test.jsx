import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import ResultCard, { SAFE_CAVEAT } from "./ResultCard.jsx";
import { CANT_CHECK, PLACEHOLDER } from "./scan.js";

// A made-up link, only ever handled as text.
const LINK = "https://parcel-redelivery.example/track?id=4821";

function reply(fields) {
  return { url: LINK, risk_level: null, score: null, reasons: [], placeholder: false, ...fields };
}

const LEVELS = [
  ["Safe", "safe", "shield-check"],
  ["Suspicious", "suspicious", "triangle-alert"],
  ["High risk", "high", "octagon-alert"],
];

describe("result card", () => {
  it.each(LEVELS)("shows %s with its own word, icon and colour", (word, level, icon) => {
    const { container } = render(<ResultCard reply={reply({ risk_level: word })} />);
    const card = container.firstElementChild;

    expect(screen.getByRole("heading", { name: word })).toBeInTheDocument();
    expect(card).toHaveAttribute("data-level", level);
    expect(card.querySelector(`svg[data-icon="${icon}"]`)).toHaveAttribute("aria-hidden", "true");
  });

  it("gives each level a different icon, so they can be told apart without colour", () => {
    const icons = LEVELS.map(([word]) => {
      const { container, unmount } = render(<ResultCard reply={reply({ risk_level: word })} />);
      const svg = container.querySelector("svg").outerHTML;
      unmount();
      return svg;
    });

    expect(new Set(icons).size).toBe(3);
  });

  it("always shows the caveat with Safe, word for word", () => {
    render(<ResultCard reply={reply({ risk_level: "Safe" })} />);

    expect(SAFE_CAVEAT).toBe(
      "No warning signs found. Still don't enter passwords or bank details from a message you weren't expecting.",
    );
    expect(screen.getByText(SAFE_CAVEAT)).toBeInTheDocument();
  });

  it.each(["Suspicious", "High risk"])("does not show the Safe caveat with %s", (word) => {
    render(<ResultCard reply={reply({ risk_level: word })} />);

    expect(screen.queryByText(SAFE_CAVEAT)).not.toBeInTheDocument();
  });

  it.each(LEVELS)("shows the checked link with %s as plain text that cannot be clicked", (word) => {
    const { container } = render(<ResultCard reply={reply({ risk_level: word })} />);

    expect(screen.getByText(LINK)).toBeInTheDocument();
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
    expect(container.querySelector("a, [href]")).toBeNull();
  });

  it("shows the placeholder message, with no level and no failure message, when the placeholder flag is set", () => {
    const { container } = render(<ResultCard reply={reply({ placeholder: true })} />);

    expect(screen.getByText(PLACEHOLDER)).toBeInTheDocument();
    expect(container.firstElementChild).toHaveAttribute("data-level", "placeholder");
    for (const [word] of LEVELS) {
      expect(screen.queryByText(word)).not.toBeInTheDocument();
    }
    expect(screen.queryByText(CANT_CHECK)).not.toBeInTheDocument();
  });

  it.each([["Unknown"], ["safe"], [""], [null], [undefined]])(
    "shows the failure message word for word for a level of %j",
    (level) => {
      const { container } = render(<ResultCard reply={reply({ risk_level: level })} />);

      expect(screen.getByText(CANT_CHECK)).toBeInTheDocument();
      expect(container.firstElementChild).toHaveAttribute("data-level", "error");
      for (const [word] of LEVELS) {
        expect(screen.queryByText(word)).not.toBeInTheDocument();
      }
    },
  );

  it("shows the failure message when there is no reply at all", () => {
    render(<ResultCard reply={null} />);

    expect(screen.getByText(CANT_CHECK)).toBeInTheDocument();
  });
});
