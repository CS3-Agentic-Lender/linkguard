import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import summary from "../../ml/reports/chart_summary.json";
import App from "./App.jsx";
import { captionFor, formatCount, formatShare } from "./BarChart.jsx";
import PhishingCharts from "./PhishingCharts.jsx";

// A small made-up summary in the same shape as ml/reports/chart_summary.json.
const MADE_UP = {
  source: "Made-up numbers for a test.",
  dataset_note: "Every legitimate link in this made-up data is a homepage.",
  totals: { phishing: 40, legitimate: 60 },
  charts: [
    {
      id: "first",
      title: "First made-up chart",
      takeaway: "First takeaway.",
      unit: "percent",
      groups: [
        { label: "Phishing", value: 25.0, count: 10, total: 40 },
        { label: "Legitimate", value: 50.0, count: 30, total: 60 },
      ],
    },
    {
      id: "tiny",
      title: "Chart with a tiny share",
      takeaway: "Second takeaway.",
      unit: "percent",
      groups: [
        { label: "Phishing", value: 12.5, count: 5, total: 40 },
        { label: "Legitimate", value: 0.0, count: 1, total: 60 },
      ],
    },
  ],
};

function charts() {
  return screen.getAllByRole("figure");
}

describe("phishing charts page, from the real summary file", () => {
  // Criterion 1: at least three charts, each comparing phishing with legitimate links.
  it("shows every chart in the summary file, at least three, each comparing the two groups", () => {
    render(<PhishingCharts />);

    expect(summary.charts.length).toBeGreaterThanOrEqual(3);
    expect(charts()).toHaveLength(summary.charts.length);
    for (const [index, chart] of charts().entries()) {
      expect(chart).toHaveAccessibleName(summary.charts[index].title);
      const rows = within(chart).getAllByRole("row");
      const groups = rows.slice(1).map((row) => within(row).getByRole("rowheader").textContent);
      expect(groups).toEqual(["Phishing", "Legitimate"]);
    }
  });

  // Criterion 2: every chart has its takeaway and a text alternative a screen reader reads.
  it("gives every chart its takeaway and a table of its numbers", () => {
    render(<PhishingCharts />);

    for (const [index, chart] of charts().entries()) {
      const expected = summary.charts[index];
      expect(chart).toHaveAccessibleDescription(expected.takeaway);
      expect(within(chart).getByText(expected.takeaway)).toBeVisible();

      const table = within(chart).getByRole("table", { name: captionFor(expected) });
      for (const group of expected.groups) {
        const row = within(table).getByRole("row", { name: new RegExp(`^${group.label}`) });
        expect(row).toHaveTextContent(formatShare(group.value, group.count));
        expect(row).toHaveTextContent(formatCount(group.count, group.total));
      }
    }
  });

  // Review follow-up: the caption must not just repeat the heading, but each table
  // still needs its own name, so screen-reader users can tell the tables apart.
  it("words each table caption differently from its heading, and gives every table its own name", () => {
    render(<PhishingCharts />);

    const captions = charts().map((chart, index) => {
      const title = summary.charts[index].title;
      const caption = within(chart).getByRole("table").querySelector("caption").textContent;
      expect(caption).toBe(`${title}, phishing compared with legitimate`);
      expect(within(chart).getAllByText(title)).toHaveLength(1);
      return caption;
    });
    expect(new Set(captions).size).toBe(captions.length);
  });

  it("hides the bars from screen readers, so the numbers are not read twice", () => {
    render(<PhishingCharts />);

    for (const bars of screen.getAllByTestId("bars")) {
      expect(bars).toHaveAttribute("aria-hidden", "true");
    }
  });

  // Criterion 3: a note that every legitimate link in the dataset is a homepage.
  it("says that the legitimate links in this dataset are all homepages", () => {
    render(<PhishingCharts />);

    expect(summary.dataset_note).toMatch(/every legitimate link .* homepage/i);
    expect(screen.getByText(summary.dataset_note)).toBeVisible();
  });

  // Criterion 4: groups told apart by text labels on the bars, not by colour alone.
  it("labels every bar with its group name and value as text", () => {
    render(<PhishingCharts />);

    for (const [index, bars] of screen.getAllByTestId("bars").entries()) {
      for (const group of summary.charts[index].groups) {
        expect(within(bars).getByText(group.label)).toBeInTheDocument();
        expect(within(bars).getByText(formatShare(group.value, group.count))).toBeInTheDocument();
      }
    }
  });

  // Criterion 5: nothing on the charts can be clicked, so no dataset link either.
  it("has no links, buttons or other controls", () => {
    const { container } = render(<PhishingCharts />);

    expect(screen.queryAllByRole("link")).toHaveLength(0);
    expect(screen.queryAllByRole("button")).toHaveLength(0);
    expect(container.querySelectorAll("a, button, input, [tabindex], [href]")).toHaveLength(0);
  });

  it("credits the dataset with the source line the licence asks for", () => {
    render(<PhishingCharts />);

    expect(screen.getByText(summary.source)).toBeVisible();
  });

  it("shows on the page after the paste-a-link form", () => {
    render(<App check={vi.fn()} />);

    const heading = screen.getByRole("heading", { level: 2, name: "Warning signs in phishing links" });
    const form = screen.getByRole("button", { name: "Check" });
    expect(form.compareDocumentPosition(heading) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });
});

describe("phishing charts page, from a made-up summary", () => {
  it("draws only what the file holds, in the file's order", () => {
    render(<PhishingCharts data={MADE_UP} />);

    expect(charts().map((chart) => chart.getAttribute("aria-labelledby"))).toEqual([
      "chart-first-title",
      "chart-tiny-title",
    ]);
    expect(screen.getByText(/40 phishing and 60 legitimate links/)).toBeVisible();
  });

  it("sizes each bar from its value", () => {
    render(<PhishingCharts data={MADE_UP} />);

    const [first] = screen.getAllByTestId("bars");
    const fills = first.querySelectorAll(".bar-fill");
    expect(fills[0]).toHaveStyle({ inlineSize: "25%" });
    expect(fills[1]).toHaveStyle({ inlineSize: "50%" });
  });

  it("gives Phishing and Legitimate bars their own class and any other group neither", () => {
    const data = {
      ...MADE_UP,
      charts: [
        {
          id: "odd",
          title: "Chart with an unknown group",
          takeaway: "Odd takeaway.",
          unit: "percent",
          groups: [
            { label: "Phishing", value: 10, count: 4, total: 40 },
            { label: "Legitimate", value: 20, count: 12, total: 60 },
            { label: "Unknown", value: 30, count: 3, total: 10 },
          ],
        },
      ],
    };
    render(<PhishingCharts data={data} />);

    const [phishing, legitimate, unknown] = screen.getByTestId("bars").querySelectorAll(".bar-fill");
    expect(phishing).toHaveClass("bar-fill--phishing");
    expect(phishing).not.toHaveClass("bar-fill--legitimate");
    expect(legitimate).toHaveClass("bar-fill--legitimate");
    expect(legitimate).not.toHaveClass("bar-fill--phishing");
    expect(unknown).not.toHaveClass("bar-fill--phishing");
    expect(unknown).not.toHaveClass("bar-fill--legitimate");
  });

  it("names a made-up chart's table from its title and the groups it compares", () => {
    render(<PhishingCharts data={MADE_UP} />);

    const first = screen.getByRole("figure", { name: "First made-up chart" });
    expect(
      within(first).getByRole("table", { name: "First made-up chart, phishing compared with legitimate" }),
    ).toBeInTheDocument();
  });

  it("shows a small share that rounds to 0.0 as under 0.1%, not as zero", () => {
    render(<PhishingCharts data={MADE_UP} />);

    const tiny = screen.getByRole("figure", { name: "Chart with a tiny share" });
    expect(within(tiny).getAllByText("under 0.1%")).toHaveLength(2);
    expect(within(tiny).queryByText("0%")).not.toBeInTheDocument();
  });
});

describe("number formatting", () => {
  it("formats shares with at most one decimal", () => {
    expect(formatShare(49.1, 49378)).toBe("49.1%");
    expect(formatShare(100.0, 134850)).toBe("100%");
    expect(formatShare(0.0, 0)).toBe("0%");
    expect(formatShare(0.0, 13)).toBe("under 0.1%");
  });

  it("formats counts with thousands separators", () => {
    expect(formatCount(49378, 100520)).toBe("49,378 of 100,520");
  });
});
