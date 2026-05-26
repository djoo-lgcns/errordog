#!/usr/bin/env python3
"""
Errordog A/B Test — stacktrace-only vs. Errordog MCP tools (via Codex CLI)

Compares diagnostic accuracy between:
  A — Codex receives only the raw stacktrace (traditional approach)
  B — Codex uses Errordog MCP tools via dap_get_stack_frames / dap_get_variables / dap_drill_into

Both conditions use `codex exec` (non-interactive subprocess).
Condition A runs with an isolated HOME so MCP servers are not loaded.
Condition B uses the real HOME where errordog is configured in ~/.codex/config.toml.

Prerequisites:
  1. codex CLI installed and authenticated  (codex --version)
  2. errordog MCP added to ~/.codex/config.toml  (see sample/.codex/config.toml for template)
  3. uv sync run in project root

Usage:
  python ab_test.py                          # all 5 scenarios
  python ab_test.py --scenarios orders,payment
  python ab_test.py --output results.json
  python ab_test.py --codex codex            # override codex binary path
  python ab_test.py --no-run                 # skip re-running scripts, use existing snapshots
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────

SAMPLE_DIR = Path(__file__).parent
PROJECT_DIR = SAMPLE_DIR.parent
DEFAULT_CODEX = "codex"
MAX_WAIT_S = 120  # per-condition timeout

PROMPT_A = """\
A Python error occurred. Identify the exact root cause using only the stacktrace below.
Do NOT call any external tools. Reply in 2-3 sentences with specific variable values as evidence.

```
{stacktrace}
```"""

PROMPT_B = """\
Use Errordog MCP tools to diagnose error ID: {error_id}

Follow this sequence:
1. dap_get_stack_frames — inspect the call stack
2. dap_get_variables(frame_index=0) — get locals at the crash point
3. dap_drill_into — expand any nested object whose variablesReference > 0

Reply in 2-3 sentences stating the exact root cause with specific variable values."""

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
        "ground_truth_keywords": ["Discontinued", "discontinued", "avg_stock", "0"],
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

# ── Result dataclasses ────────────────────────────────────────────────────────


@dataclass
class ConditionResult:
    condition: str                          # "A" or "B"
    input_tokens: int = 0                   # sum across all turns
    cached_tokens: int = 0                  # cached_input_tokens (cost saving)
    output_tokens: int = 0
    total_tokens: int = 0
    tool_calls: int = 0                     # MCP tool calls (B only)
    tool_names: list[str] = field(default_factory=list)
    response_time_s: float = 0.0
    final_response: str = ""
    matched_keywords: list[str] = field(default_factory=list)
    specificity_score: float = 0.0          # matched / total keywords
    root_cause_identified: bool = False     # score >= 0.5
    error: str = ""


@dataclass
class ScenarioResult:
    scenario_name: str
    description: str
    error_id: str
    stacktrace: str
    condition_a: ConditionResult
    condition_b: ConditionResult


# ── Codex subprocess ──────────────────────────────────────────────────────────


@dataclass
class _Usage:
    input_tokens: int = 0
    cached_tokens: int = 0
    output_tokens: int = 0

    @property
    def total(self) -> int:
        return self.input_tokens + self.output_tokens

    def __iadd__(self, other: "_Usage") -> "_Usage":
        self.input_tokens += other.input_tokens
        self.cached_tokens += other.cached_tokens
        self.output_tokens += other.output_tokens
        return self


def run_codex(
    prompt: str,
    codex_cmd: str,
    isolate_mcp: bool,
) -> tuple[str, float, int, list[str], _Usage]:
    """
    Run `codex exec` and return (response_text, elapsed_s, tool_call_count, tool_names, usage).

    Token counts come from `turn.completed` events in the JSONL stream.
    For multi-turn (Condition B), all turns are summed.

    isolate_mcp=True  → fake HOME so ~/.codex/config.toml is not loaded (Condition A)
    isolate_mcp=False → real HOME with errordog MCP configured (Condition B)
    """
    tmp_out = tempfile.mktemp(suffix=".txt")
    cmd = [
        codex_cmd,
        "--ask-for-approval", "never",
        "--sandbox", "read-only",
        "exec",
        "--color", "never",
        "--json",
        "--output-last-message", tmp_out,
        "-",
    ]

    env = os.environ.copy()
    fake_home: str | None = None
    if isolate_mcp:
        fake_home = tempfile.mkdtemp(prefix="ab_cond_a_")
        env["HOME"] = fake_home

    t0 = time.perf_counter()
    try:
        proc = subprocess.run(
            cmd,
            input=prompt,
            capture_output=True,
            text=True,
            env=env,
            timeout=MAX_WAIT_S,
        )
    except subprocess.TimeoutExpired:
        return f"(timeout after {MAX_WAIT_S}s)", MAX_WAIT_S, 0, [], _Usage()
    elapsed = time.perf_counter() - t0

    # Parse JSONL: collect tool calls and sum token usage across all turns
    tool_calls = 0
    tool_names: list[str] = []
    usage = _Usage()

    for raw in proc.stdout.splitlines():
        try:
            event = json.loads(raw)
        except json.JSONDecodeError:
            continue

        etype = event.get("type")

        # MCP tool call events
        if etype == "item.completed" and event.get("item", {}).get("type") == "tool_call":
            tool_calls += 1
            tool_names.append(event["item"].get("name", "unknown"))

        # Token usage — emitted once per turn, sum across multi-turn
        elif etype == "turn.completed":
            u = event.get("usage", {})
            usage += _Usage(
                input_tokens=u.get("input_tokens", 0),
                cached_tokens=u.get("cached_input_tokens", 0),
                output_tokens=u.get("output_tokens", 0),
            )

    # Read final response from file written by --output-last-message
    out_path = Path(tmp_out)
    if out_path.exists():
        response = out_path.read_text(encoding="utf-8").strip()
        out_path.unlink(missing_ok=True)
    else:
        # Fallback: parse last agent_message from JSONL
        response = ""
        for raw in reversed(proc.stdout.splitlines()):
            try:
                event = json.loads(raw)
                if (
                    event.get("type") == "item.completed"
                    and event.get("item", {}).get("type") == "agent_message"
                ):
                    response = event["item"].get("text", "")
                    break
            except (json.JSONDecodeError, KeyError):
                continue
        if not response and proc.stderr:
            response = f"(stderr) {proc.stderr[:300]}"

    # Clean up fake home
    if fake_home:
        import shutil
        shutil.rmtree(fake_home, ignore_errors=True)

    return response, round(elapsed, 2), tool_calls, tool_names, usage


# ── Scenario script runner ────────────────────────────────────────────────────


def run_scenario_script(script_name: str) -> tuple[str, str | None]:
    """
    Run a sample script, return (stacktrace_text, error_id).
    Strips the [errordog] capture line so Condition A only sees the raw traceback.
    """
    script_path = SAMPLE_DIR / script_name
    result = subprocess.run(
        ["uv", "run", "--directory", str(PROJECT_DIR), "python", str(script_path)],
        capture_output=True,
        text=True,
    )
    lines = result.stderr.splitlines()
    snapshot_line = next(
        (l for l in lines if "[errordog] Snapshot captured:" in l), None
    )
    error_id = (
        snapshot_line.split("Snapshot captured:")[-1].strip() if snapshot_line else None
    )
    clean_stderr = "\n".join(l for l in lines if "[errordog]" not in l)
    return clean_stderr.strip(), error_id


# ── Scoring ───────────────────────────────────────────────────────────────────


def score_response(
    text: str, keywords: list[str]
) -> tuple[list[str], float, bool]:
    text_lower = text.lower()
    matched = [kw for kw in keywords if kw.lower() in text_lower]
    score = len(matched) / len(keywords) if keywords else 0.0
    return matched, round(score, 2), score >= 0.5


# ── Condition runners ─────────────────────────────────────────────────────────


def run_condition_a(
    stacktrace: str, keywords: list[str], codex_cmd: str
) -> ConditionResult:
    result = ConditionResult(condition="A")
    try:
        response, elapsed, _, _, usage = run_codex(
            PROMPT_A.format(stacktrace=stacktrace),
            codex_cmd=codex_cmd,
            isolate_mcp=True,
        )
        result.final_response = response
        result.response_time_s = elapsed
        result.input_tokens = usage.input_tokens
        result.cached_tokens = usage.cached_tokens
        result.output_tokens = usage.output_tokens
        result.total_tokens = usage.total
        result.matched_keywords, result.specificity_score, result.root_cause_identified = (
            score_response(response, keywords)
        )
    except Exception as exc:
        result.error = str(exc)
    return result


def run_condition_b(
    error_id: str, keywords: list[str], codex_cmd: str
) -> ConditionResult:
    result = ConditionResult(condition="B")
    try:
        response, elapsed, tool_calls, tool_names, usage = run_codex(
            PROMPT_B.format(error_id=error_id),
            codex_cmd=codex_cmd,
            isolate_mcp=False,
        )
        result.final_response = response
        result.response_time_s = elapsed
        result.tool_calls = tool_calls
        result.tool_names = tool_names
        result.input_tokens = usage.input_tokens
        result.cached_tokens = usage.cached_tokens
        result.output_tokens = usage.output_tokens
        result.total_tokens = usage.total
        result.matched_keywords, result.specificity_score, result.root_cause_identified = (
            score_response(response, keywords)
        )
    except Exception as exc:
        result.error = str(exc)
    return result


# ── Output ────────────────────────────────────────────────────────────────────

_SEP = "─" * 67
_CHECK = "✓"
_CROSS = "✗"


def print_scenario(sr: ScenarioResult) -> None:
    a, b = sr.condition_a, sr.condition_b
    print(f"\n{_SEP}")
    print(f"Scenario : {sr.scenario_name} — {sr.description}")
    print(f"Error ID : {sr.error_id}")
    print(_SEP)
    print(f"{'Metric':<28} {'A: Stacktrace':>16} {'B: Errordog':>18}")
    print(_SEP)
    print(f"{'Input tokens':<28} {a.input_tokens:>16,} {b.input_tokens:>18,}")
    print(f"{'  (cached)':<28} {a.cached_tokens:>16,} {b.cached_tokens:>18,}")
    print(f"{'Output tokens':<28} {a.output_tokens:>16,} {b.output_tokens:>18,}")
    print(f"{'Total tokens':<28} {a.total_tokens:>16,} {b.total_tokens:>18,}")
    print(f"{'MCP tool calls':<28} {'0':>16} {b.tool_calls:>18}")
    if b.tool_names:
        names = ", ".join(b.tool_names)
        print(f"{'  tools used':<28} {'':>16} {names[:18]:>18}")
    print(f"{'Response time (s)':<28} {a.response_time_s:>16.1f} {b.response_time_s:>18.1f}")
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
        return sum(vals) / len(vals) if vals else 0.0

    a_in = [r.condition_a.input_tokens for r in results if not r.condition_a.error]
    b_in = [r.condition_b.input_tokens for r in results if not r.condition_b.error]
    a_out = [r.condition_a.output_tokens for r in results if not r.condition_a.error]
    b_out = [r.condition_b.output_tokens for r in results if not r.condition_b.error]
    a_tot = [r.condition_a.total_tokens for r in results if not r.condition_a.error]
    b_tot = [r.condition_b.total_tokens for r in results if not r.condition_b.error]
    a_time = [r.condition_a.response_time_s for r in results if not r.condition_a.error]
    b_time = [r.condition_b.response_time_s for r in results if not r.condition_b.error]
    b_tools = [r.condition_b.tool_calls for r in results if not r.condition_b.error]
    a_spec = [r.condition_a.specificity_score for r in results if not r.condition_a.error]
    b_spec = [r.condition_b.specificity_score for r in results if not r.condition_b.error]
    a_found = sum(1 for r in results if r.condition_a.root_cause_identified)
    b_found = sum(1 for r in results if r.condition_b.root_cause_identified)
    n = len(results)

    print(f"{'Avg input tokens':<28} {avg(a_in):>16,.0f} {avg(b_in):>18,.0f}")
    print(f"{'Avg output tokens':<28} {avg(a_out):>16,.0f} {avg(b_out):>18,.0f}")
    print(f"{'Avg total tokens':<28} {avg(a_tot):>16,.0f} {avg(b_tot):>18,.0f}")
    print(f"{'Avg MCP tool calls':<28} {'0':>16} {avg(b_tools):>18.1f}")
    print(f"{'Avg response time (s)':<28} {avg(a_time):>16.1f} {avg(b_time):>18.1f}")
    print(f"{'Avg specificity':<28} {avg(a_spec):>15.0%} {avg(b_spec):>17.0%}")
    print(f"{'Root cause found':<28} {a_found}/{n} ({a_found/n:.0%}){b_found:>14}/{n} ({b_found/n:.0%})")
    print(f"{'═' * 67}\n")


# ── Main ──────────────────────────────────────────────────────────────────────


def check_codex(codex_cmd: str) -> bool:
    try:
        result = subprocess.run(
            [codex_cmd, "--version"], capture_output=True, text=True, timeout=10
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Errordog A/B test via Codex CLI")
    parser.add_argument(
        "--scenarios",
        default="all",
        help="Comma-separated scenario names (default: all)",
    )
    parser.add_argument(
        "--codex",
        default=DEFAULT_CODEX,
        help=f"Path to codex binary (default: {DEFAULT_CODEX})",
    )
    parser.add_argument(
        "--output",
        default="",
        help="Save JSON results to this file",
    )
    parser.add_argument(
        "--no-run",
        action="store_true",
        help="Skip running scenario scripts; use the most recent existing snapshot",
    )
    args = parser.parse_args()

    # Verify codex is available
    if not check_codex(args.codex):
        print(f"Error: codex CLI not found at '{args.codex}'")
        print("Install: https://github.com/openai/codex")
        sys.exit(1)

    # Filter scenarios
    selected = set(args.scenarios.split(",")) if args.scenarios != "all" else None
    scenarios = [s for s in SCENARIOS if selected is None or s["name"] in selected]
    if not scenarios:
        print(f"Error: no scenarios match '{args.scenarios}'")
        sys.exit(1)

    print(f"\nErrordog A/B Test  |  codex={args.codex}  |  scenarios={len(scenarios)}")
    print("Condition A: stacktrace only (MCP isolated)")
    print("Condition B: Errordog MCP tools (dap_get_stack_frames → dap_get_variables → dap_drill_into)\n")

    all_results: list[ScenarioResult] = []

    for scenario in scenarios:
        name = scenario["name"]
        print(f"── Scenario: {name} ──")

        # Step 1: run script to generate snapshot
        stacktrace = ""
        error_id = ""

        if args.no_run:
            # Import errordog store directly to get most recent snapshot
            sys.path.insert(0, str(PROJECT_DIR / "src"))
            from errordog.store import SnapshotStore
            store = SnapshotStore()
            summaries = store.list_summaries()
            if summaries:
                error_id = summaries[0].error_id
                stacktrace = f"(existing snapshot: {error_id})"
            else:
                print("  SKIP — no snapshots found")
                continue
        else:
            print(f"  Running {scenario['script']} …", end=" ", flush=True)
            stacktrace, error_id = run_scenario_script(scenario["script"])
            if error_id:
                print(f"snapshot={error_id[:32]}…")
            else:
                print("SKIP (no snapshot captured)")
                continue

        keywords = scenario["ground_truth_keywords"]

        # Step 2: Condition A
        print("  Condition A (stacktrace only) …", end=" ", flush=True)
        cond_a = run_condition_a(stacktrace, keywords, args.codex)
        status_a = f"done ({cond_a.response_time_s}s)" if not cond_a.error else f"ERROR: {cond_a.error[:60]}"
        print(status_a)

        # Step 3: Condition B
        print("  Condition B (Errordog MCP) …", end=" ", flush=True)
        cond_b = run_condition_b(error_id, keywords, args.codex)
        status_b = (
            f"done ({cond_b.tool_calls} tool calls, {cond_b.response_time_s}s)"
            if not cond_b.error
            else f"ERROR: {cond_b.error[:60]}"
        )
        print(status_b)

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

    if args.output:
        out = Path(args.output)
        out.write_text(
            json.dumps(
                {"results": [asdict(r) for r in all_results]},
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        print(f"Results saved → {out}")


if __name__ == "__main__":
    main()
