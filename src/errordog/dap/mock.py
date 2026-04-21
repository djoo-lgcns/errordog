"""Mock DAP adapter — responds to IDE requests from an ESF snapshot."""

import ast
import asyncio
import logging
from typing import Any

from errordog.dap.protocol import write_message
from errordog.dap.session import DebugSession, StackFrame, Variable
from errordog.store import SnapshotStore

logger = logging.getLogger(__name__)

# Frame indices occupy 0..N-1; drill-down refs start here to avoid collisions.
_DRILLDOWN_REF_BASE = 1000


def _make_source(path: str | None) -> dict:
    """Build a DAP source object, marking internal/frozen frames as deemphasized."""
    if not path:
        return {}
    if path.startswith("<"):  # e.g. <frozen runpy>, <string>
        return {"name": path, "presentationHint": "deemphasized"}
    return {"path": path}


class MockAdapter:
    """Responds to DAP requests using a stored ESF snapshot (no live debugpy)."""

    def __init__(self, error_id: str) -> None:
        self.error_id = error_id
        self.session = DebugSession(mode="mock", error_id=error_id)
        self._seq = 1
        self._loaded = False
        self._snapshot_meta: dict = {}
        self._drilldown: dict[int, list[dict]] = {}  # ref → child variable dicts
        self._next_ref = _DRILLDOWN_REF_BASE

    # ── message builders ──────────────────────────────────────────────────

    def _next_seq(self) -> int:
        seq = self._seq
        self._seq += 1
        return seq

    def _response(self, request: dict, body: dict | None = None, *, success: bool = True) -> dict:
        return {
            "seq": self._next_seq(),
            "type": "response",
            "request_seq": request["seq"],
            "command": request["command"],
            "success": success,
            "body": body if body is not None else {},
        }

    def _event(self, event: str, body: dict | None = None) -> dict:
        return {
            "seq": self._next_seq(),
            "type": "event",
            "event": event,
            "body": body if body is not None else {},
        }

    # ── drill-down ref registry ────────────────────────────────────────────

    def _register(self, value: Any) -> int:
        """Register expandable value in drill-down map. Returns variablesReference (0 if not expandable)."""
        if isinstance(value, dict):
            ref = self._next_ref
            self._next_ref += 1
            self._drilldown[ref] = [
                self._make_var(str(k), v) for k, v in value.items()
            ]
            return ref
        if isinstance(value, (list, tuple)):
            ref = self._next_ref
            self._next_ref += 1
            self._drilldown[ref] = [
                self._make_var(f"[{i}]", v) for i, v in enumerate(value)
            ]
            return ref
        return 0

    def _make_var(self, name: str, value: Any) -> dict:
        """Build a DAP variable dict for any Python value, with recursive drill-down."""
        value_repr = repr(value)
        var_ref = self._register(value)
        return {
            "name": name,
            "value": value_repr,
            "type": type(value).__name__,
            "variablesReference": var_ref,
        }

    def _parse_repr(self, value_repr: str) -> Any:
        """Try to parse a repr string back to a Python value via ast.literal_eval."""
        try:
            return ast.literal_eval(value_repr)
        except (ValueError, SyntaxError):
            return value_repr  # fall back to the raw string

    # ── snapshot loading ──────────────────────────────────────────────────

    def _load(self) -> bool:
        """Load ESF snapshot into session state. Returns True on success."""
        store = SnapshotStore()
        try:
            snapshot = store.get_snapshot(self.error_id)
        except (FileNotFoundError, ValueError) as exc:
            logger.error("MockAdapter: cannot load snapshot %s: %s", self.error_id, exc)
            return False

        self.session.thread_id = 1
        self.session.stack_trace = [
            StackFrame(id=i, name=f.function_name, line=f.line_number, source_path=f.file_path)
            for i, f in enumerate(snapshot.frames)
        ]
        self.session.frame_id = 0

        # Build variables with drill-down refs eagerly at load time.
        # Frame index i == variablesReference used in scopes response.
        self.session.variables = {}
        for i, f in enumerate(snapshot.frames):
            frame_vars: list[Variable] = []
            for k, v_repr in f.locals.items():
                parsed = self._parse_repr(v_repr)
                var_ref = self._register(parsed)
                frame_vars.append(Variable(
                    name=k,
                    value=v_repr,
                    type=type(parsed).__name__ if not isinstance(parsed, str) else None,
                    variables_reference=var_ref,
                ))
            self.session.variables[i] = frame_vars

        self._snapshot_meta = {
            "exception_type": snapshot.exception_type,
            "exception_message": snapshot.exception_message,
        }
        self._loaded = True
        return True

    # ── request handler ───────────────────────────────────────────────────

    async def process(self, msg: dict, writer: asyncio.StreamWriter) -> bool:
        """Handle one DAP request. Returns True when the session should end."""
        command = msg.get("command", "")

        if command == "initialize":
            await write_message(writer, self._response(msg, {
                "supportsConfigurationDoneRequest": False,
            }))
            await write_message(writer, self._event("initialized"))

        elif command == "attach":
            if self._load():
                await write_message(writer, self._response(msg))
                await write_message(writer, self._event("stopped", {
                    "reason": "exception",
                    "threadId": self.session.thread_id,
                    "description": self._snapshot_meta.get("exception_type", "error"),
                    "text": self._snapshot_meta.get("exception_message", ""),
                    "allThreadsStopped": True,
                }))
            else:
                await write_message(writer, self._response(msg, {
                    "error": {"id": 1, "format": f"Snapshot not found: {self.error_id}"},
                }, success=False))
                return True

        elif command == "configurationDone":
            await write_message(writer, self._response(msg))

        elif command == "threads":
            await write_message(writer, self._response(msg, {
                "threads": [{"id": 1, "name": "MainThread"}],
            }))

        elif command == "stackTrace":
            frames = [
                {
                    "id": f.id,
                    "name": f.name,
                    "line": f.line,
                    "column": 1,
                    "source": _make_source(f.source_path),
                }
                for f in self.session.stack_trace
            ]
            await write_message(writer, self._response(msg, {
                "stackFrames": frames,
                "totalFrames": len(frames),
            }))

        elif command == "scopes":
            frame_id = msg.get("arguments", {}).get("frameId", 0)
            await write_message(writer, self._response(msg, {
                "scopes": [{
                    "name": "Locals",
                    "variablesReference": frame_id,
                    "expensive": False,
                }],
            }))

        elif command == "variables":
            var_ref = msg.get("arguments", {}).get("variablesReference", 0)
            if var_ref in self._drilldown:
                # Drill-down into a dict/list value
                await write_message(writer, self._response(msg, {
                    "variables": self._drilldown[var_ref],
                }))
            else:
                # Frame locals (var_ref == frame index)
                variables = self.session.variables.get(var_ref, [])
                await write_message(writer, self._response(msg, {
                    "variables": [
                        {
                            "name": v.name,
                            "value": v.value,
                            "type": v.type or "",
                            "variablesReference": v.variables_reference,
                        }
                        for v in variables
                    ],
                }))

        elif command == "evaluate":
            args = msg.get("arguments", {})
            expression = args.get("expression", "")
            frame_id = args.get("frameId", 0)
            frame_vars = self.session.variables.get(frame_id)
            if frame_vars is None:
                await write_message(writer, self._response(msg, {
                    "result": f"No frame with id {frame_id}",
                    "type": "",
                    "variablesReference": 0,
                }))
            else:
                namespace: dict[str, Any] = {}
                for v in frame_vars:
                    parsed = self._parse_repr(v.value)
                    if parsed != v.value or v.value == repr(parsed):
                        namespace[v.name] = parsed
                try:
                    result = eval(expression, {"__builtins__": __builtins__}, namespace)
                    var_ref = self._register(result)
                    await write_message(writer, self._response(msg, {
                        "result": repr(result),
                        "type": type(result).__name__,
                        "variablesReference": var_ref,
                    }))
                except Exception as e:
                    await write_message(writer, self._response(msg, {
                        "result": f"{type(e).__name__}: {e}",
                        "type": "",
                        "variablesReference": 0,
                    }))

        elif command == "disconnect":
            await write_message(writer, self._response(msg))
            return True

        else:
            logger.debug("MockAdapter: unsupported command %r", command)
            await write_message(writer, self._response(msg, {
                "error": {"id": 2, "format": f"Not supported in mock mode: {command}"},
            }, success=False))

        return False
