import { useRef } from "react";

import { RiskIcon } from "./ResultCard.jsx";

// Wording is copied word for word from the history story.
export const HISTORY_HEADING = "Your last 5 checks";
export const CLEAR_TEXT = "Clear my history";
export const COLUMNS = ["Date and time", "Link", "Result"];
export const NO_CHECKS = "You haven't checked any links yet";

// Irish local time, for example "8 Oct 2026, 14:05", whatever time zone the device is set to.
const IRISH_TIME = new Intl.DateTimeFormat("en-IE", {
  timeZone: "Europe/Dublin",
  day: "numeric",
  month: "short",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
});

export function irishTime(iso) {
  return IRISH_TIME.format(new Date(iso));
}

const LEVEL_CLASS = { Safe: "safe", Suspicious: "suspicious", "High risk": "high" };

/**
 * The checks saved in this browser, newest first, with a button that clears
 * them. Each link is plain text, never a link, so it can't be opened by
 * accident. Each result shows its word and icon, never colour alone. With no
 * saved checks, a short message shows in place of an empty table.
 * `checks` is the list from history.js, already newest first.
 */
export default function HistoryTable({ checks, onClear }) {
  const heading = useRef(null);

  function clear() {
    onClear();
    // The button goes once the history is empty, so focus moves to the heading
    // rather than being lost.
    heading.current?.focus();
  }

  return (
    <section className="history" aria-labelledby="history-heading">
      <h2 id="history-heading" ref={heading} tabIndex={-1}>
        {HISTORY_HEADING}
      </h2>
      {checks.length === 0 ? (
        <p className="history__empty">{NO_CHECKS}</p>
      ) : (
        <>
          {/* The explicit roles keep this a table for screen readers when a phone
              screen stacks each row into lines (see app.css). */}
          <table className="history__table" role="table">
            <thead role="rowgroup">
              <tr role="row">
                {COLUMNS.map((column) => (
                  <th key={column} scope="col" role="columnheader">
                    {column}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody role="rowgroup">
              {checks.map((check, index) => (
                // Two checks can share a time and a link, so the position keeps each key unique.
                <tr key={`${index}-${check.checkedAt}`} role="row">
                  <td role="cell" data-label={COLUMNS[0]}>
                    <time dateTime={check.checkedAt}>{irishTime(check.checkedAt)}</time>
                  </td>
                  <td role="cell" data-label={COLUMNS[1]} className="history__link">
                    {check.link}
                  </td>
                  <td role="cell" data-label={COLUMNS[2]}>
                    <span className="history__result" data-level={LEVEL_CLASS[check.result]}>
                      <RiskIcon riskLevel={check.result} />
                      <span>{check.result}</span>
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <button type="button" className="secondary-button" onClick={clear}>
            {CLEAR_TEXT}
          </button>
        </>
      )}
    </section>
  );
}
