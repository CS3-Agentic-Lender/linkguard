import { useId, useState } from "react";

import { Icon, LEVELS } from "./ResultCard.jsx";

// Wording agreed by the Product Owner for the "explain each risk level" story.
export const GUIDE_BUTTON = "What do the risk levels mean?";
export const YOUR_RESULT = "Your result";
export const BEST_GUESS =
  "These levels are LinkGuard's best guess from the link's website name, not a guarantee.";

// One plain sentence per level, in the order a reader meets them, from least to most risky.
export const LEVEL_MEANINGS = [
  {
    name: "Safe",
    meaning: "No warning signs were found in this link. Still be careful with links you weren't expecting.",
  },
  { name: "Suspicious", meaning: "Some warning signs were found. Don't open it unless you're sure it's real." },
  { name: "High risk", meaning: "This link looks like phishing. Don't open it." },
];

/**
 * A button under the result card that shows and hides one plain sentence for
 * each risk level. `level` is the result card's class ("safe", "suspicious" or
 * "high"); that level is marked with its icon, bold text and "Your result", so
 * the mark never depends on colour. Anything else shows nothing.
 *
 * It sits outside the result's live region, so opening it doesn't make screen
 * readers read the result again. The button says whether it is open
 * (aria-expanded), and the list starts closed.
 */
export default function RiskLevelGuide({ level }) {
  const [open, setOpen] = useState(false);
  const panelId = useId();
  const current = Object.values(LEVELS).find((entry) => entry.level === level);
  if (!current) {
    return null;
  }

  return (
    <div className="level-guide">
      <button
        type="button"
        className="level-guide__toggle"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((wasOpen) => !wasOpen)}
      >
        {GUIDE_BUTTON}
      </button>
      <div id={panelId} className="level-guide__panel" hidden={!open}>
        <ul className="level-guide__list">
          {LEVEL_MEANINGS.map(({ name, meaning }) => {
            const entry = LEVELS[name];
            const isCurrent = entry.level === level;
            return (
              <li
                key={name}
                className="level-guide__item"
                data-level={entry.level}
                aria-current={isCurrent ? "true" : undefined}
              >
                <Icon name={entry.icon} />
                <span>
                  <strong>{name}:</strong> {meaning}
                  {isCurrent && <span className="level-guide__current">{YOUR_RESULT}</span>}
                </span>
              </li>
            );
          })}
        </ul>
        <p className="level-guide__note">{BEST_GUESS}</p>
      </div>
    </div>
  );
}
