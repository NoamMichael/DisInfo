"""Lightweight observability for the pipeline.

Tracks events, API call timings, and pipeline stage durations.
Everything lives in-memory — no external deps.
"""

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

@dataclass
class Event:
    timestamp: str
    stage: str
    kind: str  # "start", "end", "api_call", "error", "info"
    message: str
    duration_ms: float | None = None
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = {
            "timestamp": self.timestamp,
            "stage": self.stage,
            "kind": self.kind,
            "message": self.message,
        }
        if self.duration_ms is not None:
            d["duration_ms"] = round(self.duration_ms, 1)
        if self.metadata:
            d["metadata"] = self.metadata
        return d


class PipelineObserver:
    def __init__(self):
        self.events: list[Event] = []
        self._timers: dict[str, float] = {}

    def clear(self):
        self.events.clear()
        self._timers.clear()

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat(timespec="milliseconds")

    def log(self, stage: str, kind: str, message: str, **metadata):
        evt = Event(
            timestamp=self._now(),
            stage=stage,
            kind=kind,
            message=message,
            metadata=metadata if metadata else {},
        )
        self.events.append(evt)
        return evt

    def start(self, stage: str, message: str = ""):
        self._timers[stage] = time.monotonic()
        return self.log(stage, "start", message or f"{stage} started")

    def end(self, stage: str, message: str = "", **metadata):
        start_time = self._timers.pop(stage, None)
        duration_ms = (time.monotonic() - start_time) * 1000 if start_time else None
        evt = self.log(stage, "end", message or f"{stage} completed", **metadata)
        evt.duration_ms = duration_ms
        return evt

    def api_call(self, tool: str, endpoint: str, status: str, duration_ms: float, **metadata):
        evt = self.log(
            tool, "api_call",
            f"{tool} {endpoint} -> {status}",
            endpoint=endpoint, status=status, **metadata,
        )
        evt.duration_ms = duration_ms
        return evt

    def error(self, stage: str, message: str, **metadata):
        return self.log(stage, "error", message, **metadata)

    def info(self, stage: str, message: str, **metadata):
        return self.log(stage, "info", message, **metadata)

    def get_events(self, stage: str | None = None, kind: str | None = None) -> list[dict]:
        filtered = self.events
        if stage:
            filtered = [e for e in filtered if e.stage == stage]
        if kind:
            filtered = [e for e in filtered if e.kind == kind]
        return [e.to_dict() for e in filtered]

    def summary(self) -> dict:
        api_calls = [e for e in self.events if e.kind == "api_call"]
        errors = [e for e in self.events if e.kind == "error"]
        stages = [e for e in self.events if e.kind == "end" and e.duration_ms is not None]

        total_api_ms = sum(e.duration_ms or 0 for e in api_calls)
        total_pipeline_ms = sum(e.duration_ms or 0 for e in stages)

        by_tool: dict[str, dict] = {}
        for e in api_calls:
            tool = e.stage
            if tool not in by_tool:
                by_tool[tool] = {"calls": 0, "total_ms": 0, "errors": 0}
            by_tool[tool]["calls"] += 1
            by_tool[tool]["total_ms"] = round(by_tool[tool]["total_ms"] + (e.duration_ms or 0), 1)
            if "error" in (e.metadata.get("status", "") or "").lower():
                by_tool[tool]["errors"] += 1

        return {
            "total_events": len(self.events),
            "api_calls": len(api_calls),
            "errors": len(errors),
            "total_api_time_ms": round(total_api_ms, 1),
            "total_pipeline_time_ms": round(total_pipeline_ms, 1),
            "by_tool": by_tool,
            "stage_timings": {
                e.stage: round(e.duration_ms, 1) for e in stages
            },
        }


# Global singleton
obs = PipelineObserver()
