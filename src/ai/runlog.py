"""Per-run logging for the pipeline.

Each question gets a short run id. Every stage reports through `RunLog.step`, which
writes one timestamped log line and returns a `progress` event for the UI:

    12:04:31.218 INFO  [run a1b2c3] tier2      passed   top: net_debt 0.43, ... (+184 ms)

Stages:   rule, tier1, tier2, tier3, roadmap, narrative
Statuses: running   the stage has started
          done      the stage finished and decided / produced its result
          passed    the stage ran but did not decide, so the next tier takes over
          skipped   the stage was not needed or is not available
          failed    the stage errored
"""

import logging
import time
import uuid

LOGGER_NAME = "finance_map.pipeline"
STAGES = ("rule", "tier1", "tier2", "tier3", "roadmap", "narrative")
STATUSES = ("running", "done", "passed", "skipped", "failed")


class RunLog:
    def __init__(self, question: str, logger: logging.Logger | None = None):
        self.run_id = uuid.uuid4().hex[:6]
        self.log = logger or logging.getLogger(LOGGER_NAME)
        self.t0 = time.perf_counter()
        self._stage_t0: dict[str, float] = {}
        self.outcome = "unfinished"
        short = question if len(question) <= 120 else question[:117] + "..."
        self.log.info("[run %s] question  %r", self.run_id, short)

    def elapsed_ms(self) -> int:
        return round((time.perf_counter() - self.t0) * 1000)

    def step(self, stage: str, status: str, detail: str = "", debug: str | None = None) -> dict:
        """Log one stage transition and return the matching progress event."""
        now = time.perf_counter()
        took = ""
        if status == "running":
            self._stage_t0.setdefault(stage, now)  # a second "running" update keeps the original start
        elif stage in self._stage_t0:
            took = f", stage {round((now - self._stage_t0.pop(stage)) * 1000)} ms"
        level = logging.WARNING if status == "failed" else logging.INFO
        self.log.log(
            level,
            "[run %s] %-9s %-8s %s (+%d ms%s)",
            self.run_id, stage, status, detail, self.elapsed_ms(), took,
        )
        if debug:
            self.log.debug("[run %s] %-9s detail   %s", self.run_id, stage, debug)
        return {"event": "progress", "stage": stage, "status": status, "detail": detail,
                "ms": self.elapsed_ms()}

    def finish(self) -> None:
        self.log.info("[run %s] finished  %s in %d ms", self.run_id, self.outcome, self.elapsed_ms())


def configure_logging(level: str = "INFO") -> logging.Logger:
    """One stream handler on the 'finance_map' logger (idempotent)."""
    root = logging.getLogger("finance_map")
    if not any(getattr(h, "_finance_map", False) for h in root.handlers):
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s.%(msecs)03d %(levelname)-5s %(message)s", "%H:%M:%S"))
        handler._finance_map = True  # type: ignore[attr-defined]
        root.addHandler(handler)
        root.propagate = False
    root.setLevel(level.upper())
    return root
