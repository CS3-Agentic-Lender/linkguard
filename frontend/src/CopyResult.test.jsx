import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { EVERY_RESULT, HIGH_RISK_EXTRA, SUSPICIOUS } from "./advice.js";
import CopyResult, {
  COPIED,
  COPIED_MS,
  COPY_BUTTON,
  COPY_FAILED,
  COPY_INTRO,
  COPY_TEXT_LABEL,
  COPY_WARNING,
  copyText,
} from "./CopyResult.jsx";
import PasteLinkForm, { LABEL } from "./PasteLinkForm.jsx";
import { CANT_CHECK, PLACEHOLDER } from "./scan.js";

// Made-up link on a reserved name, only ever handled as text.
const LINK = "http://secure-login-account-verify.example";
const REASONS = ["The website name in this link is unusually long.", "The website name has a lot of dots or hyphens."];

function reply(risk_level, reasons = REASONS) {
  return { url: LINK, risk_level, score: 0.87, reasons, placeholder: false };
}

function copyButton() {
  return screen.getByRole("button", { name: COPY_BUTTON });
}

async function checkAndWait(user, answer) {
  render(<PasteLinkForm check={async () => answer} />);
  await user.type(screen.getByLabelText(LABEL), LINK);
  await user.click(screen.getByRole("button", { name: "Check" }));
}

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

describe("the Copy result button (acceptance criterion 1)", () => {
  it.each(["Safe", "Suspicious", "High risk"])("sits straight under a %s result card", async (level) => {
    const user = userEvent.setup();
    await checkAndWait(user, reply(level));

    const button = await screen.findByRole("button", { name: COPY_BUTTON });
    const card = screen.getByRole("status").querySelector(".result-card");
    expect(card).not.toBeNull();
    expect(screen.getByRole("status").nextElementSibling).toContainElement(button);
  });

  it.each([
    ["a placeholder reply", { url: LINK, risk_level: null, score: null, reasons: [], placeholder: true }, PLACEHOLDER],
    ["a failed check", { url: LINK, risk_level: "Unknown", score: 0.5, reasons: [], placeholder: false }, CANT_CHECK],
  ])("isn't shown for %s, which has no result to copy", async (_, failed, message) => {
    const user = userEvent.setup();
    await checkAndWait(user, failed);

    await screen.findByText(message);
    expect(screen.queryByRole("button", { name: COPY_BUTTON })).not.toBeInTheDocument();
  });
});

describe("what gets copied (acceptance criterion 2)", () => {
  it("puts the link, level, reasons, advice and warning on the clipboard, in that order", async () => {
    const user = userEvent.setup();
    render(<CopyResult text={copyText(reply("High risk"), "high")} />);

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
    const lines = copyText(reply("Suspicious", ["One.", "Two.", "Three.", "Four."]), "suspicious").split("\n");

    expect(lines.slice(2, 5)).toEqual(["One.", "Two.", "Three."]);
    expect(lines).not.toContain("Four.");
  });

  it("says Copied for a few seconds, then goes back to Copy result", async () => {
    // The clock only moves when the test moves it, so a slow run can't pass the 3 seconds early.
    vi.useFakeTimers();
    vi.spyOn(navigator, "clipboard", "get").mockReturnValue({ writeText: () => Promise.resolve() });
    render(<CopyResult text="x" />);

    await act(async () => copyButton().click());
    expect(screen.getByRole("button", { name: COPIED })).toBeInTheDocument();

    act(() => vi.advanceTimersByTime(COPIED_MS - 1));
    expect(screen.getByRole("button", { name: COPIED })).toBeInTheDocument();
    act(() => vi.advanceTimersByTime(1));
    expect(copyButton()).toBeInTheDocument();
  });
});

describe("screen readers (acceptance criterion 3)", () => {
  it("says Copied in its own live area, outside the result's live region, so the result isn't read again", async () => {
    const user = userEvent.setup();
    await checkAndWait(user, reply("High risk"));
    const resultRegion = screen.getByRole("status");

    await user.click(await screen.findByRole("button", { name: COPY_BUTTON }));

    const copied = screen.getByRole("button", { name: COPIED });
    expect(resultRegion).not.toContainElement(copied);
    const ownArea = copied.parentElement.querySelector('[aria-live="polite"]');
    expect(ownArea).toHaveTextContent(COPIED);
    expect(resultRegion).not.toContainElement(ownArea);
  });
});

describe("a blocked clipboard (acceptance criterion 4)", () => {
  it("says how to copy by hand, and shows the full text to select, when the browser refuses", async () => {
    const user = userEvent.setup();
    vi.spyOn(navigator.clipboard, "writeText").mockRejectedValue(new DOMException("Denied", "NotAllowedError"));
    const text = copyText(reply("Suspicious"), "suspicious");
    render(<CopyResult text={text} />);

    await user.click(copyButton());

    const message = screen.getByText(COPY_FAILED);
    expect(message).toBeVisible();
    expect(message).toHaveAttribute("aria-live", "polite");
    const box = screen.getByLabelText(COPY_TEXT_LABEL);
    expect(box).toHaveValue(text);
    expect(box).toHaveAttribute("readonly");
    expect(screen.queryByRole("button", { name: COPIED })).not.toBeInTheDocument();
  });

  it("does the same when the browser has no clipboard at all", async () => {
    const user = userEvent.setup();
    vi.spyOn(navigator, "clipboard", "get").mockReturnValue(undefined);
    render(<CopyResult text="x" />);

    await user.click(copyButton());

    expect(screen.getByText(COPY_FAILED)).toBeVisible();
    expect(screen.getByLabelText(COPY_TEXT_LABEL)).toHaveValue("x");
  });
});

describe("the keyboard alone (acceptance criterion 5)", () => {
  it("can be reached with Tab and pressed with Enter or Space", async () => {
    const user = userEvent.setup();
    render(<CopyResult text={copyText(reply("High risk"), "high")} />);

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
