import { useId } from "react";

// The results files are read as text at build time. If one is missing, the glob
// is simply empty, and if one isn't valid JSON, parseFile gives null, so either
// way the page shows the "not available" message instead of failing.
const EVALUATION_FILES = import.meta.glob("../../ml/reports/evaluation_results.json", {
  eager: true,
  query: "?raw",
  import: "default",
});
const COMPARISON_FILES = import.meta.glob("../../ml/reports/cv_results.json", {
  eager: true,
  query: "?raw",
  import: "default",
});

/** The parsed JSON of a results file's text, or null if it's missing or unreadable. */
export function parseFile(text) {
  try {
    return typeof text === "string" ? JSON.parse(text) : null;
  } catch {
    return null;
  }
}

// The model the team chose and the app runs. It was picked by ROC-AUC, as agreed at
// sprint planning, and the Product Owner confirmed it on 9 November 2026 (ADR 0004
// and ml/reports/evaluation_report.md). It is a recorded decision, so it is named
// here, not worked out again from the cross-validation scores.
export const CHOSEN_MODEL = "Gradient boosting";

// Wording from the model performance story. The honesty note is word for word.
export const RESULTS_HEADING = "How well the model does";
export const NOT_AVAILABLE = "Model results aren't available yet.";
export const HONESTY_NOTE =
  "The scores come from PhiUSIIL only and are an upper bound on real-world performance, because the dataset's legitimate links are all bare homepages and the model uses hostname features only.";
export const RECALL_SENTENCE =
  "This is the number that matters most: a missed phishing link is the costly mistake, because someone may open it and trust it.";
export const BASELINE = "Baseline (most common class)";

const PERCENT = new Intl.NumberFormat("en-IE", { style: "percent", maximumFractionDigits: 1 });
const COUNT = new Intl.NumberFormat("en-IE");
const SCORE = new Intl.NumberFormat("en-IE", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const MEASURE = new Intl.NumberFormat("en-IE", { minimumFractionDigits: 3, maximumFractionDigits: 3 });

const isScore = (value) => typeof value === "number" && Number.isFinite(value) && value >= 0 && value <= 1;
const isCount = (value) => Number.isInteger(value) && value >= 0;

/**
 * The held-back test results from the evaluation script's file, or null when
 * the file is missing or doesn't hold what the page needs. A half-read file
 * never shows numbers.
 */
export function readEvaluation(file) {
  const test = file?.test;
  const matrix = file?.confusion_matrix;
  const labels = matrix?.labels;
  const counts = matrix?.counts;
  if (
    !test ||
    !["recall", "precision", "f1", "roc_auc"].every((key) => isScore(test[key])) ||
    !Array.isArray(labels) ||
    labels[0] !== "phishing" ||
    labels[1] !== "legitimate" ||
    matrix.rows !== "actual" ||
    matrix.columns !== "predicted" ||
    !Array.isArray(counts) ||
    counts.length !== 2 ||
    !counts.every((row) => Array.isArray(row) && row.length === 2 && row.every(isCount))
  ) {
    return null;
  }
  const [[caught, missed], [flagged, cleared]] = counts;
  return {
    recall: test.recall,
    precision: test.precision,
    f1: test.f1,
    rocAuc: test.roc_auc,
    caught,
    missed,
    flagged,
    cleared,
  };
}

const mean = (values) => values.reduce((sum, value) => sum + value, 0) / values.length;

/**
 * Each model's mean cross-validation scores from the training script's file, in
 * the file's order, or null when the file is missing or unreadable.
 */
export function readComparison(file) {
  const models = file?.models;
  if (!models || typeof models !== "object") {
    return null;
  }
  const rows = [];
  for (const [name, model] of Object.entries(models)) {
    const folds = model?.folds;
    if (!Array.isArray(folds) || folds.length === 0) {
      return null;
    }
    const scores = {};
    for (const key of ["recall", "precision", "f1", "roc_auc"]) {
      const values = folds.map((fold) => fold?.cv?.[key]);
      if (!values.every(isScore)) {
        return null;
      }
      scores[key] = mean(values);
    }
    rows.push({ name, ...scores });
  }
  return rows.length > 0 ? rows : null;
}

/**
 * Why the chosen model was chosen, in plain words, from its own row of the
 * comparison. It only says the model was best at ranking when the scores show it.
 * If another model caught more phishing links, it says so, because that is the
 * model the recall-first comparison picked, and the table would look odd otherwise.
 */
export function chosenReason(chosen, rows) {
  const others = rows.filter((row) => row !== chosen && row.name !== BASELINE);
  const rocAuc = MEASURE.format(chosen.roc_auc);
  const bestAtRanking = others.every((row) => chosen.roc_auc >= row.roc_auc);
  const reason = bestAtRanking
    ? `because it was best at ranking phishing links above safe ones (ROC-AUC ${rocAuc} in cross-validation), as the team agreed at sprint planning.`
    : `as the team agreed at sprint planning (ROC-AUC ${rocAuc} in cross-validation).`;
  const mostCaught = others.reduce((best, row) => (best && best.recall >= row.recall ? best : row), null);
  const recallNote =
    mostCaught && mostCaught.recall > chosen.recall
      ? ` ${mostCaught.name} caught a few more phishing links (phishing recall ${MEASURE.format(mostCaught.recall)}), and the recall-first comparison picked it, but it ranked them less well.`
      : "";
  return `${reason} The test scores above are this model's.${recallNote}`;
}


/**
 * One results table. `columns` are the column headings; each row has a heading
 * and one cell per remaining column. On a narrow screen app.css stacks each row
 * into labelled lines, so every cell carries its column name in `data-label`,
 * and the explicit roles keep it a table for screen readers when it is stacked.
 * The caption names the table.
 */
function ResultsTable({ caption, columns, rows }) {
  const captionId = useId();
  return (
    <table className="results-table" role="table" aria-labelledby={captionId}>
      <caption id={captionId}>{caption}</caption>
      <thead role="rowgroup">
        <tr role="row">
          {columns.map((column, index) =>
            column ? (
              <th key={column} scope="col" role="columnheader">
                {column}
              </th>
            ) : (
              <td key={`blank-${index}`} role="cell" />
            ),
          )}
        </tr>
      </thead>
      <tbody role="rowgroup">
        {rows.map((row) => (
          <tr key={row.heading} role="row" className={row.chosen ? "results-table__chosen" : undefined}>
            <th scope="row" role="rowheader">
              {row.heading}
              {row.chosen && <span className="results-table__tag"> (chosen)</span>}
            </th>
            {row.cells.map((cell, index) => (
              <td key={columns[index + 1]} role="cell" data-label={columns[index + 1]}>
                {cell}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function Measures({ results }) {
  return (
    <ResultsTable
      caption="Scores on the held-back test links"
      columns={["Measure", "Score", "What it means"]}
      rows={[
        {
          heading: "Phishing recall",
          cells: [PERCENT.format(results.recall), "The share of phishing links the model caught."],
        },
        {
          heading: "Precision",
          cells: [PERCENT.format(results.precision), "Of the links the model called phishing, the share that really were."],
        },
        {
          heading: "F1",
          cells: [SCORE.format(results.f1), "Recall and precision combined into one score, from 0 to 1."],
        },
        {
          heading: "ROC-AUC",
          cells: [
            SCORE.format(results.rocAuc),
            "How well the model ranks phishing links above safe ones, from 0.5 (guessing) to 1.",
          ],
        },
      ]}
    />
  );
}

function Mistakes({ results }) {
  const phishing = results.caught + results.missed;
  const legitimate = results.flagged + results.cleared;
  return (
    <>
      <h3>The mistakes it makes</h3>
      <p>
        Of {COUNT.format(phishing)} phishing links, it missed {COUNT.format(results.missed)}. Of{" "}
        {COUNT.format(legitimate)} safe links, it wrongly flagged {COUNT.format(results.flagged)} as phishing.
      </p>
      <ResultsTable
        caption="What the test links really were, against what the model said"
        columns={["", "Model said phishing", "Model said legitimate"]}
        rows={[
          {
            heading: "Really phishing",
            cells: [`${COUNT.format(results.caught)} caught`, `${COUNT.format(results.missed)} missed`],
          },
          {
            heading: "Really legitimate",
            cells: [`${COUNT.format(results.flagged)} wrongly flagged`, `${COUNT.format(results.cleared)} correctly passed`],
          },
        ]}
      />
    </>
  );
}

function Comparison({ rows }) {
  const chosen = rows.find((row) => row.name === CHOSEN_MODEL);
  return (
    <>
      <h3>The models we compared</h3>
      {chosen && (
        <p>
          We chose <strong>{chosen.name}</strong> {chosenReason(chosen, rows)}
        </p>
      )}
      <ResultsTable
        caption="Mean scores over 5 cross-validation folds on the training links"
        columns={["Model", "Phishing recall", "Precision", "F1", "ROC-AUC"]}
        rows={rows.map((row) => ({
          heading: row.name,
          chosen: row === chosen,
          cells: [row.recall, row.precision, row.f1, row.roc_auc].map((value) => MEASURE.format(value)),
        }))}
      />
    </>
  );
}

/**
 * How well LinkGuard's model does on the held-back test split: the scores, the
 * mistakes and the models it was chosen from, with the honesty note. Everything
 * is a real table with a caption, so a screen reader reads it as it is, and
 * nothing depends on colour. It only shows what the results files say. If a file
 * is missing or can't be read, it says so and shows no numbers.
 */
export default function ModelResults({
  evaluation = parseFile(Object.values(EVALUATION_FILES)[0]),
  comparison = parseFile(Object.values(COMPARISON_FILES)[0]),
}) {
  const results = readEvaluation(evaluation);
  const rows = readComparison(comparison);

  return (
    <section className="model-results" aria-labelledby="model-results-heading">
      <h2 id="model-results-heading">{RESULTS_HEADING}</h2>
      {!results || !rows ? (
        <p>{NOT_AVAILABLE}</p>
      ) : (
        <>
          <p className="model-results__lead">
            We kept {COUNT.format(results.caught + results.missed + results.flagged + results.cleared)} links back
            from training and tested the model on them. Phishing recall comes first:{" "}
            <strong>it caught {PERCENT.format(results.recall)} of phishing links.</strong> {RECALL_SENTENCE}
          </p>
          <p className="dataset-note">
            <strong>Please note:</strong> {HONESTY_NOTE}
          </p>
          <Measures results={results} />
          <Mistakes results={results} />
          <Comparison rows={rows} />
        </>
      )}
    </section>
  );
}
