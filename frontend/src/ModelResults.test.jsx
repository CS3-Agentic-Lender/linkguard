import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import App from "./App.jsx";
import ModelResults, {
  BASELINE,
  chooseModel,
  HONESTY_NOTE,
  NOT_AVAILABLE,
  parseFile,
  readComparison,
  RECALL_SENTENCE,
  RESULTS_HEADING,
} from "./ModelResults.jsx";

// Made-up results files in the same shape as the ones the ml scripts write.
const EVALUATION = {
  test: { recall: 0.5, precision: 0.8, f1: 0.615, accuracy: 0.7, roc_auc: 0.75 },
  confusion_matrix: {
    rows: "actual",
    columns: "predicted",
    labels: ["phishing", "legitimate"],
    counts: [
      [1000, 1000],
      [250, 2750],
    ],
  },
};

function folds(recall, precision, f1, roc_auc) {
  return { folds: [1, 2].map((fold) => ({ fold, cv: { recall, precision, f1, roc_auc, accuracy: 0.5 } })) };
}

const COMPARISON = {
  models: {
    [BASELINE]: folds(0, 0, 0, 0.5),
    "Model A": folds(0.6, 0.9, 0.72, 0.83),
    "Model B": folds(0.65, 0.8, 0.71, 0.78),
  },
};

function results(props = {}) {
  render(<ModelResults evaluation={EVALUATION} comparison={COMPARISON} {...props} />);
  return within(screen.getByRole("region", { name: RESULTS_HEADING }));
}

function rowsOf(table) {
  return within(table)
    .getAllByRole("row")
    .slice(1)
    .map((row) => [...row.querySelectorAll("th, td")].map((cell) => cell.textContent));
}

describe("the scores (acceptance criterion 1)", () => {
  it("shows recall, precision, F1 and ROC-AUC from the results file, recall first", () => {
    const section = results();
    const table = section.getByRole("table", { name: "Scores on the held-back test links" });

    expect(rowsOf(table).map(([name, score]) => [name, score])).toEqual([
      ["Phishing recall", "50%"],
      ["Precision", "80%"],
      ["F1", "0.62"],
      ["ROC-AUC", "0.75"],
    ]);
  });

  it("explains recall in one plain sentence before anything else", () => {
    const section = results();
    const lead = section.getByText(/caught 50% of phishing links/).closest("p");

    expect(lead).toHaveTextContent(RECALL_SENTENCE);
    expect(lead.compareDocumentPosition(section.getAllByRole("table")[0]) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("never leads with accuracy", () => {
    expect(results().queryByText(/accuracy/i)).not.toBeInTheDocument();
  });
});

describe("the mistakes (acceptance criterion 2)", () => {
  it("names the rows and columns in words and puts a count in each cell", () => {
    const table = results().getByRole("table", { name: /really were, against what the model said/ });

    expect(within(table).getAllByRole("columnheader").map((cell) => cell.textContent)).toEqual([
      "Model said phishing",
      "Model said legitimate",
    ]);
    expect(rowsOf(table)).toEqual([
      ["Really phishing", "1,000 caught", "1,000 missed"],
      ["Really legitimate", "250 wrongly flagged", "2,750 correctly passed"],
    ]);
  });

  it("says how many phishing links were missed and how many safe links were wrongly flagged", () => {
    expect(
      results().getByText(
        "Of 2,000 phishing links, it missed 1,000. Of 3,000 safe links, it wrongly flagged 250 as phishing.",
      ),
    ).toBeInTheDocument();
  });
});

describe("the model comparison (acceptance criterion 3)", () => {
  it("shows every model's mean scores, with the chosen one marked in words", () => {
    const table = results().getByRole("table", { name: /cross-validation folds/ });

    expect(rowsOf(table)).toEqual([
      [BASELINE, "0.000", "0.000", "0.000", "0.500"],
      ["Model A", "0.600", "0.900", "0.720", "0.830"],
      ["Model B (chosen)", "0.650", "0.800", "0.710", "0.780"],
    ]);
  });

  it("gives the reason the model was chosen", () => {
    expect(results().getByText(/because it caught the most phishing links/)).toHaveTextContent(
      "We chose Model B because it caught the most phishing links in testing (phishing recall 0.650).",
    );
  });

  it("splits models within 0.01 of the best recall by F1, and never picks the baseline", () => {
    const rows = readComparison({
      models: {
        [BASELINE]: folds(1, 0, 0, 0.5),
        "Model A": folds(0.645, 0.9, 0.73, 0.83),
        "Model B": folds(0.65, 0.8, 0.71, 0.78),
      },
    });

    expect(chooseModel(rows)).toMatchObject({ model: { name: "Model A" }, reason: "f1" });
  });

  it("picks the simpler model when the best are also within 0.01 on F1", () => {
    const rows = readComparison({
      models: {
        "Random forest": folds(0.645, 0.9, 0.725, 0.83),
        "Logistic regression": folds(0.64, 0.8, 0.72, 0.78),
      },
    });

    expect(chooseModel(rows)).toMatchObject({ model: { name: "Logistic regression" }, reason: "simpler" });
  });

  it("gives the reason from the step of the rule that decided, not always the highest recall", () => {
    const comparison = {
      models: {
        "Model A": folds(0.645, 0.9, 0.73, 0.83),
        "Model B": folds(0.65, 0.8, 0.71, 0.78),
      },
    };
    const reason = results({ comparison }).getByText(/^We chose/);

    expect(reason).toHaveTextContent("We chose Model A because it caught about as many phishing links as the best model");
    expect(reason).not.toHaveTextContent("caught the most phishing links");
  });

  it("averages each score over the folds", () => {
    const rows = readComparison({
      models: {
        "Model A": {
          folds: [
            { cv: { recall: 0.5, precision: 0.8, f1: 0.6, roc_auc: 0.7 } },
            { cv: { recall: 0.7, precision: 0.6, f1: 0.8, roc_auc: 0.9 } },
          ],
        },
      },
    });

    expect(rows[0].recall).toBeCloseTo(0.6);
    expect(rows[0].precision).toBeCloseTo(0.7);
  });
});

describe("the honesty note (acceptance criterion 4)", () => {
  it("shows the note word for word", () => {
    expect(results().getByText(HONESTY_NOTE)).toBeInTheDocument();
    expect(HONESTY_NOTE).toBe(
      "The scores come from PhiUSIIL only and are an upper bound on real-world performance, because the dataset's legitimate links are all bare homepages and the model uses hostname features only.",
    );
  });
});

describe("screen readers and colour (acceptance criterion 5)", () => {
  it("gives every table a caption, so a screen reader names and reads it", () => {
    const tables = results().getAllByRole("table");

    expect(tables).toHaveLength(3);
    for (const table of tables) {
      expect(table.querySelector("caption")?.textContent).toBeTruthy();
      expect(table).toHaveAccessibleName();
    }
  });

  it("marks the chosen model with a word, not colour alone", () => {
    const row = results().getByRole("rowheader", { name: /chosen/ });

    expect(row).toHaveTextContent("(chosen)");
  });
});

describe("a missing or unreadable results file (acceptance criterion 6)", () => {
  it.each([
    ["no evaluation file", { evaluation: null }],
    ["no comparison file", { comparison: null }],
    ["an evaluation file with a score missing", { evaluation: { ...EVALUATION, test: { recall: 0.5 } } }],
    ["a score that isn't a number", { evaluation: { ...EVALUATION, test: { ...EVALUATION.test, f1: "high" } } }],
    [
      "a confusion matrix with the labels the other way round",
      { evaluation: { ...EVALUATION, confusion_matrix: { ...EVALUATION.confusion_matrix, labels: ["legitimate", "phishing"] } } },
    ],
    ["a comparison with no folds", { comparison: { models: { "Model A": { folds: [] } } } }],
    ["an evaluation file that isn't valid JSON", { evaluation: parseFile('{"test": {"recall": 0.5') }],
    ["a comparison file that isn't valid JSON", { comparison: parseFile("not json") }],
  ])("shows the message and no numbers for %s", (_name, props) => {
    const section = results(props);

    expect(section.getByText(NOT_AVAILABLE)).toBeInTheDocument();
    expect(section.queryByRole("table")).not.toBeInTheDocument();
    expect(screen.getByRole("region", { name: RESULTS_HEADING }).textContent).not.toMatch(/\d/);
  });
});

describe("on the page", () => {
  it("shows the real results from ml/reports under the charts", () => {
    render(<App />);
    const section = within(screen.getByRole("region", { name: RESULTS_HEADING }));

    expect(section.queryByText(NOT_AVAILABLE)).not.toBeInTheDocument();
    expect(section.getAllByRole("table")).toHaveLength(3);
    expect(section.getByRole("rowheader", { name: /chosen/ })).toHaveTextContent("Logistic regression (balanced)");
  });
});
