import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import App from "./App.jsx";
import { HISTORY_KEY } from "./history.js";
import HistoryTable, { CLEAR_TEXT, HISTORY_HEADING, NO_CHECKS } from "./HistoryTable.jsx";
import { LABEL } from "./PasteLinkForm.jsx";

// A made-up link, only ever handled as text. Only its website name is saved.
const LINK = "https://parcel-redelivery.example/track?id=4821";
const SAVED = [{ checkedAt: "2026-11-18T21:40:00.000Z", link: "parcel-redelivery.example", result: "High risk" }];

function history() {
  return within(screen.getByRole("region", { name: HISTORY_HEADING }));
}

describe("no saved checks (done when 1 and 2)", () => {
  it("shows the message and draws no empty table", () => {
    render(<HistoryTable checks={[]} onClear={() => {}} />);

    expect(screen.getByText(NO_CHECKS)).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: CLEAR_TEXT })).not.toBeInTheDocument();
  });

  it("shows the message on a first visit, before any check", () => {
    render(<App />);

    expect(history().getByText(NO_CHECKS)).toBeInTheDocument();
    expect(history().queryByRole("table")).not.toBeInTheDocument();
  });

  it("swaps the message for the table after the first check", async () => {
    const user = userEvent.setup();
    render(<App check={async (url) => ({ url, risk_level: "Safe", score: 0.1, reasons: [], placeholder: false })} />);

    await user.type(screen.getByLabelText(LABEL), LINK);
    await user.click(screen.getByRole("button", { name: "Check" }));

    expect(await history().findByRole("table")).toBeInTheDocument();
    expect(history().queryByText(NO_CHECKS)).not.toBeInTheDocument();
  });

  it("shows the message again once the history is cleared, and after a reload", async () => {
    const user = userEvent.setup();
    window.localStorage.setItem(HISTORY_KEY, JSON.stringify(SAVED));
    const { unmount } = render(<App />);

    await user.click(history().getByRole("button", { name: CLEAR_TEXT }));
    expect(history().getByText(NO_CHECKS)).toBeInTheDocument();

    unmount();
    render(<App />);
    expect(history().getByText(NO_CHECKS)).toBeInTheDocument();
  });

  it("shows the message when storage holds nothing it can read", () => {
    window.localStorage.setItem(HISTORY_KEY, "not a list of checks");
    render(<App />);

    expect(history().getByText(NO_CHECKS)).toBeInTheDocument();
  });
});
