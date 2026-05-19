"""Single-file HTML report: scorecard by tier, failure-tag histogram,
per-case diffs (Part 4.3). No external assets - inline CSS only."""

from __future__ import annotations

import html
from typing import Any

_CSS = """
body{font:14px/1.5 system-ui,sans-serif;margin:2rem;color:#111}
h1{font-size:1.4rem}h2{font-size:1.1rem;margin-top:2rem}
table{border-collapse:collapse;width:100%;margin:.5rem 0}
th,td{border:1px solid #ddd;padding:.4rem .6rem;text-align:left}
th{background:#f5f5f5}
.bar{background:#2563eb;color:#fff;padding:0 .4rem;border-radius:2px}
.pass{color:#16a34a;font-weight:600}.fail{color:#dc2626;font-weight:600}
pre{background:#f8f8f8;padding:.5rem;overflow-x:auto;white-space:pre-wrap}
.tag{display:inline-block;background:#fee2e2;color:#991b1b;border-radius:9999px;
padding:0 .5rem;margin:0 .2rem;font-size:.8rem}
"""


def _esc(value: Any) -> str:
    return html.escape(str(value))


def _scorecard(summary: dict[str, Any]) -> str:
    rows = []
    for tier, b in sorted(summary["by_tier"].items()):
        total = b["total"] or 1
        rows.append(
            f"<tr><td>{_esc(tier)}</td><td>{b['total']}</td>"
            f"<td>{b['l1']}/{b['total']} ({100 * b['l1'] // total}%)</td>"
            f"<td>{b['l2']}/{b['total']} ({100 * b['l2'] // total}%)</td>"
            f"<td>{b['l3']}/{b['total']} ({100 * b['l3'] // total}%)</td></tr>"
        )
    return (
        "<table><tr><th>Tier</th><th>Cases</th><th>L1 syntax</th>"
        "<th>L2 structure</th><th>L3 parity</th></tr>" + "".join(rows) + "</table>"
    )


def _histogram(tag_hist: dict[str, int]) -> str:
    if not tag_hist:
        return "<p>No failure tags. 🎉</p>".replace("🎉", "")
    mx = max(tag_hist.values())
    rows = []
    for tag, n in sorted(tag_hist.items(), key=lambda kv: -kv[1]):
        width = max(1, int(40 * n / mx))
        rows.append(
            f"<tr><td>{_esc(tag)}</td><td><span class='bar'>{'&nbsp;' * width}</span> {n}</td></tr>"
        )
    return "<table><tr><th>Failure tag</th><th>Count</th></tr>" + "".join(rows) + "</table>"


def _cases(cases: list[dict[str, Any]]) -> str:
    out = []
    for c in cases:
        tags = "".join(f"<span class='tag'>{_esc(t)}</span>" for t in c.get("failure_tags", []))

        def mark(v: Any) -> str:
            if v is None:
                return "-"
            return "<span class='pass'>pass</span>" if v else "<span class='fail'>fail</span>"

        out.append(
            f"<h3>{_esc(c['case_id'])} "
            f"<small>({_esc(c['tier'])})</small></h3>"
            f"<p>L1 {mark(c['l1_syntax_pass'])} &middot; "
            f"L2 {mark(c['l2_structure_pass'])} &middot; "
            f"L3 {mark(c['l3_parity_pass'])} &middot; "
            f"L4 {_esc(c['l4_judge_score'])}</p>"
            f"<p>{tags or 'no failures'}</p>"
            f"<pre>{_esc(c['detail'].get('sql') or c['detail'])}</pre>"
        )
    return "".join(out)


def render_report(report: dict[str, Any]) -> str:
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>UnifiedIQ eval {_esc(report['run_id'])}</title>"
        f"<style>{_CSS}</style></head><body>"
        f"<h1>UnifiedIQ Eval Report</h1>"
        f"<p>run_id <code>{_esc(report['run_id'])}</code> &middot; "
        f"git <code>{_esc(report['git_sha'])}</code> &middot; "
        f"{_esc(report['created_at'])}</p>"
        f"<h2>Scorecard by tier</h2>{_scorecard(report['summary'])}"
        f"<h2>Failure-tag histogram</h2>"
        f"{_histogram(report['summary']['failure_tags'])}"
        f"<h2>Per-case detail</h2>{_cases(report['cases'])}"
        "</body></html>"
    )
