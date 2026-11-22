import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import App from "./App.jsx";
import { HISTORY_KEY, loadHistory } from "./history.js";
import HistoryTable, { CLEAR_TEXT, COLUMNS, HISTORY_HEADING, irishTime } from "./HistoryTable.jsx";
import { LABEL } from "./PasteLinkForm.jsx";

// Made-up website names, only ever handled as text. Only the website name of a
// link is saved (see history.js), so that is all the table ever shows.
const SAMPLE = [
  { checkedAt: "2026-11-18T21:40:00.000Z", link: "parcel-redelivery.example", result: "High risk" },
  { checkedAt: "2026-11-18T09:07:00.000Z", link: "bank-login.example", result: "Suspicious" },
  { checkedAt: "2026-10-08T13:05:00.000Z", link: "www.example.org", result: "Safe" },
];

// The history's own rows, leaving out its column headings and the charts' tables.
function rows() {
  const table = within(screen.getByRole("region", { name: HISTORY_HEADING })).queryByRole("table");
  return table ? within(table).getAllByRole("row").slice(1) : [];
}

describe("the history table (done when 1: newest first, three columns)", () => {
  it("has the three columns from the story", () => {
    render(<HistoryTable checks={SAMPLE} onClear={() => {}} />);

    expect(screen.getAllByRole("columnheader").map((cell) => cell.textContent)).toEqual(COLUMNS);
  });

  it("shows the date and time, link and result of each check in the order given, newest first", () => {
    render(<HistoryTable checks={SAMPLE} onClear={() => {}} />);

    expect(rows().map((row) => within(row).getAllByRole("cell").map((cell) => cell.textContent))).toEqual([
      ["18 Nov 2026, 21:40", SAMPLE[0].link, "High risk"],
      ["18 Nov 2026, 09:07", SAMPLE[1].link, "Suspicious"],
      ["8 Oct 2026, 14:05", SAMPLE[2].link, "Safe"],
    ]);
  });

  it("uses Irish local time, including summer time", () => {
    // 13:05 UTC on 8 Oct is 14:05 in Ireland, and 09:07 UTC in November is 09:07.
    expect(irishTime("2026-10-08T13:05:00.000Z")).toBe("8 Oct 2026, 14:05");
    expect(irishTime("2026-11-18T09:07:00.000Z")).toBe("18 Nov 2026, 09:07");
  });

  it("puts three checks made one after another newest first on the page", async () => {
    const user = userEvent.setup();
    const links = ["https://first.example/", "https://second.example/", "https://third.example/"];
    render(<App check={async (url) => ({ url, risk_level: "Suspicious", score: 0.4, reasons: [], placeholder: false })} />);

    for (const link of links) {
      await user.clear(screen.getByLabelText(LABEL));
      await user.type(screen.getByLabelText(LABEL), link);
      await user.click(screen.getByRole("button", { name: "Check" }));
      await screen.findByRole("cell", { name: new URL(link).hostname });
    }

    const history = screen.getByRole("region", { name: HISTORY_HEADING });
    const shown = within(history)
      .getAllByRole("row")
      .slice(1)
      .map((row) => within(row).getAllByRole("cell")[1].textContent);
    expect(shown).toEqual(["third.example", "second.example", "first.example"]);
  });
});

describe("links are plain text (done when 2)", () => {
  it("never puts a link element in the table, and clicking a link does nothing", async () => {
    const user = userEvent.setup();
    render(<HistoryTable checks={SAMPLE} onClear={() => {}} />);

    expect(within(screen.getByRole("table")).queryAllByRole("link")).toHaveLength(0);
    expect(document.querySelector("table a")).toBeNull();

    await user.click(screen.getByText(SAMPLE[0].link));
    expect(window.location.href).not.toContain("parcel-redelivery");
  });
});

describe("each result shows its word and icon (done when 3)", () => {
  it.each([
    ["High risk", "octagon-alert"],
    ["Suspicious", "triangle-alert"],
    ["Safe", "shield-check"],
  ])("shows %s with the result card's %s icon", (result, icon) => {
    render(<HistoryTable checks={SAMPLE} onClear={() => {}} />);

    const cell = screen.getByText(result, { selector: "span" }).closest("td");
    const svg = cell.querySelector("svg");
    expect(svg).toHaveAttribute("data-icon", icon);
    // The icon is decorative: the word next to it is what a screen reader reads.
    expect(svg).toHaveAttribute("aria-hidden", "true");
  });
});

describe("clear my history", () => {
  it("empties the table, keeps focus on the history heading, and stays empty after a reload", async () => {
    const user = userEvent.setup();
    window.localStorage.setItem(HISTORY_KEY, JSON.stringify(SAMPLE));
    const { unmount } = render(<App />);
    expect(rows()).toHaveLength(3);

    await user.click(screen.getByRole("button", { name: CLEAR_TEXT }));

    expect(rows()).toHaveLength(0);
    expect(screen.getByRole("heading", { name: HISTORY_HEADING })).toHaveFocus();
    expect(loadHistory()).toEqual([]);

    // A reload: the page opens again and reads storage afresh.
    unmount();
    render(<App />);
    expect(rows()).toHaveLength(0);
  });

  it("keeps the history cleared when it is cleared while a check is still running", async () => {
    const user = userEvent.setup();
    window.localStorage.setItem(HISTORY_KEY, JSON.stringify(SAMPLE));
    let finish;
    const running = new Promise((resolve) => {
      finish = resolve;
    });
    render(<App check={() => running} />);

    await user.type(screen.getByLabelText(LABEL), "https://new-check.example/");
    await user.click(screen.getByRole("button", { name: "Check" }));
    await user.click(screen.getByRole("button", { name: CLEAR_TEXT }));
    expect(rows()).toHaveLength(0);

    finish({ url: "https://new-check.example/", risk_level: "Safe", score: 0.1, reasons: [], placeholder: false });
    await screen.findByRole("cell", { name: "new-check.example" });

    // Only the new check: none of the cleared ones come back, on the page or in storage.
    expect(rows()).toHaveLength(1);
    expect(loadHistory().map(({ link }) => link)).toEqual(["new-check.example"]);
  });

  it("works from the keyboard alone", async () => {
    const user = userEvent.setup();
    const cleared = [];
    render(<HistoryTable checks={SAMPLE} onClear={() => cleared.push(true)} />);

    await user.tab();
    expect(screen.getByRole("button", { name: CLEAR_TEXT })).toHaveFocus();
    await user.keyboard("{Enter}");

    expect(cleared).toHaveLength(1);
  });
});
