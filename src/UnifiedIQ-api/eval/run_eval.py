"""Layered evaluation runner (Part 4).

L1 Syntax     - parse generated SQL with sqlglot (databricks dialect)
L2 Structure  - intent / regex / expected-columns / chart-type checks
L3 Parity     - execute generated vs expected SQL (opt-in, --run-l3)
L4 Judge      - stubbed LLM-as-judge

Every run writes eval/results/<git-sha>-<timestamp>.json and, with
--write-report, a single-file HTML report alongside it.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import subprocess
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import sqlglot
from app.config import get_settings
from app.models.responses import SQLGenerationResponse
from app.prompts.chat_system import SQL_GENERATION_SYSTEM
from app.services.llm import LLMService
from app.services.warehouse import DatabricksWarehouse

DIALECT = "databricks"
RESULTS_DIR = Path(__file__).parent / "results"

Generator = Callable[[dict[str, Any]], Awaitable[SQLGenerationResponse]]


@dataclass
class Score:
    value: float
    rationale: str


@dataclass
class CaseResult:
    case_id: str
    tier: str
    l1_syntax_pass: bool | None = None
    l2_structure_pass: bool | None = None
    l3_parity_pass: bool | None = None
    l4_judge_score: float | None = None
    failure_tags: list[str] = field(default_factory=list)
    detail: dict[str, Any] = field(default_factory=dict)


def git_sha() -> str:
    try:
        return (
            subprocess.check_output(
                ["git", "rev-parse", "--short", "HEAD"],
                stderr=subprocess.DEVNULL,
            )
            .decode()
            .strip()
        )
    except Exception:
        return "nogit"


def selected_columns(sql: str) -> list[str]:
    try:
        return [c.lower() for c in sqlglot.parse_one(sql, read=DIALECT).named_selects]
    except Exception:
        return []


def eval_l1(sql: str | None) -> tuple[bool | None, list[str]]:
    """None when there is no SQL to check (reject/clarify)."""
    if not sql:
        return None, []
    try:
        sqlglot.transpile(sql, read=DIALECT, write=DIALECT)
        return True, []
    except sqlglot.errors.ParseError:
        return False, ["l1_parse_error"]


def eval_l2(case: dict[str, Any], result: SQLGenerationResponse) -> tuple[bool, list[str]]:
    tags: list[str] = []

    if result.intent != case["expected_intent"]:
        tags.append("intent_mismatch")

    sql = result.sql or ""
    for pat in case.get("required_patterns", []):
        if not re.search(pat, sql, re.IGNORECASE):
            tags.append("missing_required_pattern")
            break
    for pat in case.get("forbidden_patterns", []):
        if re.search(pat, sql, re.IGNORECASE):
            tags.append("forbidden_pattern")
            break

    expected_cols = [c.lower() for c in case.get("expected_columns", [])]
    if expected_cols and sql:
        produced = set(selected_columns(sql))
        if not set(expected_cols).issubset(produced):
            tags.append("missing_columns")

    expected_chart = case.get("expected_chart_type", "none")
    actual_chart = result.chart_config.type if result.chart_config else "none"
    if expected_chart != actual_chart:
        tags.append("chart_type_mismatch")

    return (len(tags) == 0), tags


def judge(question: str, answer: str, expected: dict[str, Any]) -> Score:
    """Stubbed LLM-as-judge (Part 4.2 L4)."""
    if expected["expected_intent"] in ("reject", "clarify"):
        ok = bool(answer)
        return Score(1.0 if ok else 0.0, "non-empty response expected")
    ok = bool(answer)
    return Score(1.0 if ok else 0.0, "stub: SQL produced")


async def _default_generator(case: dict[str, Any]) -> SQLGenerationResponse:
    settings = get_settings()
    llm = LLMService(settings)
    messages = [
        {"role": "system", "content": SQL_GENERATION_SYSTEM},
        {"role": "user", "content": case["question"]},
    ]
    result, _ = await llm.chat_structured(messages, response_model=SQLGenerationResponse)
    return result


async def run_case(
    case: dict[str, Any],
    generate: Generator,
    *,
    warehouse: DatabricksWarehouse | None = None,
    table: str | None = None,
) -> CaseResult:
    cr = CaseResult(case_id=case["id"], tier=case["tier"])
    try:
        result = await generate(case)
    except Exception as exc:  # noqa: BLE001 - record, don't abort the run
        cr.failure_tags.append("generation_error")
        cr.detail["error"] = str(exc)
        return cr

    cr.detail["intent"] = result.intent
    cr.detail["sql"] = result.sql

    cr.l1_syntax_pass, l1_tags = eval_l1(result.sql)
    cr.l2_structure_pass, l2_tags = eval_l2(case, result)
    cr.failure_tags += l1_tags + l2_tags

    judged = judge(case["question"], result.sql or result.clarifying_question or "", case)
    cr.l4_judge_score = judged.value

    if warehouse is not None and result.sql and case.get("expected_sql"):
        gen_sql = result.sql
        exp_sql = case["expected_sql"].replace("{table}", table or "")
        try:
            gen_rows = await warehouse.execute(gen_sql)
            exp_rows = await warehouse.execute(exp_sql)
            cr.l3_parity_pass = len(gen_rows) == len(exp_rows)
            if not cr.l3_parity_pass:
                cr.failure_tags.append("l3_parity_mismatch")
        except Exception as exc:  # noqa: BLE001 - record, don't abort the run
            cr.l3_parity_pass = False
            cr.failure_tags.append("l3_exec_error")
            cr.detail["l3_error"] = str(exc)

    return cr


def summarize(cases: list[CaseResult]) -> dict[str, Any]:
    by_tier: dict[str, dict[str, int]] = {}
    tag_hist: dict[str, int] = {}
    for c in cases:
        bucket = by_tier.setdefault(c.tier, {"total": 0, "l1": 0, "l2": 0, "l3": 0})
        bucket["total"] += 1
        if c.l1_syntax_pass:
            bucket["l1"] += 1
        if c.l2_structure_pass:
            bucket["l2"] += 1
        if c.l3_parity_pass:
            bucket["l3"] += 1
        for tag in c.failure_tags:
            tag_hist[tag] = tag_hist.get(tag, 0) + 1
    return {"by_tier": by_tier, "failure_tags": tag_hist}


async def run(
    golden: list[dict[str, Any]],
    generate: Generator,
    *,
    warehouse: DatabricksWarehouse | None = None,
    table: str | None = None,
) -> dict[str, Any]:
    results = [await run_case(c, generate, warehouse=warehouse, table=table) for c in golden]
    sha = git_sha()
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return {
        "run_id": f"{sha}-{ts}",
        "git_sha": sha,
        "created_at": ts,
        "summary": summarize(results),
        "cases": [asdict(r) for r in results],
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="UnifiedIQ layered eval runner")
    p.add_argument("--golden", required=True, type=Path)
    p.add_argument("--run-l3", action="store_true")
    p.add_argument("--write-report", action="store_true")
    p.add_argument("--tier", choices=["core", "edge", "regression"])
    p.add_argument(
        "--table",
        default=None,
        help="Substituted for {table} in expected_sql during L3.",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    golden = json.loads(args.golden.read_text())
    if args.tier:
        golden = [c for c in golden if c["tier"] == args.tier]

    warehouse = None
    if args.run_l3:
        warehouse = DatabricksWarehouse(get_settings())

    report = asyncio.run(
        run(
            golden,
            _default_generator,
            warehouse=warehouse,
            table=args.table,
        )
    )

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out = RESULTS_DIR / f"{report['run_id']}.json"
    out.write_text(json.dumps(report, indent=2))
    print(f"wrote {out}")

    if args.write_report:
        try:
            from eval.report_template import render_report
        except ImportError:
            from report_template import render_report

        html = RESULTS_DIR / f"{report['run_id']}.html"
        html.write_text(render_report(report))
        print(f"wrote {html}")


if __name__ == "__main__":
    main()
