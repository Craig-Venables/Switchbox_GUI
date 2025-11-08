import os
from pathlib import Path

from Measurments.data_saver import MeasurementDataSaver, SummaryPlotData
from Measurments.single_measurement_runner import find_largest_number_in_folder


def test_save_summary_plots_creates_expected_files(tmp_path):
    saver = MeasurementDataSaver()
    plot_data = SummaryPlotData(
        all_iv=[([0.0, 1.0], [0.0, 1.0])],
        all_log=[([0.1, 1.0], [1e-6, 1e-3])],
        final_iv=([0.0, 1.0], [0.0, 1.0]),
    )

    final_iv, final_log, combined = saver.save_summary_plots(tmp_path, plot_data)

    assert final_iv is not None and final_iv.exists()
    assert final_log is not None and final_log.exists()
    assert combined is not None and combined.exists()


def test_create_log_file_appends_entries(tmp_path):
    saver = MeasurementDataSaver()
    log_dir = tmp_path / "A" / "1"
    path = saver.create_log_file(log_dir, "2025-01-01 10:00:00", "IV Sweep")

    assert path.exists()
    contents = path.read_text(encoding="utf-8")
    assert "Measurement Type: IV Sweep" in contents


def test_find_largest_number_in_folder(tmp_path):
    filenames = ["0-test.txt", "1-test.txt", "10-test.txt", "ignored.txt"]
    for name in filenames:
        (tmp_path / name).write_text("data", encoding="utf-8")

    max_index = find_largest_number_in_folder(tmp_path)
    assert max_index == 10

