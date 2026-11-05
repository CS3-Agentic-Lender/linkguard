import summary from "../../ml/reports/chart_summary.json";

import BarChart from "./BarChart.jsx";

/**
 * The phishing charts: every chart in the summary file made by the chart numbers
 * script (ml/reports/chart_summary.json), each comparing phishing with legitimate
 * links. The page only shows what the file says and works nothing out itself.
 *
 * The file holds counts, percentages and sentences only, never a link from the
 * dataset, and everything is shown as plain text, so nothing here can be clicked.
 */
export default function PhishingCharts({ data = summary }) {
  return (
    <section className="charts" aria-labelledby="charts-heading">
      <h2 id="charts-heading">Warning signs in phishing links</h2>
      <p className="charts-intro">
        These charts compare phishing links with legitimate links from a public dataset
        of {data.totals.phishing.toLocaleString("en-IE")} phishing and{" "}
        {data.totals.legitimate.toLocaleString("en-IE")} legitimate links.
      </p>
      <p className="dataset-note">
        <strong>About this data:</strong> {data.dataset_note}
      </p>
      {data.charts.map((chart) => (
        <BarChart key={chart.id} chart={chart} />
      ))}
      <p className="source">{data.source}</p>
    </section>
  );
}
