import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import App from "./App.jsx";
import { CANT_CHECK, LABEL } from "./PasteLinkForm.jsx";
import { LinkError, PLACEHOLDER, checkLink } from "./scan.js";

// The three messages, word for word from the clear-errors story. The backend
// sends them as {"error": "..."} with status 400.
const EMPTY = "Paste a link first";
const TOO_LONG = "That link is too long to check. Links over 2,000 characters can't be checked.";
const NOT_A_LINK = "That doesn't look like a web address. It usually starts with www. or https://";

const PLACEHOLDER_REPLY = { url: "x", risk_level: null, score: null, reasons: [], placeholder: true };

function reply(status, body) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("checkLink with a turned-down link", () => {
  it("rejects with the backend's own message when it replies 400 with an error", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(reply(400, { error: NOT_A_LINK }));

    const failure = await checkLink("hello there", fetchImpl).catch((error) => error);

    expect(failure).toBeInstanceOf(LinkError);
    expect(failure.message).toBe(NOT_A_LINK);
  });

  it("treats a 400 without a message as a failed check, not a link error", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(reply(400, { detail: "Bad Request" }));

    const failure = await checkLink("hello there", fetchImpl).catch((error) => error);

    expect(failure).not.toBeInstanceOf(LinkError);
  });
});

describe("error next to the link box", () => {
  it.each([
    ["an empty box", "   ", EMPTY],
    ["text that isn't a link", "hello there", NOT_A_LINK],
    ["a link over 2,000 characters", `https://a.example/${"x".repeat(2001)}`, TOO_LONG],
  ])("shows the message in words for %s, ties it to the box and keeps the text", async (_, pasted, message) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(reply(400, { error: message })));
    const user = userEvent.setup();
    render(<App />);
    const box = screen.getByLabelText(LABEL);

    await user.click(box);
    await user.paste(pasted);
    await user.keyboard("{Enter}");

    // In words, in an alert so a screen reader reads it out straight away.
    expect(await screen.findByRole("alert")).toHaveTextContent(message);
    // The box is marked invalid and described by the message, so it is read again on focus.
    expect(box).toHaveAttribute("aria-invalid", "true");
    expect(box).toHaveAccessibleDescription(expect.stringContaining(message));
    // What the user pasted stays, so they can fix it.
    expect(box).toHaveValue(pasted);
    // It isn't mixed up with the "couldn't check" failure.
    expect(screen.getByRole("status")).not.toHaveTextContent(CANT_CHECK);
  });

  it("clears the message once the text is changed and checked again", async () => {
    const fetchImpl = vi
      .fn()
      .mockResolvedValueOnce(reply(400, { error: NOT_A_LINK }))
      .mockResolvedValueOnce(reply(200, PLACEHOLDER_REPLY));
    vi.stubGlobal("fetch", fetchImpl);
    const user = userEvent.setup();
    render(<App />);
    const box = screen.getByLabelText(LABEL);

    await user.type(box, "hello there{Enter}");
    await screen.findByRole("alert");

    await user.clear(box);
    await user.type(box, "https://bank-login.example/verify{Enter}");

    expect(await screen.findByRole("status")).toHaveTextContent(PLACEHOLDER);
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(box).not.toHaveAttribute("aria-invalid");
    expect(box).not.toHaveAccessibleDescription(expect.stringContaining(NOT_A_LINK));
  });
});
