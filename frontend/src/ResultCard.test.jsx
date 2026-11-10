import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import ResultCard, { MAX_REASONS, NO_SINGLE_REASON, REASONS_HEADING, SAFE_CAVEAT } from "./ResultCard.jsx";
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

// Made-up reasons, standing in for the ones /scan will send.
const REASONS = [
  "This link uses a string of numbers instead of a website name.",
  "The website name in this link is unusually long.",
  "The website name has a lot of dots or hyphens.",
];

function reasonItems() {
  return screen.getAllByRole("listitem").map((item) => item.textContent);
}

describe("reasons on the result card", () => {
  it.each(["Suspicious", "High risk"])("shows three reasons with %s, in the order the reply gives them", (word) => {
    render(<ResultCard reply={reply({ risk_level: word, reasons: REASONS })} />);

    expect(screen.getByRole("list", { name: REASONS_HEADING })).toBeInTheDocument();
    expect(reasonItems()).toEqual(REASONS);
  });

  it("names the reasons with a heading one level below the risk level, so screen readers can jump to it", () => {
    render(<ResultCard reply={reply({ risk_level: "High risk", reasons: REASONS })} />);

    expect(screen.getByRole("heading", { level: 2, name: "High risk" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 3, name: REASONS_HEADING })).toBeInTheDocument();
  });

  it("shows a single reason", () => {
    render(<ResultCard reply={reply({ risk_level: "Suspicious", reasons: [REASONS[1]] })} />);

    expect(reasonItems()).toEqual([REASONS[1]]);
  });

  // PO decision, 9 Nov: a risky link with no reasons shows a general sentence, because a blank space looks broken.
  it.each([
    ["Suspicious", []],
    ["High risk", []],
    ["High risk", undefined],
    ["High risk", null],
    ["High risk", "not a list"],
    ["High risk", ["", "   ", 42]],
  ])("shows the general sentence under the heading with %s when the reasons are %j", (word, reasons) => {
    render(<ResultCard reply={reply({ risk_level: word, reasons })} />);

    expect(screen.getByRole("heading", { level: 3, name: REASONS_HEADING })).toBeInTheDocument();
    expect(screen.getByText(NO_SINGLE_REASON)).toBeInTheDocument();
    expect(screen.queryByRole("list")).not.toBeInTheDocument();
  });

  it("does not show the general sentence when there are reasons", () => {
    render(<ResultCard reply={reply({ risk_level: "High risk", reasons: REASONS })} />);

    expect(screen.queryByText(NO_SINGLE_REASON)).not.toBeInTheDocument();
  });

  it.each([
    ["Safe", { risk_level: "Safe" }],
    ["the placeholder", { placeholder: true }],
    ["the failure message", { risk_level: "Unknown" }],
  ])("never shows the general sentence with %s", (_, fields) => {
    render(<ResultCard reply={reply(fields)} />);

    expect(screen.queryByText(NO_SINGLE_REASON)).not.toBeInTheDocument();
    expect(screen.queryByText(REASONS_HEADING)).not.toBeInTheDocument();
  });

  it("never shows reasons with Safe, even if the reply has some", () => {
    render(<ResultCard reply={reply({ risk_level: "Safe", reasons: REASONS })} />);

    expect(screen.queryByRole("list")).not.toBeInTheDocument();
    expect(screen.queryByText(REASONS[0])).not.toBeInTheDocument();
  });

  it("never shows reasons with the placeholder message", () => {
    render(<ResultCard reply={reply({ placeholder: true, reasons: REASONS })} />);

    expect(screen.queryByRole("list")).not.toBeInTheDocument();
  });

  it("shows at most three reasons, the first three", () => {
    const four = [...REASONS, "The website name contains a lot of numbers."];

    render(<ResultCard reply={reply({ risk_level: "High risk", reasons: four })} />);

    expect(MAX_REASONS).toBe(3);
    expect(reasonItems()).toEqual(REASONS);
  });

  it("skips anything in the list that is not a sentence", () => {
    const messy = [REASONS[0], "", "   ", 42, null, { text: "x" }, REASONS[1]];

    render(<ResultCard reply={reply({ risk_level: "Suspicious", reasons: messy })} />);

    expect(reasonItems()).toEqual([REASONS[0], REASONS[1]]);
  });

  it("shows two identical reasons as two items", () => {
    render(<ResultCard reply={reply({ risk_level: "Suspicious", reasons: [REASONS[0], REASONS[0]] })} />);

    expect(reasonItems()).toEqual([REASONS[0], REASONS[0]]);
  });

  it("puts the reasons straight under the risk level, before the checked link", () => {
    const { container } = render(<ResultCard reply={reply({ risk_level: "Suspicious", reasons: REASONS })} />);
    const order = [...container.firstElementChild.children].map((child) => child.className);

    expect(order).toEqual(["result-card__level", "result-card__reasons", "result-card__link"]);
  });

  it("shows reasons as plain text, never as links", () => {
    const withAddress = ["See https://evil.example for more."];
    const { container } = render(<ResultCard reply={reply({ risk_level: "High risk", reasons: withAddress })} />);

    expect(reasonItems()).toEqual(withAddress);
    expect(container.querySelector("a, [href]")).toBeNull();
  });
});
