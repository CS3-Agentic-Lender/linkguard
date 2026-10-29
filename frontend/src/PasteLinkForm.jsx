import { useState } from "react";

import { LinkError } from "./scan.js";

// Wording is copied word for word from the paste-a-link story.
export const LABEL = "Paste the link here";
export const CHECKING = "Checking…";
export const CANT_CHECK = "We couldn't check that link just now. Please try again.";

/**
 * The box and the Check button. `check(link)` sends the pasted text off and
 * resolves with the message to show, or rejects with a LinkError saying what's
 * wrong with the pasted text. The link is only ever held as text: it is never
 * opened, fetched, previewed or shown as a clickable link.
 */
export default function PasteLinkForm({ check }) {
  const [link, setLink] = useState("");
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");

  async function handleSubmit(event) {
    event.preventDefault();
    // One request at a time. The button is marked aria-disabled rather than
    // disabled, so keyboard focus is never thrown off it while waiting.
    if (busy) return;
    setBusy(true);
    setError("");
    setStatus(CHECKING);
    try {
      setStatus(await check(link));
    } catch (failure) {
      if (failure instanceof LinkError) {
        // The pasted text stays in the box, so the user can fix it.
        setStatus("");
        setError(failure.message);
      } else {
        setStatus(CANT_CHECK);
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
      {/* Always in the page, so screen readers pick up each new message without focus moving. */}
      <p className="status" role="status" aria-live="polite">
        {status}
      </p>
    </form>
  );
}
