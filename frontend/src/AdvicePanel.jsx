import { useId } from "react";

import { ALREADY_CLICKED, ALREADY_CLICKED_HEADING, EVERY_RESULT, LEVEL_ADVICE } from "./advice.js";

export const ADVICE_HEADING = "What to do now";

/**
 * The advice under a result: that level's advice, then the lines every result
 * gets, then what to do if you already clicked. `level` is the result card's
 * class ("safe", "suspicious" or "high"); anything else shows nothing, so a
 * failed check or a placeholder never gets advice that doesn't fit it.
 *
 * It sits outside the result's live region, so screen readers read the result
 * straight away and reach the advice by heading, not all at once.
 */
export default function AdvicePanel({ level }) {
  const nowId = useId();
  const clickedId = useId();
  if (!Object.hasOwn(LEVEL_ADVICE, level ?? "")) {
    return null;
  }
  const lines = [...LEVEL_ADVICE[level], ...EVERY_RESULT];

  return (
    <section className="advice" data-level={level} aria-labelledby={nowId}>
      <h2 id={nowId} className="advice__heading">
        {ADVICE_HEADING}
      </h2>
      <ul>
        {lines.map((line) => (
          <li key={line}>{line}</li>
        ))}
      </ul>
      <h3 id={clickedId} className="advice__subheading">
        {ALREADY_CLICKED_HEADING}
      </h3>
      <ul aria-labelledby={clickedId}>
        {ALREADY_CLICKED.map(({ situation, line }) => (
          <li key={situation}>
            <strong>{situation}:</strong> {line}
          </li>
        ))}
      </ul>
    </section>
  );
}
