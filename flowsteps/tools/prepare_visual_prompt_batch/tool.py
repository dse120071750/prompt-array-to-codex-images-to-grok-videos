"""Freeze an ordered prompt batch for Codex ImageGen and Grok image-to-video."""

from __future__ import annotations

from typing import Any


IMAGE_SETTINGS = {"provider": "codex_builtin_imagegen", "aspect_ratio": "9:16"}
VIDEO_SETTINGS = {"duration_seconds": 6, "aspect_ratio": "9:16", "resolution": "720p"}


def run(input_data: dict[str, Any], draft: dict[str, Any] | None = None, **_: Any) -> dict[str, Any]:
    del draft
    if set(input_data) != {"prompts"}:
        unexpected = sorted(set(input_data) - {"prompts"})
        missing = "prompts" not in input_data
        detail = []
        if missing:
            detail.append("missing prompts")
        if unexpected:
            detail.append("unsupported fields: " + ", ".join(unexpected))
        raise ValueError("request must contain exactly prompts (" + "; ".join(detail) + ")")
    prompts = input_data.get("prompts")
    if not isinstance(prompts, list) or not prompts:
        raise ValueError("prompts must be a non-empty array")
    items: list[dict[str, Any]] = []
    for index, prompt in enumerate(prompts):
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError(f"prompts[{index}] must be a non-blank string")
        items.append({"id": f"prompt-{index + 1:03d}", "index": index, "prompt": prompt})
    return {
        "schema": "visual_prompt_batch_v1",
        "count": len(items),
        "image": dict(IMAGE_SETTINGS),
        "video": dict(VIDEO_SETTINGS),
        "items": items,
    }
