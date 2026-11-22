import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { EVERY_RESULT, HIGH_RISK_EXTRA, SUSPICIOUS } from "./advice.js";
import CopyResult, {
  COPIED,
  COPIED_MS,
  COPY_BUTTON,
  COPY_DEFANGED,
  COPY_FAILED,
  COPY_INTRO,
  COPY_TEXT_LABEL,
  COPY_WARNING,
  copyText,
  defang,
} from "./CopyResult.jsx";
import PasteLinkForm, { LABEL } from "./PasteLinkForm.jsx";
import { CANT_CHECK, PLACEHOLDER } from "./scan.js";

// Made-up link on a reserved name, only ever handled as text.
const LINK = "http://secure-login-account-verify.example";
// The same link as it is copied, so a messaging app can't make it tappable.
const COPIED_LINK = "hxxp://secure-login-account-verify[.]example";
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
        `${COPY_INTRO}${COPIED_LINK}`,
        COPY_DEFANGED,
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

    expect(text.split("\n")).toEqual([
      `${COPY_INTRO}${COPIED_LINK}`,
      COPY_DEFANGED,
      "Safe",
      ...EVERY_RESULT,
      COPY_WARNING,
    ]);
  });

  it("copies at most the three reasons the card shows", () => {
    const lines = copyText(reply("Suspicious", ["One.", "Two.", "Three.", "Four."]), "suspicious").split("\n");

    expect(lines.slice(3, 6)).toEqual(["One.", "Two.", "Three."]);
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
    expect(await navigator.clipboard.readText()).toContain(`${COPY_INTRO}${COPIED_LINK}`);

    await navigator.clipboard.writeText("");
    await user.keyboard(" ");
    expect(await navigator.clipboard.readText()).toContain(COPY_WARNING);
  });
});

// The "copied link stops being tappable" story. Messaging apps make a link tappable when
// they see a web address: a scheme such as http:// or https://, "www.", or a name and a
// dot ending such as ".com". This rough version of that test must find nothing to tap.
const TAPPABLE = /(https?:\/\/|www\.|[a-z0-9-]\.[a-z]{2,})/i;

describe("the copied link can't be tapped (copied link criterion 1)", () => {
  it.each([
    ["http://secure-login-account-verify.example", "hxxp://secure-login-account-verify[.]example"],
    ["https://paypa1.example/login.php?next=a.b", "hxxps://paypa1[.]example/login[.]php?next=a[.]b"],
    ["HTTPS://BANK.EXAMPLE", "hxxpS://BANK[.]EXAMPLE"],
    ["www.free-prize.example", "www[.]free-prize[.]example"],
    ["free-prize.example/claim", "free-prize[.]example/claim"],
  ])("writes %s as %s", (link, written) => {
    expect(defang(link)).toBe(written);
    expect(TAPPABLE.test(link)).toBe(true);
    expect(TAPPABLE.test(written)).toBe(false);
  });

  it("leaves nothing in the copied text that looks like a link to tap", () => {
    const text = copyText({ ...reply("High risk"), url: "https://www.secure-login.example/verify" }, "high");

    expect(text.split("\n")[0]).toBe(`${COPY_INTRO}hxxps://www[.]secure-login[.]example/verify`);
    expect(text).not.toMatch(TAPPABLE);
  });
});

describe("the line saying why (copied link criterion 2)", () => {
  it("comes straight after the link, in one plain sentence", () => {
    const lines = copyText(reply("Suspicious"), "suspicious").split("\n");

    expect(lines[1]).toBe(COPY_DEFANGED);
    expect(COPY_DEFANGED).toMatch(/^[^.]+\.$/);
  });
});

describe("everything else stays the same (copied link criterion 3)", () => {
  it("still shows the link on the result card exactly as it was pasted", async () => {
    const user = userEvent.setup();
    await checkAndWait(user, reply("High risk"));

    expect(screen.getByRole("status")).toHaveTextContent(`Link checked: ${LINK}`);
    expect(screen.getByRole("status")).not.toHaveTextContent(COPIED_LINK);
  });

  it.each([
    ["Safe", "safe", []],
    ["Suspicious", "suspicious", REASONS],
    ["High risk", "high", REASONS],
  ])("copies every other line of a %s result unchanged", (risk, level, reasons) => {
    const lines = copyText(reply(risk), level).split("\n");
    const advice = { safe: [], suspicious: SUSPICIOUS, high: [...SUSPICIOUS, ...HIGH_RISK_EXTRA] }[level];

    expect(lines.slice(2)).toEqual([risk, ...reasons, ...advice, ...EVERY_RESULT, COPY_WARNING]);
  });
});
