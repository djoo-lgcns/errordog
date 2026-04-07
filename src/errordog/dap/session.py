"""DAP session state — domain entities for debug session caching."""

from dataclasses import dataclass, field


@dataclass
class StackFrame:
    """One frame from a DAP stackTrace response."""

    id: int
    name: str
    line: int
    source_path: str | None = None


@dataclass
class Variable:
    """One variable from a DAP variables response."""

    name: str
    value: str
    type: str | None = None
    variables_reference: int = 0


@dataclass
class DebugSession:
    """Mutable state cached from a live or mock debug session."""

    mode: str = "proxy"  # "proxy" or "mock"
    thread_id: int | None = None
    frame_id: int | None = None
    stack_trace: list[StackFrame] = field(default_factory=list)
    # keyed by variablesReference (proxy) or frame index (mock)
    variables: dict[int, list[Variable]] = field(default_factory=dict)
    error_id: str | None = None
