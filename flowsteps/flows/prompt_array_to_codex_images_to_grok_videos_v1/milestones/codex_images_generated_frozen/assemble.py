"""Request built-in Codex ImageGen work, then freeze the returned raster files."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any


STEP_ID = "codex_images_generated_frozen"
CODEBASE = Path(__file__).resolve().parents[5]
FLOW_DIR = Path(__file__).resolve().parents[2]
GEM_PATH = FLOW_DIR / "references" / f"{STEP_ID}.md"


def _load_tool(tool_id: str) -> Any:
    path = CODEBASE / "flowsteps" / "tools" / tool_id / "tool.py"
    spec = importlib.util.spec_from_file_location(f"m8m_{tool_id}", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load tool: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _batch(value: Any) -> dict[str, Any]:
    current = value
    for _ in range(5):
        if isinstance(current, dict) and current.get("schema") == "visual_prompt_batch_v1":
            return current
        if not isinstance(current, dict):
            break
        for key in ("value", "batch", "prompt_batch", "prompt_batch_ready"):
            if isinstance(current.get(key), dict):
                current = current[key]
                break
        else:
            outputs = current.get("outputs")
            if isinstance(outputs, dict) and isinstance(outputs.get("batch"), dict):
                current = outputs["batch"]
                continue
            break
    raise ValueError("codex_images_generated_frozen needs the chosen prompt_batch output")


def _instruction(batch: dict[str, Any], findings: list[str] | None = None) -> str:
    correction = ""
    if findings:
        correction = "\n\nThe previous draft was rejected. Generate fresh replacements as needed and correct every finding:\n- " + "\n- ".join(findings)
    return (
        "Use Codex's built-in image_gen tool in this isolated worker. Make exactly one separate "
        "image_gen call per item below, sequentially in array order. Pass each item's prompt "
        "verbatim as the generation prompt; it is already detailed, so do not augment it. Require "
        "a vertical 9:16 raster and no watermark. Do not use a CLI, API key, REST API, prior image, "
        "or one call for multiple items. The built-in tool writes under Codex generated_images; do "
        "not copy or edit those files. After all calls finish, write only the draft JSON object with "
        "count and images. Each images item must contain exactly id, index, source_prompt, "
        "image_prompt, and generated_file. source_prompt and image_prompt must both equal the frozen "
        "prompt byte-for-byte; generated_file must be the absolute local file from that call. Do not "
        "include ok, PASS, Markdown, previews, or commentary.\n\nMILESTONE GEM\n\n"
        + GEM_PATH.read_text(encoding="utf-8")
        + "\n\nFROZEN PROMPT BATCH\n\n"
        + json.dumps(batch, ensure_ascii=False, indent=2)
        + correction
    )


def _need_model(batch: dict[str, Any], findings: list[str] | None = None) -> dict[str, Any]:
    return {
        "_flowstep": "NEED_MODEL",
        "model": "completion",
        "model_request": {
            "milestone": STEP_ID,
            "flowstep": "generate_with_codex_builtin_imagegen",
            "required_builtin_tool": "image_gen",
            "gem_path": str(GEM_PATH),
            "prompt_batch": batch,
            "instruction": _instruction(batch, findings),
        },
    }


def run(input_data: dict[str, Any], draft: dict[str, Any] | None = None, **kwargs: Any) -> dict[str, Any]:
    batch = _batch(input_data.get("prompt_batch") or input_data)
    if draft is None:
        return _need_model(batch)
    run_dir_raw = kwargs.get("run_dir")
    if not run_dir_raw:
        raise ValueError("codex_images_generated_frozen needs run_dir")
    run_dir = Path(str(run_dir_raw)).resolve()
    work_dir = run_dir / "milestones" / STEP_ID / "work" / "imported_images"
    request_path = run_dir / "request.json"
    not_before = request_path.stat().st_mtime if request_path.is_file() else 0.0
    freezer = _load_tool("freeze_codex_image_batch")
    judge = _load_tool("codex_images_generated_judge")
    try:
        frozen = freezer.run({
            "prompt_batch": batch,
            "draft": draft,
            "work_dir": str(work_dir),
            "not_before_epoch": not_before,
        })
    except (OSError, ValueError) as exc:
        return _need_model(batch, [str(exc)])
    receipt = judge.run({
        "prompt_batch": batch,
        "frozen": frozen,
        "gem_path": str(GEM_PATH),
    })
    if receipt.get("ok") is not True:
        return _need_model(batch, [str(item) for item in receipt.get("findings") or []])
    return {
        "outputs": {"images": frozen["images"], "manifest": frozen["manifest"]},
        "receipt": receipt,
    }
