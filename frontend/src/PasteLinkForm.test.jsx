import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import App from "./App.jsx";
import PasteLinkForm, { CANT_CHECK, CHECKING, LABEL } from "./PasteLinkForm.jsx";

// Made-up links, only ever handled as text.
const LINK = "https://parcel-redelivery.example/track?id=4821";

// A check whose reply we release by hand, so a test can look at the page while it waits.
function pendingCheck() {
  let reply;
  const check = vi.fn(
    () =>
      new Promise((resolve, reject) => {
        reply = { resolve, reject };
      }),
  );
  return { check, reply: () => reply };
}

describe("paste-a-link form", () => {
  it("shows the box with its visible label and a Check button", () => {
    render(<PasteLinkForm check={vi.fn()} />);

    expect(screen.getByText(LABEL).tagName).toBe("LABEL");
    expect(screen.getByLabelText(LABEL)).toHaveAttribute("type", "text");
    expect(screen.getByRole("button", { name: "Check" })).toHaveAttribute("type", "submit");
  });

  it("lets a keyboard user Tab to the box, then the button, and check with Enter", async () => {
    const user = userEvent.setup();
    const check = vi.fn().mockResolvedValue("Reply");
    render(<PasteLinkForm check={check} />);

    await user.tab();
    expect(screen.getByLabelText(LABEL)).toHaveFocus();
    await user.tab();
    expect(screen.getByRole("button", { name: "Check" })).toHaveFocus();

    await user.click(screen.getByLabelText(LABEL));
    await user.keyboard(`${LINK}{Enter}`);
    expect(check).toHaveBeenCalledExactlyOnceWith(LINK);
  });

  it("shows Checking… while waiting, then the reply in a polite live region, without moving focus", async () => {
    const user = userEvent.setup();
    const { check, reply } = pendingCheck();
    render(<PasteLinkForm check={check} />);
    const status = screen.getByRole("status");
    expect(status).toHaveAttribute("aria-live", "polite");

    await user.type(screen.getByLabelText(LABEL), `${LINK}{Enter}`);
    expect(status).toHaveTextContent(CHECKING);
    expect(screen.getByRole("button", { name: "Check" })).toHaveAttribute("aria-disabled", "true");

    reply().resolve("The reply from the check");
    expect(await screen.findByText("The reply from the check")).toBe(status);
    expect(screen.getByLabelText(LABEL)).toHaveFocus();
    expect(screen.getByRole("button", { name: "Check" })).toHaveAttribute("aria-disabled", "false");
  });

  it("sends only one check while one is already waiting", async () => {
    const user = userEvent.setup();
    const { check } = pendingCheck();
    render(<PasteLinkForm check={check} />);

    await user.type(screen.getByLabelText(LABEL), `${LINK}{Enter}`);
    await user.keyboard("{Enter}");
    await user.click(screen.getByRole("button", { name: "Check" }));

    expect(check).toHaveBeenCalledOnce();
  });

  it("says it couldn't check the link when the check fails", async () => {
    const user = userEvent.setup();
    const { check, reply } = pendingCheck();
    render(<PasteLinkForm check={check} />);

    await user.type(screen.getByLabelText(LABEL), `${LINK}{Enter}`);
    reply().reject(new Error("no reply"));

    expect(await screen.findByRole("status")).toHaveTextContent(CANT_CHECK);
  });

  it("never shows the pasted link as a clickable link", async () => {
    const user = userEvent.setup();
    const check = vi.fn().mockResolvedValue(`Checked ${LINK}`);
    const { container } = render(<App check={check} />);

    await user.type(screen.getByLabelText(LABEL), `${LINK}{Enter}`);
    await screen.findByText(`Checked ${LINK}`);

    expect(screen.queryAllByRole("link")).toHaveLength(0);
    expect(container.querySelectorAll("a, [href]")).toHaveLength(0);
  });
});

describe("paste-a-link page", () => {
  it("shows the heading and the form", () => {
    render(<App />);

    expect(screen.getByRole("heading", { level: 1, name: "Is this link safe?" })).toBeInTheDocument();
    expect(screen.getByLabelText(LABEL)).toBeInTheDocument();
  });

  it("says it couldn't check the link until the page is connected to /scan", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.type(screen.getByLabelText(LABEL), `${LINK}{Enter}`);

    expect(await screen.findByRole("status")).toHaveTextContent(CANT_CHECK);
  });
});
