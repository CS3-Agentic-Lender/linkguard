import { act, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";

import { ADVICE_HEADING } from "./AdvicePanel.jsx";
import App, { HELP_HASH } from "./App.jsx";
import { HELP_LINK_TEXT } from "./advice.js";
import { BACK_TEXT } from "./HelpPage.jsx";
import { LABEL } from "./PasteLinkForm.jsx";

// A made-up link, only ever handled as text.
const LINK = "https://parcel-redelivery.example/track?id=4821";

function answer(risk_level) {
  return async () => ({ url: LINK, risk_level, score: 0.5, reasons: [], placeholder: false });
}

// jsdom changes the hash on a link click but fires no hashchange event, so the tests fire it.
async function settleHash() {
  await act(async () => {
    window.dispatchEvent(new HashChangeEvent("hashchange"));
  });
}

async function goTo(hash) {
  window.location.hash = hash;
  await settleHash();
}

afterEach(() => {
  window.location.hash = "";
});

describe("where to get help link (acceptance criterion 4)", () => {
  it("sits in the header on the checker page and stays there on the help page", async () => {
    render(<App check={answer("Safe")} />);
    expect(within(screen.getByRole("banner")).getByRole("link", { name: HELP_LINK_TEXT })).toHaveAttribute(
      "href",
      HELP_HASH,
    );

    await goTo(HELP_HASH);

    expect(within(screen.getByRole("banner")).getByRole("link", { name: HELP_LINK_TEXT })).toHaveAttribute(
      "aria-current",
      "page",
    );
  });

  it("opens the help page and hides the checker", async () => {
    render(<App check={answer("Safe")} />);

    await goTo(HELP_HASH);

    expect(screen.getByRole("heading", { level: 1, name: HELP_LINK_TEXT })).toBeInTheDocument();
    expect(screen.getByLabelText(LABEL)).not.toBeVisible();
  });
});

describe("keyboard use (acceptance criterion 5)", () => {
  it("reaches the help link with Tab and opens the help page with Enter, focus on its heading", async () => {
    const user = userEvent.setup();
    render(<App check={answer("Safe")} />);

    await user.tab();
    expect(screen.getByRole("link", { name: HELP_LINK_TEXT })).toHaveFocus();

    await user.keyboard("{Enter}");
    await settleHash();

    expect(window.location.hash).toBe(HELP_HASH);
    expect(screen.getByRole("heading", { level: 1, name: HELP_LINK_TEXT })).toHaveFocus();
  });
});

describe("going to the help page and back", () => {
  it("keeps the pasted link, its result and its advice", async () => {
    const user = userEvent.setup();
    render(<App check={answer("High risk")} />);
    await user.type(screen.getByLabelText(LABEL), LINK);
    await user.click(screen.getByRole("button", { name: "Check" }));
    await screen.findByRole("region", { name: ADVICE_HEADING });

    await user.click(screen.getByRole("link", { name: HELP_LINK_TEXT }));
    await settleHash();
    expect(screen.getByRole("heading", { level: 1, name: HELP_LINK_TEXT })).toBeInTheDocument();

    await user.click(screen.getByRole("link", { name: BACK_TEXT }));
    await settleHash();

    expect(screen.queryByRole("heading", { level: 1, name: HELP_LINK_TEXT })).not.toBeInTheDocument();
    expect(screen.getByLabelText(LABEL)).toHaveValue(LINK);
    expect(screen.getByRole("heading", { name: "High risk" })).toBeVisible();
    expect(screen.getByRole("region", { name: ADVICE_HEADING })).toBeVisible();
  });
});
