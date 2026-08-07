#!/usr/bin/env python3
"""Generate an HTML report from run_loop.py output."""

import argparse
import html
import json
import sys
from pathlib import Path


PAGE_START_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
__REFRESH__    <title>__TITLE__Skill Description Optimization</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@500;600&family=Lora:wght@400;500&display=swap" rel="stylesheet">
    <style>
        body {
            font-family: 'Lora', Georgia, serif;
            max-width: 100%;
            margin: 0 auto;
            padding: 20px;
            background: #faf9f5;
            color: #141413;
        }
        h1 { font-family: 'Poppins', sans-serif; color: #141413; }
        .explainer {
            background: white;
            padding: 15px;
            border-radius: 6px;
            margin-bottom: 20px;
            border: 1px solid #e8e6dc;
            color: #b0aea5;
            font-size: 0.875rem;
            line-height: 1.6;
        }
        .summary {
            background: white;
            padding: 15px;
            border-radius: 6px;
            margin-bottom: 20px;
            border: 1px solid #e8e6dc;
        }
        .summary p { margin: 5px 0; }
        .best { color: #788c5d; font-weight: bold; }
        .table-container { overflow-x: auto; width: 100%; }
        table {
            border-collapse: collapse;
            background: white;
            border: 1px solid #e8e6dc;
            border-radius: 6px;
            font-size: 12px;
            min-width: 100%;
        }
        th, td {
            padding: 8px;
            text-align: left;
            border: 1px solid #e8e6dc;
            white-space: normal;
            word-wrap: break-word;
        }
        th {
            font-family: 'Poppins', sans-serif;
            background: #141413;
            color: #faf9f5;
            font-weight: 500;
        }
        th.test-col { background: #6a9bcc; }
        th.query-col { min-width: 200px; }
        td.description {
            font-family: monospace;
            font-size: 11px;
            word-wrap: break-word;
            max-width: 400px;
        }
        td.result { text-align: center; font-size: 16px; min-width: 40px; }
        td.test-result { background: #f0f6fc; }
        .pass { color: #788c5d; }
        .fail { color: #c44; }
        .rate { font-size: 9px; color: #b0aea5; display: block; }
        tr:hover { background: #faf9f5; }
        .score {
            display: inline-block;
            padding: 2px 6px;
            border-radius: 4px;
            font-weight: bold;
            font-size: 11px;
        }
        .score-good { background: #eef2e8; color: #788c5d; }
        .score-ok { background: #fef3c7; color: #d97706; }
        .score-bad { background: #fceaea; color: #c44; }
        .train-label { color: #b0aea5; font-size: 10px; }
        .test-label { color: #6a9bcc; font-size: 10px; font-weight: bold; }
        .best-row { background: #f5f8f2; }
        th.positive-col { border-bottom: 3px solid #788c5d; }
        th.negative-col { border-bottom: 3px solid #c44; }
        th.test-col.positive-col { border-bottom: 3px solid #788c5d; }
        th.test-col.negative-col { border-bottom: 3px solid #c44; }
        .legend { font-family: 'Poppins', sans-serif; display: flex; gap: 20px; margin-bottom: 10px; font-size: 13px; align-items: center; }
        .legend-item { display: flex; align-items: center; gap: 6px; }
        .legend-swatch { width: 16px; height: 16px; border-radius: 3px; display: inline-block; }
        .swatch-positive { background: #141413; border-bottom: 3px solid #788c5d; }
        .swatch-negative { background: #141413; border-bottom: 3px solid #c44; }
        .swatch-test { background: #6a9bcc; }
        .swatch-train { background: #141413; }
    </style>
</head>
<body>
    <h1>__TITLE__Skill Description Optimization</h1>
    <div class="explainer">
        <strong>Optimizing your skill's description.</strong> This page updates automatically as the trigger evaluator tests different versions of your skill's description. Each row is an iteration — a new description attempt. The columns show test queries: green checkmarks mean the skill triggered correctly (or correctly didn't trigger), red crosses mean it got it wrong. The "Train" score shows performance on queries used to improve the description; the "Test" score shows performance on held-out queries the optimizer hasn't seen. When it's done, apply the best-performing description to your skill.
    </div>
"""

LEGEND_HTML = """
    <div class="legend">
        <span style="font-weight:600">Query columns:</span>
        <span class="legend-item"><span class="legend-swatch swatch-positive"></span> Should trigger</span>
        <span class="legend-item"><span class="legend-swatch swatch-negative"></span> Should NOT trigger</span>
        <span class="legend-item"><span class="legend-swatch swatch-train"></span> Train</span>
        <span class="legend-item"><span class="legend-swatch swatch-test"></span> Test</span>
    </div>
"""

TABLE_START_HTML = """
    <div class="table-container">
    <table>
        <thead>
            <tr>
                <th>Iter</th>
                <th>Train</th>
                <th>Test</th>
                <th class="query-col">Description</th>
"""

TABLE_BODY_HTML = """            </tr>
        </thead>
        <tbody>
"""

PAGE_END_HTML = """        </tbody>
    </table>
    </div>

</body>
</html>
"""


def _escape(value: object) -> str:
    return html.escape(str(value))


def _render_page_start(title_prefix: str, auto_refresh: bool) -> str:
    refresh_tag = '    <meta http-equiv="refresh" content="5">\n' if auto_refresh else ""
    return (
        PAGE_START_TEMPLATE
        .replace("__REFRESH__", refresh_tag)
        .replace("__TITLE__", title_prefix)
    )


def _collect_queries(history: list[dict]) -> tuple[list[dict], list[dict]]:
    if not history:
        return [], []
    first = history[0]
    train_results = first.get("train_results", first.get("results", []))
    test_results = first.get("test_results", [])
    train_queries = [
        {"query": result["query"], "should_trigger": result.get("should_trigger", True)}
        for result in train_results
    ]
    test_queries = [
        {"query": result["query"], "should_trigger": result.get("should_trigger", True)}
        for result in test_results
    ]
    return train_queries, test_queries


def _aggregate_runs(results: list[dict]) -> tuple[int, int]:
    correct = 0
    total = 0
    for result in results:
        runs = result.get("runs", 0)
        triggers = result.get("triggers", 0)
        total += runs
        correct += triggers if result.get("should_trigger", True) else runs - triggers
    return correct, total


def _score_class(correct: int, total: int) -> str:
    if total > 0:
        ratio = correct / total
        if ratio >= 0.8:
            return "score-good"
        if ratio >= 0.5:
            return "score-ok"
    return "score-bad"


def _best_iteration(history: list[dict], has_test_queries: bool) -> object | None:
    if not history:
        return None
    if has_test_queries:
        return max(history, key=lambda item: item.get("test_passed") or 0).get("iteration")
    return max(
        history,
        key=lambda item: item.get("train_passed", item.get("passed", 0)),
    ).get("iteration")


def _render_summary(data: dict) -> str:
    score_kind = "(test)" if data.get("best_test_score") else "(train)"
    return f"""
    <div class="summary">
        <p><strong>Original:</strong> {_escape(data.get('original_description', 'N/A'))}</p>
        <p class="best"><strong>Best:</strong> {_escape(data.get('best_description', 'N/A'))}</p>
        <p><strong>Best Score:</strong> {_escape(data.get('best_score', 'N/A'))} {score_kind}</p>
        <p><strong>Iterations:</strong> {_escape(data.get('iterations_run', 0))} | <strong>Train:</strong> {_escape(data.get('train_size', '?'))} | <strong>Test:</strong> {_escape(data.get('test_size', '?'))}</p>
    </div>
"""


def _render_query_headers(train_queries: list[dict], test_queries: list[dict]) -> str:
    parts: list[str] = []
    for query_info in train_queries:
        polarity = "positive-col" if query_info["should_trigger"] else "negative-col"
        parts.append(
            f'                <th class="{polarity}">{_escape(query_info["query"])}</th>\n'
        )
    for query_info in test_queries:
        polarity = "positive-col" if query_info["should_trigger"] else "negative-col"
        parts.append(
            f'                <th class="test-col {polarity}">{_escape(query_info["query"])}</th>\n'
        )
    return "".join(parts)


def _render_result_cells(
    queries: list[dict],
    results_by_query: dict[str, dict],
    *,
    test_result: bool,
) -> str:
    parts: list[str] = []
    for query_info in queries:
        result = results_by_query.get(query_info["query"], {})
        did_pass = result.get("pass", False)
        icon = "✓" if did_pass else "✗"
        css_class = "pass" if did_pass else "fail"
        test_class = " test-result" if test_result else ""
        parts.append(
            f'                <td class="result{test_class} {css_class}">{icon}'
            f'<span class="rate">{result.get("triggers", 0)}/{result.get("runs", 0)}</span></td>\n'
        )
    return "".join(parts)


def _render_iteration_row(
    item: dict,
    train_queries: list[dict],
    test_queries: list[dict],
    best_iteration: object | None,
) -> str:
    iteration = item.get("iteration", "?")
    train_results = item.get("train_results", item.get("results", []))
    test_results = item.get("test_results", [])
    train_by_query = {result["query"]: result for result in train_results}
    test_by_query = {result["query"]: result for result in test_results}
    train_correct, train_runs = _aggregate_runs(train_results)
    test_correct, test_runs = _aggregate_runs(test_results)
    row_class = "best-row" if iteration == best_iteration else ""
    parts = [f"""            <tr class="{row_class}">
                <td>{_escape(iteration)}</td>
                <td><span class="score {_score_class(train_correct, train_runs)}">{train_correct}/{train_runs}</span></td>
                <td><span class="score {_score_class(test_correct, test_runs)}">{test_correct}/{test_runs}</span></td>
                <td class="description">{_escape(item.get('description', ''))}</td>
"""]
    parts.append(_render_result_cells(train_queries, train_by_query, test_result=False))
    parts.append(_render_result_cells(test_queries, test_by_query, test_result=True))
    parts.append("            </tr>\n")
    return "".join(parts)


def generate_html(data: dict, auto_refresh: bool = False, skill_name: str = "") -> str:
    """Generate the HTML report while preserving empty-history output."""
    if not isinstance(data, dict):
        raise ValueError("Report input must be a JSON object")
    history = data.get("history", [])
    if not isinstance(history, list) or not all(isinstance(item, dict) for item in history):
        raise ValueError("history must be a list of objects")

    title_prefix = html.escape(skill_name + " — ") if skill_name else ""
    train_queries, test_queries = _collect_queries(history)
    best_iteration = _best_iteration(history, bool(test_queries))
    parts = [
        _render_page_start(title_prefix, auto_refresh),
        _render_summary(data),
        LEGEND_HTML,
        TABLE_START_HTML,
        _render_query_headers(train_queries, test_queries),
        TABLE_BODY_HTML,
    ]
    parts.extend(
        _render_iteration_row(item, train_queries, test_queries, best_iteration)
        for item in history
    )
    parts.append(PAGE_END_HTML)
    return "".join(parts)


def load_report_data(input_path: str) -> dict:
    """Load a UTF-8 JSON object from a file or stdin with actionable errors."""
    try:
        if input_path == "-":
            data = json.load(sys.stdin)
        else:
            data = json.loads(Path(input_path).read_text(encoding="utf-8-sig"))
    except FileNotFoundError as exc:
        raise ValueError(f"Input file not found: {input_path}") from exc
    except PermissionError as exc:
        raise ValueError(f"Input file is not readable: {input_path}") from exc
    except UnicodeError as exc:
        raise ValueError(f"Input file must use UTF-8 encoding: {input_path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Input JSON is invalid: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("Input JSON must be an object")
    return data


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate HTML report from run_loop output")
    parser.add_argument("input", help="Path to JSON output from run_loop.py (or - for stdin)")
    parser.add_argument("-o", "--output", default=None, help="Output HTML file (default: stdout)")
    parser.add_argument("--skill-name", default="", help="Skill name to include in the report title")
    args = parser.parse_args(argv)

    try:
        html_output = generate_html(load_report_data(args.input), skill_name=args.skill_name)
        if args.output:
            Path(args.output).write_text(html_output, encoding="utf-8")
            print(f"Report written to {args.output}", file=sys.stderr)
        else:
            print(html_output)
    except (OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
