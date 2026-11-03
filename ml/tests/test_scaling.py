import numpy as np
import pandas as pd
import pytest

from splitting.scaling import fit_scaler, load_scaler, save_scaler, scale

TRAIN = pd.DataFrame(
    {"HostnameLength": [10, 20, 30, 40], "DigitRatioInHostname": [0.0, 0.1, 0.2, 0.5]},
    index=[0, 3, 5, 9],
)
TEST = pd.DataFrame(
    {"HostnameLength": [100, 5], "DigitRatioInHostname": [0.9, 0.0]},
    index=[1, 7],
)


def test_scaled_training_rows_have_mean_zero_and_unit_spread():
    scaler = fit_scaler(TRAIN)

    scaled = scale(scaler, TRAIN)

    np.testing.assert_allclose(scaled.mean(), 0.0, atol=1e-12)
    np.testing.assert_allclose(scaled.std(ddof=0), 1.0)


def test_scaler_is_fitted_on_the_training_rows_only():
    scaler = fit_scaler(TRAIN)

    np.testing.assert_allclose(scaler.mean_, TRAIN.mean().to_numpy())


def test_scaling_the_test_rows_does_not_refit_the_scaler():
    scaler = fit_scaler(TRAIN)
    mean_before = scaler.mean_.copy()

    scaled_test = scale(scaler, TEST)

    np.testing.assert_array_equal(scaler.mean_, mean_before)
    # Test rows are measured against the training mean, so they are not centred on 0.
    assert scaled_test["HostnameLength"].iloc[0] > 3


def test_scaled_rows_keep_their_index_and_column_names():
    scaler = fit_scaler(TRAIN)

    scaled = scale(scaler, TEST)

    assert scaled.index.tolist() == [1, 7]
    assert scaled.columns.tolist() == TRAIN.columns.tolist()


def test_scaling_does_not_change_the_input():
    original = TEST.copy()
    scaler = fit_scaler(TRAIN)

    scale(scaler, TEST)

    pd.testing.assert_frame_equal(TEST, original)


def test_rejects_columns_in_a_different_order():
    scaler = fit_scaler(TRAIN)

    with pytest.raises(ValueError, match="columns"):
        scale(scaler, TEST[["DigitRatioInHostname", "HostnameLength"]])


def test_reloaded_scaler_gives_exactly_the_same_output(tmp_path):
    scaler = fit_scaler(TRAIN)

    path = save_scaler(scaler, tmp_path / "models" / "scaler.joblib")
    reloaded = load_scaler(path)

    pd.testing.assert_frame_equal(scale(reloaded, TEST), scale(scaler, TEST))
