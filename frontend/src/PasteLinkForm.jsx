import { useState } from "react";

import ResultCard from "./ResultCard.jsx";
import { LinkError } from "./scan.js";

// Wording is copied word for word from the paste-a-link story.
export const LABEL = "Paste the link here";
export const CHECKING = "Checking…";

/**
 * The box, the Check button and the result card. `check(link)` sends the
 * pasted text off and resolves with the /scan reply for the card, or rejects
 * with a LinkError saying what's wrong with the pasted text. The link is only ever held as text: it is never
 * opened, fetched, previewed or shown as a clickable link.
 */
export default function PasteLinkForm({ check }) {
  const [link, setLink] = useState("");
  const [busy, setBusy] = useState(false);
  // The /scan reply the card shows, or null before the first check.
  const [reply, setReply] = useState(null);
  const [error, setError] = useState("");

  async function handleSubmit(event) {
    event.preventDefault();
    // One request at a time. The button is marked aria-disabled rather than
    // disabled, so keyboard focus is never thrown off it while waiting.
    if (busy) return;
    setBusy(true);
    setError("");
    setReply(null);
    try {
      setReply(await check(link));
    } catch (failure) {
      if (failure instanceof LinkError) {
        // The pasted text stays in the box, so the user can fix it.
        setError(failure.message);
      } else {
        // A reply with no level: the card shows its "couldn't check" message.
        setReply({});
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="check-form" onSubmit={handleSubmit} noValidate>
      <label htmlFor="link">{LABEL}</label>
      {/* Read out as soon as it appears, and tied to the box so it is read again on focus. */}
      {error && (
        <p id="link-error" className="field-error" role="alert">
          <svg aria-hidden="true" focusable="false" viewBox="0 0 24 24" width="20" height="20">
            <circle cx="12" cy="12" r="10" fill="none" stroke="currentColor" strokeWidth="2" />
            <path d="M12 7v6M12 16.5v.5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
          </svg>
          <span>{error}</span>
        </p>
      )}
      <div className="check-row">
        <input
          id="link"
          name="link"
          type="text"
          inputMode="url"
          autoComplete="off"
          autoCapitalize="off"
          spellCheck={false}
          aria-invalid={error ? true : undefined}
          aria-describedby={error ? "link-error link-help" : "link-help"}
          value={link}
          onChange={(event) => setLink(event.target.value)}
        />
        <button type="submit" aria-disabled={busy}>
          Check
        </button>
      </div>
      <p id="link-help" className="help">
        Press Enter or select Check.
      </p>
      {/* Always in the page, so screen readers pick up each new result without focus moving. */}
      <div className="status" role="status" aria-live="polite">
        {busy ? CHECKING : reply && <ResultCard reply={reply} />}
      </div>
    </form>
  );
}
