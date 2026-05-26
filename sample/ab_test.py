#!/usr/bin/env python3
"""
Errordog A/B Test: Stacktrace-only vs. Errordog MCP tools

Compares token usage and diagnostic accuracy between:
  A — GPT receives only the raw stacktrace (traditional approach)
  B — GPT uses Errordog function-calling tools (dap_get_variables, dap_drill_into, …)

Prerequisites:
  1. Errordog HTTP server running in a separate terminal:
       errordog serve --http --port=8080
  2. OPENAI_API_KEY environment variable set
  3. openai and requests packages installed:
       pip install openai requests

Usage:
  python ab_test.py                           # all 5 scenarios
  python ab_test.py --scenarios orders,payment
  python ab_test.py --model gpt-4o --output results.json
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

import requests

try:
    from openai import OpenAI
except ImportError:
    print("Error: openai not installed.  Run: pip install openai requests")
    sys.exit(1)

# ── Config ────────────────────────────────────────────────────────────────────

ERRORDOG_BASE_URL = "http://localhost:8080"
SAMPLE_DIR = Path(__file__).parent
PROJECT_DIR = SAMPLE_DIR.parent
DEFAULT_MODEL = "gpt-4o-mini"
MAX_TOOL_TURNS = 8  # prevent infinite loops in condition B

SYSTEM_PROMPT = (
    "You are a Python debugging expert. "
    "Identify the exact root cause with specific variable values as evidence. "
    "Be concise — 2-3 sentences maximum."
)

# ── Scenarios ─────────────────────────────────────────────────────────────────

SCENARIOS: list[dict] = [
    {
        "name": "orders",
        "description": "TypeError — string price × int quantity",
        "script": "orders.py",
        "ground_truth_keywords": ["free", "'free'", "string", "str"],
    },
    {
        "name": "payment",
        "description": "ValueError — discount rate > 1 causes negative amount",
        "script": "payment.py",
        "ground_truth_keywords": ["1.5", "rate", "discount", "INVALID_CODE"],
    },
    {
        "name": "inventory",
        "description": "ZeroDivisionError — avg_stock is 0 for discontinued category",
        "script": "inventory.py",
        "ground_truth_keywords": ["Discontinued", "discontinued", "zero", "avg_stock", "0"],
    },
    {
        "name": "user_auth",
        "description": "KeyError — 'role' key missing from permissions dict",
        "script": "user_auth.py",
        "ground_truth_keywords": ["role", "'role'", "viewer", "u_002", "permissions"],
    },
    {
        "name": "report_gen",
        "description": "TypeError — fetch_sales_data returns None for unknown region",
        "script": "report_gen.py",
        "ground_truth_keywords": ["None", "Daegu", "NoneType", "database.get"],
    },
]

# ── OpenAI tool definitions (mirrors Errordog HTTP endpoints) ─────────────────

ERRORDOG_TOOLS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "list_errors",
            "description": (
                "Return list of stored error snapshots sorted by timestamp descending. "
                "Call this first to get the error_id of the most recent error."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "dap_get_stack_frames",
            "description": (
                "Get stack frames for a snapshot. "
                "frame_index=0 is the crash point (innermost frame). "
                "Use the returned frame_index in dap_get_variables."
            ),
            "parameters": {
                "type": "object",
                "properties": {"error_id": {"type": "string", "description": "Error ID from list_errors"}},
                "required": ["error_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "dap_get_variables",
            "description": (
                "Get local variables for a specific stack frame. "
                "If a variable's variablesReference > 0, call dap_drill_into to expand it."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "error_id": {"type": "string"},
                    "frame_index": {"type": "integer", "default": 0, "description": "0 = crash point"},
                },
                "required": ["error_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "dap_drill_into",
            "description": (
                "Drill into a nested object (dict, list, tuple) using its variablesReference. "
                "Returns child variables. Use when variablesReference > 0 from dap_get_variables."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "error_id": {"type": "string"},
                    "variables_reference": {"type": "integer", "description": "variablesReference from dap_get_variables or previous dap_drill_into"},
                },
                "required": ["error_id", "variables_reference"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "evaluate_expression",
            "description": "Evaluate a Python expression against the locals of a snapshot frame.",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {"type": "string", "description": "Python expression to evaluate"},
                    "error_id": {"type": "string"},
                    "frame_index": {"type": "integer", "default": 0},
                },
                "required": ["expression", "error_id"],
            },
        },
    },
]

# ── Result dataclasses ────────────────────────────────────────────────────────


@dataclass
class ConditionResult:
    condition: str                    # "A" or "B"
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    tool_calls: int = 0               # B only
    response_time_s: float = 0.0
    final_response: str = ""
    matched_keywords: list[str] = field(default_factory=list)
    specificity_score: float = 0.0   # matched / total keywords
    root_cause_identified: bool = False
    error: str = ""


@dataclass
class ScenarioResult:
    scenario_name: str
    description: str
    error_id: str
    stacktrace: str
    condition_a: ConditionResult
    condition_b: ConditionResult


# ── Helpers ───────────────────────────────────────────────────────────────────


def check_server() -> bool:
    """Return True if Errordog HTTP server is reachable."""
    try:
        resp = requests.get(f"{ERRORDOG_BASE_URL}/health", timeout=3)
        return resp.status_code == 200
    except Exception:
        return False


def call_errordog_http(tool_name: str, args: dict) -> str:
    """Call an Errordog HTTP endpoint and return JSON string result."""
    try:
        resp = requests.post(
            f"{ERRORDOG_BASE_URL}/tools/{tool_name}",
            json=args,
            timeout=10,
        )
        return json.dumps(resp.json())
    except Exception as exc:
        return json.dumps({"error": str(exc)})


def run_scenario_script(script_name: str) -> tuple[str, str | None]:
    """
    Run a sample scenario script and return (stderr_output, error_id).
    The script auto-saves an Errordog snapshot via `import errordog.tracker`.
    """
    script_path = SAMPLE_DIR / script_name
    result = subprocess.run(
        [sys.executable, str(script_path)],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_DIR),  # ensure errordog is importable via uv
    )
    # Combine stderr lines, strip the "[errordog] Snapshot captured: ..." line
    # to give Condition A the same info a developer would see
    lines = result.stderr.splitlines()
    snapshot_line = next((l for l in lines if "[errordog] Snapshot captured:" in l), None)
    error_id = snapshot_line.split("Snapshot captured:")[-1].strip() if snapshot_line else None
    clean_stderr = "\n".join(l for l in lines if "[errordog]" not in l)
    return clean_stderr.strip(), error_id


def _run_with_uv(script_name: str) -> tuple[str, str | None]:
    """Fallback: run via `uv run` if direct python fails."""
    script_path = SAMPLE_DIR / script_name
    result = subprocess.run(
        ["uv", "run", "--directory", str(PROJECT_DIR), "python", str(script_path)],
        capture_output=True,
        text=True,
    )
    lines = result.stderr.splitlines()
    snapshot_line = next((l for l in lines if "[errordog] Snapshot captured:" in l), None)
    error_id = snapshot_line.split("Snapshot captured:")[-1].strip() if snapshot_line else None
    clean_stderr = "\n".join(l for l in lines if "[errordog]" not in l)
    return clean_stderr.strip(), error_id


def score_response(text: str, keywords: list[str]) -> tuple[list[str], float, bool]:
    """Return (matched_keywords, specificity_score, root_cause_identified)."""
    text_lower = text.lower()
    matched = [kw for kw in keywords if kw.lower() in text_lower]
    score = len(matched) / len(keywords) if keywords else 0.0
    identified = score >= 0.5  # at least half the keywords → root cause found
    return matched, round(score, 2), identified


# ── Condition A: Stacktrace only ──────────────────────────────────────────────


def run_condition_a(
    stacktrace: str,
    keywords: list[str],
    client: OpenAI,
    model: str,
) -> ConditionResult:
    result = ConditionResult(condition="A")
    prompt = (
        "A Python error occurred. Identify the exact root cause.\n\n"
        f"```\n{stacktrace}\n```"
    )
    try:
        t0 = time.perf_counter()
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            max_tokens=300,
        )
        result.response_time_s = round(time.perf_counter() - t0, 2)
        usage = response.usage
        result.prompt_tokens = usage.prompt_tokens
        result.completion_tokens = usage.completion_tokens
        result.total_tokens = usage.total_tokens
        result.final_response = response.choices[0].message.content or ""
        result.matched_keywords, result.specificity_score, result.root_cause_identified = (
            score_response(result.final_response, keywords)
        )
    except Exception as exc:
        result.error = str(exc)
    return result


# ── Condition B: Errordog tools ───────────────────────────────────────────────


def run_condition_b(
    error_id: str,
    keywords: list[str],
    client: OpenAI,
    model: str,
) -> ConditionResult:
    result = ConditionResult(condition="B")
    messages: list[dict] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Use the Errordog tools to diagnose error `{error_id}`. "
                "Start with dap_get_stack_frames, inspect variables at the crash frame, "
                "drill into nested objects as needed, then state the exact root cause."
            ),
        },
    ]
    try:
        t0 = time.perf_counter()
        for _ in range(MAX_TOOL_TURNS):
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                tools=ERRORDOG_TOOLS,
                tool_choice="auto",
                max_tokens=500,
            )
            usage = response.usage
            result.prompt_tokens += usage.prompt_tokens
            result.completion_tokens += usage.completion_tokens
            result.total_tokens += usage.total_tokens

            choice = response.choices[0]
            messages.append(choice.message.model_dump(exclude_unset=False))

            if choice.finish_reason == "stop":
                result.final_response = choice.message.content or ""
                break

            if choice.finish_reason == "tool_calls" and choice.message.tool_calls:
                for tc in choice.message.tool_calls:
                    result.tool_calls += 1
                    args = json.loads(tc.function.arguments)
                    tool_result = call_errordog_http(tc.function.name, args)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": tool_result,
                    })

        result.response_time_s = round(time.perf_counter() - t0, 2)
        result.matched_keywords, result.specificity_score, result.root_cause_identified = (
            score_response(result.final_response, keywords)
        )
    except Exception as exc:
        result.error = str(exc)
    return result


# ── Output ────────────────────────────────────────────────────────────────────

_CHECK = "✓"
_CROSS = "✗"
_SEP = "─" * 67


def print_scenario(sr: ScenarioResult) -> None:
    a, b = sr.condition_a, sr.condition_b
    print(f"\n{_SEP}")
    print(f"Scenario : {sr.scenario_name} — {sr.description}")
    print(f"Error ID : {sr.error_id}")
    print(_SEP)
    print(f"{'Metric':<28} {'A: Stacktrace':>16} {'B: Errordog':>18}")
    print(_SEP)
    print(f"{'Input tokens':<28} {a.prompt_tokens:>16,} {b.prompt_tokens:>18,}")
    print(f"{'Output tokens':<28} {a.completion_tokens:>16,} {b.completion_tokens:>18,}")
    print(f"{'Total tokens':<28} {a.total_tokens:>16,} {b.total_tokens:>18,}")
    print(f"{'Tool calls':<28} {0:>16} {b.tool_calls:>18}")
    print(f"{'Response time (s)':<28} {a.response_time_s:>16.1f} {b.response_time_s:>18.1f}")
    kw_total = len(sr.condition_a.matched_keywords or b.matched_keywords or [])
    print(f"{'Specificity score':<28} {a.specificity_score:>15.0%} {b.specificity_score:>17.0%}")
    a_id = f"{_CHECK} Yes" if a.root_cause_identified else f"{_CROSS} Partial"
    b_id = f"{_CHECK} Yes" if b.root_cause_identified else f"{_CROSS} Partial"
    print(f"{'Root cause identified':<28} {a_id:>16} {b_id:>18}")
    print(_SEP)
    if a.final_response:
        preview = a.final_response[:120].replace("\n", " ")
        print(f"  A: {preview}{'…' if len(a.final_response) > 120 else ''}")
    if b.final_response:
        preview = b.final_response[:120].replace("\n", " ")
        print(f"  B: {preview}{'…' if len(b.final_response) > 120 else ''}")
    if a.error:
        print(f"  A error: {a.error}")
    if b.error:
        print(f"  B error: {b.error}")


def print_summary(results: list[ScenarioResult]) -> None:
    if not results:
        return
    print(f"\n{'═' * 67}")
    print("SUMMARY")
    print(f"{'═' * 67}")
    print(f"{'Metric':<28} {'A: Stacktrace':>16} {'B: Errordog':>18}")
    print(f"{'─' * 67}")

    def avg(vals: list) -> float:
        return sum(vals) / len(vals) if vals else 0

    a_tokens = [r.condition_a.total_tokens for r in results if not r.condition_a.error]
    b_tokens = [r.condition_b.total_tokens for r in results if not r.condition_b.error]
    a_time = [r.condition_a.response_time_s for r in results if not r.condition_a.error]
    b_time = [r.condition_b.response_time_s for r in results if not r.condition_b.error]
    b_tools = [r.condition_b.tool_calls for r in results if not r.condition_b.error]
    a_spec = [r.condition_a.specificity_score for r in results if not r.condition_a.error]
    b_spec = [r.condition_b.specificity_score for r in results if not r.condition_b.error]
    a_found = sum(1 for r in results if r.condition_a.root_cause_identified)
    b_found = sum(1 for r in results if r.condition_b.root_cause_identified)
    n = len(results)

    print(f"{'Avg total tokens':<28} {avg(a_tokens):>16,.0f} {avg(b_tokens):>18,.0f}")
    print(f"{'Avg tool calls':<28} {'0':>16} {avg(b_tools):>18.1f}")
    print(f"{'Avg response time (s)':<28} {avg(a_time):>16.1f} {avg(b_time):>18.1f}")
    print(f"{'Avg specificity':<28} {avg(a_spec):>15.0%} {avg(b_spec):>17.0%}")
    print(f"{'Root cause found':<28} {a_found}/{n} ({a_found/n:.0%}){b_found:>14}/{n} ({b_found/n:.0%})")
    print(f"{'═' * 67}\n")


# ── Main ──────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description="Errordog A/B test")
    parser.add_argument(
        "--scenarios",
        default="all",
        help="Comma-separated scenario names (all | orders,payment,…)",
    )
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"OpenAI model (default: {DEFAULT_MODEL})")
    parser.add_argument("--output", default="", help="Save JSON results to this file path")
    parser.add_argument(
        "--no-run",
        action="store_true",
        help="Skip running scenario scripts (use existing snapshots)",
    )
    args = parser.parse_args()

    # Validate API key
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        print("Error: OPENAI_API_KEY environment variable not set.")
        sys.exit(1)

    # Validate server
    if not check_server():
        print(
            f"Error: Errordog HTTP server not reachable at {ERRORDOG_BASE_URL}\n"
            "Start it with:  errordog serve --http --port=8080"
        )
        sys.exit(1)

    # Filter scenarios
    selected_names = set(args.scenarios.split(",")) if args.scenarios != "all" else None
    scenarios = [s for s in SCENARIOS if selected_names is None or s["name"] in selected_names]
    if not scenarios:
        print(f"Error: No scenarios match '{args.scenarios}'")
        sys.exit(1)

    client = OpenAI(api_key=api_key)

    print(f"\nErrordog A/B Test  |  model={args.model}  |  scenarios={len(scenarios)}")
    print(f"Condition A: stacktrace only  |  Condition B: Errordog tools\n")

    all_results: list[ScenarioResult] = []

    for scenario in scenarios:
        name = scenario["name"]
        print(f"Running scenario: {name} …", end=" ", flush=True)

        # Step 1: Run script to capture stacktrace + snapshot
        stacktrace = ""
        error_id = ""

        if args.no_run:
            # Use most recent snapshot from Errordog
            resp = requests.post(f"{ERRORDOG_BASE_URL}/tools/list_errors", json={}, timeout=5)
            errors = resp.json()
            error_id = errors[0]["error_id"] if errors else ""
            stacktrace = f"(existing snapshot: {error_id})"
        else:
            stderr, eid = run_scenario_script(scenario["script"])
            if not eid:
                # Fallback to uv run
                stderr, eid = _run_with_uv(scenario["script"])
            stacktrace = stderr
            error_id = eid or ""

        if not error_id:
            print("SKIP (no snapshot)")
            continue

        print(f"snapshot={error_id[:28]}…")
        keywords = scenario["ground_truth_keywords"]

        # Step 2: Condition A
        print("  Running condition A (stacktrace only) …", end=" ", flush=True)
        cond_a = run_condition_a(stacktrace, keywords, client, args.model)
        print(f"done ({cond_a.total_tokens} tokens, {cond_a.response_time_s}s)")

        # Step 3: Condition B
        print("  Running condition B (Errordog tools) …", end=" ", flush=True)
        cond_b = run_condition_b(error_id, keywords, client, args.model)
        print(f"done ({cond_b.total_tokens} tokens, {cond_b.tool_calls} tool calls, {cond_b.response_time_s}s)")

        sr = ScenarioResult(
            scenario_name=name,
            description=scenario["description"],
            error_id=error_id,
            stacktrace=stacktrace,
            condition_a=cond_a,
            condition_b=cond_b,
        )
        all_results.append(sr)
        print_scenario(sr)

    print_summary(all_results)

    # Optionally save JSON
    if args.output:
        output_path = Path(args.output)
        output_path.write_text(
            json.dumps(
                {
                    "model": args.model,
                    "results": [asdict(r) for r in all_results],
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        print(f"Results saved to {output_path}")


if __name__ == "__main__":
    main()
