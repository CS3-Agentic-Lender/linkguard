import { useEffect, useId, useRef, useState } from "react";

import { EVERY_RESULT, LEVEL_ADVICE } from "./advice.js";
import { readableReasons } from "./ResultCard.jsx";

// Wording from the "copy the result and advice" story.
export const COPY_BUTTON = "Copy result";
export const COPIED = "Copied";
export const COPY_FAILED = "Couldn't copy. Select the text and copy it yourself.";
export const COPY_TEXT_LABEL = "Text to copy";
export const COPY_INTRO = "LinkGuard checked this link: ";
export const COPY_WARNING = "Do not open this link unless LinkGuard said it was safe.";
// Wording agreed on the "copied link stops being tappable" story.
export const COPY_DEFANGED = "The link is written like this on purpose, so it can't be opened by a tap.";
// How long the button says "Copied" before it goes back to "Copy result".
export const COPIED_MS = 3000;

/**
 * The link written so messaging apps don't turn it into something to tap: a leading
 * "http" becomes "hxxp" (so "https" becomes "hxxps") and every dot becomes "[.]".
 * Without a working scheme or a plain dot, apps no longer see a web address in it.
 * Only the copied text uses this; the result card still shows the link as pasted.
 */
export function defang(url) {
  return url.replace(/^http/i, "hxxp").replaceAll(".", "[.]");
}

/**
 * The plain text the copy button puts on the clipboard, in the story's order: the
 * link (defanged, with a line saying why), the risk level, the reasons one per line,
 * that level's advice, then the warning. `level` is the result card's class
 * ("safe", "suspicious" or "high").
 */
export function copyText(reply, level) {
  const reasons = level === "safe" ? [] : readableReasons(reply.reasons);
  const advice = [...LEVEL_ADVICE[level], ...EVERY_RESULT];
  return [
    `${COPY_INTRO}${defang(reply.url ?? "")}`,
    COPY_DEFANGED,
    reply.risk_level,
    ...reasons,
    ...advice,
    COPY_WARNING,
  ].join("\n");
}

/**
 * The "Copy result" button, straight under the result card.
 *
 * It sits outside the result's live region: that region is a role="status", which
 * screen readers treat as atomic, so a label change inside it would read the whole
 * result out again. Instead it has its own small polite live area, which says only
 * "Copied" or the failure message. If the browser has no clipboard or refuses, the full text
 * is shown in a read-only box so it can be selected and copied by hand.
 */
export default function CopyResult({ text }) {
  const [state, setState] = useState("idle");
  const timer = useRef(null);
  const boxId = useId();
  useEffect(() => () => clearTimeout(timer.current), []);

  async function copy() {
    clearTimeout(timer.current);
    try {
      if (!navigator.clipboard?.writeText) {
        throw new Error("No clipboard");
      }
      await navigator.clipboard.writeText(text);
      setState("copied");
      timer.current = setTimeout(() => setState("idle"), COPIED_MS);
    } catch {
      setState("failed");
    }
  }

  const message = { idle: "", copied: COPIED, failed: COPY_FAILED }[state];

  return (
    <div className="copy-result">
      <button type="button" className="copy-result__button" onClick={copy}>
        {state === "copied" ? COPIED : COPY_BUTTON}
      </button>
      <p
        aria-live="polite"
        className={state === "failed" ? "copy-result__message copy-result__message--error" : "visually-hidden"}
      >
        {message}
      </p>
      {state === "failed" && (
        <>
          <label htmlFor={boxId} className="copy-result__label">
            {COPY_TEXT_LABEL}
          </label>
          <textarea id={boxId} className="copy-result__text" readOnly rows={8} value={text} />
        </>
      )}
    </div>
  );
}
