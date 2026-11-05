import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import App from "./App.jsx";
import { CANT_CHECK, LABEL } from "./PasteLinkForm.jsx";
import { SAFE_CAVEAT } from "./ResultCard.jsx";
import { PLACEHOLDER, checkLink } from "./scan.js";

// Made-up link, only ever handled as text.
const LINK = "https://bank-login.example/verify";

// The placeholder reply exactly as the backend sends it today.
const PLACEHOLDER_REPLY = { url: LINK, risk_level: null, score: null, reasons: [], placeholder: true };

function reply(status, body) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("checkLink", () => {
  it("sends the pasted text to POST /scan as JSON", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(reply(200, PLACEHOLDER_REPLY));

    await checkLink(LINK, fetchImpl);

    expect(fetchImpl).toHaveBeenCalledExactlyOnceWith("/scan", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url: LINK }),
    });
  });

  it("passes the placeholder reply on to the result card", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(reply(200, PLACEHOLDER_REPLY));

    await expect(checkLink(LINK, fetchImpl)).resolves.toEqual(PLACEHOLDER_REPLY);
  });

  it("fails when the backend can't be reached", async () => {
    const fetchImpl = vi.fn().mockRejectedValue(new TypeError("Failed to fetch"));

    await expect(checkLink(LINK, fetchImpl)).rejects.toThrow();
  });

  it.each([500, 502, 503])("fails when the backend replies with server error %i", async (status) => {
    const fetchImpl = vi.fn().mockResolvedValue(reply(status, { detail: "Internal Server Error" }));

    await expect(checkLink(LINK, fetchImpl)).rejects.toThrow(String(status));
  });

  it("passes a reply with a risk level on to the result card", async () => {
    const result = { url: LINK, risk_level: "Safe", score: 0.1, reasons: [], placeholder: false };
    const fetchImpl = vi.fn().mockResolvedValue(reply(200, result));

    await expect(checkLink(LINK, fetchImpl)).resolves.toEqual(result);
  });
});

describe("paste-a-link page connected to /scan", () => {
  it("shows the placeholder message after one request to /scan, and no risk level", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(reply(200, PLACEHOLDER_REPLY));
    vi.stubGlobal("fetch", fetchImpl);
    const user = userEvent.setup();
    render(<App />);

    await user.type(screen.getByLabelText(LABEL), `${LINK}{Enter}`);

    const status = await screen.findByRole("status");
    expect(status).toHaveTextContent(PLACEHOLDER);
    expect(status).not.toHaveTextContent(/Safe|Suspicious|High risk/);
    expect(fetchImpl).toHaveBeenCalledOnce();
    expect(fetchImpl.mock.calls[0][0]).toBe("/scan");
  });

  it("shows the couldn't-check message when the backend is stopped", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    const user = userEvent.setup();
    render(<App />);

    await user.type(screen.getByLabelText(LABEL), `${LINK}{Enter}`);

    expect(await screen.findByRole("status")).toHaveTextContent(CANT_CHECK);
  });

  it("shows the couldn't-check message when the backend replies with a server error", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(reply(500, { detail: "Internal Server Error" })));
    const user = userEvent.setup();
    render(<App />);

    await user.type(screen.getByLabelText(LABEL), `${LINK}{Enter}`);

    expect(await screen.findByRole("status")).toHaveTextContent(CANT_CHECK);
  });

  it.each([
    ["Safe", "safe"],
    ["Suspicious", "suspicious"],
    ["High risk", "high"],
  ])("shows a %s reply on the result card after one request to /scan", async (level, dataLevel) => {
    const result = { url: LINK, risk_level: level, score: 0.5, reasons: [], placeholder: false };
    const fetchImpl = vi.fn().mockResolvedValue(reply(200, result));
    vi.stubGlobal("fetch", fetchImpl);
    const user = userEvent.setup();
    render(<App />);

    await user.type(screen.getByLabelText(LABEL), `${LINK}{Enter}`);

    const status = await screen.findByRole("status");
    const heading = await screen.findByRole("heading", { name: level });
    expect(status).toContainElement(heading);
    expect(status.querySelector(".result-card")).toHaveAttribute("data-level", dataLevel);
    expect(status).not.toHaveTextContent(CANT_CHECK);
    expect(status).not.toHaveTextContent(PLACEHOLDER);
    expect(fetchImpl).toHaveBeenCalledOnce();
    expect(fetchImpl.mock.calls[0][0]).toBe("/scan");
  });

  it("shows the Safe caveat with a Safe reply", async () => {
    const result = { url: LINK, risk_level: "Safe", score: 0.1, reasons: [], placeholder: false };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(reply(200, result)));
    const user = userEvent.setup();
    render(<App />);

    await user.type(screen.getByLabelText(LABEL), `${LINK}{Enter}`);

    expect(await screen.findByRole("status")).toHaveTextContent(SAFE_CAVEAT);
  });

  it.each([["Unknown"], ["safe"], [""], [null]])(
    "shows the couldn't-check message, not a level, for a reply with risk level %j",
    async (level) => {
      const result = { url: LINK, risk_level: level, score: 0.5, reasons: [], placeholder: false };
      vi.stubGlobal("fetch", vi.fn().mockResolvedValue(reply(200, result)));
      const user = userEvent.setup();
      render(<App />);

      await user.type(screen.getByLabelText(LABEL), `${LINK}{Enter}`);

      const status = await screen.findByRole("status");
      await screen.findByText(CANT_CHECK);
      expect(status).toHaveTextContent(CANT_CHECK);
      expect(screen.queryByRole("heading", { name: /Safe|Suspicious|High risk/ })).not.toBeInTheDocument();
    },
  );
});
