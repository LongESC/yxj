"""LangGraph Agent 回调 — token 统计、步骤记录、LangSmith 标签"""

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)


class AgentCallback:
    """Agent 执行过程中的回调记录"""

    def __init__(self):
        self.steps: list[dict] = []
        self._step_start: float = 0

    def on_node_enter(self, node_name: str) -> None:
        self._step_start = time.time()
        logger.debug("Agent → %s", node_name)

    def on_node_exit(self, node_name: str, **kwargs: Any) -> None:
        duration_ms = int((time.time() - self._step_start) * 1000)
        step = {"node": node_name, "duration_ms": duration_ms, **kwargs}
        self.steps.append(step)

    def on_tool_call(self, tool_name: str, tool_args: dict) -> None:
        logger.info("Tool call: %s(%s)", tool_name, tool_args)

    def on_tool_result(self, tool_name: str, result: str) -> None:
        logger.info("Tool result: %s → %d chars", tool_name, len(result))

    def get_metadata(self) -> dict:
        return {
            "steps": self.steps,
            "total_duration_ms": sum(s.get("duration_ms", 0) for s in self.steps),
        }
