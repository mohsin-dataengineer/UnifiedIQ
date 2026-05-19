import json
from pathlib import Path

from app.models.domain import ChartConfig
from app.models.responses import SQLGenerationResponse
from eval.report_template import render_report
from eval.run_eval import eval_l1, eval_l2, judge, run

GOLDEN = Path(__file__).parents[1] / "eval" / "golden_test_set.json"


def test_l1_syntax():
    assert eval_l1("SELECT a FROM t") == (True, [])
    ok, tags = eval_l1("SELEKT a FRM")
    assert ok is False and tags == ["l1_parse_error"]
    assert eval_l1(None) == (None, [])


def test_l2_passes_on_good_result():
    case = {
        "expected_intent": "data",
        "expected_columns": ["region", "total_revenue"],
        "required_patterns": ["GROUP BY"],
        "forbidden_patterns": ["SELECT \\*"],
        "expected_chart_type": "none",
    }
    res = SQLGenerationResponse(
        intent="data",
        sql="SELECT region, SUM(x) AS total_revenue FROM t GROUP BY region",
    )
    ok, tags = eval_l2(case, res)
    assert ok and tags == []


def test_l2_flags_select_star_and_intent():
    case = {
        "expected_intent": "data",
        "expected_columns": [],
        "required_patterns": [],
        "forbidden_patterns": ["SELECT \\*"],
        "expected_chart_type": "none",
    }
    res = SQLGenerationResponse(intent="chart", sql="SELECT * FROM t")
    ok, tags = eval_l2(case, res)
    assert not ok
    assert "intent_mismatch" in tags
    assert "forbidden_pattern" in tags


def test_l2_chart_type_mismatch():
    case = {
        "expected_intent": "chart",
        "expected_columns": [],
        "required_patterns": [],
        "forbidden_patterns": [],
        "expected_chart_type": "bar",
    }
    res = SQLGenerationResponse(
        intent="chart",
        sql="SELECT a, b FROM t",
        chart_config=ChartConfig(type="line"),
    )
    ok, tags = eval_l2(case, res)
    assert not ok and "chart_type_mismatch" in tags


def test_judge_stub():
    assert judge("q", "answer", {"expected_intent": "data"}).value == 1.0
    assert judge("q", "", {"expected_intent": "reject"}).value == 0.0


async def test_run_over_golden_with_fake_generator():
    golden = json.loads(GOLDEN.read_text())

    async def fake_gen(case):
        if case["expected_intent"] in ("reject", "clarify"):
            return SQLGenerationResponse(
                intent=case["expected_intent"],
                clarifying_question="?",
                rejection_reason="no",
            )
        return SQLGenerationResponse(
            intent=case["expected_intent"],
            sql=case["expected_sql"].replace("{table}", "sales"),
            chart_config=ChartConfig(type=case["expected_chart_type"]),
        )

    report = await run(golden, fake_gen)
    assert report["git_sha"]
    assert set(report["summary"]["by_tier"]) == {
        "core",
        "edge",
        "regression",
    }
    html = render_report(report)
    assert report["run_id"] in html
    assert "<table" in html
