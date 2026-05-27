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

Step 1. Call dap_get_stack_frames(error_id).
  Read exception_type and exception_message to understand what went wrong.
  frame_index=0 is the crash point (innermost frame).

Step 2. Call dap_get_variables(error_id, frame_index=0).
  Each variable has a "value" field with its full Python repr — read this first.
  - If the bad value is readable directly from "value" or exception_message, \
state the root cause. Do NOT call dap_drill_into.
  - Only call dap_drill_into if "value" is too large or truncated to identify the \
specific bad value (e.g. a long list where the offending element is not obvious).
    - Drill into the ONE most suspicious variable. Stop as soon as the bad value is clear.

Reply in 2-3 sentences. Name the exact bad value literally (e.g. 'free', 'Daegu', None, 1.5) \
— not just its type. Include the variable name, function name, and line number."""

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
    input_tokens: int = 0                  # raw input_tokens from turn.completed (cache-independent)
    net_input_tokens: int = 0             # input_tokens - cached_input_tokens (actual processing cost)
    output_tokens: int = 0
    total_tokens: int = 0                   # input + output
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
    """
    Accumulates token counts across all turns in one codex exec run.

    Uses raw input_tokens (not net of cache) so measurements are independent
    of OpenAI's server-side Automatic Prompt Caching state. Cached tokens are
    a billing discount on the server side, but the model still processes the
    full context — and crucially, the cache warm/cold state varies across
    scenario runs (scenario 1 starts cold; later scenarios benefit from prior
    warm-up), which would skew per-scenario averages if we subtracted them.
    """
    input_tokens: int = 0        # raw input_tokens — cache-state independent
    output_tokens: int = 0
    turns: list[dict] = field(default_factory=list)  # per-turn breakdown for --debug

    @property
    def total(self) -> int:
        return self.input_tokens + self.output_tokens

    @property
    def net_input_tokens(self) -> int:
        """input_tokens minus cached_input_tokens — actual processing cost."""
        return sum(t["net"] for t in self.turns)

    def add_turn(self, input_tokens: int, cached_tokens: int, output_tokens: int) -> None:
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        self.turns.append({
            "input": input_tokens,
            "cached": cached_tokens,
            "net": input_tokens - cached_tokens,
            "output": output_tokens,
        })


def run_codex(
    prompt: str,
    codex_cmd: str,
    isolate_mcp: bool,
    debug: bool = False,
) -> tuple[str, float, int, list[str], _Usage]:
    """
    Run `codex exec` and return (response_text, elapsed_s, tool_call_count, tool_names, usage).

    Isolation flags applied every run:
      --ephemeral           no session files persisted; each run starts fresh
      --ignore-user-config  (Condition A only) skip ~/.codex/config.toml → no MCP servers

    Token counts come from turn.completed events (JSONL).
    net_input_tokens = Σ(input_tokens - cached_input_tokens) per turn.
    """
    tmp_out = tempfile.mktemp(suffix=".txt")
    # Both conditions start from the same clean slate (--ignore-user-config).
    # Condition B additionally injects errordog MCP via -c so the only
    # variable between A and B is MCP tool availability — not other user config.
    cmd = [codex_cmd, "exec", "--sandbox", "read-only", "--ephemeral", "--ignore-user-config"]
    if not isolate_mcp:
        # Inject errordog MCP server config inline
        cmd += [
            "-c", f'mcp_servers.errordog.command="uv"',
            "-c", (
                f'mcp_servers.errordog.args='
                f'["run", "--directory", "{PROJECT_DIR}", "python", "-m", "errordog", "serve"]'
            ),
            "-c", 'mcp_servers.errordog.default_tools_approval_mode="approve"',
        ]
    cmd += ["--color", "never", "--json", "--output-last-message", tmp_out, "-"]

    t0 = time.perf_counter()
    try:
        proc = subprocess.run(
            cmd,
            input=prompt,
            capture_output=True,
            text=True,
            timeout=MAX_WAIT_S,
        )
    except subprocess.TimeoutExpired:
        return f"(timeout after {MAX_WAIT_S}s)", MAX_WAIT_S, 0, [], _Usage()
    elapsed = time.perf_counter() - t0

    # Parse JSONL: collect tool calls and accumulate token usage
    tool_calls = 0
    tool_names: list[str] = []
    usage = _Usage()
    lines = proc.stdout.splitlines()

    for raw in lines:
        try:
            event = json.loads(raw)
        except json.JSONDecodeError:
            continue

        etype = event.get("type")

        if etype == "item.completed" and event.get("item", {}).get("type") == "mcp_tool_call":
            tool_calls += 1
            tool_names.append(event["item"].get("tool", "unknown"))

        elif etype == "turn.completed":
            u = event.get("usage", {})
            # Subtract cached tokens: they represent context repeated from prior turns,
            # not fresh tokens processed in this turn.
            usage.add_turn(
                input_tokens=u.get("input_tokens", 0),
                cached_tokens=u.get("cached_input_tokens", 0),
                output_tokens=u.get("output_tokens", 0),
            )

    if debug:
        cond_label = "A (no MCP)" if isolate_mcp else "B (MCP)"
        print(f"\n  [debug {cond_label}] JSONL events: {len(lines)} lines")
        print(f"  [debug {cond_label}] tool_names: {tool_names}")
        print(f"  [debug {cond_label}] per-turn tokens:")
        for i, t in enumerate(usage.turns):
            print(f"    turn {i+1}: input={t['input']:,}  cached={t['cached']:,}  "
                  f"net={t['net']:,}  output={t['output']:,}")
        print(f"  [debug {cond_label}] total input={usage.input_tokens:,}  "
              f"output={usage.output_tokens:,}")

    # Read final response
    out_path = Path(tmp_out)
    if out_path.exists():
        response = out_path.read_text(encoding="utf-8").strip()
        out_path.unlink(missing_ok=True)
    else:
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
    stacktrace: str, keywords: list[str], codex_cmd: str, debug: bool = False
) -> ConditionResult:
    result = ConditionResult(condition="A")
    try:
        response, elapsed, _, _, usage = run_codex(
            PROMPT_A.format(stacktrace=stacktrace),
            codex_cmd=codex_cmd,
            isolate_mcp=True,
            debug=debug,
        )
        result.final_response = response
        result.response_time_s = elapsed
        result.input_tokens = usage.input_tokens
        result.net_input_tokens = usage.net_input_tokens
        result.output_tokens = usage.output_tokens
        result.total_tokens = usage.total
        result.matched_keywords, result.specificity_score, result.root_cause_identified = (
            score_response(response, keywords)
        )
    except Exception as exc:
        result.error = str(exc)
    return result


def run_condition_b(
    error_id: str, keywords: list[str], codex_cmd: str, debug: bool = False
) -> ConditionResult:
    result = ConditionResult(condition="B")
    try:
        response, elapsed, tool_calls, tool_names, usage = run_codex(
            PROMPT_B.format(error_id=error_id),
            codex_cmd=codex_cmd,
            isolate_mcp=False,
            debug=debug,
        )
        result.final_response = response
        result.response_time_s = elapsed
        result.tool_calls = tool_calls
        result.tool_names = tool_names
        result.input_tokens = usage.input_tokens
        result.net_input_tokens = usage.net_input_tokens
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


def print_scenario(sr: ScenarioResult) -> None:
    a, b = sr.condition_a, sr.condition_b
    print(f"\n{_SEP}")
    print(f"Scenario : {sr.scenario_name} — {sr.description}")
    print(f"Error ID : {sr.error_id}")
    print(_SEP)
    print(f"{'Metric':<28} {'A: Stacktrace':>16} {'B: Errordog':>18}")
    print(_SEP)
    print(f"{'Input tokens (raw)':<28} {a.input_tokens:>16,} {b.input_tokens:>18,}")
    print(f"{'  net (uncached)':<28} {a.net_input_tokens:>16,} {b.net_input_tokens:>18,}")
    print(f"{'Output tokens':<28} {a.output_tokens:>16,} {b.output_tokens:>18,}")
    print(f"{'Total tokens':<28} {a.total_tokens:>16,} {b.total_tokens:>18,}")
    print(f"{'MCP tool calls':<28} {'0':>16} {b.tool_calls:>18}")
    if b.tool_names:
        unique_names = list(dict.fromkeys(b.tool_names))
        parts = [
            f"{n}×{b.tool_names.count(n)}" if b.tool_names.count(n) > 1 else n
            for n in unique_names
        ]
        print(f"{'  tools used':<28} {'':>16} {', '.join(parts)}")
    print(f"{'Response time (s)':<28} {a.response_time_s:>16.1f} {b.response_time_s:>18.1f}")
    total_kw = len(next(
        (s["ground_truth_keywords"] for s in SCENARIOS if s["name"] == sr.scenario_name), []
    ))
    a_kw = f"{len(a.matched_keywords)}/{total_kw} ({a.specificity_score:.0%})"
    b_kw = f"{len(b.matched_keywords)}/{total_kw} ({b.specificity_score:.0%})"
    print(f"{'Keyword match':<28} {a_kw:>16} {b_kw:>18}")
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
    a_net = [r.condition_a.net_input_tokens for r in results if not r.condition_a.error]
    b_net = [r.condition_b.net_input_tokens for r in results if not r.condition_b.error]
    a_out = [r.condition_a.output_tokens for r in results if not r.condition_a.error]
    b_out = [r.condition_b.output_tokens for r in results if not r.condition_b.error]
    a_tot = [r.condition_a.total_tokens for r in results if not r.condition_a.error]
    b_tot = [r.condition_b.total_tokens for r in results if not r.condition_b.error]
    a_time = [r.condition_a.response_time_s for r in results if not r.condition_a.error]
    b_time = [r.condition_b.response_time_s for r in results if not r.condition_b.error]
    b_tools = [r.condition_b.tool_calls for r in results if not r.condition_b.error]
    a_spec = [r.condition_a.specificity_score for r in results if not r.condition_a.error]
    b_spec = [r.condition_b.specificity_score for r in results if not r.condition_b.error]
    # Keyword coverage: total matched / total possible across all scenarios
    _kw_by_name = {s["name"]: s["ground_truth_keywords"] for s in SCENARIOS}
    a_kw_hit = sum(len(r.condition_a.matched_keywords) for r in results if not r.condition_a.error)
    b_kw_hit = sum(len(r.condition_b.matched_keywords) for r in results if not r.condition_b.error)
    a_kw_tot = sum(
        len(_kw_by_name.get(r.scenario_name, []))
        for r in results if not r.condition_a.error
    )
    b_kw_tot = sum(
        len(_kw_by_name.get(r.scenario_name, []))
        for r in results if not r.condition_b.error
    )

    print(f"{'Avg input tokens (raw)':<28} {avg(a_in):>16,.0f} {avg(b_in):>18,.0f}")
    print(f"{'  avg net (uncached)':<28} {avg(a_net):>16,.0f} {avg(b_net):>18,.0f}")
    print(f"{'Avg output tokens':<28} {avg(a_out):>16,.0f} {avg(b_out):>18,.0f}")
    print(f"{'Avg total tokens':<28} {avg(a_tot):>16,.0f} {avg(b_tot):>18,.0f}")
    print(f"{'Avg MCP tool calls':<28} {'0':>16} {avg(b_tools):>18.1f}")
    print(f"{'Avg response time (s)':<28} {avg(a_time):>16.1f} {avg(b_time):>18.1f}")
    print(f"{'Avg specificity':<28} {avg(a_spec):>15.0%} {avg(b_spec):>17.0%}")
    a_kw = f"{a_kw_hit}/{a_kw_tot} ({a_kw_hit/a_kw_tot:.0%})" if a_kw_tot else "n/a"
    b_kw = f"{b_kw_hit}/{b_kw_tot} ({b_kw_hit/b_kw_tot:.0%})" if b_kw_tot else "n/a"
    print(f"{'Keyword coverage':<28} {a_kw:>16} {b_kw:>18}")
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
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Print per-turn token breakdown and full tool_names for each run",
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
        cond_a = run_condition_a(stacktrace, keywords, args.codex, debug=args.debug)
        status_a = f"done ({cond_a.response_time_s}s)" if not cond_a.error else f"ERROR: {cond_a.error[:60]}"
        print(status_a)

        # Step 3: Condition B
        print("  Condition B (Errordog MCP) …", end=" ", flush=True)
        cond_b = run_condition_b(error_id, keywords, args.codex, debug=args.debug)
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
