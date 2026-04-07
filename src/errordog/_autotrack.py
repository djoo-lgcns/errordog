"""Auto-activation entry point installed via errordog-autotrack.pth.

Imported by Python on startup in any environment where errordog is installed.
Silently skipped if errordog is broken or unavailable.
"""


def _activate() -> None:
    try:
        import errordog.tracker  # noqa: F401
    except Exception:
        pass


_activate()
