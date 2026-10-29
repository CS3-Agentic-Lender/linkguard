import { useState } from "react";

// Wording is copied word for word from the paste-a-link story.
export const LABEL = "Paste the link here";
export const CHECKING = "Checking…";
export const CANT_CHECK = "We couldn't check that link just now. Please try again.";

/**
 * The box and the Check button. `check(link)` sends the pasted text off and
 * resolves with the message to show. The link is only ever held as text: it is
 * never opened, fetched, previewed or shown as a clickable link.
 */
export default function PasteLinkForm({ check }) {
  const [link, setLink] = useState("");
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState("");

  async function handleSubmit(event) {
    event.preventDefault();
    // One request at a time. The button is marked aria-disabled rather than
    // disabled, so keyboard focus is never thrown off it while waiting.
    if (busy) return;
    setBusy(true);
    setStatus(CHECKING);
    try {
      setStatus(await check(link));
    } catch {
      setStatus(CANT_CHECK);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="check-form" onSubmit={handleSubmit} noValidate>
      <label htmlFor="link">{LABEL}</label>
      <div className="check-row">
        <input
          id="link"
          name="link"
          type="text"
          inputMode="url"
          autoComplete="off"
          autoCapitalize="off"
          spellCheck={false}
          aria-describedby="link-help"
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
