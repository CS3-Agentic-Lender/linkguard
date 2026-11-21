import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { ADVICE_HEADING } from "./AdvicePanel.jsx";
import PasteLinkForm, { CHECK_ANOTHER, LABEL } from "./PasteLinkForm.jsx";
import { LinkError } from "./scan.js";

// A made-up link, only ever handled as text.
const LINK = "https://parcel-redelivery.example/track?id=4821";

function answer(risk_level) {
  return async () => ({ url: LINK, risk_level, score: 0.7, reasons: [], placeholder: false });
}

async function checkALink(user, check) {
  render(<PasteLinkForm check={check} />);
  await user.type(screen.getByLabelText(LABEL), LINK);
  await user.click(screen.getByRole("button", { name: "Check" }));
}

describe("check another link (acceptance criterion 1)", () => {
  it.each(["Safe", "Suspicious", "High risk"])("shows the button under a %s result", async (level) => {
    const user = userEvent.setup();
    await checkALink(user, answer(level));

    const button = await screen.findByRole("button", { name: CHECK_ANOTHER });
    const card = screen.getByRole("heading", { name: level });
    // The button comes after the result in the page, so it reads and shows under it.
    expect(card.compareDocumentPosition(button) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("shows the button under the couldn't check message too", async () => {
    const user = userEvent.setup();
    await checkALink(user, async () => {
      throw new Error("offline");
    });

    expect(await screen.findByRole("button", { name: CHECK_ANOTHER })).toBeInTheDocument();
  });
});

describe("selecting it (acceptance criterion 2)", () => {
  it("empties the box, removes the result and its advice, and puts the cursor in the box", async () => {
    const user = userEvent.setup();
    await checkALink(user, answer("High risk"));
    await screen.findByRole("region", { name: ADVICE_HEADING });

    await user.click(screen.getByRole("button", { name: CHECK_ANOTHER }));

    const box = screen.getByLabelText(LABEL);
    expect(box).toHaveValue("");
    expect(box).toHaveFocus();
    expect(screen.queryByRole("heading", { name: "High risk" })).not.toBeInTheDocument();
    expect(screen.queryByRole("region", { name: ADVICE_HEADING })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: CHECK_ANOTHER })).not.toBeInTheDocument();
  });

  it("never sends the pasted link again", async () => {
    const user = userEvent.setup();
    const calls = [];
    await checkALink(user, async (link) => {
      calls.push(link);
      return { url: LINK, risk_level: "Safe", score: 0.1, reasons: [], placeholder: false };
    });

    await user.click(await screen.findByRole("button", { name: CHECK_ANOTHER }));

    expect(calls).toEqual([LINK]);
  });
});

describe("keyboard use (acceptance criterion 3)", () => {
  it.each([["Enter", "{Enter}"], ["Space", " "]])("works from Tab then %s", async (_name, key) => {
    const user = userEvent.setup();
    await checkALink(user, answer("Suspicious"));
    const button = await screen.findByRole("button", { name: CHECK_ANOTHER });

    // Tab moves on from the Check button until it reaches Check another link.
    for (let presses = 0; presses < 20 && document.activeElement !== button; presses += 1) {
      await user.tab();
    }
    expect(button).toHaveFocus();
    await user.keyboard(key);

    expect(screen.getByLabelText(LABEL)).toHaveValue("");
    expect(screen.getByLabelText(LABEL)).toHaveFocus();
    expect(screen.queryByRole("heading", { name: "Suspicious" })).not.toBeInTheDocument();
  });
});

describe("before the first check (acceptance criterion 4)", () => {
  it("is not shown on an empty form", () => {
    render(<PasteLinkForm check={answer("Safe")} />);

    expect(screen.queryByRole("button", { name: CHECK_ANOTHER })).not.toBeInTheDocument();
  });

  it("is not shown while a check is running", async () => {
    const user = userEvent.setup();
    await checkALink(user, () => new Promise(() => {}));

    expect(screen.queryByRole("button", { name: CHECK_ANOTHER })).not.toBeInTheDocument();
  });

  it("is not shown when the pasted text was turned down, so the text stays to fix", async () => {
    const user = userEvent.setup();
    await checkALink(user, async () => {
      throw new LinkError("Paste a link first");
    });

    await screen.findByRole("alert");
    expect(screen.queryByRole("button", { name: CHECK_ANOTHER })).not.toBeInTheDocument();
    expect(screen.getByLabelText(LABEL)).toHaveValue(LINK);
  });
});
