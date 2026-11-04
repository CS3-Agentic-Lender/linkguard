/**
 * One chart: a heading, a one-line takeaway, horizontal bars and a table of the
 * same numbers. Drawn with plain elements and CSS, as docs/adr/0003-chart-drawing.md
 * decides: no chart library.
 *
 * The bars carry their group name and value as real text, so nothing depends on
 * colour or hovering. The bars are hidden from screen readers, which read the table
 * instead, so nothing is announced twice. Nothing in a chart is interactive.
 */

const PERCENT = new Intl.NumberFormat("en-IE", { maximumFractionDigits: 1 });
const COUNT = new Intl.NumberFormat("en-IE");

// The summary file rounds to one decimal, so a small but real share can read 0.0.
export function formatShare(value, count) {
  if (value === 0 && count > 0) return "under 0.1%";
  return `${PERCENT.format(value)}%`;
}

export function formatCount(count, total) {
  return `${COUNT.format(count)} of ${COUNT.format(total)}`;
}

// The table's caption keeps the chart's title, so each table has its own name when a
// screen reader lists tables, and adds what is compared, so it isn't just the heading
// again: "Links that use HTTPS, phishing compared with legitimate".
export function captionFor(chart) {
  const groups = chart.groups.map((group) => group.label.toLowerCase()).join(" compared with ");
  return `${chart.title}, ${groups}`;
}

// A class name per group, so each group keeps its own bar colour on every chart.
// Only Phishing and Legitimate have colours; any other label gets the neutral bar.
function groupClass(label) {
  return `bar-fill bar-fill--${label.toLowerCase().replace(/[^a-z]+/g, "-")}`;
}

export default function BarChart({ chart }) {
  const titleId = `chart-${chart.id}-title`;
  const takeawayId = `chart-${chart.id}-takeaway`;

  return (
    <figure className="chart" aria-labelledby={titleId} aria-describedby={takeawayId}>
      <h3 id={titleId} className="chart-title">
        {chart.title}
      </h3>
      <p id={takeawayId} className="chart-takeaway">
        {chart.takeaway}
      </p>

      <div className="bars" aria-hidden="true" data-testid="bars">
        {chart.groups.map((group) => (
          <div className="bar-row" key={group.label}>
            <span className="bar-label">{group.label}</span>
            <span className="bar-value">{formatShare(group.value, group.count)}</span>
            <span className="bar-track">
              <span className={groupClass(group.label)} style={{ inlineSize: `${group.value}%` }} />
            </span>
          </div>
        ))}
      </div>

      {/* A table ignores the width and clipping that hide it, so a div hides it instead. */}
      <div className="visually-hidden">
        <table>
          {/* Worded differently from the heading, so a screen reader doesn't just repeat it. */}
          <caption>{captionFor(chart)}</caption>
          <thead>
            <tr>
              <th scope="col">Group</th>
              <th scope="col">Share</th>
              <th scope="col">Links</th>
            </tr>
          </thead>
          <tbody>
            {chart.groups.map((group) => (
              <tr key={group.label}>
                <th scope="row">{group.label}</th>
                <td>{formatShare(group.value, group.count)}</td>
                <td>{formatCount(group.count, group.total)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </figure>
  );
}
