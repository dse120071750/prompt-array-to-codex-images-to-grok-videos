"""Deterministically judge a frozen Codex ImageGen batch."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def run(input_data: dict[str, Any], params: dict[str, Any] | None = None, **_: Any) -> dict[str, Any]:
    del params
    batch = input_data.get("prompt_batch") if isinstance(input_data.get("prompt_batch"), dict) else {}
    frozen = input_data.get("frozen") if isinstance(input_data.get("frozen"), dict) else {}
    items = batch.get("items") if isinstance(batch.get("items"), list) else []
    images = frozen.get("images") if isinstance(frozen.get("images"), list) else []
    manifest = frozen.get("manifest") if isinstance(frozen.get("manifest"), dict) else {}
    findings: list[str] = []
    if not items:
        findings.append("the frozen prompt batch is empty")
    if len(images) != len(items) or manifest.get("count") != len(items):
        findings.append("image count must equal the frozen prompt count")
    if manifest.get("schema") != "codex_image_batch_v1" or manifest.get("provider") != "codex_builtin_imagegen":
        findings.append("manifest must identify Codex built-in ImageGen")
    manifest_items = manifest.get("items") if isinstance(manifest.get("items"), list) else []
    if len(manifest_items) != len(items):
        findings.append("manifest item count is incomplete")
    for index, expected in enumerate(items):
        if index >= len(images) or index >= len(manifest_items):
            break
        image = images[index]
        manifest_item = manifest_items[index]
        expected_id = f"prompt-{index + 1:03d}"
        if not isinstance(image, dict) or not isinstance(manifest_item, dict):
            findings.append(f"image {index} is malformed")
            continue
        if image != manifest_item:
            findings.append(f"image {index} and manifest mapping differ")
        if image.get("id") != f"prompt_{index + 1:03d}" or image.get("stable_id") != expected_id or image.get("index") != index:
            findings.append(f"image {index} has the wrong stable ID/order")
        if image.get("source_prompt") != expected.get("prompt") or image.get("image_prompt") != expected.get("prompt"):
            findings.append(f"image {index} changed its source prompt")
        path = Path(str(image.get("path") or ""))
        if not path.is_file() or path.stat().st_size != image.get("bytes"):
            findings.append(f"image {index} file or byte count is invalid")
        if not isinstance(image.get("sha256"), str) or len(image["sha256"]) != 64:
            findings.append(f"image {index} has no valid checksum")
        width, height = image.get("width"), image.get("height")
        if not isinstance(width, int) or not isinstance(height, int) or height <= width:
            findings.append(f"image {index} is not a validated portrait raster")
    receipt: dict[str, Any] = {
        "ok": not findings,
        "code": "pass" if not findings else "rejected",
        "findings": findings,
        "count": len(images),
        "provider": "codex_builtin_imagegen",
    }
    if input_data.get("gem_path"):
        receipt["gem"] = str(input_data["gem_path"])
    return receipt
