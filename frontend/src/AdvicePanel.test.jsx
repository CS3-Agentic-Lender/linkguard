import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import AdvicePanel, { ADVICE_HEADING } from "./AdvicePanel.jsx";
import { ALREADY_CLICKED, ALREADY_CLICKED_HEADING, EVERY_RESULT, HIGH_RISK_EXTRA, SUSPICIOUS } from "./advice.js";
import PasteLinkForm, { LABEL } from "./PasteLinkForm.jsx";
import { SAFE_CAVEAT } from "./ResultCard.jsx";

// The advice text file with its sources. Every line the panel shows must be in it.
const ADVICE_FILE = readFileSync(resolve(process.cwd(), "../docs/advice.md"), "utf8");

// A made-up link, only ever handled as text.
const LINK = "https://parcel-redelivery.example/track?id=4821";

function answer(risk_level) {
  return async () => ({ url: LINK, risk_level, score: 0.5, reasons: [], placeholder: false });
}

async function checkAs(risk_level) {
  const user = userEvent.setup();
  render(<PasteLinkForm check={answer(risk_level)} />);
  await user.type(screen.getByLabelText(LABEL), LINK);
  await user.click(screen.getByRole("button", { name: "Check" }));
  return screen.findByRole("region", { name: ADVICE_HEADING });
}

describe("advice after a scan (acceptance criterion 1)", () => {
  it("shows the Suspicious advice with a Suspicious result", async () => {
    const panel = await checkAs("Suspicious");

    for (const line of SUSPICIOUS) expect(within(panel).getByText(line)).toBeInTheDocument();
    for (const line of HIGH_RISK_EXTRA) expect(within(panel).queryByText(line)).not.toBeInTheDocument();
  });

  it("shows all the Suspicious advice plus reporting and blocking with a High risk result", async () => {
    const panel = await checkAs("High risk");

    for (const line of [...SUSPICIOUS, ...HIGH_RISK_EXTRA]) {
      expect(within(panel).getByText(line)).toBeInTheDocument();
    }
  });

  it("shows the every-result advice with Safe, and none of the risky-link advice", async () => {
    const panel = await checkAs("Safe");

    for (const line of EVERY_RESULT) expect(within(panel).getByText(line)).toBeInTheDocument();
    for (const line of SUSPICIOUS) expect(within(panel).queryByText(line)).not.toBeInTheDocument();
    // The Safe caveat stays on the card, unchanged.
    expect(screen.getByText(SAFE_CAVEAT)).toBeInTheDocument();
  });

  it.each(["Suspicious", "High risk"])("shows the every-result advice with %s too", async (level) => {
    const panel = await checkAs(level);

    for (const line of EVERY_RESULT) expect(within(panel).getByText(line)).toBeInTheDocument();
  });

  it.each([undefined, null, "Unknown", "placeholder"])("shows no advice for a failed or placeholder check (%s)", (level) => {
    const { container } = render(<AdvicePanel level={level} />);

    expect(container).toBeEmptyDOMElement();
  });

  it("keeps the advice out of the live region, so it is not read out with every result", async () => {
    const panel = await checkAs("High risk");

    expect(screen.getByRole("status")).not.toContainElement(panel);
  });

  it("keeps every advice sentence short", () => {
    const lines = [...EVERY_RESULT, ...SUSPICIOUS, ...HIGH_RISK_EXTRA, ...ALREADY_CLICKED.map(({ line }) => line)];
    for (const line of lines) {
      for (const sentence of line.split(/(?<=\.)\s+/)) {
        expect(sentence.split(/\s+/).length, sentence).toBeLessThanOrEqual(25);
      }
    }
  });
});

describe("if you already clicked (acceptance criterion 2)", () => {
  it.each(["Safe", "Suspicious", "High risk"])("shows the five steps with %s", async (level) => {
    const panel = await checkAs(level);
    const list = within(panel).getByRole("list", { name: ALREADY_CLICKED_HEADING });

    expect(within(panel).getByRole("heading", { name: ALREADY_CLICKED_HEADING })).toBeInTheDocument();
    expect(within(list).getAllByRole("listitem")).toHaveLength(5);
    const text = list.textContent;
    for (const step of [/bank/i, /password/i, /antivirus/i, /Garda/, /IT department/]) {
      expect(text).toMatch(step);
    }
  });
});

describe("every advice line has a source (acceptance criterion 3)", () => {
  const shown = [
    ...EVERY_RESULT,
    ...SUSPICIOUS,
    ...HIGH_RISK_EXTRA,
    ...ALREADY_CLICKED.flatMap(({ situation, line }) => [situation, line]),
  ];

  it.each(shown)("is in docs/advice.md word for word: %s", (line) => {
    expect(ADVICE_FILE).toContain(line);
  });

  it("copies the Safe caveat into the advice file word for word", () => {
    expect(ADVICE_FILE).toContain(SAFE_CAVEAT);
  });

  it.each(["safe", "suspicious", "high"])("never shows a UK-only reporting route (%s)", (level) => {
    render(<AdvicePanel level={level} />);

    expect(document.body.textContent).not.toMatch(/7726/);
    expect(document.body.textContent).not.toMatch(/phishing\.gov\.uk/i);
  });
});
