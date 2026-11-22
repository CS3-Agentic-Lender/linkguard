import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import PasteLinkForm, { LABEL } from "./PasteLinkForm.jsx";
import RiskLevelGuide, { BEST_GUESS, GUIDE_BUTTON, LEVEL_MEANINGS, YOUR_RESULT } from "./RiskLevelGuide.jsx";
import { CANT_CHECK, PLACEHOLDER } from "./scan.js";

// Made-up links, only ever handled as text.
const LINK = "https://parcel-redelivery.example/track?id=4821";
const OTHER_LINK = "https://refund-help.example/claim";

function guideButton() {
  return screen.getByRole("button", { name: GUIDE_BUTTON });
}

async function openGuide(level = "suspicious") {
  const user = userEvent.setup();
  render(<RiskLevelGuide level={level} />);
  await user.click(guideButton());
  return { user, list: screen.getByRole("list") };
}

describe("the risk level explanation (acceptance criterion 1)", () => {
  it("is closed at first, and shows one sentence for each of the three levels when opened", async () => {
    const user = userEvent.setup();
    render(<RiskLevelGuide level="safe" />);
    expect(screen.queryByRole("list")).not.toBeInTheDocument();

    await user.click(guideButton());

    const items = within(screen.getByRole("list")).getAllByRole("listitem");
    expect(items).toHaveLength(3);
    for (const [index, { name, meaning }] of LEVEL_MEANINGS.entries()) {
      expect(items[index]).toHaveTextContent(`${name}: ${meaning}`);
    }
  });

  it("uses one short plain sentence or two per level", () => {
    for (const { meaning } of LEVEL_MEANINGS) {
      expect(meaning.split(/(?<=\.)\s/).length).toBeLessThanOrEqual(2);
      expect(meaning.length).toBeLessThanOrEqual(100);
    }
  });
});

describe("hiding it again (acceptance criterion 2)", () => {
  it("hides the sentences when the button is selected again", async () => {
    const { user } = await openGuide();

    await user.click(guideButton());

    expect(screen.queryByRole("list")).not.toBeInTheDocument();
  });
});

describe("marking the current level (acceptance criterion 3)", () => {
  it.each([
    ["safe", "Safe"],
    ["suspicious", "Suspicious"],
    ["high", "High risk"],
  ])("marks %s with its word, its icon and 'Your result', and no other level", async (level, name) => {
    const { list } = await openGuide(level);

    const current = within(list)
      .getAllByRole("listitem")
      .filter((item) => item.getAttribute("aria-current") === "true");
    expect(current).toHaveLength(1);
    expect(current[0]).toHaveTextContent(`${name}:`);
    expect(current[0]).toHaveTextContent(YOUR_RESULT);
    expect(current[0].querySelector("svg[data-icon]")).not.toBeNull();
    expect(within(list).getAllByText(YOUR_RESULT)).toHaveLength(1);
  });

  it("separates the sentence and 'Your result' with a space, so they aren't read as one word", async () => {
    const { list } = await openGuide("suspicious");

    const current = within(list)
      .getAllByRole("listitem")
      .find((item) => item.getAttribute("aria-current") === "true");
    const meaning = LEVEL_MEANINGS.find(({ name }) => name === "Suspicious").meaning;
    expect(current.textContent).toContain(`${meaning} ${YOUR_RESULT}`);
  });

  it("gives every level its own icon, hidden from screen readers since the word says it", async () => {
    const { list } = await openGuide();

    const icons = within(list)
      .getAllByRole("listitem")
      .map((item) => item.querySelector("svg"));
    expect(new Set(icons.map((icon) => icon.dataset.icon)).size).toBe(3);
    for (const icon of icons) expect(icon).toHaveAttribute("aria-hidden", "true");
  });
});

describe("a best guess, not a guarantee (acceptance criterion 4)", () => {
  it("says the result is a best guess, not a guarantee", async () => {
    await openGuide();

    expect(screen.getByText(BEST_GUESS)).toBeVisible();
    expect(BEST_GUESS).toMatch(/best guess/);
    expect(BEST_GUESS).toMatch(/not a guarantee/);
  });
});

describe("keyboard and screen readers (acceptance criterion 5)", () => {
  it("is a real button that says whether it is open or closed, and points at what it opens", async () => {
    const user = userEvent.setup();
    render(<RiskLevelGuide level="high" />);
    const button = guideButton();
    expect(button).toHaveAttribute("type", "button");
    expect(button).toHaveAttribute("aria-expanded", "false");

    await user.click(button);

    expect(button).toHaveAttribute("aria-expanded", "true");
    const panel = document.getElementById(button.getAttribute("aria-controls"));
    expect(panel).toBeVisible();
    expect(within(panel).getByRole("list")).toBeInTheDocument();
  });

  it("opens with Enter and closes with Space from the keyboard alone", async () => {
    const user = userEvent.setup();
    render(<RiskLevelGuide level="safe" />);

    await user.tab();
    expect(guideButton()).toHaveFocus();
    await user.keyboard("{Enter}");
    expect(guideButton()).toHaveAttribute("aria-expanded", "true");
    await user.keyboard(" ");
    expect(guideButton()).toHaveAttribute("aria-expanded", "false");
  });
});

describe("on the page", () => {
  function answer(risk_level) {
    return async (link) => ({ url: link, risk_level, score: 0.5, reasons: [], placeholder: false });
  }

  async function check(user, link) {
    const box = screen.getByLabelText(LABEL);
    await user.clear(box);
    await user.type(box, link);
    await user.click(screen.getByRole("button", { name: "Check" }));
  }

  it("sits under the result, outside its live region, so opening it doesn't read the result again", async () => {
    const user = userEvent.setup();
    render(<PasteLinkForm check={answer("High risk")} />);
    await check(user, LINK);

    const button = await screen.findByRole("button", { name: GUIDE_BUTTON });
    expect(screen.getByRole("status")).not.toContainElement(button);
  });

  it("starts closed again when a different link is checked", async () => {
    const user = userEvent.setup();
    render(<PasteLinkForm check={answer("Suspicious")} />);
    await check(user, LINK);
    await user.click(await screen.findByRole("button", { name: GUIDE_BUTTON }));
    expect(screen.getByRole("button", { name: GUIDE_BUTTON })).toHaveAttribute("aria-expanded", "true");

    await check(user, OTHER_LINK);

    const button = await screen.findByRole("button", { name: GUIDE_BUTTON });
    expect(button).toHaveAttribute("aria-expanded", "false");
  });

  it.each([
    ["a placeholder reply", { url: LINK, risk_level: null, score: null, reasons: [], placeholder: true }, PLACEHOLDER],
    ["a failed check", { url: LINK, risk_level: "Unknown", score: 0.5, reasons: [], placeholder: false }, CANT_CHECK],
  ])("isn't shown for %s", async (_, reply, message) => {
    const user = userEvent.setup();
    render(<PasteLinkForm check={async () => reply} />);
    await check(user, LINK);

    await screen.findByText(message);
    expect(screen.queryByRole("button", { name: GUIDE_BUTTON })).not.toBeInTheDocument();
  });
});
