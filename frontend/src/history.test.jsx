import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import App from "./App.jsx";
import { checkFrom, clearHistory, HISTORY_KEY, linkToKeep, loadHistory, MAX_CHECKS, saveCheck } from "./history.js";
import { LABEL } from "./PasteLinkForm.jsx";

// Made-up links, only ever handled as text.
const LINK = "https://parcel-redelivery.example/track/4821";
// All that is saved of LINK: its website name.
const SITE = "parcel-redelivery.example";

function check(n, result = "Suspicious") {
  return { checkedAt: new Date(Date.UTC(2026, 10, 18, 9, n)).toISOString(), link: `https://site-${n}.example/`, result };
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("saving each check (done when 1)", () => {
  it("keeps only the newest 5 of six checks, newest first", () => {
    for (let n = 1; n <= 6; n += 1) {
      saveCheck(check(n));
    }

    const saved = loadHistory();
    expect(saved).toHaveLength(MAX_CHECKS);
    expect(saved.map(({ link }) => link)).toEqual([6, 5, 4, 3, 2].map((n) => `https://site-${n}.example/`));
  });

  it("saves the time, the link's website name as text and the result, and nothing else", () => {
    const now = new Date("2026-11-18T09:07:00Z");
    const saved = checkFrom({ url: LINK, risk_level: "High risk", score: 0.93, reasons: ["Long name"], placeholder: false }, now);

    expect(saved).toEqual({ checkedAt: "2026-11-18T09:07:00.000Z", link: SITE, result: "High risk" });
  });

  it("keeps no personal details that a link can carry", () => {
    // Made-up details, only ever handled as text.
    const reply = {
      url: "https://alice:hunter2@bank-login.example/reset?email=alice%40example.invalid&token=abc123#step2",
      risk_level: "High risk",
      placeholder: false,
    };

    const saved = checkFrom(reply);

    expect(saved.link).toBe("bank-login.example");
    expect(JSON.stringify(saved)).not.toMatch(/alice|hunter2|reset|email|token|abc123|step2|https/);
  });

  it.each([
    ["no path", "https://www.example.org", "www.example.org"],
    ["a path", "https://parcel-redelivery.example/track/4821", SITE],
    ["a personal path", "https://bank-login.example/reset/alice", "bank-login.example"],
    ["a port and a query", "http://192.0.2.10:8080/login?next=/home", "192.0.2.10"],
  ])("keeps only the website name of a link with %s", (_name, link, kept) => {
    expect(linkToKeep(link)).toBe(kept);
  });

  it.each([
    ["a placeholder reply", { url: LINK, risk_level: "Safe", placeholder: true }],
    ["a couldn't check reply", {}],
    ["a level it doesn't know", { url: LINK, risk_level: "Unknown" }],
    ["a reply with no cleaned link", { risk_level: "Safe" }],
    ["a reply whose link isn't a link", { url: "not a link", risk_level: "Safe" }],
  ])("saves nothing for %s", (_name, reply) => {
    expect(checkFrom(reply)).toBeNull();
  });
});

describe("clearing my history (done when 2)", () => {
  it("removes every saved check, and they stay gone after a reload", () => {
    saveCheck(check(1));
    saveCheck(check(2));

    clearHistory();

    expect(loadHistory()).toEqual([]);
    // A reload reads storage afresh, as loadHistory does.
    expect(window.localStorage.getItem(HISTORY_KEY)).toBeNull();
  });
});

describe("nothing is sent to the backend (done when 3)", () => {
  it("only sends the pasted link to /scan, and saves the check in this browser", async () => {
    const user = userEvent.setup();
    const network = vi.spyOn(globalThis, "fetch").mockRejectedValue(new Error("no network in tests"));
    const scan = vi.fn(async () => ({ url: LINK, risk_level: "Suspicious", score: 0.4, reasons: [], placeholder: false }));
    render(<App check={scan} />);

    await user.type(screen.getByLabelText(LABEL), LINK);
    await user.click(screen.getByRole("button", { name: "Check" }));
    await screen.findByRole("heading", { name: "Suspicious" });

    expect(scan).toHaveBeenCalledTimes(1);
    expect(scan).toHaveBeenCalledWith(LINK);
    expect(network).not.toHaveBeenCalled();
    expect(loadHistory()).toEqual([expect.objectContaining({ link: SITE, result: "Suspicious" })]);
  });
});

describe("bad or missing storage", () => {
  it.each([
    ["not JSON", "{oops"],
    ["not a list", '{"link":"x"}'],
    ["entries it didn't save", '[{"link":"","result":"Safe","checkedAt":"2026-11-18"},{"result":"Maybe"},null]'],
  ])("shows no checks when storage holds %s", (_name, value) => {
    window.localStorage.setItem(HISTORY_KEY, value);

    expect(loadHistory()).toEqual([]);
  });

  it("keeps the good entries and skips the bad ones", () => {
    window.localStorage.setItem(HISTORY_KEY, JSON.stringify([check(2), { result: "Maybe" }, check(1)]));

    expect(loadHistory()).toEqual([check(2), check(1)]);
  });

  it("never throws when the browser refuses to store anything", () => {
    const refusing = {
      getItem: () => {
        throw new Error("blocked");
      },
      setItem: () => {
        throw new Error("blocked");
      },
      removeItem: () => {
        throw new Error("blocked");
      },
    };

    expect(loadHistory(refusing)).toEqual([]);
    expect(saveCheck(check(1), { storage: refusing })).toEqual([check(1)]);
    expect(() => clearHistory(refusing)).not.toThrow();
  });

  it("keeps every check on the page when the browser stops storing them", () => {
    const full = {
      getItem: () => JSON.stringify([check(1)]),
      setItem: () => {
        throw new Error("storage is full");
      },
      removeItem: () => {},
    };

    let showing = saveCheck(check(2), { storage: full });
    showing = saveCheck(check(3), { storage: full, current: showing });

    expect(showing).toEqual([check(3), check(2), check(1)]);
  });
});
