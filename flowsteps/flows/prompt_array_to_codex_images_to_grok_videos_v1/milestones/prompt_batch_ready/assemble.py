"""Validate and freeze the ordered visual prompt batch."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any


CODEBASE = Path(__file__).resolve().parents[5]
TOOL_PATH = CODEBASE / "flowsteps" / "tools" / "prepare_visual_prompt_batch" / "tool.py"


def _tool() -> Any:
    spec = importlib.util.spec_from_file_location("prepare_visual_prompt_batch", TOOL_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load tool: {TOOL_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run(input_data: dict[str, Any], draft: dict[str, Any] | None = None, **_: Any) -> dict[str, Any]:
    del draft
    request = input_data.get("request")
    if not isinstance(request, dict):
        raise ValueError("prompt_batch_ready needs user.request")
    return {"outputs": {"batch": _tool().run(request)}}
