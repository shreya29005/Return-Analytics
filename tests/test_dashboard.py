"""Observation templates (artificial inputs) and a Streamlit AppTest smoke check."""
import pandas as pd
import pytest

from dashboard import insights
from src.config import DATABASE_PATH


def prio(rows):
    cols = ["priority_rank", "product_category", "eligible_purchases", "returned_purchases", "return_rate",
            "baseline_rate", "rate_diff_pp", "share_of_returns", "leading_reason", "leading_reason_share",
            "leading_reason_margin_pp", "reasons_tied_at_top", "value_associated_with_returned",
            "meets_min_support", "ranking_basis"]
    return pd.DataFrame(rows, columns=cols)


ROW_A = [1, "A", 100, 60, 0.6, 0.5, 10.0, 0.6, "Defective", 0.5, 20.0, 1, 600.0, True, "returned purchase count"]
ROW_B = [2, "B", 100, 40, 0.4, 0.5, -10.0, 0.4, "Changed mind", 0.3, 1.0, 1, 400.0, True, "returned purchase count"]


def test_observations_handle_empty_and_no_returns():
    empty = pd.Series({"eligible_purchases": 0, "returned_purchases": 0})
    assert insights.observations(empty, prio([]), pd.DataFrame()) == []
    none = pd.Series({"eligible_purchases": 20, "returned_purchases": 0})
    out = insights.observations(none, prio([]), pd.DataFrame())
    assert len(out) == 1 and "No returns" in out[0]


def test_observations_use_filtered_numbers():
    ov = pd.Series({"eligible_purchases": 200, "returned_purchases": 100})
    reasons = pd.DataFrame({"return_reason": ["Defective", "Changed mind"], "returned_purchases": [70, 30],
                            "share_of_returns": [0.7, 0.3]})
    out = insights.observations(ov, prio([ROW_A, ROW_B]), reasons)
    assert "A ranks first" in out[0] and "60 of 100" in out[0]
    assert "spread of 20.0 pp" in out[1]
    assert len(out) == 3


def test_actions_require_clear_leading_reason_and_support():
    acts = insights.actions(prio([ROW_A, ROW_B]))
    assert list(acts["Priority"]) == [1]  # B's leading reason is only 1 pp ahead
    low = prio([ROW_A[:13] + [False, ROW_A[14]]])
    assert insights.actions(low).empty


@pytest.mark.skipif(not DATABASE_PATH.exists(), reason="run `python pipeline.py` first")
def test_dashboard_pages_render_filtered_and_empty_states():
    from streamlit.testing.v1 import AppTest
    from src.config import PROJECT_ROOT
    at = AppTest.from_file(str(PROJECT_ROOT / "dashboard" / "app.py"), default_timeout=120).run()
    assert not at.exception
    assert [m.label for m in at.metric][:3] == ["Eligible purchases", "Returned purchases", "Observed return rate"]
    for page in ["views/2_reasons_and_patterns.py", "views/3_investigation_priorities.py"]:
        at.switch_page(page).run()
        assert not at.exception, page
        assert not at.info or "No purchases" not in at.info[0].value  # filters survive page switch
    at.switch_page("views/1_returns_overview.py").run()
    at.multiselect[0].set_value([]).run()
    assert not at.exception and "No purchases" in at.info[0].value
    at.button[0].click().run()
    assert not at.exception and at.metric[0].value != "0"
