---
status: accepted
---

# Draw the phishing charts as plain React bars, with no chart library

The phishing charts page compares phishing links with legitimate links, a few figures at a time, such as the share of each class that uses HTTPS. The frontend is React 19 built with Vite (see `0001-frontend-test-runner.md`), and AGENTS.md says a new library needs a team decision recorded here. We draw every chart as **plain horizontal bars built from our own React components and CSS**, with no chart library. Each bar carries its label and value as real text, and each chart comes with a table of the same numbers that a screen reader reads out.

Proposed by Nikoloz on 3 November 2026 (Sprint 2) and accepted the same day with the agreement of Ibrahima (Product Owner) and Nic, recorded below.

## What the charts have to do

From the chart stories and the brief:

- Each chart compares **two groups** (phishing and legitimate) on one measure, and the page shows at least three such charts. The numbers come from a small summary file of counts and percentages, so there are only a handful of values per chart, and they never change while the page is open.
- Phishing and legitimate are told apart by **text labels on the chart**, not by colour alone, and chart colours have at least **3:1 contrast** against the background.
- Each chart has a one-line takeaway and a **text alternative** (a short description or a table of the numbers) that a screen reader reads out.
- Our users include older and less confident people, so text is at least 16px, nothing needs hovering to be read, and the page works on a phone.
- Tests run in jsdom with Vitest and React Testing Library (`0001-frontend-test-runner.md`). A check that "every chart has its takeaway and text alternative" has to be a normal component test.

## Decision

Build one small, reusable `BarChart` component in `frontend/src/` and draw every chart with it.

### How a chart is built

```jsx
<figure aria-labelledby="https-title" aria-describedby="https-takeaway">
  <h2 id="https-title">Links that use HTTPS</h2>
  <p id="https-takeaway">{takeaway}</p>

  {/* The picture. Hidden from screen readers, which read the table instead. */}
  <div className="bar-chart" aria-hidden="true">
    <div className="bar-row">
      <span className="bar-label">Phishing</span>
      <span className="bar-track"><span className="bar-fill" style={{ inlineSize: "49.1%" }} /></span>
      <span className="bar-value">49.1%</span>
    </div>
    <div className="bar-row">
      <span className="bar-label">Legitimate</span>
      ...
    </div>
  </div>

  {/* The text alternative: the same numbers as a real table. */}
  <table>
    <caption>Links that use HTTPS, phishing compared with legitimate</caption>
    <thead><tr><th scope="col">Group</th><th scope="col">Share</th><th scope="col">Links</th></tr></thead>
    <tbody>
      <tr><th scope="row">Phishing</th><td>49.1%</td><td>…</td></tr>
      <tr><th scope="row">Legitimate</th><td>100%</td><td>…</td></tr>
    </tbody>
  </table>
</figure>
```

The markup above shows the structure, not final names or wording. The charts story decides those.

- **Visible labels on bars.** Every bar row shows its group name ("Phishing", "Legitimate") and its value as ordinary text next to the bar. Nothing is only in a tooltip or a legend, so the chart reads the same without colour, without a mouse, and when zoomed. Colour is a second cue, never the only one.
- **Bar length.** The bar fill's width is the value as a percentage of the chart's scale, set with an inline `inline-size` style. Horizontal bars are used because group names stay readable on a narrow phone screen and the value text sits at the end of the bar.
- **Screen readers.** The picture is `aria-hidden`, and a real `<table>` with a `<caption>` and `<th scope>` headers holds the same numbers. A screen reader announces the chart's heading and takeaway, then reads the table cell by cell with its headers, which is the "table of the numbers" text alternative the chart story asks for. Whether the table is also shown on screen, or hidden visually with a standard visually-hidden class, is a design choice for the charts story's wireframe. The table stays in the page either way, so it is always read out.
- **Keyboard.** The charts are not interactive: no hover, no tooltips, no clicking. There is nothing to focus, so keyboard users lose nothing, and the page's tab order stays the paste-a-link form and links only.
- **Colours and type.** Bar colours, text sizes and spacing come from `frontend/src/styles/tokens.css`. Any new bar colour is added there, and a pair for it (the bar colour against the surface it sits on, minimum 3:1) is added to `PAIRS` in `frontend/scripts/check-contrast.mjs`. `npm run contrast` only checks the pairs listed there, so a colour without a pair is not checked.
- **Responsive.** Bars are flexbox and percentage widths, so they fit any screen width with no resize listener or measuring code.
- **No links.** The component only renders text from the summary file. It never turns a value into a link, so no dataset URL can become clickable.

### What the component takes

The component draws whatever the summary file gives it and works nothing out itself, apart from the bar width. Per chart it needs: a title, a one-line takeaway, a unit (for example percent), and for each group a label and a value, plus the count behind it if the table shows counts. The exact shape of the summary file belongs to the story that prepares the chart numbers and takeaways. This list is only what the drawing side needs, so the two can be matched when that file is made.

### Testing

Because the charts are ordinary DOM elements, the charts story tests them with React Testing Library like any other component: every chart has a heading, a takeaway and a table; the table has a row per group with the right numbers; group names appear as text; and nothing in a chart is a link. No canvas mock, no `ResizeObserver` stub and no snapshot of library SVG is needed.

## Considered options

| | Plain React bars (chosen) | Recharts 3 | Chart.js 4 with react-chartjs-2 | Plotly (react-plotly.js) |
|---|---|---|---|---|
| New dependencies | None | Recharts plus about 11 runtime packages (Redux Toolkit, Immer, victory-vendor and others) | 2 packages | 2 packages, Plotly itself several MB |
| Draws to | HTML elements | SVG | `<canvas>` | SVG and WebGL |
| Labels on bars | Ordinary text | `LabelList`, configured per bar | A plugin (`chartjs-plugin-datalabels`), so a third package | Built-in text on bars |
| Screen reader | Real table we write; picture hidden | `accessibilityLayer` adds keyboard focus to tooltips, but the table is still ours to write | Canvas is a picture with no text inside, so the table is still ours to write | Mostly hidden SVG; the table is still ours to write |
| jsdom tests | Normal component tests | `ResponsiveContainer` measures the page, which jsdom can't, so tests need size stubs | jsdom has no canvas, so tests need a canvas mock and can't see the bars | Heavy to load in tests; needs browser APIs jsdom lacks |
| Fits two-bar comparisons | Yes, it is exactly that | Yes, with more than we need | Yes, with more than we need | Yes, with far more than we need |

- **Recharts** (turned down for now): the most natural React chart library, SVG-based and with React 19 support. For two bars a chart it adds about a dozen runtime packages to a frontend that today has only React, and its responsive container needs layout measurement that jsdom doesn't do, so our tests would need stubs. The labels and the screen-reader table would still be work we do ourselves. It is the first option to reconsider if a later chart needs axes, lines or many points (see Consequences).
- **Chart.js with react-chartjs-2** (turned down): small and popular, but it draws on a `<canvas>`, so the bars and their labels are pixels, not text. A screen reader gets nothing from the canvas, bar labels need an extra plugin, and jsdom cannot draw a canvas, so tests can't check what is shown.
- **Plotly** (turned down): powerful for scientific and interactive charts, but several megabytes of JavaScript for a handful of bars, and its hover and zoom tools are the wrong interaction for our users.
- **Hand-drawn SVG** (turned down): accessible and dependency-free like the chosen option, but we would have to wrap and position text ourselves, and SVG text does not reflow on a narrow screen or with large text the way HTML does.

## Accessibility summary

| Need | How this decision meets it |
|---|---|
| Labels on bars | Group name and value are text on every bar row |
| Not colour alone | Text labels carry the meaning; colour is a second cue |
| 3:1 contrast for bar colours | Colours are tokens, each with a 3:1 pair in `check-contrast.mjs`, checked by `npm run contrast` |
| Screen reader alternative | A `<table>` with caption and headers holds the same numbers; the picture is `aria-hidden` |
| Keyboard | Nothing interactive, so nothing to reach; no hover-only content |
| Zoom and small screens | HTML text reflows; bars are percentage widths |
| No clickable dataset links | The component renders text only |

## Consequences

- No package is added to `frontend/package.json` for charts, so there is nothing new to update or audit.
- We write and own about one component and a short stylesheet. Axis lines, gridlines and animation are not provided; the phishing charts don't need them.
- The charts story, not this decision, picks the charts, their wording, their colours from the tokens, and whether the table is visible.
- **When to revisit.** If a later story needs a chart that is not a simple bar comparison (a line over time, a scatter plot, a chart with many categories and an axis), write a new decision record that supersedes this one. Recharts is the first option to check then.

## Team agreement

Accepted on 3 November 2026.

| Who | Role this sprint | Where and when |
|---|---|---|
| Nikoloz | Proposed it | This record and the #dev thread in Slack, 3 Nov |
| Ibrahima | Product Owner; owns the chart numbers | Approving review on the pull request for this record, 3 Nov. Confirmed the chart summary file already gives each chart a title, takeaway and unit, and each group a label, value, count and total, so the file and the component match. |
| Nic | Developer | Approving review on the pull request for this record, 3 Nov. Asked for the 49.1% example figure and the contrast-pair note, both made. |

Solomon (Scrum Master) had not replied when this was accepted. If he objects, the decision is reopened with a new record.
