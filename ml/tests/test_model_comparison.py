import copy
import json

import pytest

from ranking.final_list import FINAL_FEATURES
from training.model_comparison import (
    BASELINE,
    BALANCED_LR,
    MATRIX_DIR_NAME,
    MODEL_NAMES,
    PLAIN_LR,
    REPORT_NAME,
    RESULTS_NAME,
    ModelComparisonError,
    check_results,
    choose_model,
    class_balance_note,
    confusion_chart,
    confusion_matrix,
    fit_note,
    matrix_file_name,
    mean_scores,
    report,
    score_table,
    scores_from_counts,
    trade_off,
    main,
)

FOLDS = 5
# Each made-up fold holds 500 training rows: 200 phishing and 300 legitimate.
FOLD_PHISHING, FOLD_LEGITIMATE = 200, 300
# Per model: mean cross-validation recall, wrongly flagged legitimate links per fold, ROC-AUC,
# then the training recall and F1. The other scores are worked out from the counts.
MADE_UP = {
    BASELINE: (0.0, 0, 0.5, 0.0, 0.0),
    PLAIN_LR: (0.70, 30, 0.85, 0.71, 0.76),
    BALANCED_LR: (0.78, 60, 0.85, 0.79, 0.76),
    "Random forest": (0.82, 30, 0.92, 0.99, 0.99),
    "Gradient boosting": (0.80, 20, 0.91, 0.84, 0.86),
}
# Fold recalls are the mean plus these offsets, so the standard deviation is known.
OFFSETS = (-0.02, -0.01, 0.0, 0.01, 0.02)


def made_up_model(recall, false_alarms, roc_auc, train_recall, train_f1):
    folds = []
    for fold, offset in enumerate(OFFSETS, start=1):
        tp = round(FOLD_PHISHING * (recall + offset)) if recall else 0
        counts = {"tp": tp, "fp": false_alarms, "fn": FOLD_PHISHING - tp, "tn": FOLD_LEGITIMATE - false_alarms}
        cv = {metric: round(value, 6) for metric, value in scores_from_counts(counts).items()}
        cv["roc_auc"] = roc_auc
        train = dict(cv, recall=train_recall, f1=train_f1)
        folds.append({"fold": fold, "cv": cv, "train": train, "confusion": counts})
    return {"folds": folds}


def made_up_results(means=None):
    means = means or MADE_UP
    return {
        "features": list(FINAL_FEATURES),
        "folds": FOLDS,
        "seed": 0,
        "training_rows": FOLDS * (FOLD_PHISHING + FOLD_LEGITIMATE),
        "class_balance": {"phishing": FOLDS * FOLD_PHISHING, "legitimate": FOLDS * FOLD_LEGITIMATE},
        "models": {name: made_up_model(*values) for name, values in means.items()},
    }


def with_means(**changes):
    means = dict(MADE_UP)
    means.update(changes)
    return made_up_results(means)


# Scores: mean and spread over the folds (AC3)


def test_the_table_is_the_mean_and_standard_deviation_over_the_folds():
    cv = score_table(made_up_results())
    forest = cv.loc["Random forest"]
    assert forest["recall mean"] == pytest.approx(0.82)
    # Offsets of -0.02 to 0.02 in steps of 0.01 have a sample standard deviation of 0.0158.
    assert forest["recall std"] == pytest.approx(0.015811, abs=1e-6)
    assert forest["roc_auc std"] == pytest.approx(0.0)


def test_the_report_puts_recall_first_and_accuracy_last():
    page = report(made_up_results())
    header = next(line for line in page.splitlines() if line.startswith("| Model |"))
    columns = [cell.strip() for cell in header.strip("|").split("|")]
    assert columns[1] == "Phishing recall"
    assert columns[-1] == "Accuracy"
    assert columns.index("Precision") < columns.index("F1") < columns.index("ROC-AUC")


def test_every_model_and_the_baseline_has_a_row_with_mean_and_spread():
    page = report(made_up_results())
    for name in MODEL_NAMES:
        row = next(line for line in page.splitlines() if line.startswith(f"| {name} |"))
        assert "±" in row
    forest_row = next(line for line in page.splitlines() if line.startswith("| Random forest |"))
    assert "0.820 ± 0.016" in forest_row


# The chosen model and why (AC4)


def test_the_highest_mean_recall_wins():
    name, reason = choose_model(mean_scores(made_up_results(), "cv"))
    assert name == "Random forest"
    assert "recall" in reason


def test_f1_decides_when_recall_is_close():
    # Gradient boosting is within 0.01 on recall, and its F1 is clearly higher.
    results = with_means(**{"Gradient boosting": (0.815, 5, 0.93, 0.84, 0.88)})
    name, reason = choose_model(mean_scores(results, "cv"))
    assert name == "Gradient boosting"
    assert "F1" in reason


def test_the_simpler_model_wins_when_recall_and_f1_are_both_close():
    # Logistic regression ties the forest on recall and F1, and it is the simpler model.
    results = with_means(**{PLAIN_LR: (0.82, 30, 0.90, 0.83, 0.84)})
    name, reason = choose_model(mean_scores(results, "cv"))
    assert name == PLAIN_LR
    assert "simpler" in reason


def test_a_tie_on_recall_is_described_against_the_best():
    results = with_means(**{"Gradient boosting": (0.815, 5, 0.93, 0.84, 0.88)})
    _, reason = choose_model(mean_scores(results, "cv"))
    assert "within 0.01 of the best mean phishing recall" in reason
    assert "of each other" not in reason


def test_the_reason_says_what_the_choice_costs():
    cv_means = mean_scores(made_up_results(), "cv")
    # Gradient boosting flags fewer legitimate links, so the forest gives up some precision.
    cost = trade_off(cv_means, "Random forest")
    assert "precision (0.845 against 0.889 for Gradient boosting)" in cost
    assert "ROC-AUC" not in cost
    page = report(made_up_results())
    assert page.index(cost) > page.index("Chosen model: Random forest")


def test_the_reason_says_when_the_choice_costs_nothing():
    results = with_means(**{"Random forest": (0.82, 0, 0.95, 0.83, 0.90)})
    assert "costs nothing" in trade_off(mean_scores(results, "cv"), "Random forest")


def test_the_baseline_is_never_chosen():
    results = with_means(**{BASELINE: (0.98, 300, 0.5, 1.0, 0.60)})
    name, _ = choose_model(mean_scores(results, "cv"))
    assert name != BASELINE


def test_the_page_is_labelled_as_in_dataset_results_and_names_the_choice_under_the_table():
    page = report(made_up_results())
    assert "in-dataset cross-validation results, not real-world accuracy" in page.lower()
    table_end = page.index("| Gradient boosting |")
    assert page.index("Chosen model: Random forest") > table_end


# Training scores next to the cross-validation scores (AC5)


def _tables(page):
    """The header and rows of each table on the page, in order."""
    tables, current = [], None
    for line in page.splitlines():
        if line.startswith("| Model |"):
            current = {"columns": [cell.strip() for cell in line.strip("|").split("|")], "rows": {}}
            tables.append(current)
        elif current is not None and line.startswith("| ") and not line.startswith("|---"):
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            current["rows"][cells[0]] = cells
        elif not line.startswith("|"):
            current = None
    return tables


def test_the_main_table_keeps_the_four_measures_together_with_accuracy_last():
    main_table = _tables(report(made_up_results()))[0]
    assert main_table["columns"] == ["Model", "Phishing recall", "Precision", "F1", "ROC-AUC", "Accuracy"]


def test_training_recall_and_f1_sit_next_to_the_cross_validation_ones():
    tables = _tables(report(made_up_results()))
    assert len(tables) == 2
    fit_table = tables[1]
    assert fit_table["columns"] == ["Model", "Phishing recall", "Recall on training rows", "F1", "F1 on training rows"]
    assert set(fit_table["rows"]) == set(MODEL_NAMES)
    forest = fit_table["rows"]["Random forest"]
    assert forest[1] == "0.820"
    assert forest[2] == "0.990"
    assert forest[4] == "0.990"


def test_the_fit_note_sits_under_the_training_table_and_says_what_it_checks():
    page = report(made_up_results())
    assert page.index("Random forest looks overfit") > page.index("| Model | Phishing recall | Recall on training rows")
    note = fit_note(*(mean_scores(with_means(**{"Random forest": (0.82, 30, 0.92, 0.83, 0.73)}), part) for part in ("train", "cv")))
    assert "Every training recall and F1 is within 0.05 of its cross-validation score." in note


def test_the_fit_note_flags_a_model_much_better_on_training_rows():
    results = made_up_results()
    note = fit_note(mean_scores(results, "train"), mean_scores(results, "cv"))
    assert "\n" not in note
    assert "Random forest looks overfit" in note
    assert "Gradient boosting looks overfit" not in note
    assert "No model looks underfit" in note


def test_the_fit_note_flags_a_model_low_on_training_rows_too():
    results = with_means(**{PLAIN_LR: (0.50, 30, 0.70, 0.51, 0.56)})
    note = fit_note(mean_scores(results, "train"), mean_scores(results, "cv"))
    assert "Logistic regression looks underfit" in note
    assert f"{BASELINE} looks underfit" not in note


# Class balance and class weights (AC8)


def test_the_class_balance_note_gives_the_training_counts_and_shares():
    results = made_up_results()
    note = class_balance_note(results, "Random forest", mean_scores(results, "cv"))
    assert "1,000 phishing (40.0%)" in note
    assert "1,500 legitimate (60.0%)" in note


def test_the_note_says_the_chosen_model_has_no_class_weights_and_what_they_did():
    results = made_up_results()
    note = class_balance_note(results, "Random forest", mean_scores(results, "cv"))
    assert "does not use class weights" in note
    assert "0.700 to 0.780" in note  # logistic regression's recall without and with weights


def test_the_note_says_when_the_chosen_model_uses_class_weights():
    results = with_means(**{BALANCED_LR: (0.95, 60, 0.90, 0.95, 0.80)})
    chosen, _ = choose_model(mean_scores(results, "cv"))
    assert chosen == BALANCED_LR
    note = class_balance_note(results, chosen, mean_scores(results, "cv"))
    assert 'uses class weights (class_weight="balanced")' in note


# Confusion matrices (AC6)


def test_the_confusion_matrix_adds_up_the_held_out_folds():
    matrix = confusion_matrix(made_up_results()["models"]["Random forest"])
    assert list(matrix.index) == ["phishing", "legitimate"]
    assert list(matrix.columns) == ["phishing", "legitimate"]
    assert matrix.loc["phishing", "phishing"] == 820
    assert matrix.loc["phishing", "legitimate"] == 180
    assert matrix.loc["legitimate", "phishing"] == 150
    assert matrix.loc["legitimate", "legitimate"] == 1350
    assert int(matrix.to_numpy().sum()) == 2500


def test_the_chart_names_both_classes_in_words_and_shows_the_counts():
    matrix = confusion_matrix(made_up_results()["models"]["Random forest"])
    figure = confusion_chart("Random forest", matrix)
    axis = figure.axes[0]
    assert [label.get_text() for label in axis.get_xticklabels()] == ["phishing", "legitimate"]
    assert [label.get_text() for label in axis.get_yticklabels()] == ["phishing", "legitimate"]
    cell_texts = {text.get_text() for text in axis.texts}
    assert {"820", "180", "150", "1,350"} <= cell_texts


def test_matrix_file_names_are_plain():
    assert matrix_file_name(BASELINE) == "baseline_most_common_class.png"
    assert matrix_file_name(BALANCED_LR) == "logistic_regression_balanced.png"


# Checks on the results file


def test_a_good_results_file_passes():
    check_results(made_up_results())


def double_counts(counts):
    counts.update({count: 2 * value for count, value in counts.items()})


@pytest.mark.parametrize(
    "spoil, message",
    [
        (lambda r: r["models"].pop("Random forest"), "Random forest"),
        (lambda r: r["models"]["Random forest"]["folds"].pop(), "5 folds"),
        (lambda r: r.update(features=r["features"][:-1]), "final feature list"),
        (lambda r: r["models"][PLAIN_LR]["folds"][0]["cv"].pop("roc_auc"), "roc_auc"),
        (lambda r: r["models"][PLAIN_LR]["folds"][0]["cv"].update(recall=1.5), "between 0 and 1"),
        # Doubling every count keeps the scores but predicts some rows twice.
        (lambda r: double_counts(r["models"][PLAIN_LR]["folds"][0]["confusion"]), "every training row"),
        (lambda r: r.update(training_rows=999), "every training row"),
        (lambda r: r["class_balance"].update(phishing=999), "phishing label"),
        (lambda r: r.update(folds=4), "needs 5 folds"),
        (lambda r: r["models"][PLAIN_LR]["folds"][0]["cv"].update(recall=0.99), "do not match"),
        (lambda r: r["models"][PLAIN_LR]["folds"][0]["confusion"].update(tp=134.5, fn=65.5), "whole number"),
        (lambda r: r["models"][PLAIN_LR]["folds"][0]["confusion"].update(tp=-1, fn=201), "whole number"),
        (lambda r: r["class_balance"].update(legitimate=1), "class balance"),
        # A partial file: each key the report reads is missing in turn.
        (lambda r: r.pop("training_rows"), "training_rows is missing"),
        (lambda r: r.pop("class_balance"), "class_balance is missing"),
        (lambda r: r.pop("seed"), "seed is missing"),
        (lambda r: r["class_balance"].pop("legitimate"), "legitimate is missing"),
        (lambda r: r["models"][PLAIN_LR].pop("folds"), "folds is missing"),
        (lambda r: r["models"][PLAIN_LR]["folds"][2].pop("confusion"), "fold 3: confusion is missing"),
        (lambda r: r["models"][PLAIN_LR]["folds"][0].pop("train"), "train is missing"),
        (lambda r: r["models"][PLAIN_LR]["folds"][0].update(confusion=[1, 2, 3, 4]), "not a set of named values"),
        (lambda r: r.update(models=[]), "not a set of named values"),
        (lambda r: r["models"][PLAIN_LR].update(folds="five"), "folds are not a list"),
    ],
)
def test_a_wrong_results_file_is_refused_by_name(spoil, message):
    results = copy.deepcopy(made_up_results())
    spoil(results)
    with pytest.raises(ModelComparisonError, match=message):
        check_results(results)


# The whole run


def test_main_writes_the_report_and_one_matrix_per_model(tmp_path):
    reports = tmp_path / "reports"
    reports.mkdir()
    (reports / RESULTS_NAME).write_text(json.dumps(made_up_results()))
    assert main(tmp_path) == 0
    page = (reports / REPORT_NAME).read_text()
    assert "Chosen model: Random forest" in page
    charts = sorted(path.name for path in (reports / MATRIX_DIR_NAME).iterdir())
    assert charts == sorted(matrix_file_name(name) for name in MODEL_NAMES)
    for name in MODEL_NAMES:
        assert f"{MATRIX_DIR_NAME}/{matrix_file_name(name)}" in page


def test_main_stops_and_saves_nothing_without_the_results_file(tmp_path, capsys):
    assert main(tmp_path) == 1
    assert "training.classifiers" in capsys.readouterr().out
    assert not (tmp_path / "reports" / REPORT_NAME).exists()


def test_main_stops_and_saves_nothing_for_a_wrong_results_file(tmp_path, capsys):
    reports = tmp_path / "reports"
    reports.mkdir()
    results = made_up_results()
    results["models"].pop("Gradient boosting")
    (reports / RESULTS_NAME).write_text(json.dumps(results))
    assert main(tmp_path) == 1
    assert "Model comparison stopped" in capsys.readouterr().out
    assert not (reports / REPORT_NAME).exists()
    assert not (reports / MATRIX_DIR_NAME).exists()


def test_a_results_file_that_is_not_a_set_of_named_values_is_refused():
    with pytest.raises(ModelComparisonError, match="not a set of named values"):
        check_results([1, 2, 3])


def test_main_stops_and_saves_nothing_for_a_cut_off_results_file(tmp_path, capsys):
    reports = tmp_path / "reports"
    reports.mkdir()
    whole = json.dumps(made_up_results())
    (reports / RESULTS_NAME).write_text(whole[: len(whole) // 2])
    assert main(tmp_path) == 1
    out = capsys.readouterr().out
    assert "Model comparison stopped" in out
    assert "not valid JSON" in out
    assert not (reports / REPORT_NAME).exists()
    assert not (reports / MATRIX_DIR_NAME).exists()


def test_main_stops_and_saves_nothing_for_a_partial_results_file(tmp_path, capsys):
    reports = tmp_path / "reports"
    reports.mkdir()
    results = made_up_results()
    del results["models"][PLAIN_LR]["folds"][0]["cv"]
    (reports / RESULTS_NAME).write_text(json.dumps(results))
    assert main(tmp_path) == 1
    assert "cv is missing" in capsys.readouterr().out
    assert not (reports / REPORT_NAME).exists()
