import { act, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { EVERY_RESULT, HIGH_RISK_EXTRA, SUSPICIOUS } from "./advice.js";
import PasteLinkForm, { LABEL } from "./PasteLinkForm.jsx";
import ResultCard, {
  COPIED,
  COPIED_MS,
  COPY_BUTTON,
  COPY_FAILED,
  COPY_INTRO,
  COPY_WARNING,
  copyText,
} from "./ResultCard.jsx";

// Made-up link on a reserved name, only ever handled as text.
const LINK = "http://secure-login-account-verify.example";
const REASONS = ["The website name in this link is unusually long.", "The website name has a lot of dots or hyphens."];

function reply(risk_level, reasons = REASONS) {
  return { url: LINK, risk_level, score: 0.87, reasons, placeholder: false };
}

function copyButton() {
  return screen.getByRole("button", { name: COPY_BUTTON });
}

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

describe("the Copy result button (acceptance criterion 1)", () => {
  it.each(["Safe", "Suspicious", "High risk"])("is on a %s result card", (level) => {
    render(<ResultCard reply={reply(level)} />);

    expect(copyButton()).toBeInTheDocument();
  });

  it.each([
    ["a placeholder reply", { url: LINK, risk_level: null, score: null, reasons: [], placeholder: true }],
    ["a failed check", { url: LINK, risk_level: "Unknown", score: 0.5, reasons: [], placeholder: false }],
  ])("isn't shown for %s, which has no result to copy", (_, failed) => {
    render(<ResultCard reply={failed} />);

    expect(screen.queryByRole("button", { name: COPY_BUTTON })).not.toBeInTheDocument();
  });
});

describe("what gets copied (acceptance criterion 2)", () => {
  it("puts the link, level, reasons, advice and warning on the clipboard, in that order", async () => {
    const user = userEvent.setup();
    render(<ResultCard reply={reply("High risk")} />);

    await user.click(copyButton());

    expect(await navigator.clipboard.readText()).toBe(
      [
        `${COPY_INTRO}${LINK}`,
        "High risk",
        ...REASONS,
        ...SUSPICIOUS,
        ...HIGH_RISK_EXTRA,
        ...EVERY_RESULT,
        COPY_WARNING,
      ].join("\n"),
    );
  });

  it("copies no reasons for a Safe result, and only the advice every result gets", () => {
    const text = copyText(reply("Safe", []), "safe");

    expect(text.split("\n")).toEqual([`${COPY_INTRO}${LINK}`, "Safe", ...EVERY_RESULT, COPY_WARNING]);
  });

  it("copies at most the three reasons the card shows", () => {
    const many = ["One.", "Two.", "Three.", "Four."];

    const lines = copyText(reply("Suspicious", many), "suspicious").split("\n");

    expect(lines.slice(2, 5)).toEqual(["One.", "Two.", "Three."]);
    expect(lines).not.toContain("Four.");
  });

  it("says Copied for a few seconds, then goes back to Copy result", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    render(<ResultCard reply={reply("Suspicious")} />);

    await user.click(copyButton());
    expect(screen.getByRole("button", { name: COPIED })).toBeInTheDocument();

    act(() => vi.advanceTimersByTime(COPIED_MS));
    expect(copyButton()).toBeInTheDocument();
  });
});

describe("screen readers (acceptance criterion 3)", () => {
  it("changes the button to Copied inside the result's live region, so it is announced", async () => {
    const user = userEvent.setup();
    render(<PasteLinkForm check={async () => reply("High risk")} />);
    await user.type(screen.getByLabelText(LABEL), LINK);
    await user.click(screen.getByRole("button", { name: "Check" }));

    await user.click(await screen.findByRole("button", { name: COPY_BUTTON }));

    expect(within(screen.getByRole("status")).getByRole("button", { name: COPIED })).toBeInTheDocument();
  });
});

describe("a blocked clipboard (acceptance criterion 4)", () => {
  it("says how to copy by hand when the browser refuses", async () => {
    const user = userEvent.setup();
    vi.spyOn(navigator.clipboard, "writeText").mockRejectedValue(new DOMException("Denied", "NotAllowedError"));
    render(<ResultCard reply={reply("Suspicious")} />);

    await user.click(copyButton());

    expect(screen.getByText(COPY_FAILED)).toBeVisible();
    expect(screen.queryByRole("button", { name: COPIED })).not.toBeInTheDocument();
  });

  it("says how to copy by hand when the browser has no clipboard at all", async () => {
    const user = userEvent.setup();
    vi.spyOn(navigator, "clipboard", "get").mockReturnValue(undefined);
    render(<ResultCard reply={reply("Safe", [])} />);

    await user.click(copyButton());

    expect(screen.getByText(COPY_FAILED)).toBeVisible();
  });
});

describe("the keyboard alone (acceptance criterion 5)", () => {
  it("can be reached with Tab and pressed with Enter or Space", async () => {
    const user = userEvent.setup();
    render(<ResultCard reply={reply("High risk")} />);

    await user.tab();
    expect(copyButton()).toHaveFocus();
    expect(copyButton()).toHaveAttribute("type", "button");
    await user.keyboard("{Enter}");
    expect(await navigator.clipboard.readText()).toContain(`${COPY_INTRO}${LINK}`);

    await navigator.clipboard.writeText("");
    await user.keyboard(" ");
    expect(await navigator.clipboard.readText()).toContain(COPY_WARNING);
  });
});
