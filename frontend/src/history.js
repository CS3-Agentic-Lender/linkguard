// The last few checks, kept in this browser only. Nothing here is ever sent to
// the backend or saved anywhere else, and no personal details are kept: each
// check is just when it was made, the link's website name as text and its result.

export const HISTORY_KEY = "linkguard-history";
export const MAX_CHECKS = 5;

// The three result words /scan can send. Anything else in storage is ignored.
const RESULTS = new Set(["Safe", "Suspicious", "High risk"]);

function browserStorage() {
  try {
    return typeof window === "undefined" ? null : window.localStorage;
  } catch {
    // Some browsers refuse storage altogether, for example with cookies blocked.
    return null;
  }
}

function isCheck(entry) {
  return (
    entry !== null &&
    typeof entry === "object" &&
    typeof entry.link === "string" &&
    entry.link.trim() !== "" &&
    RESULTS.has(entry.result) &&
    typeof entry.checkedAt === "string" &&
    !Number.isNaN(Date.parse(entry.checkedAt))
  );
}

/**
 * The saved checks, newest first, at most MAX_CHECKS. Anything in storage that
 * isn't a check we saved (edited by hand, from an older version, or not JSON at
 * all) is skipped, so a bad entry never breaks the page.
 */
export function loadHistory(storage = browserStorage()) {
  try {
    const saved = JSON.parse(storage?.getItem(HISTORY_KEY) ?? "[]");
    return Array.isArray(saved) ? saved.filter(isCheck).slice(0, MAX_CHECKS) : [];
  } catch {
    return [];
  }
}

/**
 * The part of a cleaned link that is safe to keep: only its website name, as the
 * Product Owner decided on 21 Nov. Everything else can carry personal details, so
 * it is dropped before saving: a user name or password before the website name,
 * the path (such as /reset/alice), the query string (such as ?email=... or
 * ?token=...) and the part after #. Parsing the text with URL never opens or
 * looks up the link. Returns null for text that isn't a link with a website name.
 */
export function linkToKeep(link) {
  try {
    return new URL(link).hostname || null;
  } catch {
    return null;
  }
}

/**
 * The check to save for a /scan reply, or null when there is nothing to save:
 * a placeholder, a "couldn't check" reply or one with no cleaned link. Only the
 * link's website name is kept (see linkToKeep).
 */
export function checkFrom(reply, now = new Date()) {
  if (reply?.placeholder === true || !RESULTS.has(reply?.risk_level)) {
    return null;
  }
  const link = typeof reply.url === "string" ? linkToKeep(reply.url.trim()) : null;
  if (!link) {
    return null;
  }
  return { checkedAt: now.toISOString(), link, result: reply.risk_level };
}

/**
 * Saves a check in front of the others and keeps only the newest MAX_CHECKS.
 * Returns the list to show. `current` is the list already showing, so a check
 * the browser refused to store is not lost from the page by the next one; it
 * defaults to what is saved. If the browser won't store anything, the list is
 * still returned, so the checks show until the page is closed.
 */
export function saveCheck(check, { storage = browserStorage(), current = loadHistory(storage) } = {}) {
  const checks = [check, ...current].slice(0, MAX_CHECKS);
  try {
    storage?.setItem(HISTORY_KEY, JSON.stringify(checks));
  } catch {
    // Storage is full or switched off. Nothing else to do.
  }
  return checks;
}

/** Removes every saved check from this browser. */
export function clearHistory(storage = browserStorage()) {
  try {
    storage?.removeItem(HISTORY_KEY);
  } catch {
    // Storage is switched off, so there is nothing saved to remove.
  }
}
