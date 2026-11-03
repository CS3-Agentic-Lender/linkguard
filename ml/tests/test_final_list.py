import numpy as np
import pandas as pd

from features.hostname import FEATURE_NAMES
from ranking.final_list import CHART_NAME, DROPPED, FINAL_FEATURES, KEPT, REPORT_NAME, WATCH, main, report
from ranking.training_split import FEATURES_CSV_NAME, SPLIT_CSV_NAME
from splitting.scaling import SCALER_FILE_NAME, fit_scaler, save_scaler
from splitting.split import save_split

ROWS = 600


def made_up_feature_set(rows: int = ROWS) -> pd.DataFrame:
    generator = np.random.default_rng(1)
    host_number = np.arange(rows) // 12
    label = host_number % 2
    frame = pd.DataFrame({"row": range(rows)})
    for name in FEATURE_NAMES:
        frame[name] = generator.integers(0, 5, rows).astype(float)
    frame["HostnameLength"] = 10 + 20 * label + generator.integers(0, 3, rows)
    frame["IsDomainIP"] = (np.arange(rows) % 50 == 0).astype(int)
    frame["label"] = label
    frame["host"] = [f"host{number}.example" for number in host_number]
    return frame


def made_up_split(rows: int = ROWS) -> pd.DataFrame:
    host_number = np.arange(rows) // 12
    return pd.DataFrame({"row": range(rows), "set": np.where(host_number % 5 == 4, "test", "train")})


def save_inputs(ml_dir, with_scaler: bool = True):
    (ml_dir / "data").mkdir()
    features, split = made_up_feature_set(), made_up_split()
    features.to_csv(ml_dir / "data" / FEATURES_CSV_NAME, index=False)
    save_split(split.set_index("row")["set"], features.set_index("row")["host"], ml_dir / "data" / SPLIT_CSV_NAME)
    if with_scaler:
        training = features[split["set"] == "train"][list(FEATURE_NAMES)]
        save_scaler(fit_scaler(training), ml_dir / "models" / SCALER_FILE_NAME)


def test_the_list_keeps_eight_and_drops_the_two_copies():
    assert len(FINAL_FEATURES) == 8
    assert set(DROPPED) == {"NoOfLettersInHostname", "SpecialCharRatioInHostname"}
    assert set(FINAL_FEATURES) | set(DROPPED) == set(FEATURE_NAMES)
    assert set(FINAL_FEATURES).isdisjoint(DROPPED)
    assert list(FINAL_FEATURES) == [name for name in FEATURE_NAMES if name in FINAL_FEATURES]


def test_watched_features_are_kept_and_every_dropped_feature_has_a_reason():
    assert set(WATCH) <= set(FINAL_FEATURES)
    assert all(reason.strip() for reason in DROPPED.values())
    assert "IsDomainIP" in FINAL_FEATURES


def test_every_kept_feature_has_exactly_one_reason():
    # IsDomainIP's reason is built in the report, the watched ones come from WATCH, the rest from KEPT.
    reasons = set(KEPT) | set(WATCH) | {"IsDomainIP"}
    assert reasons == set(FINAL_FEATURES)
    assert len(KEPT) + len(WATCH) + 1 == len(FINAL_FEATURES)


def test_report_names_every_feature_with_its_reason():
    ranks = pd.DataFrame({m: range(1, 11) for m in ("Mutual information", "Forest (built-in)", "Forest (held-out hosts)", "PCA weight")},
                         index=list(FEATURE_NAMES))

    page = report(ranks, 510, 188_295)

    for name in FEATURE_NAMES:
        assert f"`{name}`" in page
    for reason in DROPPED.values():
        assert reason in page
    assert "only 510 of 188,295 training links use an IP address" in page
    assert "Kept, but watched." in page
    assert CHART_NAME in page


def test_main_saves_the_list_and_the_chart_and_returns_0(tmp_path, capsys):
    save_inputs(tmp_path)

    code = main(tmp_path)

    assert code == 0
    assert (tmp_path / "reports" / REPORT_NAME).exists()
    assert (tmp_path / "reports" / CHART_NAME).exists()
    assert "Saved" in capsys.readouterr().out


def test_main_explains_a_missing_scaler_saves_nothing_and_returns_1(tmp_path, capsys):
    save_inputs(tmp_path, with_scaler=False)

    code = main(tmp_path)

    assert code == 1
    assert not (tmp_path / "reports" / REPORT_NAME).exists()
    assert "Final feature list stopped:" in capsys.readouterr().out
