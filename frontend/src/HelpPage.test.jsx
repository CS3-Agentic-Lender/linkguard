import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { HELP_LINK_TEXT, HELP_ROUTES } from "./advice.js";
import HelpPage, { BACK_TEXT } from "./HelpPage.jsx";

// The advice text file with its sources. Every route the page shows must be in it.
const ADVICE_FILE = readFileSync(resolve(process.cwd(), "../docs/advice.md"), "utf8");

describe("where to get help page", () => {
  it("lists every Irish reporting route under its heading", () => {
    render(<HelpPage />);

    expect(screen.getByRole("heading", { level: 1, name: HELP_LINK_TEXT })).toBeInTheDocument();
    for (const { situation, where } of HELP_ROUTES) {
      expect(screen.getByText(situation)).toBeInTheDocument();
      expect(screen.getByText(where)).toBeInTheDocument();
    }
  });

  it.each(HELP_ROUTES.flatMap(({ situation, where }) => [situation, where]))(
    "takes each route from docs/advice.md word for word: %s",
    (text) => {
      expect(ADVICE_FILE).toContain(text);
    },
  );

  it("never shows a UK-only reporting route", () => {
    render(<HelpPage />);

    expect(document.body.textContent).not.toMatch(/7726/);
    expect(document.body.textContent).not.toMatch(/phishing\.gov\.uk/i);
  });

  it("shows each route's documented official source and keeps Back keyboard reachable", async () => {
    const user = userEvent.setup();
    render(<HelpPage />);

    expect(screen.getAllByRole("link")).toHaveLength(HELP_ROUTES.length + 1);
    for (const [index, { source }] of HELP_ROUTES.entries()) {
      const route = screen.getAllByRole("listitem")[index];
      const link = within(route).getByRole("link", { name: source.name });
      expect(link).toHaveAttribute("href", source.url);
      expect(ADVICE_FILE).toContain(source.url);
      await user.tab();
      expect(link).toHaveFocus();
    }
    await user.tab();
    expect(screen.getByRole("link", { name: BACK_TEXT })).toHaveFocus();
    expect(screen.getByRole("link", { name: BACK_TEXT })).toHaveAttribute("href", "#");
  });
});
