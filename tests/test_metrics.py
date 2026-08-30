from simulation.metrics.metrics import compute_stat, percent_improvement, summarize_rows


def test_compute_stat_basic_values():
    stat = compute_stat([1, 2, 3, 4, 5])
    assert stat.mean == 3
    assert stat.median == 3
    assert stat.min == 1
    assert stat.max == 5
    assert stat.n == 5
    assert stat.stdev > 0


def test_compute_stat_empty_list():
    stat = compute_stat([])
    assert stat.n == 0
    assert stat.mean == 0.0


def test_percent_improvement_lower_is_better_metric():
    # completion_time: MAS faster than baseline -> positive improvement.
    improvement = percent_improvement(baseline_value=100, mas_value=80, metric="completion_time")
    assert improvement == 20.0

    # MAS slower -> negative improvement (must not be mislabeled as a win).
    worse = percent_improvement(baseline_value=100, mas_value=120, metric="completion_time")
    assert worse == -20.0


def test_percent_improvement_higher_is_better_metric():
    # victims_rescued: MAS rescuing more is an improvement.
    improvement = percent_improvement(baseline_value=10, mas_value=15, metric="victims_rescued")
    assert improvement == 50.0


def test_percent_improvement_handles_zero_baseline():
    assert percent_improvement(0, 5, "completion_time") == 0.0


def test_summarize_rows_groups_and_aggregates():
    rows = [
        {"policy": "mas", "victim_count": 10, "completion_time": 100},
        {"policy": "mas", "victim_count": 10, "completion_time": 120},
        {"policy": "baseline", "victim_count": 10, "completion_time": 80},
    ]
    summary = summarize_rows(rows, group_keys=["policy", "victim_count"], value_keys=["completion_time"])
    mas_entry = next(s for s in summary if s["policy"] == "mas")
    assert mas_entry["n_runs"] == 2
    assert mas_entry["completion_time_mean"] == 110
