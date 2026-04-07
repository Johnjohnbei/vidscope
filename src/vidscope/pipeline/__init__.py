"""VidScope pipeline layer.

Hosts the generic :class:`PipelineRunner` and helpers that compose a
sequence of :class:`~vidscope.ports.pipeline.Stage` instances into a
single transactional flow.

Imports from :mod:`vidscope.domain` and :mod:`vidscope.ports` only —
never a concrete adapter.
"""

from __future__ import annotations

from vidscope.pipeline.runner import PipelineRunner, RunResult, StageOutcome

__all__ = ["PipelineRunner", "RunResult", "StageOutcome"]
