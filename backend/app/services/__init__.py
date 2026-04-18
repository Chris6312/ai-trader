from __future__ import annotations

__all__ = [
    "ExecutionError",
    "PaperExecutionEngine",
    "PaperExecutionRequest",
    "PaperExecutionResult",
]


def __getattr__(name: str):
    if name in __all__:
        from app.services.execution_engine import (
            ExecutionError,
            PaperExecutionEngine,
            PaperExecutionRequest,
            PaperExecutionResult,
        )

        exports = {
            "ExecutionError": ExecutionError,
            "PaperExecutionEngine": PaperExecutionEngine,
            "PaperExecutionRequest": PaperExecutionRequest,
            "PaperExecutionResult": PaperExecutionResult,
        }
        return exports[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
