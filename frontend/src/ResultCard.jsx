import { useId } from "react";

import { CANT_CHECK, PLACEHOLDER } from "./scan.js";

// Wording is copied word for word from the result card story.
export const SAFE_CAVEAT =
  "No warning signs found. Still don't enter passwords or bank details from a message you weren't expecting.";

// Introduces the reasons on a Suspicious or High risk result, and names the list for screen readers.
export const REASONS_HEADING = "Why this link looks risky";
export const MAX_REASONS = 3;

// Icon paths from the Lucide set, as named in tokens.css for each risk level.
const ICONS = {
  "shield-check": (
    <>
      <path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z" />
      <path d="m9 12 2 2 4-4" />
    </>
  ),
  "triangle-alert": (
    <>
      <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3" />
      <path d="M12 9v4" />
      <path d="M12 17h.01" />
    </>
  ),
  "octagon-alert": (
    <>
      <path d="M12 16h.01" />
      <path d="M12 8v4" />
      <path d="M15.312 2a2 2 0 0 1 1.414.586l4.688 4.688A2 2 0 0 1 22 8.688v6.624a2 2 0 0 1-.586 1.414l-4.688 4.688a2 2 0 0 1-1.414.586H8.688a2 2 0 0 1-1.414-.586l-4.688-4.688A2 2 0 0 1 2 15.312V8.688a2 2 0 0 1 .586-1.414l4.688-4.688A2 2 0 0 1 8.688 2z" />
    </>
  ),
  info: (
    <>
      <circle cx="12" cy="12" r="10" />
      <path d="M12 16v-4" />
      <path d="M12 8h.01" />
    </>
  ),
  "circle-x": (
    <>
      <circle cx="12" cy="12" r="10" />
      <path d="m15 9-6 6" />
      <path d="m9 9 6 6" />
    </>
  ),
};

// The three levels /scan can send, keyed by the backend's exact wording.
const LEVELS = {
  Safe: { level: "safe", icon: "shield-check" },
  Suspicious: { level: "suspicious", icon: "triangle-alert" },
  "High risk": { level: "high", icon: "octagon-alert" },
};

function Icon({ name }) {
  return (
    <svg
      data-icon={name}
      aria-hidden="true"
      focusable="false"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {ICONS[name]}
    </svg>
  );
}

/**
 * The reply's reasons that can be shown: plain, non-blank sentences, in the
 * reply's order, at most MAX_REASONS. Anything else in the list is skipped.
 */
function readableReasons(reasons) {
  if (!Array.isArray(reasons)) {
    return [];
  }
  return reasons.filter((reason) => typeof reason === "string" && reason.trim() !== "").slice(0, MAX_REASONS);
}

/**
 * Up to three reasons as a list, named by its heading. The heading sits one
 * level below the risk level, so screen reader users can jump to it. The card
 * sits in the form's live region, so screen readers read the reasons with the result.
 */
function Reasons({ reasons }) {
  const headingId = useId();
  return (
    <div className="result-card__reasons">
      <h3 id={headingId} className="result-card__reasons-heading">
        {REASONS_HEADING}
      </h3>
      <ul aria-labelledby={headingId}>
        {reasons.map((reason, index) => (
          // Two reasons can be the same sentence, so the position keeps each key unique.
          <li key={`${index}-${reason}`}>{reason}</li>
        ))}
      </ul>
    </div>
  );
}

/**
 * Shows one /scan reply as a risk level: its word, icon and colour, never the
 * colour alone. A placeholder reply shows the placeholder message and no level.
 * Anything else, including no reply, shows the failure message rather than a
 * guess. The checked link is shown as plain text only, never as a link.
 * Suspicious and High risk results show the reply's reasons under the level.
 * A Safe result never shows reasons.
 */
export default function ResultCard({ reply }) {
  if (reply?.placeholder === true) {
    return (
      <div className="result-card result-card--notice" data-level="placeholder">
        <p className="result-card__notice">
          <Icon name="info" />
          <span>{PLACEHOLDER}</span>
        </p>
      </div>
    );
  }

  const match = Object.hasOwn(LEVELS, reply?.risk_level ?? "") ? LEVELS[reply.risk_level] : null;
  if (!match) {
    return (
      <div className="result-card result-card--notice" data-level="error">
        <p className="result-card__notice">
          <Icon name="circle-x" />
          <span>{CANT_CHECK}</span>
        </p>
      </div>
    );
  }

  const reasons = match.level === "safe" ? [] : readableReasons(reply.reasons);

  return (
    <div className="result-card" data-level={match.level}>
      <h2 className="result-card__level">
        <Icon name={match.icon} />
        <span>{reply.risk_level}</span>
      </h2>
      {reasons.length > 0 && <Reasons reasons={reasons} />}
      {reply.url && (
        <p className="result-card__link">
          Link checked: <span>{reply.url}</span>
        </p>
      )}
      {match.level === "safe" && <p className="result-card__caveat">{SAFE_CAVEAT}</p>}
    </div>
  );
}
