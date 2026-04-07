"""Mock DAP adapter — responds to IDE requests from an ESF snapshot."""

import asyncio
import logging

from errordog.dap.protocol import write_message
from errordog.dap.session import DebugSession, StackFrame, Variable
from errordog.store import SnapshotStore

logger = logging.getLogger(__name__)


class MockAdapter:
    """Responds to DAP requests using a stored ESF snapshot (no live debugpy)."""

    def __init__(self, error_id: str) -> None:
        self.error_id = error_id
        self.session = DebugSession(mode="mock", error_id=error_id)
        self._seq = 1
        self._loaded = False
        self._snapshot_meta: dict = {}

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
        # frame index == variablesReference (synthetic, used in scopes response)
        self.session.variables = {
            i: [Variable(name=k, value=v) for k, v in f.locals.items()]
            for i, f in enumerate(snapshot.frames)
        }
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
                    "column": 0,
                    "source": {"path": f.source_path} if f.source_path else {},
                }
                for f in self.session.stack_trace
            ]
            await write_message(writer, self._response(msg, {
                "stackFrames": frames,
                "totalFrames": len(frames),
            }))

        elif command == "scopes":
            frame_id = msg.get("arguments", {}).get("frameId", 0)
            # Use frame_id as variablesReference so variables requests can look up by frame index
            await write_message(writer, self._response(msg, {
                "scopes": [{
                    "name": "Locals",
                    "variablesReference": frame_id,
                    "expensive": False,
                }],
            }))

        elif command == "variables":
            var_ref = msg.get("arguments", {}).get("variablesReference", 0)
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

        elif command == "disconnect":
            await write_message(writer, self._response(msg))
            return True

        else:
            logger.debug("MockAdapter: unsupported command %r", command)
            await write_message(writer, self._response(msg, {
                "error": {"id": 2, "format": f"Not supported in mock mode: {command}"},
            }, success=False))

        return False
